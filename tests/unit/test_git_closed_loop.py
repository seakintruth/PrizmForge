"""Tests for Workstream A Phase 1: git/pre-commit closed loop.

The loop is closed only when a failed hook:
  - makes materialize return a non-success status ("git_failed")
  - emits edit.git_failed and never edit.materialized
  - writes one CRITICAL agent_feedback row (deduped by proposal_id)
  - writes an errors row with a truncated hook excerpt
  - leaves addressing_feedback_ids unaddressed

These tests drive the real caller paths (_gate_and_materialize and
run_developer_mutation) with a mocked git_commit failure; the return-toggle
tests lock the writer status semantics.
"""

from __future__ import annotations

import json

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _git_failure_result(stderr="pre-commit hook failed\nruff: E501", file_path="pkg/app.py"):
    return {
        "ok": False,
        "attempted": True,
        "code": 1,
        "stage": "commit",
        "stdout": "",
        "stderr": stderr,
        "file_path": file_path,
        "commit_hash": None,
    }


def _git_success_result(file_path="pkg/app.py"):
    return {
        "ok": True,
        "attempted": True,
        "code": 0,
        "stage": "commit",
        "stdout": "",
        "stderr": "",
        "file_path": file_path,
        "commit_hash": "abc1234",
    }


def _event_rows(conn, event_type, proposal_id=None):
    if proposal_id is None:
        return conn.execute(
            "SELECT type, proposal_id, payload_json FROM events WHERE type = ? ORDER BY id",
            (event_type,),
        ).fetchall()
    return conn.execute(
        "SELECT type, proposal_id, payload_json FROM events WHERE type = ? AND proposal_id = ? ORDER BY id",
        (event_type, proposal_id),
    ).fetchall()


def _feedback_rows(conn, proposal_id=None):
    if proposal_id is None:
        return conn.execute("SELECT * FROM agent_feedback ORDER BY id").fetchall()
    return conn.execute(
        "SELECT * FROM agent_feedback WHERE file_event_id = ? ORDER BY id",
        (proposal_id,),
    ).fetchall()


def _error_rows(conn, level=None):
    if level:
        return conn.execute(
            "SELECT level, message FROM errors WHERE level = ? ORDER BY id",
            (level,),
        ).fetchall()
    return conn.execute("SELECT level, message FROM errors ORDER BY id").fetchall()


def _make_proposal(ops, *, target="pkg/app.py"):
    """Create an approved (not yet applied) proposal in the temp DB; return its id.

    materialize_proposal() applies any non-'applied' proposal itself, so setting
    approved-but-unapplied keeps callers that approve-then-materialize
    (run_developer_mutation, _gate_and_materialize) on the exact production
    path instead of double-applying or pretending the proposal is done.
    """
    from file_editing.db import get_db_connection
    from workflow.proposal_builder import create_proposal_from_developer_output

    prop = create_proposal_from_developer_output(
        {
            "target_file_path": target,
            "summary": "create module files to test hook behavior",
            "rationale": "Creating module files to exercise the git hook closed loop",
            "operations": ops,
        },
        1,
        target,
    )
    assert prop["status"] == "success", prop
    proposal_id = prop["proposal_id"]
    with get_db_connection() as conn:
        conn.execute(
            "UPDATE edit_proposals SET status = 'approved' WHERE proposal_id = ?",
            (proposal_id,),
        )
    return proposal_id


# ---------------------------------------------------------------------------
# Fixture: config everywhere + git enabled
# ---------------------------------------------------------------------------


@pytest.fixture
def git_config_env(monkeypatch, tmp_path):
    """Patch get_config at the same import sites conftest does, git on."""
    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    cfg = {
        "project_directory": str(project_dir),
        "background_agents_enabled": False,
        "git": True,
        "git_auto_commit": True,
        "token_budget": {"max_tokens_per_4h": 1_000_000},
    }
    from core import config as core_config

    for target in (
        "core.config.get_config",
        "core.content_safety.get_config",
        "core.context_manager.get_config",
        "core.db.get_config",
        "core.endpoint_manager.get_config",
        "core.file_operations.get_config",
        "core.file_retrieval.get_config",
        "core.index_context.get_config",
        "core.llm_test_mode.get_config",
        "core.rate_limiter.get_config",
        "core.symbol_index.get_config",
        "agents.base.get_config",
        "workflow.task_runner.get_config",
        "workflow.shell_developer.get_config",
        "cli.commands.get_config",
        "interactive.get_config",
        "utils.git_operations.get_config",
    ):
        try:
            monkeypatch.setattr(target, lambda c=cfg: c)
        except (AttributeError, ImportError):
            pass
    monkeypatch.setattr(core_config, "get_config", lambda: cfg)

    # Symbol-index refresh opens a *second* connection inside the writer's open
    # write transaction, which busy-waits ~30s then fails with "database is
    # locked" on multi-file proposals (pre-existing, unrelated to the git hook
    # path). Stub it so these tests exercise the git closed loop, not that stall.
    try:
        from core import index_context as index_mod

        monkeypatch.setattr(index_mod, "refresh_file_symbols", lambda file_path, content: 0)
    except ImportError:
        pass

    return cfg, project_dir


# ---------------------------------------------------------------------------
# File-id rules (PR-94 nits: UNIQUE race + is_deleted consistency)
# ---------------------------------------------------------------------------


class TestFileIdRules:
    def test_reuses_and_resurrects_soft_deleted_path(self, git_config_env, temp_db):
        from file_editing.db import get_db_connection
        from file_editing.writer import _get_or_create_file_id_short, initialize_file_lines

        with get_db_connection() as conn:
            cur = conn.execute("INSERT INTO files (file_path, current_version, is_deleted, has_been_written_to_disk) VALUES ('pkg/old.py', 1, 1, 0)")
            deleted_id = cur.lastrowid

        # file_path is UNIQUE: the lookup must reuse the soft-deleted row,
        # never attempt a second INSERT for the same path.
        with get_db_connection() as conn:
            assert _get_or_create_file_id_short(conn, "pkg/old.py") == deleted_id

        # Re-initializing resurrects the row and rewrites its lines in place.
        init = initialize_file_lines("pkg/old.py", "x = 1\ny = 2\n")
        assert init["status"] == "success"
        assert init["file_id"] == deleted_id
        with get_db_connection() as conn:
            row = conn.execute("SELECT file_id, is_deleted FROM files WHERE file_path = 'pkg/old.py'").fetchone()
            assert int(row[1]) == 0
            n = conn.execute(
                "SELECT COUNT(*) FROM file_lines WHERE file_id = ? AND is_deleted = 0",
                (deleted_id,),
            ).fetchone()[0]
            assert n == init["line_count"] == 3


# ---------------------------------------------------------------------------
# Backlog drain picks the git_hook CRITICAL row first (PR-94 nit #4)
# ---------------------------------------------------------------------------


class TestBacklogDrain:
    def test_git_hook_critical_drains_before_high(self, git_config_env, temp_db):
        from datetime import datetime, timezone

        from core.db_connection import get_db_connection
        from workflow.backlog import apply_backlog_overrides, fetch_top_feedback

        task_id = "bl_githook"
        iso = datetime.now(timezone.utc).isoformat()
        with get_db_connection() as conn:
            conn.execute(
                "INSERT INTO agent_feedback (agent_name, file_path, priority, category, message, task_id, addressed, timestamp) "
                "VALUES ('jr_reviewer', 'warn.py', 'HIGH', 'style', 'minor formatting', ?, 0, ?)",
                (task_id, iso),
            )
            conn.execute(
                "INSERT INTO agent_feedback (agent_name, file_path, priority, category, message, suggestion, task_id, addressed, timestamp) "
                "VALUES ('git_hook', 'pkg/app.py', 'CRITICAL', 'bug', 'git commit failed (code=1): pre-commit hook failed', "
                "'Fix the pre-commit hook failure before continuing.', ?, 0, ?)",
                (task_id, iso),
            )
            top = fetch_top_feedback(conn, task_id)
            out = apply_backlog_overrides(task_id, {"next_agent": "background"}, conn)

        assert top is not None
        assert top[2] == "bug"  # agent category
        assert top[3] == "pkg/app.py"
        assert "git commit failed" in top[4]
        assert out["next_agent"] == "developer"
        assert out["files_needed"] == ["pkg/app.py"]
        assert out["addressing_feedback_ids"] == [top[0]]
        assert "pre-commit hook failure" in out["instructions"]

    def test_multiple_critical_rows_pick_newest_unaddressed(self, git_config_env, temp_db):
        from datetime import datetime, timedelta, timezone

        from core.db_connection import get_db_connection
        from workflow.backlog import fetch_top_feedback

        task_id = "bl_multi"
        base = datetime.now(timezone.utc)
        with get_db_connection() as conn:
            for i in (0, 1):
                conn.execute(
                    "INSERT INTO agent_feedback (agent_name, file_path, priority, category, message, task_id, addressed, timestamp) "
                    "VALUES ('git_hook', ?, 'CRITICAL', 'bug', ?, ?, 0, ?)",
                    (
                        f"f{i}.py",
                        f"git commit failed for f{i}",
                        task_id,
                        (base - timedelta(hours=i)).isoformat(),
                    ),
                )
            top = fetch_top_feedback(conn, task_id)
        assert top is not None and "f1" in top[3]


# ---------------------------------------------------------------------------
# Writer status semantics
# ---------------------------------------------------------------------------


class TestMaterializeStatus:
    def test_hook_failure_is_not_success(self, git_config_env, monkeypatch, temp_db):
        pid = _make_proposal([{"type": "create_file", "target_file_path": "pkg/app.py", "initial_content": ["x = 1"]}])
        monkeypatch.setattr(
            "file_editing.writer.git_commit",
            lambda fp, msg, **kwargs: _git_failure_result(file_path=fp),
        )

        from file_editing.writer import materialize_proposal

        mat = materialize_proposal(pid)

        assert mat["status"] == "git_failed"  # explicitly NOT "success"
        assert mat["materialized_files"]  # disk write still happened (fix-forward)
        gf = mat["git_failed"]
        assert gf is not None
        assert gf["ok"] is False and gf["code"] == 1
        assert "pre-commit hook failed" in gf["stderr"]

    def test_hook_success_returns_success(self, git_config_env, monkeypatch, temp_db):
        pid = _make_proposal([{"type": "create_file", "target_file_path": "pkg/app.py", "initial_content": ["x = 1"]}])
        monkeypatch.setattr(
            "file_editing.writer.git_commit",
            lambda fp, msg, **kwargs: _git_success_result(file_path=fp),
        )

        from file_editing.writer import materialize_proposal

        mat = materialize_proposal(pid)

        assert mat["status"] == "success"
        assert mat["git_failed"] is None

    def test_git_disabled_is_not_a_failure(self, git_config_env, monkeypatch, temp_db):
        pid = _make_proposal([{"type": "create_file", "target_file_path": "pkg/app.py", "initial_content": ["x = 1"]}])
        monkeypatch.setattr(
            "file_editing.writer.git_commit",
            lambda fp, msg, **kwargs: {**_git_failure_result(file_path=fp), "attempted": False, "stage": "disabled"},
        )

        from file_editing.writer import materialize_proposal

        mat = materialize_proposal(pid)

        assert mat["status"] == "success"
        assert mat["git_failed"] is None

    def test_multi_file_success_does_not_clear_failure(self, git_config_env, monkeypatch, temp_db):
        pid = _make_proposal(
            [
                {"type": "create_file", "target_file_path": "pkg/app.py", "initial_content": ["x = 1"]},
                {"type": "create_file", "target_file_path": "pkg/other.py", "initial_content": ["y = 2"]},
            ]
        )

        def fake_git_commit(rel_path, _msg, **kwargs):
            if rel_path == "pkg/app.py":
                return _git_failure_result(file_path=rel_path)
            return _git_success_result(file_path=rel_path)

        monkeypatch.setattr("file_editing.writer.git_commit", fake_git_commit)

        from file_editing.writer import materialize_proposal

        mat = materialize_proposal(pid)

        # File A fails the hook, file B commits fine. The failure must survive.
        assert mat["status"] == "git_failed"
        assert mat["git_failed"]["file_path"] == "pkg/app.py"
        assert mat["git_failed"]["ok"] is False

    def test_multi_file_all_success(self, git_config_env, monkeypatch, temp_db):
        pid = _make_proposal(
            [
                {"type": "create_file", "target_file_path": "pkg/app.py", "initial_content": ["x = 1"]},
                {"type": "create_file", "target_file_path": "pkg/other.py", "initial_content": ["y = 2"]},
            ]
        )
        monkeypatch.setattr(
            "file_editing.writer.git_commit",
            lambda fp, msg, **kwargs: _git_success_result(file_path=fp),
        )

        from file_editing.writer import materialize_proposal

        mat = materialize_proposal(pid)

        assert mat["status"] == "success"
        assert mat["git_failed"] is None


# ---------------------------------------------------------------------------
# record_git_failure helper (shared by both callers)
# ---------------------------------------------------------------------------


class TestRecordGitFailureHelper:
    def test_records_event_and_critical_feedback_deduped(self, git_config_env, monkeypatch, temp_db):
        from file_editing.db import get_db_connection
        from workflow.git_failure import record_git_failure

        pid = "proposal-git-1"
        mat = {"status": "git_failed", "git_failed": _git_failure_result()}

        assert record_git_failure(mat, task_id="T-1", proposal_id=pid) is True
        # Re-materialize / retried turn must not duplicate the feedback row.
        assert record_git_failure(mat, task_id="T-1", proposal_id=pid) is True

        with get_db_connection() as conn:
            assert len(_event_rows(conn, "edit.git_failed", pid)) == 2
            assert not _event_rows(conn, "edit.materialized", pid)
            fb = _feedback_rows(conn, pid)
            assert len(fb) == 1
            assert fb[0]["priority"] == "CRITICAL"
            assert fb[0]["agent_name"] == "git_hook"
            assert "pre-commit hook failed" in fb[0]["message"]

    def test_returns_false_when_not_attempted(self, git_config_env, temp_db):
        from workflow.git_failure import record_git_failure

        assert record_git_failure({"status": "success", "git_failed": None}, "T", "p") is False
        assert (
            record_git_failure(
                {"status": "success", "git_failed": {**_git_failure_result(), "attempted": False}},
                "T",
                "p",
            )
            is False
        )


# ---------------------------------------------------------------------------
# Shell path: _gate_and_materialize
# ---------------------------------------------------------------------------


class TestGateAndMaterializeClosedLoop:
    def test_git_failure_emits_event_feedback_errors(self, git_config_env, monkeypatch, temp_db):
        from file_editing.db import get_db_connection
        from workflow.shell_developer import SessionResult, _gate_and_materialize

        pid = _make_proposal([{"type": "create_file", "target_file_path": "pkg/app.py", "initial_content": ["x = 1"]}])
        monkeypatch.setattr(
            "agents.base.call_agent",
            lambda agent_name, prompt, task_id, *a, **k: json.dumps({"decision": "APPROVE", "reason": "ok", "suggestions": []}),
        )
        monkeypatch.setattr(
            "file_editing.writer.git_commit",
            lambda fp, msg, **kwargs: _git_failure_result(file_path=fp),
        )

        progress = {"edit_failures": 0}
        status = _gate_and_materialize(
            proposal_id=pid,
            payload_dict={},
            target_file_path="pkg/app.py",
            diff_text="",
            result=SessionResult(),
            fallback_used=False,
            task_id="T-shell-git",
            progress=progress,
            current_turn=1,
        )

        assert status == "git_failed"
        # The failed hook must not be counted as a materialized file.
        assert progress.get("files_modified", 0) == 0
        assert progress.get("materialize_successes", 0) == 0

        with get_db_connection() as conn:
            assert _event_rows(conn, "edit.git_failed", pid)
            assert not _event_rows(conn, "edit.materialized", pid)
            fb = _feedback_rows(conn, pid)
            assert len(fb) == 1 and fb[0]["priority"] == "CRITICAL"
            errs = _error_rows(conn, level="CRITICAL")
            assert any("git commit failed" in e["message"] for e in errs)
            assert any("pre-commit hook failed" in e["message"] for e in errs)


# ---------------------------------------------------------------------------
# Developer path: run_developer_mutation + addressing guard
# ---------------------------------------------------------------------------


class TestRunDeveloperMutationClosedLoop:
    def test_addressing_not_closed_and_loop_is_recorded(self, git_config_env, monkeypatch, temp_db, mock_llm):
        from file_editing.db import get_db_connection
        from file_editing.writer import initialize_file_lines
        from workflow.developer_edit import run_developer_mutation

        _cfg, project_dir = git_config_env
        lines = [f"# line {i}" for i in range(80)]
        lines[10] = "value = OLD"
        body = "\n".join(lines) + "\n"
        (project_dir / "app.py").write_text(body)
        initialize_file_lines("app.py", body)

        # Pre-existing CRITICAL feedback that this turn claims to address.
        with get_db_connection() as conn:
            cur = conn.execute(
                "INSERT INTO agent_feedback (task_id, agent_name, message, priority, addressed, timestamp) "
                "VALUES (?, 'backlog_redirect', 'poison file must be fixed', 'CRITICAL', 0, ?)",
                ("git_fail_task", "2026-01-01T00:00:00"),
            )
            fb_id = cur.lastrowid

        new_body = body.replace("value = OLD", "value = NEW")
        mock_llm.set_response(
            "developer",
            json.dumps(
                {
                    "target_file_path": "app.py",
                    "new_content": new_body,
                    "summary": "rename OLD to NEW",
                    "rationale": "replace whole file content to update the stale constant",
                }
            ),
        )
        mock_llm.set_response(
            "reviewer",
            json.dumps({"decision": "APPROVE", "reason": "ok", "suggestions": []}),
        )
        monkeypatch.setattr(
            "file_editing.writer.git_commit",
            lambda fp, msg, **kwargs: _git_failure_result(file_path=fp),
        )

        progress: dict = {}
        with mock_llm.patch_call_agent():
            result = run_developer_mutation(
                task_id="git_fail_task",
                instructions="Rename OLD to NEW in app.py",
                user_command="Rename OLD to NEW",
                requested_files=["app.py"],
                conversation_context=[],
                model_choice=None,
                preferred_modes=["find_replace"],
                fallback_order=["find_replace"],
                small_file_threshold=180,
                progress=progress,
                decision={"addressing_feedback_ids": [fb_id]},
                current_turn=1,
            )

        assert result["status"] == "git_failed", result
        assert progress.get("files_modified", 0) == 0
        assert progress.get("materialize_successes", 0) == 0

        with get_db_connection() as conn:
            # The CRITICAL feedback that "caused" this write must NOT close.
            row = conn.execute("SELECT addressed FROM agent_feedback WHERE id = ?", (fb_id,)).fetchone()
            assert int(row[0] or 0) == 0

            pid = result["proposal_id"]
            assert _event_rows(conn, "edit.git_failed", pid)
            assert not _event_rows(conn, "edit.materialized", pid)
            fb = _feedback_rows(conn, pid)
            assert len(fb) == 1 and fb[0]["priority"] == "CRITICAL"
            errs = _error_rows(conn, level="CRITICAL")
            assert any("git commit failed" in e["message"] for e in errs)
            assert any("pre-commit hook failed" in e["message"] for e in errs)
