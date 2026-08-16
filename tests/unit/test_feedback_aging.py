"""Feedback insert, aging, and backlog force-override."""

from __future__ import annotations

from datetime import datetime, timedelta


def test_save_and_fetch_feedback(temp_db):
    from core.db_helpers import get_unaddressed_feedback, save_agent_feedback

    save_agent_feedback(
        agent_name="jr_reviewer",
        file_path="app.py",
        priority="HIGH",
        category="bug",
        message="null deref risk",
        suggestion="add guard",
        task_id="t1",
        file_event_id="evt-1",
    )
    items = get_unaddressed_feedback("t1")
    assert len(items) == 1
    assert items[0]["priority"] == "HIGH"
    assert items[0]["file_path"] == "app.py"


def test_age_feedback_dismisses_old_low_only(temp_db):
    from core.db_connection import get_db_connection
    from core.db_helpers import age_feedback_backlog

    old = (datetime.now() - timedelta(days=30)).isoformat()
    recent = datetime.now().isoformat()
    with get_db_connection() as conn:
        for i, (pri, ts) in enumerate(
            [
                ("LOW", old),
                ("LOW", recent),
                ("CRITICAL", old),
                ("HIGH", old),
                ("MEDIUM", old),
            ],
            start=1,
        ):
            conn.execute(
                """
                INSERT INTO agent_feedback
                (agent_name, file_path, priority, category, message, task_id,
                 addressed, timestamp)
                VALUES ('jr_reviewer', 'f.py', ?, 'style', ?, 't_age', 0, ?)
                """,
                (pri, f"msg-{i}", ts),
            )

    result = age_feedback_backlog(max_age_days_low=7, max_unaddressed=200)
    assert result["dismissed_low"] >= 1

    with get_db_connection() as conn:
        rows = conn.execute("SELECT priority, addressed, addressed_by FROM agent_feedback WHERE task_id = 't_age'").fetchall()
        by_pri = {}
        for pri, addressed, by in rows:
            by_pri.setdefault(pri.upper(), []).append((addressed, by))

        # Old LOW dismissed by system_aging
        assert any(a == 1 and by == "system_aging" for a, by in by_pri["LOW"])
        # CRITICAL / HIGH never auto-dismissed by aging
        assert all(a == 0 for a, _ in by_pri["CRITICAL"])
        assert all(a == 0 for a, _ in by_pri["HIGH"])


def test_backlog_force_override_above_threshold(temp_db):
    from core.db_connection import get_db_connection
    from core.db_helpers import save_agent_feedback
    from workflow.backlog import apply_backlog_overrides

    for i in range(55):
        save_agent_feedback(
            agent_name="jr_reviewer",
            file_path="app.py",
            priority="MEDIUM" if i else "CRITICAL",
            category="style",
            message=f"issue {i}",
            suggestion=None,
            task_id="t_force",
            file_event_id=f"e{i}",
        )

    with get_db_connection() as conn:
        decision = apply_backlog_overrides(
            "t_force",
            {"next_agent": "background", "reasoning": "idle"},
            conn,
            force_threshold=50,
        )
    assert decision is not None
    assert decision["next_agent"] == "developer"
    assert "BACKLOG OVERRIDE" in decision.get("reasoning", "")
    assert decision.get("addressing_feedback_ids")
