"""
tests/integration/test_harness_rollouts_cycle.py

Full-cycle coverage for the harness-evolution P0 rollout recording
(docs/TODO.md §12.1): run_task_cycle must create a rollout row carrying
the harness fingerprint and finalize it (with token backfill) when the
cycle ends.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

pytestmark = pytest.mark.slow


def _install_cycle_config(monkeypatch, project_dir: Path) -> None:
    """Replace get_config everywhere it was imported at module level."""

    def fake_config():
        return {
            "project_directory": str(project_dir),
            "background_agents_enabled": False,
            "file_editing": {
                "preferred_modes": ["find_replace", "full_replace"],
                "fallback_order": ["find_replace", "full_replace"],
                "small_file_threshold_lines": 180,
            },
            "endpoints": {},
            "git": False,
            "token_budget": {"max_tokens_per_4h": 1_000_000},
            "default_model": "mock-model",
            "default_iteration_minutes": 1,
            "min_iterations_before_complete": 1,
            "background_agents": {},
            "background_feeder": {},
        }

    targets = [
        "core.config.get_config",
        "workflow.task_runner.get_config",
        "workflow.developer_edit.get_config",
        "workflow.edit_mode_selector.get_config",
        "agents.orchestrator.get_config",
        "agents.base.get_config",
        "agents.parallel_workers.get_config",
        "agents.reporter_worker.get_config",
        "agents.resource_controller_worker.get_config",
        "file_editing.writer.get_config",
    ]
    for path in targets:
        try:
            monkeypatch.setattr(path, fake_config)
        except (AttributeError, ImportError):
            pass


@pytest.fixture
def cycle_env(temp_db, tmp_path, monkeypatch):
    from file_editing.writer import initialize_file_lines

    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    (project_dir / "app.py").write_text("value = OLD\n", encoding="utf-8")

    _install_cycle_config(monkeypatch, project_dir)
    initialize_file_lines("app.py", "value = OLD\n")

    try:
        from agents.parallel_workers import get_agent_pool

        pool = get_agent_pool()
        if getattr(pool, "running", False):
            pool.stop()
    except Exception:
        pass

    yield project_dir

    try:
        from agents.parallel_workers import get_agent_pool

        get_agent_pool().stop()
    except Exception:
        pass


def test_run_task_cycle_records_and_finalizes_rollout(mock_llm, cycle_env, temp_db):
    """Orchestrator → developer → complete leaves a labeled rollout row."""
    from harness.fingerprint import latest_rollout
    from workflow.task_runner import run_task_cycle

    orch_dev = json.dumps(
        {
            "next_agent": "developer",
            "instructions": "Rename OLD to NEW in app.py",
            "files_needed": ["app.py"],
            "reasoning": "rename",
        }
    )
    orch_done = json.dumps({"next_agent": "complete", "instructions": "done", "reasoning": "finished"})
    mock_llm.set_responses("orchestrator", [orch_dev, orch_done, orch_done, orch_done])
    mock_llm.set_responses(
        "developer",
        [
            "FILES_NEEDED: app.py\nPLAN: rename",
            json.dumps(
                {
                    "target_file_path": "app.py",
                    "summary": "rename OLD to NEW",
                    "rationale": "Consistent spec for the application constant",
                    "operations": [
                        {
                            "type": "find_replace",
                            "find": "OLD",
                            "replace": "NEW",
                            "rationale": "Consistent spec for the constant",
                        }
                    ],
                }
            ),
        ],
    )
    mock_llm.set_response(
        "reviewer",
        json.dumps({"decision": "APPROVE", "reason": "safe", "suggestions": []}),
    )

    with mock_llm.patch_call_agent():
        run_task_cycle("cycle_harness_1", "Rename OLD to NEW in app.py", max_turns=3)

    from core.db_connection import get_db_connection

    with get_db_connection() as conn:
        task = conn.execute("SELECT status FROM tasks WHERE id = ?", ("cycle_harness_1",)).fetchone()
        assert task is not None and task[0] in ("completed", "no_change_required")

    row = latest_rollout("cycle_harness_1")
    assert row is not None
    assert row["task_id"] == "cycle_harness_1"
    assert row["status"] == "passed"
    assert row["infra_abort"] == 0
    assert row["harness_tag"]  # git describe / short sha
    assert len(row["prompt_hash"]) == 64
    assert row["completed_at"] is not None
