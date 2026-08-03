"""
Proposal undo / version restore (Phase D2).

Stores a content snapshot when a proposal is approved (before materialize)
via the events/write log path, and can restore by proposal_id.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict
from core.db_connection import get_db_connection
from core.events import publish_event
from file_editing.db import reconstruct_file_content
from file_editing.writer import initialize_file_lines, write_file_to_disk


def ensure_snapshot_table(conn) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS proposal_snapshots (
            proposal_id TEXT PRIMARY KEY,
            file_path TEXT NOT NULL,
            content_before TEXT,
            created_at TEXT
        )
        """)


def snapshot_before_apply(proposal_id: str) -> Dict[str, Any]:
    """Capture current file content for an approved proposal before materialize."""
    with get_db_connection() as conn:
        ensure_snapshot_table(conn)
        row = conn.execute(
            "SELECT target_file_path, target_file_id FROM edit_proposals WHERE proposal_id = ?",
            (proposal_id,),
        ).fetchone()
        if not row:
            return {"status": "error", "message": "proposal not found"}
        path, file_id = row[0], row[1]
        content = reconstruct_file_content(conn, file_id) if file_id else ""
        conn.execute(
            """
            INSERT OR REPLACE INTO proposal_snapshots (proposal_id, file_path, content_before, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (proposal_id, path, content, datetime.now(timezone.utc).isoformat()),
        )
        return {"status": "success", "file_path": path, "bytes": len(content or "")}


def undo_proposal(proposal_id: str, *, write_disk: bool = True) -> Dict[str, Any]:
    """
    Restore content from snapshot taken before apply.
    Explicit proposal_id required (no silent global revert).
    """
    with get_db_connection() as conn:
        ensure_snapshot_table(conn)
        snap = conn.execute(
            "SELECT file_path, content_before FROM proposal_snapshots WHERE proposal_id = ?",
            (proposal_id,),
        ).fetchone()
        if not snap:
            return {
                "status": "error",
                "message": f"no snapshot for proposal {proposal_id}",
            }
        path, content = snap[0], snap[1] if snap[1] is not None else ""

    init = initialize_file_lines(path, content)
    if init.get("status") != "success":
        return {"status": "error", "message": f"restore init failed: {init}"}

    disk = {"status": "skipped"}
    if write_disk:
        disk = write_file_to_disk(path, content, proposal_id=proposal_id)

    with get_db_connection() as conn:
        conn.execute(
            "UPDATE edit_proposals SET status = 'undone' WHERE proposal_id = ?",
            (proposal_id,),
        )

    publish_event(
        "edit.undone",
        source="undo",
        proposal_id=proposal_id,
        payload={"file_path": path, "disk": disk.get("status")},
    )
    return {
        "status": "success",
        "proposal_id": proposal_id,
        "file_path": path,
        "disk": disk,
    }
