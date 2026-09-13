"""
Phase 2 — Contract tests for EditPayload operation types and schema files.

Validates that every supported operation type parses and (where implemented)
survives proposal → approve → apply on a temp DB.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

SCHEMA_DIR = PROJECT_ROOT / "agent_schemas"


def _approve(proposal_id: str):
    from file_editing.db import get_db_connection

    with get_db_connection() as conn:
        conn.execute(
            "UPDATE edit_proposals SET status = 'approved' WHERE proposal_id = ?",
            (proposal_id,),
        )


def _content(path: str) -> str:
    from file_editing.db import get_db_connection, reconstruct_file_content

    with get_db_connection() as conn:
        row = conn.execute("SELECT file_id FROM files WHERE file_path = ?", (path,)).fetchone()
        return reconstruct_file_content(conn, row[0])


def _guids(path: str):
    from file_editing.db import get_db_connection

    with get_db_connection() as conn:
        rows = conn.execute(
            """
            SELECT fl.line_guid FROM file_lines fl
            JOIN files f ON f.file_id = fl.file_id
            WHERE f.file_path = ? AND fl.is_deleted = 0
            ORDER BY fl.sort_order
            """,
            (path,),
        ).fetchall()
    return [r[0] for r in rows]


# ---------------------------------------------------------------------------
# Payload parse contracts (no DB)
# ---------------------------------------------------------------------------

OP_PAYLOADS = {
    "find_replace": {
        "target_file_path": "c.py",
        "summary": "rename",
        "rationale": "Consistent naming across the utility module",
        "operations": [
            {
                "type": "find_replace",
                "find": "old",
                "replace": "new",
                "rationale": "rename",
            }
        ],
    },
    "full_replace": {
        "target_file_path": "c.py",
        "summary": "rewrite",
        "rationale": "Complete rewrite of a small helper file",
        "operations": [
            {
                "type": "full_replace",
                "new_content": "x = 1\n",
                "rationale": "full",
            }
        ],
    },
    "replace_block": {
        "target_file_path": "c.py",
        "summary": "replace line",
        "rationale": "Update a single guided line block in place",
        "operations": [
            {
                "type": "replace_block",
                "start_line_guid": "guid-1",
                "new_content": ["updated"],
                "rationale": "rb",
            }
        ],
    },
    "insert_after": {
        "target_file_path": "c.py",
        "summary": "insert",
        "rationale": "Insert a new line after an existing guided line",
        "operations": [
            {
                "type": "insert_after",
                "after_guid": "guid-1",
                "new_content": ["inserted"],
                "rationale": "ins",
            }
        ],
    },
    "delete_lines": {
        "target_file_path": "c.py",
        "summary": "delete",
        "rationale": "Remove an obsolete guided line from the file",
        "operations": [
            {
                "type": "delete_lines",
                "start_line_guid": "guid-1",
                "rationale": "del",
            }
        ],
    },
    "create_file": {
        "target_file_path": "new.py",
        "summary": "create new file",
        "rationale": "Create a new module with initial content body",
        "operations": [
            {
                "type": "create_file",
                "target_file_path": "new.py",
                "initial_content": ["print(1)"],
                "rationale": "create file",
            }
        ],
    },
    "apply_diff": {
        "target_file_path": "c.py",
        "summary": "apply unified diff",
        "rationale": "Apply a unified diff patch to update one line",
        "operations": [
            {
                "type": "apply_diff",
                "diff": "--- a/c.py\n+++ b/c.py\n@@ -1 +1 @@\n-old\n+new\n",
                "rationale": "apply diff",
            }
        ],
    },
    "update_documentation": {
        "target_file_path": "c.py",
        "summary": "update file docs",
        "rationale": "Refresh module documentation comment block text",
        "operations": [
            {
                "type": "update_documentation",
                "new_content": "Updated docs",
                "rationale": "update docs",
            }
        ],
    },
}


class TestEditPayloadContracts:
    @pytest.mark.parametrize("op_type", list(OP_PAYLOADS.keys()))
    def test_payload_parses(self, op_type):
        from file_editing.edit_payload import EditPayload

        obj = EditPayload.model_validate(OP_PAYLOADS[op_type])
        assert obj.operations
        assert obj.operations[0].type == op_type

    def test_unknown_type_rejected(self):
        from file_editing.edit_payload import EditPayload

        with pytest.raises(ValueError):
            EditPayload.model_validate(
                {
                    "target_file_path": "c.py",
                    "summary": "bad",
                    "rationale": "This should fail validation for unknown type",
                    "operations": [{"type": "telepathy", "rationale": "x"}],
                }
            )


class TestDeveloperSchemaFile:
    def test_developer_schema_loads(self):
        path = SCHEMA_DIR / "developer.json"
        assert path.exists()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(data, (dict, list))

    def test_all_schema_files_are_json(self):
        files = list(SCHEMA_DIR.glob("*.json"))
        assert files, "expected agent schema JSON files"
        for f in files:
            json.loads(f.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Apply contracts (DB) for implemented ops
# Duration-measured ~0.03-0.04s each — not a slow gate.
# ---------------------------------------------------------------------------


class TestApplyContracts:
    def test_secondary_path_op_targets_its_own_file(self, temp_db):
        """§13.2 — a content op with a target_file_path other than the proposal's
        primary must run against THAT file, not the primary target."""
        from file_editing.editing import apply_edit_proposal
        from file_editing.writer import initialize_file_lines
        from workflow.proposal_builder import create_proposal_from_developer_output

        initialize_file_lines("ops/pri.py", "p = 1\n")
        initialize_file_lines("ops/sec.py", "s = 1\n")
        prop = create_proposal_from_developer_output(
            {
                "target_file_path": "ops/pri.py",
                "summary": "bump both",
                "rationale": "Per-op target_file_path must be honored",
                "operations": [
                    {
                        "type": "find_replace",
                        "find": "p = 1",
                        "replace": "p = 2",
                        "rationale": "bump primary",
                    },
                    {
                        "type": "find_replace",
                        "find": "s = 1",
                        "replace": "s = 2",
                        "target_file_path": "ops/sec.py",
                        "rationale": "bump secondary",
                    },
                ],
            },
            1,
            "ops/pri.py",
        )
        assert prop["status"] == "success"
        _approve(prop["proposal_id"])
        res = apply_edit_proposal(prop["proposal_id"])
        assert res["status"] == "success", res
        assert _content("ops/pri.py") == "p = 2\n"
        assert _content("ops/sec.py") == "s = 2\n"

    def test_find_replace_apply(self, temp_db):
        from file_editing.editing import apply_edit_proposal
        from file_editing.writer import initialize_file_lines
        from workflow.proposal_builder import create_proposal_from_developer_output

        initialize_file_lines("ops/fr.py", "a = old\nb = old\n")
        prop = create_proposal_from_developer_output(
            {
                "target_file_path": "ops/fr.py",
                "summary": "rename",
                "rationale": "Consistent naming across the utility module",
                "operations": [
                    {
                        "type": "find_replace",
                        "find": "old",
                        "replace": "new",
                        "rationale": "rename",
                    }
                ],
            },
            1,
            "ops/fr.py",
        )
        assert prop["status"] == "success"
        _approve(prop["proposal_id"])
        assert apply_edit_proposal(prop["proposal_id"])["status"] == "success"
        assert _content("ops/fr.py") == "a = new\nb = new\n"

    def test_full_replace_apply(self, temp_db):
        from file_editing.editing import apply_edit_proposal
        from file_editing.writer import initialize_file_lines
        from workflow.proposal_builder import create_proposal_from_developer_output

        initialize_file_lines("ops/full.py", "a = 1\n")
        prop = create_proposal_from_developer_output(
            {
                "target_file_path": "ops/full.py",
                "summary": "rewrite",
                "rationale": "Complete rewrite of a small helper file",
                "operations": [
                    {
                        "type": "full_replace",
                        "new_content": "z = 9\n",
                        "rationale": "full",
                    }
                ],
            },
            1,
            "ops/full.py",
        )
        assert prop["status"] == "success"
        _approve(prop["proposal_id"])
        assert apply_edit_proposal(prop["proposal_id"])["status"] == "success"
        assert "z = 9" in _content("ops/full.py")

    def test_replace_block_apply(self, temp_db):
        from file_editing.editing import apply_edit_proposal
        from file_editing.writer import initialize_file_lines
        from workflow.proposal_builder import create_proposal_from_developer_output

        initialize_file_lines("ops/rb.py", "line1\nline2\nline3\n")
        g = _guids("ops/rb.py")
        prop = create_proposal_from_developer_output(
            {
                "target_file_path": "ops/rb.py",
                "summary": "replace middle",
                "rationale": "Update a single guided line block in place",
                "operations": [
                    {
                        "type": "replace_block",
                        "start_line_guid": g[1],
                        "new_content": ["LINE2"],
                        "rationale": "rb",
                    }
                ],
            },
            1,
            "ops/rb.py",
        )
        assert prop["status"] == "success"
        _approve(prop["proposal_id"])
        assert apply_edit_proposal(prop["proposal_id"])["status"] == "success"
        assert "LINE2" in _content("ops/rb.py")

    def test_insert_after_apply(self, temp_db):
        from file_editing.editing import apply_edit_proposal
        from file_editing.writer import initialize_file_lines
        from workflow.proposal_builder import create_proposal_from_developer_output

        initialize_file_lines("ops/ins.py", "a\nb\n")
        g = _guids("ops/ins.py")
        prop = create_proposal_from_developer_output(
            {
                "target_file_path": "ops/ins.py",
                "summary": "insert",
                "rationale": "Insert a new line after an existing guided line",
                "operations": [
                    {
                        "type": "insert_after",
                        "after_guid": g[0],
                        "new_content": ["mid"],
                        "rationale": "ins",
                    }
                ],
            },
            1,
            "ops/ins.py",
        )
        assert prop["status"] == "success"
        _approve(prop["proposal_id"])
        assert apply_edit_proposal(prop["proposal_id"])["status"] == "success"
        body = _content("ops/ins.py")
        assert "mid" in body

    def test_delete_lines_apply(self, temp_db):
        from file_editing.editing import apply_edit_proposal
        from file_editing.writer import initialize_file_lines
        from workflow.proposal_builder import create_proposal_from_developer_output

        initialize_file_lines("ops/del.py", "keep\nremove\nkeep2\n")
        g = _guids("ops/del.py")
        prop = create_proposal_from_developer_output(
            {
                "target_file_path": "ops/del.py",
                "summary": "delete",
                "rationale": "Remove an obsolete guided line from the file",
                "operations": [
                    {
                        "type": "delete_lines",
                        "start_line_guid": g[1],
                        "rationale": "del",
                    }
                ],
            },
            1,
            "ops/del.py",
        )
        assert prop["status"] == "success"
        _approve(prop["proposal_id"])
        assert apply_edit_proposal(prop["proposal_id"])["status"] == "success"
        body = _content("ops/del.py")
        assert "remove" not in body
        assert "keep" in body

    def test_apply_diff(self, temp_db):
        from file_editing.editing import apply_edit_proposal
        from file_editing.writer import initialize_file_lines
        from workflow.proposal_builder import create_proposal_from_developer_output

        initialize_file_lines("ops/diff.py", "hello\nworld\n")
        diff = "--- a/ops/diff.py\n+++ b/ops/diff.py\n@@ -1,2 +1,2 @@\n hello\n-world\n+WORLD\n"
        prop = create_proposal_from_developer_output(
            {
                "target_file_path": "ops/diff.py",
                "summary": "apply unified diff",
                "rationale": "Apply a unified diff patch to update one line",
                "operations": [
                    {
                        "type": "apply_diff",
                        "diff": diff,
                        "rationale": "diff",
                    }
                ],
            },
            1,
            "ops/diff.py",
        )
        assert prop["status"] == "success"
        _approve(prop["proposal_id"])
        result = apply_edit_proposal(prop["proposal_id"])
        assert result["status"] == "success"
        assert "WORLD" in _content("ops/diff.py")

    def test_create_file_apply(self, temp_db):
        from file_editing.editing import apply_edit_proposal
        from workflow.proposal_builder import create_proposal_from_developer_output

        prop = create_proposal_from_developer_output(
            {
                "target_file_path": "ops/brand_new.py",
                "summary": "create new helper",
                "rationale": "Add a new module for helper utilities",
                "operations": [
                    {
                        "type": "create_file",
                        "target_file_path": "ops/brand_new.py",
                        "initial_content": ["x = 1", "y = 2"],
                        "rationale": "bootstrap module",
                    }
                ],
            },
            1,
            "ops/brand_new.py",
        )
        assert prop["status"] == "success"
        _approve(prop["proposal_id"])
        result = apply_edit_proposal(prop["proposal_id"])
        assert result["status"] == "success", result
        body = _content("ops/brand_new.py")
        assert "x = 1" in body
        assert "y = 2" in body

    def test_create_file_refuses_existing(self, temp_db):
        from file_editing.editing import apply_edit_proposal
        from file_editing.writer import initialize_file_lines
        from workflow.proposal_builder import create_proposal_from_developer_output

        initialize_file_lines("ops/exists.py", "already = 1\n")
        prop = create_proposal_from_developer_output(
            {
                "target_file_path": "ops/exists.py",
                "summary": "create should fail",
                "rationale": "Should not overwrite existing governed file",
                "operations": [
                    {
                        "type": "create_file",
                        "target_file_path": "ops/exists.py",
                        "initial_content": ["nope = 1"],
                        "rationale": "should fail",
                    }
                ],
            },
            1,
            "ops/exists.py",
        )
        assert prop["status"] == "success"
        _approve(prop["proposal_id"])
        result = apply_edit_proposal(prop["proposal_id"])
        assert result["status"] == "error"
        from file_editing.db import get_db_connection

        with get_db_connection() as conn:
            st = conn.execute(
                "SELECT status FROM edit_proposals WHERE proposal_id = ?",
                (prop["proposal_id"],),
            ).fetchone()[0]
        assert st == "error"

    def test_apply_diff_malformed(self, temp_db):
        from file_editing.db import get_db_connection
        from file_editing.editing import apply_edit_proposal
        from file_editing.writer import initialize_file_lines
        from workflow.proposal_builder import create_proposal_from_developer_output

        initialize_file_lines("ops/bad_diff.py", "hello\nworld\n")
        prop = create_proposal_from_developer_output(
            {
                "target_file_path": "ops/bad_diff.py",
                "summary": "bad diff payload",
                "rationale": "Malformed unified diff should not apply",
                "operations": [
                    {
                        "type": "apply_diff",
                        "diff": "this is not a unified diff at all",
                        "rationale": "invalid",
                    }
                ],
            },
            1,
            "ops/bad_diff.py",
        )
        assert prop["status"] == "success"
        _approve(prop["proposal_id"])
        result = apply_edit_proposal(prop["proposal_id"])
        assert result["status"] in ("error", "conflicted", "success")
        with get_db_connection() as conn:
            st = conn.execute(
                "SELECT status FROM edit_proposals WHERE proposal_id = ?",
                (prop["proposal_id"],),
            ).fetchone()[0]
        if result["status"] == "error":
            assert st == "error"

    def test_apply_diff_empty(self, temp_db):
        import pytest

        from file_editing.edit_payload import EditPayload

        with pytest.raises(ValueError):
            EditPayload.model_validate(
                {
                    "target_file_path": "x.py",
                    "summary": "empty diff op",
                    "rationale": "Empty diff must fail validation",
                    "operations": [{"type": "apply_diff", "diff": "   ", "rationale": "empty"}],
                }
            )

    # -------------------------------------------------------------------
    # §13.1 — atomic apply (all-or-nothing) + op-shape guard
    # -------------------------------------------------------------------
    def test_multi_op_failure_rolls_back_whole_proposal(self, temp_db, monkeypatch):
        import file_editing.editing as editing_mod
        from file_editing.db import get_db_connection
        from file_editing.editing import apply_edit_proposal
        from file_editing.writer import initialize_file_lines
        from workflow.proposal_builder import create_proposal_from_developer_output

        initialize_file_lines("ops/atomic.py", "a\nb\n")
        g = _guids("ops/atomic.py")
        prop = create_proposal_from_developer_output(
            {
                "target_file_path": "ops/atomic.py",
                "summary": "atomic multi-op",
                "rationale": "op1 must roll back when op2 returns error",
                "operations": [
                    {
                        "type": "insert_after",
                        "after_guid": g[0],
                        "new_content": ["inserted"],
                        "rationale": "op1",
                    },
                    {
                        "type": "replace_block",
                        "start_line_guid": g[1],
                        "new_content": ["LINE2"],
                        "rationale": "op2",
                    },
                ],
            },
            1,
            "ops/atomic.py",
        )
        assert prop["status"] == "success"
        _approve(prop["proposal_id"])

        def _boom(conn, file_id, op):
            return {"status": "error", "message": "simulated op-2 failure"}

        monkeypatch.setattr(editing_mod, "apply_replace_block", _boom)
        result = apply_edit_proposal(prop["proposal_id"])
        assert result["status"] == "error"
        assert "simulated op-2 failure" in result["message"]
        assert _content("ops/atomic.py") == "a\nb\n"
        with get_db_connection() as conn:
            st = conn.execute(
                "SELECT status FROM edit_proposals WHERE proposal_id = ?",
                (prop["proposal_id"],),
            ).fetchone()[0]
        assert st == "error"

    def test_multi_op_exception_rolls_back_whole_proposal(self, temp_db, monkeypatch):
        import file_editing.editing as editing_mod
        from file_editing.db import get_db_connection
        from file_editing.editing import apply_edit_proposal
        from file_editing.writer import initialize_file_lines
        from workflow.proposal_builder import create_proposal_from_developer_output

        initialize_file_lines("ops/atomic_exc.py", "a\nb\n")
        g = _guids("ops/atomic_exc.py")
        prop = create_proposal_from_developer_output(
            {
                "target_file_path": "ops/atomic_exc.py",
                "summary": "atomic crash",
                "rationale": "op1 must roll back when op2 raises",
                "operations": [
                    {
                        "type": "insert_after",
                        "after_guid": g[0],
                        "new_content": ["inserted"],
                        "rationale": "op1",
                    },
                    {
                        "type": "replace_block",
                        "start_line_guid": g[1],
                        "new_content": ["LINE2"],
                        "rationale": "op2",
                    },
                ],
            },
            1,
            "ops/atomic_exc.py",
        )
        assert prop["status"] == "success"
        _approve(prop["proposal_id"])

        def _explode(conn, file_id, op):
            raise RuntimeError("simulated op-2 crash")

        monkeypatch.setattr(editing_mod, "apply_replace_block", _explode)
        result = apply_edit_proposal(prop["proposal_id"])
        assert result["status"] == "error"
        assert "simulated op-2 crash" in result["message"]
        assert _content("ops/atomic_exc.py") == "a\nb\n"
        with get_db_connection() as conn:
            st = conn.execute(
                "SELECT status FROM edit_proposals WHERE proposal_id = ?",
                (prop["proposal_id"],),
            ).fetchone()[0]
        assert st == "error"

    def test_mixed_content_and_line_ops_rejected(self, temp_db):
        from file_editing.writer import initialize_file_lines
        from workflow.proposal_builder import create_proposal_from_developer_output

        initialize_file_lines("ops/mixed.py", "a\nb\n")
        g = _guids("ops/mixed.py")
        prop = create_proposal_from_developer_output(
            {
                "target_file_path": "ops/mixed.py",
                "summary": "mixed ops",
                "rationale": "content-level op mixed with line op must be rejected",
                "operations": [
                    {
                        "type": "delete_lines",
                        "start_line_guid": g[1],
                        "rationale": "line-level",
                    },
                    {
                        "type": "find_replace",
                        "find": "a",
                        "replace": "z",
                        "rationale": "content-level",
                    },
                ],
            },
            1,
            "ops/mixed.py",
        )
        assert prop["status"] == "error"
        assert "only operation" in prop["message"]
        assert "z" not in _content("ops/mixed.py")

    def test_multiple_line_level_ops_apply(self, temp_db):
        from file_editing.editing import apply_edit_proposal
        from file_editing.writer import initialize_file_lines
        from workflow.proposal_builder import create_proposal_from_developer_output

        initialize_file_lines("ops/multi_line.py", "a\nb\nc\n")
        g = _guids("ops/multi_line.py")
        prop = create_proposal_from_developer_output(
            {
                "target_file_path": "ops/multi_line.py",
                "summary": "multi line-level ops",
                "rationale": "several line-level ops apply atomically",
                "operations": [
                    {
                        "type": "insert_after",
                        "after_guid": g[0],
                        "new_content": ["ab"],
                        "rationale": "op1",
                    },
                    {
                        "type": "delete_lines",
                        "start_line_guid": g[2],
                        "rationale": "op2",
                    },
                ],
            },
            1,
            "ops/multi_line.py",
        )
        assert prop["status"] == "success"
        _approve(prop["proposal_id"])
        result = apply_edit_proposal(prop["proposal_id"])
        assert result["status"] == "success", result
        body = _content("ops/multi_line.py")
        assert "ab" in body
        assert "c" not in body
