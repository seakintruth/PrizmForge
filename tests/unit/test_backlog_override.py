"""P1.2 — Backlog override rules for unattended runs."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _seed_feedback(conn, task_id: str, n: int, priority: str = "HIGH"):
    for i in range(n):
        conn.execute(
            """
            INSERT INTO agent_feedback
            (agent_name, file_path, priority, category, message, suggestion, task_id, addressed, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)
            """,
            (
                "jr_reviewer",
                f"mod{i}.py",
                priority if i else "CRITICAL",
                "style",
                f"issue {i}",
                f"fix {i}",
                task_id,
                datetime.now(timezone.utc).isoformat(),
            ),
        )


def test_force_override_above_threshold(temp_db):
    from core.db_connection import get_db_connection
    from workflow.backlog import apply_backlog_overrides

    task_id = "bl_force"
    with get_db_connection() as conn:
        _seed_feedback(conn, task_id, 51)
        decision = {"next_agent": "background", "instructions": "idle"}
        out = apply_backlog_overrides(task_id, decision, conn, force_threshold=50)
    assert out is not None
    assert out["next_agent"] == "developer"
    assert out["addressing_feedback_ids"]
    assert "BACKLOG OVERRIDE" in out["reasoning"]
    assert out["files_needed"]
    assert "Feedback ID" in out["instructions"]


def test_redirect_background_when_small_backlog(temp_db):
    from core.db_connection import get_db_connection
    from workflow.backlog import apply_backlog_overrides

    task_id = "bl_redir"
    with get_db_connection() as conn:
        _seed_feedback(conn, task_id, 3)
        decision = {"next_agent": "background", "instructions": "bg work", "model": None}
        out = apply_backlog_overrides(task_id, decision, conn, force_threshold=50)
    assert out["next_agent"] == "developer"
    assert "OVERRIDE:" in out["reasoning"]
    assert out["addressing_feedback_ids"]


def test_no_override_when_empty_and_developer(temp_db):
    from core.db_connection import get_db_connection
    from workflow.backlog import apply_backlog_overrides

    task_id = "bl_none"
    with get_db_connection() as conn:
        decision = {"next_agent": "developer", "instructions": "edit foo"}
        out = apply_backlog_overrides(task_id, decision, conn)
    assert out["next_agent"] == "developer"
    assert out["instructions"] == "edit foo"


def test_critical_sorted_first(temp_db):
    from core.db_connection import get_db_connection
    from workflow.backlog import apply_backlog_overrides, fetch_top_feedback

    task_id = "bl_sort"
    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO agent_feedback
            (agent_name, file_path, priority, category, message, task_id, addressed, timestamp)
            VALUES ('a', 'low.py', 'LOW', 'x', 'low', ?, 0, ?)
            """,
            (task_id, datetime.now(timezone.utc).isoformat()),
        )
        conn.execute(
            """
            INSERT INTO agent_feedback
            (agent_name, file_path, priority, category, message, task_id, addressed, timestamp)
            VALUES ('a', 'crit.py', 'CRITICAL', 'x', 'crit', ?, 0, ?)
            """,
            (task_id, datetime.now(timezone.utc).isoformat()),
        )
        top = fetch_top_feedback(conn, task_id)
        out = apply_backlog_overrides(
            task_id,
            {"next_agent": "background"},
            conn,
            force_threshold=0,  # force path with any backlog
        )
    assert top[3] == "crit.py"
    assert out["files_needed"] == ["crit.py"]
