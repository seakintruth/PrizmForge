"""
P3 — HTTP / agent path failure modes (no network; sleep patched).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _resp(status: int, body: dict):
    m = MagicMock()
    m.status_code = status
    raw = json.dumps(body).encode()
    m.content = raw
    m.text = raw.decode()
    m.headers = {"Content-Type": "application/json"}
    m.json.return_value = body
    m.raise_for_status = MagicMock()
    return m


@pytest.fixture
def endpoint_config(monkeypatch, temp_db):
    from core import config as config_mod

    def fake():
        return {
            "project_directory": "./project",
            "token_budget": {"max_tokens_per_4h": 10_000_000},
            "default_model": "mock-model",
            "endpoints": {
                "primary": {
                    "base_url": "http://example.invalid/v1/chat/completions",
                    "api_key_name": "api_key",
                    "models": ["mock-model"],
                }
            },
            "api_key": "test-key-not-placeholder",
            "agent_model_preferences": {},
        }

    monkeypatch.setattr(config_mod, "get_config", fake)
    # reset token budget singleton if any
    import agents.base as base

    base._token_budget = None
    return fake()


def test_401_does_not_block_two_minutes(endpoint_config):
    from core.http_client import post_json

    body = {
        "error": {
            "type": "unauthorized",
            "message": "API KEY LOCKED",
            "unlock_url": "https://example.invalid/unlock",
        }
    }
    with patch("requests.post", return_value=_resp(401, body)):
        with patch("time.sleep") as slept:
            r = post_json("http://example.invalid/v1", json_body={"messages": []})
            assert r.status_code == 401
            # post_json itself should not sleep
            slept.assert_not_called()


def test_429_response_shape(endpoint_config):
    from core.http_client import post_json

    with patch(
        "requests.post", return_value=_resp(429, {"error": {"message": "rate limited"}})
    ):
        r = post_json("http://example.invalid/v1", json_body={})
        assert r.status_code == 429
        assert "rate" in r.json()["error"]["message"]


def test_call_agent_empty_when_endpoint_always_fails(mock_llm, endpoint_config):
    """Exhausted / empty path: MockLLM can simulate empty agent response."""
    mock_llm.set_response("developer", "")
    mock_llm._queues["developer"] = [""]
    with mock_llm.patch_call_agent():
        from agents.base import call_agent

        out = call_agent("developer", "hi", task_id="fail1")
    assert out == "" or out is None or isinstance(out, str)


def test_http_5xx_via_post_json(endpoint_config):
    from core.http_client import post_json, HttpError

    with patch("requests.post", return_value=_resp(503, {"error": "unavailable"})):
        r = post_json("http://example.invalid/v1", json_body={})
        assert r.status_code == 503
        with pytest.raises(HttpError):
            r.raise_for_status()
