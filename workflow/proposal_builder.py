# =============================================================================
# PrizmForge/workflow/proposal_builder.py
# Version: 1.7
# Purpose: Bridge between Developer agent output and governed edit proposals
#          Fully aligned with current edit_proposals schema
# =============================================================================

import json
import sqlite3
from typing import Any, Dict, Optional, List
from uuid import uuid4
from datetime import datetime

from file_editing.edit_payload import EditPayload
from file_editing.db import get_db_connection, log_error


def _get_or_create_file_id(conn: sqlite3.Connection, target_file_path: str) -> int:
    """Get existing file_id or create a new file record."""
    cursor = conn.execute(
        "SELECT file_id FROM files WHERE file_path = ? AND is_deleted = 0",
        (target_file_path,)
    )
    row = cursor.fetchone()
    if row:
        return row[0]

    cursor = conn.execute(
        """INSERT INTO files (file_path, current_version, is_deleted, has_been_written_to_disk)
           VALUES (?, 1, 0, 0)""",
        (target_file_path,)
    )
    return cursor.lastrowid


def _get_affected_guids_from_operation(op) -> List[str]:
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


def _capture_hashes_for_operations(
    conn: sqlite3.Connection,
    file_id: int,
    payload: EditPayload
) -> tuple[list[str], dict]:
    """Capture current hashes for optimistic concurrency validation."""
    affected_guids: list[str] = []
    expected_hashes: dict = {}

    for op in payload.operations:
        guids = _get_affected_guids_from_operation(op)
        if guids:
            affected_guids.extend(guids)
            for guid in guids:
                row = conn.execute(
                    "SELECT content_hash FROM file_lines WHERE line_guid = ? AND is_deleted = 0",
                    (guid,)
                ).fetchone()
                if row:
                    expected_hashes[guid] = row[0]

    return list(set(affected_guids)), expected_hashes


def create_proposal_from_developer_output(
    developer_output: str | dict,
    proposed_by_agent_id: int,
    target_file_path: str,
    rationale: Optional[str] = None
) -> Dict[str, Any]:
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

            conn.execute("""
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
                    write_end_line_guid
                ) VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?, datetime('now'), NULL, NULL, NULL, NULL, NULL)
            """, (
                proposal_id,
                file_id,
                target_file_path,
                payload.model_dump_json(),
                json.dumps(affected_guids),
                json.dumps(expected_hashes),
                proposed_by_agent_id,
                rationale or payload.rationale
            ))

            log_error(
                "proposal_builder", "create_proposal", "INFO",
                f"Proposal created: {proposal_id} for {target_file_path}",
                proposal_id=proposal_id
            )

            return {
                "status": "success",
                "proposal_id": proposal_id,
                "target_file_path": target_file_path,
                "affected_line_guids": affected_guids,
                "message": "Proposal created and ready for review"
            }

    except Exception as e:
        log_error("proposal_builder", "create_proposal", "HIGH", str(e))
        return {
            "status": "error",
            "message": f"Failed to create proposal: {str(e)}"
        }


def update_proposal_status(
    proposal_id: str,
    new_status: str,
    reviewed_by_agent_id: Optional[int] = None
) -> bool:
    """Update proposal status and set reviewed_at when a reviewer acts."""
    allowed_statuses = {"pending", "under_review", "approved", "rejected", "applied", "needs_revalidation"}
    if new_status not in allowed_statuses:
        return False

    try:
        with get_db_connection() as conn:
            if reviewed_by_agent_id:
                conn.execute("""
                    UPDATE edit_proposals 
                    SET status = ?, 
                        reviewed_by_agent_id = ?, 
                        reviewed_at = datetime('now')
                    WHERE proposal_id = ?
                """, (new_status, reviewed_by_agent_id, proposal_id))
            else:
                conn.execute(
                    "UPDATE edit_proposals SET status = ? WHERE proposal_id = ?",
                    (new_status, proposal_id)
                )
        return True
    except Exception as e:
        log_error("proposal_builder", "update_status", "HIGH", str(e), proposal_id=proposal_id)
        return False