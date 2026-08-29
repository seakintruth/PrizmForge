"""Main task execution workflow"""

import json
import time
from datetime import datetime
from typing import Any

from agents.base import _last_call_http_latency, call_agent
from agents.orchestrator import call_orchestrator
from agents.parallel_workers import get_agent_pool
from core.config import get_config
from core.db_connection import get_db_connection
from core.db_helpers import age_feedback_backlog, complete_task, create_task, post_message
from core.file_operations import get_file_content_from_db, is_secret_path, should_ignore_file
from workflow.backlog import apply_backlog_overrides, count_unaddressed_feedback
from workflow.developer_edit import run_developer_mutation
from workflow.edit_mode_selector import DEFAULT_FALLBACK_ORDER
from workflow.path_targets import extract_files_needed_from_text, sanitize_path_token

# Governed editing imports

# Active-work tracking: accumulates HTTP latency (seconds) across call_agent
# invocations within a single iteration. Rate-limit sleeps and DB lock
# backoffs are excluded so iteration timeouts count only real work.
_active_work_seconds: float = 0.0

#: Sequential-agent network failures within one iteration before the busy-loop
#: guard pauses scheduling for a turn (plan §8.4 residual, §15 decision 5).
NETWORK_FAILURE_PAUSE_THRESHOLD = 2

#: Consecutive developer sessions that materialize zero file changes before the
#: loop stops respinning the identical session (d9, soak recompute 2026-08-29:
#: task_002/003/005 ran 30-call shell sessions producing no changes under
#: rate-limit pressure, yet the orchestrator re-dispatched the same developer
#: turn every iteration — "📋 Decision: developer", Work 0.0s each time).
NO_PROGRESS_TURNS_THRESHOLD = 3


def _is_network_failure_text(text: str | None) -> bool:
    """Detect endpoint-outage phrasing in an agent result message.

    Matches the shell developer's ``LlmUnavailable`` exit status and the
    endpoint-manager's "endpoint unavailable" wording. Keep the check cheap and
    obvious so future outage phrasings are easy to extend.
    """
    hay = (text or "").lower().replace("_", "")
    return "llmunavailable" in hay or "endpoint unavailable" in hay or "network" in hay


def _edit_mode_settings(config: dict) -> tuple[list | None, list, int]:
    """Multi-mode editing config (t-shirt size + fallback), shared by dispatch sites."""
    fe_cfg = config.get("file_editing", {}) or {}
    # Legacy single-method setting is treated as a soft preference only
    legacy_method = fe_cfg.get("method", "guid_sloc")
    preferred_modes = fe_cfg.get("preferred_modes") or (
        [legacy_method] if legacy_method in ("guid_sloc", "guid", "full_replace", "planned_diff", "find_replace") else None
    )
    # Normalize legacy names
    if preferred_modes:
        preferred_modes = [("guid" if m in ("guid_sloc", "guid") else "diff" if m in ("planned_diff", "diff") else m) for m in preferred_modes]
    fallback_order = fe_cfg.get("fallback_order") or list(DEFAULT_FALLBACK_ORDER)
    small_file_threshold = int(fe_cfg.get("small_file_threshold_lines", 180))
    return preferred_modes, fallback_order, small_file_threshold


def _inject_seed_feedback(task_id: str, user_command: str) -> None:
    """Insert the active seed/task description as HIGH feedback so the
    prioritizer/orchestrator/redirect machinery has concrete work from turn 1.

    Without this, a cold-start run has backlog=0 and the orchestrator rationally
    chooses 'background', orphaning the seed task until reviewers happen to post
    findings. Idempotent per (task_id, category='seed_task').
    """
    if not user_command or not user_command.strip():
        return
    try:
        with get_db_connection() as conn:
            existing = conn.execute(
                "SELECT COUNT(*) FROM agent_feedback WHERE task_id = ? AND category = 'seed_task'",
                (task_id,),
            ).fetchone()[0]
            if existing:
                return
            conn.execute(
                """
                INSERT INTO agent_feedback
                (agent_name, file_path, priority, category, message, suggestion,
                 task_id, file_event_id, timestamp)
                VALUES ('system', NULL, 'HIGH', 'seed_task', ?, NULL, ?, ?, ?)
                """,
                (
                    f"[SEED TASK] {user_command.strip()[:1000]}",
                    task_id,
                    f"seed-{task_id}",
                    datetime.now().isoformat(),
                ),
            )
            print(f"🌱 Seed task registered as feedback item (task {task_id})")
    except Exception as e:
        print(f"   ⚠️  Seed feedback injection skipped: {e}")


def _dispatch_developer(
    *,
    task_id: str,
    instructions: str,
    user_command: str,
    decision: dict,
    conversation_context: list,
    model_choice: str | None,
    progress: dict,
    current_turn: int,
    requested_files: list[str] | None = None,
) -> dict:
    """Single developer dispatch point honoring ``developer.implementation``.

    Shared by the orchestrator 'developer' path and the BACKLOG_PROCESSING
    redirect so the shell/edit_payload switch applies everywhere. Returns the
    mutation result dict; callers append it to conversation_context.
    """
    config = get_config()
    dev_impl = (config.get("developer", {}) or {}).get("implementation", "edit_payload")
    if dev_impl == "shell":
        from workflow.shell_developer import run_shell_developer_turn

        mut = run_shell_developer_turn(
            task_id=task_id,
            instructions=instructions or user_command,
            user_command=user_command,
            conversation_context=conversation_context,
            model_choice=model_choice,
            progress=progress,
            decision=decision,
            current_turn=current_turn,
        )
        if mut.get("status") not in ("success", "rejected"):
            print(f"   ⚠️  Shell developer status: {mut.get('status')} {mut.get('message', '')}")
        return mut

    preferred_modes, fallback_order, small_file_threshold = _edit_mode_settings(config)
    mut = run_developer_mutation(
        task_id=task_id,
        instructions=instructions or user_command,
        user_command=user_command,
        requested_files=requested_files or [],
        conversation_context=conversation_context,
        model_choice=model_choice,
        preferred_modes=preferred_modes,
        fallback_order=fallback_order,
        small_file_threshold=small_file_threshold,
        progress=progress,
        decision=decision,
        current_turn=current_turn,
    )
    if mut.get("status") not in ("success", "rejected"):
        print(f"   ⚠️  Developer mutation status: {mut.get('status')} {mut.get('message', '')}")
    return mut


def _finish_gate_blocked(
    critical_count: int,
    high_pending: int,
    highs_pending_turns: int,
    grace: int,
) -> tuple[bool, str]:
    """Decide whether a FINISH decision must be deferred.

    CRITICAL items always block. HIGH items block only until the orchestrator
    has requested completion `grace` consecutive turns with them still pending
    — background reviewers keep the HIGH backlog non-empty indefinitely, which
    in the 12h soak prevented every task from ever closing.
    """
    if critical_count > 0:
        return True, f"{critical_count} CRITICAL item(s) remain"
    if high_pending > 0 and highs_pending_turns < grace:
        return True, f"{high_pending} HIGH item(s) pending (grace {highs_pending_turns}/{grace})"
    return False, ""


def _finalize_task(task_id: str, progress: dict, reason: str) -> None:
    """Write a terminal status for a task.

    `completed` when the task produced file changes, `stalled` otherwise.
    Never downgrades an already-terminal task (e.g. completed via FINISH).
    """
    status = "completed" if progress.get("files_modified", 0) > 0 else "stalled"
    result = f"{reason}: files_modified={progress.get('files_modified', 0)}"
    try:
        with get_db_connection() as conn:
            conn.execute(
                """
                UPDATE tasks SET status = ?, completed_at = ?, result = ?
                WHERE id = ? AND status = 'in_progress'
            """,
                (status, datetime.now().isoformat(), result, task_id),
            )
        print(f"📌 Task {task_id} finalized as '{status}' ({result})")
    except Exception as e:
        print(f"   ⚠️  Failed to finalize task {task_id}: {e}")


def _ensure_pool_started(
    agent_pool: Any,
    task_id: str,
    progress: dict,
    current_turn: int,
    *,
    pool_start_after_turns: int = 2,
) -> None:
    """Defer the background pool start (residual W5, soak 2026-08-29).

    Soak9 started the pool instantly and queued a 1155-event initial burst
    that shared the core code loop's RateLimiter/TokenBudget, producing the
    429 flood. The pool now starts only after the task's FIRST successful
    materialize proves it is a real working task, or after
    ``pool_start_after_turns`` turns - whichever comes first. Idempotent:
    BackgroundAgentPool.start is a no-op once running, and test FakePools
    have no start() to guard against.
    """
    if agent_pool is None or not hasattr(agent_pool, "start"):
        return
    if getattr(agent_pool, "running", False):
        return
    if progress.get("materialize_successes", 0) == 0 and current_turn < pool_start_after_turns:
        return
    print("   🌱 Deferred background pool start: task is productive, spawning workers")
    agent_pool.start(task_id)


class NetworkBusyLoopGuard:
    """Busy-loop guard for sequential-agent network outages (plan §8.4 decision 5).

    Counts network-grade agent failures; once the threshold is reached it pauses
    scheduling for a single iteration and surfaces exactly ONE CRITICAL summary
    per outage episode. A successful agent response resets both the counter and
    the episode flag, so a recovered proxy resumes at full cadence and a
    persistent outage cannot flood the message/error tables.
    """

    def __init__(self, threshold: int = NETWORK_FAILURE_PAUSE_THRESHOLD):
        self.threshold = max(1, int(threshold))
        self._fail_count = 0
        self._critical_shown = False
        self.pause_requested = False

    def record_failure(self) -> bool:
        """Register one network-grade failure; True when the loop must pause."""
        self._fail_count += 1
        if self._fail_count >= self.threshold and not self.pause_requested:
            self.pause_requested = True
            return True
        return False

    def surface(self, task_id: str) -> None:
        """Write the single CRITICAL outage summary (no-op once per episode)."""
        if self._critical_shown:
            return
        self._critical_shown = True
        post_message(
            "system",
            "orchestrator",
            "Sequential agents failed network — pausing scheduling for one iteration. Single CRITICAL summary for the outage; the loop resumes automatically.",
            task_id,
            "CRITICAL",
        )

    def record_success(self) -> None:
        """A sequential agent responded: outage (if any) is over."""
        self._fail_count = 0
        self._critical_shown = False

    def consume_pause(self) -> None:
        self.pause_requested = False


class NoProgressLoopGuard:
    """d9: stop respinning an identical no-progress developer session.

    Soak9 (2026-08-29): tasks 002, 003 and 005 all show files_modified=0 while
    the orchestrator chose "developer" every single iteration; each shell session
    burned 30 model calls (mostly rate-limit retries) and returned error with
    "Work: 0.0s". Counting consecutive zero-change developer turns is the same
    signal ``_finalize_task`` uses to call a task stalled.

    Once the streak reaches the threshold the guard latches: subsequent
    "developer" decisions are redirected to background discovery and ONE HIGH
    stall summary is posted per episode. Any developer turn that actually
    materializes a file clears the streak and the latch.
    """

    def __init__(self, threshold: int = NO_PROGRESS_TURNS_THRESHOLD):
        self.threshold = max(1, int(threshold))
        self._streak = 0
        self._stall_shown = False

    def stalled(self) -> bool:
        return self._streak >= self.threshold

    def record_change(self) -> None:
        self._streak = 0
        self._stall_shown = False

    def record_no_change(self, task_id: str) -> bool:
        """Count one zero-change turn; True once the guard latches."""
        self._streak += 1
        if self._streak >= self.threshold and not self._stall_shown:
            self._stall_shown = True
            post_message(
                "system",
                "orchestrator",
                (
                    f"No progress: developer produced no file changes in {self._streak} "
                    "consecutive sessions. Pausing developer re-dispatch; routing "
                    "through other agents."
                ),
                task_id,
                "HIGH",
            )
        return self._streak >= self.threshold


def _record_developer_progress(guard: NoProgressLoopGuard, task_id: str, progress: dict, files_before: int) -> None:
    """Feed the d9 guard from a developer turn's file-change delta."""
    if progress["files_modified"] > files_before:
        guard.record_change()
    else:
        guard.record_no_change(task_id)


def run_task_cycle(  # noqa: C901
    task_id: str,
    user_command: str,
    max_turns: int = 20,
    time_box_minutes: int | None = None,
):
    """Run complete task cycle with orchestration"""
    config = get_config()

    if time_box_minutes is None:
        time_box_minutes = config.get("default_iteration_minutes", 5)

    min_iterations = config.get("min_iterations_before_complete", 3)
    background_enabled = config.get("background_agents_enabled", True)

    preferred_modes, fallback_order, _small_file_threshold = _edit_mode_settings(config)

    print(f"\n{'=' * 60}")
    print(f"🚀 Task: {task_id}")
    print(f"⏱️  Iteration: {time_box_minutes}m | Min iterations: {min_iterations}")
    print(f"📝 Edit modes: preferred={preferred_modes or 'auto'} | fallback={fallback_order}")
    print(f"{'=' * 60}\n")

    create_task(task_id, user_command)
    _inject_seed_feedback(task_id, user_command)
    start_time = time.time()

    # Backlog hygiene: age out old LOW items and cap unbounded growth
    try:
        fe_age = config.get("feedback") or {}
        aging = age_feedback_backlog(
            max_age_days_low=int(fe_age.get("max_age_days_low", 7)),
            max_unaddressed=int(fe_age.get("max_unaddressed", 200)),
        )
        if aging.get("dismissed_low") or aging.get("trimmed_medium"):
            print(f"🧹 Backlog aging: dismissed_low={aging.get('dismissed_low', 0)} trimmed_medium={aging.get('trimmed_medium', 0)}")
    except Exception as e:
        print(f"   ⚠️  Backlog aging skipped: {e}")

    agent_pool = None
    if background_enabled:
        agent_pool = get_agent_pool()
        # Residual W5: NO eager pool.start(task_id) here. Background workers
        # (and their queued burst) are deferred until _ensure_pool_started,
        # called each iteration, decides the task is real.
        print()

    conversation_context = []
    current_turn = 0

    progress = {
        "files_modified": 0,
        "developer_calls": 0,
        "reviewer_calls": 0,
        "researcher_calls": 0,
        "last_file_change": None,
        "valid_edit_payloads": 0,
        "edit_failures": 0,
        "fallback_successes": 0,
        "materialize_successes": 0,
    }
    finish_grace_turns = 0

    network_guard = NetworkBusyLoopGuard()
    no_progress_guard = NoProgressLoopGuard()

    try:
        max_orchestrator_retries = 3

        while current_turn < max_turns:
            current_turn += 1
            _ensure_pool_started(agent_pool, task_id, progress, current_turn)
            iteration_start = time.time()
            iteration_end = iteration_start + (time_box_minutes * 60)
            active_budget = time_box_minutes * 60

            # Busy-loop guard: consume one full iteration without any agent
            # dispatch after a sequential-agent network outage (plan §8.4).
            if network_guard.pause_requested:
                print("   🛑 Pausing scheduling for one iteration (sequential-agent network failure guard).")
                network_guard.consume_pause()
                continue

            orchestrator_attempts = 0
            decision = None

            # Reset active-work counter for this iteration
            global _active_work_seconds
            _active_work_seconds = 0.0

            elapsed_total = (time.time() - start_time) / 60
            time_remaining = (iteration_end - time.time()) / 60

            print(f"\n{'=' * 60}")
            print(f"🔄 Iteration {current_turn}/{max_turns} | Elapsed: {elapsed_total:.1f}m | Work: {_active_work_seconds:.1f}s")
            print(f"{'=' * 60}\n")

            while orchestrator_attempts < max_orchestrator_retries and not decision:
                orchestrator_attempts += 1
                if orchestrator_attempts > 1:
                    print(f"   🔄 Orchestrator retry {orchestrator_attempts}/{max_orchestrator_retries}...")

                decision = call_orchestrator(
                    task_id,
                    user_command,
                    conversation_context,
                    current_turn,
                    max_turns,
                    time_remaining,
                )
                if decision:
                    network_guard.record_success()
                _active_work_seconds += _last_call_http_latency

                try:
                    with get_db_connection() as conn:
                        cursor = conn.cursor()

                        cursor.execute(
                            """
                            SELECT COUNT(*) FROM agent_feedback
                            WHERE task_id = ? AND addressed = 0
                        """,
                            (task_id,),
                        )
                        total_backlog = cursor.fetchone()[0]

                        decision = apply_backlog_overrides(task_id, decision, conn)
                        total_backlog = count_unaddressed_feedback(conn, task_id)
                        if decision and decision.get("reasoning", "").startswith("BACKLOG OVERRIDE"):
                            print(f"   🚨 BACKLOG OVERRIDE: {decision.get('reasoning')}")
                        elif decision and "OVERRIDE:" in str(decision.get("reasoning", "")):
                            print(f"   🔄 REDIRECT: background → developer (backlog: {total_backlog})")

                except Exception as e:
                    print(f"   ⚠️  Backlog check failed: {e}")

                if not decision and orchestrator_attempts < max_orchestrator_retries:
                    post_message(
                        "system",
                        "orchestrator",
                        "Previous response failed to parse. Please respond with valid JSON.",
                        task_id,
                        "CRITICAL",
                    )
                    time.sleep(2)

            # All retries exhausted without a parseable decision — fail safe
            # instead of crashing the unattended loop. If the token budget is
            # exhausted (the usual cause), stop the cycle cleanly: retrying
            # would just burn the remaining time on guaranteed failures.
            if decision is None:
                budget_exhausted = False
                try:
                    from agents.base import get_token_budget

                    budget_exhausted = not get_token_budget().can_spend(1)
                except Exception as e:
                    print(f"   ⚠️  Token budget check failed: {e}")

                if budget_exhausted:
                    print(f"   🛑 Orchestrator failed after {max_orchestrator_retries} attempts AND token budget is exhausted — ending task cycle cleanly.")
                    post_message(
                        "system",
                        "orchestrator",
                        "Task cycle ended: orchestrator unresponsive and token budget exhausted. Checkpoint saved; resume when budget resets.",
                        task_id,
                        "HIGH",
                    )
                    # Residual P6: budget-exhausted cycles were ending with the
                    # task still 'in_progress'; finalize (completed/stalled)
                    # so the run table reflects reality.
                    _finalize_task(task_id, progress, reason="token budget exhausted")
                    return progress

                if network_guard.record_failure():
                    network_guard.surface(task_id)

                print(
                    f"   ❌ Orchestrator failed to produce a valid decision after "
                    f"{max_orchestrator_retries} attempts — using fail-safe "
                    f"'background' dispatch and continuing."
                )
                post_message(
                    "system",
                    "orchestrator",
                    "Orchestrator repeatedly returned unparseable output. Continuing with background discovery while the loop retries.",
                    task_id,
                    "HIGH",
                )
                decision = {
                    "next_agent": "background",
                    "instructions": user_command,
                    "files_needed": [],
                    "reasoning": "FAILSAFE: orchestrator returned no parseable decision; background discovery dispatched to keep the cycle productive.",
                }

            next_agent = decision.get("next_agent", "complete")
            instructions = decision.get("instructions", "")
            files_needed = decision.get("files_needed", [])
            model_choice = decision.get("model")

            print(f"📋 Decision: {next_agent}")

            conversation_context.append({"role": "assistant", "content": json.dumps(decision)})

            # d9: after a streak of zero-change developer sessions, stop
            # respinning the identical session. Redirect developer choices to
            # background discovery (FAILSAFE-style, same shape as the fallback
            # decision above) until a developer turn actually changes a file.
            if next_agent == "developer" and no_progress_guard.stalled():
                print("   🧯 No-progress stall guard: redirecting developer dispatch to background discovery.")
                decision = {
                    "next_agent": "background",
                    "instructions": user_command,
                    "files_needed": [],
                    "reasoning": "Stall guard: repeated no-progress developer sessions; background discovery dispatched.",
                }
                next_agent = "background"

            # =====================================================
            # COMPLETION HANDLING
            # =====================================================
            if next_agent == "complete":
                if current_turn < min_iterations:
                    post_message(
                        "system",
                        "orchestrator",
                        "Task completion requested too early.",
                        task_id,
                        "HIGH",
                    )
                    continue

                with get_db_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        SELECT
                            SUM(CASE WHEN priority = 'CRITICAL' THEN 1 ELSE 0 END),
                            SUM(CASE WHEN priority = 'HIGH' THEN 1 ELSE 0 END)
                        FROM agent_feedback
                        WHERE task_id = ? AND addressed = 0
                        AND priority IN ('CRITICAL', 'HIGH')
                    """,
                        (task_id,),
                    )
                    row = cursor.fetchone()
                    critical_count = row[0] or 0
                    high_pending = row[1] or 0

                if high_pending > 0 and critical_count == 0:
                    finish_grace_turns += 1
                else:
                    finish_grace_turns = 0

                gate_cfg = config.get("finish_gate", {}) or {}
                blocked, block_reason = _finish_gate_blocked(
                    critical_count=critical_count,
                    high_pending=high_pending,
                    highs_pending_turns=finish_grace_turns,
                    grace=int(gate_cfg.get("high_grace_iterations", 3)),
                )
                if blocked:
                    post_message(
                        "system",
                        "orchestrator",
                        f"Finish deferred: {block_reason}.",
                        task_id,
                        "CRITICAL" if critical_count else "HIGH",
                    )
                    continue

                print(f"✅ Task marked complete after {current_turn} iterations")
                complete_task(task_id, "Completed by orchestrator decision")
                continue

            # =====================================================
            # DEVELOPER PATH
            # =====================================================
            if next_agent == "developer":
                # Shell implementation skips Phase-1 file negotiation entirely;
                # the worktree agent explores and verifies on its own.
                dev_impl = (config.get("developer", {}) or {}).get("implementation", "edit_payload")
                if dev_impl == "shell":
                    files_before = progress["files_modified"]
                    mut = _dispatch_developer(
                        task_id=task_id,
                        instructions=instructions or user_command,
                        user_command=user_command,
                        decision=decision,
                        conversation_context=conversation_context,
                        model_choice=model_choice,
                        progress=progress,
                        current_turn=current_turn,
                    )
                    _active_work_seconds += _last_call_http_latency
                    if _is_network_failure_text(str(mut.get("message", ""))):
                        network_guard.record_failure()
                        if network_guard.pause_requested:
                            network_guard.surface(task_id)
                    else:
                        network_guard.record_success()
                    _record_developer_progress(no_progress_guard, task_id, progress, files_before)
                    conversation_context.append({"role": "assistant", "content": json.dumps(mut, default=str)[:4000]})
                    continue

                #  === PHASE 1: UNDERSTANDING (Conditional - skip if backlog override) ===
                understanding_prompt = f"""{instructions}

**Task Context:**
- You have access to the project file list
- You can request specific files by path

Please respond with:
1. Which file(s) you need to examine (provide exact paths)
2. What changes you plan to make
3. Why these changes address the feedback

Format:
FILES_NEEDED: path/to/file1.py, path/to/file2.py
PLAN: [brief explanation]"""

                print("\n💭 Phase 1: Developer analyzing task...")
                understanding = call_agent(
                    "developer",
                    understanding_prompt,
                    task_id,
                    conversation_context,
                    model_choice,
                )
                _active_work_seconds += _last_call_http_latency

                if not understanding:
                    print("   ❌ Developer failed to respond")
                    network_guard.record_failure()
                    if network_guard.pause_requested:
                        network_guard.surface(task_id)
                    continue

                print("   ✅ Developer response received")
                network_guard.record_success()

                # === EXTRACT FILES FROM PHASE 1 (sanitized) ===
                requested_files = extract_files_needed_from_text(understanding or "")

                if not requested_files and files_needed:
                    requested_files = []
                    for f in files_needed:
                        clean = sanitize_path_token(f) if f else None
                        if clean:
                            requested_files.append(clean)
                    if requested_files:
                        print(f"   📋 Using orchestrator's files_needed: {', '.join(requested_files)}")

                if not requested_files:
                    addressing_ids = decision.get("addressing_feedback_ids", [])
                    if addressing_ids:
                        with get_db_connection() as conn:
                            cursor = conn.cursor()
                            cursor.execute(
                                """
                                SELECT file_path FROM agent_feedback
                                WHERE id = ? LIMIT 1
                            """,
                                (addressing_ids[0],),
                            )
                            row = cursor.fetchone()
                            if row:
                                clean = sanitize_path_token(row[0])
                                if clean:
                                    requested_files = [clean]

                if not requested_files:
                    requested_files = ["app.py", "README.md"]
                    print(f"   🚀 Cold-start default: Assigning initial target files: {', '.join(requested_files)}")

                # Validate / filter paths (drop anything that fails sanitization)
                valid_files = []
                for fpath in requested_files:
                    clean = sanitize_path_token(fpath)
                    if not clean:
                        print(f"   ⚠️  Skipping invalid path token: {fpath!r}")
                        continue
                    content_db = get_file_content_from_db(clean)
                    if content_db is not None:
                        valid_files.append(clean)
                        print(f"   📄 Existing file found in DB: {clean}")
                    else:
                        valid_files.append(clean)
                        print(f"   ✨ New file target registered for creation: {clean}")

                requested_files = valid_files

                # === DEVELOPER MUTATION (extracted) ===
                files_before = progress["files_modified"]
                mut = _dispatch_developer(
                    task_id=task_id,
                    instructions=instructions or user_command,
                    user_command=user_command,
                    decision=decision,
                    conversation_context=conversation_context,
                    model_choice=model_choice,
                    progress=progress,
                    current_turn=current_turn,
                    requested_files=requested_files,
                )
                _active_work_seconds += _last_call_http_latency
                _record_developer_progress(no_progress_guard, task_id, progress, files_before)

            # BACKGROUND AGENTS - Yield control
            # =====================================================
            elif next_agent == "background":
                try:
                    # Ensure the deferred pool is live before queueing
                    # (residual W5) so the orchestrator's explicit
                    # 'background' decision triggers the same productive-task
                    # gate as a materialize would.
                    _ensure_pool_started(agent_pool, task_id, progress, current_turn)
                    from agents.resource_controller_worker import get_resource_controller

                    rc = get_resource_controller()
                    current_decision = rc.get_current_decision()

                    # Check if in backlog mode (freeze or hard tier: no random
                    # feeder reviews — route orchestrator 'background' to the
                    # single active developer repair instead, plan §4.3).
                    if current_decision and current_decision.level in ("BACKLOG_PROCESSING", "BACKLOG_WARNING"):
                        with get_db_connection() as conn:
                            cursor = conn.cursor()
                            cursor.execute("""SELECT COUNT(*) FROM agent_feedback
                                             WHERE addressed = 0 AND category != 'seed_task'""")
                            backlog_count = cursor.fetchone()[0]

                            cursor.execute("""
                                SELECT id, priority, category, file_path, message, suggestion
                                FROM agent_feedback
                                WHERE addressed = 0 AND category != 'seed_task'
                                ORDER BY
                                    CASE priority
                                        WHEN 'CRITICAL' THEN 1
                                        WHEN 'HIGH' THEN 2
                                        WHEN 'MEDIUM' THEN 3
                                        ELSE 4
                                    END,
                                    timestamp
                                LIMIT 1
                            """)
                            top_item = cursor.fetchone()

                            if not top_item:
                                print("   ℹ️  Backlog cleared! Marking complete.")
                                next_agent = "complete"
                            else:
                                (
                                    fb_id,
                                    priority,
                                    category,
                                    file_path,
                                    message,
                                    suggestion,
                                ) = top_item

                                cursor.execute("""
                                    SELECT id, priority, category, file_path, message
                                    FROM agent_feedback
                                    WHERE addressed = 0 AND category != 'seed_task'
                                    ORDER BY
                                        CASE priority
                                            WHEN 'CRITICAL' THEN 1
                                            WHEN 'HIGH' THEN 2
                                            WHEN 'MEDIUM' THEN 3
                                            ELSE 4
                                        END,
                                        timestamp
                                    LIMIT 4 OFFSET 1
                                """)
                                next_items = cursor.fetchall()

                        if top_item and not no_progress_guard.stalled():
                            print(f"   ⚠️  Orchestrator chose 'background', but agents are PAUSED (backlog: {backlog_count})")
                            print("   🔄 Redirecting to 'developer' to work on prioritized feedback")

                            developer_instructions = f"""**BACKLOG PROCESSING MODE - {backlog_count} items to address**

**YOUR TASK: Fix the highest priority item**

**Item #{fb_id} - [{priority}] {category}**
- File: `{file_path}`
- Issue: {message}
"""

                            if suggestion:
                                developer_instructions += f"- Suggested fix: {suggestion}\n"

                            if next_items:
                                developer_instructions += "\n**Context - Next items in queue:**\n"
                                for idx, (
                                    _nxt_id,
                                    nxt_priority,
                                    nxt_category,
                                    nxt_file,
                                    nxt_message,
                                ) in enumerate(next_items, 2):
                                    developer_instructions += f"{idx}. [{nxt_priority}] {nxt_category} in `{nxt_file}` - {nxt_message[:60]}...\n"

                            developer_instructions += f"""
**IMPORTANT:**
- Create EditPayload with operations to fix item #{fb_id}
- Reference feedback_id {fb_id} in your proposal rationale
- Focus ONLY on this item - don't try to fix everything at once
"""

                            post_message(
                                "system",
                                "orchestrator",
                                f"🚨 BACKLOG MODE: {backlog_count} items. Processing item #{fb_id}: [{priority}] {category}",
                                task_id,
                                "HIGH",
                            )

                            print(f"   📋 Target: Item #{fb_id} - [{priority}] {category}")
                            print(f"   📄 File: {file_path}")
                            print(f"   💡 Issue: {message[:80]}{'...' if len(message) > 80 else ''}")

                            # Real dispatch through the configured developer
                            # implementation; addressing_feedback_ids makes
                            # materialized work mark this item addressed.
                            print(f"   🔄 Dispatching developer for item #{fb_id}")
                            files_before = progress["files_modified"]
                            mut = _dispatch_developer(
                                task_id=task_id,
                                instructions=developer_instructions,
                                user_command=user_command,
                                decision={
                                    **decision,
                                    "addressing_feedback_ids": [fb_id],
                                    "reasoning": "BACKLOG PROCESSING redirect",
                                },
                                conversation_context=conversation_context,
                                model_choice=model_choice,
                                progress=progress,
                                current_turn=current_turn,
                                requested_files=[file_path] if file_path else [],
                            )
                            _active_work_seconds += _last_call_http_latency
                            if _is_network_failure_text(str(mut.get("message", ""))):
                                network_guard.record_failure()
                                if network_guard.pause_requested:
                                    network_guard.surface(task_id)
                            else:
                                network_guard.record_success()
                            _record_developer_progress(no_progress_guard, task_id, progress, files_before)
                            conversation_context.append({"role": "assistant", "content": json.dumps(mut, default=str)[:4000]})

                        elif top_item:
                            # d9: stall latch — do not respin the identical
                            # developer session from backlog redirect either.
                            print("   🧯 No-progress stall guard: keeping developer paused in backlog mode.")
                            time.sleep(8)

                    else:
                        # NORMAL MODE: Yield to background agents
                        print("   ⏸️  Yielding to background agents...")

                        try:
                            resource_controller = get_resource_controller()
                            resource_controller.temporarily_disable_throttling(duration_seconds=30)
                            print("     🔓 Resource restrictions temporarily lifted")
                        except Exception as e:
                            print(f"    ⚠️  Exception handled in task_runner.py: {e}")

                        try:
                            agent_pool = get_agent_pool()

                            with get_db_connection() as conn:
                                cursor = conn.cursor()

                                cursor.execute("""
                                    SELECT file_path FROM project_files
                                    WHERE is_binary = 0
                                    ORDER BY last_modified DESC
                                    LIMIT 5
                                """)
                                recent_files = [row[0] for row in cursor.fetchall()]

                                cursor.execute("""
                                    SELECT file_path FROM project_files
                                    WHERE is_binary = 0
                                    ORDER BY RANDOM()
                                    LIMIT 5
                                """)
                                random_files = [row[0] for row in cursor.fetchall()]

                            all_files = list(set(recent_files + random_files))

                            # Workstream E §7.2: never hand secrets / caches to agents
                            all_files = [f for f in all_files if f and not should_ignore_file(f) and not is_secret_path(f)]

                            for file_path in all_files:
                                try:
                                    content = get_file_content_from_db(file_path)
                                    if content:
                                        agent_pool.queue_file_change(
                                            file_path=file_path,
                                            operation="review",
                                            content=content,
                                        )
                                except Exception as e:
                                    print(f"     ⚠️  Failed to queue {file_path}: {e}")

                            print(f"     📤 Queued {len(all_files)} files for background review")

                        except Exception as e:
                            print(f"     ⚠️  Failed to queue files: {e}")

                        time.sleep(8)

                except Exception as e:
                    print(f"   ⚠️  Background agent handling error: {e}")
                    import traceback

                    traceback.print_exc()

            else:
                print(f"⚠️  Unknown or unsupported agent decision: {next_agent}")

            if _active_work_seconds >= active_budget:
                print(f"\n⏰ Iteration timeout (active work: {_active_work_seconds:.1f}s >= {active_budget}s)")

            time.sleep(0.5)

        # Loop exhausted without an orchestrator FINISH: write a terminal
        # status so the task does not linger as in_progress forever (soak:
        # 5/5 tasks orphaned this way).
        _finalize_task(task_id, progress, reason="max_turns exhausted")

    except KeyboardInterrupt:
        # Residual P6: a manual stop must still write a terminal status; the
        # finally block (worker stop) still runs below.
        _finalize_task(task_id, progress, reason="KeyboardInterrupt")
        raise
    except Exception as e:
        _finalize_task(task_id, progress, reason=f"error: {e}")
        raise

    finally:
        if background_enabled:
            get_agent_pool().stop()

    print(f"\n{'=' * 60}")
    print(f"📊 Task Summary | Iterations: {current_turn} | Duration: {(time.time() - start_time) / 60:.1f}m")
    print(f"   Files Modified: {progress['files_modified']}")
    print(f"   Developer calls: {progress.get('developer_calls', 0)}")
    print(f"   Valid edit payloads: {progress.get('valid_edit_payloads', 0)}")
    print(f"   Edit failures: {progress.get('edit_failures', 0)}")
    print(f"   Fallback successes: {progress.get('fallback_successes', 0)}")
    print(f"   Materialize successes: {progress.get('materialize_successes', 0)}")
    print(f"{'=' * 60}\n")
