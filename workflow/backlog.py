"""
Backlog override helpers for unattended runs.

Extracted so production rules can be unit-tested without a full task cycle.
"""

from __future__ import annotations

from typing import Any

#: Growth tiers per plan §4.3. `soft_start` begins dedupe/intake softening,
#: `hard_start` pauses most background agents (single active repair), and
#: `freeze_at` freezes nearly all feedback agents (prioritizer + developer
#: only). Overridable via config ``feedback.tiers``.
DEFAULT_BACKLOG_TIERS = {
    "soft_start": 50,
    "hard_start": 100,
    "freeze_at": 200,
}


def normalize_backlog_tiers(config: dict | None = None) -> dict:
    """Resolve effective backlog tier thresholds from config (or defaults)."""
    if config is None:
        from core.config import get_config

        config = get_config() or {}
    tiers = (config.get("feedback") or {}).get("tiers") or {}
    out = dict(DEFAULT_BACKLOG_TIERS)
    for key in DEFAULT_BACKLOG_TIERS:
        value = tiers.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            out[key] = int(value)
    return out


def resolve_backlog_tier(unaddressed: int, config: dict | None = None) -> str:
    """Map an unaddressed count to a tier name.

    ``freeze`` (> freeze_at), ``hard`` (> hard_start), ``soft``
    (>= soft_start), else ``normal``.
    """
    tiers = normalize_backlog_tiers(config)
    if unaddressed > tiers["freeze_at"]:
        return "freeze"
    if unaddressed > tiers["hard_start"]:
        return "hard"
    if unaddressed >= tiers["soft_start"]:
        return "soft"
    return "normal"


def tier_pool_policy(tier: str) -> dict[str, Any]:
    """Return the agent-pool policy for a backlog tier.

    Used by the resource controller and the background dispatch branch so the
    "does the pool start random feeder reviews?" decision is a pure function.
    """
    if tier == "freeze":
        return {
            "level": "BACKLOG_PROCESSING",
            "active_agents": ["prioritizer"],
            "background_feeders": False,
            "background_feeder_interval": 9999,
            "reasoning": "freeze: prioritizer + developer only",
        }
    if tier == "hard":
        return {
            "level": "BACKLOG_WARNING",
            "active_agents": ["jr_reviewer", "prioritizer"],
            "background_feeders": False,
            "background_feeder_interval": 300,
            "reasoning": "hard: reviewers on changed files only, single active repair",
        }
    if tier == "soft":
        return {
            "level": "BACKLOG_SOFT",
            "active_agents": None,
            "background_feeders": True,
            "background_feeder_interval": None,
            "reasoning": "soft: intake softening, dedupe on insert",
        }
    return {
        "level": "NORMAL",
        "active_agents": None,
        "background_feeders": True,
        "background_feeder_interval": None,
        "reasoning": "normal: no backlog throttling",
    }


def count_unaddressed_feedback(conn, task_id: str) -> int:
    """Count unaddressed feedback items for routing decisions.

    seed_task items are excluded: they have no file_path, cannot be
    selected by fetch_top_feedback for the developer, and are handled
    separately by the seed-task addressing path (see
    shell_developer._mark_feedback_addressed). Including them here would
    inflate counts and incorrectly trigger backlog overrides.
    """
    row = conn.execute(
        """
        SELECT COUNT(*) FROM agent_feedback
        WHERE task_id = ? AND addressed = 0 AND category != 'seed_task'
        """,
        (task_id,),
    ).fetchone()
    return int(row[0] if row else 0)


def fetch_top_feedback(conn, task_id: str) -> tuple | None:
    """Pick the highest-priority unaddressed, non-stuck feedback item.

    Excludes seed_task items (which have no file_path) so the developer
    is never dispatched against a non-file target. Seed tasks are addressed
    by the developer turn itself via _mark_feedback_addressed.
    """
    return conn.execute(
        """
        SELECT id, priority, category, file_path, message, suggestion
        FROM agent_feedback
        WHERE task_id = ? AND addressed = 0 AND IFNULL(stuck, 0) = 0
              AND category != 'seed_task'
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


def mark_targeted(conn, fb_id: int, threshold: int) -> None:
    """Increment the targeting counter for a feedback id.

    When the same item has been handed to the developer ``threshold`` times
    without a materialize success (addressed stays 0), mark it ``stuck`` so
    the prioritizer stops cycling on it (plan §4.4.5).
    """
    conn.execute("UPDATE agent_feedback SET targeted_count = targeted_count + 1 WHERE id = ?", (fb_id,))
    conn.execute(
        "UPDATE agent_feedback SET stuck = 1 WHERE id = ? AND targeted_count >= ?",
        (fb_id, threshold),
    )


def stuck_feedback_ids(conn, task_id: str) -> list[int]:
    """Ids of unaddressed feedback items flagged stuck after repeated targeting."""
    rows = conn.execute(
        "SELECT id FROM agent_feedback WHERE task_id = ? AND addressed = 0 AND stuck = 1 ORDER BY id",
        (task_id,),
    ).fetchall()
    return [r[0] for r in rows]


def apply_backlog_overrides(
    task_id: str,
    decision: dict[str, Any] | None,
    conn,
    *,
    force_threshold: int | None = None,
) -> dict[str, Any] | None:
    """
    Apply unattended backlog routing rules.

    - If unaddressed count > force_threshold (default: hard tier from config):
      force developer on top feedback item, tracking targeting for stuck-id.
    - Else if count > 0 and decision next_agent == background: redirect to developer.

    Returns the (possibly new) decision dict.
    """
    total = count_unaddressed_feedback(conn, task_id)

    if force_threshold is None:
        force_threshold = normalize_backlog_tiers()["hard_start"]

    if total > force_threshold:
        top = fetch_top_feedback(conn, task_id)
        if not top:
            return decision
        fb_id, priority, category, file_path, message, suggestion = top
        mark_targeted(conn, fb_id, threshold=_stuck_threshold())
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
        mark_targeted(conn, fb_id, threshold=_stuck_threshold())
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


def _stuck_threshold() -> int:
    """Times a feedback id may be handed to the developer before it is stuck."""
    from core.config import get_config

    cfg = (get_config() or {}).get("feedback", {}) or {}
    raw = cfg.get("stuck_threshold", 3)
    try:
        return max(2, int(raw))
    except (TypeError, ValueError):
        return 3
