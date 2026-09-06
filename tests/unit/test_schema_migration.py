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
    conn.executescript("""
        CREATE TABLE edit_proposals (
            proposal_id TEXT PRIMARY KEY,
            target_file_id INTEGER,
            edit_payload TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        INSERT INTO edit_proposals (proposal_id, target_file_id, edit_payload, status)
        VALUES ('legacy-prop-1', 1, '{"ops":[]}', 'pending');
        """)
    conn.commit()
    conn.close()


def test_migrate_adds_task_id_and_mode_columns(temp_db, monkeypatch):
    """init_db / _migrate_schema must ALTER existing edit_proposals tables."""
    from core import db as db_mod

    db_path = Path(temp_db)
    # Replace with legacy shape after temp_db already initialized
    _create_legacy_edit_proposals_db(db_path)

    cols_before = {row[1] for row in sqlite3.connect(str(db_path)).execute("PRAGMA table_info(edit_proposals)").fetchall()}
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


def test_migrate_adds_token_log_endpoint_name(temp_db, monkeypatch):
    """§8.1a: existing token_log tables gain endpoint_name."""
    import sqlite3

    from core import db as db_mod

    db_path = Path(temp_db)
    conn = sqlite3.connect(str(db_path))
    conn.execute("DROP TABLE IF EXISTS token_log")
    conn.execute("CREATE TABLE token_log (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, tokens_used INTEGER)")
    conn.execute("INSERT INTO token_log (timestamp, tokens_used) VALUES ('2026-01-01T00:00:00', 12)")
    conn.commit()
    conn.close()

    monkeypatch.setenv("PRIZMFORGE_DB_PATH", str(db_path))
    db_mod.init_db()

    conn = sqlite3.connect(str(db_path))
    cols = {row[1] for row in conn.execute("PRAGMA table_info(token_log)").fetchall()}
    assert "endpoint_name" in cols
    row = conn.execute("SELECT tokens_used, endpoint_name FROM token_log").fetchone()
    assert row[0] == 12
    assert row[1] is None
    conn.close()


def test_migrate_adds_model_health_retry_after_s(temp_db, monkeypatch):
    """§5: existing model_health_events tables gain retry_after_s."""
    from core import db as db_mod

    db_path = Path(temp_db)
    conn = sqlite3.connect(str(db_path))
    conn.execute("DROP TABLE IF EXISTS model_health_events")
    conn.execute("""
        CREATE TABLE model_health_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            model_ref TEXT NOT NULL,
            endpoint TEXT,
            ok INTEGER NOT NULL,
            latency_ms INTEGER DEFAULT 0,
            kind TEXT
        )
        """)
    conn.execute(
        "INSERT INTO model_health_events (ts, model_ref, endpoint, ok, latency_ms, kind) VALUES ('2026-01-01T00:00:00', 'ep/m', 'ep', 0, 0, 'rate_limited')"
    )
    conn.commit()
    conn.close()

    monkeypatch.setenv("PRIZMFORGE_DB_PATH", str(db_path))
    db_mod.init_db()

    conn = sqlite3.connect(str(db_path))
    cols = {row[1] for row in conn.execute("PRAGMA table_info(model_health_events)").fetchall()}
    assert "retry_after_s" in cols
    row = conn.execute("SELECT kind, retry_after_s FROM model_health_events").fetchone()
    assert row[0] == "rate_limited"
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
