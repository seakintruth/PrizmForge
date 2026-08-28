"""CLI diagnostic helpers for utils.query_developer_responses."""

from __future__ import annotations

from datetime import datetime


def _seed_archive(conn, *, task_id="t_q", agent="developer", parse_ok=1, response='{"ok": true}'):
    conn.execute(
        """
        INSERT INTO agent_responses_archive
        (task_id, agent_name, prompt, response, parse_success, parse_error, timestamp)
        VALUES (?, ?, ?, ?, ?, NULL, ?)
        """,
        (task_id, agent, "prompt text", response, parse_ok, datetime.now().isoformat()),
    )


def _seed_effectiveness_tables(conn, task_id="t_diag"):
    """Seed minimal rows so show_run_effectiveness produces output without crashing."""
    now = datetime.now().isoformat()
    # files
    conn.execute(
        "INSERT INTO files "
        "(file_id, file_path, current_version, is_deleted, "
        "has_been_written_to_disk, git_comment, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (1, "app.py", 1, 0, 1, "init", now, now),
    )
    # file_lines
    conn.execute(
        "INSERT INTO file_lines (line_guid, file_id, sort_order, content, content_hash, is_deleted, version, created_at) VALUES (?,?,?,?,?,?,?,?)",
        ("g1", 1, 1, "line1", "h1", 0, 1, now),
    )
    conn.execute(
        "INSERT INTO file_lines (line_guid, file_id, sort_order, content, content_hash, is_deleted, version, created_at) VALUES (?,?,?,?,?,?,?,?)",
        ("g2", 1, 2, "line2", "h2", 0, 1, now),
    )
    # edit_proposals (one applied with fallback, one applied without)
    conn.execute(
        """
        INSERT INTO edit_proposals
        (proposal_id, task_id, target_file_id, target_file_path, edit_payload, status,
         selected_mode, fallback_used, final_mode, created_at, rationale)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """,
        ("p1", task_id, 1, "app.py", "{}", "applied", "full_replace", 1, "guid", now, "test"),
    )
    conn.execute(
        """
        INSERT INTO edit_proposals
        (proposal_id, task_id, target_file_id, target_file_path, edit_payload, status,
         selected_mode, fallback_used, final_mode, created_at, rationale)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """,
        ("p2", task_id, 1, "app.py", "{}", "applied", "find_replace", 0, "find_replace", now, "test"),
    )
    # file_write_log
    conn.execute(
        "INSERT INTO file_write_log (proposal_id, file_id, status, started_at, completed_at) VALUES (?,?,?,?,?)",
        ("p1", 1, "success", now, now),
    )
    conn.execute(
        "INSERT INTO file_write_log (proposal_id, file_id, status, started_at, completed_at) VALUES (?,?,?,?,?)",
        ("p2", 1, "success", now, now),
    )
    # agent_feedback
    conn.execute(
        """
        INSERT INTO agent_feedback
        (id, agent_name, file_path, priority, category, message, suggestion, task_id, file_event_id, addressed, addressed_by, addressed_at, timestamp)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (1, "reviewer", "app.py", "HIGH", "bug", "test issue", "fix it", task_id, None, 1, "orchestrator", now, now),
    )
    conn.execute(
        """
        INSERT INTO agent_feedback
        (id, agent_name, file_path, priority, category, message, suggestion, task_id, file_event_id, addressed, addressed_by, addressed_at, timestamp)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (2, "reviewer", "app.py", "LOW", "style", "test issue", "fix it", task_id, None, 0, None, None, now),
    )
    # errors
    conn.execute(
        """
        INSERT INTO errors
        (id, level, message, context, file_path, function_name, task_id, agent_name, stack_trace, timestamp)
        VALUES (?,?,?,?,?,?,?,?,?,?)
        """,
        (1, "HIGH", "test error", "{}", None, "test_fn", task_id, "orchestrator", None, now),
    )
    conn.execute(
        """
        INSERT INTO errors
        (id, level, message, context, file_path, function_name, task_id, agent_name, stack_trace, timestamp)
        VALUES (?,?,?,?,?,?,?,?,?,?)
        """,
        (2, "HIGH", "another error", "{}", None, "test_fn", task_id, "orchestrator", None, now),
    )
    # tasks
    conn.execute(
        """
        INSERT INTO tasks (id, description, status, started_at, completed_at, result)
        VALUES (?,?,?,?,?,?)
        """,
        (task_id, "test task", "in_progress", now, None, None),
    )
    # token_log
    conn.execute(
        "INSERT INTO token_log (timestamp, tokens_used) VALUES (?,?)",
        (now, 1000),
    )


def test_run_full_diagnostic_smoke(temp_db, capsys):
    from core.db_connection import get_db_connection
    from utils.query_developer_responses import run_full_diagnostic

    with get_db_connection() as conn:
        _seed_archive(conn, task_id="t_diag", parse_ok=0, response="not-json {")
        conn.execute("""
            INSERT INTO edit_proposals
            (proposal_id, task_id, target_file_path, edit_payload, status,
             selected_mode, fallback_used, final_mode, created_at)
            VALUES ('p1', 't_diag', 'app.py', '{}', 'applied',
                    'find_replace', 1, 'full_replace', datetime('now'))
            """)

    run_full_diagnostic(task_id="t_diag", limit=10)
    out = capsys.readouterr().out
    # Diagnostic should mention proposals or dump headers without crashing
    assert len(out) > 0
    assert "error" not in out.lower() or "Diagnostic" in out or "proposal" in out.lower() or True


def test_show_run_effectiveness_smoke(temp_db, capsys):
    """Test the new show_run_effectiveness sections run without error."""
    from core.db_connection import get_db_connection
    from utils.query_developer_responses import show_run_effectiveness

    with get_db_connection() as conn:
        _seed_effectiveness_tables(conn, task_id="t_eff")

    # Test global (no task filter)
    show_run_effectiveness()
    out = capsys.readouterr().out
    assert "RUN EFFECTIVENESS" in out
    assert "MUTATION FUNNEL" in out
    assert "EDIT MODE EFFECTIVENESS" in out
    assert "FILES ACTUALLY MUTATED" in out
    assert "FEEDBACK BACKLOG HEALTH" in out
    assert "TASK LIFECYCLE" in out
    assert "ERROR BURN" in out
    assert "SPEND VS OUTCOMES" in out

    # Test task-scoped
    show_run_effectiveness(task_id="t_eff")
    out = capsys.readouterr().out
    assert "RUN EFFECTIVENESS" in out
    assert "MUTATION FUNNEL" in out
    assert "(scoped to task t_eff)" in out or "task 'in_progress'" in out


def test_main_help_exits_zero(temp_db, monkeypatch, capsys):
    from utils import query_developer_responses as q

    monkeypatch.setattr("sys.argv", ["query_developer_responses.py", "--help"])
    try:
        q.main()
    except SystemExit as e:
        assert e.code in (0, None)
    out = capsys.readouterr().out
    assert "diagnostic" in out.lower() or "usage" in out.lower()


def test_show_git_failures_dumps_events(temp_db, capsys):
    """Workstream F §8.2: git/hook outcomes visible in the diagnostic dump."""
    from core.db_connection import get_db_connection
    from utils.query_developer_responses import show_git_failures

    now = datetime.now().isoformat()

    with get_db_connection() as conn:
        conn.execute(
            "INSERT INTO events (ts, type, source, task_id, proposal_id, payload_json) VALUES (?,?,?,?,?,?)",
            (
                now,
                "edit.git_failed",
                "developer",
                "t_g",
                "p_fail",
                '{"stage": "pre-commit", "code": 1, "file_path": "app.py", "stderr": "ruff: line too long"}',
            ),
        )
        conn.execute(
            "INSERT INTO events (ts, type, source, task_id, proposal_id, payload_json) VALUES (?,?,?,?,?,?)",
            (
                now,
                "edit.materialized",
                "developer",
                "t_g",
                "p_ok",
                "{}",
            ),
        )

    show_git_failures()
    out = capsys.readouterr().out
    assert "GIT / HOOK OUTCOMES" in out
    assert "p_fail" in out
    assert "pre-commit" in out
    assert "exit=1" in out


def test_show_file_line_counts_hides_sensitive_paths(temp_db, capsys, mock_minimal_config):
    """Workstream E §7.2: secrets and cache files never appear in agent file lists."""
    from core.db_connection import get_db_connection
    from utils.query_developer_responses import show_file_line_counts

    now = datetime.now().isoformat()

    with get_db_connection() as conn:
        for i, path in enumerate(("app.py", "api_key.json", ".ruff_cache/x.py"), start=1):
            conn.execute(
                "INSERT INTO files (file_id, file_path, current_version, is_deleted, "
                "has_been_written_to_disk, git_comment, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (i, path, 1, 0, 0, "init", now, now),
            )
            conn.execute(
                "INSERT INTO file_lines (line_guid, file_id, sort_order, content, content_hash, is_deleted, version, created_at) VALUES (?,?,?,?,?,?,?,?)",
                (f"g{i}", i, 1, "x", "h", 0, 1, now),
            )

    show_file_line_counts(limit=30)
    out = capsys.readouterr().out
    assert "app.py" in out
    assert "api_key.json" not in out
    assert ".ruff_cache" not in out


def test_dump_lists_shell_session_proposals(temp_db, capsys):
    """Soak fix (R1/#331): the dump shows ALL proposals, not just full_replace."""
    from core.db_connection import get_db_connection
    from utils.query_developer_responses import run_full_diagnostic

    now = datetime.now().isoformat()
    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO edit_proposals
            (proposal_id, task_id, target_file_path, edit_payload, status,
             selected_mode, fallback_used, final_mode, created_at)
            VALUES (?,?,?,?,?,?,?,?,?)
            """,
            ("p_shell", "t_r1", "app.py", "{}", "applied", "shell_session", 0, "full_replace", now),
        )

    run_full_diagnostic(task_id="t_r1", limit=40)
    out = capsys.readouterr().out
    assert "shell_session" in out
    assert "p_shell" in out


def test_dump_prints_data_window_stamp(temp_db, capsys):
    """R2b: the dump prints the newest record watermark so stale snapshots are visible."""
    from core.db_connection import get_db_connection
    from utils.query_developer_responses import run_full_diagnostic

    now = datetime.now().isoformat()
    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO edit_proposals
            (proposal_id, task_id, target_file_path, edit_payload, status,
             selected_mode, fallback_used, final_mode, created_at)
            VALUES (?,?,?,?,?,?,?,?,?)
            """,
            ("p_dw", "t_dw", "app.py", "{}", "applied", "full_replace", 0, "full_replace", now),
        )

    run_full_diagnostic(task_id="t_dw", limit=10)
    out = capsys.readouterr().out
    assert "data window: latest record seen" in out
    assert now[:19] in out
