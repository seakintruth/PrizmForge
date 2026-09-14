"""§14.4 driver-wiring integration: one terminal task end-to-end with a mocked runner.

Setup runs in the cloned checkout, the (mocked) agent edits, and the command
verifier passes/fails against the checkout — hermetically, no real LLM.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


def _terminal_task(url: str, commit: str, *, command: str = "test -f marker.txt"):
    from harness.benchmark.tasks import parse_bench_task

    return parse_bench_task(
        {
            "task_id": "c2_marker",
            "kind": "terminal",
            "seed": "Create marker.txt at the repo root",
            "repo": {"url": url, "commit": commit},
            "setup": ["git config user.email bench@test", "git config user.name bench"],
            "verifier": {"command": command, "timeout": 30},
            "k": 1,
            "contract": [{"file_path": "code.py", "fragment": "marker", "mode": "contains"}],
        }
    )


def _make_origins_repo(root: Path) -> tuple[str, str]:
    root.mkdir(parents=True, exist_ok=True)
    (root / "code.py").write_text("x = 1\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email", "bench@test"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "bench"], check=True)
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "seed"], check=True)
    commit = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
    return str(root), commit


def _mock_agent(do_edit: bool):
    """Mock run_task_cycle: makes the edit directly in the checkout + evidence rows."""
    from core.db_connection import get_db_connection
    from core.db_helpers import create_task, mark_task_status

    def _run(task_id, user_command, max_turns=20, time_box_minutes=None):
        create_task(task_id, user_command)
        proj = _project_dir()
        if do_edit:
            _ev = proj / "marker.txt"
            _ev.write_text("done\n", encoding="utf-8")
            with get_db_connection() as conn:
                conn.execute(
                    "INSERT INTO edit_proposals (proposal_id, task_id, target_file_path, edit_payload, status) "
                    "VALUES ('mock-p', ?, 'marker.txt', '{}', 'applied')",
                    (task_id,),
                )
                conn.execute(
                    "INSERT INTO file_write_log (proposal_id, file_id, status, started_at, completed_at) "
                    "VALUES ('mock-p', 1, 'success', '2026-01-01', '2026-01-01')",
                )
            mark_task_status(task_id, "completed", "solved")
        else:
            mark_task_status(task_id, "failed", "unsolved")

    return _run


def _project_dir():
    from core.config import get_config

    return Path(get_config()["project_directory"])


@pytest.mark.usefixtures("temp_db")
class TestTerminalDriverE2E:
    def test_terminal_task_passes_via_command_verifier(self, tmp_path, monkeypatch):
        import workflow.task_runner as tr
        from harness.benchmark.driver import run_benchmark

        monkeypatch.setattr(tr, "run_task_cycle", _mock_agent(do_edit=True))
        url, commit = _make_origins_repo(tmp_path / "origins")
        task = _terminal_task(url, commit)
        results = run_benchmark(iteration=1, tasks=[task], max_turns=5, project_dir=tmp_path / "base")
        assert results["total_trials"] == 1
        assert results["passed_trials"] == 1
        assert results["tasks"][0]["trials"][0]["note"] == "command_ok"

    def test_terminal_task_fails_without_edit_evidence(self, tmp_path, monkeypatch):
        import workflow.task_runner as tr
        from harness.benchmark.driver import run_benchmark

        monkeypatch.setattr(tr, "run_task_cycle", _mock_agent(do_edit=False))
        url, commit = _make_origins_repo(tmp_path / "origins")
        task = _terminal_task(url, commit)
        results = run_benchmark(iteration=1, tasks=[task], max_turns=5, project_dir=tmp_path / "base")
        assert results["passed_trials"] == 0
        assert results["tasks"][0]["trials"][0]["note"] == "status:failed"

    def test_terminal_task_content_contract_rejected_when_verifier_fails(self, tmp_path, monkeypatch):
        import workflow.task_runner as tr
        from harness.benchmark.driver import run_benchmark

        monkeypatch.setattr(tr, "run_task_cycle", _mock_agent(do_edit=True))
        url, commit = _make_origins_repo(tmp_path / "origins")
        task = _terminal_task(url, commit, command="test -f does-not-exist.txt")
        results = run_benchmark(iteration=1, tasks=[task], max_turns=5, project_dir=tmp_path / "base")
        assert results["passed_trials"] == 0
        assert "command:" in results["tasks"][0]["trials"][0]["note"]
