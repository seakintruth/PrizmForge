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
        row = conn.execute(
            """
            SELECT agent_name, parse_success, parse_error, response
            FROM agent_responses_archive
            WHERE task_id = 't_arc'
            """
        ).fetchone()
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
        row = conn.execute(
            "SELECT parse_success, parse_error FROM agent_responses_archive WHERE task_id = 't_fail'"
        ).fetchone()
    assert row[0] == 0
    assert row[1] == "JSONDecodeError"
