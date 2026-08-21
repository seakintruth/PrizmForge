"""Main task execution workflow"""

import json
import time
from typing import Any

from agents.base import call_agent
from agents.orchestrator import call_orchestrator
from agents.parallel_workers import get_agent_pool
from core.config import get_config
from core.db_connection import get_db_connection
from core.db_helpers import age_feedback_backlog, complete_task, create_task, post_message
from core.file_operations import get_file_content_from_db
from workflow.backlog import apply_backlog_overrides, count_unaddressed_feedback
from workflow.developer_edit import run_developer_mutation
from workflow.edit_mode_selector import DEFAULT_FALLBACK_ORDER
from workflow.path_targets import extract_files_needed_from_text, sanitize_path_token


def run_task_cycle(  # noqa: C901
    task_id: str,
    user_command: str,
    max_turns: int = 20,
    time_box_minutes: int | None = None,
):
    """
    Run complete task cycle with orchestration and proper backlog handling.

    This is the main control loop for PrizmForge's autonomous editing.
    It coordinates between the orchestrator, developer, and background agents.
    """
    config = get_config()

    if time_box_minutes is None:
        time_box_minutes = config.get("default_iteration_minutes", 5)

    min_iterations = config.get("min_iterations_before_complete", 3)
    background_enabled = config.get("background_agents_enabled", True)

    # Multi-mode editing configuration (t-shirt size + fallback)
    fe_cfg = config.get("file_editing", {}) or {}
    legacy_method = fe_cfg.get("method", "guid_sloc")
    preferred_modes = fe_cfg.get("preferred_modes") or (
        [legacy_method] if legacy_method in ("guid_sloc", "guid", "full_replace", "planned_diff", "find_replace") else None
    )
    # Normalize legacy names
    if preferred_modes:
        preferred_modes = [("guid" if m in ("guid_sloc", "guid") else "diff" if m in ("planned_diff", "diff") else m) for m in preferred_modes]

    fallback_order = fe_cfg.get("fallback_order") or list(DEFAULT_FALLBACK_ORDER)
    small_file_threshold = int(fe_cfg.get("small_file_threshold_lines", 180))

    print(f"\n{'=' * 60}")
    print(f"🚀 Task: {task_id}")
    print(f"⏱️  Iteration: {time_box_minutes}m | Min iterations: {min_iterations}")
    print(f"📝 Edit modes: preferred={preferred_modes or 'auto'} | fallback={fallback_order}")
    print(f"{'=' * 60}\n")

    create_task(task_id, user_command)
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

    if background_enabled:
        agent_pool = get_agent_pool()
        agent_pool.start(task_id)
        print()

    conversation_context = []
    current_turn = 0

    progress: dict[str, Any] = {
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

    try:
        max_orchestrator_retries = 3

        while current_turn < max_turns:
            current_turn += 1
            iteration_end = time.time() + (time_box_minutes * 60)

            elapsed_total = (time.time() - start_time) / 60
            time_remaining = (iteration_end - time.time()) / 60

            print(f"\n{'=' * 60}")
            print(f"🔄 Iteration {current_turn}/{max_turns} | Elapsed: {elapsed_total:.1f}m")
            print(f"{'=' * 60}\n")

            # === ORCHESTRATOR DECISION WITH RETRY ===
            decision = None
            for attempt in range(max_orchestrator_retries):
                if attempt > 0:
                    print(f"   🔄 Orchestrator retry {attempt + 1}/{max_orchestrator_retries}...")

                decision = call_orchestrator(
                    task_id,
                    user_command,
                    conversation_context,
                    current_turn,
                    max_turns,
                    time_remaining,
                )

                try:
                    with get_db_connection() as conn:
                        decision = apply_backlog_overrides(task_id, decision, conn)
                        total_backlog = count_unaddressed_feedback(conn, task_id)

                        if decision and decision.get("reasoning", "").startswith("BACKLOG OVERRIDE"):
                            print(f"   🚨 BACKLOG OVERRIDE: {decision.get('reasoning')}")
                        elif decision and "OVERRIDE:" in str(decision.get("reasoning", "")):
                            print(f"   🔄 REDIRECT: background → developer (backlog: {total_backlog})")
                except Exception as e:
                    print(f"   ⚠️  Backlog check failed: {e}")

                if decision:
                    break

                if attempt < max_orchestrator_retries - 1:
                    post_message(
                        "system",
                        "orchestrator",
                        "Previous response failed to parse. Please respond with valid JSON.",
                        task_id,
                        "CRITICAL",
                    )
                    time.sleep(2)

            next_agent = decision.get("next_agent", "complete") if decision else "complete"
            instructions = decision.get("instructions", "") if decision else ""
            files_needed = decision.get("files_needed", []) if decision else []
            model_choice = decision.get("model") if decision else None

            print(f"📋 Decision: {next_agent}")

            if decision:
                conversation_context.append({"role": "assistant", "content": json.dumps(decision)})

            # =====================================================
            # COMPLETION HANDLING
            # =====================================================
            if next_agent == "complete":
                if current_turn < min_iterations:
                    post_message("system", "orchestrator", "Task completion requested too early.", task_id, "HIGH")
                    continue

                with get_db_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        SELECT COUNT(*) FROM agent_feedback
                        WHERE task_id = ? AND addressed = 0
                        AND priority IN ('CRITICAL', 'HIGH')
                        """,
                        (task_id,),
                    )
                    critical_count = cursor.fetchone()[0]

                if critical_count > 0:
                    post_message("system", "orchestrator", f"{critical_count} CRITICAL/HIGH items remain.", task_id, "CRITICAL")
                    continue

                print(f"✅ Task marked complete after {current_turn} iterations")
                complete_task(task_id, "Completed by orchestrator decision")
                break

            # =====================================================
            # DEVELOPER PATH
            # =====================================================
            if next_agent == "developer":
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

                if not understanding:
                    print("   ❌ Developer failed to respond")
                    continue

                print("   ✅ Developer response received")

                requested_files = extract_files_needed_from_text(understanding or "")

                if not requested_files and files_needed:
                    requested_files = [sanitize_path_token(f) for f in files_needed if sanitize_path_token(f)]

                if not requested_files and decision and decision.get("addressing_feedback_ids"):
                    with get_db_connection() as conn:
                        row = conn.execute("SELECT file_path FROM agent_feedback WHERE id = ? LIMIT 1", (decision["addressing_feedback_ids"][0],)).fetchone()
                        if row and row[0]:
                            clean = sanitize_path_token(row[0])
                            if clean:
                                requested_files = [clean]

                if not requested_files:
                    requested_files = ["app.py", "README.md"]
                    print(f"   🚀 Cold-start default: {', '.join(requested_files)}")

                valid_files = [sanitize_path_token(f) for f in requested_files if sanitize_path_token(f)]
                requested_files = valid_files or ["app.py"]

                mut = run_developer_mutation(
                    task_id=task_id,
                    instructions=instructions or user_command,
                    user_command=user_command,
                    requested_files=requested_files,
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

            # =====================================================
            # BACKGROUND AGENTS - Yield control
            # =====================================================
            elif next_agent == "background":
                try:
                    from agents.resource_controller_worker import get_resource_controller

                    rc = get_resource_controller()
                    current_decision = rc.get_current_decision()

                    if current_decision and current_decision.level == "BACKLOG_PROCESSING":
                        # === FIXED: Actually process the backlog item ===
                        with get_db_connection() as conn:
                            cursor = conn.cursor()
                            cursor.execute("SELECT COUNT(*) FROM agent_feedback WHERE addressed = 0")
                            backlog_count = cursor.fetchone()[0]

                            cursor.execute("""
                                SELECT id, priority, category, file_path, message, suggestion
                                FROM agent_feedback
                                WHERE addressed = 0
                                ORDER BY
                                    CASE priority WHEN 'CRITICAL' THEN 1 WHEN 'HIGH' THEN 2
                                    WHEN 'MEDIUM' THEN 3 ELSE 4 END,
                                    timestamp
                                LIMIT 5
                            """)
                            items = cursor.fetchall()

                        if not items:
                            print("   ℹ️  Backlog cleared! Marking complete.")
                            next_agent = "complete"
                            continue

                        fb_id, priority, category, file_path, message, suggestion = items[0]
                        next_items = items[1:]

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
                            for idx, (_, nxt_pri, nxt_cat, nxt_file, nxt_msg) in enumerate(next_items, 2):
                                developer_instructions += f"{idx}. [{nxt_pri}] {nxt_cat} in `{nxt_file}` - {nxt_msg[:60]}...\n"

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

                        target_files = [sanitize_path_token(file_path)] if sanitize_path_token(file_path) else ["app.py"]

                        mut = run_developer_mutation(
                            task_id=task_id,
                            instructions=developer_instructions,
                            user_command=user_command,
                            requested_files=target_files,
                            conversation_context=conversation_context,
                            model_choice=model_choice,
                            preferred_modes=preferred_modes,
                            fallback_order=fallback_order,
                            small_file_threshold=small_file_threshold,
                            progress=progress,
                            decision=decision or {},
                            current_turn=current_turn,
                        )

                        print(f"   📊 Backlog mutation status: {mut.get('status', 'unknown')}")

                    else:
                        print("   ⏸️  Yielding to background agents...")
                        resource_controller = get_resource_controller()
                        resource_controller.temporarily_disable_throttling(duration_seconds=30)

                        # Existing background review logic (kept for full feature parity)
                        try:
                            agent_pool = get_agent_pool()
                            with get_db_connection() as conn:
                                cursor = conn.cursor()
                                cursor.execute("""
                                    SELECT file_path FROM project_files
                                    WHERE is_binary = 0
                                    ORDER BY last_modified DESC LIMIT 5
                                """)
                                recent = [r[0] for r in cursor.fetchall()]

                                cursor.execute("""
                                    SELECT file_path FROM project_files
                                    WHERE is_binary = 0 ORDER BY RANDOM() LIMIT 5
                                """)
                                random_files = [r[0] for r in cursor.fetchall()]

                            for fpath in set(recent + random_files):
                                content = get_file_content_from_db(fpath)
                                if content:
                                    agent_pool.queue_file_change(fpath, "review", content)
                        except Exception as e:
                            print(f"     ⚠️  Failed to queue files: {e}")

                        time.sleep(4)

                except Exception as e:
                    print(f"   ⚠️  Background agent handling error: {e}")
                    import traceback

                    traceback.print_exc()

            else:
                print(f"⚠️  Unknown or unsupported agent decision: {next_agent}")

            if time.time() >= iteration_end:
                print("\n⏰ Iteration timeout")

            time.sleep(0.5)

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
