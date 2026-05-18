# agents/orchestrator.py

from agents.base import call_agent
from core.context_manager import get_context_manager 
from core.config import get_config
from core.json_parser import parse_json_response


def call_orchestrator(task_id: str, user_command: str, conversation_context: list,
                     current_turn: int, max_turns: int, time_remaining: float) -> dict:
    """Call orchestrator with smart token-aware context"""
    
    context_mgr = get_context_manager()
    
    config = get_config()
    model = config.get("agent_model_preferences", {}).get("orchestrator")
    
    context_str, metadata = context_mgr.build_orchestrator_context(
        task_id, user_command, conversation_context, model
    )
    
    utilization = metadata['context_utilization']
    utilization_color = "🟢" if utilization < 0.5 else "🟡" if utilization < 0.8 else "🔴"
    
    print(f"  {utilization_color} Context: {metadata['tokens_used']:,} / {metadata['context_limit']:,} tokens "
          f"({utilization:.1%} utilization)")
    print(f"     Files: {len(metadata['files_included'])} included")
    
    if metadata['files_excluded']:
        print(f"     ⚠️  {len(metadata['files_excluded'])} files excluded - {metadata['truncation_reason']}")
    
    prompt = f"""{context_str}

**Progress:** Turn {current_turn}/{max_turns} | Time remaining: {time_remaining:.1f}m

What should we do next?

**Important Rules:**
- You should **only** call `developer` when there is actionable work from the message bus or proposals.
- You should **never** directly call `reviewer` or `researcher`. These now run as background agents.
- If there is no clear high-priority work from the message bus or pending proposals, return `"next_agent": "background"` so background agents can continue their work.

Respond **ONLY** with valid JSON in this exact format:
{{
  "feedback_summary": "Brief summary of current state and prioritized items",
  "next_agent": "developer|background|complete",
  "instructions": "Clear instructions (only used when calling developer)",
  "reasoning": "Why you made this decision",
  "files_needed": ["optional list of files"],
  "addressing_feedback_ids": [123, 456],
  "model": "optional-model-override"
}}"""

    response = call_agent("orchestrator", prompt, task_id, conversation_context, model)
    
    if not response:
        return None
    
    decision = parse_json_response(
        response,
        expected_keys=["next_agent", "reasoning"],
        strict=False,
        agent_name="orchestrator"
    )
    
    return decision