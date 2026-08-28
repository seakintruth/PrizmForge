import json
import sqlite3
from typing import Any
from uuid import uuid4

from core.events import publish_event
from file_editing.db import get_db_connection, log_error
from file_editing.edit_payload import EditPayload

# =============================================================================
# PrizmForge/workflow/proposal_builder.py
# Version: 1.9
# Purpose: Bridge between Developer agent output and governed edit proposals
#          Fully aligned with current edit_proposals schema (includes task_id)
# =============================================================================


def _get_or_create_file_id(conn: sqlite3.Connection, target_file_path: str) -> int:
    """Get existing file_id or create a new file record."""
    cursor = conn.execute(
        "SELECT file_id FROM files WHERE file_path = ? AND is_deleted = 0",
        (target_file_path,),
    )
    row = cursor.fetchone()
    if row:
        return row[0]

    cursor = conn.execute(
        """INSERT INTO files (file_path, current_version, is_deleted, has_been_written_to_disk)
           VALUES (?, 1, 0, 0)""",
        (target_file_path,),
    )
    return cursor.lastrowid


def _get_affected_guids_from_operation(op) -> list[str]:
    """
    Extract line GUIDs that should be validated for optimistic concurrency.
    """
    if op.type == "replace_block":
        guids = [op.start_line_guid]
        if getattr(op, "end_line_guid", None):
            guids.append(op.end_line_guid)
        return guids

    elif op.type == "delete_lines":
        guids = [op.start_line_guid]
        if getattr(op, "end_line_guid", None):
            guids.append(op.end_line_guid)
        return guids

    elif op.type == "insert_after":
        after_guid = getattr(op, "after_guid", None)
        return [after_guid] if after_guid else []

    return []


def _capture_hashes_for_operations(conn: sqlite3.Connection, file_id: int, payload: EditPayload) -> tuple[list[str], dict]:
    """Capture current hashes for optimistic concurrency validation.

    All affected line GUIDs are fetched in a single ``IN (...)`` lookup rather
    than issuing one SELECT per GUID (PR-83 residual P3).
    """
    affected_guids: list[str] = []
    for op in payload.operations:
        affected_guids.extend(_get_affected_guids_from_operation(op))

    unique_guids = list(set(affected_guids))
    expected_hashes: dict = {}
    if unique_guids:
        placeholders = ",".join("?" for _ in unique_guids)
        rows = conn.execute(
            f"SELECT line_guid, content_hash FROM file_lines WHERE line_guid IN ({placeholders}) AND is_deleted = 0",
            unique_guids,
        ).fetchall()
        expected_hashes = {row[0]: row[1] for row in rows}

    return unique_guids, expected_hashes


def create_proposal_from_developer_output(
    developer_output: str | dict,
    proposed_by_agent_id: int,
    target_file_path: str,
    rationale: str | None = None,
    selected_mode: str | None = None,
    fallback_used: bool = False,
    final_mode: str | None = None,
    task_id: str | None = None,
) -> dict[str, Any]:
    """Creates a governed edit proposal from Developer output."""
    try:
        if isinstance(developer_output, str):
            payload = EditPayload.model_validate_json(developer_output)
        else:
            payload = EditPayload.model_validate(developer_output)

        with get_db_connection() as conn:
            file_id = _get_or_create_file_id(conn, target_file_path)
            affected_guids, expected_hashes = _capture_hashes_for_operations(conn, file_id, payload)

            proposal_id = str(uuid4())

            # Embed mode info in rationale prefix for auditability even without columns
            base_rationale = rationale or payload.rationale or ""
            mode_tag = ""
            if selected_mode or final_mode:
                mode_tag = f"[mode={final_mode or selected_mode}"
                if fallback_used:
                    mode_tag += f" fallback_from={selected_mode}"
                mode_tag += "] "
            full_rationale = mode_tag + base_rationale

            conn.execute(
                """
                INSERT INTO edit_proposals (
                    proposal_id,
                    target_file_id,
                    target_file_path,
                    edit_payload,
                    affected_line_guids,
                    expected_hashes,
                    status,
                    proposed_by_agent_id,
                    rationale,
                    created_at,
                    reviewed_at,
                    write_started_at,
                    write_completed_at,
                    write_start_line_guid,
                    write_end_line_guid,
                    selected_mode,
                    fallback_used,
                    final_mode,
                    task_id
                ) VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?, datetime('now'), NULL, NULL, NULL, NULL, NULL, ?, ?, ?, ?)
            """,
                (
                    proposal_id,
                    file_id,
                    target_file_path,
                    payload.model_dump_json(),
                    json.dumps(affected_guids),
                    json.dumps(expected_hashes),
                    proposed_by_agent_id,
                    full_rationale,
                    selected_mode,
                    1 if fallback_used else 0,
                    final_mode or selected_mode,
                    task_id,
                ),
            )

            result = {
                "status": "success",
                "proposal_id": proposal_id,
                "target_file_path": target_file_path,
                "affected_line_guids": affected_guids,
                "selected_mode": selected_mode,
                "fallback_used": fallback_used,
                "final_mode": final_mode or selected_mode,
                "task_id": task_id,
                "message": "Proposal created and ready for review",
            }

        # After commit: audit log + event (never inside the write transaction)
        log_error(
            "proposal_builder",
            "create_proposal",
            "INFO",
            f"Proposal created: {proposal_id} for {target_file_path}",
            proposal_id=proposal_id,
        )
        publish_event(
            "proposal.created",
            source="proposal_builder",
            task_id=task_id,
            proposal_id=result["proposal_id"],
            payload={
                "target_file_path": result["target_file_path"],
                "selected_mode": result.get("selected_mode"),
                "fallback_used": result.get("fallback_used"),
                "task_id": task_id,
            },
        )
        return result

    except Exception as e:
        log_error("proposal_builder", "create_proposal", "HIGH", str(e))
        return {"status": "error", "message": f"Failed to create proposal: {e!s}"}


def update_proposal_status(proposal_id: str, new_status: str, reviewed_by_agent_id: int | None = None) -> bool:
    """Update proposal status and set reviewed_at when a reviewer acts."""
    allowed_statuses = {
        "pending",
        "under_review",
        "approved",
        "rejected",
        "applied",
        "needs_revalidation",
    }
    if new_status not in allowed_statuses:
        return False

    try:
        with get_db_connection() as conn:
            if reviewed_by_agent_id:
                conn.execute(
                    """
                    UPDATE edit_proposals
                    SET status = ?,
                        reviewed_by_agent_id = ?,
                        reviewed_at = datetime('now')
                    WHERE proposal_id = ?
                """,
                    (new_status, reviewed_by_agent_id, proposal_id),
                )
            else:
                conn.execute(
                    "UPDATE edit_proposals SET status = ? WHERE proposal_id = ?",
                    (new_status, proposal_id),
                )
        return True
    except Exception as e:
        log_error("proposal_builder", "update_status", "HIGH", str(e), proposal_id=proposal_id)
        return False
