"""Unit coverage for file_editing.edit_payload dataclasses and validation."""

from __future__ import annotations

import json

import pytest

from file_editing.edit_payload import (
    DeleteLines,
    EditPayload,
    FindReplace,
    FullReplace,
    InsertAfter,
    ReplaceBlock,
)


def test_replace_block_coerces_string_new_content():
    op = ReplaceBlock(start_line_guid="g1", new_content="single line", rationale="enough text")
    assert op.new_content == ["single line"]
    assert op.type == "replace_block"


def test_replace_block_rejects_bad_new_content_type():
    with pytest.raises(ValueError, match="new_content"):
        ReplaceBlock(start_line_guid="g1", new_content=123, rationale="enough text")


def test_insert_after_coerces_string():
    op = InsertAfter(after_guid=None, new_content="x", rationale="enough text")
    assert op.new_content == ["x"]


def test_find_replace_requires_non_empty_find():
    with pytest.raises(ValueError, match="find"):
        FindReplace(find="", replace="x", rationale="enough text")


def test_find_replace_rejects_negative_count():
    with pytest.raises(ValueError, match="count"):
        FindReplace(find="a", replace="b", count=-1, rationale="enough text")


def test_full_replace_joins_list_lines():
    op = FullReplace(new_content=["a = 1", "b = 2"], rationale="enough text")
    assert "a = 1" in op.new_content
    assert "b = 2" in op.new_content


def test_full_replace_rejects_blank():
    with pytest.raises(ValueError, match="empty"):
        FullReplace(new_content="   ", rationale="enough text")


def test_rationale_auto_expand_when_short():
    op = DeleteLines(start_line_guid="g1", rationale="short")
    assert len(op.rationale) >= 10


def test_rationale_rejects_too_long():
    with pytest.raises(ValueError, match="500"):
        DeleteLines(start_line_guid="g1", rationale="x" * 501)


def test_edit_payload_model_validate_find_replace():
    data = {
        "target_file_path": "a.py",
        "summary": "rename symbol",
        "rationale": "consistent naming across module",
        "operations": [{"type": "find_replace", "find": "OLD", "replace": "NEW"}],
    }
    payload = EditPayload.model_validate(data)
    assert payload.target_file_path == "a.py"
    assert len(payload.operations) == 1
    assert payload.operations[0].type == "find_replace"
    assert payload.operations[0].find == "OLD"


def test_edit_payload_model_validate_json_roundtrip():
    data = {
        "target_file_path": "b.py",
        "summary": "insert block",
        "rationale": "add helper after header",
        "operations": [
            {
                "type": "insert_after",
                "after_guid": "g0",
                "new_content": ["def helper():", "    return 1"],
            }
        ],
    }
    payload = EditPayload.model_validate_json(json.dumps(data))
    dumped = json.loads(payload.model_dump_json())
    assert dumped["target_file_path"] == "b.py"
    assert dumped["operations"][0]["type"] == "insert_after"


def test_edit_payload_unknown_op_type():
    data = {
        "target_file_path": "a.py",
        "summary": "bad op",
        "rationale": "should fail validation",
        "operations": [{"type": "teleport_block", "start_line_guid": "g1"}],
    }
    with pytest.raises(ValueError, match="Unknown operation type"):
        EditPayload.model_validate(data)


def test_edit_payload_short_summary_rejected():
    with pytest.raises(ValueError, match="summary"):
        EditPayload(
            target_file_path="a.py",
            summary="x",
            rationale="long enough rationale",
            operations=[],
        )


def test_edit_payload_auto_rationale_on_ops():
    data = {
        "target_file_path": "a.py",
        "summary": "delete lines",
        "rationale": "remove dead code block",
        "operations": [{"type": "delete_lines", "start_line_guid": "g1"}],
    }
    payload = EditPayload.model_validate(data)
    assert payload.operations[0].rationale  # auto-filled
