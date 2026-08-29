"""Database helper functions"""

import re
from datetime import datetime, timedelta

from core.db import get_db_path as _get_db_path
from core.db_connection import get_db_connection

# Canonical review-taxonomy categories (mirrors the prioritizer prompt).
_CANONICAL_CATEGORIES = (
    "security",
    "bug",
    "performance",
    "maintainability",
    "documentation",
    "architecture",
    "style",
    "test",
    "other",
)

# Process/bookkeeping categories that pass through untouched.
_PROCESS_CATEGORIES = ("seed_task", "review_rejection", "uncategorized")

_CATEGORY_ALIASES = {
    # security
    "vulnerability": "security",
    "vulnerabilities": "security",
    "security-vulnerability": "security",
    # bug
    "defect": "bug",
    "bugfix": "bug",
    "error": "bug",
    "failure": "bug",
    "crash": "bug",
    "logic-error": "bug",
    # performance
    "perf": "performance",
    "optimization": "performance",
    "efficiency": "performance",
    "latency": "performance",
    "memory": "performance",
    # maintainability
    "maintenance": "maintainability",
    "code-smell": "maintainability",
    "code_smell": "maintainability",
    "code smell": "maintainability",
    "refactor": "maintainability",
    "refactoring": "maintainability",
    "tech-debt": "maintainability",
    "technical-debt": "maintainability",
    "complexity": "maintainability",
    "robustness": "maintainability",
    "consistency": "maintainability",
    "organization": "maintainability",
    "readability": "maintainability",
    "type-safety": "maintainability",
    "type_safety": "maintainability",
    "testability": "maintainability",
    "dead-code": "maintainability",
    "duplication": "maintainability",
    # documentation
    "docs": "documentation",
    "doc": "documentation",
    "comment": "documentation",
    "comments": "documentation",
    "completeness": "documentation",
    # architecture
    "design": "architecture",
    "structure": "architecture",
    "pattern": "architecture",
    "coupling": "architecture",
    "cohesion": "architecture",
    "modularity": "architecture",
    # style
    "formatting": "style",
    "format": "style",
    "naming": "style",
    "lint": "style",
    "polish": "style",
    # test
    "test": "test",
    "tests": "test",
    "testing": "test",
    "unittest": "test",
    "unit-test": "test",
    "regression": "test",
    "coverage": "test",
    "test-coverage": "test",
    "test_gap": "test",
    "test-quality": "test",
    "coverage-gap": "test",
}


def normalize_category(raw: str | None) -> str:
    """Map an LLM-emitted feedback category onto the canonical taxonomy.

    Reviewer models emit free-form categories ("Code Smell", "test-coverage",
    "coverage-gap" ...). Left verbatim they fragment backlog grouping, dedup and
    task-generation counts (a 12h soak produced 36 distinct values). Canonical
    targets mirror the prioritizer prompt; process categories pass through.
    """
    if not raw:
        return "other"
    key = str(raw).strip().lower().replace("-", "_").replace(" ", "_")
    if key in _PROCESS_CATEGORIES or key in _CANONICAL_CATEGORIES:
        return key
    if key in _CATEGORY_ALIASES:
        return _CATEGORY_ALIASES[key]
    # Alias keys were written with hyphens/spaces above; re-check underscore form.
    for alias, canonical in _CATEGORY_ALIASES.items():
        if alias.replace("-", "_") == key:
            return canonical
    return "other"


def get_db_path() -> str:
    """Get database path"""

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


def get_unread_messages(agent: str, task_id: str | None = None, min_priority: str = "LOW") -> list[dict]:
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


def mark_messages_read(message_ids: list[int]):
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
    raw_response: str | None = None,
    parsed_decision: str | None = None,
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


def normalize_feedback_message(message: str) -> str:
    """Collapse a feedback message to a stable dedupe key.

    Whitespace, punctuation and case are normalized so findings that differ
    only in phrasing/highlighting map to the same key (Workstream B §4.4.1).
    """
    text = " ".join(str(message).split())
    text = re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
    return re.sub(r"\s+", " ", text).strip()


def _dedupe_settings() -> tuple[bool, int]:
    # Import lazily so tests that patch core.config.get_config take effect
    # (module-bound imports would pin the original function object).
    from core.config import get_config

    cfg = (get_config() or {}).get("feedback", {}) or {}
    dedupe = cfg.get("dedupe") or {}
    return bool(dedupe.get("enabled", True)), int(dedupe.get("window_minutes", 30))


def save_agent_feedback(
    agent_name: str,
    file_path: str,
    priority: str,
    category: str,
    message: str,
    suggestion: str | None,
    task_id: str,
    file_event_id: str,
):
    """Save feedback from background agent"""
    category = normalize_category(category)
    enabled, window_minutes = _dedupe_settings()
    dup_key = normalize_feedback_message(message) if enabled else None
    with get_db_connection() as conn:
        if enabled:
            now_iso = datetime.now().isoformat()
            cutoff = (datetime.now() - timedelta(minutes=window_minutes)).isoformat()
            existing = conn.execute(
                """
                SELECT id FROM agent_feedback
                WHERE addressed = 0
                  AND task_id = ?
                  AND IFNULL(file_path, '') = IFNULL(?, '')
                  AND category = ?
                  AND dup_key = ?
                  AND timestamp >= ?
                ORDER BY timestamp DESC
                LIMIT 1
                """,
                (task_id, file_path or "", category, dup_key, cutoff),
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE agent_feedback SET dup_count = dup_count + 1, timestamp = ? WHERE id = ?",
                    (now_iso, existing[0]),
                )
                return
        conn.execute(
            """
            INSERT INTO agent_feedback
            (agent_name, file_path, priority, category, message, suggestion,
            task_id, file_event_id, timestamp, dup_key, dup_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
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
                dup_key,
            ),
        )


def get_unaddressed_feedback(task_id: str, min_priority: str = "LOW") -> list[dict]:
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


def mark_feedback_addressed(feedback_ids: list[int], addressed_by: str):
    """Mark feedback as addressed"""
    if not feedback_ids:
        return
    with get_db_connection() as conn:
        placeholders = ",".join("?" * len(feedback_ids))
        conn.execute(
            f"UPDATE agent_feedback SET addressed = 1, addressed_by = ?, addressed_at = ? WHERE id IN ({placeholders})",
            [addressed_by, datetime.now().isoformat(), *feedback_ids],
        )


def backlog_metrics(conn, *, task_id: str | None = None) -> dict:
    """Gather backlog health numbers for project reports (Workstream B §4.6).

    Keys: ``unaddressed``, ``posted_this_hour``, ``addressed_this_hour``,
    ``stuck_ids`` (unaddressed items flagged stuck after repeated targeting).
    A ``task_id`` optionally scopes the unaddressed/stuck counts.
    """
    hour_ago = (datetime.now() - timedelta(hours=1)).isoformat()
    task_filter = " AND task_id = ?" if task_id else ""
    params: tuple = (task_id,) if task_id else ()

    with conn:
        unaddressed = conn.execute(
            f"SELECT COUNT(*) FROM agent_feedback WHERE addressed = 0 AND category != 'seed_task'{task_filter}",
            params,
        ).fetchone()[0]
        posted_this_hour = conn.execute(
            "SELECT COUNT(*) FROM agent_feedback WHERE timestamp >= ?",
            (hour_ago,),
        ).fetchone()[0]
        addressed_this_hour = conn.execute(
            "SELECT COUNT(*) FROM agent_feedback WHERE addressed = 1 AND addressed_at >= ?",
            (hour_ago,),
        ).fetchone()[0]
        stuck = conn.execute(
            f"SELECT id FROM agent_feedback WHERE stuck = 1 AND addressed = 0{task_filter} ORDER BY id",
            params,
        ).fetchall()
    return {
        "unaddressed": int(unaddressed),
        "posted_this_hour": int(posted_this_hour),
        "addressed_this_hour": int(addressed_this_hour),
        "stuck_ids": [r[0] for r in stuck],
    }


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

        # Cap total unaddressed by dismissing oldest MEDIUM items only.
        # seed_task rows are excluded so seed inflation never triggers trimming.
        row = conn.execute("SELECT COUNT(*) FROM agent_feedback WHERE addressed = 0 AND category != 'seed_task'").fetchone()
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
                    [now.isoformat(), *ids],
                )
                trimmed_medium = len(ids)

    return {
        "dismissed_low": dismissed_low,
        "trimmed_medium": trimmed_medium,
    }
