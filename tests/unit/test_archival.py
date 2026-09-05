"""Raw response archival helper."""

from __future__ import annotations


def test_archive_raw_response_success(temp_db):
    from core.archival import archive_raw_response
    from core.db_connection import get_db_connection

    archive_raw_response(
        task_id="t_arc",
        agent_name="developer",
        prompt="do the thing",
        response='{"operations": []}',
        parse_success=True,
    )
    with get_db_connection() as conn:
        row = conn.execute("""
            SELECT agent_name, parse_success, parse_error, response
            FROM agent_responses_archive
            WHERE task_id = 't_arc'
            """).fetchone()
    assert row is not None
    assert row[0] == "developer"
    assert row[1] == 1
    assert row[2] is None
    assert "operations" in row[3]


def test_archive_raw_response_parse_failure(temp_db):
    from core.archival import archive_raw_response
    from core.db_connection import get_db_connection

    archive_raw_response(
        task_id="t_fail",
        agent_name="orchestrator",
        prompt="decide",
        response="not json",
        parse_success=False,
        parse_error="JSONDecodeError",
    )
    with get_db_connection() as conn:
        row = conn.execute("SELECT parse_success, parse_error FROM agent_responses_archive WHERE task_id = 't_fail'").fetchone()
    assert row[0] == 0
    assert row[1] == "JSONDecodeError"


def test_archive_raw_response_shell_step_columns(temp_db):
    """Pass 1 Phase 3.1: shell observability columns persist per developer step."""
    from core.archival import archive_raw_response
    from core.db_connection import get_db_connection

    archive_raw_response(
        task_id="t_shell",
        agent_name="developer",
        prompt="workspace evidence",
        response="```bash\necho hi\n```",
        parse_success=True,
        model="mock-model",
        step_number=1,
        response_format_status="VALID_BASH_BLOCK",
        command="echo hi",
        command_exit_code=0,
    )
    with get_db_connection() as conn:
        row = conn.execute("""
            SELECT model, step_number, response_format_status, command, command_exit_code
            FROM agent_responses_archive
            WHERE task_id = 't_shell'
            """).fetchone()
    assert row == ("mock-model", 1, "VALID_BASH_BLOCK", "echo hi", 0)


def test_archive_raw_response_old_schema_migrated(temp_db):
    """A DB created before the new columns must still insert after migration."""
    from core.archival import archive_raw_response
    from core.db_connection import get_db_connection

    archive_raw_response(
        task_id="t_legacy_schema",
        agent_name="developer",
        prompt="old",
        response="old response",
        parse_success=True,
    )
    with get_db_connection() as conn:
        row = conn.execute("SELECT model, step_number FROM agent_responses_archive WHERE task_id = 't_legacy_schema'").fetchone()
    assert row == (None, None)
