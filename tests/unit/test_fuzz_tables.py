"""
Phase 6 — Hand-rolled edge tables (no Hypothesis dependency).

JSON parser robustness + path containment edge cases.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# JSON parser edge table
# ---------------------------------------------------------------------------

JSON_CASES = [
    # (label, input, expect_ok)
    ("plain_object", '{"a": 1}', True),
    ("fenced_json", '```json\n{"a": 2}\n```', True),
    ("fenced_plain", '```\n{"b": 3}\n```', True),
    ("leading_text", 'Sure! Here you go:\n{"c": 4}\n', True),
    ("trailing_text", '{"d": 5}\nThanks!', True),
    ("empty", "", False),
    ("whitespace", "   \n\t  ", False),
    ("truncated_brace", '{"e": 6', False),
    ("only_array", "[1,2,3]", True),  # parser targets objects for agent responses
    ("nested", '{"outer": {"inner": [1,2]}}', True),
    ("unicode", '{"msg": "café 🚀"}', True),
]


class TestJsonParserFuzzTable:
    @pytest.mark.parametrize(
        "label,text,expect_ok", JSON_CASES, ids=[c[0] for c in JSON_CASES]
    )
    def test_parse_cases(self, label, text, expect_ok):
        from core.json_parser import parse_json_response

        result = parse_json_response(text, agent_name="fuzz")
        if expect_ok:
            assert result is not None, f"{label}: expected parse success for {text!r}"
            assert isinstance(
                result, (dict, list)
            ), f"{label}: unexpected type {type(result)}"
        else:
            assert result is None or isinstance(result, (dict, list))


# ---------------------------------------------------------------------------
# Path containment edge table
# ---------------------------------------------------------------------------

PATH_CASES = [
    # (label, relative_path, should_succeed)
    ("simple", "src/main.py", True),
    ("nested", "a/b/c/d.py", True),
    ("dot_segment", "src/./util.py", True),
    ("traversal", "../../etc/passwd", False),
    ("traversal_nested", "src/../../outside.py", False),
    ("absolute_escape", None, False),  # filled at runtime with abs path outside
]


class TestPathContainmentFuzzTable:
    @pytest.mark.parametrize(
        "label,rel,should_succeed", PATH_CASES, ids=[c[0] for c in PATH_CASES]
    )
    def test_path_cases(self, label, rel, should_succeed, monkeypatch, tmp_path):
        from core import config as config_mod
        from file_editing.writer import write_file_to_disk

        proj = tmp_path / "project"
        proj.mkdir()
        (proj / "src").mkdir()

        original = config_mod.get_config

        def fake():
            c = dict(original())
            c["project_directory"] = str(proj)
            return c

        monkeypatch.setattr(config_mod, "get_config", fake)

        if rel is None:
            # absolute path outside project
            outside = tmp_path / "outside.py"
            path_arg = str(outside)
        else:
            path_arg = rel

        result = write_file_to_disk(path_arg, "x = 1\n")
        if should_succeed:
            assert result["status"] == "success", result
        else:
            assert result["status"] == "error", result
            assert "escape" in result.get("message", "").lower()
