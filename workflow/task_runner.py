"""Main task execution workflow"""

import json
import time

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

# Governed editing imports


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

    # Multi-mode editing config (t-shirt size + fallback)
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

    try:
        max_orchestrator_retries = 3

        while current_turn < max_turns:
            current_turn += 1
            iteration_start = time.time()
            iteration_end = iteration_start + (time_box_minutes * 60)

            orchestrator_attempts = 0
            decision = None

            elapsed_total = (time.time() - start_time) / 60
            time_remaining = (iteration_end - time.time()) / 60

            print(f"\n{'=' * 60}")
            print(f"🔄 Iteration {current_turn}/{max_turns} | Elapsed: {elapsed_total:.1f}m")
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

            next_agent = decision.get("next_agent", "complete")
            instructions = decision.get("instructions", "")
            files_needed = decision.get("files_needed", [])
            model_choice = decision.get("model")

            print(f"📋 Decision: {next_agent}")

            conversation_context.append({"role": "assistant", "content": json.dumps(decision)})

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
                        SELECT COUNT(*) FROM agent_feedback
                        WHERE task_id = ? AND addressed = 0
                        AND priority IN ('CRITICAL', 'HIGH')
                    """,
                        (task_id,),
                    )
                    critical_count = cursor.fetchone()[0]

                if critical_count > 0:
                    post_message(
                        "system",
                        "orchestrator",
                        f"{critical_count} CRITICAL/HIGH items remain.",
                        task_id,
                        "CRITICAL",
                    )
                    continue

                print(f"✅ Task marked complete after {current_turn} iterations")
                complete_task(task_id, "Completed by orchestrator decision")
                continue

            # =====================================================
            # DEVELOPER PATH
            # =====================================================
            if next_agent == "developer":
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

                if not understanding:
                    print("   ❌ Developer failed to respond")
                    continue

                print("   ✅ Developer response received")

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

            # BACKGROUND AGENTS - Yield control
            # =====================================================
            elif next_agent == "background":
                try:
                    from agents.resource_controller_worker import get_resource_controller

                    rc = get_resource_controller()
                    current_decision = rc.get_current_decision()

                    # Check if in backlog mode
                    if current_decision and current_decision.level == "BACKLOG_PROCESSING":
                        with get_db_connection() as conn:
                            cursor = conn.cursor()
                            cursor.execute("SELECT COUNT(*) FROM agent_feedback WHERE addressed = 0")
                            backlog_count = cursor.fetchone()[0]

                            cursor.execute("""
                                SELECT id, priority, category, file_path, message, suggestion
                                FROM agent_feedback
                                WHERE addressed = 0
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
                                    WHERE addressed = 0
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

                        if top_item:
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

                            # Recursively call developer path (simplified - just log it)
                            print("   🔄 Would process via developer agent (implementation needed)")

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
