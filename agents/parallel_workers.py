"""Parallel background agent workers with continuous file feeding"""

import queue
import random
import sqlite3
import threading
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime

from agents.archivist_worker import get_archivist_worker
from agents.base import call_agent
from agents.prioritizer_worker import get_prioritizer_worker
from agents.reporter_worker import get_reporter_worker
from agents.response_cleaner import clean_llm_response
from core.config import get_config
from core.db import get_db_path
from core.db_helpers import post_message, save_agent_feedback
from core.file_operations import compute_file_hash, format_file_with_guids
from core.json_parser import parse_json_response
from file_editing.db import log_error


@dataclass
class FileChangeEvent:
    """File change event"""

    event_id: str
    file_path: str
    operation: str
    content: str | None
    content_hash: str | None
    metadata: dict | None
    task_id: str
    timestamp: str
    priority: int = 5  # 1=highest, 10=lowest


class BoundedSet:
    """LRU Bounded Set to prevent memory leaks in tracking recently queued files."""

    def __init__(self, max_size=1000):
        self._data = OrderedDict()
        self.max_size = max_size

    def add(self, item):
        if item in self._data:
            self._data.move_to_end(item)
        else:
            self._data[item] = True
            if len(self._data) > self.max_size:
                self._data.popitem(last=False)

    def __contains__(self, item):
        return item in self._data

    def clear(self):
        self._data.clear()


class BackgroundAgentPool:
    def __init__(self):

        self.event_queue = queue.Queue()
        self.workers = []
        self.feeder_thread = None
        self.running = False
        self.task_id = None
        self.recently_queued = {}
        self._queue_lock = threading.Lock()  # protects recently_queued
        self._state_lock = threading.Lock()  # protects running/workers/feeder/filter
        self.active_agents_filter = None  # None = all active

        # ✅ Load agent configurations from config
        config = get_config()

        self.agent_configs = config.get("background_agents", {})
        self.feeder_config = config.get("background_feeder", {})
        self.feeder_interval = self.feeder_config.get("interval_seconds", 30)
        self.base_feeder_interval = self.feeder_interval  # Store original

        # ✅ Categorize agents by behavior
        self.modification_agents = []  # Review on every file change
        self.random_review_agents = []  # Periodic random review

        for agent_name, agent_config in self.agent_configs.items():
            if not agent_config.get("enabled", True):
                continue

            if agent_config.get("on_modification", False):
                self.modification_agents.append(agent_name)

            if agent_config.get("random_review", False):
                self.random_review_agents.append(agent_name)

    def start(self, task_id: str):
        """Start background workers with granular configuration.

        Safe against concurrent start/stop: if a previous stop left live threads,
        they are joined before new workers are launched.
        """
        with self._state_lock:
            if self.running:
                return

            # Ensure any leftover threads from a timed-out stop are gone
            self._join_workers_unlocked(timeout=1.0)

            self.running = True
            self.task_id = task_id

            all_agents = set(self.modification_agents + self.random_review_agents)
            if not all_agents:
                print("    ⚠️  No background agents enabled")
                return

            with self._queue_lock:
                self.recently_queued = {agent: BoundedSet(max_size=1000) for agent in all_agents}

            for agent_name in all_agents:
                worker = threading.Thread(
                    target=self._worker_loop,
                    args=(agent_name,),
                    daemon=True,
                    name=f"{agent_name}-worker",
                )
                worker.start()
                self.workers.append(worker)

                config = self.agent_configs.get(agent_name, {})
                mod_flag = "on_mod" if config.get("on_modification") else ""
                random_flag = "random" if config.get("random_review") else ""
                flags = f"[{mod_flag}+{random_flag}]" if mod_flag and random_flag else f"[{mod_flag or random_flag}]"
                print(f"    🤖 Started {agent_name} worker {flags}")

            # Start support workers outside the critical section is fine once
            # running=True is visible; they have their own lifecycle.
            self._start_support_workers(task_id)

            self._queue_all_files_for_initial_review()
            self._queue_modified_files()

            if self.random_review_agents:
                self.feeder_thread = threading.Thread(
                    target=self._file_feeder_loop,
                    daemon=True,
                    name="file-feeder",
                )
                self.feeder_thread.start()
                print(f"    🔄 Started continuous file feeder for {len(self.random_review_agents)} agent(s)")

    def _join_workers_unlocked(self, timeout: float = 2.0) -> None:
        """Join feeder + analysis workers. Caller must hold _state_lock."""
        if self.feeder_thread is not None:
            self.feeder_thread.join(timeout=timeout)
            self.feeder_thread = None

        for worker in self.workers:
            worker.join(timeout=timeout)
        self.workers.clear()

        # Drain any leftover events so a restart does not reprocess stale work
        try:
            while True:
                self.event_queue.get_nowait()
        except queue.Empty:
            pass

    def stop(self):
        """Stop all workers including feeder and support workers.

        Sets running=False first so worker loops exit, then joins threads and
        drains the queue. Support workers are stopped after analysis workers.
        """
        from agents.resource_controller_worker import get_resource_controller

        with self._state_lock:
            if not self.running and not self.workers and self.feeder_thread is None:
                return

            self.running = False
            self._join_workers_unlocked(timeout=2.0)

        # Support workers outside state lock (they manage their own threads)
        get_archivist_worker().stop()
        get_prioritizer_worker().stop()
        get_reporter_worker().stop()
        get_resource_controller().stop()

        with self._queue_lock:
            self.recently_queued.clear()

        print("    🛑 Stopped background workers")

    def _start_support_workers(self, task_id: str):
        """Start archivist, prioritizer, reporter, resource controller"""
        from agents.resource_controller_worker import get_resource_controller

        get_archivist_worker().start(task_id)
        get_prioritizer_worker().start(task_id)
        get_reporter_worker().start(task_id)
        get_resource_controller().start(task_id)

    def _queue_all_files_for_initial_review(self):
        """Queue ALL project files for initial review when task starts"""
        try:
            conn = sqlite3.connect(get_db_path())
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT
                    pf.file_path, pf.content, pf.content_hash, pf.last_modified,
                    pf.size_bytes, pf.file_type, fs.summary, fs.purpose, fs.line_count
                FROM project_files pf
                LEFT JOIN file_summaries fs ON pf.file_path = fs.file_path
                WHERE pf.is_binary = 0
                ORDER BY pf.last_modified DESC
            """
            )

            all_files = cursor.fetchall()
            conn.close()

            if not all_files:
                print("    ⚠️  No files found for initial review")
                return

            queued_count = 0

            # Queue all files for each agent
            for _agent_name in self.modification_agents + self.random_review_agents:
                for file_data in all_files:
                    event = self._create_file_event(file_data, "initial_review", priority=3)
                    self.event_queue.put(event)
                    queued_count += 1

            print(f"    🔍 Queued {queued_count} files for initial peer review")

        except Exception as e:
            print(f"    ⚠️  Error queuing files for initial review: {e}")

    def _queue_modified_files(self):
        """Queue files modified since last review - only to modification_agents"""
        try:
            conn = sqlite3.connect(get_db_path())
            cursor = conn.cursor()

            queued_count = 0

            # Only queue to modification_agents
            for agent_name in self.modification_agents:
                cursor.execute(
                    """
                    SELECT
                        pf.file_path, pf.content, pf.content_hash, pf.last_modified,
                        pf.size_bytes, pf.file_type, fs.summary, fs.purpose, fs.line_count,
                        art.last_reviewed_at, art.content_hash_reviewed
                    FROM project_files pf
                    LEFT JOIN file_summaries fs ON pf.file_path = fs.file_path
                    LEFT JOIN agent_review_tracking art ON pf.file_path = art.file_path
                        AND art.agent_name = ?
                    WHERE pf.is_binary = 0
                    AND (
                        art.last_reviewed_at IS NULL
                        OR pf.last_modified > art.last_reviewed_at
                        OR pf.content_hash != art.content_hash_reviewed
                    )
                    ORDER BY pf.last_modified DESC
                """,
                    (agent_name,),
                )

                modified_files = cursor.fetchall()

                for file_data in modified_files:
                    event = self._create_file_event(file_data, "modified_since_review", priority=1)
                    self.event_queue.put(event)

                    with self._queue_lock:
                        if agent_name in self.recently_queued:
                            self.recently_queued[agent_name].add(file_data[0])
                    queued_count += 1

            conn.close()

            if queued_count > 0:
                print(f"    🔥 Queued {queued_count} modified file(s) for {len(self.modification_agents)} agent(s)")

        except Exception as e:
            print(f"    ⚠️  Error queuing modified files: {e}")

    def _file_feeder_loop(self):
        """Feed random files to agents that want them"""
        while self.running:
            try:
                # Dynamic interval based on queue size
                queue_size = self.event_queue.qsize()
                self._adjust_feeder_interval(queue_size)

                time.sleep(self.feeder_interval)

                if not self.running:
                    break

                # Only feed to random_review_agents
                self._feed_random_files()

            except Exception as e:
                print(f"    ⚠️  File feeder error: {e}")
                time.sleep(60)

    def _adjust_feeder_interval(self, queue_size: int):
        """Adjust feeding interval based on queue backlog to prevent overwhelming agents."""
        with self._state_lock:
            if queue_size < 10:
                self.feeder_interval = self.base_feeder_interval
            elif queue_size < 50:
                self.feeder_interval = self.base_feeder_interval * 1.5
            elif queue_size < 100:
                self.feeder_interval = self.base_feeder_interval * 3
            else:
                self.feeder_interval = self.base_feeder_interval * 10
                interval = self.feeder_interval
            interval = self.feeder_interval
        if queue_size > 150:
            print(f"    ⚠️  Queue backlog: {queue_size} items. Slowing feeder to {interval}s")

    def _feed_random_files(self):
        """Feed random files to agents with random_review=true"""
        try:
            conn = sqlite3.connect(get_db_path())
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT
                    pf.file_path, pf.content, pf.content_hash, pf.last_modified,
                    pf.size_bytes, pf.file_type, fs.summary, fs.purpose, fs.line_count
                FROM project_files pf
                LEFT JOIN file_summaries fs ON pf.file_path = fs.file_path
                WHERE pf.is_binary = 0
            """
            )

            all_files = cursor.fetchall()
            conn.close()

            if not all_files:
                return

            # Feed to each random_review agent
            for agent_name in self.random_review_agents:
                agent_config = self.agent_configs.get(agent_name, {})
                files_per_cycle = agent_config.get(
                    "random_files_per_cycle",
                    self.feeder_config.get("files_per_agent_default", 3),
                )

                with self._queue_lock:
                    tracking_set = self.recently_queued.get(agent_name)
                    if tracking_set is None:
                        tracking_set = BoundedSet()
                        self.recently_queued[agent_name] = tracking_set

                    available_files = [f for f in all_files if f[0] not in tracking_set]

                    if not available_files:
                        if agent_name in self.recently_queued:
                            self.recently_queued[agent_name].clear()
                        available_files = all_files

                    selected_files = random.sample(available_files, min(files_per_cycle, len(available_files)))

                    for file_data in selected_files:
                        event = self._create_file_event(file_data, "random_review", priority=7)
                        self.event_queue.put(event)
                        if agent_name in self.recently_queued:
                            self.recently_queued[agent_name].add(file_data[0])

            print(f"    🎲 Fed random files to {len(self.random_review_agents)} agent(s)")

        except Exception as e:
            print(f"    ⚠️  Error feeding random files: {e}")

    def _create_file_event(self, file_data: tuple, operation: str, priority: int) -> FileChangeEvent:
        """Helper to create file event from database row"""
        return FileChangeEvent(
            event_id=str(uuid.uuid4()),
            file_path=file_data[0],
            operation=operation,
            content=file_data[1],
            content_hash=file_data[2],
            metadata={
                "last_modified": file_data[3],
                "size_bytes": file_data[4],
                "file_type": file_data[5],
                "summary": file_data[6],
                "purpose": file_data[7],
                "line_count": file_data[8],
            },
            task_id=self.task_id,
            timestamp=datetime.now().isoformat(),
            priority=priority,
        )

    def queue_file_change(self, file_path: str, operation: str, content: str | None):
        """Queue a file change for immediate processing - only to modification_agents"""
        try:
            content_hash = compute_file_hash(content) if content else None

            conn = sqlite3.connect(get_db_path())
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    pf.last_modified, pf.size_bytes, pf.file_type,
                    fs.summary, fs.purpose, fs.line_count
                FROM project_files pf
                LEFT JOIN file_summaries fs ON pf.file_path = fs.file_path
                WHERE pf.file_path = ?
            """,
                (file_path,),
            )

            result = cursor.fetchone()
            conn.close()

            if result:
                metadata = {
                    "last_modified": result[0],
                    "size_bytes": result[1],
                    "file_type": result[2],
                    "summary": result[3],
                    "purpose": result[4],
                    "line_count": result[5],
                }
            else:
                metadata = None
        except Exception:
            content_hash = None
            metadata = None

        event = FileChangeEvent(
            event_id=str(uuid.uuid4()),
            file_path=file_path,
            operation=operation,
            content=content,
            content_hash=content_hash,
            metadata=metadata,
            task_id=self.task_id,
            timestamp=datetime.now().isoformat(),
            priority=1,  # HIGHEST priority
        )

        # Only queue to modification_agents
        self.event_queue.put(event)

        # ✅ Use Thread Lock to safely update recently queued
        with self._queue_lock:
            for agent_name in self.modification_agents:
                if agent_name in self.recently_queued:
                    self.recently_queued[agent_name].add(file_path)

        print(f"    📤 Queued {file_path} for {len(self.modification_agents)} modification agent(s)")

    def _worker_loop(self, agent_name: str):
        """Main worker loop for a FEEDBACK agent"""
        while self.running:
            # CHECK: Only affects feedback agents in this pool
            # Support workers run in their own threads, unaffected
            #
            # active_agents_filter states:
            #   None          = no filtering (all run)
            #   set()         = all paused
            #   {"agent1"}    = only agent1 runs
            #
            if self.active_agents_filter is not None:
                if len(self.active_agents_filter) == 0:
                    # All FEEDBACK agents paused (support workers still run)
                    time.sleep(5)
                    continue

                if agent_name not in self.active_agents_filter:
                    # This specific feedback agent paused
                    time.sleep(5)
                    continue

            try:
                event = self.event_queue.get(timeout=1.0)
            except queue.Empty:
                continue

            if event.content is None:
                continue

            # ✅ ADD THIS: Small delay before processing to avoid connection storms
            time.sleep(0.5)  # 500ms between agent calls

            self._process_file(agent_name, event)

    def _process_file(self, agent_name: str, event: FileChangeEvent):
        """Process a file with an agent"""

        try:
            file_formatted = format_file_with_guids(event.file_path)

            metadata_str = ""
            if event.metadata:
                metadata_str = "\n**File Metadata:**\n"
                if event.metadata.get("purpose"):
                    metadata_str += f"- Purpose: {event.metadata['purpose']}\n"
                if event.metadata.get("line_count"):
                    metadata_str += f"- Lines: {event.metadata['line_count']}\n"
                if event.metadata.get("last_modified"):
                    metadata_str += f"- Modified: {event.metadata['last_modified'][:19]}\n"

            op_descriptions = {
                "modified_since_review": "modified since your last review",
                "random_review": "selected for periodic review",
                "initial_review": "initial review",
                "create": "newly created",
                "modify": "just modified",
            }
            operation_desc = op_descriptions.get(event.operation, event.operation)

            prompt = f"""File {operation_desc}: {event.file_path}
    {metadata_str}
    {file_formatted}
    Analyze and provide feedback in JSON format."""

            agent_config = self.agent_configs.get(agent_name, {})
            model_override = agent_config.get("model")

            max_attempts = 3

            for attempt in range(1, max_attempts + 1):
                if attempt == 1:
                    # First try: Normal prompt
                    full_prompt = prompt
                elif attempt == 2:
                    # Second try: Add strong JSON enforcement
                    full_prompt = f"""{prompt}

    CRITICAL: Your previous response was not valid JSON.

    You MUST respond with ONLY valid JSON. No explanations, no markdown, no text outside the JSON.

    Start with {{ and end with }}. Nothing before or after."""
                else:
                    # Third try: Ultra-strict prompt
                    full_prompt = """Your previous 2 responses failed JSON validation.

    This is your FINAL attempt. Respond with ONLY this structure:

    {
    "findings": [
        {"priority": "HIGH", "category": "bug", "message": "Issue here", "suggestion": "Fix here"}
    ],
    "summary": "Brief summary"
    }

    START YOUR RESPONSE WITH { RIGHT NOW. NO OTHER TEXT."""

                if attempt > 1:
                    print(f"    🔄 {agent_name}: Retry {attempt}/{max_attempts} with stricter prompt")

                response = call_agent(
                    agent_name,
                    full_prompt,
                    event.task_id,
                    model_override=model_override,
                    auto_resume=False,
                )  # Don't auto-resume on retries

                if not response:
                    continue  # Try again

                # Clean response
                cleaned_response = clean_llm_response(response, agent_name)

                if cleaned_response:
                    # Success!
                    self._parse_and_save_feedback(agent_name, event, cleaned_response)
                    self._update_review_tracking(agent_name, event)
                    return  # Done

            # All attempts failed
            print(f"    ❌ {agent_name}: Failed after {max_attempts} attempts")
            log_error(
                "parallel_workers",
                "json_validation",
                "HIGH",
                f"{agent_name} failed JSON validation after {max_attempts} attempts",
                task_id=event.task_id,
                file_path=event.file_path,
            )

        except Exception as e:
            print(f"    ⚠️  {agent_name} error on {event.file_path}: {e}")
            log_error(
                "parallel_workers",
                "process_file",
                "HIGH",
                f"{agent_name} exception: {e!s}",
                task_id=event.task_id,
                file_path=event.file_path,
            )

    def _parse_and_save_feedback(self, agent_name: str, event: FileChangeEvent, response: str):
        """Parse response and save feedback"""

        try:
            data = parse_json_response(response, expected_keys=None, strict=False, agent_name=agent_name)

            if not data:
                return

            items = None
            array_field_names = [
                "findings",
                "suggestions",
                "documentation_issues",
                "issues",
                "security_findings",
                "items",
                "results",
                "feedback",
                "observations",
                "recommendations",
            ]

            for field_name in array_field_names:
                if field_name in data and isinstance(data[field_name], list):
                    items = data[field_name]
                    print(f"    [i]  {agent_name}: Found items in '{field_name}' field")
                    break

            if items is None or len(items) == 0:
                if any(key in data for key in ["priority", "message", "issue", "finding"]):
                    items = [data]
                    print(f"    [i]  {agent_name}: Treating entire response as single item")
                else:
                    print(f"    ⚠️  {agent_name}: No actionable items found in response")
                    return

            saved_count = 0
            for item in items:
                if not isinstance(item, dict):
                    continue

                priority = (item.get("priority") or item.get("severity") or item.get("level") or "MEDIUM").upper()

                priority_map = {
                    "CRITICAL": "CRITICAL",
                    "URGENT": "CRITICAL",
                    "HIGH": "HIGH",
                    "IMPORTANT": "HIGH",
                    "MEDIUM": "MEDIUM",
                    "MODERATE": "MEDIUM",
                    "LOW": "LOW",
                    "MINOR": "LOW",
                    "INFO": "LOW",
                }
                priority = priority_map.get(priority, "MEDIUM")

                category = (item.get("category") or item.get("type") or item.get("kind") or "other").lower()

                message = item.get("message") or item.get("issue") or item.get("description") or item.get("finding") or item.get("observation") or str(item)

                suggestion = item.get("suggestion") or item.get("fix") or item.get("recommendation") or item.get("solution") or ""

                # ✅ REQUIRE: Must have at least a message
                if not message or len(str(message)) < 10:
                    continue

                save_agent_feedback(
                    agent_name,
                    event.file_path,
                    priority,
                    category,
                    str(message)[:1000],
                    str(suggestion)[:1000] if suggestion else None,
                    event.task_id,
                    event.event_id,
                )
                saved_count += 1

                if priority in ["CRITICAL", "HIGH"]:
                    post_message(
                        agent_name,
                        "orchestrator",
                        f"[{priority}] {event.file_path}: {str(message)[:100]}",
                        event.task_id,
                        priority,
                    )

            if saved_count > 0:
                print(f"    ✅ {agent_name} posted {saved_count} feedback item(s)")
            else:
                print(f"    [i]  {agent_name}: Response parsed but no valid items extracted")

        except Exception as e:
            print(f"    ⚠️  {agent_name}: Error processing response: {e}")

    def _update_review_tracking(self, agent_name: str, event: FileChangeEvent):
        """Update when this agent last reviewed this file"""
        try:
            conn = sqlite3.connect(get_db_path())
            conn.execute(
                """
                INSERT INTO agent_review_tracking
                (agent_name, file_path, last_reviewed_at, content_hash_reviewed, feedback_count)
                VALUES (?, ?, ?, ?, 1)
                ON CONFLICT(agent_name, file_path) DO UPDATE SET
                    last_reviewed_at = excluded.last_reviewed_at,
                    content_hash_reviewed = excluded.content_hash_reviewed,
                    feedback_count = feedback_count + 1
            """,
                (
                    agent_name,
                    event.file_path,
                    datetime.now().isoformat(),
                    event.content_hash,
                ),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"    ⚠️  Error updating review tracking: {e}")

    def set_feeder_interval(self, interval: int):
        """Dynamically adjust feeder interval (called by resource controller)."""
        with self._state_lock:
            self.feeder_interval = interval
        print(f"    🎛️  Feeder interval adjusted to {interval}s")

    def set_active_agents(self, active_agents: list[str]):
        """
        Enable/disable specific FEEDBACK agents (called by resource controller)

        IMPORTANT: This ONLY affects feedback-generating agents (jr_reviewer, etc.)
        Support workers (prioritizer, archivist, reporter, resource_controller)
        are NEVER disabled - they always run.
        """
        support_workers = {
            "prioritizer",
            "archivist",
            "project_reporter",
            "resource_controller",
        }
        feedback_agents_only = [a for a in active_agents if a not in support_workers]

        with self._state_lock:
            if not feedback_agents_only:
                print("    🛑 PAUSING all background feedback agents (backlog too high)")
                print("    ✅ Support workers (prioritizer, archivist, etc.) still active")
                self.active_agents_filter = set()  # Empty = no feedback agents
                return

            all_feedback_agents = set(self.modification_agents + self.random_review_agents)
            for agent_name in all_feedback_agents:
                if agent_name not in feedback_agents_only:
                    print(f"    🔇 Disabled {agent_name} (backlog management)")
            for agent_name in feedback_agents_only:
                print(f"    🔊 Re-enabled {agent_name}")

            self.active_agents_filter = set(feedback_agents_only)

    def force_review_cycle(self, file_limit: int = 8):
        """
        Force background agents to review files immediately.
        """
        print("🔄 Forcing background review cycle...")
        if not self.running:
            print("    ⚠️  Background agents are not running")
            return
        try:
            try:
                from agents.resource_controller_worker import get_resource_controller

                rc = get_resource_controller()
                rc.temporarily_disable_throttling(duration_seconds=45)
                print("    🔓 Resource restrictions temporarily lifted for this cycle")
            except Exception as e:
                print(f"    ⚠️  Exception handled in parallel_workers.py: {e}")

            conn = sqlite3.connect(get_db_path())
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT file_path, content, content_hash, last_modified, size_bytes, file_type
                FROM project_files
                WHERE is_binary = 0
                ORDER BY last_modified DESC
                LIMIT ?
            """,
                (file_limit // 2 + 1,),
            )
            modified_files = cursor.fetchall()

            cursor.execute(
                """
                SELECT file_path, content, content_hash, last_modified, size_bytes, file_type
                FROM project_files
                WHERE is_binary = 0
                ORDER BY RANDOM()
                LIMIT ?
            """,
                (file_limit // 2,),
            )
            random_files = cursor.fetchall()
            conn.close()

            all_files = modified_files + random_files
            if not all_files:
                print("    ⚠️  No files available to review")
                return

            queued_count = 0
            for file_data in all_files:
                event = FileChangeEvent(
                    event_id=str(uuid.uuid4()),
                    file_path=file_data[0],
                    operation="forced_review",
                    content=file_data[1],
                    content_hash=file_data[2],
                    metadata={
                        "last_modified": file_data[3],
                        "size_bytes": file_data[4],
                        "file_type": file_data[5],
                    },
                    task_id=self.task_id,
                    timestamp=datetime.now().isoformat(),
                    priority=2,
                )
                self.event_queue.put(event)
                queued_count += 1

            print(f"    ✅ Queued {queued_count} files for forced review by background agents")
            print("    📤 Background agents will now analyze and post suggestions to the message bus")
        except Exception as e:
            print(f"    ❌ Error during forced review cycle: {e}")


# Global pool
_agent_pool = None


def get_agent_pool() -> BackgroundAgentPool:
    """Get global agent pool"""
    global _agent_pool
    if _agent_pool is None:
        _agent_pool = BackgroundAgentPool()
    return _agent_pool
