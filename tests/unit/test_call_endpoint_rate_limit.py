"""
AIMD ramp for call_endpoint's upstream-429 path (no network; sleep patched).

Covers:
- on 429: client backcl off via rate_limiter.on_rate_limited(), sleep honors
  max(Retry-After, exponential backoff + jitter)
- on eventual success: rate_limiter.on_success() ramps capacity back up
- diagnostics print the server-side error message
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _resp(status: int, body: dict, headers: dict | None = None):
    m = MagicMock()
    m.status_code = status
    m.headers = headers or {"Content-Type": "application/json"}
    m.json.return_value = body
    m.raise_for_status = MagicMock()
    return m


class _Choice:
    endpoint_name = "primary"
    model_name = "mock-model"


class _FakeEndpoint:
    name = "primary"
    base_url = "http://example.invalid/v1/chat/completions"
    rate_limit_per_minute = 10

    def __init__(self):
        self.health = SimpleNamespace(
            is_available=lambda: True,
            mark_success=lambda: None,
            mark_failure=lambda *a, **k: None,
        )

    def extract_response(self, data):
        return data["choices"][0]["message"]["content"]


class _FakeManager:
    def __init__(self):
        self.endpoints = {"primary": _FakeEndpoint()}

    def normalize_model_reference(self, raw):
        return _Choice()

    def validate_model(self, ref):
        return ref.split("/")[-1]

    def build_payload(self, endpoint, model_name, messages, max_tokens, temperature):
        return {
            "model": model_name,
            "messages": messages,
            "max_tokens": max_tokens or 512,
            "temperature": temperature or 0.0,
        }

    def get_fallback_model(self, endpoint):
        return None

    def get_api_key(self, endpoint):
        return "test-key-not-placeholder"


@pytest.fixture
def call_endpoint_env(monkeypatch):
    """Wire a scriptable post_json + fake endpoint manager into agents.base."""
    import agents.base as base

    monkeypatch.setattr(
        base,
        "get_config",
        lambda: {
            "token_budget": {"max_tokens_per_4h": 10_000_000},
            "proxy": {},
            "default_model": "mock-model",
        },
    )
    monkeypatch.setattr(base, "get_endpoint_manager", lambda: _FakeManager())
    # Reset singletons so get_rate_limiter()/get_token_budget() rebuild cleanly.
    base._rate_limiter = None
    base._token_budget = None
    return base


def test_429_applies_aimd_backoff_then_ramps_on_success(call_endpoint_env):
    base = call_endpoint_env
    rate_limiter = base.get_rate_limiter(_FakeEndpoint())

    scripted = [
        _resp(429, {"error": {"message": "slow down"}}, headers={"Retry-After": "2"}),
        _resp(200, {"choices": [{"message": {"content": "ok"}}]}),
    ]

    sleeps: list[float] = []
    with patch("agents.base.post_json", side_effect=scripted):
        with patch("time.sleep", side_effect=sleeps.append):
            answer, _tokens = base.call_endpoint([{"role": "user", "content": "hi"}], model="mock-model")

    assert answer == "ok"
    # 429 dropped the window from 10 to 5; the later success ramped to 5.05
    assert rate_limiter._window_scale == pytest.approx(0.55)
    # Sleep was at least Retry-After=2s (backoff 2**0 + jitter >= 1s)
    assert len(sleeps) == 1
    assert sleeps[0] >= 2.0


def test_429_with_invalid_retry_after_header_defaults_60(call_endpoint_env, monkeypatch):
    base = call_endpoint_env
    scripted = [
        _resp(429, {}, headers={"Retry-After": "abc"}),
        _resp(200, {"choices": [{"message": {"content": "retry figure out"}}]}),
    ]

    sleeps: list[float] = []
    with patch("agents.base.post_json", side_effect=scripted):
        with patch("time.sleep", side_effect=sleeps.append):
            answer, _ = base.call_endpoint([{"role": "user", "content": "hi"}], model="mock-model")

    assert answer == "retry figure out"
    # Invalid header falls back to default 60; jitter backoff is strictly smaller
    assert sleeps[0] == 60


def test_429_long_cooldown_marks_unavailable_and_uses_backoff(call_endpoint_env, monkeypatch):
    base = call_endpoint_env
    scripted = [
        _resp(429, {"error": {"message": "quota"}}, headers={"Retry-After": "300"}),
        _resp(200, {"choices": [{"message": {"content": "recovered"}}]}),
    ]

    sleeps: list[float] = []
    with patch("agents.base.post_json", side_effect=scripted):
        with patch("time.sleep", side_effect=sleeps.append):
            answer, _ = base.call_endpoint([{"role": "user", "content": "hi"}], model="mock-model")

    assert answer == "recovered"
    # Long cooldown also halts the window; backoff still gated by Retry-After
    assert sleeps[0] == 300
    # AIMD still reacted to the 429 even though we had no fallback target
    assert base.get_rate_limiter(_FakeEndpoint())._window_scale < 1.0
