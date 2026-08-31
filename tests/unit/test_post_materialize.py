"""Workstream C — post-materialize targeted re-verify (§5).

Acceptance criteria (§5.5):
  1. After mock successful materialize, exactly one high-priority queue entry
     for that path (bounded set).
  2. After git failure, no "celebration" counters; developer receives path list
     from parsed ruff output when possible.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.db_connection import get_db_connection
from workflow.path_targets import parse_hook_cited_files
from workflow.post_materialize import apply_materialize_outcome, notify_path_changed, queue_localized_verify

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class _FakePool:
    def __init__(self, running: bool = True):
        self.running = running
        self.events: list[SimpleNamespace] = []

    def queue_file_change(self, file_path: str, operation: str, content: str | None):
        self.events.append(SimpleNamespace(file_path=file_path, operation=operation, content=content, priority=1))


@pytest.fixture
def running_pool(monkeypatch):
    pool = _FakePool(running=True)
    monkeypatch.setattr("agents.parallel_workers.get_agent_pool", lambda: pool)
    monkeypatch.setattr("core.file_operations.get_file_content_from_db", lambda _path: "src")
    return pool


class TestQueueLocalizedVerify:
    def test_exactly_one_high_priority_entry_per_path(self, temp_db, running_pool):
        counts = queue_localized_verify(["a.py", "b.py", "a.py"], "t_c")
        assert counts == 2
        assert [e.file_path for e in running_pool.events] == ["a.py", "b.py"]
        assert all(e.operation == "verify" for e in running_pool.events)
        assert all(e.priority == 1 for e in running_pool.events)

    def test_no_queue_when_pool_not_running(self, temp_db, monkeypatch):
        monkeypatch.setattr("agents.parallel_workers.get_agent_pool", lambda: _FakePool(running=False))
        assert queue_localized_verify(["a.py"], "t_c") == 0


class TestNotifyPathChanged:
    def test_creates_single_orchestrator_message(self, temp_db):
        notify_path_changed(["a.py", "lib/b.py"], "t_c")
        notify_path_changed([], "t_c")
        with get_db_connection() as conn:
            rows = conn.execute("SELECT content, priority FROM messages WHERE task_id = 't_c'").fetchall()
        assert len(rows) == 1
        assert "Path changed: a.py, lib/b.py" in rows[0][0]
        assert rows[0][1] == "HIGH"


class TestApplyMaterializeOutcome:
    def test_success_increments_counters_and_localizes_verify(self, temp_db, running_pool):
        progress = {"files_modified": 0, "materialize_successes": 0, "edit_failures": 0}
        mat = {"status": "success", "proposal_id": "p1", "materialized_files": ["a.py", "b.py"]}
        status = apply_materialize_outcome(mat, task_id="t_c", progress=progress)
        assert status == "success"
        assert progress == {"files_modified": 1, "materialize_successes": 1, "edit_failures": 0}
        assert [e.file_path for e in running_pool.events] == ["a.py", "b.py"]
        with get_db_connection() as conn:
            msg = conn.execute("SELECT COUNT(*) FROM messages WHERE task_id = 't_c'").fetchone()[0]
            ev = conn.execute("SELECT COUNT(*) FROM events WHERE type = 'edit.materialized'").fetchone()[0]
        assert msg == 1
        assert ev == 1

    def test_git_failure_no_celebration_and_cites_files(self, temp_db):
        progress = {"files_modified": 4, "materialize_successes": 4, "edit_failures": 0}
        stderr = "app.py:3:5: F401 'os' imported but unused\nlib/util.py:12:1: E402 module level import not at top of file\nsome prose line without a path\n"
        mat = {
            "status": "git_failed",
            "proposal_id": "p_git",
            "materialized_files": ["app.py"],
            "git_failed": {
                "attempted": True,
                "stage": "pre-commit",
                "code": 1,
                "stderr": stderr,
                "file_path": "app.py",
            },
        }
        status = apply_materialize_outcome(mat, task_id="t_c", progress=progress)
        assert status == "git_failed"
        assert progress == {"files_modified": 4, "materialize_successes": 4, "edit_failures": 0}
        with get_db_connection() as conn:
            fb = conn.execute("SELECT message FROM agent_feedback WHERE task_id = 't_c'").fetchone()
            ev = conn.execute("SELECT COUNT(*) FROM events WHERE type = 'edit.materialized'").fetchone()[0]
            git_ev = conn.execute("SELECT COUNT(*) FROM events WHERE type = 'edit.git_failed'").fetchone()[0]
        assert ev == 0, "git failure must never emit edit.materialized"
        assert git_ev == 1
        assert fb is not None
        assert "HOOK CITED FILES:** app.py, lib/util.py" in fb[0]
        assert "fix these specific files" in fb[0]

    def test_other_failure_increments_failure_counter(self, temp_db):
        progress = {"files_modified": 0, "edit_failures": 0}
        status = apply_materialize_outcome({"status": "conflicted", "proposal_id": "p2"}, task_id="t_c", progress=progress)
        assert status == "conflicted"
        assert progress["edit_failures"] == 1
        with get_db_connection() as conn:
            ev = conn.execute("SELECT COUNT(*) FROM events WHERE type = 'edit.failed'").fetchone()[0]
        assert ev == 1


class TestParseHookCitedFiles:
    def test_parses_ruff_flake_diagnostics(self):
        stderr = (
            "app.py:3:5: F401 'os' imported but unused\n"
            "  app.py:10:1: E305 expected 2 blank lines\n"
            "lib/util.py:12:1: E402 module level import not at top\n"
            "not a file line\n"
        )
        assert parse_hook_cited_files(stderr) == ["app.py", "lib/util.py"]

    def test_dedupes_and_caps(self):
        stderr = "a.py:1:2: X\n" * 10
        assert parse_hook_cited_files(stderr, max_files=3) == ["a.py"]
        stderr2 = "\n".join(f"f{i}.py:1:1: X" for i in range(8))
        assert len(parse_hook_cited_files(stderr2, max_files=4)) == 4

    def test_empty_and_junk(self):
        assert parse_hook_cited_files(None) == []
        assert parse_hook_cited_files("  ") == []
        assert parse_hook_cited_files("README has no diagnostics") == []
