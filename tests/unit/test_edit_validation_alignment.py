"""Workstream D (Phase 2): edit-payload / developer-phase validation alignment.

Accomplishes the plan's "one schema, two gates": the developer validator now
enforces the same per-operation required fields as proposal_builder's
EditPayload, so a payload can never be declared valid at the developer phase
and then fail proposal creation. Acceptance criteria (UNATTENDED §6.4):
  - op type ``guid`` is invalid,
  - ``find_replace`` without ``find`` is invalid,
  - invalid ops never create a proposal row.
"""

from __future__ import annotations

import pytest

from core.edit_response_validator import EditFailureReason, validate_developer_edit_response


class TestRejectGuidType:
    @pytest.mark.parametrize(
        "payload",
        [
            {"target_file_path": "a.py", "summary": "claim", "rationale": "claim line guid", "operations": [{"type": "guid", "start_line_guid": "g1"}]},
            {"type": "guid", "start_line_guid": "g1", "rationale": "claim line guid"},
        ],
    )
    def test_guid_type_is_invalid(self, payload):
        r = validate_developer_edit_response(__import__("json").dumps(payload))
        assert r.is_valid is False
        assert r.reason == EditFailureReason.INVALID_OPERATION

    @pytest.mark.parametrize(
        "op_type",
        ["guid", "find", "delete", "apply", "full file replace"],
    )
    def test_unknown_type_names_invalid(self, op_type):
        payload = {
            "target_file_path": "a.py",
            "summary": "rename",
            "rationale": "consistent naming",
            "operations": [{"type": op_type, "rationale": "some change"}],
        }
        r = validate_developer_edit_response(__import__("json").dumps(payload))
        assert r.is_valid is False
        assert r.reason == EditFailureReason.INVALID_OPERATION


class TestRequireFindReplaceFields:
    @pytest.mark.parametrize(
        "op",
        [
            {"type": "find_replace"},
            {"type": "find_replace", "replace": "NEW"},
            {"type": "find_replace", "find": "", "replace": "NEW"},
            {"type": "find_replace", "find": "OLD"},
            {"type": "find_replace", "find": "OLD", "replace": 42},
        ],
    )
    def test_find_replace_missing_fields_invalid(self, op):
        payload = {"target_file_path": "a.py", "summary": "rename", "rationale": "rename consistently", "operations": [op]}
        r = validate_developer_edit_response(__import__("json").dumps(payload))
        assert r.is_valid is False
        assert r.reason == EditFailureReason.INVALID_OPERATION

    def test_find_replace_with_both_fields_valid(self):
        payload = {
            "target_file_path": "a.py",
            "summary": "rename constant",
            "rationale": "consistent naming",
            "operations": [{"type": "find_replace", "find": "OLD", "replace": "NEW"}],
        }
        r = validate_developer_edit_response(__import__("json").dumps(payload))
        assert r.is_valid is True

    def test_replace_block_requires_anchor_guid(self):
        payload = {
            "target_file_path": "a.py",
            "summary": "swap block",
            "rationale": "swap block implementation",
            "operations": [{"type": "replace_block", "new_content": ["x = 1"]}],
        }
        r = validate_developer_edit_response(__import__("json").dumps(payload))
        assert r.is_valid is False
        assert r.reason == EditFailureReason.INVALID_OPERATION


class TestSchemaParityWithEditPayload:
    """A payload valid at the developer gate must survive proposal creation."""

    def test_full_replace_op_accepts_list_content(self):
        payload = {
            "target_file_path": "a.py",
            "summary": "rewrite file",
            "rationale": "rewrite the whole module",
            "operations": [{"type": "full_replace", "new_content": ["x = 1", "y = 2"]}],
        }
        r = validate_developer_edit_response(__import__("json").dumps(payload))
        assert r.is_valid is True

    @pytest.mark.parametrize(
        "op",
        [
            {"type": "create_file", "target_file_path": "new.py", "initial_content": ["x = 1"]},
            {"type": "insert_after", "after_guid": "g1", "new_content": ["y = 2"]},
            {"type": "delete_lines", "start_line_guid": "g1"},
            {"type": "apply_diff", "diff": "--- a\n+++ b\n@@ -1 +1 @@\n-x\n+y\n"},
        ],
    )
    def test_valid_ops_all_accepted(self, op):
        payload = {"target_file_path": "a.py", "summary": "edit file", "rationale": "edit the target file", "operations": [op]}
        r = validate_developer_edit_response(__import__("json").dumps(payload))
        assert r.is_valid is True, r.message


class TestNoProposalForInvalidOps:
    def test_invalid_ops_create_no_proposal_row(self, temp_db):
        from file_editing.db import get_db_connection
        from workflow.proposal_builder import create_proposal_from_developer_output

        with get_db_connection() as conn:
            before = conn.execute("SELECT COUNT(*) FROM edit_proposals").fetchone()[0]

        results = [
            create_proposal_from_developer_output(
                {
                    "target_file_path": "a.py",
                    "summary": "claim line",
                    "rationale": "use the legacy guid mode name",
                    "operations": [{"type": "guid", "start_line_guid": "g1"}],
                },
                1,
                "a.py",
            ),
            create_proposal_from_developer_output(
                {
                    "target_file_path": "a.py",
                    "summary": "rename",
                    "rationale": "rename the constant for clarity",
                    "operations": [{"type": "find_replace", "replace": "NEW"}],
                },
                1,
                "a.py",
            ),
        ]

        for result in results:
            assert result["status"] == "error", result

        with get_db_connection() as conn:
            after = conn.execute("SELECT COUNT(*) FROM edit_proposals").fetchone()[0]
        assert after == before
