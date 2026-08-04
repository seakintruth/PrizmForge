from typing import List, Optional

"""Database helper functions"""

from datetime import datetime
from typing import Dict

from core.db_connection import get_db_connection


def get_db_path() -> str:
    """Get database path"""
    from core.db import get_db_path as _get_db_path

    return _get_db_path()


def post_message(
    from_agent: str,
    to_agent: str,
    content: str,
    task_id: str = "global",
    priority: str = "MEDIUM",
):
    """Post message to message bus"""
    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO messages (timestamp, from_agent, to_agent, content, task_id, priority, read)
            VALUES (?, ?, ?, ?, ?, ?, 0)
        """,
            (
                datetime.now().isoformat(),
                from_agent,
                to_agent,
                content,
                task_id,
                priority,
            ),
        )


def get_unread_messages(agent: str, task_id: Optional[str] = None, min_priority: str = "LOW") -> List[Dict]:
    """Get unread messages for agent"""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        if task_id:
            cursor.execute(
                """
                SELECT id, from_agent, content, timestamp, priority
                FROM messages
                WHERE to_agent = ? AND task_id = ? AND read = 0
                ORDER BY
                    CASE priority
                        WHEN 'CRITICAL' THEN 1
                        WHEN 'HIGH' THEN 2
                        WHEN 'MEDIUM' THEN 3
                        ELSE 4
                    END,
                    timestamp
            """,
                (agent, task_id),
            )
        else:
            cursor.execute(
                """
                SELECT id, from_agent, content, timestamp, priority
                FROM messages
                WHERE to_agent = ? AND read = 0
                ORDER BY
                    CASE priority
                        WHEN 'CRITICAL' THEN 1
                        WHEN 'HIGH' THEN 2
                        WHEN 'MEDIUM' THEN 3
                        ELSE 4
                    END,
                    timestamp
            """,
                (agent,),
            )

        messages = []
        for row in cursor.fetchall():
            messages.append(
                {
                    "id": row[0],
                    "from": row[1],
                    "content": row[2],
                    "timestamp": row[3],
                    "priority": row[4],
                }
            )
    return messages


def mark_messages_read(message_ids: List[int]):
    """Mark messages as read"""
    if not message_ids:
        return
    with get_db_connection() as conn:
        placeholders = ",".join("?" * len(message_ids))
        conn.execute(f"UPDATE messages SET read = 1 WHERE id IN ({placeholders})", message_ids)


def save_conversation(
    task_id: str,
    agent: str,
    role: str,
    content: str,
    raw_response: Optional[str] = None,
    parsed_decision: Optional[str] = None,
):
    """Save conversation to history"""
    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO conversation_history
            (task_id, agent, role, content, raw_response, parsed_decision, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                task_id,
                agent,
                role,
                content,
                raw_response or content,
                parsed_decision,
                datetime.now().isoformat(),
            ),
        )


def create_task(task_id: str, description: str):
    """Create new task"""
    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO tasks (id, description, status, started_at)
            VALUES (?, ?, 'in_progress', ?)
        """,
            (task_id, description, datetime.now().isoformat()),
        )


def complete_task(task_id: str, result: str):
    """Mark task as complete"""
    with get_db_connection() as conn:
        conn.execute(
            """
            UPDATE tasks SET status = 'completed', completed_at = ?, result = ?
            WHERE id = ?
        """,
            (datetime.now().isoformat(), result, task_id),
        )


def save_agent_feedback(
    agent_name: str,
    file_path: str,
    priority: str,
    category: str,
    message: str,
    suggestion: Optional[str],
    task_id: str,
    file_event_id: str,
):
    """Save feedback from background agent"""
    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO agent_feedback
            (agent_name, file_path, priority, category, message, suggestion,
            task_id, file_event_id, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                agent_name,
                file_path,
                priority,
                category,
                message,
                suggestion,
                task_id,
                file_event_id,
                datetime.now().isoformat(),
            ),
        )


def get_unaddressed_feedback(task_id: str, min_priority: str = "LOW") -> List[Dict]:
    """Get unaddressed feedback for task"""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id, agent_name, file_path, priority, category, message, suggestion, timestamp
            FROM agent_feedback
            WHERE task_id = ? AND addressed = 0
            ORDER BY
                CASE priority
                    WHEN 'CRITICAL' THEN 1
                    WHEN 'HIGH' THEN 2
                    WHEN 'MEDIUM' THEN 3
                    ELSE 4
                END,
                timestamp
        """,
            (task_id,),
        )

        feedback = []
        for row in cursor.fetchall():
            feedback.append(
                {
                    "id": row[0],
                    "agent": row[1],
                    "file_path": row[2],
                    "priority": row[3],
                    "category": row[4],
                    "message": row[5],
                    "suggestion": row[6],
                    "timestamp": row[7],
                }
            )

    return feedback


def mark_feedback_addressed(feedback_ids: List[int], addressed_by: str):
    """Mark feedback as addressed"""
    if not feedback_ids:
        return
    with get_db_connection() as conn:
        placeholders = ",".join("?" * len(feedback_ids))
        conn.execute(
            f"UPDATE agent_feedback SET addressed = 1, addressed_by = ?, addressed_at = ? WHERE id IN ({placeholders})",
            [addressed_by, datetime.now().isoformat()] + feedback_ids,
        )


def age_feedback_backlog(
    max_age_days_low: int = 7,
    max_unaddressed: int = 200,
) -> dict:
    """
    Dismiss aged LOW-priority feedback and optionally trim the oldest
    MEDIUM items when the backlog exceeds max_unaddressed.

    CRITICAL and HIGH items are never auto-dismissed.
    Returns counts of rows affected.
    """
    from datetime import timedelta

    dismissed_low = 0
    trimmed_medium = 0
    now = datetime.now()
    cutoff = (now - timedelta(days=max_age_days_low)).isoformat()

    with get_db_connection() as conn:
        # Age out old LOW items
        cur = conn.execute(
            """
            UPDATE agent_feedback
            SET addressed = 1,
                addressed_by = 'system_aging',
                addressed_at = ?
            WHERE addressed = 0
              AND UPPER(priority) = 'LOW'
              AND timestamp IS NOT NULL
              AND timestamp < ?
            """,
            (now.isoformat(), cutoff),
        )
        dismissed_low = cur.rowcount if cur.rowcount is not None else 0

        # Cap total unaddressed by dismissing oldest MEDIUM items only
        row = conn.execute("SELECT COUNT(*) FROM agent_feedback WHERE addressed = 0").fetchone()
        total = row[0] if row else 0
        if total > max_unaddressed:
            excess = total - max_unaddressed
            # Select oldest MEDIUM ids
            ids = [
                r[0]
                for r in conn.execute(
                    """
                    SELECT id FROM agent_feedback
                    WHERE addressed = 0 AND UPPER(priority) = 'MEDIUM'
                    ORDER BY timestamp ASC
                    LIMIT ?
                    """,
                    (excess,),
                ).fetchall()
            ]
            if ids:
                placeholders = ",".join("?" * len(ids))
                conn.execute(
                    f"""
                    UPDATE agent_feedback
                    SET addressed = 1,
                        addressed_by = 'system_backlog_cap',
                        addressed_at = ?
                    WHERE id IN ({placeholders})
                    """,
                    [now.isoformat()] + ids,
                )
                trimmed_medium = len(ids)

    return {
        "dismissed_low": dismissed_low,
        "trimmed_medium": trimmed_medium,
    }
