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
