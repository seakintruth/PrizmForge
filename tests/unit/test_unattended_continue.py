"""Unattended continue gates and next-task generation."""

from __future__ import annotations

from datetime import datetime, timedelta

from core.cli_modes import CLIMode, CLIState, UnattendedConfig
from interactive import generate_next_task, should_continue_unattended


def test_stops_when_duration_exceeded():
    state = CLIState(mode=CLIMode.UNATTENDED, start_time=datetime.now() - timedelta(hours=3))
    cfg = UnattendedConfig(max_duration_hours=2.0)
    assert should_continue_unattended(state, cfg) is False


def test_continues_within_duration():
    state = CLIState(mode=CLIMode.UNATTENDED, start_time=datetime.now())
    cfg = UnattendedConfig(max_duration_hours=5.0)
    assert should_continue_unattended(state, cfg) is True


def test_stops_when_seed_queue_empty_and_no_autogen():
    state = CLIState(mode=CLIMode.UNATTENDED, start_time=datetime.now(), total_iterations=1)
    cfg = UnattendedConfig(auto_generate_tasks=False, _seed_queue=[])
    assert should_continue_unattended(state, cfg) is False


def test_stops_when_backlog_empty_flag(temp_db):
    state = CLIState(mode=CLIMode.UNATTENDED, start_time=datetime.now(), total_iterations=2)
    cfg = UnattendedConfig(stop_when_backlog_empty=True, max_duration_hours=10.0)
    # No unaddressed feedback rows → stop
    assert should_continue_unattended(state, cfg) is False


def test_continues_when_backlog_has_items(temp_db):
    from core.db_helpers import save_agent_feedback

    save_agent_feedback(
        agent_name="jr_reviewer",
        file_path="a.py",
        priority="HIGH",
        category="bug",
        message="real issue about missing timeout",
        suggestion=None,
        task_id="t1",
        file_event_id="e1",
    )
    state = CLIState(mode=CLIMode.UNATTENDED, start_time=datetime.now(), total_iterations=1)
    cfg = UnattendedConfig(stop_when_backlog_empty=True, max_duration_hours=10.0)
    assert should_continue_unattended(state, cfg) is True


def test_generate_next_task_pops_seed_queue():
    state = CLIState(mode=CLIMode.UNATTENDED, start_time=datetime.now())
    cfg = UnattendedConfig(_seed_queue=["seed A", "seed B"], auto_generate_tasks=False)
    assert generate_next_task(state, cfg) == "seed A"
    assert generate_next_task(state, cfg) == "seed B"
    assert cfg._seed_queue == []


def test_generate_next_task_prioritizes_critical_feedback(temp_db):
    from core.db_helpers import save_agent_feedback

    save_agent_feedback(
        agent_name="security_reviewer",
        file_path="auth.py",
        priority="CRITICAL",
        category="security",
        message="SQL injection risk in query builder",
        suggestion="parameterize",
        task_id="t1",
        file_event_id="e1",
    )
    state = CLIState(mode=CLIMode.UNATTENDED, start_time=datetime.now())
    cfg = UnattendedConfig(
        _seed_queue=[],
        auto_generate_tasks=True,
        prioritize_critical_issues=True,
    )
    task = generate_next_task(state, cfg)
    assert "CRITICAL" in task or "security" in task.lower()
