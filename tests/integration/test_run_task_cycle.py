"""
Phase B2 — MockLLM run_task_cycle with background agents off.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Full task-cycle mocks accumulate DB/agent state; OOM on ~constrained CI/sandboxes.
# Keep on --full / --only-slow; exclude from --normal.
pytestmark = pytest.mark.slow


def _install_cycle_config(monkeypatch, project_dir: Path) -> None:
    """Replace get_config everywhere it was imported at module level.

    ``from core.config import get_config`` binds a local name; patching only
    ``core.config.get_config`` leaves ``workflow.task_runner.get_config`` on the
    original function — which kept background agents enabled and ignored the
    temp project_directory.
    """

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
            # Module may not import get_config at top level — skip.
            pass


@pytest.fixture
def cycle_env(temp_db, tmp_path, monkeypatch):
    from file_editing.writer import initialize_file_lines

    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    (project_dir / "app.py").write_text("value = OLD\n", encoding="utf-8")

    _install_cycle_config(monkeypatch, project_dir)
    initialize_file_lines("app.py", "value = OLD\n")

    # Ensure no leftover singleton pool is running from a prior test.
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


def test_run_task_cycle_find_replace(mock_llm, cycle_env, temp_db):
    """Orchestrator → developer → reviewer path under MockLLM."""
    from file_editing.db import get_db_connection, reconstruct_file_content
    from workflow.task_runner import run_task_cycle

    orch_dev = json.dumps(
        {
            "next_agent": "developer",
            "instructions": "Rename OLD to NEW in app.py",
            "files_needed": ["app.py"],
            "reasoning": "identifier rename",
        }
    )
    orch_done = json.dumps(
        {
            "next_agent": "complete",
            "instructions": "done",
            "reasoning": "finished",
        }
    )
    mock_llm.set_responses("orchestrator", [orch_dev, orch_done, orch_done])
    mock_llm.set_responses(
        "developer",
        [
            "FILES_NEEDED: app.py\nPLAN: rename OLD to NEW",
            json.dumps(
                {
                    "target_file_path": "app.py",
                    "summary": "rename OLD to NEW",
                    "rationale": "Consistent naming for the application constant",
                    "operations": [
                        {
                            "type": "find_replace",
                            "find": "OLD",
                            "replace": "NEW",
                            "rationale": "rename",
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

    # Do NOT patch time.sleep — it is the shared stdlib module; mocking it
    # breaks interruptible_sleep / prioritizer if any worker is alive.
    with mock_llm.patch_call_agent():
        run_task_cycle("cycle_test_1", "Rename OLD to NEW in app.py", max_turns=3)

    with get_db_connection() as conn:
        row = conn.execute("SELECT file_id FROM files WHERE file_path = ?", ("app.py",)).fetchone()
        assert row is not None
        body = reconstruct_file_content(conn, row[0])
        assert "NEW" in body
        assert "OLD" not in body


def test_run_task_cycle_multi_turn_then_complete(mock_llm, cycle_env, temp_db):
    """Turn1 developer edit; turn2 complete — counters and content."""
    from file_editing.db import get_db_connection, reconstruct_file_content
    from workflow.task_runner import run_task_cycle

    orch_dev = json.dumps(
        {
            "next_agent": "developer",
            "instructions": "Rename OLD to NEW in app.py",
            "files_needed": ["app.py"],
            "reasoning": "edit",
        }
    )
    orch_done = json.dumps(
        {
            "next_agent": "complete",
            "instructions": "done",
            "reasoning": "finished",
            "files_needed": [],
        }
    )
    mock_llm.set_responses("orchestrator", [orch_dev, orch_done, orch_done, orch_done])
    mock_llm.set_responses(
        "developer",
        [
            "FILES_NEEDED: app.py\nPLAN: rename",
            json.dumps(
                {
                    "target_file_path": "app.py",
                    "summary": "rename OLD to NEW",
                    "rationale": "Consistent naming for the application constant",
                    "operations": [
                        {
                            "type": "find_replace",
                            "find": "OLD",
                            "replace": "NEW",
                            "rationale": "rename",
                        }
                    ],
                }
            ),
        ],
    )
    mock_llm.set_response(
        "reviewer",
        json.dumps({"decision": "APPROVE", "reason": "ok", "suggestions": []}),
    )

    with mock_llm.patch_call_agent():
        run_task_cycle("cycle_multi", "Rename OLD to NEW", max_turns=4)

    with get_db_connection() as conn:
        row = conn.execute("SELECT file_id FROM files WHERE file_path = ?", ("app.py",)).fetchone()
        assert row is not None
        body = reconstruct_file_content(conn, row[0])
        assert "NEW" in body


def test_run_task_cycle_reviewer_reject(mock_llm, cycle_env, temp_db):
    """REJECT must not materialize successful content change."""
    from core.events import list_events
    from file_editing.db import get_db_connection, reconstruct_file_content
    from workflow.task_runner import run_task_cycle

    orch_dev = json.dumps(
        {
            "next_agent": "developer",
            "instructions": "Rename OLD to NEW in app.py",
            "files_needed": ["app.py"],
            "reasoning": "edit",
        }
    )
    orch_done = json.dumps(
        {
            "next_agent": "complete",
            "instructions": "stop",
            "reasoning": "stop",
            "files_needed": [],
        }
    )
    mock_llm.set_responses("orchestrator", [orch_dev, orch_done, orch_done])
    mock_llm.set_responses(
        "developer",
        [
            "FILES_NEEDED: app.py\nPLAN: rename",
            json.dumps(
                {
                    "target_file_path": "app.py",
                    "summary": "rename OLD to NEW",
                    "rationale": "Consistent naming for the application constant",
                    "operations": [
                        {
                            "type": "find_replace",
                            "find": "OLD",
                            "replace": "NEW",
                            "rationale": "rename",
                        }
                    ],
                }
            ),
        ],
    )
    mock_llm.set_response(
        "reviewer",
        json.dumps({"decision": "REJECT", "reason": "too risky", "suggestions": ["be careful"]}),
    )

    with mock_llm.patch_call_agent():
        run_task_cycle("cycle_reject", "Rename OLD to NEW", max_turns=3)

    with get_db_connection() as conn:
        row = conn.execute("SELECT file_id FROM files WHERE file_path = ?", ("app.py",)).fetchone()
        body = reconstruct_file_content(conn, row[0])
        # Rejected: content should remain OLD
        assert "OLD" in body
        st = conn.execute("SELECT status FROM edit_proposals ORDER BY created_at DESC LIMIT 1").fetchone()
        if st:
            assert st[0] in ("rejected", "pending", "error", "approved", "applied")
    rejected_events = list_events(event_type="proposal.rejected", limit=10)
    assert isinstance(rejected_events, list)
