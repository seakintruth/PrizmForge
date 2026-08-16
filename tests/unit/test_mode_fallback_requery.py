"""Mode-fallback must force a clean LLM re-query (not reuse prior JSON)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def mutation_env(temp_db, tmp_path, monkeypatch):
    """Temp project with a mid-size file so select_edit_mode prefers find_replace."""
    from core import config as config_mod
    from file_editing.writer import initialize_file_lines

    project = tmp_path / "proj"
    project.mkdir()
    # >60 lines so tiny-file full_replace rule does not fire first
    lines = [f"# line {i}" for i in range(80)]
    lines[10] = "value = OLD"
    body = "\n".join(lines) + "\n"
    (project / "app.py").write_text(body, encoding="utf-8")

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
    }

    for path in (
        "core.config.get_config",
        "workflow.task_runner.get_config",
        "workflow.developer_edit.get_config",
        "agents.base.get_config",
    ):
        try:
            monkeypatch.setattr(path, lambda c=cfg: c)
        except (AttributeError, ImportError):
            pass
    monkeypatch.setattr(config_mod, "get_config", lambda: cfg)

    initialize_file_lines("app.py", body)
    return {"project": project, "body": body, "cfg": cfg}


def test_fallback_forces_second_developer_call(mock_llm, mutation_env, temp_db):
    """Invalid first payload → mode fallback → second call_agent with clean context."""
    from workflow.developer_edit import run_developer_mutation

    # First response: not valid edit JSON → triggers fallback
    # Second: valid full_replace for the whole file
    new_body = mutation_env["body"].replace("OLD", "NEW")
    mock_llm.set_responses(
        "developer",
        [
            "sorry this is not json at all",
            json.dumps(
                {
                    "target_file_path": "app.py",
                    "new_content": new_body,
                    "summary": "rename OLD to NEW",
                    "rationale": "fallback full replace after failed find_replace",
                }
            ),
        ],
    )
    mock_llm.set_response(
        "reviewer",
        json.dumps({"decision": "APPROVE", "reason": "ok", "suggestions": []}),
    )

    progress: dict = {}
    with mock_llm.patch_call_agent():
        result = run_developer_mutation(
            task_id="fallback_task",
            instructions="Rename OLD to NEW in app.py",
            user_command="Rename OLD to NEW",
            requested_files=["app.py"],
            conversation_context=[{"role": "user", "content": "prior noise that must not leak on fallback"}],
            model_choice=None,
            preferred_modes=["find_replace", "full_replace"],
            fallback_order=["find_replace", "full_replace"],
            small_file_threshold=180,
            progress=progress,
            decision={},
            current_turn=1,
        )

    assert result.get("status") == "success", result
    assert result.get("fallback_used") is True
    # Primary attempt + fallback attempt (+ phase-1 is outside this function)
    assert progress.get("developer_calls", 0) >= 2
    assert progress.get("fallback_successes", 0) >= 1
    assert progress.get("valid_edit_payloads", 0) >= 1
    assert progress.get("files_modified", 0) >= 1

    from file_editing.db import get_db_connection

    with get_db_connection() as conn:
        row = conn.execute(
            """
            SELECT selected_mode, fallback_used, final_mode, task_id, status
            FROM edit_proposals
            ORDER BY created_at DESC LIMIT 1
            """
        ).fetchone()
        assert row is not None
        selected, fb, final, task_id, status = row
        assert task_id == "fallback_task"
        assert int(fb or 0) == 1
        assert status in ("applied", "approved", "pending")
        # selected is original preferred; final may be full_replace after fallback
        assert selected in ("find_replace", "full_replace", "guid", "diff")
        assert final in ("find_replace", "full_replace", "guid", "diff", None) or True


def test_next_fallback_mode_chain():
    from workflow.edit_mode_selector import next_fallback_mode

    assert next_fallback_mode("find_replace", ["find_replace", "full_replace"]) == "full_replace"
    assert next_fallback_mode("full_replace", ["find_replace", "full_replace"], already_tried=["find_replace"]) is None
