"""Unit coverage for core.response_parser.ResponseParser facade."""

from __future__ import annotations

from core.json_parser import ParseStatus
from core.response_parser import ResponseParser


def test_empty_response():
    p = ResponseParser()
    r = p.parse("")
    assert r.status == ParseStatus.EMPTY
    assert r.data is None
    assert r.confidence == 0.0


def test_whitespace_only():
    p = ResponseParser()
    r = p.parse("  \n  ")
    assert r.status == ParseStatus.EMPTY


def test_plain_json_object():
    p = ResponseParser()
    r = p.parse('{"decision": "APPROVE", "reason": "ok"}')
    assert r.success is True
    assert r.data["decision"] == "APPROVE"
    assert r.confidence == 1.0


def test_markdown_json_fence():
    p = ResponseParser()
    raw = 'Sure:\n```json\n{"next_agent": "developer"}\n```\n'
    r = p.parse(raw)
    assert r.success is True
    assert r.data["next_agent"] == "developer"


def test_generic_code_block_with_json():
    p = ResponseParser()
    raw = "```\n{\"ok\": true}\n```"
    r = p.parse(raw)
    assert r.success is True
    assert r.data["ok"] is True


def test_code_block_with_language_tag_stripped():
    p = ResponseParser()
    # Non-json language tag on first line should be dropped when content is JSON
    raw = "```python\n{\"value\": 42}\n```"
    r = p.parse(raw)
    # Either succeeds via code-block strategy after stripping tag, or via raw slice
    assert r.success is True
    assert r.data.get("value") == 42 or r.data.get("_value") is not None


def test_raw_brace_slice_with_preamble():
    p = ResponseParser()
    raw = 'Here is the result: {"status": "ok", "n": 3} Thanks.'
    r = p.parse(raw)
    assert r.success is True
    assert r.data["status"] == "ok"
    assert r.data["n"] == 3


def test_raw_array_slice():
    p = ResponseParser()
    raw = 'Items: [{"id": 1}, {"id": 2}]'
    r = p.parse(raw)
    assert r.success is True
    # Arrays are wrapped as {"_value": [...]}
    assert "_value" in r.data
    assert isinstance(r.data["_value"], list)
    assert r.data["_value"][0]["id"] == 1


def test_no_json_is_malformed():
    p = ResponseParser()
    r = p.parse("sorry I cannot help with that")
    assert r.success is False
    assert r.status == ParseStatus.MALFORMED


def test_invalid_json_inside_fences():
    p = ResponseParser()
    raw = "```json\n{not valid json}\n```"
    r = p.parse(raw)
    assert r.success is False
    assert r.status == ParseStatus.MALFORMED


def test_prefers_earliest_structure():
    """When both object and array appear, earliest start wins."""
    p = ResponseParser()
    # Object starts before array
    raw = '{"a": 1} and also [2, 3]'
    r = p.parse(raw)
    assert r.success is True
    assert r.data.get("a") == 1


def test_truncated_object_fails():
    p = ResponseParser()
    r = p.parse('{"action": "edit", "content": "print(')
    assert r.success is False
    assert r.status == ParseStatus.MALFORMED
