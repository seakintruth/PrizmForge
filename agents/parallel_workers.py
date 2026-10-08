"""Parallel background agent workers with continuous file feeding"""

import queue
import random
import re
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
from agents.worker_utils import (
    foreground_session_active,
    interruptible_sleep,
    support_frozen,
)
from core.config import get_config
from core.db import get_db_path
from core.db_helpers import is_praise_only_feedback, post_message, save_agent_feedback, utcnow_iso
from core.file_operations import compute_file_hash
from core.json_parser import parse_json_response
from core.review_feed import (
    MAX_LINES_PER_SLICE,
    MAX_SLICES,
    SliceSpec,
    blast_radius_paths,
    build_reviewer_map,
    coverage_sweep_next,
    extract_covered,
    extract_need_files,
    serve_need_files,
)
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
        self.sweep_thread = None
        self.running = False
        self.task_id = None
        self.recently_queued = {}
        self._queue_lock = threading.Lock()  # protects recently_queued
        self._state_lock = threading.Lock()  # protects running/workers/feeder/filter
        self.active_agents_filter = None  # None = all active
        # Soak §19.4: free-tier posture — while the active task has not yet
        # materialized a file (files_modified == 0), the random feeder and
        # coverage sweep pause so a 50-call day is not burned by hollow
        # reviews before the proposal lands. set_active_agents([]) already
        # silences the feedback workers; this gates the feeder/sweep too.
        self.feeder_paused = False
        # Soak §19.4: hollow-receipt refusal ledger — (agent_name, file_path,
        # content_hash) triples refused once. Feeders skip them until the file
        # content changes (new hash), so the same file is never retried in the
        # same cycle: one refuse row, next file.
        self._hollow_refused: set[tuple[str, str, str]] = set()
        # Soak §19.4: free-tier pause-until-materialize snapshot stack. One
        # entry = the active_agents_filter captured when the pause began, so a
        # resume restores exactly the prior stance (even one set by the
        # resource controller) instead of blindly re-enabling everything.
        self._free_tier_pause_stack: list = []

        # Load agent configurations from config
        config = get_config()

        self.agent_configs = config.get("background_agents", {}) or {}
        self.feeder_config = config.get("background_feeder", {}) or {}
        self.feeder_interval = self.feeder_config.get("interval_seconds", 30)
        self.base_feeder_interval = self.feeder_interval  # Store original

        # §16.2: long-horizon coverage sweep runs when random_review is off,
        # paused while a foreground (developer) session is active.
        self.sweep_config = config.get("background_sweep", {}) or {}
        self.sweep_interval = int(self.sweep_config.get("interval_seconds", 300))

        # Categorize agents by behavior
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

        Respects ``background_agents_enabled``. When False, this is a no-op so
        tests and unattended runs with the flag off never spawn LLM workers.
        """
        config = get_config()
        if not config.get("background_agents_enabled", True):
            print("    Background agents disabled (background_agents_enabled=False)")
            return

        with self._state_lock:
            if self.running:
                return

            # Ensure any leftover threads from a timed-out stop are gone
            self._join_workers_unlocked(timeout=1.0)

            self.running = True
            self.task_id = task_id

            all_agents = set(self.modification_agents + self.random_review_agents)
            if not all_agents:
                print("    Warning: No background agents enabled")
                # Still mark running=False — nothing to stop later
                self.running = False
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

                agent_cfg = self.agent_configs.get(agent_name, {})
                mod_flag = "on_mod" if agent_cfg.get("on_modification") else ""
                random_flag = "random" if agent_cfg.get("random_review") else ""
                flags = f"[{mod_flag}+{random_flag}]" if mod_flag and random_flag else f"[{mod_flag or random_flag}]"
                print(f"    Started {agent_name} worker {flags}")

            self._start_support_workers(task_id)

            self._queue_all_files_for_initial_review()
            self._queue_modified_files()

            # W8 (soak recompute, 2026-08-29): intake softening at the pool
            # level. If the initial burst already overwhelmed the queue, slow
            # the feeder hard BEFORE it starts so the shared per-endpoint
            # RateLimiter is not flooded (429 -> 60s sleeps in the code loop).
            # Implemented as a feeder-interval bump, NOT as a ThrottleDecision:
            # active_agents=[] would deadlock a queued batch (paused agents
            # never drain it) and active_agents=None would crash _apply_decision.
            soft_batch = int(self.agent_configs.get("intake_soft_batch", 100))
            if self.event_queue.qsize() > soft_batch:
                self.feeder_interval = 120.0
                self.base_feeder_interval = 120.0
                print(f"    ⚠️  Queue burst of {self.event_queue.qsize()} events exceeds intake soft-batch ({soft_batch}); slowing feeder to 120s")

            if self.random_review_agents:
                self.feeder_thread = threading.Thread(
                    target=self._file_feeder_loop,
                    daemon=True,
                    name="file-feeder",
                )
                self.feeder_thread.start()
                print(f"    Started continuous file feeder for {len(self.random_review_agents)} agent(s)")

            # §16.2: coverage sweep keeps the ledger growing even with
            # random_review off. It pauses itself while a foreground developer
            # session is active (see _sweep_loop).
            if self.modification_agents and self.sweep_config.get("enabled", True):
                self.sweep_thread = threading.Thread(
                    target=self._sweep_loop,
                    daemon=True,
                    name="coverage-sweep",
                )
                self.sweep_thread.start()
                print(f"    Started coverage sweep (every {self.sweep_interval}s, paused during developer sessions)")

    def _join_workers_unlocked(self, timeout: float = 2.0) -> None:
        """Join feeder + sweep + analysis workers. Caller must hold _state_lock."""
        if self.feeder_thread is not None:
            self.feeder_thread.join(timeout=timeout)
            self.feeder_thread = None

        if self.sweep_thread is not None:
            self.sweep_thread.join(timeout=timeout)
            self.sweep_thread = None

        for worker in self.workers:
            worker.join(timeout=timeout)
        self.workers.clear()

        try:
            while True:
                self.event_queue.get_nowait()
        except queue.Empty:
            pass

    def stop(self):
        """Stop all workers including feeder and support workers."""
        from agents.resource_controller_worker import get_resource_controller

        with self._state_lock:
            if not self.running and not self.workers and self.feeder_thread is None and self.sweep_thread is None:
                # Still stop support workers — they may have been started elsewhere
                pass
            else:
                self.running = False
                self._join_workers_unlocked(timeout=2.0)

        get_archivist_worker().stop()
        get_prioritizer_worker().stop()
        get_reporter_worker().stop()
        get_resource_controller().stop()

        with self._queue_lock:
            self.recently_queued.clear()

        print("    Stopped background workers")

    def _start_support_workers(self, task_id: str):
        """Start archivist, prioritizer, reporter, resource controller"""
        from agents.resource_controller_worker import get_resource_controller

        get_archivist_worker().start(task_id)
        get_prioritizer_worker().start(task_id)
        get_reporter_worker().start(task_id)
        get_resource_controller().start(task_id)

    def _queue_all_files_for_initial_review(self):
        """Queue project files for initial review when task starts.

        W7 (soak recompute, 2026-08-29): capped by
        ``background_agents.initial_review_max_files`` (default 5). Soak9
        queued ALL 231 files for all 3 agents (693 events) plus 462 modified
        -file events in one burst, all sharing the core loop's RateLimiter and
        TokenBudget, which is what produced the 429 flood.

        Phase 4.1 (soak recompute): when the active task's seed feedback names
        an indexed file, initial review begins with ONLY that file target so a
        single-file seed task does not generate a repository-wide feedback
        backlog. Broad peers (task_runner, proposal_builder, pre_commit.sh,
        models_cli) are never enqueued as part of the initial burst.
        """
        try:
            conn = sqlite3.connect(get_db_path())
            cursor = conn.cursor()

            max_files = int(self.agent_configs.get("initial_review_max_files", 5))
            target_file = self._resolve_seed_target_path(cursor)
            if target_file:
                cursor.execute(
                    """
                    SELECT
                        pf.file_path, pf.content, pf.content_hash, pf.last_modified,
                        pf.size_bytes, pf.file_type, fs.summary, fs.purpose, fs.line_count
                    FROM project_files pf
                    LEFT JOIN file_summaries fs ON pf.file_path = fs.file_path
                    WHERE pf.is_binary = 0 AND pf.file_path = ?
                    """,
                    (target_file,),
                )
            else:
                cursor.execute(
                    """
                    SELECT
                        pf.file_path, pf.content, pf.content_hash, pf.last_modified,
                        pf.size_bytes, pf.file_type, fs.summary, fs.purpose, fs.line_count
                    FROM project_files pf
                    LEFT JOIN file_summaries fs ON pf.file_path = fs.file_path
                    WHERE pf.is_binary = 0
                    ORDER BY pf.last_modified DESC
                    LIMIT ?
                    """,
                    (max_files,),
                )

            all_files = cursor.fetchall()
            conn.close()

            if not all_files:
                print("    No files found for initial review")
                return

            queued_count = 0

            for _agent_name in self.modification_agents + self.random_review_agents:
                for file_data in all_files:
                    event = self._create_file_event(file_data, "initial_review", priority=3)
                    self.event_queue.put(event)
                    queued_count += 1

            print(f"    Queued {queued_count} files for initial peer review")

        except Exception as e:
            print(f"    Error queuing files for initial review: {e}")

    def _resolve_seed_target_path(self, cursor) -> str | None:
        """Best-effort extraction of the task-target file path from seed feedback.

        Returns the single indexed, non-binary file path named by the seed task
        for this pool task, or None when there is no seed item (or no indexed
        match). Candidates are file-like tokens from the seed message, tested
        longest-first so a deep path beats a shared prefix.
        """
        if not self.task_id:
            return None
        try:
            row = cursor.execute(
                """
                SELECT message FROM agent_feedback
                WHERE task_id = ? AND category = 'seed_task' AND addressed = 0
                ORDER BY timestamp DESC LIMIT 1
                """,
                (self.task_id,),
            ).fetchone()
        except sqlite3.Error as e:
            print(f"    Seed target lookup skipped: {e}")
            return None
        if not row or not row[0]:
            return None
        candidates = sorted(set(re.findall(r"[\w./-]+\.\w+", row[0])), key=len, reverse=True)
        for candidate in candidates:
            hit = cursor.execute(
                "SELECT 1 FROM project_files WHERE is_binary = 0 AND file_path = ?",
                (candidate,),
            ).fetchone()
            if hit:
                return candidate
        return None

    def _queue_modified_files(self):
        """Queue files modified since last review + their blast radius (§16.1).

        Each modified root is fed together with the depth-≤2 blast radius from
        symbol_index (consumers/importers/tests) instead of a random sibling.
        Roots keep priority 1; radius neighbors are queued at priority 2.
        """
        try:
            conn = sqlite3.connect(get_db_path())
            cursor = conn.cursor()

            max_files = int(self.agent_configs.get("initial_review_max_files", 5))
            candidate_rows = conn.execute("SELECT file_path, content FROM project_files WHERE is_binary = 0").fetchall()

            queued_count = 0
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
                    LIMIT ?
                """,
                    (agent_name, max_files),
                )

                modified_files = cursor.fetchall()

                fed_for_agent = 0
                max_events_per_agent = max_files * 3

                for file_data in modified_files:
                    if fed_for_agent >= max_events_per_agent:
                        break

                    root_path = file_data[0]
                    try:
                        radius_paths = blast_radius_paths(conn, root_path, candidates=candidate_rows, max_paths=5)
                    except Exception as e:
                        print(f"    Blast radius probe failed for {root_path}: {e}")
                        radius_paths = [root_path]

                    if not radius_paths:
                        radius_paths = [root_path]

                    for path in radius_paths:
                        if fed_for_agent >= max_events_per_agent:
                            break

                        with self._queue_lock:
                            tracking_set = self.recently_queued.get(agent_name)
                            if tracking_set and path in tracking_set:
                                continue

                        event = self._file_event_for_path(cursor, path, root_path)
                        if event is None:
                            continue

                        # Soak §19.4: a file refused earlier this cycle (hollow
                        # receipt at the current hash) is not re-fed until its
                        # content changes — don't burn the free-tier day on a
                        # reviewer that already said "nothing found".
                        if self._is_hollow_refused(agent_name, path, event.content_hash):
                            continue

                        self.event_queue.put(event)
                        with self._queue_lock:
                            if tracking_set is None:
                                tracking_set = BoundedSet()
                                self.recently_queued[agent_name] = tracking_set
                            tracking_set.add(path)
                        queued_count += 1
                        fed_for_agent += 1

            conn.close()

            if queued_count > 0:
                print(f"    Queued {queued_count} modified/blast-radius file(s) for {len(self.modification_agents)} agent(s)")

        except Exception as e:
            print(f"    Error queuing modified files: {e}")

    def _file_event_for_path(self, cursor, path: str, root_path: str) -> FileChangeEvent | None:
        """Event row for a feed target; roots are ``modified_since_review``."""
        row = cursor.execute(
            """
            SELECT
                pf.file_path, pf.content, pf.content_hash, pf.last_modified,
                pf.size_bytes, pf.file_type, fs.summary, fs.purpose, fs.line_count
            FROM project_files pf
            LEFT JOIN file_summaries fs ON pf.file_path = fs.file_path
            WHERE pf.file_path = ? AND pf.is_binary = 0
            """,
            (path,),
        ).fetchone()
        if row is None:
            return None
        if path == root_path:
            return self._create_file_event(row, "modified_since_review", priority=1)
        return self._create_file_event(row, "blast_radius", priority=2)

    def _file_feeder_loop(self):
        """Feed random files to agents that want them"""
        while self.running:
            try:
                queue_size = self.event_queue.qsize()
                self._adjust_feeder_interval(queue_size)
                # interruptible so stop() does not wait out a 30-300s sleep
                interruptible_sleep(self.feeder_interval, lambda: self.running)

                if not self.running:
                    break

                self._feed_random_files()

            except Exception as e:
                print(f"    File feeder error: {e}")
                interruptible_sleep(5, lambda: self.running)

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
        if queue_size > 150:
            print(f"    Queue backlog: {queue_size} items. Slowing feeder to {interval}s")

    def _feed_random_files(self):
        """Feed random files to agents with random_review=true"""
        try:
            if self.feeder_paused:
                print("    Random feeder paused (free-tier posture); skipping cycle")
                return
            conn = sqlite3.connect(get_db_path())
            cursor = conn.cursor()

            # Phase 4.3 (soak recompute): pause the random feeder once
            # unaddressed feedback exceeds the cap so the backlog stops
            # growing (success criterion: no repository-wide feedback flood).
            if self.task_id:
                from workflow.backlog import count_unaddressed_feedback

                max_unaddressed = int(self.agent_configs.get("max_unaddressed_feedback_before_pause", 10))
                if count_unaddressed_feedback(conn, self.task_id) > max_unaddressed:
                    conn.close()
                    print(f"    Pausing random file feeder: unaddressed feedback exceeds {max_unaddressed} (Phase 4.3)")
                    return

            cursor.execute("""
                SELECT
                    pf.file_path, pf.content, pf.content_hash, pf.last_modified,
                    pf.size_bytes, pf.file_type, fs.summary, fs.purpose, fs.line_count
                FROM project_files pf
                LEFT JOIN file_summaries fs ON pf.file_path = fs.file_path
                WHERE pf.is_binary = 0
            """)

            all_files = cursor.fetchall()
            conn.close()

            if not all_files:
                return

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

                # Soak §19.4: skip files refused this cycle (hollow receipt at
                # the current hash) so the random feeder moves to the next file
                # instead of re-picking the same refusal. Evaluated outside the
                # queue lock (non-reentrant); fall-back wrap-around re-applies
                # the same refusal filter afterwards.
                if not available_files:
                    with self._queue_lock:
                        if agent_name in self.recently_queued:
                            self.recently_queued[agent_name].clear()
                    available_files = all_files
                available_files = [f for f in available_files if not self._is_hollow_refused(agent_name, f[0], f[2])]
                if not available_files:
                    continue

                selected_files = random.sample(available_files, min(files_per_cycle, len(available_files)))

                for file_data in selected_files:
                    event = self._create_file_event(file_data, "random_review", priority=7)
                    self.event_queue.put(event)
                    if agent_name in self.recently_queued:
                        with self._queue_lock:
                            self.recently_queued[agent_name].add(file_data[0])

            print(f"    Fed random files to {len(self.random_review_agents)} agent(s)")

        except Exception as e:
            print(f"    Error feeding random files: {e}")

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

        self.event_queue.put(event)

        with self._queue_lock:
            for agent_name in self.modification_agents:
                if agent_name in self.recently_queued:
                    self.recently_queued[agent_name].add(file_path)

        print(f"    Queued {file_path} for {len(self.modification_agents)} modification agent(s)")

    def _worker_loop(self, agent_name: str):
        """Main worker loop for a FEEDBACK agent"""
        while self.running:
            # §6.3: while every configured endpoint is latched, freeze
            # feedback agents (jr_reviewer, etc.) too — not just the support
            # workers — so they stop burning the last quota carries.
            if support_frozen():
                interruptible_sleep(5.0, lambda: self.running)
                continue

            if self.active_agents_filter is not None:
                if len(self.active_agents_filter) == 0:
                    interruptible_sleep(1.0, lambda: self.running)
                    continue

                if agent_name not in self.active_agents_filter:
                    interruptible_sleep(1.0, lambda: self.running)
                    continue

            try:
                event = self.event_queue.get(timeout=1.0)
            except queue.Empty:
                continue

            if event.content is None:
                continue

            interruptible_sleep(0.1, lambda: self.running)

            self._process_file(agent_name, event)

    def _process_file(self, agent_name: str, event: FileChangeEvent):
        """Process a file with an agent (map-first peer review, §16.1).

        Phase 1 feeds the reviewer a compact structural **map** (≤80 rows from
        ``file_summaries`` + ``file_symbols``) — never a full file body. If the
        reviewer asks for content (``need_files``), Phase 2 serves those exact
        slices from the governed DB and runs one confirm pass. Differences are
        merged into a single feedback save; acknowledged ranges are written to
        ``review_coverage`` by ``_record_coverage``.

        Coverage-sweep events (§16.2) short-circuit to ``_process_sweep_chunk``.
        """

        try:
            sweep_spec = (event.metadata or {}).get("sweep_slice")
            if sweep_spec:
                self._process_sweep_chunk(agent_name, event, sweep_spec)
                return

            agent_config = self.agent_configs.get(agent_name, {})
            model_override = agent_config.get("model")

            conn = sqlite3.connect(get_db_path())
            try:
                project_map = build_reviewer_map(conn, focus_path=event.file_path)
            finally:
                conn.close()

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
                "blast_radius": "changed (this file is in the blast radius of a recent change)",
                "random_review": "selected for periodic review",
                "initial_review": "initial review",
                "create": "newly created",
                "modify": "just modified",
                "forced_review": "selected for a forced review cycle",
            }
            operation_desc = op_descriptions.get(event.operation, event.operation)

            v1_prompt = self._build_reviewer_prompt(event.file_path, operation_desc, metadata_str, project_map, context_block=None)
            response1 = self._call_reviewer_with_retries(agent_name, event, v1_prompt, model_override)
            if not response1:
                self._mark_review_failed(agent_name, event)
                return

            data1 = self._parse_review_json(response1)
            if data1 is None:
                self._mark_review_failed(agent_name, event)
                return

            data1, response_final = self._serve_requested_slices(agent_name, event, data1, response1, model_override)

            cleaned = clean_llm_response(response_final, agent_name)
            if cleaned:
                if self._is_hollow_receipt(data1):
                    print(f"    {agent_name}: hollow receipt (no findings and no covered) — refused (Qwen-style)")
                    self._mark_hollow_refused(agent_name, event.file_path, event.content_hash)
                    log_error(
                        "MEDIUM",
                        "parallel_workers",
                        "hollow_receipt",
                        f"{agent_name} returned neither findings nor covered for {event.file_path}; receipt refused",
                        task_id=event.task_id,
                        file_path=event.file_path,
                    )
                    return
                self._parse_and_save_feedback(agent_name, event, cleaned)
                self._update_review_tracking(agent_name, event)
                self._record_coverage(agent_name, event, data1)
                return

            self._mark_review_failed(agent_name, event)

        except Exception as e:
            print(f"    {agent_name} error on {event.file_path}: {e}")
            log_error(
                "HIGH",
                "parallel_workers",
                "process_file",
                f"{agent_name} exception: {e!s}",
                task_id=event.task_id,
                file_path=event.file_path,
            )

    @staticmethod
    def _build_reviewer_prompt(
        file_path: str,
        operation_desc: str,
        metadata_str: str,
        project_map: str,
        context_block: str | None,
    ) -> str:
        """Map-first reviewer prompt with the §16.1 JSON contract."""
        need_files_cap = f"{MAX_SLICES} ranges of at most {MAX_LINES_PER_SLICE} lines each"
        schema_hint = "start=end=0 means the WHOLE file was assessed"
        prompt = f"""File {operation_desc}: {file_path}
{metadata_str}
{project_map}

You are reviewing this target repository. The map above is STRUCTURAL ONLY —
you have NOT seen any file bodies. Never fabricate file content you have not read.

Respond with ONLY valid JSON:

{{
  "findings": [
    {{
      "priority": "HIGH|MEDIUM|LOW",
      "category": "bug|security|perf|style|docs",
      "file_path": "repo-relative path",
      "line": 0,
      "message": "what is wrong",
      "suggestion": "how to fix"
    }}
  ],
  "covered": [{{"file_path": "path", "start": 0, "end": 0}}],
  "need_files": [{{"file_path": "path", "start": 1, "end": 120, "why": "reason"}}],
  "summary": "brief summary"
}}

Rules:
- "covered": 1-based inclusive line ranges you were able to assess. {schema_hint}.
- "need_files": EXACT 1-based inclusive line windows you must READ to give
  accurate findings. At most {need_files_cap}.
- If you need no additional content, "need_files" MUST be [] — never invent
  findings from the map alone.
- Every finding must carry an explicit "file_path".
"""
        if context_block:
            prompt += (
                "\nBelow are the EXACT slices you requested. Read them now, "
                "then re-emit the JSON with your final findings. "
                '"need_files" must be [] in this final response.\n\n'
                f"{context_block}\n"
            )
        return prompt

    def _call_reviewer_with_retries(self, agent_name: str, event: FileChangeEvent, prompt: str, model_override: str | None) -> str | None:
        """Call the reviewer with the existing 3-attempt format-retry scaffold.

        Returns the last response string, or None when the endpoint returned
        nothing (transport problem — stricter prompts cannot help).
        """
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            if attempt == 1:
                full_prompt = prompt
            elif attempt == 2:
                full_prompt = f"""{prompt}

CRITICAL: Your previous response was not valid JSON.

You MUST respond with ONLY valid JSON. No explanations, no markdown, no text outside the JSON.

Start with {{ and end with }}. Nothing before or after."""
            else:
                full_prompt = """Your previous 2 responses failed JSON validation.

This is your FINAL attempt. Respond with ONLY this structure:

{
  "findings": [
    {"priority": "HIGH", "category": "bug", "file_path": "path", "message": "Issue here", "suggestion": "Fix here"}
  ],
  "covered": [{"file_path": "path", "start": 0, "end": 0}],
  "need_files": [],
  "summary": "Brief summary"
}

START YOUR RESPONSE WITH { RIGHT NOW. NO OTHER TEXT."""

            if attempt > 1:
                print(f"    {agent_name}: Retry {attempt}/{max_attempts} with stricter prompt")
                time.sleep(2)  # Brief backoff between format-retries

            response = call_agent(
                agent_name,
                full_prompt,
                event.task_id,
                model_override=model_override,
                auto_resume=False,
            )

            if not response:
                # Empty response = endpoint/transport problem, not a JSON
                # formatting problem. Stricter prompts cannot help — soak data
                # showed 147 events burning all 3 attempts this way.
                print(f"    {agent_name}: Empty response (endpoint issue) — skipping format retries")
                time.sleep(20)
                return None

            cleaned_response = clean_llm_response(response, agent_name)

            if cleaned_response:
                return cleaned_response

        print(f"    {agent_name}: Failed after {max_attempts} attempts")
        return None

    @staticmethod
    def _parse_review_json(response: str) -> dict | None:
        return parse_json_response(response, expected_keys=None, strict=False)

    def _serve_requested_slices(
        self,
        agent_name: str,
        event: FileChangeEvent,
        data: dict,
        response1: str,
        model_override: str | None,
    ) -> tuple[dict, str]:
        """Honor ``need_files`` from the map pass with one bounded confirm pass.

        Returns ``(merged_data, response_text)``. When no slices are requested
        (or nothing could be served), the phase-1 data/response is returned
        unchanged.
        """
        specs = extract_need_files(data)
        if not specs:
            return data, response1

        conn = sqlite3.connect(get_db_path())
        try:
            slices_block = serve_need_files(conn, specs)
        finally:
            conn.close()

        if not slices_block:
            print(f"    {agent_name}: need_files could not be served from the governed DB; using map pass")
            return data, response1

        confirm_prompt = self._build_reviewer_prompt(
            event.file_path,
            "target of this review cycle",
            "",
            "**Target repository map** (unchanged from map pass).",
            context_block=slices_block,
        )
        print(f"    {agent_name}: serving {len(specs)} requested slice(s); running confirm pass")
        response2 = self._call_reviewer_with_retries(agent_name, event, confirm_prompt, model_override)
        if not response2:
            print(f"    {agent_name}: confirm pass returned nothing; keeping map-pass findings")
            return data, response1

        data2 = self._parse_review_json(response2)
        if data2 is None:
            print(f"    {agent_name}: confirm pass failed JSON validation; keeping map-pass findings")
            return data, response1

        print(f"    {agent_name}: confirm pass merged ({len(data2.get('findings', []))} finding(s))")
        return data2, response2

    def _record_coverage(self, agent_name: str, event: FileChangeEvent, data: dict | None):
        """Write §16.1/§16.2 coverage receipts to the review_coverage ledger."""
        if not data:
            return None
        covered = extract_covered(data)
        if not covered:
            return None
        try:
            conn = sqlite3.connect(get_db_path())
            ts = utcnow_iso()
            for c in covered:
                conn.execute(
                    """
                    INSERT INTO review_coverage
                    (agent_name, file_path, lines_lo, lines_hi, content_hash, covered_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(agent_name, file_path, lines_lo, lines_hi) DO UPDATE SET
                        content_hash = excluded.content_hash,
                        covered_at = excluded.covered_at
                    """,
                    (agent_name, c.file_path, c.lines_lo, c.lines_hi, event.content_hash, ts),
                )
            conn.commit()
            conn.close()
            print(f"    {agent_name}: recorded {len(covered)} coverage receipt(s) to the ledger")
        except Exception as e:
            print(f"    Error recording reviewed coverage: {e}")
        return None

    @staticmethod
    def _is_hollow_receipt(data) -> bool:
        """§16.2: no findings AND no covered ranges = a content-free receipt.

        Refuse it (Qwen-style ack) so the file stays due for a real review.
        """
        if not isinstance(data, dict):
            return True
        findings = data.get("findings")
        if isinstance(findings, list) and findings:
            return False
        if extract_covered(data):
            return False
        return True

    def _mark_hollow_refused(self, agent_name: str, file_path: str, content_hash: str | None):
        """Soak §19.4: record ONE refuse row so the same file is not retried
        in the same cycle. Keyed on content_hash so a materialized edit (new
        hash) makes the file eligible again."""
        with self._queue_lock:
            self._hollow_refused.add((agent_name, file_path, content_hash or ""))
        print(f"    {agent_name}: refuse row recorded for {file_path} (same-cycle retry suppressed)")

    def _is_hollow_refused(self, agent_name: str, file_path: str, content_hash: str | None) -> bool:
        with self._queue_lock:
            return (agent_name, file_path, content_hash or "") in self._hollow_refused

    def _sweep_loop(self):
        """Lowest-priority coverage sweep, paused during developer sessions."""
        while self.running:
            interruptible_sleep(self.sweep_interval, lambda: self.running)
            if not self.running:
                break
            try:
                self._sweep_cycle()
            except Exception as e:
                print(f"    Coverage sweep error: {e}")
                interruptible_sleep(5, lambda: self.running)

    def _sweep_cycle(self):
        """Queue one next-uncovered chunk per reviewer agent (§16.2)."""
        if foreground_session_active():
            return
        if self.feeder_paused:
            print("    Coverage sweep paused (free-tier posture); skipping cycle")
            return
        if not self.modification_agents:
            return
        conn = sqlite3.connect(get_db_path())
        cursor = conn.cursor()
        try:
            for agent_name in self.modification_agents:
                spec = coverage_sweep_next(conn, agent_name=agent_name)
                if spec is None:
                    continue
                with self._queue_lock:
                    tracking_set = self.recently_queued.get(agent_name)
                    if tracking_set and spec.file_path in tracking_set:
                        continue
                # Soak §19.4: skip files refused this cycle (hollow receipt at
                # the current hash) — coverage sweep must not re-target the file
                # that just produced "no findings and no covered".
                if self._is_hollow_refused(agent_name, spec.file_path, self._current_hash_for(conn, spec.file_path)):
                    continue
                event = self._sweep_event_for(cursor, spec)
                if event is None:
                    continue
                self.event_queue.put(event)
                with self._queue_lock:
                    if tracking_set is None:
                        tracking_set = BoundedSet()
                        self.recently_queued[agent_name] = tracking_set
                    tracking_set.add(spec.file_path)
                print(f"    Coverage sweep: {agent_name} next chunk {spec.file_path} lines {spec.start}-{spec.end}")
        finally:
            conn.close()

    def _current_hash_for(self, conn, file_path: str) -> str | None:
        row = (
            conn.cursor()
            .execute(
                "SELECT content_hash FROM project_files WHERE file_path = ? AND is_binary = 0",
                (file_path,),
            )
            .fetchone()
        )
        return row[0] if row else None

    def _sweep_event_for(self, cursor, spec: SliceSpec) -> FileChangeEvent | None:
        """Event for a sweep chunk; content_hash is the file's current hash."""
        row = cursor.execute(
            """
            SELECT
                pf.file_path, pf.content, pf.content_hash, pf.last_modified,
                pf.size_bytes, pf.file_type, fs.summary, fs.purpose, fs.line_count
            FROM project_files pf
            LEFT JOIN file_summaries fs ON pf.file_path = fs.file_path
            WHERE pf.file_path = ? AND pf.is_binary = 0
            """,
            (spec.file_path,),
        ).fetchone()
        if row is None:
            return None
        event = self._create_file_event(row, "coverage_sweep", priority=4)
        if not event.content:
            event.content = "coverage_sweep"
        event.metadata = dict(event.metadata or {})
        event.metadata["sweep_slice"] = {
            "file_path": spec.file_path,
            "start": spec.start,
            "end": spec.end,
        }
        return event

    def _process_sweep_chunk(self, agent_name: str, event: FileChangeEvent, sweep_spec: dict):
        """Review exactly one governed chunk (80-120 lines) and receipt it."""
        try:
            file_path = sweep_spec.get("file_path")
            start, end = int(sweep_spec.get("start", 0)), int(sweep_spec.get("end", 0))
            if not file_path or start <= 0 or end < start:
                return
            spec = SliceSpec(file_path=file_path, start=start, end=end, why="coverage sweep")

            conn = sqlite3.connect(get_db_path())
            try:
                chunk_block = serve_need_files(conn, [spec])
            finally:
                conn.close()
            if not chunk_block:
                print(f"    {agent_name}: sweep chunk for {file_path} could not be served; skipping")
                return

            agent_config = self.agent_configs.get(agent_name, {})
            model_override = agent_config.get("model")
            prompt = (
                f"Coverage sweep — review ONLY this exact chunk of {file_path}.\n\n"
                f"{chunk_block}\n\n"
                'List findings inside this chunk. If the chunk is fine, "findings" MUST be [].\n'
                'Then re-emit the JSON with "covered" set to EXACTLY '
                f'[{{"file_path": "{file_path}", "start": {start}, "end": {end}}}].\n'
                '"need_files" MUST be []. Never mark ranges you did not read.\n\n'
                "{\n"
                '  "findings": [\n'
                '    {"priority": "HIGH|MEDIUM|LOW", "category": "bug|security|perf|style|docs",\n'
                '     "file_path": "' + file_path + '", "line": 0, "message": "...", "suggestion": "..."}\n'
                "  ],\n"
                f'  "covered": [{{"file_path": "{file_path}", "start": {start}, "end": {end}}}],\n'
                '  "need_files": [],\n'
                '  "summary": "..."\n'
                "}"
            )

            response = self._call_reviewer_with_retries(agent_name, event, prompt, model_override)
            if not response:
                return
            data = self._parse_review_json(response)
            if data is None:
                self._mark_review_failed(agent_name, event)
                return
            if self._is_hollow_receipt(data):
                print(f"    {agent_name}: hollow sweep receipt (no findings, no covered) — refused")
                self._mark_hollow_refused(agent_name, event.file_path, event.content_hash)
                return

            self._parse_and_save_feedback(agent_name, event, response)
            self._update_review_tracking(agent_name, event)
            self._record_coverage(agent_name, event, data)

        except Exception as e:
            print(f"    {agent_name} error on sweep chunk {event.file_path}: {e}")
            log_error(
                "HIGH",
                "parallel_workers",
                "process_file",
                f"{agent_name} exception: {e!s}",
                task_id=event.task_id,
                file_path=event.file_path,
            )

    def _mark_review_failed(self, agent_name: str, event: FileChangeEvent):
        """Log the exhausted-attempts outcome once (json_validation)."""
        log_error(
            "HIGH",
            "parallel_workers",
            "json_validation",
            f"{agent_name} failed JSON validation after 3 attempts",
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
                    print(f"    {agent_name}: Found items in '{field_name}' field")
                    break

            if items is None or len(items) == 0:
                if any(key in data for key in ["priority", "message", "issue", "finding"]):
                    items = [data]
                    print(f"    {agent_name}: Treating entire response as single item")
                else:
                    print(f"    {agent_name}: No actionable items found in response")
                    return

            saved_count = 0
            max_per_cycle = int(self.agent_configs.get("feedback_items_per_reviewer_cycle", 3))
            for item in items:
                if saved_count >= max_per_cycle:
                    print(f"    {agent_name}: cycle cap reached ({max_per_cycle}/response); skipping remaining items")
                    break
                if not isinstance(item, dict):
                    continue

                item_path = item.get("file_path") or item.get("file") or event.file_path
                if not item_path:
                    print(f"    {agent_name}: skipping item without a specific file path (Phase 4.2)")
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

                if not message or len(str(message)) < 10:
                    continue

                if is_praise_only_feedback(str(message), str(suggestion) if suggestion else None):
                    print(f"    {agent_name}: discarding praise-only/confirmation item (Phase 4.2): {str(message)[:80]}")
                    continue

                save_agent_feedback(
                    agent_name,
                    item_path,
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
                        f"[{priority}] {item_path}: {str(message)[:100]}",
                        event.task_id,
                        priority,
                    )

            if saved_count > 0:
                print(f"    {agent_name} posted {saved_count} feedback item(s)")
            else:
                print(f"    {agent_name}: Response parsed but no valid items extracted")

        except Exception as e:
            print(f"    {agent_name}: Error processing response: {e}")

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
            print(f"    Error updating review tracking: {e}")

    def set_feeder_interval(self, interval: int):
        """Dynamically adjust feeder interval (called by resource controller).

        Updates both the live interval and base_feeder_interval so the
        adaptive feeder loop (_adjust_feeder_interval) does not immediately
        overwrite the value from the stale baseline.
        """
        with self._state_lock:
            self.base_feeder_interval = float(interval)
            self.feeder_interval = float(interval)
        print(f"    Feeder interval adjusted to {interval}s")

    def set_feeder_paused(self, paused: bool):
        """Soak §19.4: stop the random feeder + coverage sweep while on the
        free-tier before the first file materializes (files_modified == 0).

        Feedback *workers* are already silenced by ``set_active_agents([])``;
        this stops the periodic loops that would otherwise keep enqueueing
        hollow-review events and burning the free-tier day's quota before the
        shell worktree produces a proposal.
        """
        with self._state_lock:
            self.feeder_paused = bool(paused)
        print(f"    {'Pausing' if paused else 'Resuming'} random feeder / coverage sweep (free-tier posture)")

    def set_free_tier_pause(self, paused: bool):
        """Soak §19.4: pause feedback agents + random feeder + sweep until the
        active task materializes its first file (files_modified == 0).

        Idempotent: the first ``paused=True`` snapshots the current
        ``active_agents_filter``; every subsequent ``paused=True`` is a no-op;
        the matching ``paused=False`` restores exactly that snapshot (however
        many agent turns later the first file lands).
        """
        with self._state_lock:
            if paused and len(self._free_tier_pause_stack) == 0:
                self._free_tier_pause_stack.append(self.active_agents_filter)
            elif not paused and len(self._free_tier_pause_stack) > 0:
                previous = self._free_tier_pause_stack.pop()
            else:
                return
        if paused:
            self.set_active_agents([])
            self.set_feeder_paused(True)
            print("   🛑 Free-tier posture: feedback agents + feeder paused until the first file materializes")
        else:
            self.set_active_agents(previous)
            self.set_feeder_paused(False)
            print("   ✅ First file materialized: background feedback agents + feeder resumed")

    def set_active_agents(self, active_agents: list[str] | None):
        """
        Enable/disable specific FEEDBACK agents (called by resource controller)

        IMPORTANT: This ONLY affects feedback-generating agents (jr_reviewer, etc.)
        Support workers (prioritizer, archivist, reporter, resource_controller)
        are NEVER disabled - they always run.

        ``active_agents=None`` resets the filter entirely (all feedback agents
        active again, W6 lane-isolation resume); ``[]`` pauses every feedback
        agent while support workers keep running.
        """
        if active_agents is None:
            with self._state_lock:
                print("    Resuming ALL background feedback agents")
                self.active_agents_filter = None
            return

        support_workers = {
            "prioritizer",
            "archivist",
            "project_reporter",
            "resource_controller",
        }
        feedback_agents_only = [a for a in active_agents if a not in support_workers]

        with self._state_lock:
            if not feedback_agents_only:
                print("    PAUSING all background feedback agents (backlog too high)")
                print("    Support workers (prioritizer, archivist, etc.) still active")
                self.active_agents_filter = set()
                return

            all_feedback_agents = set(self.modification_agents + self.random_review_agents)
            for agent_name in all_feedback_agents:
                if agent_name not in feedback_agents_only:
                    print(f"    Disabled {agent_name} (backlog management)")
            for agent_name in feedback_agents_only:
                print(f"    Re-enabled {agent_name}")

            self.active_agents_filter = set(feedback_agents_only)

    def force_review_cycle(self, file_limit: int = 8):
        """Force background agents to review files immediately."""
        print("Forcing background review cycle...")
        if not self.running:
            print("    Background agents are not running")
            return
        try:
            try:
                from agents.resource_controller_worker import get_resource_controller

                rc = get_resource_controller()
                rc.temporarily_disable_throttling(duration_seconds=45)
                print("    Resource restrictions temporarily lifted for this cycle")
            except Exception as e:
                print(f"    Exception handled in parallel_workers.py: {e}")

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
                print("    No files available to review")
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

            print(f"    Queued {queued_count} files for forced review by background agents")
            print("    Background agents will now analyze and post suggestions to the message bus")
        except Exception as e:
            print(f"    Error during forced review cycle: {e}")


# Global pool
_agent_pool = None


def get_agent_pool() -> BackgroundAgentPool:
    """Get global agent pool"""
    global _agent_pool
    if _agent_pool is None:
        _agent_pool = BackgroundAgentPool()
    return _agent_pool
