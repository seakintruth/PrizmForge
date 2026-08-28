"""Archivist restore detection and message archive persistence."""

from __future__ import annotations

import json
from datetime import datetime, timedelta

from agents.archivist_worker import ArchivistWorker


def test_needs_context_restore_keywords():
    worker = ArchivistWorker()
    assert worker._needs_context_restore("What was the previous decision on auth?") is True
    assert worker._needs_context_restore("remind me what we already discussed") is True
    assert worker._needs_context_restore("show file content of app.py") is False
    assert worker._needs_context_restore("what files need review") is False
    assert worker._needs_context_restore("plain status update") is False


def test_save_message_archive_inserts_row(temp_db):
    worker = ArchivistWorker()
    worker.current_task_id = "t_arch"

    old_ts = (datetime.now() - timedelta(minutes=30)).isoformat()
    messages = [
        {
            "id": i,
            "from": "developer",
            "to": "orchestrator",
            "content": f"msg {i}",
            "timestamp": old_ts,
            "priority": "MEDIUM",
            "task_id": "t_arch",
        }
        for i in range(1, 6)
    ]
    response = json.dumps({"summary": "Five agent handoffs archived", "key_decisions": ["use find_replace"]})

    from core.db_connection import get_db_connection

    with get_db_connection() as conn:
        worker._save_message_archive("t_arch", messages, response, conn=conn)

    with get_db_connection() as conn:
        row = conn.execute("""
            SELECT task_id, summary, original_message_count, key_decisions
            FROM archived_context
            WHERE task_id = 't_arch'
            ORDER BY id DESC LIMIT 1
            """).fetchone()
    assert row is not None
    assert row[0] == "t_arch"
    assert "archived" in (row[1] or "").lower() or "handoff" in (row[1] or "").lower() or row[1]
    assert row[2] == 5
    assert "find_replace" in (row[3] or "")


def test_archive_old_messages_requires_threshold(temp_db, mock_llm):
    """Fewer than 5 read messages → no archive call."""
    worker = ArchivistWorker()
    worker.current_task_id = "t_few"
    from core.db_connection import get_db_connection

    old = (datetime.now() - timedelta(minutes=30)).isoformat()
    with get_db_connection() as conn:
        for _ in range(3):
            conn.execute(
                """
                INSERT INTO messages (from_agent, to_agent, content, task_id, priority, read, timestamp)
                VALUES ('a', 'b', 'x', 't_few', 'LOW', 1, ?)
                """,
                (old,),
            )

    mock_llm.set_response("archivist", json.dumps({"summary": "should not run", "key_decisions": []}))
    with mock_llm.patch_call_agent():
        worker._archive_old_messages()

    with get_db_connection() as conn:
        n = conn.execute("SELECT COUNT(*) FROM archived_context WHERE task_id = 't_few'").fetchone()[0]
    assert n == 0


# ---------------------------------------------------------------------------
# Soak fix: unparseable archivist output must not be archived (35/36 junk rows)
# ---------------------------------------------------------------------------


def test_save_message_archive_skips_junk_on_parse_fail(temp_db):
    """Garbage archivist output → no row written, caller is told to keep originals."""
    worker = ArchivistWorker()
    worker.current_task_id = "t_junk"
    old_ts = (datetime.now() - timedelta(minutes=30)).isoformat()
    messages = [
        {
            "id": i,
            "from": "developer",
            "to": "orchestrator",
            "content": f"msg {i}",
            "timestamp": old_ts,
            "priority": "MEDIUM",
            "task_id": "t_junk",
        }
        for i in range(1, 6)
    ]

    from core.db_connection import get_db_connection

    with get_db_connection() as conn:
        saved = worker._save_message_archive("t_junk", messages, "not-json {{{", conn=conn)
    assert saved is False

    with get_db_connection() as conn:
        n = conn.execute("SELECT COUNT(*) FROM archived_context WHERE task_id = 't_junk'").fetchone()[0]
    assert n == 0


def test_archive_old_messages_keeps_originals_when_archivist_junk(temp_db, mock_llm):
    """Message-bus path keeps real messages instead of deleting after a junk summary."""
    worker = ArchivistWorker()
    worker.current_task_id = "t_bus"
    from core.db_connection import get_db_connection

    old = (datetime.now() - timedelta(minutes=30)).isoformat()
    with get_db_connection() as conn:
        for i in range(6):
            conn.execute(
                """
                INSERT INTO messages (from_agent, to_agent, content, task_id, priority, read, timestamp)
                VALUES ('a', 'b', ?, 't_bus', 'LOW', 1, ?)
                """,
                (f"bus msg {i}", old),
            )

    mock_llm.set_response("archivist", "sounds good, archiving everything")
    with mock_llm.patch_call_agent():
        worker._archive_old_messages()

    with get_db_connection() as conn:
        n_rows = conn.execute("SELECT COUNT(*) FROM archived_context WHERE task_id = 't_bus'").fetchone()[0]
        n_msgs = conn.execute("SELECT COUNT(*) FROM messages WHERE task_id = 't_bus'").fetchone()[0]
    assert n_rows == 0
    assert n_msgs == 6
