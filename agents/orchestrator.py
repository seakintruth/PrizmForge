# agents/orchestrator.py

from agents.base import call_agent
from core.context_manager import get_context_manager
from core.config import get_config
from core.json_parser import parse_json_response


def call_orchestrator(
    task_id: str,
    user_command: str,
    conversation_context: list,
    current_turn: int,
    max_turns: int,
    time_remaining: float,
) -> dict:
    """Call orchestrator with smart token-aware context"""

    context_mgr = get_context_manager()

    config = get_config()
    model = config.get("agent_model_preferences", {}).get("orchestrator")

    context_str, metadata = context_mgr.build_orchestrator_context(
        task_id, user_command, conversation_context, model
    )

    utilization = metadata["context_utilization"]
    utilization_color = (
        "🟢" if utilization < 0.5 else "🟡" if utilization < 0.8 else "🔴"
    )

    print(
        f"  {utilization_color} Context: {metadata['tokens_used']:,} / {metadata['context_limit']:,} tokens "
        f"({utilization:.1%} utilization)"
    )
    print(f"     Files: {len(metadata['files_included'])} included")

    if metadata["files_excluded"]:
        print(
            f"     ⚠️  {len(metadata['files_excluded'])} files excluded - {metadata['truncation_reason']}"
        )

    # Get current feedback backlog count (ALL priorities)
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN priority = 'CRITICAL' THEN 1 ELSE 0 END) as critical,
                    SUM(CASE WHEN priority = 'HIGH' THEN 1 ELSE 0 END) as high,
                    SUM(CASE WHEN priority = 'MEDIUM' THEN 1 ELSE 0 END) as medium,
                    SUM(CASE WHEN priority = 'LOW' THEN 1 ELSE 0 END) as low
                FROM agent_feedback
                WHERE task_id = ? AND addressed = 0
            """,
                (task_id,),
            )
            total, critical, high, medium, low = cursor.fetchone()
    except:
        total, critical, high, medium, low = 0, 0, 0, 0, 0

    # Get CLI mode to know if we should allow 'complete'
    try:
        from core.cli_modes import get_cli_mode_from_config, CLIMode

        cli_mode = get_cli_mode_from_config(config)
        is_unattended = cli_mode == CLIMode.UNATTENDED
    except:
        is_unattended = False

    prompt = f"""{context_str}

**Progress:** Turn {current_turn}/{max_turns} | Time remaining: {time_remaining:.1f}m

**Current Feedback Backlog:** {total} unaddressed
  - CRITICAL: {critical}
  - HIGH: {high}
  - MEDIUM: {medium}
  - LOW: {low}

What should we do next?

**DECISION RULES:**
1. **If backlog > 0** → call "developer" to address highest priority item
2. **If backlog = 0** → call "background" to generate new feedback
3. **Only call "complete"** when:
   - Backlog is empty (0 items)
   - Minimum iterations met ({config.get('min_iterations_before_complete', 3)})
   - Task objectives satisfied
   {"- **NEVER use 'complete' in unattended mode** (current mode: unattended)" if is_unattended else ""}

**Remember:** Work through ALL items in priority order (CRITICAL → HIGH → MEDIUM → LOW), not just high priority ones.

Respond **ONLY** with valid JSON in this exact format:
{{
  "feedback_summary": "Backlog status and next item to address",
  "next_agent": "developer|background|complete",
  "instructions": "Specific instructions for highest priority item, referencing feedback ID",
  "reasoning": "Why you made this decision (include backlog count)",
  "files_needed": ["files to edit"],
  "addressing_feedback_ids": [123],
  "model": "optional-model-override"
}}"""

    response = call_agent("orchestrator", prompt, task_id, conversation_context, model)

    if not response:
        return None

    decision = parse_json_response(
        response,
        expected_keys=["next_agent", "reasoning"],
        strict=False,
        agent_name="orchestrator",
    )

    return decision
