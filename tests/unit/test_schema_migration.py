"""Additive schema migration for databases created before column additions."""

from __future__ import annotations

import sqlite3
from pathlib import Path


def _create_legacy_edit_proposals_db(path: Path) -> None:
    """Minimal pre-migration shape: edit_proposals without task_id / mode cols."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    conn = sqlite3.connect(str(path))
    conn.executescript(
        """
        CREATE TABLE edit_proposals (
            proposal_id TEXT PRIMARY KEY,
            target_file_id INTEGER,
            edit_payload TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        INSERT INTO edit_proposals (proposal_id, target_file_id, edit_payload, status)
        VALUES ('legacy-prop-1', 1, '{"ops":[]}', 'pending');
        """
    )
    conn.commit()
    conn.close()


def test_migrate_adds_task_id_and_mode_columns(temp_db, monkeypatch):
    """init_db / _migrate_schema must ALTER existing edit_proposals tables."""
    from core import db as db_mod

    db_path = Path(temp_db)
    # Replace with legacy shape after temp_db already initialized
    _create_legacy_edit_proposals_db(db_path)

    cols_before = {
        row[1]
        for row in sqlite3.connect(str(db_path)).execute("PRAGMA table_info(edit_proposals)").fetchall()
    }
    assert "task_id" not in cols_before
    assert "selected_mode" not in cols_before
    assert "fallback_used" not in cols_before
    assert "final_mode" not in cols_before

    # Re-run init which applies _migrate_schema
    monkeypatch.setenv("PRIZMFORGE_DB_PATH", str(db_path))
    db_mod.init_db()

    conn = sqlite3.connect(str(db_path))
    cols_after = {row[1] for row in conn.execute("PRAGMA table_info(edit_proposals)").fetchall()}
    for required in ("task_id", "selected_mode", "fallback_used", "final_mode", "target_file_path"):
        assert required in cols_after, f"missing migrated column: {required}"

    # Legacy row still readable
    row = conn.execute(
        "SELECT proposal_id, task_id, status FROM edit_proposals WHERE proposal_id = ?",
        ("legacy-prop-1",),
    ).fetchone()
    assert row is not None
    assert row[0] == "legacy-prop-1"
    assert row[2] == "pending"
    # Newly added nullable column defaults to NULL for old rows
    assert row[1] is None
    conn.close()


def test_ensure_column_is_idempotent(temp_db):
    """Second migration pass must not raise."""
    from core.db import _migrate_schema, get_db_path

    conn = sqlite3.connect(get_db_path())
    _migrate_schema(conn)
    _migrate_schema(conn)
    conn.commit()
    cols = {row[1] for row in conn.execute("PRAGMA table_info(edit_proposals)").fetchall()}
    assert "task_id" in cols
    conn.close()
