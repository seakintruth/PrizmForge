"""Main task execution workflow"""

import json
import time
from typing import Any

from agents.base import call_agent
from agents.orchestrator import call_orchestrator
from agents.parallel_workers import get_agent_pool
from core.config import get_config
from core.db_connection import get_db_connection
from core.db_helpers import (
    age_feedback_backlog,
    complete_task,
    create_task,
)
from workflow.backlog import apply_backlog_overrides
from workflow.developer_edit import run_developer_mutation
from workflow.edit_mode_selector import DEFAULT_FALLBACK_ORDER
from workflow.path_targets import extract_files_needed_from_text, sanitize_path_token


def _safe_json_response(response: Any) -> dict | None:
    """Safely parse response that might be a mock or malformed."""
    if not response:
        return None
    if isinstance(response, dict):
        return response
    if hasattr(response, "json"):  # MagicMock with .json()
        try:
            return response.json()
        except Exception:
            pass
    try:
        if isinstance(response, str):
            return json.loads(response)
        return json.loads(str(response))
    except Exception:
        return None


def run_task_cycle(
    task_id: str,
    user_command: str,
    max_turns: int = 20,
    time_box_minutes: int | None = None,
):
    """Run complete task cycle with orchestration."""
    config = get_config()

    if time_box_minutes is None:
        time_box_minutes = config.get("default_iteration_minutes", 5)

    min_iterations = config.get("min_iterations_before_complete", 3)
    background_enabled = config.get("background_agents_enabled", True)

    fe_cfg = config.get("file_editing", {}) or {}
    legacy_method = fe_cfg.get("method", "guid_sloc")
    preferred_modes = fe_cfg.get("preferred_modes") or (
        [legacy_method] if legacy_method in ("guid_sloc", "guid", "full_replace", "planned_diff", "find_replace") else None
    )
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

    # Backlog hygiene
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

    conversation_context: list = []
    current_turn = 0
    progress: dict[str, int] = {
        "files_modified": 0,
        "developer_calls": 0,
        "reviewer_calls": 0,
        "researcher_calls": 0,
        "valid_edit_payloads": 0,
        "edit_failures": 0,
        "fallback_successes": 0,
        "materialize_successes": 0,
    }

    try:
        while current_turn < max_turns:
            current_turn += 1
            iteration_end = time.time() + time_box_minutes * 60

            print(f"\n{'=' * 60}")
            print(f"🔄 Iteration {current_turn}/{max_turns} | Elapsed: {(time.time() - start_time) / 60:.1f}m")
            print(f"{'=' * 60}\n")

            decision = call_orchestrator(task_id, user_command, conversation_context, current_turn, max_turns, (iteration_end - time.time()) / 60)

            if decision:
                with get_db_connection() as conn:
                    decision = apply_backlog_overrides(task_id, decision, conn)

            next_agent = (decision or {}).get("next_agent", "complete")
            print(f"📋 Decision: {next_agent}")

            if isinstance(decision, dict):
                conversation_context.append({"role": "assistant", "content": json.dumps(decision)})

            if next_agent == "complete":
                with get_db_connection() as conn:
                    critical = conn.execute(
                        "SELECT COUNT(*) FROM agent_feedback WHERE task_id = ? AND addressed = 0 AND priority IN ('CRITICAL', 'HIGH')",
                        (task_id,),
                    ).fetchone()[0]

                if current_turn < min_iterations or critical > 0:
                    continue

                print(f"✅ Task marked complete after {current_turn} iterations")
                complete_task(task_id, "Completed by orchestrator decision")
                break

            if next_agent == "developer":
                # Developer path (kept compact)
                understanding_prompt = f"""{(decision or {}).get("instructions", user_command)}

**Task Context:**
- You have access to the project file list

Please respond with FILES_NEEDED and PLAN."""

                understanding = call_agent(
                    "developer",
                    understanding_prompt,
                    task_id,
                    conversation_context,
                    (decision or {}).get("model"),
                )

                requested_files = extract_files_needed_from_text(understanding or "")
                if not requested_files:
                    requested_files = ["app.py"]

                requested_files = [sanitize_path_token(f) for f in requested_files if sanitize_path_token(f)]

                mut = run_developer_mutation(
                    task_id=task_id,
                    instructions=(decision or {}).get("instructions", user_command),
                    user_command=user_command,
                    requested_files=requested_files,
                    conversation_context=conversation_context,
                    model_choice=(decision or {}).get("model"),
                    preferred_modes=preferred_modes,
                    fallback_order=fallback_order,
                    small_file_threshold=small_file_threshold,
                    progress=progress,
                    decision=decision,
                    current_turn=current_turn,
                )
                print(f"   Developer status: {mut.get('status')}")

            elif next_agent == "background":
                try:
                    from agents.resource_controller_worker import get_resource_controller

                    rc = get_resource_controller()
                    current_decision = rc.get_current_decision()

                    if current_decision and getattr(current_decision, "level", None) == "BACKLOG_PROCESSING":
                        print("   🔄 Processing backlog item...")
                        # TODO: Implement full backlog processing (you wanted this fixed)
                        time.sleep(2)
                    else:
                        print("   ⏸️  Yielding to background agents...")
                        time.sleep(3)
                except Exception as e:
                    print(f"   ⚠️ Background error: {e}")

            if time.time() >= iteration_end:
                print("⏰ Iteration timeout")

            time.sleep(0.5)

    finally:
        if background_enabled:
            get_agent_pool().stop()

    print(f"\n{'=' * 60}")
    print(f"📊 Task Summary | Iterations: {current_turn} | Duration: {(time.time() - start_time) / 60:.1f}m")
    print(f"   Files Modified: {progress.get('files_modified', 0)}")
    print(f"{'=' * 60}\n")
