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
