"""Developer edit payload validation matrix."""

from __future__ import annotations

import json

from core.edit_response_validator import EditFailureReason, validate_developer_edit_response


def test_empty_response():
    r = validate_developer_edit_response("")
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


def test_full_replace_valid():
    payload = {"target_file_path": "a.py", "new_content": "print(1)\n", "summary": "x"}
    r = validate_developer_edit_response(json.dumps(payload))
    assert r.is_valid is True
    assert r.detected_mode == "full_replace"


def test_full_replace_missing_content():
    payload = {"target_file_path": "a.py", "new_content": "   ", "summary": "x"}
    r = validate_developer_edit_response(json.dumps(payload))
    assert r.is_valid is False
    assert r.reason == EditFailureReason.FULL_REPLACE_MISSING_CONTENT


def test_find_replace_top_level():
    payload = {"target_file_path": "a.py", "find": "OLD", "replace": "NEW"}
    r = validate_developer_edit_response(json.dumps(payload))
    assert r.is_valid is True
    assert r.detected_mode == "find_replace"


def test_operations_find_replace():
    payload = {
        "target_file_path": "a.py",
        "summary": "rename",
        "rationale": "consistent naming",
        "operations": [{"type": "find_replace", "find": "OLD", "replace": "NEW"}],
    }
    r = validate_developer_edit_response(json.dumps(payload))
    assert r.is_valid is True
    assert r.detected_mode in ("guid", "find_replace") or r.data is not None


def test_empty_operations():
    payload = {"target_file_path": "a.py", "summary": "noop", "operations": []}
    r = validate_developer_edit_response(json.dumps(payload))
    assert r.is_valid is False
    assert r.reason == EditFailureReason.EMPTY_OPERATIONS


def test_markdown_fenced_json_accepted():
    inner = {"target_file_path": "a.py", "new_content": "x = 1\n", "summary": "ok"}
    text = "```json\n" + json.dumps(inner) + "\n```"
    r = validate_developer_edit_response(text)
    assert r.is_valid is True
    assert r.detected_mode == "full_replace"
