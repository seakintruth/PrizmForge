"""
Proposal undo / version restore (Phase D2).

Stores a content snapshot when a proposal is approved (before materialize)
via the events/write log path, and can restore by proposal_id. Snapshots now
cover EVERY file a proposal touches (multi-file §13.2): one row per
(proposal_id, file_path), so undo restores each affected path — files that
did not exist before the apply (`content_before` NULL) are soft-deleted from
the governed store and unlinked from disk instead of being recreated empty.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.db_connection import get_db_connection
from core.events import publish_event
from file_editing.db import reconstruct_file_content
from file_editing.writer import _delete_file_from_disk, initialize_file_lines, write_file_to_disk

_SNAPSHOT_SQL = """
    CREATE TABLE IF NOT EXISTS proposal_snapshots (
        proposal_id TEXT NOT NULL,
        file_path TEXT NOT NULL,
        content_before TEXT,
        created_at TEXT,
        PRIMARY KEY (proposal_id, file_path)
    )
"""


def ensure_snapshot_table(conn) -> None:
    table = conn.execute("SELECT name, sql FROM sqlite_master WHERE type = 'table' AND name = 'proposal_snapshots'").fetchone()
    if table is None:
        conn.execute(_SNAPSHOT_SQL)
        return
    sql = (table[1] or "").replace("\n", " ")
    if "PRIMARY KEY (proposal_id, file_path)" not in sql:
        # Pre-§13.2 single-row-per-proposal shape: rebuild. Snapshots are
        # ephemeral restore metadata; losing a stale-format table is acceptable.
        print("[MEDIUM] file_editing.undo: rebuilt proposal_snapshots (old single-file schema)")
        conn.execute("DROP TABLE proposal_snapshots")
        conn.execute(_SNAPSHOT_SQL)


def snapshot_before_apply(proposal_id: str) -> dict[str, Any]:
    """Capture per-file content for every path an approved proposal touches."""
    from file_editing.writer import _proposal_affected_paths

    with get_db_connection() as conn:
        ensure_snapshot_table(conn)
        row = conn.execute(
            "SELECT * FROM edit_proposals WHERE proposal_id = ?",
            (proposal_id,),
        ).fetchone()
        if not row:
            return {"status": "error", "message": "proposal not found"}
        row = dict(row) if hasattr(row, "keys") else dict(zip([c[1] for c in conn.execute("PRAGMA table_info(edit_proposals)")], row, strict=False))
        paths = _proposal_affected_paths(row)
        if not paths:
            return {"status": "error", "message": "proposal touches no files"}
        for path in sorted(paths):
            rec = conn.execute("SELECT file_id FROM files WHERE file_path = ?", (path,)).fetchone()
            # content_before NULL == the file did not exist before this apply.
            content = reconstruct_file_content(conn, rec[0]) if rec else None
            conn.execute(
                """
                INSERT OR REPLACE INTO proposal_snapshots (proposal_id, file_path, content_before, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (proposal_id, path, content, datetime.now(timezone.utc).isoformat()),
            )
        return {"status": "success", "file_paths": sorted(paths), "files": len(paths)}


def _soft_delete_governed(file_path: str) -> None:
    """Soft-delete the governed files/file_lines rows for a path."""
    with get_db_connection() as conn:
        rec = conn.execute("SELECT file_id FROM files WHERE file_path = ?", (file_path,)).fetchone()
        if not rec:
            return
        conn.execute("UPDATE files SET is_deleted = 1 WHERE file_id = ?", (rec[0],))
        conn.execute("UPDATE file_lines SET is_deleted = 1 WHERE file_id = ?", (rec[0],))


def _project_dir() -> Path:
    from core.config import get_config

    return Path(get_config().get("project_directory", "./project")).resolve()


def undo_proposal(proposal_id: str, *, write_disk: bool = True) -> dict[str, Any]:
    """
    Restore every snapshot path for a proposal from its pre-apply content.

    Explicit proposal_id required (no silent global revert). A path whose
    snapshot content is NULL did not exist before the proposal: its governed
    rows are soft-deleted and the disk file (if writable) is unlinked, instead
    of being recreated empty.
    """
    with get_db_connection() as conn:
        ensure_snapshot_table(conn)
        snaps = conn.execute(
            "SELECT file_path, content_before FROM proposal_snapshots WHERE proposal_id = ?",
            (proposal_id,),
        ).fetchall()
    if not snaps:
        return {
            "status": "error",
            "message": f"no snapshot for proposal {proposal_id}",
        }

    restored: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for file_path, content_before in snaps:
        existed = content_before is not None
        content = content_before if existed else ""
        if existed:
            init = initialize_file_lines(file_path, content)
            if init.get("status") != "success":
                failures.append({"file_path": file_path, "message": f"restore init failed: {init}"})
                continue
            disk = {"status": "skipped"}
            if write_disk:
                disk = write_file_to_disk(file_path, content, proposal_id=proposal_id)
        else:
            _soft_delete_governed(file_path)
            disk = {"status": "skipped"}
            if write_disk:
                disk = _delete_file_from_disk(file_path, _project_dir())
        if write_disk and disk.get("status") != "success":
            failures.append({"file_path": file_path, "message": disk.get("message", "disk restore failed")})
            continue
        restored.append({"file_path": file_path, "disk": disk.get("status"), "existed": existed})

    if failures:
        return {
            "status": "error",
            "proposal_id": proposal_id,
            "message": "partial restore",
            "restored": restored,
            "failures": failures,
        }

    with get_db_connection() as conn:
        conn.execute(
            "UPDATE edit_proposals SET status = 'undone' WHERE proposal_id = ?",
            (proposal_id,),
        )

    publish_event(
        "edit.undone",
        source="undo",
        proposal_id=proposal_id,
        payload={"file_paths": [r["file_path"] for r in restored], "files": len(restored)},
    )
    return {
        "status": "success",
        "proposal_id": proposal_id,
        "file_path": restored[0]["file_path"] if restored else None,
        "file_paths": [r["file_path"] for r in restored],
        "files": restored,
    }
