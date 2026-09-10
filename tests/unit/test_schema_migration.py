"""Non-backwards-compatible database initialization.

Database initialization always builds the full canonical schema in one pass;
an existing DB from an older schema version is discarded and rebuilt, never
ALTER-migrated.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path


def _create_legacy_db(path: Path) -> None:
    """Minimal pre-canonical shape: old agent_responses_archive without shell cols."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    conn = sqlite3.connect(str(path))
    conn.executescript("""
        CREATE TABLE agent_responses_archive (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT,
            agent_name TEXT,
            prompt TEXT,
            response TEXT,
            parse_success INTEGER,
            parse_error TEXT,
            timestamp TEXT
        );
        CREATE TABLE edit_proposals (
            proposal_id TEXT PRIMARY KEY,
            target_file_id INTEGER,
            edit_payload TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE endpoint_health (
            endpoint_name TEXT PRIMARY KEY,
            status TEXT
        );
        INSERT INTO agent_responses_archive (task_id, agent_name, response)
        VALUES ('legacy-task', 'developer', 'old data');
        """)
    conn.commit()
    conn.close()


def test_fresh_db_is_current_after_init(temp_db, monkeypatch):
    """A freshly initialized DB carries the current schema version."""
    from core import db as db_mod

    conn = sqlite3.connect(temp_db)
    assert conn.execute("PRAGMA user_version;").fetchone()[0] == db_mod.SCHEMA_VERSION
    cols = {row[1] for row in conn.execute("PRAGMA table_info(agent_responses_archive)")}
    for required in ("model", "step_number", "response_format_status", "command", "command_exit_code"):
        assert required in cols, f"missing canonical column: {required}"
    cols = {row[1] for row in conn.execute("PRAGMA table_info(endpoint_health)")}
    for required in ("tokens_per_minute", "tokens_remaining_minute", "tokens_reset_epoch"):
        assert required in cols, f"missing canonical column: {required}"
    conn.close()


def test_stale_db_is_recreated_not_migrated(temp_db, monkeypatch):
    """An old-schema DB is wiped and rebuilt, so legacy data is not preserved."""
    from core import db as db_mod

    db_path = Path(temp_db)
    _create_legacy_db(db_path)

    monkeypatch.setenv("PRIZMFORGE_DB_PATH", str(db_path))
    db_mod.init_db()

    conn = sqlite3.connect(str(db_path))
    cols = {row[1] for row in conn.execute("PRAGMA table_info(agent_responses_archive)")}
    assert "model" in cols
    row = conn.execute("SELECT COUNT(*) FROM agent_responses_archive WHERE task_id = 'legacy-task'").fetchone()
    assert row[0] == 0
    assert conn.execute("PRAGMA user_version;").fetchone()[0] == db_mod.SCHEMA_VERSION
    conn.close()


def test_init_is_idempotent(temp_db, monkeypatch):
    """Re-initializing an already-current DB must not raise or wipe data."""
    from core import db as db_mod
    from core.db_connection import get_db_connection

    with get_db_connection() as conn:
        conn.execute("INSERT INTO messages (task_id, from_agent, content) VALUES ('t1', 'a', 'keep')")

    monkeypatch.setenv("PRIZMFORGE_DB_PATH", temp_db)
    db_mod.init_db()

    with get_db_connection() as conn:
        row = conn.execute("SELECT COUNT(*) FROM messages WHERE task_id = 't1' AND from_agent = 'a'").fetchone()
    assert row[0] == 1


def test_split_sql_keeps_semicolon_in_comment_and_string():
    from core.db import _apply_schema, _split_sql_statements

    sql = """
    -- note: keep ; here
    CREATE TABLE t_semi (x TEXT DEFAULT 'a;b');
    CREATE TABLE "u;semi" (y TEXT);
    /* block ; comment */
    CREATE TABLE v_semi (z INTEGER);
    """
    stmts = _split_sql_statements(sql)
    assert len(stmts) == 3
    assert "DEFAULT 'a;b'" in stmts[0]
    assert '"u;semi"' in stmts[1]

    conn = sqlite3.connect(":memory:")
    _apply_schema(conn, sql)
    names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert {"t_semi", "u;semi", "v_semi"} <= names
    conn.close()
