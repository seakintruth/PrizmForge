"""
Git closed loop: record a failed git commit / pre-commit hook for the
mutation path (Workstream A, Phase 1).

When materialize_proposal() returns status="git_failed" the disk write
already happened (fix-forward default). This helper surfaces the failure
to the feedback loop so the next developer turn can act on it:
  - emits edit.git_failed event (never edit.materialized)
  - writes one CRITICAL agent_feedback row, deduped by proposal_id
  - prints a console summary with the hook excerpt

Both developer_edit.run_developer_mutation and
shell_developer._gate_and_materialize share this path so the dedupe /
event logic lives in exactly one place.
"""

from __future__ import annotations

from typing import Any

from core.db_connection import get_db_connection
from core.db_helpers import save_agent_feedback
from core.events import publish_event

_HOOK_EXCERPT_MAX = 500


def record_git_failure(mat: dict[str, Any], task_id: str | None, proposal_id: str) -> bool:
    """Record a git/hook failure into events + CRITICAL feedback.

    Returns True when a git failure was recorded, False when the result
    carries no attempted git failure (callers fall through to their
    normal materialized / failed branches).
    """
    git_failed = mat.get("git_failed") or {}
    if not git_failed.get("attempted"):
        return False

    stderr_excerpt = (git_failed.get("stderr") or "")[:_HOOK_EXCERPT_MAX]
    publish_event(
        "edit.git_failed",
        source="writer",
        task_id=task_id,
        proposal_id=proposal_id,
        payload=git_failed,
    )

    # CRITICAL feedback — dedupe by proposal_id in file_event_id so a
    # re-materialize (e.g. retried turn) cannot pile up duplicate rows.
    with get_db_connection() as conn:
        existing = conn.execute(
            "SELECT id FROM agent_feedback WHERE file_event_id = ? LIMIT 1",
            (proposal_id,),
        ).fetchone()
    if not existing:
        save_agent_feedback(
            agent_name="git_hook",
            file_path=git_failed.get("file_path") or "",
            priority="CRITICAL",
            category="bug",
            message=f"git {git_failed.get('stage', '?')} failed (code={git_failed.get('code')}): " + stderr_excerpt,
            suggestion="Fix the pre-commit hook failure before continuing.",
            task_id=task_id or "",
            file_event_id=proposal_id,
        )

    print(f"   🔴 Git {git_failed.get('stage', '?')} failed (code={git_failed.get('code')})")
    print(f"      Hook excerpt: {stderr_excerpt[:200]}")
    return True
