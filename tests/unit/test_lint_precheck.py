"""Optional in-process ruff pre-check (plan §7.2, hook remains authoritative).

Closed loop: on a non-zero ruff exit the proposal materializes as
``lint_failed`` (disk write kept, git skipped), one ``edit.lint_failed`` event
and one CRITICAL feedback row per proposal are written post-commit, and the
next developer turn can fix forward. Disabled by default.
"""

from core.db_connection import get_db_connection
from file_editing.writer import _run_ruff_precheck, materialize_proposal
from workflow.proposal_builder import create_proposal_from_developer_output


class FakeRuffProcess:
    returncode = 1
    stdout = ""
    stderr = "app.py:2:89: E501 Line too long (92 > 88)"


class FakeRuffOk:
    returncode = 0
    stdout = ""
    stderr = ""


def _propose_approved(target="app.py"):
    prop = create_proposal_from_developer_output(
        {
            "target_file_path": target,
            "summary": "ruff precheck probe",
            "rationale": "ruff precheck probe proposal",
            "operations": [{"type": "create_file", "target_file_path": target, "initial_content": ["x = 'a really really long string ' * 30"]}],
        },
        1,
        target,
    )
    assert prop["status"] == "success", prop
    from file_editing.db import get_db_connection as edit_db

    with edit_db() as conn:
        conn.execute("UPDATE edit_proposals SET status = 'approved' WHERE proposal_id = ?", (prop["proposal_id"],))
    return prop["proposal_id"]


class TestRunPrecheck:
    def test_disabled_returns_empty(self, mock_minimal_config):
        assert _run_ruff_precheck(None, None, "app.py") == {}

    def test_failure_marker(self, tmp_path, mock_minimal_config, monkeypatch):
        # Hermetic: pre-check result does not depend on ruff being installed.
        mock_minimal_config["file_editing"] = {"in_process_ruff_check": True}
        monkeypatch.setattr("file_editing.writer.subprocess.run", lambda *_a, **_k: FakeRuffOk())
        f = tmp_path / "app.py"
        f.write_text("x = 1\n")
        res = _run_ruff_precheck(f, tmp_path, "app.py")
        assert res == {"attempted": True, "ok": True}


class TestMaterializeLintGate:
    def test_ruff_failure_surfaces_lint_failed_closed_loop(self, mock_minimal_config, temp_db, monkeypatch):
        mock_minimal_config["file_editing"] = {"in_process_ruff_check": True}
        monkeypatch.setattr(
            "file_editing.writer.subprocess.run",
            lambda *_a, **_k: FakeRuffProcess(),
        )
        pid = _propose_approved()

        mat = materialize_proposal(pid)

        assert mat["status"] == "lint_failed"
        assert mat["lint_failed"]["code"] == 1
        with get_db_connection() as conn:
            events = conn.execute("SELECT type FROM events WHERE type = 'edit.lint_failed' AND proposal_id = ?", (pid,)).fetchall()
            assert len(events) == 1
            fb = conn.execute(
                "SELECT agent_name, priority, category FROM agent_feedback WHERE file_event_id = ?",
                (pid,),
            ).fetchall()
            assert len(fb) == 1
            assert fb[0][0] == "ruff_precheck"
            assert fb[0][1] == "CRITICAL"
            status = conn.execute("SELECT status FROM edit_proposals WHERE proposal_id = ?", (pid,)).fetchone()[0]
            # Residual P5: the write-log row reflects the real single status of
            # the write (the ruff gate it actually went through), not "success".
            log_status = conn.execute(
                "SELECT status FROM file_write_log WHERE proposal_id = ? ORDER BY log_id",
                (pid,),
            ).fetchall()
        assert status == "applied"
        assert log_status and log_status[0][0] == "lint_failed"

    def test_ruff_ok_passes_through(self, mock_minimal_config, temp_db, monkeypatch):
        mock_minimal_config["file_editing"] = {"in_process_ruff_check": True}
        monkeypatch.setattr(
            "file_editing.writer.subprocess.run",
            lambda *_a, **_k: FakeRuffOk(),
        )
        pid = _propose_approved()

        mat = materialize_proposal(pid)

        assert mat["status"] == "success"
        with get_db_connection() as conn:
            events = conn.execute("SELECT type FROM events WHERE type = 'edit.lint_failed' AND proposal_id = ?", (pid,)).fetchall()
        assert events == []

    def test_disabled_has_no_lint_gate(self, mock_minimal_config, temp_db):
        pid = _propose_approved()

        mat = materialize_proposal(pid)

        assert mat["status"] == "success"
        with get_db_connection() as conn:
            events = conn.execute("SELECT type FROM events WHERE type = 'edit.lint_failed' AND proposal_id = ?", (pid,)).fetchall()
        assert events == []
