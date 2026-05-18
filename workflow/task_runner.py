"""Main task execution workflow"""
import time
import json
import re
from typing import Optional

from agents.orchestrator import call_orchestrator
from agents.base import call_agent
from agents.parallel_workers import get_agent_pool
from core.db_helpers import create_task, complete_task, post_message
from core.file_operations import (
    get_file_content_from_db,
    format_file_for_agent,
    format_file_with_guids,      # GUID-aware version for Developer/Reviewer
)
from core.config import get_config
from core.db_connection import get_db_connection
from core.json_parser import parse_json_response

# Governed editing imports
from workflow.proposal_builder import create_proposal_from_developer_output, update_proposal_status
from file_editing.writer import materialize_proposal
from file_editing.db import log_error


def run_task_cycle(task_id: str, user_command: str, max_turns: int = 20,
                   time_box_minutes: Optional[int] = None):
    """Run complete task cycle with orchestration"""
    config = get_config()
    
    if time_box_minutes is None:
        time_box_minutes = config.get("default_iteration_minutes", 5)
    
    min_iterations = config.get("min_iterations_before_complete", 3)
    background_enabled = config.get("background_agents_enabled", True)
    
    print(f"\n{'='*60}")
    print(f"🚀 Task: {task_id}")
    print(f"⏱️  Iteration: {time_box_minutes}m | Min iterations: {min_iterations}")
    print(f"{'='*60}\n")
    
    create_task(task_id, user_command)
    start_time = time.time()
    
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
        "last_file_change": None
    }

    try:
        MAX_ORCHESTRATOR_RETRIES = 3

        while current_turn < max_turns:
            current_turn += 1
            iteration_start = time.time()
            iteration_end = iteration_start + (time_box_minutes * 60)

            orchestrator_attempts = 0
            decision = None

            elapsed_total = (time.time() - start_time) / 60
            time_remaining = (iteration_end - time.time()) / 60
            
            print(f"\n{'='*60}")
            print(f"🔄 Iteration {current_turn}/{max_turns} | Elapsed: {elapsed_total:.1f}m")
            print(f"{'='*60}\n")
            
            while orchestrator_attempts < MAX_ORCHESTRATOR_RETRIES and not decision:
                orchestrator_attempts += 1
                if orchestrator_attempts > 1:
                    print(f"   🔄 Orchestrator retry {orchestrator_attempts}/{MAX_ORCHESTRATOR_RETRIES}...")
                
                decision = call_orchestrator(
                    task_id, user_command, conversation_context,
                    current_turn, max_turns, time_remaining
                )
                
                if not decision and orchestrator_attempts < MAX_ORCHESTRATOR_RETRIES:
                    post_message("system", "orchestrator", 
                        "Previous response failed to parse. Please respond with valid JSON.", task_id, "CRITICAL")
                    time.sleep(2)
            
            if not decision:
                print(f"❌ Orchestrator failed after {MAX_ORCHESTRATOR_RETRIES} attempts")
                decision = {
                    "next_agent": "reviewer",
                    "reasoning": "Orchestrator failed - defaulting to review",
                    "instructions": "Review the current state",
                    "files_needed": []
                }
                
            next_agent = decision.get("next_agent", "").lower()
         
            # Progress forcing
            if current_turn > 3 and progress["files_modified"] == 0 and progress["developer_calls"] == 0:
                print(f"⚠️  FORCING developer call - no file changes after {current_turn} turns")
                next_agent = "developer"

            if next_agent == "developer":
                progress["developer_calls"] += 1
            elif next_agent == "reviewer":
                progress["reviewer_calls"] += 1
            elif next_agent == "researcher":
                progress["researcher_calls"] += 1
            
            instructions = decision.get("instructions", "")
            files_needed = decision.get("files_needed", [])
            model_choice = decision.get("model")
            
            print(f"📋 Decision: {next_agent}")
            
            conversation_context.append({"role": "assistant", "content": json.dumps(decision)})
            
            # COMPLETION HANDLING
            if next_agent == "complete":
                if current_turn < min_iterations:
                    post_message("system", "orchestrator", 
                        f"Task completion requested too early.", task_id, "HIGH")
                    continue
                
                with get_db_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT COUNT(*) FROM agent_feedback
                        WHERE task_id = ? AND addressed = 0 
                        AND priority IN ('CRITICAL', 'HIGH')
                    """, (task_id,))
                    critical_count = cursor.fetchone()[0]
                
                if critical_count > 0:
                    post_message("system", "orchestrator", 
                        f"{critical_count} CRITICAL/HIGH items remain.", task_id, "CRITICAL")
                    continue
                
                print(f"✅ Task marked complete after {current_turn} iterations")
                complete_task(task_id, "Completed by orchestrator decision")
                continue

            # =====================================================
            # DEVELOPER → GOVERNED EDITING PATH (Primary path)
            # =====================================================
            if next_agent == "developer":
                enhanced_instructions = instructions

                # === GUID-AWARE FILE CONTEXT (Required for EditPayload) ===
                if files_needed:
                    enhanced_instructions += "\n\n**📄 Requested File Contents (with line_guids):**\n\n"
                    for file_path in files_needed:
                        enhanced_instructions += format_file_with_guids(file_path) + "\n\n"

                response = call_agent("developer", enhanced_instructions, task_id, conversation_context, model_choice)
                
                if response:
                    conversation_context.append({"role": "assistant", "content": response[:500]})

                    print(f"\n📝 Creating governed edit proposal...")

                    target_file_path = "unknown_file.py"
                    try:
                        match = re.search(r'"target_file_path"\s*:\s*"([^"]+)"', response)
                        if match:
                            target_file_path = match.group(1)
                    except Exception:
                        pass

                    proposal_result = create_proposal_from_developer_output(
                        developer_output=response,
                        proposed_by_agent_id=1,
                        target_file_path=target_file_path
                    )

                    if proposal_result.get("status") == "success":
                        proposal_id = proposal_result["proposal_id"]
                        print(f"   ✅ Proposal created: {proposal_id}")
                        update_proposal_status(proposal_id, "under_review")

                        # REVIEWER EVALUATION (JSON)
                        print(f"   🔍 Sending to Reviewer for decision...")
                        reviewer_prompt = f"""Review this edit proposal:

Proposal ID: {proposal_id}
Target File: {target_file_path}

{response}

Respond ONLY with valid JSON:
{{
  "decision": "APPROVE" | "REJECT",
  "reason": "Explanation if rejecting",
  "suggestions": ["Optional improvements (allowed on both approve and reject)"]
}}"""

                        reviewer_response = call_agent("reviewer", reviewer_prompt, task_id)

                        try:
                            decision_data = json.loads(reviewer_response)
                            decision = decision_data.get("decision", "").upper()
                            reason = decision_data.get("reason", "")
                            suggestions = decision_data.get("suggestions", [])

                            # Always post suggestions if provided (on both APPROVE and REJECT)
                            if suggestions:
                                suggestion_text = "\n".join([f"- {s}" for s in suggestions])
                                post_message("reviewer", "prioritizer",
                                    f"Suggestions from Reviewer for Proposal {proposal_id}:\n{suggestion_text}",
                                    task_id, "MEDIUM")

                            if decision == "REJECT":
                                print(f"   ❌ Reviewer rejected proposal: {reason}")
                                update_proposal_status(proposal_id, "rejected")
                                post_message("reviewer", "orchestrator",
                                    f"Proposal {proposal_id} REJECTED.\nReason: {reason}", task_id, "HIGH")

                            elif decision == "APPROVE":
                                print(f"   ✅ Reviewer approved proposal {proposal_id}")
                                update_proposal_status(proposal_id, "approved")
                                print(f"   📝 Materializing changes to disk...")
                                materialize_proposal(proposal_id)
                                progress["files_modified"] += 1
                                progress["last_file_change"] = current_turn

                        except json.JSONDecodeError:
                            print(f"   ❌ Reviewer returned invalid JSON.")
                            log_error("task_runner", "reviewer", "HIGH", 
                                      "Invalid JSON from reviewer", proposal_id=proposal_id)

            # =====================================================
            # BACKGROUND AGENTS – Yield control
            # =====================================================
            elif next_agent == "background":
                print("   ⏸️  Yielding to background agents...")

                # 1. Temporarily lift resource controller restrictions for this turn
                try:
                    from core.resource_controller import get_resource_controller
                    resource_controller = get_resource_controller()
                    resource_controller.temporarily_disable_throttling(duration_seconds=30)
                    print("     🔓 Resource restrictions temporarily lifted for background agents")
                except Exception:
                    pass  # Resource controller may not be active

                # 2. Prompt background agents by queuing files for review
                try:
                    agent_pool = get_agent_pool()

                    with get_db_connection() as conn:
                        cursor = conn.cursor()
                        # Queue recently modified files first (high priority)
                        cursor.execute("""
                            SELECT file_path FROM project_files 
                            WHERE is_binary = 0 
                            ORDER BY last_modified DESC 
                            LIMIT 5
                        """)
                        recent_files = [row[0] for row in cursor.fetchall()]

                        # Also queue some random files
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
                                    priority=3  # Medium-high priority
                                )
                        except Exception as e:
                            print(f"     ⚠️  Failed to queue {file_path}: {e}")

                    print(f"     📤 Queued {len(all_files)} files for background review")

                except Exception as e:
                    print(f"     ⚠️  Failed to prompt background agents: {e}")

                # 3. Give background agents time to work
                time.sleep(8)

            else:
                print(f"⚠️  Unknown or unsupported agent decision: {next_agent}")

            if time.time() >= iteration_end:
                print(f"\n⏰ Iteration timeout")
            
            time.sleep(0.5)

    finally:
        if background_enabled:
            get_agent_pool().stop()

    print(f"\n{'='*60}")
    print(f"📊 Task Summary | Iterations: {current_turn} | Duration: {(time.time()-start_time)/60:.1f}m")
    print(f"{'='*60}\n")