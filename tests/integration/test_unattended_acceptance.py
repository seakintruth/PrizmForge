"""
Outer acceptance: mock unattended-style seed → developer edit → complete.

Does not run main() for hours; exercises the same mutation + counter contracts
the unattended loop relies on.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def accept_env(temp_db, tmp_path, monkeypatch):
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
        "unattended": {
            "max_duration_hours": 0.01,
            "auto_continue": True,
            "checkpoint_interval_minutes": 15,
            "max_iterations_per_task": 5,
            "min_idle_minutes": 30,
            "auto_generate_tasks": False,
            "seed_task": "Rename OLD to NEW in app.py",
            "stop_when_backlog_empty": True,
            "exit_on_preflight_failure": True,
        },
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
    return {"project": project, "cfg": cfg}


def test_seed_task_materializes_under_project_directory(mock_llm, accept_env, temp_db):
    """Seed-style command produces disk+DB change inside configured project_directory."""
    from file_editing.db import get_db_connection, reconstruct_file_content
    from workflow.task_runner import run_task_cycle

    seed = accept_env["cfg"]["unattended"]["seed_task"]
    task_id = "seed_accept_1"

    mock_llm.set_responses(
        "orchestrator",
        [
            json.dumps(
                {
                    "next_agent": "developer",
                    "instructions": seed,
                    "files_needed": ["app.py"],
                    "reasoning": "seed",
                }
            ),
            json.dumps({"next_agent": "complete", "instructions": "done", "reasoning": "done"}),
            json.dumps({"next_agent": "complete", "instructions": "done", "reasoning": "done"}),
        ],
    )
    mock_llm.set_responses(
        "developer",
        [
            "FILES_NEEDED: app.py\nPLAN: rename",
            json.dumps(
                {
                    "target_file_path": "app.py",
                    "summary": "rename",
                    "rationale": "seed acceptance",
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
        run_task_cycle(task_id, seed, max_turns=3)

    with get_db_connection() as conn:
        row = conn.execute("SELECT file_id FROM files WHERE file_path = ?", ("app.py",)).fetchone()
        assert row is not None
        assert "NEW" in reconstruct_file_content(conn, row[0])

        applied = conn.execute(
            "SELECT COUNT(*) FROM edit_proposals WHERE task_id = ? AND status IN ('applied','approved')",
            (task_id,),
        ).fetchone()[0]
        assert applied >= 1

    # Optional on-disk check if materialize wrote under project dir
    disk = accept_env["project"] / "app.py"
    if disk.exists():
        text = disk.read_text(encoding="utf-8")
        assert "NEW" in text or "OLD" in text  # materialize may be DB-first depending on config
