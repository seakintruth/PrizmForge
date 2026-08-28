"""R2 observability: network failures land in errors with agent_name + model context.

Soak evidence (2026-08-28): all 128 network-error rows had agent_name=NULL,
so the API storm could not be attributed to any one agent.
"""

from __future__ import annotations


def test_log_error_persists_agent_name_and_details(temp_db):
    """The log_error contract: agent_name column + model context in the row."""
    from core.db_connection import get_db_connection
    from file_editing.db import log_error

    log_error(
        component="agents.base",
        category="call_agent",
        severity="HIGH",
        message="reviewer failed to return a response (API/Network error)",
        task_id="t_r2",
        details={
            "prompt_length": 13,
            "model": "mock-model",
            "agent_name": "reviewer",
        },
        agent_name="reviewer",
    )

    with get_db_connection() as conn:
        row = conn.execute("SELECT agent_name, context FROM errors WHERE task_id = 't_r2' ORDER BY id DESC LIMIT 1").fetchone()
    assert row is not None
    assert row[0] == "reviewer"
    assert "mock-model" in (row[1] or "")


def test_call_agent_failure_logs_agent_name_and_model(mock_minimal_config, temp_db, monkeypatch, capsys):
    """End-to-end: a None endpoint response routes through log_error with attribution."""
    from agents.base import call_agent

    monkeypatch.setattr("agents.base.call_endpoint", lambda *a, **k: (None, 0))

    result = call_agent("reviewer", "review please", task_id="t_r2net")

    assert result is None
    out = capsys.readouterr().out
    assert "reviewer failed" in out

    from core.db_connection import get_db_connection

    with get_db_connection() as conn:
        row = conn.execute("SELECT agent_name, context FROM errors WHERE task_id = 't_r2net' ORDER BY id DESC LIMIT 1").fetchone()
    assert row is not None
    assert row[0] == "reviewer"
    assert "prompt_length" in (row[1] or "")
    assert "agent_name" in (row[1] or "")
