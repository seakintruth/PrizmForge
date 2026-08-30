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
    raw = '```\n{"ok": true}\n```'
    r = p.parse(raw)
    assert r.success is True
    assert r.data["ok"] is True


def test_code_block_with_language_tag_stripped():
    p = ResponseParser()
    # Non-json language tag on first line should be dropped when content is JSON
    raw = '```python\n{"value": 42}\n```'
    r = p.parse(raw)
    assert r.success is True
    assert r.data["value"] == 42


def test_code_block_json5_tag_stripped():
    """json5/jsonc/uppercase-JSON tags are not prose; body is still parsed."""
    for tag in ["json5", "jsonc", "JSON", "c++", "javascript+json"]:
        p = ResponseParser()
        r = p.parse(f'```{tag}\n{{"value": 42}}\n```')
        assert r.success is True, tag
        assert r.data["value"] == 42, tag


def test_tagged_block_with_non_json_body_is_not_code():
    """A python-tagged fence whose body is prose must not parse as JSON."""
    p = ResponseParser()
    r = p.parse("```python\nprint('hello world')\n```")
    assert r.success is False
    assert r.status == ParseStatus.MALFORMED


def test_json_tag_with_non_json_body_is_malformed():
    p = ResponseParser()
    r = p.parse("```json\n{not valid json}\n```")
    assert r.success is False
    assert r.status == ParseStatus.MALFORMED


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
    assert r.data["_value"][1]["id"] == 2


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


def test_free_text_without_braces_is_malformed():
    """Raw extraction with no braces and no fence yields MALFORMED, not a slice."""
    p = ResponseParser()
    r = p.parse("just words here")
    assert r.success is False
    assert r.status == ParseStatus.MALFORMED


def test_prefers_earliest_structure():
    """When both object and array appear, earliest start wins."""
    p = ResponseParser()
    raw = '{"a": 1} and also [2, 3]'
    r = p.parse(raw)
    assert r.success is True
    assert r.data["a"] == 1


def test_truncated_object_fails():
    p = ResponseParser()
    r = p.parse('{"action": "edit", "content": "print(')
    assert r.success is False
    assert r.status == ParseStatus.MALFORMED
