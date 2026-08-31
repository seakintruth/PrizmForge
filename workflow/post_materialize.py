"""
Post-materialize targeted re-verify (Workstream C, plan §5).

After a *successful* materialize, refresh system state for touched files only:
one high-priority FileChangeEvent per path (localized verify), an orchestrator
message, and publication of the single ``edit.materialized`` event. On
git/hook **failure** the outcome is applied without any "celebration" counters
and the hook-cited files are parsed for the next developer turn.
"""

from __future__ import annotations

from typing import Any

from core.events import publish_event


def queue_localized_verify(materialized_paths: list[str], task_id: str | None) -> int:
    """Queue exactly one high-priority FileChangeEvent per changed path.

    Returns the number of events queued (0 when the background pool is not
    running — nothing would consume the events anyway).
    """
    from agents.parallel_workers import get_agent_pool
    from core.file_operations import get_file_content_from_db

    pool = get_agent_pool()
    if not pool.running:
        return 0

    queued = 0
    seen: set[str] = set()
    for path in materialized_paths or []:
        if not path or path in seen:
            continue
        seen.add(path)
        content = get_file_content_from_db(path)
        pool.queue_file_change(file_path=path, operation="verify", content=content)
        queued += 1
    return queued


def notify_path_changed(materialized_paths: list[str], task_id: str) -> None:
    """Tell the orchestrator which paths changed so the next decision can verify."""
    from core.db_helpers import post_message

    paths = [p for p in materialized_paths or [] if p]
    if not paths:
        return
    post_message(
        "developer",
        "orchestrator",
        f"Path changed: {', '.join(paths)}. Verify before next feature.",
        task_id,
        "HIGH",
    )


def apply_materialize_outcome(
    mat: dict[str, Any],
    *,
    task_id: str,
    progress: dict[str, Any],
) -> str:
    """Route a materialize result to its correct outcomes.

    - ``git_failed`` → record the failure feedback (no success counters, no
      ``edit.materialized``). The next developer turn receives the parsed
      hook-cited files.
    - ``success`` → increment counters, emit ``edit.materialized``, queue a
      bounded localized verify, and notify the orchestrator of changed paths.
    - otherwise → ``edit.failed`` + failure counter.

    Returns the outcome status name.
    """
    status = mat.get("status") if isinstance(mat, dict) else "error"

    if status == "git_failed":
        from workflow.git_failure import record_git_failure

        record_git_failure(mat, task_id, mat.get("proposal_id") or "")
        return "git_failed"

    if status == "success":
        publish_event(
            "edit.materialized",
            source="writer",
            task_id=task_id,
            proposal_id=mat.get("proposal_id"),
            payload=mat,
        )
        progress["files_modified"] = progress.get("files_modified", 0) + 1
        progress["materialize_successes"] = progress.get("materialize_successes", 0) + 1
        queue_localized_verify(mat.get("materialized_files") or [], task_id)
        notify_path_changed(mat.get("materialized_files") or [], task_id)
        return "success"

    publish_event(
        "edit.failed",
        source="writer",
        task_id=task_id,
        proposal_id=mat.get("proposal_id") if isinstance(mat, dict) else None,
        payload=mat,
    )
    progress["edit_failures"] = progress.get("edit_failures", 0) + 1
    return status if isinstance(status, str) else "error"
