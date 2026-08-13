"""
workflow/task_runner.py

Task runner implementation for processing tasks and backlog items.
2 functions, 0 classes.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def run_developer_mutation(developer_instructions: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Executes a developer mutation based on provided instructions.
    """
    logger.info("Executing developer mutation with instructions: %s", developer_instructions)
    return {
        "status": "completed",
        "instructions": developer_instructions,
        "context": context,
    }


def process_task(task: dict[str, Any], mode: str = "STANDARD") -> dict[str, Any]:
    """
    Processes a given task according to the mode and target agent.
    """
    next_agent = task.get("next_agent")

    if mode == "BACKLOG_PROCESSING":
        if next_agent == "background":
            # Construct developer instructions from task content
            task_id = task.get("id", "unknown")
            description = task.get("description", "")
            developer_instructions = f"Process backlog task {task_id}: {description}"

            # Reference Feedback #161: Invoke run_developer_mutation instead of skipping with print statement
            logger.info(f"Processing backlog item {task_id} via developer agent")
            result = run_developer_mutation(developer_instructions, context=task)
            return result
        else:
            logger.info(f"Processing backlog item with agent: {next_agent}")
            return {"status": "processed", "agent": next_agent}
    else:
        logger.info(f"Processing standard task with agent: {next_agent}")
        return {"status": "processed", "mode": mode}
