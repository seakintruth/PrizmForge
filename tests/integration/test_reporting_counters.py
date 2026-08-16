"""Regression: task progress counters must match DB after materialize."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# Keep with normal suite — fast under MockLLM


@pytest.fixture
def counter_env(temp_db, tmp_path, monkeypatch):
    from core import config as config_mod
    from file_editing.writer import initialize_file_lines

    project = tmp_path / "proj"
    project.mkdir()
    (project / "app.py").write_text("value = OLD\n", encoding="utf-8")

    cfg = {
        "project_directory": str(project),
        "background_agents_enabled": False,
        "git": False,
        "file_editing": {
            "preferred_modes": ["find_replace", "full_replace"],
            "fallback_order": ["find_replace", "full_replace"],
            "small_file_threshold_lines": 180,
        },
        "endpoints": {},
        "default_model": "mock-model",
        "token_budget": {"max_tokens_per_4h": 1_000_000},
        "default_iteration_minutes": 1,
        "min_iterations_before_complete": 1,
    }
    monkeypatch.setattr(config_mod, "get_config", lambda: cfg)
    for path in (
        "workflow.task_runner.get_config",
        "workflow.developer_edit.get_config",
        "agents.orchestrator.get_config",
        "agents.base.get_config",
    ):
        try:
            monkeypatch.setattr(path, lambda c=cfg: c)
        except (AttributeError, ImportError):
            pass

    initialize_file_lines("app.py", "value = OLD\n")
    return project


def test_files_modified_matches_applied_proposals(mock_llm, counter_env, temp_db):
    """After a successful cycle, proposals carry task_id and progress is non-zero."""
    from file_editing.db import get_db_connection, reconstruct_file_content
    from workflow.task_runner import run_task_cycle

    task_id = "counter_task_1"
    orch_dev = json.dumps(
        {
            "next_agent": "developer",
            "instructions": "Rename OLD to NEW in app.py",
            "files_needed": ["app.py"],
            "reasoning": "rename",
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
                    "rationale": "Consistent naming",
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

    with mock_llm.patch_call_agent():
        run_task_cycle(task_id, "Rename OLD to NEW in app.py", max_turns=3)

    with get_db_connection() as conn:
        # Content changed
        row = conn.execute("SELECT file_id FROM files WHERE file_path = ?", ("app.py",)).fetchone()
        assert row is not None
        body = reconstruct_file_content(conn, row[0])
        assert "NEW" in body

        # Proposals for this task must carry task_id
        props = conn.execute(
            """
            SELECT proposal_id, task_id, status, fallback_used
            FROM edit_proposals
            WHERE task_id = ?
            """,
            (task_id,),
        ).fetchall()
        assert len(props) >= 1, "expected at least one proposal with task_id set"
        for _pid, tid, status, _fb in props:
            assert tid == task_id
            assert status in ("applied", "approved", "pending", "rejected")

        # No orphan applied proposals missing task_id from this run
        orphans = conn.execute(
            """
            SELECT COUNT(*) FROM edit_proposals
            WHERE status IN ('applied', 'approved') AND (task_id IS NULL OR task_id = '')
            """
        ).fetchone()[0]
        assert orphans == 0
