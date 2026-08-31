"""
Phase 1 golden-path workflow tests.

Exercises the governed edit loop under MockLLM with real sqlite + temp disk:
  orchestrator decision → developer payload → validate → proposal →
  reviewer APPROVE → apply → materialize → assert file content + counters

No network. No new dependencies (stdlib MockLLM + pytest).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# Thin harness mirroring task_runner's developer → materialize path
# ---------------------------------------------------------------------------


def run_governed_edit_once(
    *,
    target_file: str,
    developer_raw: str,
    project_dir: Path,
    selected_mode: str = "find_replace",
    fallback_used: bool = False,
    final_mode: str | None = None,
) -> dict:
    """
    One-shot governed edit:
      validate → create_proposal → approve → apply → materialize
    Returns a progress-like dict for assertions.
    """
    from core import config as config_mod
    from core.edit_response_validator import validate_developer_edit_response
    from file_editing.db import get_db_connection
    from file_editing.editing import apply_edit_proposal
    from file_editing.writer import materialize_proposal
    from workflow.proposal_builder import create_proposal_from_developer_output

    progress: dict[str, Any] = {
        "valid_edit_payloads": 0,
        "edit_failures": 0,
        "fallback_successes": 0,
        "materialize_successes": 0,
        "files_modified": 0,
        "proposal_id": None,
        "final_content": None,
        "validation_mode": None,
        "apply_status": None,
        "materialize_status": None,
    }

    # Ensure writes land under the temp project root
    original_get_config = config_mod.get_config

    def _cfg():
        c = dict(original_get_config())
        c["project_directory"] = str(project_dir)
        return c

    config_mod.get_config = _cfg
    try:
        validation = validate_developer_edit_response(developer_raw)
        if not validation.is_valid:
            progress["edit_failures"] += 1
            progress["validation_error"] = validation.reason
            return progress

        progress["valid_edit_payloads"] += 1
        progress["validation_mode"] = validation.detected_mode
        if fallback_used:
            progress["fallback_successes"] += 1

        # Prefer parsed dict from validator; fall back to raw string
        payload = validation.data if validation.data is not None else developer_raw
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError:
                payload = developer_raw

        prop = create_proposal_from_developer_output(
            payload,
            proposed_by_agent_id=1,
            target_file_path=target_file,
            selected_mode=selected_mode,
            fallback_used=fallback_used,
            final_mode=final_mode or validation.detected_mode or selected_mode,
        )
        if prop.get("status") != "success":
            progress["edit_failures"] += 1
            progress["proposal_error"] = prop
            return progress

        proposal_id = prop["proposal_id"]
        progress["proposal_id"] = proposal_id

        with get_db_connection() as conn:
            conn.execute(
                "UPDATE edit_proposals SET status = 'approved' WHERE proposal_id = ?",
                (proposal_id,),
            )

        apply_result = apply_edit_proposal(proposal_id)
        progress["apply_status"] = apply_result.get("status")
        if apply_result.get("status") != "success":
            progress["edit_failures"] += 1
            return progress

        mat = materialize_proposal(proposal_id)
        progress["materialize_status"] = mat.get("status")
        if mat.get("status") == "success":
            progress["materialize_successes"] += 1
            progress["files_modified"] += 1
            # Read from disk under project_dir
            disk_path = project_dir / target_file
            if disk_path.exists():
                progress["final_content"] = disk_path.read_text(encoding="utf-8")
        else:
            progress["edit_failures"] += 1

        return progress
    finally:
        config_mod.get_config = original_get_config


def _init_file(rel_path: str, content: str, project_dir: Path) -> None:
    from file_editing.writer import initialize_file_lines

    # Also seed on disk so materialize path is realistic
    full = project_dir / rel_path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")
    initialize_file_lines(rel_path, content)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGoldenPathFindReplace:
    def test_orchestrator_developer_reviewer_materialize(self, temp_db, mock_llm, tmp_path):
        """Full golden path with MockLLM-scripted agent responses."""
        project_dir = tmp_path / "proj"
        project_dir.mkdir()
        rel = "src/app.py"
        _init_file(rel, "name = old_value\nprint(name)\n", project_dir)

        mock_llm.set_response(
            "orchestrator",
            json.dumps(
                {
                    "next_agent": "developer",
                    "instructions": f"Rename old_value to new_value in {rel}",
                    "files_needed": [rel],
                    "reasoning": "Identifier rename",
                }
            ),
        )
        developer_payload = {
            "target_file_path": rel,
            "summary": "Rename old_value to new_value",
            "rationale": "Consistent naming for the application constant",
            "operations": [
                {
                    "type": "find_replace",
                    "find": "old_value",
                    "replace": "new_value",
                    "rationale": "Rename identifier",
                }
            ],
        }
        mock_llm.set_response("developer", json.dumps(developer_payload))
        mock_llm.set_response(
            "reviewer",
            json.dumps({"decision": "APPROVE", "reason": "Safe rename", "suggestions": []}),
        )

        with mock_llm.patch_call_agent():
            from agents.base import call_agent

            orch = json.loads(call_agent("orchestrator", "start", task_id="gold1"))
            assert orch["next_agent"] == "developer"

            raw = call_agent("developer", orch["instructions"], task_id="gold1")
            review = json.loads(call_agent("reviewer", raw, task_id="gold1"))
            assert review["decision"] == "APPROVE"

        progress = run_governed_edit_once(
            target_file=rel,
            developer_raw=raw,
            project_dir=project_dir,
            selected_mode="find_replace",
            final_mode="find_replace",
        )

        assert progress["valid_edit_payloads"] == 1
        assert progress["edit_failures"] == 0
        assert progress["materialize_successes"] == 1
        assert progress["files_modified"] == 1
        assert progress["apply_status"] == "success"
        assert progress["materialize_status"] == "success"
        assert progress["final_content"] is not None
        assert "new_value" in progress["final_content"]
        assert "old_value" not in progress["final_content"]


class TestGoldenPathFallback:
    def test_invalid_json_then_find_replace_succeeds(self, temp_db, mock_llm, tmp_path):
        """GUID attempt fails validation; fallback find_replace materializes."""
        from core.edit_response_validator import validate_developer_edit_response
        from workflow.edit_mode_selector import next_fallback_mode

        project_dir = tmp_path / "proj"
        project_dir.mkdir()
        rel = "lib/util.py"
        _init_file(rel, "x = ALPHA\ny = ALPHA\n", project_dir)

        mock_llm.set_responses(
            "developer",
            [
                "I am unable to emit proper JSON for GUID mode right now.",
                json.dumps(
                    {
                        "target_file_path": rel,
                        "summary": "Rename ALPHA to BETA",
                        "rationale": "Update constant across the utility module",
                        "operations": [
                            {
                                "type": "find_replace",
                                "find": "ALPHA",
                                "replace": "BETA",
                                "rationale": "Rename constant",
                            }
                        ],
                    }
                ),
            ],
        )

        mode = "guid"
        tried = []
        final_raw = None
        fallback_used = False

        with mock_llm.patch_call_agent():
            from agents.base import call_agent

            for _ in range(4):
                raw = call_agent("developer", f"edit with mode={mode}", task_id="gold_fb")
                v = validate_developer_edit_response(raw)
                if v.is_valid:
                    final_raw = raw
                    break
                tried.append(mode)
                nxt = next_fallback_mode(mode, already_tried=tried)
                if not nxt:
                    break
                mode = nxt
                fallback_used = True

        assert final_raw is not None
        assert "guid" in tried

        progress = run_governed_edit_once(
            target_file=rel,
            developer_raw=final_raw,
            project_dir=project_dir,
            selected_mode="guid",
            fallback_used=fallback_used,
            final_mode="find_replace",
        )

        assert progress["valid_edit_payloads"] == 1
        assert progress["fallback_successes"] == 1
        assert progress["materialize_successes"] == 1
        assert "BETA" in (progress["final_content"] or "")
        assert "ALPHA" not in (progress["final_content"] or "")


class TestGoldenPathFullReplace:
    def test_small_file_full_replace(self, temp_db, mock_llm, tmp_path):
        from workflow.edit_mode_selector import MODE_FULL_REPLACE, select_edit_mode

        project_dir = tmp_path / "proj"
        project_dir.mkdir()
        rel = "tiny.py"
        content = "a = 1\nb = 2\n"
        _init_file(rel, content, project_dir)

        decision = select_edit_mode(
            file_line_count=2,
            instructions="rewrite the entire helper module",
        )
        assert decision.selected_mode == MODE_FULL_REPLACE

        new_body = "a = 100\nb = 200\nc = 300\n"
        mock_llm.set_response(
            "developer",
            json.dumps(
                {
                    "target_file_path": rel,
                    "summary": "Rewrite tiny helper",
                    "rationale": "Full rewrite of a small configuration helper module",
                    "operations": [
                        {
                            "type": "full_replace",
                            "new_content": new_body,
                            "rationale": "Replace entire file",
                        }
                    ],
                }
            ),
        )

        with mock_llm.patch_call_agent():
            from agents.base import call_agent

            raw = call_agent("developer", "rewrite tiny.py", task_id="gold_fr")

        progress = run_governed_edit_once(
            target_file=rel,
            developer_raw=raw,
            project_dir=project_dir,
            selected_mode="full_replace",
            final_mode="full_replace",
        )

        assert progress["valid_edit_payloads"] == 1
        assert progress["materialize_successes"] == 1
        assert progress["final_content"] is not None
        assert "c = 300" in progress["final_content"]


class TestGoldenPathCounters:
    def test_failed_validation_increments_edit_failures(self, temp_db, tmp_path):
        project_dir = tmp_path / "proj"
        project_dir.mkdir()
        rel = "x.py"
        _init_file(rel, "z = 1\n", project_dir)

        progress = run_governed_edit_once(
            target_file=rel,
            developer_raw="this is not json at all",
            project_dir=project_dir,
        )
        assert progress["valid_edit_payloads"] == 0
        assert progress["edit_failures"] == 1
        assert progress["materialize_successes"] == 0
