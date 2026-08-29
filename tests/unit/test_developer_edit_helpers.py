"""Unit tests for developer_edit helpers (no LLM)."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def test_normalize_full_replace_shape():
    from workflow.developer_edit import _normalize_payload

    data = {
        "target_file_path": "a.py",
        "new_content": "x = 1\n",
        "summary": "rewrite file",
        "rationale": "full replace normalization test case",
    }
    out = _normalize_payload(data, "full_replace", ["a.py"])
    assert "operations" in out
    assert out["operations"][0]["type"] == "full_replace"


def test_normalize_find_top_level():
    from workflow.developer_edit import _normalize_payload

    data = {"find": "OLD", "replace": "NEW", "summary": "rename ident"}
    out = _normalize_payload(data, "find_replace", ["b.py"])
    assert out["target_file_path"] == "b.py"
    assert out["operations"][0]["type"] == "find_replace"


def test_normalize_diff_shape():
    from workflow.developer_edit import _normalize_payload

    data = {
        "diff": "--- a\n+++ b\n",
        "summary": "apply patch",
        "rationale": "diff normalization helper test",
    }
    out = _normalize_payload(data, "diff", ["c.py"])
    assert out["operations"][0]["type"] == "apply_diff"


def test_normalize_bare_single_op_wraps_without_operations_key():
    # Residual P1: an LLM may return one operation's fields at the top level
    # (with a "type") and no "operations" list. It must be wrapped, never
    # dropped, so a payload cannot reach a proposal empty.
    from workflow.developer_edit import MODE_FULL_REPLACE, _normalize_payload

    data = {
        "target_file_path": "e.py",
        "summary": "create module",
        "rationale": "bare single-op shape",
        "type": "create_file",
        "initial_content": ["x = 1"],
    }
    out = _normalize_payload(data, "full_replace", ["e.py"])
    assert len(out["operations"]) == 1
    op = out["operations"][0]
    assert op["type"] == "create_file"
    assert op["initial_content"] == ["x = 1"]
    # payload-level context keys do not leak into the operation
    assert "summary" not in op
    assert "rationale" in op  # op-context field preserved for the reviewer
    assert out["_final_mode"] == MODE_FULL_REPLACE


def test_normalize_bare_apply_diff_op():
    from workflow.developer_edit import MODE_DIFF, _normalize_payload

    data = {"type": "apply_diff", "diff": "--- a\n+++ b\n", "summary": "s"}
    out = _normalize_payload(data, "diff", ["d.py"])
    assert out["operations"][0]["type"] == "apply_diff"
    assert out["_final_mode"] == MODE_DIFF


def test_normalize_payload_without_type_or_operations_stays_empty():
    # Backstop: neither a bare-op shape nor an operations list -> the empty
    # payload must be rejected downstream (EditPayload.model_validate raises).
    from file_editing.edit_payload import EditPayload
    from workflow.developer_edit import _normalize_payload

    out = _normalize_payload({"target_file_path": "z.py", "summary": "s"}, "full_replace", ["z.py"])
    assert "operations" not in out
    try:
        EditPayload.model_validate(out)
    except ValueError as e:
        assert "at least one operation" in str(e)
    else:  # pragma: no cover - backstop regressed
        raise AssertionError("empty operations must raise ValueError")
