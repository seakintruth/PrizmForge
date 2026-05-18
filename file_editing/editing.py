# =============================================================================
# PrizmForge/file_editing/editing.py
# Version: 1.6 - Range-based editing + Detailed operation results
# Purpose: Core editing engine with optimistic validation, safe range operations,
#          and detailed feedback on lines affected.
# =============================================================================

import sqlite3
from typing import Dict, Any, List, Optional
from uuid import uuid4
import hashlib
import json

from .db import get_db_connection, log_error


# =============================================================================
# Configuration
# =============================================================================
INITIAL_GAP = 1024.0
MIN_GAP_THRESHOLD = 0.001
RENUMBER_GAP = 1024.0


def _compute_hash(content: str) -> str:
    return hashlib.md5(content.encode()).hexdigest()


def _validate_guid_exists(conn: sqlite3.Connection, file_id: int, line_guid: str) -> bool:
    if not line_guid:
        return False
    row = conn.execute(
        "SELECT 1 FROM file_lines WHERE line_guid = ? AND file_id = ? AND is_deleted = 0",
        (line_guid, file_id)
    ).fetchone()
    return row is not None


def _validate_operation_guids(conn: sqlite3.Connection, file_id: int, op) -> bool:
    """
    Validate that referenced line GUIDs exist for the given operation.
    Supports replace_block, delete_lines, and insert_after.
    """
    if op.type == "replace_block":
        if not _validate_guid_exists(conn, file_id, op.start_line_guid):
            return False
        if getattr(op, 'end_line_guid', None) and not _validate_guid_exists(conn, file_id, op.end_line_guid):
            return False
        return True

    elif op.type == "delete_lines":
        if not _validate_guid_exists(conn, file_id, op.start_line_guid):
            return False
        if getattr(op, 'end_line_guid', None) and not _validate_guid_exists(conn, file_id, op.end_line_guid):
            return False
        return True

    elif op.type == "insert_after":
        # after_guid can be None (for new/empty files)
        after_guid = getattr(op, 'after_guid', None)
        if after_guid is None:
            return True
        return _validate_guid_exists(conn, file_id, after_guid)

    # Unknown operation type — be conservative
    return False


def get_insert_sort_order(
    conn: sqlite3.Connection, 
    file_id: int, 
    after_guid: Optional[str] = None
) -> float:
    try:
        if after_guid is None:
            min_row = conn.execute(
                "SELECT MIN(sort_order) FROM file_lines WHERE file_id = ? AND is_deleted = 0",
                (file_id,)
            ).fetchone()
            if min_row and min_row[0] is not None:
                return min_row[0] - (INITIAL_GAP / 2)
            return INITIAL_GAP / 2

        row = conn.execute(
            "SELECT sort_order FROM file_lines WHERE line_guid = ? AND is_deleted = 0",
            (after_guid,)
        ).fetchone()
        if row:
            current = row[0]
            next_row = conn.execute(
                """SELECT sort_order FROM file_lines 
                   WHERE file_id = ? AND sort_order > ? AND is_deleted = 0
                   ORDER BY sort_order LIMIT 1""",
                (file_id, current)
            ).fetchone()

            if next_row and next_row[0] is not None:
                gap = next_row[0] - current
                if gap < MIN_GAP_THRESHOLD:
                    renumber_sort_orders(conn, file_id)
                    return get_insert_sort_order(conn, file_id, after_guid)
                return current + (gap / 2)
            return current + INITIAL_GAP

        max_row = conn.execute(
            "SELECT MAX(sort_order) FROM file_lines WHERE file_id = ? AND is_deleted = 0",
            (file_id,)
        ).fetchone()
        return (max_row[0] or 0.0) + INITIAL_GAP

    except Exception as e:
        log_error("file_editing", "get_insert_sort_order", "HIGH", str(e), file_id=file_id)
        raise


def renumber_sort_orders(conn: sqlite3.Connection, file_id: int) -> None:
    try:
        cursor = conn.execute("""
            SELECT line_guid FROM file_lines 
            WHERE file_id = ? AND is_deleted = 0 
            ORDER BY sort_order
        """, (file_id,))
        line_guids = [row[0] for row in cursor.fetchall()]

        for i, line_guid in enumerate(line_guids):
            new_sort = (i + 1) * RENUMBER_GAP
            conn.execute(
                "UPDATE file_lines SET sort_order = ? WHERE line_guid = ?",
                (new_sort, line_guid)
            )

        log_error(
            "file_editing", "renumber_sort_orders", "INFO",
            f"Renumbered {len(line_guids)} lines", file_id=file_id
        )
    except Exception as e:
        log_error("file_editing", "renumber_sort_orders", "HIGH", str(e), file_id=file_id)
        raise


def validate_proposal(conn, proposal: dict) -> bool:
    if not proposal.get("expected_hashes"):
        return True
    try:
        expected = json.loads(proposal["expected_hashes"])
        affected = json.loads(proposal.get("affected_line_guids", "[]"))
        for guid in affected:
            row = conn.execute(
                "SELECT content_hash FROM file_lines WHERE line_guid = ? AND is_deleted = 0",
                (guid,)
            ).fetchone()
            if not row or row[0] != expected.get(guid):
                log_error("file_editing", "validation", "HIGH",
                          f"Hash mismatch on line {guid}", proposal_id=proposal.get("proposal_id"))
                return False
        return True
    except Exception as e:
        log_error("file_editing", "validation", "HIGH", str(e), proposal_id=proposal.get("proposal_id"))
        return False


# =============================================================================
# Core Apply Functions with Detailed Return Values
# =============================================================================

def apply_replace_block(conn: sqlite3.Connection, file_id: int, op) -> Dict[str, Any]:
    """
    Replace a range of lines.
    Returns detailed information about the operation.
    """
    start_guid = op.start_line_guid
    end_guid = getattr(op, 'end_line_guid', None)
    new_content = getattr(op, 'new_content', [])

    # Get sort orders
    start_row = conn.execute(
        "SELECT sort_order FROM file_lines WHERE line_guid = ? AND file_id = ? AND is_deleted = 0",
        (start_guid, file_id)
    ).fetchone()

    if not start_row:
        return {"status": "error", "message": f"Start GUID not found: {start_guid}"}

    start_sort = start_row[0]
    end_sort = start_sort

    if end_guid:
        end_row = conn.execute(
            "SELECT sort_order FROM file_lines WHERE line_guid = ? AND file_id = ? AND is_deleted = 0",
            (end_guid, file_id)
        ).fetchone()
        if end_row:
            end_sort = end_row[0]

    # Count lines that will be deleted
    count_row = conn.execute("""
        SELECT COUNT(*) FROM file_lines 
        WHERE file_id = ? 
          AND sort_order >= ? 
          AND sort_order <= ?
          AND is_deleted = 0
    """, (file_id, start_sort, end_sort)).fetchone()
    lines_deleted = count_row[0] if count_row else 0

    # Soft delete the range
    conn.execute("""
        UPDATE file_lines 
        SET is_deleted = 1 
        WHERE file_id = ? 
          AND sort_order >= ? 
          AND sort_order <= ?
          AND is_deleted = 0
    """, (file_id, start_sort, end_sort))

    # Insert new lines
    for i, line in enumerate(new_content):
        new_guid = str(uuid4())
        conn.execute("""
            INSERT INTO file_lines 
                (line_guid, file_id, sort_order, content, content_hash, version, is_deleted)
            VALUES (?, ?, ?, ?, ?, 1, 0)
        """, (new_guid, file_id, start_sort + (i * 0.5), line, _compute_hash(line)))

    return {
        "status": "success",
        "lines_deleted": lines_deleted,
        "lines_inserted": len(new_content)
    }


def apply_insert_after(conn: sqlite3.Connection, file_id: int, op) -> Dict[str, Any]:
    """Insert new lines after a specific GUID."""
    after_guid = getattr(op, 'after_guid', None)
    new_contents = getattr(op, 'new_content', [])

    if not new_contents:
        return {"status": "success", "lines_inserted": 0}

    current_after = after_guid
    for content in new_contents:
        new_sort = get_insert_sort_order(conn, file_id, current_after)
        new_guid = str(uuid4())
        conn.execute("""
            INSERT INTO file_lines 
                (line_guid, file_id, sort_order, content, content_hash, version, is_deleted)
            VALUES (?, ?, ?, ?, ?, 1, 0)
        """, (new_guid, file_id, new_sort, content, _compute_hash(content)))
        current_after = new_guid

    return {
        "status": "success",
        "lines_inserted": len(new_contents)
    }


def apply_delete_lines(conn: sqlite3.Connection, file_id: int, op) -> Dict[str, Any]:
    """
    Delete a range of lines using start_line_guid and optional end_line_guid.
    """
    start_guid = op.start_line_guid
    end_guid = getattr(op, 'end_line_guid', None)

    start_row = conn.execute(
        "SELECT sort_order FROM file_lines WHERE line_guid = ? AND file_id = ? AND is_deleted = 0",
        (start_guid, file_id)
    ).fetchone()

    if not start_row:
        return {"status": "error", "message": f"Start GUID not found: {start_guid}"}

    start_sort = start_row[0]
    end_sort = start_sort

    if end_guid:
        end_row = conn.execute(
            "SELECT sort_order FROM file_lines WHERE line_guid = ? AND file_id = ? AND is_deleted = 0",
            (end_guid, file_id)
        ).fetchone()
        if end_row:
            end_sort = end_row[0]

    # Count lines in range
    count_row = conn.execute("""
        SELECT COUNT(*) FROM file_lines 
        WHERE file_id = ? 
          AND sort_order >= ? 
          AND sort_order <= ?
          AND is_deleted = 0
    """, (file_id, start_sort, end_sort)).fetchone()
    lines_deleted = count_row[0] if count_row else 0

    # Soft delete the range
    conn.execute("""
        UPDATE file_lines 
        SET is_deleted = 1 
        WHERE file_id = ? 
          AND sort_order >= ? 
          AND sort_order <= ?
          AND is_deleted = 0
    """, (file_id, start_sort, end_sort))

    return {
        "status": "success",
        "lines_deleted": lines_deleted
    }


def apply_update_documentation(conn: sqlite3.Connection, file_id: int, op):
    new_content = getattr(op, 'new_content', '')
    conn.execute("""
        INSERT INTO file_documentation (file_id, content, version, updated_at)
        VALUES (?, ?, 1, datetime('now'))
        ON CONFLICT(file_id) DO UPDATE SET 
            content = excluded.content,
            version = file_documentation.version + 1,
            updated_at = datetime('now')
    """, (file_id, new_content))


def apply_edit_proposal(proposal_id: str) -> Dict[str, Any]:
    with get_db_connection() as conn:
        proposal_row = conn.execute(
            "SELECT * FROM edit_proposals WHERE proposal_id = ?", (proposal_id,)
        ).fetchone()

        if not proposal_row or proposal_row["status"] != "approved":
            return {"status": "error", "message": "Proposal not approved"}

        if not validate_proposal(conn, dict(proposal_row)):
            log_error("file_editing", "apply", "HIGH", "Optimistic validation failed", 
                      proposal_id=proposal_id)
            return {"status": "conflicted"}

        try:
            from .edit_payload import EditPayload
            payload = EditPayload.model_validate_json(proposal_row["edit_payload"])
            file_id = proposal_row["target_file_id"]

            # Strict GUID validation
            for op in payload.operations:
                if not _validate_operation_guids(conn, file_id, op):
                    log_error("file_editing", "apply", "HIGH",
                              f"Referenced line GUID not found in operation: {op.type}",
                              proposal_id=proposal_id)
                    return {"status": "conflicted", "message": "Referenced line GUID not found"}

            operation_results = []

            for op in payload.operations:
                if op.type == "replace_block":
                    result = apply_replace_block(conn, file_id, op)
                    operation_results.append(result)
                elif op.type == "insert_after":
                    result = apply_insert_after(conn, file_id, op)
                    operation_results.append(result)
                elif op.type == "delete_lines":
                    result = apply_delete_lines(conn, file_id, op)
                    operation_results.append(result)
                elif op.type == "update_documentation":
                    apply_update_documentation(conn, file_id, op)
                elif op.type == "create_file":
                    pass

            conn.execute(
                "UPDATE edit_proposals SET status = 'applied' WHERE proposal_id = ?",
                (proposal_id,)
            )

            return {
                "status": "success",
                "proposal_id": proposal_id,
                "operations": operation_results
            }

        except Exception as e:
            log_error("file_editing", "apply", "HIGH", str(e), proposal_id=proposal_id)
            return {"status": "error", "message": str(e)}