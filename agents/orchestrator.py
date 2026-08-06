# agents/orchestrator.py
from agents.base import call_agent
from core.config import get_config
from core.context_manager import get_context_manager
from core.db_connection import get_db_connection
from core.json_parser import parse_json_response


def call_orchestrator(
    task_id: str,
    user_command: str,
    conversation_context: list,
    current_turn: int,
    max_turns: int,
    time_remaining: float,
) -> dict:

  """Call orchestrator with smart token-aware context & hard guardrails"""
  context_mgr = get_context_manager()
  config = get_config()
  model = config.get("agent_model_preferences", {}).get("orchestrator")
  background_enabled = config.get("background_agents_enabled", True)

  context_str, metadata = context_mgr.build_orchestrator_context(
      task_id, user_command, conversation_context, model
  )
  file_count = len(metadata.get("files_included", []))

  # Get feedback backlog count
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
  except Exception:
    total, critical, high, medium, low = 0, 0, 0, 0, 0

  # Check CLI mode
  try:

    from core.cli_modes import CLIMode, get_cli_mode_from_config

    cli_mode = get_cli_mode_from_config(config)
    is_unattended = cli_mode == CLIMode.UNATTENDED
  except Exception:
    is_unattended = False

  # =========================================================================
  # ⚡ PROGRAMMATIC SHORT-CIRCUITS (Avoid API Call for Hard Constraints)
  # =========================================================================

  # Rule A: Cold-start or empty project -> Short-circuit directly to developer
  if file_count == 0 and total == 0:
    print(
        "  ⚡ Short-circuit: Project directory is empty (0 files). Routing"
        " directly to developer."
    )
    return {
        "feedback_summary": (
            "Cold start: No project files exist. Initializing scaffolding."
        ),
        "next_agent": "developer",
        "instructions": (
            f"Initial project setup for task: {user_command}. Create required"
            " source files and scaffolding under project_directory."
        ),
        "reasoning": (
            "Programmatic short-circuit: 0 project files exist; developer must"
            " write initial code before analysis or background review."
        ),
        "files_needed": [],
        "addressing_feedback_ids": [],
        "model": model,
    }

  # =========================================================================
  # 🤖 LLM DECISION PATH
  # =========================================================================
  prompt = f"""{context_str}
**Progress:** Turn {current_turn}/{max_turns} | Time remaining: {time_remaining:.1f}m
**System Flags:** background_agents_enabled={background_enabled} | project_files_count={file_count}

**Current Feedback Backlog:** {total} unaddressed
  - CRITICAL: {critical}
  - HIGH: {high}
  - MEDIUM: {medium}
  - LOW: {low}

What should we do next?

**DECISION RULES:**
1. **If backlog > 0** → Call "developer" to address highest priority feedback item.
2. **If backlog == 0 AND background_agents_enabled is TRUE** → Call "background" to discover new issues.
3. **If backlog == 0 AND background_agents_enabled is FALSE** → Call "developer" to implement/refine task objectives.
4. **Only call "complete"** when backlog is 0, files exist, task is satisfied, and not in unattended mode.

Respond **ONLY** with valid JSON in this exact format:
{{
  "feedback_summary": "Backlog status and next item to address",
  "next_agent": "developer|background|complete",
  "instructions": "Specific instructions for developer agent, referencing task requirements or feedback ID",
  "reasoning": "Why you made this decision",
  "files_needed": ["files to edit/create"],
  "addressing_feedback_ids": [],
  "model": "optional-model-override"
}}"""

  response = call_agent(
      "orchestrator", prompt, task_id, conversation_context, model
  )
  if not response:
    return None

  decision = parse_json_response(
      response,
      expected_keys=["next_agent", "reasoning"],
      strict=False,
      agent_name="orchestrator",
  )

  # Hard enforcement post-check: Overriding 'background' if background agents are disabled
  if (
      not background_enabled
      and decision
      and decision.get("next_agent") == "background"
  ):
    decision["next_agent"] = "developer"
    decision["reasoning"] += " (Overridden: background_agents_enabled is False)"

  return decision
