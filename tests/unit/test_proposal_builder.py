"""Unit coverage for workflow.proposal_builder (GUIDs, task_id, status)."""

from __future__ import annotations

from workflow.proposal_builder import (
    _get_affected_guids_from_operation,
    create_proposal_from_developer_output,
    update_proposal_status,
)


class TestGetAffectedGuids:
    def test_replace_block_guids(self):
        class MockOp:
            type = "replace_block"
            start_line_guid = "guid-123"
            end_line_guid = "guid-456"

        guids = _get_affected_guids_from_operation(MockOp())
        assert guids == ["guid-123", "guid-456"]

    def test_delete_lines_guids(self):
        class MockOp:
            type = "delete_lines"
            start_line_guid = "guid-a"
            end_line_guid = None

        guids = _get_affected_guids_from_operation(MockOp())
        assert guids == ["guid-a"]

    def test_insert_after_with_guid(self):
        class MockOp:
            type = "insert_after"
            after_guid = "guid-xyz"

        assert _get_affected_guids_from_operation(MockOp()) == ["guid-xyz"]

    def test_insert_after_without_guid(self):
        class MockOp:
            type = "insert_after"
            after_guid = None

        assert _get_affected_guids_from_operation(MockOp()) == []

    def test_find_replace_has_no_guids(self):
        class MockOp:
            type = "find_replace"

        assert _get_affected_guids_from_operation(MockOp()) == []


class TestCreateProposal:
    def test_create_find_replace_persists_task_id(self, temp_db):
        payload = {
            "target_file_path": "demo/task.py",
            "summary": "rename constant",
            "rationale": "Consistent naming for the module constant",
            "operations": [
                {
                    "type": "find_replace",
                    "find": "OLD",
                    "replace": "NEW",
                    "rationale": "Rename OLD to NEW",
                }
            ],
        }
        result = create_proposal_from_developer_output(
            developer_output=payload,
            proposed_by_agent_id=1,
            target_file_path="demo/task.py",
            selected_mode="find_replace",
            fallback_used=False,
            final_mode="find_replace",
            task_id="task-abc-1",
        )
        assert result["status"] == "success"
        assert result["proposal_id"]
        assert result["task_id"] == "task-abc-1"
        assert result["selected_mode"] == "find_replace"
        assert result["fallback_used"] is False

        from file_editing.db import get_db_connection

        with get_db_connection() as conn:
            row = conn.execute(
                "SELECT task_id, selected_mode, fallback_used, final_mode, status FROM edit_proposals WHERE proposal_id = ?",
                (result["proposal_id"],),
            ).fetchone()
            assert row is not None
            assert row[0] == "task-abc-1"
            assert row[1] == "find_replace"
            assert int(row[2]) == 0
            assert row[3] == "find_replace"
            assert row[4] == "pending"

    def test_create_with_fallback_metadata(self, temp_db):
        payload = {
            "target_file_path": "demo/fb.py",
            "summary": "fallback path",
            "rationale": "GUID failed so find_replace was used",
            "operations": [
                {
                    "type": "find_replace",
                    "find": "a",
                    "replace": "b",
                    "rationale": "simple swap",
                }
            ],
        }
        result = create_proposal_from_developer_output(
            payload,
            proposed_by_agent_id=2,
            target_file_path="demo/fb.py",
            selected_mode="guid",
            fallback_used=True,
            final_mode="find_replace",
            task_id="task-fb",
        )
        assert result["status"] == "success"
        assert result["fallback_used"] is True
        assert result["final_mode"] == "find_replace"
        assert result["selected_mode"] == "guid"

        # Mode tag is embedded in the persisted rationale for auditability
        from file_editing.db import get_db_connection

        with get_db_connection() as conn:
            row = conn.execute(
                "SELECT rationale, fallback_used, final_mode FROM edit_proposals WHERE proposal_id = ?",
                (result["proposal_id"],),
            ).fetchone()
            assert row is not None
            rationale = row[0] or ""
            assert "fallback_from=guid" in rationale
            assert "mode=find_replace" in rationale or "mode=guid" in rationale
            assert int(row[1]) == 1
            assert row[2] == "find_replace"

    def test_invalid_payload_returns_error(self, temp_db):
        result = create_proposal_from_developer_output(
            developer_output={"not": "valid"},
            proposed_by_agent_id=1,
            target_file_path="x.py",
        )
        assert result["status"] == "error"
        assert "message" in result
        assert result["message"]  # non-empty error text

    def test_update_status_approve(self, temp_db):
        payload = {
            "target_file_path": "demo/st.py",
            "summary": "status flow",
            "rationale": "Exercise update_proposal_status path",
            "operations": [
                {
                    "type": "find_replace",
                    "find": "1",
                    "replace": "2",
                    "rationale": "bump number",
                }
            ],
        }
        created = create_proposal_from_developer_output(payload, 1, "demo/st.py", task_id="t-status")
        assert created["status"] == "success"
        ok = update_proposal_status(created["proposal_id"], "approved", reviewed_by_agent_id=9)
        assert ok is True

        from file_editing.db import get_db_connection

        with get_db_connection() as conn:
            row = conn.execute(
                "SELECT status, reviewed_by_agent_id FROM edit_proposals WHERE proposal_id = ?",
                (created["proposal_id"],),
            ).fetchone()
            assert row[0] == "approved"
            assert row[1] == 9

    def test_update_status_rejects_unknown(self, temp_db):
        assert update_proposal_status("no-such", "not_a_real_status") is False

    def test_update_status_without_reviewer(self, temp_db):
        payload = {
            "target_file_path": "demo/nr.py",
            "summary": "no reviewer id",
            "rationale": "Status update without reviewed_by_agent_id",
            "operations": [
                {
                    "type": "find_replace",
                    "find": "x",
                    "replace": "y",
                    "rationale": "swap",
                }
            ],
        }
        created = create_proposal_from_developer_output(payload, 1, "demo/nr.py")
        assert created["status"] == "success"
        ok = update_proposal_status(created["proposal_id"], "under_review")
        assert ok is True

        from file_editing.db import get_db_connection

        with get_db_connection() as conn:
            row = conn.execute(
                "SELECT status FROM edit_proposals WHERE proposal_id = ?",
                (created["proposal_id"],),
            ).fetchone()
            assert row[0] == "under_review"
