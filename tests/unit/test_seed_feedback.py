"""Seed task must be injected as agent_feedback so the loop has work from turn 1."""

from workflow.task_runner import _inject_seed_feedback


def test_inject_seed_feedback_creates_row(temp_db):
    _inject_seed_feedback("task_001", "Review the repository's plans and todos")
    from core.db_connection import get_db_connection

    with get_db_connection() as conn:
        row = conn.execute("""
            SELECT agent_name, priority, category, message, addressed
            FROM agent_feedback WHERE task_id = 'task_001'
            """).fetchone()

    assert row is not None
    agent_name, priority, category, message, addressed = row
    assert agent_name == "system"
    assert priority == "HIGH"
    assert category == "seed_task"
    assert "plans" in message
    assert addressed == 0


def test_inject_seed_feedback_is_idempotent(temp_db):
    _inject_seed_feedback("task_001", "Do the thing")
    _inject_seed_feedback("task_001", "Do the thing")  # second call must not duplicate

    from core.db_connection import get_db_connection

    with get_db_connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM agent_feedback WHERE task_id = 'task_001' AND category = 'seed_task'").fetchone()[0]

    assert count == 1


def test_inject_seed_feedback_ignores_empty_command(temp_db):
    _inject_seed_feedback("task_empty", "   ")
    from core.db_connection import get_db_connection

    with get_db_connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM agent_feedback WHERE task_id = 'task_empty'").fetchone()[0]

    assert count == 0


def test_backlog_overrides_exclude_seed_task(temp_db):
    """Regression test for feedback #317: seed_task items must not be counted
    as backlog entries or be picked as the top feedback item.

    The seed task is the original user command; it is addressed by the
    developer turn itself. Counting it in the backlog and dispatching the
    developer against it (file_path=NULL) would prevent real HIGH-priority
    bug items from ever being processed.
    """
    from core.db_connection import get_db_connection
    from workflow.backlog import count_unaddressed_feedback, fetch_top_feedback

    task_id = "backlog_seed_test"
    with get_db_connection() as conn:
        # seed_task item (no file_path) - the focus of feedback #317
        conn.execute(
            """
            INSERT INTO agent_feedback
            (agent_name, file_path, priority, category, message, suggestion, task_id, addressed, timestamp)
            VALUES ('system', NULL, 'HIGH', 'seed_task', 'Address 37 HIGH bug issues', NULL, ?, 0, ?)
            """,
            (task_id, "2024-01-01T00:00:00+00:00"),
        )
        # Real HIGH bug with a file
        conn.execute(
            """
            INSERT INTO agent_feedback
            (agent_name, file_path, priority, category, message, suggestion, task_id, addressed, timestamp)
            VALUES ('reviewer', 'core/foo.py', 'HIGH', 'bug', 'Null pointer in handler', NULL, ?, 0, ?)
            """,
            (task_id, "2024-01-01T00:00:01+00:00"),
        )

    with get_db_connection() as conn:
        # Only the real bug should be counted, NOT the seed_task
        assert count_unaddressed_feedback(conn, task_id) == 1
        # The top item should be the real bug, not the seed_task
        top = fetch_top_feedback(conn, task_id)
        assert top is not None
        _fb_id, _priority, category, file_path, _message, _suggestion = top
        assert category == "bug"
        assert file_path == "core/foo.py"
