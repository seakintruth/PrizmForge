"""Verifier for the v1 boxed benchmark (docs/benchmark_v1.md §3).

Decides a trial's verdict from the rollout row + the task content contract:

1. infra_aborted — the run died on endpoint infra (§12.1 classifier): counts as
   a pass@1 failure but is excluded from root-cause blaming.
2. failed — the trial did not finish with a real terminal "passed" outcome
   (stalled / timed_out / zero-command failed), or the governed file content
   does not satisfy the contract.
3. passed — real finish **and** every content assertion holds.

Every verdict carries a note and a ``component_hint`` from the fixed enum.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

#: Fixed component_hint enum (HARNESS_EVOLUTION_DESIGN.md §4.3).
COMPONENT_HINTS: frozenset[str] = frozenset(
    {
        "harness_prompt",
        "tool",
        "middleware",
        "skill",
        "memory",
        "subagent",
        "worktree",
        "endpoint",
        "task_contract",
        "parallel_worker",
        "database",
        "verifier",
    }
)

#: Verdict vocabulary.
PASSED = "passed"
FAILED = "failed"
INFRA_ABORTED = "infra_aborted"


@dataclass(frozen=True)
class Verdict:
    verdict: str
    note: str = ""
    component_hint: str = ""

    def __post_init__(self) -> None:
        if self.component_hint and self.component_hint not in COMPONENT_HINTS:
            raise ValueError(f"unknown component_hint: {self.component_hint!r}")


def _assertion_note(assertion) -> str:
    return f"content:{assertion.file_path}:{assertion.mode}"


def _check_assertion(assertion, content: str | None) -> bool:
    """True when governed file content satisfies the assertion."""
    mode = assertion.mode
    fragment = assertion.fragment
    if mode == "contains":
        return content is not None and fragment in content
    if mode == "exact":
        return content is not None and content == fragment
    if mode == "absent":
        return content is None or fragment not in content
    # Unknown mode is a verifier bug — fail closed.
    return False


def _read_file(file_path: str) -> str | None:
    from core.file_operations import get_file_content_from_db

    try:
        return get_file_content_from_db(file_path)
    except Exception:
        return None


def verify_trial(task, rollout: dict[str, Any] | None) -> Verdict:
    """Return the verdict for one trial given its rollout row (never raises)."""
    if rollout is None:
        return Verdict(FAILED, note="no_rollout", component_hint="verifier")
    if rollout.get("infra_abort") or rollout.get("status") == INFRA_ABORTED:
        return Verdict(INFRA_ABORTED, note="infra_aborted", component_hint="endpoint")

    status = rollout.get("status")
    if status != PASSED:
        return Verdict(FAILED, note=f"status:{status}", component_hint="task_contract")

    for assertion in task.contract:
        content = _read_file(assertion.file_path)
        if not _check_assertion(assertion, content):
            return Verdict(
                FAILED,
                note=_assertion_note(assertion),
                component_hint="task_contract",
            )
    return Verdict(PASSED, note="content_ok", component_hint="verifier")


def record_verdict(rollout_id: int, verdict: Verdict, contract_hash: str) -> None:
    """Persist ``contract_hash / verdict / verdict_note`` onto a rollout row.

    Best-effort — the rollouts table is the observability substrate, and a write
    failure must never take down the loop.
    """
    from core.db_connection import get_db_connection

    try:
        with get_db_connection() as conn:
            conn.execute(
                """
                UPDATE rollouts
                SET contract_hash = ?, verdict = ?, verdict_note = ?
                WHERE rollout_id = ?
                """,
                (contract_hash, verdict.verdict, verdict.note, int(rollout_id)),
            )
    except Exception as e:
        print(f"   ⚠️  Could not record verdict for rollout {rollout_id}: {e}")
