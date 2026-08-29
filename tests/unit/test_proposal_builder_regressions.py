"""PR-83 residual P2/P3 regressions for workflow/proposal_builder.py.

P2 - the per-call runtime ``ALTER TABLE edit_proposals ADD COLUMN`` loop is
removed; the columns are owned by the canonical schema + one-time migration in
core/db.py.
P3 - ``_capture_hashes_for_operations`` fetches all affected line-GUID hashes in
a single ``IN (...)`` query instead of one SELECT per GUID.
"""

from __future__ import annotations

from contextlib import contextmanager

import pytest


class _RecordingConn:
    """Proxy that records SQL statements executed through a connection."""

    def __init__(self, conn, log: list[str]):
        self._conn_ = conn
        self._log_ = log

    def __getattr__(self, name):
        return getattr(self._conn_, name)

    def execute(self, sql, *args, **kwargs):
        self._log_.append(sql)
        return self._conn_.execute(sql, *args, **kwargs)


@pytest.fixture
def recording_proposal_builder(monkeypatch):
    """Point proposal_builder at its DB connection through a recording proxy."""
    import workflow.proposal_builder as pb

    real_get_db_connection = pb.get_db_connection
    sql_log: list[str] = []

    @contextmanager
    def _recording():
        with real_get_db_connection() as conn:
            yield _RecordingConn(conn, sql_log)

    monkeypatch.setattr(pb, "get_db_connection", _recording)
    return sql_log


class TestNoRuntimeAlter:
    def test_proposal_create_uses_schema_columns_not_runtime_ddl(self, temp_db, recording_proposal_builder):
        from workflow.proposal_builder import create_proposal_from_developer_output

        result = create_proposal_from_developer_output(
            {
                "target_file_path": "pkg/app.py",
                "summary": "add module",
                "rationale": "add a module to exercise proposal creation",
                "operations": [{"type": "create_file", "target_file_path": "pkg/app.py", "initial_content": ["x = 1"]}],
            },
            1,
            "pkg/app.py",
        )

        assert result["status"] == "success", result
        assert recording_proposal_builder, "expected at least the proposal INSERT"

        # The old best-effort loop issued ALTER TABLE on every create.
        assert all("ALTER TABLE" not in stmt for stmt in recording_proposal_builder)
        # Non-hollow: the columns must come from the canonical schema/migration.
        from file_editing.db import get_db_connection

        with get_db_connection() as conn:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(edit_proposals)")}
        assert {"selected_mode", "fallback_used", "final_mode", "task_id"} <= cols


class TestBatchHashCapture:
    def _seed_with_guids(self, temp_db):
        from file_editing.db import get_db_connection
        from file_editing.writer import initialize_file_lines

        initialize_file_lines("pkg/app.py", "a = 1\nb = 2\nc = 3\n")
        with get_db_connection() as conn:
            file_id = conn.execute("SELECT file_id FROM files WHERE file_path = 'pkg/app.py' AND is_deleted = 0").fetchone()[0]
            return [
                r[0]
                for r in conn.execute(
                    "SELECT line_guid FROM file_lines WHERE file_id = ? ORDER BY sort_order",
                    (file_id,),
                )
            ]

    def test_hashes_fetched_in_single_in_query(self, temp_db, recording_proposal_builder):
        from workflow.proposal_builder import create_proposal_from_developer_output

        guids = self._seed_with_guids(temp_db)
        g0, g1 = guids[0], guids[1]

        result = create_proposal_from_developer_output(
            {
                "target_file_path": "pkg/app.py",
                "summary": "delete a line",
                "rationale": "remove a line in the governed file to exercise hash capture",
                "operations": [{"type": "delete_lines", "start_line_guid": g0, "end_line_guid": g1}],
            },
            1,
            "pkg/app.py",
        )

        assert result["status"] == "success", result

        hash_selects = [s for s in recording_proposal_builder if "FROM file_lines" in s]
        assert len(hash_selects) == 1, "expected exactly one batched hash lookup"
        assert "IN (" in hash_selects[0]
        # A per-GUID equality scan would emit the query once per GUID.
        assert all("line_guid =" not in s for s in hash_selects)

        assert set(result["affected_line_guids"]) == {g0, g1}

    def test_no_guids_short_circuits(self, temp_db, recording_proposal_builder):
        from workflow.proposal_builder import create_proposal_from_developer_output

        result = create_proposal_from_developer_output(
            {
                "target_file_path": "pkg/new.py",
                "summary": "add module",
                "rationale": "create a fresh module with no line-guid operations",
                "operations": [{"type": "create_file", "target_file_path": "pkg/new.py", "initial_content": ["x = 1"]}],
            },
            1,
            "pkg/new.py",
        )

        assert result["status"] == "success", result
        assert result["affected_line_guids"] == []
        # With no affected GUIDs the batched query must not run an empty IN ().
        assert all("IN (" not in s or "FROM file_lines" not in s for s in recording_proposal_builder)


class TestBareSingleOpPayload:
    """Residual P1: a single-operation payload without an ``operations`` list."""

    def test_bare_payload_creates_proposal(self, temp_db):
        from workflow.proposal_builder import create_proposal_from_developer_output

        result = create_proposal_from_developer_output(
            {
                "target_file_path": "pkg/bare.py",
                "summary": "add module",
                "rationale": "bare single-operation shape",
                "type": "create_file",
                "initial_content": ["x = 1"],
            },
            1,
            "pkg/bare.py",
        )

        assert result["status"] == "success", result

    def test_payload_missing_operations_and_type_rejected(self, temp_db):
        from workflow.proposal_builder import create_proposal_from_developer_output

        # Backstop: neither a bare-op ("type") shape nor an operations list.
        result = create_proposal_from_developer_output(
            {"target_file_path": "pkg/blank.py", "summary": "no operations"},
            1,
            "pkg/blank.py",
        )
        assert result["status"] == "error"

    def test_empty_operations_list_rejected(self, temp_db):
        from workflow.proposal_builder import create_proposal_from_developer_output

        result = create_proposal_from_developer_output(
            {
                "target_file_path": "pkg/blank.py",
                "summary": "no operations",
                "rationale": "empty list backstop",
                "operations": [],
            },
            1,
            "pkg/blank.py",
        )
        assert result["status"] == "error"


class TestDeleteThenRecreate:
    """Residual P2: delete_file followed by recreate must REUSE the file_id."""

    def _propose(self, ops, target, *, approve=False):
        from workflow.proposal_builder import create_proposal_from_developer_output

        prop = create_proposal_from_developer_output(
            {"target_file_path": target, "summary": "work step now", "rationale": "working file edits", "operations": ops},
            1,
            target,
        )
        assert prop["status"] == "success", prop
        if approve:
            from file_editing.db import get_db_connection as _edit_db

            with _edit_db() as conn:
                conn.execute("UPDATE edit_proposals SET status = 'approved' WHERE proposal_id = ?", (prop["proposal_id"],))
        return prop["proposal_id"]

    def test_recreate_reuses_soft_deleted_file_id(self, temp_db):
        from file_editing.db import get_db_connection
        from file_editing.edit_payload import DeleteFile
        from file_editing.editing import apply_delete_file
        from file_editing.writer import initialize_file_lines

        with get_db_connection() as conn:
            file_id = initialize_file_lines("pkg/reuse.py", "VALUE = 1\n", conn=conn)["file_id"]
            apply_delete_file(conn, file_id, DeleteFile(target_file_path="pkg/reuse.py", rationale="remove"))
            assert conn.execute("SELECT is_deleted FROM files WHERE file_id = ?", (file_id,)).fetchone()[0] == 1

        # Recreate on the same path through the FULL proposal path.
        self._propose(
            [{"type": "create_file", "target_file_path": "pkg/reuse.py", "initial_content": ["VALUE = 2"]}],
            "pkg/reuse.py",
        )

        with get_db_connection() as conn:
            # Same path -> same file_id (resurrected), never a second live row.
            rows = conn.execute("SELECT file_id FROM files WHERE file_path = 'pkg/reuse.py' ORDER BY file_id").fetchall()
            assert len(rows) == 1
            assert rows[0]["file_id"] == file_id
            assert conn.execute("SELECT is_deleted FROM files WHERE file_id = ?", (file_id,)).fetchone()[0] == 0

    def test_delete_then_recreate_has_single_file_row(self, temp_db):
        from file_editing.db import get_db_connection
        from file_editing.writer import materialize_proposal

        path = "pkg/cycle.py"
        create_pid = self._propose(
            [{"type": "create_file", "target_file_path": path, "initial_content": ["VALUE = 1"]}],
            path,
            approve=True,
        )
        assert materialize_proposal(create_pid)["status"] == "success"
        delete_pid = self._propose(
            [{"type": "delete_file", "target_file_path": path, "rationale": "remove"}],
            path,
            approve=True,
        )
        assert materialize_proposal(delete_pid)["status"] == "success"

        recreate_pid = self._propose(
            [{"type": "create_file", "target_file_path": path, "initial_content": ["VALUE = 2"]}],
            path,
            approve=True,
        )
        assert materialize_proposal(recreate_pid)["status"] == "success"

        with get_db_connection() as conn:
            rows = conn.execute("SELECT file_id, is_deleted FROM files WHERE file_path = ?", (path,)).fetchall()
            # Residual P2: exactly one file row, live again (no orphan duplicates).
            assert len(rows) == 1
            assert rows[0]["is_deleted"] == 0
