"""Context archival helpers"""

from datetime import datetime

from core.db_connection import get_db_connection


def archive_raw_response(
    task_id: str,
    agent_name: str,
    prompt: str,
    response: str,
    parse_success: bool,
    parse_error: str | None = None,
    *,
    model: str | None = None,
    step_number: int | None = None,
    response_format_status: str | None = None,
    command: str | None = None,
    command_exit_code: int | None = None,
):
    """Archive raw agent response for debugging.

    ``model``/``step_number``/``response_format_status``/``command``/
    ``command_exit_code`` support Pass 1 shell observability (Phase 3.1) and
    default to NULL for callers that do not supply them.
    """
    try:
        with get_db_connection() as conn:
            conn.execute(
                """
                INSERT INTO agent_responses_archive
                (task_id, agent_name, prompt, response, parse_success, parse_error,
                 timestamp, model, step_number, response_format_status, command,
                 command_exit_code)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    task_id,
                    agent_name,
                    prompt,
                    response,
                    1 if parse_success else 0,
                    parse_error,
                    datetime.now().isoformat(),
                    model,
                    step_number,
                    response_format_status,
                    command,
                    command_exit_code,
                ),
            )
    except Exception as e:
        print(f"⚠️  Failed to archive response: {e}")
