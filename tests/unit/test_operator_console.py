"""Operator console substrate (Part 1) + tier-agnostic hardening (Part 2).

Covers:
- core/operator_view.py read-only read model (snapshot, task_trace,
  developer_session_live in-flight detection, feedback_backlog)
- shell heartbeat events (shell_turn_start / shell_model_call_started /
  shell_command_executed / shell_spinning) written by the run loop
- context_manager rendering never showing "in `None`" and de-aliasing
  seed_task rows
- _inject_seed_feedback attaching docs/TODO.md for discovery seeds
- no_progress_stall_limit terminating novel-no-change loops (Soak18 gap)
"""

from __future__ import annotations

import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

from core import operator_view as ov
from workflow import shell_developer as sd

FINISH = sd.FINISH_TOKEN


# ---------------------------------------------------------------------------
# Real-session harness (mirrors test_shell_developer_feed_fixes.py)
# ---------------------------------------------------------------------------
def _repo(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=str(root), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=str(root), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=str(root), check=True, capture_output=True)
    wf = root / "workflow"
    wf.mkdir()
    (wf / "__init__.py").write_text("# marker\n")
    (root / "app.py").write_text("def greet():\n    return 'old'\n")
    subprocess.run(["git", "add", "-A"], cwd=str(root), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=str(root), check=True, capture_output=True)
    return root


def _real_session(root: Path, script: list[str], task_id: str = "T-operator", **cfg):
    wt = sd.ShellWorktree(root, parent_dir=str(root.parent))
    wt.create()
    session = sd.ShellDeveloperSession(
        sd.ShellDeveloperConfig(
            step_limit=cfg.pop("step_limit", 8),
            max_consecutive_format_errors=cfg.pop("max_consecutive_format_errors", 3),
            **cfg,
        ),
        worktree=wt,
        task_id=task_id,
    )
    state = {"i": 0}

    def fake_llm(self):
        if state["i"] >= len(script):
            return None
        text = script[state["i"]]
        state["i"] += 1
        return text

    session._llm = fake_llm.__get__(session, type(session))
    return session, wt, state


# ---------------------------------------------------------------------------
# operator_view read model
# ---------------------------------------------------------------------------
def test_snapshot_reads_tasks_backlog_endpoints_spend(temp_db):
    from core.db_connection import get_db_connection

    with get_db_connection() as conn:
        conn.execute("INSERT INTO tasks (id, description, status, started_at) VALUES ('ta', 'd', 'in_progress', '2026-01-01T00:00:00')")
        conn.execute(
            "INSERT INTO agent_feedback (agent_name, file_path, priority, category, message, addressed, task_id) "
            "VALUES ('system', NULL, 'HIGH', 'seed_task', 'review plans', 0, 'ta')"
        )
        conn.execute("INSERT INTO endpoint_health (endpoint_name, status, consecutive_failures) VALUES ('ep1', 'misconfigured', 3)")
        conn.execute("INSERT INTO token_log (timestamp, tokens_used, endpoint_name) VALUES ('2026-01-01T00:00:00', 500, 'ep1')")
        conn.execute(
            "INSERT INTO model_health_events (ts, model_ref, endpoint, ok, latency_ms, kind) VALUES ('2026-01-01T00:00:00', 'm', 'ep1', 1, 150, 'ok')"
        )

    snap = ov.snapshot(db_path=temp_db)
    assert snap["tasks"][0]["id"] == "ta"
    assert snap["backlog"] == {"open": 1, "high": 1, "stuck": 0}
    assert snap["endpoints"][0]["endpoint_name"] == "ep1"
    assert snap["endpoints"][0]["status"] == "misconfigured"
    assert snap["spend"]["total_tokens"] == 500
    assert snap["health"]["calls"] == 1
    assert snap["health"]["ok"] == 1


def test_snapshot_tolerates_missing_token_columns(temp_db):
    from core.db_connection import get_db_connection

    with get_db_connection() as conn:
        conn.execute("INSERT INTO endpoint_health (endpoint_name, status) VALUES ('ep1', 'available')")
    snap = ov.snapshot(db_path=temp_db)
    assert snap["endpoints"][0]["endpoint_name"] == "ep1"
    assert snap["endpoints"][0]["tokens_per_minute"] is None


def test_snapshot_spend_window_counts_recent_tokens(temp_db):
    """Soak22: window cutoff must be now - window, counted in naive-local."""
    from core.db_connection import get_db_connection

    now = datetime.now(timezone.utc)
    recent = (datetime.now() - timedelta(hours=1)).isoformat()
    old = (datetime.now() - timedelta(hours=5)).isoformat()
    future = (datetime.now() + timedelta(hours=1)).isoformat()
    with get_db_connection() as conn:
        conn.execute("INSERT INTO token_log (timestamp, tokens_used) VALUES (?, 500)", (recent,))
        conn.execute("INSERT INTO token_log (timestamp, tokens_used) VALUES (?, 700)", (old,))
        conn.execute("INSERT INTO token_log (timestamp, tokens_used) VALUES (?, 300)", (future,))

    snap = ov.snapshot(db_path=temp_db, now=now)
    # recent (1h ago) + future (1h ahead) are both >= cutoff → counted; the 5h
    # row is the only one excluded. Pre-fix (cutoff = now) counted only the
    # future row (300), so 800 proves the cutoff no longer points at `now`.
    assert snap["spend"]["window_tokens"] == 800
    assert snap["spend"]["total_tokens"] == 1500


def test_snapshot_latch_countdown_is_remaining_not_age(temp_db):
    """Soak22: unavailable_in_s = seconds until unlatched (not seconds since)."""
    from core.db_connection import get_db_connection

    now = datetime.now(timezone.utc)
    in_future = (datetime.now() + timedelta(seconds=300)).isoformat()
    expired = (datetime.now() - timedelta(seconds=60)).isoformat()
    with get_db_connection() as conn:
        conn.execute(
            "INSERT INTO endpoint_health (endpoint_name, status, unavailable_until) VALUES ('ep1', 'rate_limited', ?)",
            (in_future,),
        )
        conn.execute(
            "INSERT INTO endpoint_health (endpoint_name, status, unavailable_until) VALUES ('ep2', 'rate_limited', ?)",
            (expired,),
        )

    snap = ov.snapshot(db_path=temp_db, now=now)
    by_name = {e["endpoint_name"]: e for e in snap["endpoints"]}
    assert 0 < by_name["ep1"]["unavailable_in_s"] <= 300
    assert by_name["ep2"]["unavailable_in_s"] == 0


def test_task_trace_returns_steps_and_events(temp_db):
    from core.db_connection import get_db_connection

    with get_db_connection() as conn:
        conn.execute("INSERT INTO tasks (id, description, status) VALUES ('tb', 'd', 'in_progress')")
        conn.execute(
            "INSERT INTO agent_responses_archive (task_id, agent_name, prompt, response, parse_success, step_number, timestamp) "
            "VALUES ('tb', 'developer', 'p', 'r', 1, 1, '2026-01-01T00:00:00')"
        )
        conn.execute(
            "INSERT INTO events (task_id, ts, type, source, payload_json) "
            "VALUES ('tb', '2026-01-01T00:00:01', 'shell_command_executed', 'developer', '{\"exit_code\": 0}')"
        )
    trace = ov.task_trace("tb", db_path=temp_db)
    assert len(trace["steps"]) == 1
    assert trace["steps"][0]["step_number"] == 1
    assert trace["events"][0]["type"] == "shell_command_executed"
    assert trace["events"][0]["payload"] == {"exit_code": 0}
    assert trace["task"]["status"] == "in_progress"


def test_developer_session_live_in_flight_detection(temp_db):
    from core.db_connection import get_db_connection

    old = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    fresh = datetime.now(timezone.utc).isoformat()
    with get_db_connection() as conn:
        conn.execute(
            "INSERT INTO agent_responses_archive (task_id, agent_name, prompt, response, parse_success, "
            "command, command_exit_code, step_number, timestamp) "
            "VALUES ('tc', 'developer', 'p', 'r', 1, 'cat app.py', 0, 1, ?)",
            (old,),
        )
        conn.execute(
            "INSERT INTO events (task_id, ts, type, source, payload_json) VALUES ('tc', ?, 'shell_model_call_started', 'developer', '{\"step_number\": 2}')",
            (fresh,),
        )
    live = ov.developer_session_live("tc", db_path=temp_db)
    assert live["in_flight"] is True
    assert live["in_flight_s"] is not None
    assert live["last_command"] == "cat app.py"

    # A completed command after the marker supersedes the in-flight state.
    after = datetime.now(timezone.utc).isoformat()
    with get_db_connection() as conn:
        conn.execute(
            "INSERT INTO events (task_id, ts, type, source, payload_json) VALUES ('tc', ?, 'shell_command_executed', 'developer', '{\"exit_code\": 0}')",
            (after,),
        )
    live2 = ov.developer_session_live("tc", db_path=temp_db)
    assert live2["in_flight"] is False


def test_feedback_backlog_filters_open_items_by_task(temp_db):
    from core.db_connection import get_db_connection

    with get_db_connection() as conn:
        conn.execute(
            "INSERT INTO agent_feedback (id, agent_name, priority, category, message, addressed, task_id, stuck) "
            "VALUES (1, 'system', 'HIGH', 'seed_task', 'open', 0, 'td', 0)"
        )
        conn.execute(
            "INSERT INTO agent_feedback (id, agent_name, priority, category, message, addressed, task_id, stuck) "
            "VALUES (2, 'system', 'LOW', 'x', 'addressed', 1, 'td', 0)"
        )
        conn.execute(
            "INSERT INTO agent_feedback (id, agent_name, priority, category, message, addressed, task_id, stuck) "
            "VALUES (3, 'system', 'HIGH', 'y', 'other', 0, 'te', 0)"
        )
    rows = ov.feedback_backlog("td", db_path=temp_db)
    assert [r["id"] for r in rows] == [1]
    assert ov.feedback_backlog(db_path=temp_db) and len(ov.feedback_backlog(db_path=temp_db)) == 2


# ---------------------------------------------------------------------------
# Heartbeat events from the shell run loop
# ---------------------------------------------------------------------------
def test_run_loop_publishes_heartbeat_events(temp_db):
    root = _repo(Path(temp_db).parent / "op-repo")
    session, wt, _state = _real_session(
        root,
        ["```bash\necho hi\n```", f"{FINISH}\nDone"],
        task_id="T-heartbeat",
    )
    try:
        result = session.run("Say hi")
        assert result.exit_status == "Finished"
    finally:
        wt.cleanup()

    from core.db_connection import get_db_connection

    with get_db_connection() as conn:
        types = [r[0] for r in conn.execute("SELECT type FROM events WHERE task_id = 'T-heartbeat' ORDER BY id").fetchall()]
    assert "shell_turn_start" in types
    assert "shell_model_call_started" in types
    assert "shell_command_executed" in types


def test_no_progress_loop_emits_shell_spinning_event(temp_db):
    root = _repo(Path(temp_db).parent / "np-repo")
    cmds = ["echo a", "echo b", "echo c"]
    session, wt, _state = _real_session(
        root,
        [f"```bash\n{c}\n```" for c in cmds],
        task_id="T-noprogress",
        no_progress_stall_limit=3,
        no_change_stall_limit=6,
        step_limit=10,
    )
    try:
        result = session.run("Inspect app.py")
        # Soak18 gap closed: novel successful no-change steps now hit the
        # no-progress tripwire instead of burning to the step limit.
        assert result.exit_status == "NoProgress"
        assert result.n_model_calls <= 3
        assert "no_progress_stall_limit" in result.summary
    finally:
        wt.cleanup()

    from core.db_connection import get_db_connection

    with get_db_connection() as conn:
        types = [r[0] for r in conn.execute("SELECT type FROM events WHERE task_id = 'T-noprogress' ORDER BY id").fetchall()]
    assert "shell_spinning" in types
    assert "shell_turn_start" in types
    assert "shell_command_executed" in types


# ---------------------------------------------------------------------------
# context_manager: never render "in `None`"; de-alias seed_task rows
# ---------------------------------------------------------------------------
def test_context_manager_seed_task_never_renders_in_none(temp_db):
    from core.context_manager import ContextManager
    from core.db_connection import get_db_connection

    with get_db_connection() as conn:
        conn.execute(
            "INSERT INTO agent_feedback (id, agent_name, file_path, priority, category, message, suggestion, addressed, task_id) "
            "VALUES (1, 'system', NULL, 'HIGH', 'seed_task', 'Review the plans and ideas', NULL, 0, 't_cx')"
        )
        conn.execute(
            "INSERT INTO agent_feedback (id, agent_name, file_path, priority, category, message, suggestion, addressed, task_id) "
            "VALUES (2, 'system', NULL, 'MEDIUM', 'reviewer', 'Plain finding without a file', NULL, 0, 't_cx')"
        )
        conn.execute(
            "INSERT INTO agent_feedback (id, agent_name, file_path, priority, category, message, suggestion, addressed, task_id) "
            "VALUES (3, 'system', 'docs/TODO.md', 'LOW', 'reviewer', 'Targeted finding', NULL, 0, 't_cx')"
        )

    text = ContextManager()._get_prioritized_suggestions("t_cx")
    assert text is not None
    assert "`None`" not in text
    assert "seed task" in text
    assert "docs/TODO.md" in text
    # The category token must not appear as a phantom code-fix noun.
    assert not any(" seed_task " in t for t in text.splitlines() if t.strip().startswith("1. "))
    assert "Plain finding without a file" in text
    assert "(ID: 1)" in text


# ---------------------------------------------------------------------------
# _inject_seed_feedback: attach docs file_path for discovery seeds
# ---------------------------------------------------------------------------
def test_inject_seed_feedback_attaches_discovery_doc(tmp_path, monkeypatch, temp_db):
    project = tmp_path / "project"
    docs = project / "docs"
    docs.mkdir(parents=True)
    (docs / "TODO.md").write_text("# TODO\n- fix things\n")
    monkeypatch.setattr("workflow.task_runner.get_config", lambda: {"project_directory": str(project)})

    from core.db_connection import get_db_connection
    from workflow.task_runner import _inject_seed_feedback

    with get_db_connection() as conn:
        conn.execute("DELETE FROM agent_feedback")

    _inject_seed_feedback("t_seed1", "Review the repository's plans, ideas and todos")
    with get_db_connection() as conn:
        row = conn.execute("SELECT file_path, category, message FROM agent_feedback WHERE task_id = 't_seed1'").fetchone()
        assert row[0] == "docs/TODO.md"
        assert row[1] == "seed_task"

    # A targeted non-discovery seed must stay untargeted (no docs override).
    _inject_seed_feedback("t_seed2", "Implement the paginator in app.py")
    with get_db_connection() as conn:
        row = conn.execute("SELECT file_path FROM agent_feedback WHERE task_id = 't_seed2'").fetchone()
        assert row[0] is None

    # Idempotent per task: the second call must not overwrite file_path.
    _inject_seed_feedback("t_seed1", "Review the plans, ideas and todos")
    with get_db_connection() as conn:
        row = conn.execute("SELECT COUNT(*) AS n, MAX(file_path) AS fp FROM agent_feedback WHERE task_id = 't_seed1'").fetchone()
        assert row[0] == 1
        assert row[1] == "docs/TODO.md"


def test_inject_seed_feedback_no_docs_stays_null(tmp_path, monkeypatch, temp_db):
    project = tmp_path / "empty"
    project.mkdir(parents=True)
    monkeypatch.setattr("workflow.task_runner.get_config", lambda: {"project_directory": str(project)})

    from core.db_connection import get_db_connection
    from workflow.task_runner import _inject_seed_feedback

    with get_db_connection() as conn:
        conn.execute("DELETE FROM agent_feedback")

    _inject_seed_feedback("t_seed3", "Review the plans, ideas and todos")
    with get_db_connection() as conn:
        row = conn.execute("SELECT file_path FROM agent_feedback WHERE task_id = 't_seed3'").fetchone()
        assert row[0] is None


# ---------------------------------------------------------------------------
# no_progress_stall_limit config surface
# ---------------------------------------------------------------------------
def test_no_progress_stall_limit_config_parse(tmp_path, monkeypatch):
    cfg = sd.ShellDeveloperConfig.from_config()
    assert cfg.no_progress_stall_limit == 10

    monkeypatch.setattr(
        "workflow.shell_developer.get_config",
        lambda: {"shell_developer": {"no_progress_stall_limit": 4}},
    )
    cfg2 = sd.ShellDeveloperConfig.from_config()
    assert cfg2.no_progress_stall_limit == 4
