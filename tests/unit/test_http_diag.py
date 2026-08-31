"""HTTP error diagnostic dump — headers + body, secrets redacted."""

from __future__ import annotations

import json
from types import SimpleNamespace

from core.http_diag import extract_error_payload, format_http_error_dump


def _resp(status: int, body, headers: dict | None = None):
    text = body if isinstance(body, str) else json.dumps(body)
    return SimpleNamespace(status_code=status, headers=headers or {}, text=text)


def test_openai_style_error_dict_is_parsed():
    payload = {
        "error": {
            "message": "Error from provider (Console): Rate limit exceeded. Please try again later.",
            "type": "provider_error",
            "code": 429,
            "metadata": {"provider": "opencode"},
        }
    }
    parsed = extract_error_payload(json.dumps(payload))
    assert parsed["message"].startswith("Error from provider")
    assert parsed["code"] == 429
    assert parsed["metadata"]["provider"] == "opencode"


def test_string_error_field_is_not_dropped():
    parsed = extract_error_payload(json.dumps({"error": "slow down", "request_id": "abc"}))
    assert parsed["message"] == "slow down"
    assert "request_id" in parsed["keys"]


def test_dump_includes_status_headers_and_body():
    resp = _resp(
        429,
        {"error": {"message": "quota", "type": "rate_limit"}},
        headers={
            "Retry-After": "12",
            "x-ratelimit-remaining": "0",
            "Authorization": "Bearer secret-token",
            "x-request-id": "req-1",
        },
    )
    dump = format_http_error_dump(
        resp,
        url="https://opencode.ai/zen/v1/chat/completions",
        model="big-pickle",
        endpoint="opencode",
    )
    assert "HTTP 429" in dump
    assert "endpoint: opencode" in dump
    assert "url: https://opencode.ai/zen/v1/chat/completions" in dump
    assert "model: big-pickle" in dump
    assert "Retry-After" in dump
    assert "x-request-id" in dump
    assert "secret-token" not in dump
    assert "<redacted>" in dump
    assert "quota" in dump
    assert "body (" in dump


def test_non_json_body_still_printed():
    dump = format_http_error_dump(_resp(502, "<html>bad gateway</html>"))
    assert "HTTP 502" in dump
    assert "<html>bad gateway</html>" in dump
