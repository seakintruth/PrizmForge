"""Prioritizer phase-1 quality filter (no live worker thread)."""

from __future__ import annotations

from agents.prioritizer_worker import FeedbackItem, PrioritizerWorker


def _item(raw_id: int, message: str, category: str = "bug", suggestion: str | None = None) -> FeedbackItem:
    return FeedbackItem(
        id=str(raw_id),
        from_agent="jr_reviewer",
        file_path="app.py",
        priority="MEDIUM",
        category=category,
        message=message,
        suggestion=suggestion or "",
        timestamp="2026-01-01T00:00:00",
        raw_id=raw_id,
        item_type="feedback",
    )


def test_filter_dismisses_placeholder_and_short_messages(temp_db):
    worker = PrioritizerWorker()
    # Seed DB rows that match raw_id so UPDATE can mark addressed
    from core.db_connection import get_db_connection

    with get_db_connection() as conn:
        for i, msg in enumerate(["todo", "bug", "x", "Real substantive issue about null checks"], start=1):
            conn.execute(
                """
                INSERT INTO agent_feedback
                (id, agent_name, file_path, priority, category, message, task_id, addressed, timestamp)
                VALUES (?, 'jr_reviewer', 'app.py', 'MEDIUM', 'bug', ?, 't_q', 0, datetime('now'))
                """,
                (i, msg),
            )

    items = [
        _item(1, "todo"),
        _item(2, "bug"),  # too short / generic
        _item(3, "x"),  # < 15 chars
        _item(4, "Real substantive issue about null checks"),
        _item(5, "bug", category="bug"),  # repeats category — but message is generic pattern first
    ]

    valid, dismissed = worker._filter_low_quality_feedback(items)
    assert dismissed >= 3
    assert any("null checks" in v.message for v in valid)

    with get_db_connection() as conn:
        rows = conn.execute("SELECT id, addressed, addressed_by FROM agent_feedback WHERE task_id = 't_q' ORDER BY id").fetchall()
    dismissed_ids = {r[0] for r in rows if r[1] == 1}
    assert 1 in dismissed_ids or 2 in dismissed_ids or 3 in dismissed_ids
    # Substantive item should remain unaddressed if it was in DB
    row4 = [r for r in rows if r[0] == 4]
    if row4:
        assert row4[0][1] == 0


def test_filter_dismisses_category_echo(temp_db):
    worker = PrioritizerWorker()
    from core.db_connection import get_db_connection

    with get_db_connection() as conn:
        conn.execute("""
            INSERT INTO agent_feedback
            (id, agent_name, file_path, priority, category, message, task_id, addressed, timestamp)
            VALUES (10, 'jr_reviewer', 'a.py', 'LOW', 'style', 'style', 't_echo', 0, datetime('now'))
            """)

    valid, dismissed = worker._filter_low_quality_feedback([_item(10, "style", category="style")])
    assert dismissed == 1
    assert valid == []

    with get_db_connection() as conn:
        row = conn.execute("SELECT addressed_by FROM agent_feedback WHERE id = 10").fetchone()
    assert row and row[0] == "prioritizer_quality_filter"
