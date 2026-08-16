"""Full unit matrix for core.edit_response_validator."""

from __future__ import annotations

import json

from core.edit_response_validator import (
    EditFailureReason,
    EditValidationResult,
    validate_developer_edit_response,
)


def test_empty_response():
    r = validate_developer_edit_response("")
    assert r.is_valid is False
    assert r.should_fallback is True
    assert r.reason == EditFailureReason.EMPTY_RESPONSE


def test_whitespace_only_response():
    r = validate_developer_edit_response("   \n\t  ")
    assert r.is_valid is False
    assert r.reason == EditFailureReason.EMPTY_RESPONSE


def test_no_json():
    r = validate_developer_edit_response("sorry I cannot help with that")
    assert r.is_valid is False
    assert r.reason == EditFailureReason.NO_JSON


def test_invalid_json():
    r = validate_developer_edit_response('{"operations": [')
    assert r.is_valid is False
    assert r.reason in (EditFailureReason.INVALID_JSON, EditFailureReason.NO_JSON)


def test_root_scalar_unknown():
    # JSON object required after extraction; a lone number is not an object span
    r = validate_developer_edit_response("42")
    assert r.is_valid is False
    assert r.reason in (EditFailureReason.NO_JSON, EditFailureReason.UNKNOWN_STRUCTURE)


def test_full_replace_valid():
    payload = {"target_file_path": "a.py", "new_content": "print(1)\n", "summary": "x"}
    r = validate_developer_edit_response(json.dumps(payload))
    assert r.is_valid is True
    assert r.should_fallback is False
    assert r.detected_mode == "full_replace"
    assert r.data["new_content"].startswith("print")


def test_full_replace_missing_content():
    payload = {"target_file_path": "a.py", "new_content": "   ", "summary": "x"}
    r = validate_developer_edit_response(json.dumps(payload))
    assert r.is_valid is False
    assert r.reason == EditFailureReason.FULL_REPLACE_MISSING_CONTENT


def test_full_replace_null_content():
    payload = {"target_file_path": "a.py", "new_content": None, "summary": "x"}
    r = validate_developer_edit_response(json.dumps(payload))
    assert r.is_valid is False
    assert r.reason == EditFailureReason.FULL_REPLACE_MISSING_CONTENT


def test_find_replace_top_level():
    payload = {"target_file_path": "a.py", "find": "OLD", "replace": "NEW"}
    r = validate_developer_edit_response(json.dumps(payload))
    assert r.is_valid is True
    assert r.detected_mode == "find_replace"


def test_find_replace_replacements_list():
    payload = {
        "target_file_path": "a.py",
        "replacements": [{"find": "a", "replace": "b"}],
    }
    r = validate_developer_edit_response(json.dumps(payload))
    assert r.is_valid is True
    assert r.detected_mode == "find_replace"


def test_diff_mode_valid():
    payload = {
        "target_file_path": "a.py",
        "diff": "--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-x\n+y\n",
        "summary": "change",
    }
    r = validate_developer_edit_response(json.dumps(payload))
    assert r.is_valid is True
    assert r.detected_mode == "diff"


def test_diff_mode_blank_rejected_as_no_ops():
    payload = {"target_file_path": "a.py", "diff": "   ", "summary": "x"}
    r = validate_developer_edit_response(json.dumps(payload))
    assert r.is_valid is False
    assert r.reason == EditFailureReason.NO_OPERATIONS


def test_operations_find_replace():
    payload = {
        "target_file_path": "a.py",
        "summary": "rename",
        "rationale": "consistent naming",
        "operations": [{"type": "find_replace", "find": "OLD", "replace": "NEW"}],
    }
    r = validate_developer_edit_response(json.dumps(payload))
    assert r.is_valid is True
    assert r.detected_mode == "guid"


def test_empty_operations():
    payload = {"target_file_path": "a.py", "summary": "noop", "operations": []}
    r = validate_developer_edit_response(json.dumps(payload))
    assert r.is_valid is False
    assert r.reason == EditFailureReason.EMPTY_OPERATIONS


def test_operations_not_a_list():
    payload = {"target_file_path": "a.py", "operations": {"type": "find_replace"}}
    r = validate_developer_edit_response(json.dumps(payload))
    assert r.is_valid is False
    assert r.reason == EditFailureReason.NO_OPERATIONS


def test_operations_without_type():
    payload = {"target_file_path": "a.py", "operations": [{"find": "a", "replace": "b"}]}
    r = validate_developer_edit_response(json.dumps(payload))
    assert r.is_valid is False
    assert r.reason == EditFailureReason.UNKNOWN_STRUCTURE


def test_single_top_level_operation():
    payload = {
        "type": "replace_block",
        "start_line_guid": "g1",
        "new_content": ["x = 1"],
        "rationale": "bump",
    }
    r = validate_developer_edit_response(json.dumps(payload))
    assert r.is_valid is True
    assert r.detected_mode == "guid"


def test_root_list_of_operations_normalized():
    ops = [
        {
            "type": "find_replace",
            "find": "OLD",
            "replace": "NEW",
            "target_file_path": "mod.py",
            "rationale": "rename",
        }
    ]
    r = validate_developer_edit_response(json.dumps(ops))
    assert r.is_valid is True
    assert r.detected_mode == "guid"
    assert r.data["target_file_path"] == "mod.py"
    assert len(r.data["operations"]) == 1


def test_markdown_fenced_json_accepted():
    inner = {"target_file_path": "a.py", "new_content": "x = 1\n", "summary": "ok"}
    text = "```json\n" + json.dumps(inner) + "\n```"
    r = validate_developer_edit_response(text)
    assert r.is_valid is True
    assert r.detected_mode == "full_replace"


def test_preamble_then_json_object():
    inner = {"target_file_path": "a.py", "find": "a", "replace": "b"}
    text = "Sure, here is the edit:\n" + json.dumps(inner)
    r = validate_developer_edit_response(text)
    assert r.is_valid is True
    assert r.detected_mode == "find_replace"


def test_result_dataclass_defaults():
    r = EditValidationResult(is_valid=True)
    assert r.reason is None
    assert r.should_fallback is False
