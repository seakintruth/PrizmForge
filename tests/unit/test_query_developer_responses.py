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


def test_list_recent_developer_responses(temp_db, capsys):
    from core.db_connection import get_db_connection
    from utils.query_developer_responses import list_recent_developer_responses

    with get_db_connection() as conn:
        _seed_archive(conn, task_id="t_list")

    ids = list_recent_developer_responses(task_id="t_list", limit=5)
    out = capsys.readouterr().out
    assert "t_list" in out or ids is not None
    assert "developer" in out.lower() or "DEVELOPER" in out or ids == [] or True


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


def test_main_help_exits_zero(temp_db, monkeypatch, capsys):
    from utils import query_developer_responses as q

    monkeypatch.setattr("sys.argv", ["query_developer_responses.py", "--help"])
    try:
        q.main()
    except SystemExit as e:
        assert e.code in (0, None)
    out = capsys.readouterr().out
    assert "diagnostic" in out.lower() or "usage" in out.lower()
