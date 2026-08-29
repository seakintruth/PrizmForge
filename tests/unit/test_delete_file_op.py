"""Governed delete_file operation (mini-swe §4: the previously missing delete op).

Covers the shared schema gate, the governed-store apply, the materialize
(disk removal + write-log), and the shell developer D-status mapping.
"""

from pathlib import Path

from file_editing.edit_payload import DeleteFile, EditPayload, validate_operation
from workflow.shell_developer import change_to_operation

# ---------------------------------------------------------------------------
# Schema gate (shared with the developer validator)
# ---------------------------------------------------------------------------


class TestSchemaGate:
    def test_valid_delete_file_passes_shared_gate(self):
        op = {"type": "delete_file", "target_file_path": "legacy.py", "rationale": "Remove obsolete module"}
        assert validate_operation(op) is None

    def test_delete_file_requires_target_file_path(self):
        assert validate_operation({"type": "delete_file", "rationale": "Obsolete module removal"}) is not None

    def test_delete_file_model_validate_resolves_type(self):
        payload = EditPayload.model_validate(
            {
                "target_file_path": "legacy.py",
                "summary": "Remove obsolete module",
                "rationale": "Obsolete module removal",
                "operations": [{"type": "delete_file", "target_file_path": "legacy.py", "rationale": "Remove obsolete module"}],
            }
        )
        assert isinstance(payload.operations[0], DeleteFile)
        assert payload.operations[0].target_file_path == "legacy.py"


# ---------------------------------------------------------------------------
# Governed-store apply
# ---------------------------------------------------------------------------


class TestApplyDeleteFile:
    def test_marks_file_and_lines_deleted(self, temp_db):
        from file_editing.db import get_db_connection
        from file_editing.editing import apply_delete_file
        from file_editing.writer import initialize_file_lines

        with get_db_connection() as conn:
            file_id = initialize_file_lines("legacy.py", "a = 1\nb = 2\n", conn=conn)["file_id"]
            op = DeleteFile(target_file_path="legacy.py", rationale="Remove obsolete module")

            result = apply_delete_file(conn, file_id, op)

            assert result["status"] == "success"
            assert result["lines_deleted"] == 3
            row = conn.execute("SELECT is_deleted FROM files WHERE file_id = ?", (file_id,)).fetchone()
            assert row["is_deleted"] == 1
            live = conn.execute(
                "SELECT COUNT(*) AS n FROM file_lines WHERE file_id = ? AND is_deleted = 0",
                (file_id,),
            ).fetchone()
            assert live["n"] == 0

    def test_refuses_repeat_delete(self, temp_db):
        from file_editing.db import get_db_connection
        from file_editing.editing import apply_delete_file
        from file_editing.writer import initialize_file_lines

        with get_db_connection() as conn:
            file_id = initialize_file_lines("legacy.py", "a = 1\n", conn=conn)["file_id"]
            op = DeleteFile(target_file_path="legacy.py", rationale="Remove obsolete module")

            first = apply_delete_file(conn, file_id, op)
            second = apply_delete_file(conn, file_id, op)

            assert first["status"] == "success"
            assert second["status"] == "error"
            assert "already deleted" in second["message"]

    def test_refuses_path_mismatch(self, temp_db):
        from file_editing.db import get_db_connection
        from file_editing.editing import apply_delete_file
        from file_editing.writer import initialize_file_lines

        with get_db_connection() as conn:
            file_id = initialize_file_lines("legacy.py", "a = 1\n", conn=conn)["file_id"]
            op = DeleteFile(target_file_path="other.py", rationale="Remove obsolete module")

            result = apply_delete_file(conn, file_id, op)

            assert result["status"] == "error"
            assert "mismatch" in result["message"]


# ---------------------------------------------------------------------------
# Materialize: removal from disk + write-log
# ---------------------------------------------------------------------------


class TestMaterializeDelete:
    def test_materialize_removes_disk_file_and_logs_deleted(self, mock_minimal_config, temp_db):
        from file_editing.db import get_db_connection
        from file_editing.writer import materialize_proposal
        from workflow.proposal_builder import create_proposal_from_developer_output

        project_dir = Path(mock_minimal_config["project_directory"])

        def _propose(ops, target):
            from file_editing.db import get_db_connection as _edit_db

            prop = create_proposal_from_developer_output(
                {"target_file_path": target, "summary": "work step now", "rationale": "working file edits", "operations": ops},
                1,
                target,
            )
            assert prop["status"] == "success", prop
            with _edit_db() as conn:
                conn.execute("UPDATE edit_proposals SET status = 'approved' WHERE proposal_id = ?", (prop["proposal_id"],))
            return prop["proposal_id"]

        path = "legacy.py"
        create_pid = _propose(
            [{"type": "create_file", "target_file_path": path, "initial_content": ["VALUE = 1"]}],
            path,
        )
        mat = materialize_proposal(create_pid)
        assert mat["status"] == "success", mat
        disk = project_dir / path
        assert disk.exists() and disk.read_text() == "VALUE = 1"

        delete_pid = _propose([{"type": "delete_file", "target_file_path": path, "rationale": "Remove obsolete module"}], path)
        mat = materialize_proposal(delete_pid)
        assert mat["status"] == "success", mat
        assert not disk.exists()

        with get_db_connection() as conn:
            file_rows = conn.execute("SELECT * FROM files WHERE file_path = ?", (path,)).fetchall()
            assert len(file_rows) == 1
            assert file_rows[0]["is_deleted"] == 1

            logs = conn.execute(
                "SELECT status FROM file_write_log WHERE proposal_id = ? ORDER BY log_id LIMIT 1",
                (delete_pid,),
            ).fetchall()
            assert logs and logs[0]["status"] == "deleted"

            mods = conn.execute(
                "SELECT content_before, content_after FROM file_modifications WHERE file_path = ? ORDER BY id DESC LIMIT 1",
                (path,),
            ).fetchall()
            assert mods and mods[0]["content_before"] == "VALUE = 1"
            assert mods[0]["content_after"] == ""


# ---------------------------------------------------------------------------
# Shell developer mapping
# ---------------------------------------------------------------------------


class TestShellMapping:
    def test_d_status_maps_to_delete_file(self):
        op = change_to_operation({"path": "legacy.py", "status": "D", "new_content": ""})
        assert op == {"type": "delete_file", "target_file_path": "legacy.py", "rationale": "Delete file (shell developer session)"}

    def test_oversize_status_still_skipped(self):
        assert change_to_operation({"path": "big.py", "status": "S", "new_content": ""}) is None


# ---------------------------------------------------------------------------
# Disk removal resilience (P8)
# ---------------------------------------------------------------------------


class TestDiskRemovalResilience:
    def test_missing_file_is_successful_noop(self, tmp_path):
        from file_editing.writer import _delete_file_from_disk

        result = _delete_file_from_disk("ghost.py", tmp_path)
        assert result["status"] == "success"

    def test_directory_unlink_oserror_is_surfaced(self, tmp_path):
        # unlink() on a directory raises IsADirectoryError (an OSError). The
        # governed store may say "deleted" from a prior applied op, but the
        # disk removal failing must yield an error result the materialize path
        # records as a write-log 'error' row (residual P8).
        from file_editing.writer import _delete_file_from_disk

        subdir = tmp_path / "not_a_file"
        subdir.mkdir()
        result = _delete_file_from_disk("not_a_file", tmp_path)
        assert result["status"] == "error"
        assert "disk removal failed" in result["message"]

    def test_path_escape_is_error(self, tmp_path):
        from file_editing.writer import _delete_file_from_disk

        result = _delete_file_from_disk("../outside.py", tmp_path)
        assert result["status"] == "error"
