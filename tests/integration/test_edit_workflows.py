"""
Integration workflows for multi-mode governed editing + mocked LLM agents.

Covers:
- find_replace / full_replace / guid proposal → approve → apply pipelines
- mode selection + fallback chain
- edit response validation failure modes
- scripted multi-agent turns (orchestrator / developer / reviewer)

Pipeline cases measured ~0.03–0.05s — not a slow gate.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _guids_for(file_path: str):
    from file_editing.db import get_db_connection

    with get_db_connection() as conn:
        rows = conn.execute(
            """
            SELECT fl.line_guid FROM file_lines fl
            JOIN files f ON f.file_id = fl.file_id
            WHERE f.file_path = ? AND fl.is_deleted = 0
            ORDER BY fl.sort_order
            """,
            (file_path,),
        ).fetchall()
    return [r[0] for r in rows]


def _approve(proposal_id: str):
    from file_editing.db import get_db_connection

    with get_db_connection() as conn:
        conn.execute(
            "UPDATE edit_proposals SET status = 'approved' WHERE proposal_id = ?",
            (proposal_id,),
        )


def _content(file_path: str) -> str:
    from file_editing.db import get_db_connection, reconstruct_file_content

    with get_db_connection() as conn:
        row = conn.execute("SELECT file_id FROM files WHERE file_path = ?", (file_path,)).fetchone()
        assert row is not None, f"file not found: {file_path}"
        return reconstruct_file_content(conn, row[0])


# ---------------------------------------------------------------------------
# Pipeline workflows (no LLM required) — demoted from slow
# ---------------------------------------------------------------------------


class TestFindReplaceWorkflow:
    def test_proposal_approve_apply(self, temp_db):
        from file_editing.editing import apply_edit_proposal
        from file_editing.writer import initialize_file_lines
        from workflow.proposal_builder import create_proposal_from_developer_output

        initialize_file_lines("wf/rename.py", "x = old_name\ny = old_name\n")
        payload = {
            "target_file_path": "wf/rename.py",
            "summary": "Rename old_name to new_name",
            "rationale": "Consistent naming across the module",
            "operations": [
                {
                    "type": "find_replace",
                    "find": "old_name",
                    "replace": "new_name",
                    "rationale": "Rename identifier",
                }
            ],
        }
        prop = create_proposal_from_developer_output(
            payload,
            1,
            "wf/rename.py",
            selected_mode="guid",
            fallback_used=True,
            final_mode="find_replace",
        )
        assert prop["status"] == "success"
        assert prop["fallback_used"] is True
        assert prop["final_mode"] == "find_replace"

        _approve(prop["proposal_id"])
        result = apply_edit_proposal(prop["proposal_id"])
        assert result["status"] == "success"
        assert _content("wf/rename.py") == "x = new_name\ny = new_name\n"


class TestFullReplaceWorkflow:
    def test_proposal_approve_apply(self, temp_db):
        from file_editing.editing import apply_edit_proposal
        from file_editing.writer import initialize_file_lines
        from workflow.proposal_builder import create_proposal_from_developer_output

        initialize_file_lines("wf/small.py", "a = 1\nb = 2\n")
        payload = {
            "target_file_path": "wf/small.py",
            "summary": "Rewrite small file",
            "rationale": "Complete rewrite of a small helper module",
            "operations": [
                {
                    "type": "full_replace",
                    "new_content": "a = 10\nb = 20\nc = 30\n",
                    "rationale": "Replace entire file content",
                }
            ],
        }
        prop = create_proposal_from_developer_output(
            payload,
            1,
            "wf/small.py",
            selected_mode="full_replace",
            final_mode="full_replace",
        )
        assert prop["status"] == "success"
        _approve(prop["proposal_id"])
        result = apply_edit_proposal(prop["proposal_id"])
        assert result["status"] == "success"
        assert "c = 30" in _content("wf/small.py")


class TestGuidReplaceWorkflow:
    def test_proposal_approve_apply(self, temp_db):
        from file_editing.editing import apply_edit_proposal
        from file_editing.writer import initialize_file_lines
        from workflow.proposal_builder import create_proposal_from_developer_output

        initialize_file_lines(
            "wf/guid.py",
            "def hello():\n    print('old')\n    return True\n",
        )
        guids = _guids_for("wf/guid.py")
        assert len(guids) >= 2

        payload = {
            "target_file_path": "wf/guid.py",
            "summary": "Update print statement",
            "rationale": "Change the printed greeting message",
            "operations": [
                {
                    "type": "replace_block",
                    "start_line_guid": guids[1],
                    "new_content": ["    print('new')"],
                    "rationale": "Replace print line",
                }
            ],
        }
        prop = create_proposal_from_developer_output(payload, 1, "wf/guid.py")
        assert prop["status"] == "success"
        _approve(prop["proposal_id"])
        result = apply_edit_proposal(prop["proposal_id"])
        assert result["status"] == "success"
        assert "print('new')" in _content("wf/guid.py")


class TestDiffWorkflow:
    def test_proposal_approve_apply(self, temp_db):
        from file_editing.editing import apply_edit_proposal
        from file_editing.writer import initialize_file_lines
        from workflow.proposal_builder import create_proposal_from_developer_output

        initialize_file_lines(
            "wf/diff.py",
            "def hello():\n    print('old')\n    return True\n",
        )
        diff = "--- a/wf/diff.py\n+++ b/wf/diff.py\n@@ -1,3 +1,3 @@\n def hello():\n-    print('old')\n+    print('new')\n     return True\n"
        payload = {
            "target_file_path": "wf/diff.py",
            "summary": "Update print via diff",
            "rationale": "Apply planned unified diff to print statement",
            "operations": [
                {
                    "type": "apply_diff",
                    "diff": diff,
                    "rationale": "Apply unified diff",
                }
            ],
        }
        prop = create_proposal_from_developer_output(
            payload,
            1,
            "wf/diff.py",
            selected_mode="diff",
            final_mode="diff",
        )
        assert prop["status"] == "success"
        _approve(prop["proposal_id"])
        result = apply_edit_proposal(prop["proposal_id"])
        assert result["status"] == "success"
        assert "print('new')" in _content("wf/diff.py")


# ---------------------------------------------------------------------------
# Mode selection / validation workflows
# ---------------------------------------------------------------------------


class TestModeSelectionWorkflow:
    def test_tshirt_and_fallback_chain(self):
        from workflow.edit_mode_selector import MODE_FIND_REPLACE, MODE_FULL_REPLACE, MODE_GUID, next_fallback_mode, select_edit_mode

        small = select_edit_mode(40, "rewrite the helper")
        assert small.selected_mode == MODE_FULL_REPLACE

        rename = select_edit_mode(300, "rename foo to bar in this file")
        assert rename.selected_mode == MODE_FIND_REPLACE

        large = select_edit_mode(800, "refactor architecture across modules")
        assert large.selected_mode == MODE_GUID

        # Walk full fallback chain from guid
        mode = MODE_GUID
        tried = []
        while mode:
            tried.append(mode)
            mode = next_fallback_mode(mode, already_tried=tried)
        assert tried == ["guid", "diff", "find_replace", "full_replace"]


class TestValidationWorkflow:
    def test_empty_ops_and_recovery_signal(self):
        from core.edit_response_validator import EditFailureReason, validate_developer_edit_response
        from workflow.edit_mode_selector import next_fallback_mode

        bad = validate_developer_edit_response('{"target_file_path":"a.py","summary":"x","operations":[],"rationale":"enough text here"}')
        assert not bad.is_valid
        assert bad.reason == EditFailureReason.EMPTY_OPERATIONS

        # After GUID failure, next mode should be diff
        nxt = next_fallback_mode("guid", already_tried=["guid"])
        assert nxt == "diff"

        good = validate_developer_edit_response('{"target_file_path":"a.py","find":"old","replace":"new"}')
        assert good.is_valid
        assert good.detected_mode == "find_replace"


# ---------------------------------------------------------------------------
# Scripted multi-agent workflows (MockLLM)
# ---------------------------------------------------------------------------


class TestMockedAgentWorkflow:
    def test_orchestrator_developer_reviewer_sequence(self, mock_llm):
        """Script a short multi-agent turn sequence without network."""
        mock_llm.set_responses(
            "orchestrator",
            [
                json.dumps(
                    {
                        "next_agent": "developer",
                        "instructions": "Rename old_name to new_name in wf/x.py",
                        "files_needed": ["wf/x.py"],
                        "reasoning": "Highest priority backlog item",
                    }
                ),
                json.dumps(
                    {
                        "next_agent": "complete",
                        "instructions": "Done",
                        "reasoning": "All feedback addressed",
                    }
                ),
            ],
        )
        mock_llm.set_responses(
            "developer",
            [
                "FILES_NEEDED: wf/x.py\nPLAN: rename old_name to new_name",
                json.dumps(
                    {
                        "target_file_path": "wf/x.py",
                        "summary": "Rename identifier",
                        "rationale": "Consistent naming across the module",
                        "operations": [
                            {
                                "type": "find_replace",
                                "find": "old_name",
                                "replace": "new_name",
                                "rationale": "Rename identifier",
                            }
                        ],
                    }
                ),
            ],
        )
        mock_llm.set_response(
            "reviewer",
            json.dumps({"decision": "APPROVE", "reason": "Looks correct", "suggestions": []}),
        )

        with mock_llm.patch_call_agent():
            from agents.base import call_agent

            orch1 = json.loads(call_agent("orchestrator", "start task", task_id="wf1"))
            assert orch1["next_agent"] == "developer"

            plan = call_agent("developer", orch1["instructions"], task_id="wf1")
            assert "FILES_NEEDED" in plan or "old_name" in plan

            edit = call_agent("developer", "emit json", task_id="wf1")
            edit_data = json.loads(edit)
            assert edit_data["operations"][0]["type"] == "find_replace"

            review = json.loads(call_agent("reviewer", edit, task_id="wf1"))
            assert review["decision"] == "APPROVE"

            orch2 = json.loads(call_agent("orchestrator", "continue", task_id="wf1"))
            assert orch2["next_agent"] == "complete"

        assert len(mock_llm.calls_for("orchestrator")) == 2
        assert len(mock_llm.calls_for("developer")) == 2
        assert len(mock_llm.calls_for("reviewer")) == 1

    def test_developer_invalid_then_valid_fallback(self, mock_llm):
        """Simulate GUID failure response then a valid find_replace response."""
        from core.edit_response_validator import validate_developer_edit_response
        from workflow.edit_mode_selector import next_fallback_mode

        mock_llm.set_responses(
            "developer",
            [
                "Sorry I cannot produce JSON right now.",
                json.dumps(
                    {
                        "target_file_path": "a.py",
                        "find": "old",
                        "replace": "new",
                    }
                ),
            ],
        )

        with mock_llm.patch_call_agent():
            from agents.base import call_agent

            mode = "guid"
            tried = []
            final = None
            for _ in range(4):
                raw = call_agent("developer", f"edit using {mode}", task_id="fb1")
                validation = validate_developer_edit_response(raw)
                if validation.is_valid:
                    final = validation
                    break
                tried.append(mode)
                mode = next_fallback_mode(mode, already_tried=tried)
                if not mode:
                    break

        assert final is not None
        assert final.detected_mode == "find_replace"
        assert "guid" in tried  # first attempt failed

    def test_mocked_developer_output_creates_proposal(self, temp_db, mock_llm):
        """End-to-end: mocked developer JSON → proposal → apply."""
        from file_editing.editing import apply_edit_proposal
        from file_editing.writer import initialize_file_lines
        from workflow.proposal_builder import create_proposal_from_developer_output

        initialize_file_lines("wf/mock.py", "value = OLD\n")
        mock_llm.set_response(
            "developer",
            json.dumps(
                {
                    "target_file_path": "wf/mock.py",
                    "summary": "Replace OLD with NEW",
                    "rationale": "Update constant value for the new release",
                    "operations": [
                        {
                            "type": "find_replace",
                            "find": "OLD",
                            "replace": "NEW",
                            "rationale": "Replace constant",
                        }
                    ],
                }
            ),
        )

        with mock_llm.patch_call_agent():
            from agents.base import call_agent

            raw = call_agent("developer", "replace OLD", task_id="wf_mock")

        prop = create_proposal_from_developer_output(
            raw,
            1,
            "wf/mock.py",
            selected_mode="find_replace",
            final_mode="find_replace",
        )
        assert prop["status"] == "success"
        _approve(prop["proposal_id"])
        result = apply_edit_proposal(prop["proposal_id"])
        assert result["status"] == "success"
        assert "NEW" in _content("wf/mock.py")
