"""
Backlog override helpers for unattended runs.

Extracted so production rules can be unit-tested without a full task cycle.
"""

from __future__ import annotations

from typing import Any


def count_unaddressed_feedback(conn, task_id: str) -> int:
    row = conn.execute(
        """
        SELECT COUNT(*) FROM agent_feedback
        WHERE task_id = ? AND addressed = 0
        """,
        (task_id,),
    ).fetchone()
    return int(row[0] if row else 0)


def fetch_top_feedback(conn, task_id: str) -> tuple | None:
    return conn.execute(
        """
        SELECT id, priority, category, file_path, message, suggestion
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
        LIMIT 1
        """,
        (task_id,),
    ).fetchone()


def apply_backlog_overrides(
    task_id: str,
    decision: dict[str, Any] | None,
    conn,
    *,
    force_threshold: int = 50,
) -> dict[str, Any] | None:
    """
    Apply unattended backlog routing rules.

    - If unaddressed count > force_threshold: force developer on top feedback item.
    - Else if count > 0 and decision next_agent == background: redirect to developer.

    Returns the (possibly new) decision dict.
    """
    total = count_unaddressed_feedback(conn, task_id)

    if total > force_threshold:
        top = fetch_top_feedback(conn, task_id)
        if not top:
            return decision
        fb_id, priority, category, file_path, message, suggestion = top
        return {
            "next_agent": "developer",
            "instructions": (
                f"**BACKLOG MODE: {total} unaddressed items**\n\n"
                f"**FIX THIS SPECIFIC ITEM:**\n\n"
                f"Feedback ID: {fb_id}\n"
                f"Priority: {priority}\n"
                f"Category: {category}\n"
                f"File: {file_path}\n\n"
                f"Issue: {message}\n\n" + (f"Suggested fix: {suggestion}\n\n" if suggestion else "") + f"**CRITICAL:**\n"
                f"- Skip analysis phase\n"
                f"- FILES_NEEDED: {file_path}\n"
                f"- Prefer a simple, reliable edit (find_replace or full_replace for small files)\n"
                f"- Reference feedback #{fb_id} in your rationale\n"
            ),
            "reasoning": f"BACKLOG OVERRIDE: {total} items, processing #{fb_id}",
            "files_needed": [file_path] if file_path else [],
            "addressing_feedback_ids": [fb_id],
            "feedback_summary": (f"Backlog: {total} items. Processing highest priority: #{fb_id} [{priority}] {category}"),
            "model": (decision or {}).get("model"),
        }

    if total > 0 and decision and decision.get("next_agent") == "background":
        top = fetch_top_feedback(conn, task_id)
        if not top:
            return decision
        fb_id, priority, category, file_path, message, suggestion = top
        out = dict(decision)
        out["next_agent"] = "developer"
        out["instructions"] = f"Address feedback #{fb_id}: [{priority}] {category} in {file_path}\n\nIssue: {message}\n\n"
        if suggestion:
            out["instructions"] += f"Suggested fix: {suggestion}"
        out["files_needed"] = [file_path] if file_path else []
        out["addressing_feedback_ids"] = [fb_id]
        out["reasoning"] = f"OVERRIDE: {total} items in backlog"
        return out

    return decision
