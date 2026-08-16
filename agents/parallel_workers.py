"""Parallel background agent workers with continuous file feeding"""

import queue
import random
import sqlite3
import threading
import uuid
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime

from agents.archivist_worker import get_archivist_worker
from agents.base import call_agent
from agents.prioritizer_worker import get_prioritizer_worker
from agents.reporter_worker import get_reporter_worker
from agents.response_cleaner import clean_llm_response
from agents.worker_utils import interruptible_sleep
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
    """Manages a pool of background agent workers that continuously process file changes."""

    def __init__(self):
        self.running = False
        self.workers = []
        self.event_queue = queue.Queue()
        self._queue_lock = threading.Lock()
        self.recently_queued = BoundedSet(max_size=2000)
        self.feeder_thread = None
        self._state_lock = threading.Lock()  # protects running/workers/feeder/filter
        self.active_agents_filter = None  # None = all active

        # Load agent configurations from config
        config = get_config()

        self.agent_configs = config.get("background_agents", {}) or {}
        self.feeder_config = config.get("background_feeder", {}) or {}
        self.feeder_interval = self.feeder_config.get("interval_seconds", 30)
        self.base_feeder_interval = self.feeder_interval  # Store original

        # Categorize agents by behavior
        self.modification_agents = []  # Review on every file change
        self.random_review_agents = []  # Periodic random review

        for agent_name, agent_cfg in self.agent_configs.items():
            if not agent_cfg.get("enabled", True):
                continue
            if agent_cfg.get("on_modification"):
                self.modification_agents.append(agent_name)
            if agent_cfg.get("random_review"):
                self.random_review_agents.append(agent_name)

        # Support workers (started/stopped with the pool)
        self.prioritizer = None
        self.reporter = None
        self.archivist = None

    def start(self, task_id: str = "background"):
        """Start all configured background workers.

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

            # Clean up any leftover threads from a previous incomplete stop
            self._join_workers(timeout=2.0)

            all_agents = set(self.modification_agents + self.random_review_agents)
            if not all_agents:
                print("    Warning: No background agents enabled")
                # Still mark running=False — nothing to stop later
                self.running = False
                return

            with self._queue_lock:
                # Clear any stale events
                while not self.event_queue.empty():
                    try:
                        self.event_queue.get_nowait()
                    except queue.Empty:
                        break

            self.running = True
            self.workers = []

            for agent_name in all_agents:
                worker = threading.Thread(
                    target=self._worker_loop,
                    args=(agent_name, task_id),
                    name=f"bg-{agent_name}",
                    daemon=True,
                )
                worker.start()
                self.workers.append(worker)

                agent_cfg = self.agent_configs.get(agent_name, {})
                mod_flag = "on_mod" if agent_cfg.get("on_modification") else ""
                random_flag = "random" if agent_cfg.get("random_review") else ""
                flags = f"[{mod_flag}+{random_flag}]" if mod_flag and random_flag else f"[{mod_flag or random_flag}]"
                print(f"    Started {agent_name} worker {flags}")

            # Start continuous feeder for random-review agents
            if self.random_review_agents:
                self.feeder_thread = threading.Thread(
                    target=self._file_feeder_loop,
                    args=(task_id,),
                    name="file-feeder",
                    daemon=True,
                )
                self.feeder_thread.start()
                print(f"    Started continuous file feeder for {len(self.random_review_agents)} agent(s)")

            # Start support workers
            try:
                self.prioritizer = get_prioritizer_worker()
                self.prioritizer.start()
            except Exception as e:
                print(f"    Warning: prioritizer start failed: {e}")

            try:
                self.reporter = get_reporter_worker()
                self.reporter.start()
            except Exception as e:
                print(f"    Warning: reporter start failed: {e}")

            try:
                self.archivist = get_archivist_worker()
                self.archivist.start()
            except Exception as e:
                print(f"    Warning: archivist start failed: {e}")

    def stop(self):
        """Stop all workers and support services."""
        with self._state_lock:
            if not self.running:
                # Still stop support workers — they may have been started elsewhere
                self._stop_support_workers()
                return

            self.running = False

        # Signal feeder and workers to exit (they check self.running)
        self._join_workers(timeout=10.0)

        with self._state_lock:
            self.workers = []
            self.feeder_thread = None

        self._stop_support_workers()
        print("    Background agent pool stopped")

    def _stop_support_workers(self):
        for name, worker in [
            ("prioritizer", self.prioritizer),
            ("reporter", self.reporter),
            ("archivist", self.archivist),
        ]:
            if worker is not None:
                try:
                    worker.stop()
                except Exception as e:
                    print(f"    Warning: {name} stop failed: {e}")
        self.prioritizer = None
        self.reporter = None
        self.archivist = None

    def _join_workers(self, timeout: float = 5.0):
        """Join worker and feeder threads."""
        threads = list(self.workers)
        if self.feeder_thread is not None:
            threads.append(self.feeder_thread)
        for t in threads:
            if t is not None and t.is_alive():
                t.join(timeout=timeout)

    def queue_file_change(
        self,
        file_path: str,
        operation: str = "modified",
        content: str | None = None,
        metadata: dict | None = None,
        task_id: str = "background",
        priority: int = 5,
    ):
        """Queue a file change event for background agents."""
        if not self.running:
            return

        # Skip if recently queued (dedup)
        dedup_key = f"{file_path}:{operation}"
        if dedup_key in self.recently_queued:
            return
        self.recently_queued.add(dedup_key)

        content_hash = None
        if content is not None:
            content_hash = compute_file_hash(content)

        event = FileChangeEvent(
            event_id=str(uuid.uuid4()),
            file_path=file_path,
            operation=operation,
            content=content,
            content_hash=content_hash,
            metadata=metadata or {},
            task_id=task_id,
            timestamp=datetime.utcnow().isoformat(),
            priority=priority,
        )

        with self._queue_lock:
            self.event_queue.put(event)

    def set_active_agents(self, agent_names: list[str] | None):
        """Restrict which agents process events. None = all."""
        with self._state_lock:
            self.active_agents_filter = set(agent_names) if agent_names else None

    def set_feeder_interval(self, seconds: float):
        """Update feeder interval (and base for adaptive adjustments)."""
        with self._state_lock:
            self.feeder_interval = max(5.0, float(seconds))
            self.base_feeder_interval = self.feeder_interval

    def force_review_cycle(self, task_id: str = "background"):
        """Force a full random-review cycle of project files."""
        if not self.running:
            return
        self._queue_random_files(task_id, force=True)

    def _adjust_feeder_interval(self, queue_size: int):
        """Slow down feeder when queue is backed up."""
        if queue_size > 50:
            self.feeder_interval = min(300, self.base_feeder_interval * 4)
        elif queue_size > 20:
            self.feeder_interval = min(120, self.base_feeder_interval * 2)
        else:
            self.feeder_interval = self.base_feeder_interval

    def _file_feeder_loop(self, task_id: str):
        """Periodically queue random project files for review agents."""
        while self.running:
            try:
                queue_size = self.event_queue.qsize()
                self._adjust_feeder_interval(queue_size)

                # interruptible so stop() does not wait out a 30-300s sleep
                interruptible_sleep(self.feeder_interval, lambda: self.running)

                if not self.running:
                    break

                self._queue_random_files(task_id)
            except Exception as e:
                log_error(f"file_feeder_loop error: {e}")
                interruptible_sleep(5, lambda: self.running)

    def _queue_random_files(self, task_id: str, force: bool = False):
        """Pick a sample of project files and queue them."""
        try:
            config = get_config()
            project_dir = config.get("project_directory", ".")
            from pathlib import Path

            root = Path(project_dir)
            if not root.exists():
                return

            # Collect candidate source files
            candidates = []
            for ext in (".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".md"):
                candidates.extend(root.rglob(f"*{ext}"))

            # Filter out common non-source paths
            skip_parts = {".git", "node_modules", "__pycache__", ".venv", "venv", ".PrizmForge", "dist", "build"}
            files = [
                str(p.relative_to(root)) if p.is_relative_to(root) else str(p)
                for p in candidates
                if p.is_file() and not any(part in skip_parts for part in p.parts)
            ]

            if not files:
                return

            sample_size = min(5 if not force else 15, len(files))
            selected = random.sample(files, sample_size)

            for rel_path in selected:
                full = root / rel_path
                try:
                    content = full.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    content = None
                self.queue_file_change(
                    file_path=rel_path,
                    operation="review",
                    content=content,
                    task_id=task_id,
                    priority=7,
                )
        except Exception as e:
            log_error(f"_queue_random_files error: {e}")

    def _worker_loop(self, agent_name: str, task_id: str):
        """Worker loop: pull events and call the agent."""
        while self.running:
            try:
                try:
                    event = self.event_queue.get(timeout=1.0)
                except queue.Empty:
                    interruptible_sleep(1.0, lambda: self.running)
                    continue

                # Active filter
                with self._state_lock:
                    filt = self.active_agents_filter
                if filt is not None and agent_name not in filt:
                    interruptible_sleep(1.0, lambda: self.running)
                    continue

                self._process_event(agent_name, event)
            except Exception as e:
                log_error(f"worker_loop({agent_name}) error: {e}")
                interruptible_sleep(0.1, lambda: self.running)

    def _process_event(self, agent_name: str, event: FileChangeEvent):
        """Invoke a background agent on a single file-change event."""
        try:
            # Build a compact context prompt
            content_preview = ""
            if event.content:
                # Truncate large files for the prompt
                lines = event.content.splitlines()
                if len(lines) > 200:
                    content_preview = "\n".join(lines[:100]) + "\n... [truncated] ...\n" + "\n".join(lines[-50:])
                else:
                    content_preview = event.content

            prompt = f"""Background review of file change.

File: {event.file_path}
Operation: {event.operation}
Task ID: {event.task_id}
Timestamp: {event.timestamp}

Content:
```
{content_preview}
```

Respond with JSON only:
{{
  "findings": [{{ "severity": "low|medium|high", "message": "...", "suggestion": "..." }}],
  "summary": "one-line summary"
}}
"""

            response = call_agent(
                agent_name=agent_name,
                prompt=prompt,
                task_id=event.task_id,
            )

            if not response:
                return

            cleaned = clean_llm_response(response)
            data = parse_json_response(cleaned, expected_keys=["findings", "summary"])

            if data and data.get("findings"):
                for finding in data["findings"]:
                    save_agent_feedback(
                        from_agent=agent_name,
                        file_path=event.file_path,
                        priority=str(finding.get("severity", "medium")).upper(),
                        category="background_review",
                        message=finding.get("message", ""),
                        suggestion=finding.get("suggestion", ""),
                        task_id=event.task_id,
                    )

            if data and data.get("summary"):
                post_message(
                    from_agent=agent_name,
                    to_agent="orchestrator",
                    message=f"[bg] {event.file_path}: {data['summary']}",
                    task_id=event.task_id,
                )

        except Exception as e:
            log_error(f"_process_event({agent_name}, {event.file_path}) error: {e}")


# Global singleton
_agent_pool: BackgroundAgentPool | None = None
_pool_lock = threading.Lock()


def get_agent_pool() -> BackgroundAgentPool:
    """Get global agent pool"""
    global _agent_pool
    with _pool_lock:
        if _agent_pool is None:
            _agent_pool = BackgroundAgentPool()
        return _agent_pool
