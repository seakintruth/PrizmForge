"""LLM response JSON extraction / cleaning."""

from __future__ import annotations

import json

from agents.response_cleaner import clean_llm_response, extract_json_aggressively


def test_extract_plain_json():
    raw = '{"decision": "APPROVE", "reason": "ok"}'
    cleaned, err = extract_json_aggressively(raw, "reviewer")
    assert err is None
    assert cleaned is not None
    assert json.loads(cleaned)["decision"] == "APPROVE"


def test_extract_fenced_json():
    raw = 'Sure, here is the result:\n```json\n{"next_agent": "developer"}\n```\n'
    cleaned, err = extract_json_aggressively(raw, "orchestrator")
    assert err is None
    assert json.loads(cleaned)["next_agent"] == "developer"


def test_extract_with_prefix_noise():
    raw = 'Here is the JSON:\n{"operations": [{"type": "find_replace", "find": "a", "replace": "b"}]}'
    cleaned, err = extract_json_aggressively(raw, "developer")
    assert err is None
    data = json.loads(cleaned)
    assert data["operations"][0]["type"] == "find_replace"


def test_extract_empty_fails():
    cleaned, err = extract_json_aggressively("", "developer")
    assert cleaned is None
    assert err


def test_extract_no_brace_fails():
    cleaned, err = extract_json_aggressively("no json here at all", "developer")
    assert cleaned is None
    assert "brace" in err.lower() or "opening" in err.lower()


def test_clean_llm_response_returns_none_on_garbage():
    assert clean_llm_response("???", "developer") is None


def test_clean_llm_response_success():
    out = clean_llm_response('{"ok": true}', "developer")
    assert out is not None
    assert json.loads(out)["ok"] is True
