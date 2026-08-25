"""BACKLOG_PROCESSING branch must dispatch the developer, not log a stub."""

from unittest.mock import MagicMock

from workflow import task_runner as tr


class _FakeRCDecision:
    level = "BACKLOG_PROCESSING"


class _FakeRC:
    def get_current_decision(self):
        return _FakeRCDecision()


def test_backlog_processing_redirects_to_developer(temp_db, monkeypatch):
    """Orchestrator says background while in BACKLOG_PROCESSING -> developer runs."""
    from core.db_connection import get_db_connection

    with get_db_connection() as conn:
        conn.execute("""
            INSERT INTO agent_feedback
            (agent_name, file_path, priority, category, message, suggestion, task_id, addressed, timestamp)
            VALUES ('jr_reviewer', 'app.py', 'HIGH', 'bug', 'Fix the frobnicator', 'call frob()', 't_bp', 0, datetime('now'))
            """)

    # Deterministic config: legacy developer path, no background agents.
    monkeypatch.setattr(
        tr,
        "get_config",
        lambda: {
            "default_iteration_minutes": 1,
            "min_iterations_before_complete": 1,
            "background_agents_enabled": False,
            "developer": {"implementation": "edit_payload"},
        },
    )
    monkeypatch.setattr(tr, "create_task", lambda *_: None)
    monkeypatch.setattr(tr, "_inject_seed_feedback", lambda *_: None)
    monkeypatch.setattr(tr, "age_feedback_backlog", lambda **k: {})
    # Keep the orchestrator's 'background' decision (no backlog override flip).
    monkeypatch.setattr(tr, "apply_backlog_overrides", lambda _tid, d, _conn: d)

    decisions = iter(
        [
            {"next_agent": "background", "instructions": "", "files_needed": []},
        ]
    )
    monkeypatch.setattr(tr, "call_orchestrator", lambda *a, **k: next(decisions))
    monkeypatch.setattr("agents.resource_controller_worker.get_resource_controller", lambda: _FakeRC())

    developer_mock = MagicMock(return_value={"status": "success"})
    monkeypatch.setattr(tr, "run_developer_mutation", developer_mock)

    tr.run_task_cycle("t_bp", "seed", max_turns=1, time_box_minutes=0)

    assert developer_mock.called, "developer was never dispatched in BACKLOG_PROCESSING mode"
    kwargs = developer_mock.call_args.kwargs
    assert kwargs["decision"].get("addressing_feedback_ids"), "dispatch must reference the feedback item"
