"""The honest gate: `init_db` must never stamp a schema it does not verify.

| On disk                                   | Action                             |
|-------------------------------------------|------------------------------------|
| no file                                   | create -> DDL -> verify -> version  |
| current version, verify passes            | open only (no unlink/DDL/rewrite)   |
| current version, verify fails             | refuse to start, do not stamp       |
| version mismatch (incl. 0)                | unlink + rebuild -> verify -> stamp |
| unlink fails                              | raise, never apply in place         |
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from core import db as db_mod


def _current_db(db_path: Path) -> None:
    """Build a brand-new canonical DB at ``db_path`` (env must already point there)."""
    db_mod.init_db()


def _stamp(db_path: Path, version: int) -> None:
    conn = sqlite3.connect(str(db_path))
    conn.execute(f"PRAGMA user_version = {version};")
    conn.commit()
    conn.close()


def _read_version(db_path: Path) -> int:
    conn = sqlite3.connect(str(db_path))
    try:
        return int(conn.execute("PRAGMA user_version;").fetchone()[0])
    finally:
        conn.close()


def _cols(db_path: Path, table: str) -> set[str]:
    conn = sqlite3.connect(str(db_path))
    try:
        return {row[1] for row in conn.execute(f"PRAGMA table_info({table});").fetchall()}
    finally:
        conn.close()


def _insert_message(db_path: Path, task_id: str, content: str) -> None:
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO messages (task_id, from_agent, content) VALUES (?, ?, ?)",
        (task_id, "a", content),
    )
    conn.commit()
    conn.close()


def _message_count(db_path: Path) -> int:
    conn = sqlite3.connect(str(db_path))
    try:
        return int(conn.execute("SELECT COUNT(*) FROM messages;").fetchone()[0])
    finally:
        conn.close()


def test_no_file_becomes_current_schema(_isolate_prizmforge_workspace):
    """A fresh file gets canonical DDL + version, and only then is stamped."""
    db_path = Path(_isolate_prizmforge_workspace["db_path"])
    assert not db_path.exists()

    _current_db(db_path)

    assert _read_version(db_path) == db_mod.SCHEMA_VERSION
    names = _table_names(db_path)
    assert set(db_mod.REQUIRED_TABLES) <= names
    assert {"verdict", "contract_hash", "verdict_note"} <= _cols(db_path, "rollouts")
    assert {"tokens_per_minute", "tokens_remaining_minute", "tokens_reset_epoch"} <= _cols(db_path, "endpoint_health")
    assert {"step_number", "response_format_status", "command", "command_exit_code"} <= _cols(db_path, "agent_responses_archive")


def test_current_db_is_opened_not_rebuilt(_isolate_prizmforge_workspace):
    """Second init on an honest current DB leaves inode, rows, and version alone."""
    db_path = Path(_isolate_prizmforge_workspace["db_path"])
    _current_db(db_path)
    _insert_message(db_path, "t1", "keep me")
    inode_before = db_path.stat().st_ino
    version_before = _read_version(db_path)

    _current_db(db_path)

    assert db_path.stat().st_ino == inode_before
    assert _message_count(db_path) == 1
    assert _read_version(db_path) == version_before


def test_current_version_but_broken_shape_refuses_to_start(_isolate_prizmforge_workspace):
    """user_version matches but a required table is gone -> raise, no stamp."""
    db_path = Path(_isolate_prizmforge_workspace["db_path"])
    _current_db(db_path)

    conn = sqlite3.connect(str(db_path))
    conn.execute("DROP TABLE rollouts;")
    conn.commit()
    conn.close()

    with pytest.raises(RuntimeError, match="claims user_version"):
        _current_db(db_path)

    assert db_path.exists()
    assert _read_version(db_path) == db_mod.SCHEMA_VERSION


def test_stale_version_is_replaced_and_rebuilt(_isolate_prizmforge_workspace):
    """Version mismatch discards the file: legacy rows gone, new schema stamped."""
    db_path = Path(_isolate_prizmforge_workspace["db_path"])
    _current_db(db_path)
    _insert_message(db_path, "stale", "should vanish")
    _stamp(db_path, db_mod.SCHEMA_VERSION - 1)

    _current_db(db_path)

    assert _read_version(db_path) == db_mod.SCHEMA_VERSION
    assert _message_count(db_path) == 0
    assert "verdict" in _cols(db_path, "rollouts")


def test_unlink_failure_raises_and_never_stamps(_isolate_prizmforge_workspace, monkeypatch):
    """If the stale DB cannot be discarded, init must raise and version stays put."""
    db_path = Path(_isolate_prizmforge_workspace["db_path"])
    _current_db(db_path)
    _stamp(db_path, db_mod.SCHEMA_VERSION - 1)

    def _fail_unlink(self, missing_ok: bool = False):
        raise OSError("injected unlink failure")

    monkeypatch.setattr(Path, "unlink", _fail_unlink)

    with pytest.raises(RuntimeError, match="refusing to lie about schema"):
        _current_db(db_path)

    assert db_path.exists()
    assert _read_version(db_path) == db_mod.SCHEMA_VERSION - 1


def _table_names(db_path: Path) -> set[str]:
    conn = sqlite3.connect(str(db_path))
    try:
        return {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()}
    finally:
        conn.close()
