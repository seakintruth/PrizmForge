"""Full unit matrix for core.json_parser.JSONParser and convenience helpers."""

from __future__ import annotations

from core.json_parser import (
    JSONParser,
    ParseResult,
    ParseStatus,
    get_json_parser,
    parse_json_response,
)

# ---------------------------------------------------------------------------
# ParseResult helpers
# ---------------------------------------------------------------------------


def test_parse_result_success_property():
    r = ParseResult(status=ParseStatus.SUCCESS, data={"a": 1}, error=None, raw_json="{}", confidence=1.0)
    assert r.success is True
    assert r.can_resume is False


def test_parse_result_truncated_can_resume():
    r = ParseResult(status=ParseStatus.TRUNCATED, data=None, error="cut", raw_json="{", confidence=0.3)
    assert r.success is False
    assert r.can_resume is True


# ---------------------------------------------------------------------------
# Extraction strategies via JSONParser.parse
# ---------------------------------------------------------------------------


def test_parse_empty_response():
    p = JSONParser()
    r = p.parse("")
    assert r.status == ParseStatus.EMPTY
    assert r.data is None
    assert r.confidence == 0.0


def test_parse_whitespace_only():
    p = JSONParser()
    r = p.parse("   \n\t  ")
    assert r.status == ParseStatus.EMPTY


def test_parse_plain_object():
    p = JSONParser()
    raw = '{"action": "create_file", "filename": "test.py"}'
    r = p.parse(raw)
    assert r.success is True
    assert r.data["action"] == "create_file"
    assert r.confidence == 1.0


def test_parse_plain_array_as_object_wrapper_not_forced():
    """Root arrays parse successfully when expected_keys is not set."""
    p = JSONParser()
    r = p.parse('[{"type": "find_replace"}]')
    assert r.success is True
    assert isinstance(r.data, list)
    assert r.data[0]["type"] == "find_replace"


def test_extract_markdown_json_fence():
    p = JSONParser()
    raw = """Here you go:
```json
{"next_agent": "developer", "ok": true}
```
Thanks.
"""
    r = p.parse(raw)
    assert r.success is True
    assert r.data["next_agent"] == "developer"


def test_extract_generic_markdown_fence_with_json():
    p = JSONParser()
    raw = """```
{"status": "ok"}
```"""
    r = p.parse(raw)
    assert r.success is True
    assert r.data["status"] == "ok"


def test_extract_generic_markdown_fence_ignores_non_json():
    p = JSONParser()
    raw = """```
This is not JSON at all
```"""
    r = p.parse(raw)
    assert r.success is False
    assert r.status == ParseStatus.MALFORMED


def test_extract_brace_bounded_with_preamble():
    p = JSONParser()
    raw = 'Sure, here is the payload: {"decision": "APPROVE", "reason": "lgtm"} Please proceed.'
    r = p.parse(raw)
    assert r.success is True
    assert r.data["decision"] == "APPROVE"


def test_brace_matching_ignores_braces_inside_strings():
    p = JSONParser()
    raw = '{"msg": "use {curly} braces carefully", "n": 1}'
    r = p.parse(raw)
    assert r.success is True
    assert "{curly}" in r.data["msg"]
    assert r.data["n"] == 1


def test_brace_matching_with_escaped_quotes():
    p = JSONParser()
    raw = '{"path": "C:\\Users\\test", "done": true}'
    r = p.parse(raw)
    assert r.success is True
    assert r.data["done"] is True


def test_malformed_unclosed_object_is_truncated_or_malformed():
    p = JSONParser()
    raw = '{"action": "create_file", "content": "print("hello'
    r = p.parse(raw)
    assert r.success is False
    assert r.status in (ParseStatus.TRUNCATED, ParseStatus.MALFORMED)


def test_truncated_unclosed_braces_detected():
    p = JSONParser()
    raw = '{"a": 1, "b": {"c": 2'
    r = p.parse(raw)
    assert r.success is False
    assert r.status in (ParseStatus.TRUNCATED, ParseStatus.MALFORMED)


def test_ends_with_comma_looks_truncated():
    p = JSONParser()
    assert p._looks_truncated('{"a": 1,') is True


def test_balanced_object_not_truncated():
    p = JSONParser()
    assert p._looks_truncated('{"a": 1}') is False


def test_odd_quote_count_looks_truncated():
    p = JSONParser()
    assert p._looks_truncated('{"a": "unterminated') is True


# ---------------------------------------------------------------------------
# expected_keys
# ---------------------------------------------------------------------------


def test_expected_keys_all_present():
    p = JSONParser()
    r = p.parse('{"a": 1, "b": 2}', expected_keys=["a", "b"])
    assert r.success is True
    assert r.confidence == 1.0


def test_expected_keys_missing_non_strict_still_success():
    p = JSONParser()
    r = p.parse('{"a": 1}', expected_keys=["a", "b"], strict=False)
    assert r.success is True
    assert r.confidence < 1.0
    assert r.error is not None
    assert "Missing" in r.error


def test_expected_keys_missing_strict_is_malformed():
    p = JSONParser()
    r = p.parse('{"a": 1}', expected_keys=["a", "b"], strict=True)
    assert r.success is False
    assert r.status == ParseStatus.MALFORMED
    assert "Missing" in (r.error or "")


# ---------------------------------------------------------------------------
# Resume prompt
# ---------------------------------------------------------------------------


def test_build_resume_prompt_contains_context():
    p = JSONParser()
    partial = '{"action": "edit", "target": "main.py",'
    prompt = p.build_resume_prompt(partial, "Please produce an edit payload")
    assert "truncated" in prompt.lower()
    assert "continue" in prompt.lower()
    assert "main.py" in prompt


def test_build_resume_prompt_short_partial():
    p = JSONParser()
    prompt = p.build_resume_prompt("{", "do stuff")
    assert "continue" in prompt.lower()
    assert "complete" in prompt.lower()


# ---------------------------------------------------------------------------
# Convenience + singleton
# ---------------------------------------------------------------------------


def test_get_json_parser_singleton():
    a = get_json_parser()
    b = get_json_parser()
    assert a is b


def test_parse_json_response_valid():
    raw = '{"action": "create_file", "filename": "test.py"}'
    result = parse_json_response(raw)
    assert result is not None
    assert result["action"] == "create_file"


def test_parse_json_response_markdown():
    raw = """```json
{"action": "edit", "target": "main.py"}
```"""
    result = parse_json_response(raw)
    assert result is not None
    assert result["action"] == "edit"


def test_parse_json_response_malformed_returns_none():
    raw = '{"action": "create", "filename": "test.py"'  # truncated
    result = parse_json_response(raw)
    assert result is None


def test_parse_json_response_empty_returns_none():
    assert parse_json_response("") is None


def test_parse_json_response_with_auto_resume_success():
    """Truncated JSON + auto_resume callback must merge and return parsed data."""
    # Ends mid-value so _looks_truncated is True and can_resume fires
    partial = '{"status": "ok", "msg":'
    continuation = ' "done"}'

    def resume_cb(prompt: str) -> str:
        assert "truncated" in prompt.lower() or "continue" in prompt.lower()
        return continuation

    result = parse_json_response(partial, auto_resume=resume_cb, agent_name="test")
    assert result is not None, "auto_resume must produce a successful parse"
    assert result["status"] == "ok"
    assert result["msg"] == "done"


def test_parse_json_response_surrounding_text():
    raw = """Here is the response:
{"status": "ok", "message": "done"}
Please review."""
    result = parse_json_response(raw)
    assert result is not None
    assert result["status"] == "ok"
    assert result["message"] == "done"
