"""Verifier for the boxed benchmark (docs/benchmark_v1.md §3, docs/TODO.md §14.3).

Decides a trial's verdict from the rollout row + the task contract:

1. infra_aborted — the run died on endpoint infra (§12.1 classifier): counts as
   a pass@1 failure but is excluded from root-cause blaming.
2. failed — the trial did not finish with a real terminal "passed" outcome
   (stalled / timed_out / zero-command failed), or the governed file content
   does not satisfy the contract, or the command verifier did not exit 0.
3. passed — real finish **and** every content assertion holds (content tasks),
   or the verifier command exits 0 with governed-edit evidence present
   (terminal tasks, §14.3 command mode).

Every verdict carries a note and a ``component_hint`` from the fixed enum.
"""

from __future__ import annotations

import functools
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
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

#: CommandRunner = ``Callable[[command, timeout_s], (exit_code, output)]``.
CommandRunner = Callable[[str, int], tuple[int, str]]


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
    if mode == "new":
        # §13.5 "mode: new" — must be absent in the fixture, present after.
        # The fixture keys are checked by the caller (needs task context); the
        # content half is: fragment present now.
        return content is not None and fragment in content
    # Unknown mode is a verifier bug — fail closed.
    return False


def _read_file(file_path: str, workdir: str | Path | None = None) -> tuple[str | None, str | None]:
    """Read file content from the governed DB, with the on-disk trial worktree
    as fallback, recording which source satisfied (§13.5).

    Returns ``(content, source)`` where ``source`` is ``"db"`` (governed
    content), ``"disk"`` (file under the bench project dir), or ``None`` when
    neither source yields the file. Never raises.
    """
    from core.file_operations import get_file_content_from_db

    source: str | None = None
    content: str | None = None
    try:
        content = get_file_content_from_db(file_path)
        if content is not None:
            source = "db"
    except Exception:
        content = None

    if content is None and workdir is not None:
        try:
            base = Path(workdir).resolve()
            candidate = (base / file_path).resolve()
            if candidate.is_relative_to(base) and candidate.is_file():
                content = candidate.read_text(encoding="utf-8", errors="replace")
                source = "disk"
        except Exception:
            content = None
    return content, source


def evidence_satisfied(task_id: str) -> bool:
    """§13.5/§14.3 honesty gate: at least one real governed edit for the trial.

    A trial that "finished" without any proposal that applied AND wrote to disk
    (``edit_proposals.status = 'applied'`` joined to a ``file_write_log`` row
    with ``status = 'success'``) must not pass, even when the verifier command
    exits 0. Never raises — on DB trouble it degrades to False so a command
    victory alone can never silence the gate.
    """
    try:
        from core.db_connection import get_db_connection

        with get_db_connection() as conn:
            row = conn.execute(
                """
                SELECT 1 FROM edit_proposals ep
                JOIN file_write_log wl ON wl.proposal_id = ep.proposal_id
                WHERE ep.task_id = ?
                  AND ep.status = 'applied'
                  AND wl.status = 'success'
                LIMIT 1
                """,
                (str(task_id)[:200],),
            ).fetchone()
            return row is not None
    except Exception:
        return False


def _command_runner(workdir: str | Path) -> CommandRunner:
    """Default §14.3 runner: ShellWorktree.run_test_command semantics, no worktree."""
    from workflow.shell_developer import run_shell_test

    return functools.partial(run_shell_test, cwd=str(workdir))


def verify_trial(
    task,
    rollout: dict[str, Any] | None,
    *,
    workdir: str | Path | None = None,
    runner: CommandRunner | None = None,
) -> Verdict:
    """Return the verdict for one trial given its rollout row (never raises)."""
    if rollout is None:
        return Verdict(FAILED, note="no_rollout", component_hint="verifier")
    if rollout.get("infra_abort") or rollout.get("status") == INFRA_ABORTED:
        return Verdict(INFRA_ABORTED, note="infra_aborted", component_hint="endpoint")

    status = rollout.get("status")
    if status != PASSED:
        return Verdict(FAILED, note=f"status:{status}", component_hint="task_contract")

    # §14.3 command mode: verifier command exits 0 + governed-edit evidence.
    if task.verifier is not None:
        if workdir is None:
            return Verdict(FAILED, note="verifier_aborted:no_workdir", component_hint="verifier")
        if not evidence_satisfied(str(rollout.get("task_id") or "")):
            return Verdict(
                FAILED,
                note="no_governed_edit_evidence",
                component_hint="verifier",
            )
        run = runner if runner is not None else _command_runner(workdir)
        exit_code, output = run(task.verifier.command, task.verifier.timeout)
        if exit_code == 0:
            return Verdict(PASSED, note="command_ok", component_hint="verifier")
        tail = (output or "")[:200]
        if exit_code == 124:
            return Verdict(FAILED, note=f"command:timed_out:{tail}", component_hint="verifier")
        return Verdict(FAILED, note=f"command:{exit_code}:{tail}", component_hint="verifier")

    used_disk = False
    for assertion in task.contract:
        content, source = _read_file(assertion.file_path, workdir)
        if source == "disk":
            used_disk = True
        if assertion.mode == "new" and assertion.file_path in (task.fixture or {}):
            # §13.5 "mode: new": a fragment already true in the fixture cannot
            # satisfy the task's "created by the agent" claim.
            return Verdict(
                FAILED,
                note=f"{_assertion_note(assertion)}:preexisting_in_fixture",
                component_hint="task_contract",
            )
        if not _check_assertion(assertion, content):
            # Record which source (db/disk) the failing content came from.
            note = _assertion_note(assertion)
            if source == "disk":
                note = f"{note}:disk"
            return Verdict(FAILED, note=note, component_hint="task_contract")
    note = "content_ok:disk" if used_disk else "content_ok"
    return Verdict(PASSED, note=note, component_hint="verifier")


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
