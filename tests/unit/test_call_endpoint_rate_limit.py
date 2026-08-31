"""
AIMD ramp for call_endpoint's upstream-429 path (no network; sleep patched).

Covers:
- on 429: client back off via rate_limiter.on_rate_limited(), sleep honors
  max(Retry-After, exponential backoff + jitter)
- on eventual success: rate_limiter.on_success() ramps capacity back up
- on >= 400: the full HTTP dump (status/url/model/headers/parsed error/body)
  is printed with auth redacted and stashed on health.last_http_dump
- on a LOCAL health latch hit, the skip message says so and reprints the dump
  without calling the API
- quota vs burst: daily-quota 429s (Remaining: 0 / body keywords) park or
  sleep-to-reset instead of the short 60s hop; true bursts keep the short
  Retry-After backoff unchanged
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from core.endpoint_manager import EndpointStatus

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _resp(status: int, body: dict, headers: dict | None = None):
    m = MagicMock()
    m.status_code = status
    m.headers = headers or {"Content-Type": "application/json"}
    m.json.return_value = body
    m.raise_for_status = MagicMock()
    m.text = json.dumps(body)
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


class _RecordingHealth(SimpleNamespace):
    def __init__(self):
        super().__init__(parked=[])

    def is_available(self):
        return True

    def time_until_available(self):
        return 0

    def mark_success(self):
        pass

    def mark_failure(self, status, cooldown_minutes=None):
        self.parked.append((status, cooldown_minutes))


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


def test_429_dumps_body_and_redacts_auth(call_endpoint_env, capfd):
    base = call_endpoint_env
    scripted = [
        _resp(
            429,
            {"error": {"message": "quota", "type": "rate_limit", "metadata": {"provider": "opencode"}}},
            headers={
                "Authorization": "Bearer secret-token",
                "Retry-After": "2",
                "x-request-id": "req-1",
            },
        ),
        _resp(200, {"choices": [{"message": {"content": "ok"}}]}),
    ]

    sleeps: list[float] = []
    with patch("agents.base.post_json", side_effect=scripted):
        with patch("time.sleep", side_effect=sleeps.append):
            answer, _ = base.call_endpoint([{"role": "user", "content": "hi"}], model="mock-model")

    assert answer == "ok"
    out = capfd.readouterr().out
    assert "HTTP 429" in out
    assert "quota" in out
    assert "x-request-id" in out
    assert "<redacted>" in out
    assert "secret-token" not in out
    assert "body (" in out


def test_local_latch_skip_prints_dump_without_calling_api(call_endpoint_env, capfd):
    base = call_endpoint_env
    manager = _FakeManager()
    fake = _FakeEndpoint()
    fake.health = SimpleNamespace(
        is_available=lambda: False,
        time_until_available=lambda: 272,
        status=SimpleNamespace(value="unavailable"),
        last_http_dump="   HTTP 429\n   body: prior",
        mark_success=lambda: None,
        mark_failure=lambda *a, **k: None,
    )
    manager.endpoints = {"primary": fake}

    def boom(*args, **kwargs):
        raise AssertionError("post_json must not be called on a local health latch")

    sleeps: list[float] = []
    with patch.object(base, "get_endpoint_manager", lambda: manager):
        with patch("agents.base.post_json", side_effect=boom):
            with patch("time.sleep", side_effect=sleeps.append):
                answer, _ = base.call_endpoint([{"role": "user", "content": "hi"}], model="mock-model")

    out = capfd.readouterr().out
    assert "LOCAL health latch" in out
    assert "Not calling the API" in out
    assert "Last HTTP dump from when this latch was set:" in out
    assert "HTTP 429" in out
    assert "body: prior" in out
    assert answer is None
    assert sleeps[0] == 120  # 272s wait clamped to the 30..120 backoff window


def test_429_quota_ms_reset_parks_and_does_not_hop(call_endpoint_env, capfd):
    """Distant daily-quota reset (ms) parks the endpoint instead of the 60s hop."""
    base = call_endpoint_env
    health = _RecordingHealth()
    fake = _FakeEndpoint()
    fake.health = health
    manager = _FakeManager()
    manager.endpoints = {"primary": fake}

    reset_ms = int((time.time() + 7200) * 1000)
    scripted = [
        _resp(
            429,
            {"error": {"message": "quota"}},
            headers={
                "Retry-After": "60",
                "X-RateLimit-Limit": "50",
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(reset_ms),
            },
        )
    ]

    sleeps: list[float] = []
    with patch.object(base, "get_endpoint_manager", lambda: manager):
        with patch("agents.base.post_json", side_effect=scripted):
            with patch("time.sleep", side_effect=sleeps.append):
                answer, _ = base.call_endpoint([{"role": "user", "content": "hi"}], model="mock-model")

    assert answer is None
    assert health.parked == [(EndpointStatus.RATE_LIMITED, 15)]
    assert sleeps == []
    out = capfd.readouterr().out
    assert "Daily quota exhausted" in out
    assert "parking" in out


def test_429_quota_body_token_parks_and_does_not_hop(call_endpoint_env, capfd):
    """Body-keyword quota without a Reset header parks 15m; no 1s hop."""
    base = call_endpoint_env
    health = _RecordingHealth()
    fake = _FakeEndpoint()
    fake.health = health
    manager = _FakeManager()
    manager.endpoints = {"primary": fake}
    scripted = [
        _resp(
            429,
            {"error": {"message": "free-models-per-day daily quota. Add 10 credits to unlock more."}},
            headers={"Content-Type": "application/json"},
        )
    ]

    sleeps: list[float] = []
    with patch.object(base, "get_endpoint_manager", lambda: manager):
        with patch("agents.base.post_json", side_effect=scripted):
            with patch("time.sleep", side_effect=sleeps.append):
                answer, _ = base.call_endpoint([{"role": "user", "content": "hi"}], model="mock-model")

    assert answer is None
    assert health.parked == [(EndpointStatus.RATE_LIMITED, 15)]
    assert sleeps == []
    out = capfd.readouterr().out
    assert "Daily quota exhausted" in out
    assert "body signal" in out


def test_429_quota_short_reset_sleeps_to_reset_then_retries(call_endpoint_env, capfd):
    """Remaining==0 with Reset within 60s sleeps the remaining wait instead of parking."""
    base = call_endpoint_env
    scripted = [
        _resp(
            429,
            {"error": {"message": "quota"}},
            headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "30"},
        ),
        _resp(200, {"choices": [{"message": {"content": "recovered"}}]}),
    ]

    sleeps: list[float] = []
    with patch("agents.base.post_json", side_effect=scripted):
        with patch("time.sleep", side_effect=sleeps.append):
            answer, _ = base.call_endpoint([{"role": "user", "content": "hi"}], model="mock-model")

    assert answer == "recovered"
    assert 25 <= sleeps[0] <= 35
    assert "sleeping to reset" in capfd.readouterr().out


def test_429_burst_with_ratelimit_headers_not_quota(call_endpoint_env, capfd):
    """Remaining > 0 with no Reset header keeps the short burst backoff."""
    base = call_endpoint_env
    rate_limiter = base.get_rate_limiter(_FakeEndpoint())
    scripted = [
        _resp(
            429,
            {"error": {"message": "slow down"}},
            headers={
                "Retry-After": "2",
                "X-RateLimit-Limit": "50",
                "X-RateLimit-Remaining": "30",
            },
        ),
        _resp(200, {"choices": [{"message": {"content": "ok"}}]}),
    ]

    sleeps: list[float] = []
    with patch("agents.base.post_json", side_effect=scripted):
        with patch("time.sleep", side_effect=sleeps.append):
            answer, _ = base.call_endpoint([{"role": "user", "content": "hi"}], model="mock-model")

    assert answer == "ok"
    assert sleeps[0] >= 2.0
    assert rate_limiter._window_scale < 1.0
    assert "Daily quota exhausted" not in capfd.readouterr().out


def test_skip_path_all_parked_sleeps_bounded_backoff(call_endpoint_env, capfd):
    """Both endpoints latched: skip path sleeps a bounded backoff, no hot loop."""
    base = call_endpoint_env
    fake = _FakeEndpoint()
    fake.health = SimpleNamespace(
        is_available=lambda: False,
        status=SimpleNamespace(value="rate_limited"),
        time_until_available=lambda: 300,
        mark_success=lambda: None,
        mark_failure=lambda *a, **k: None,
    )
    manager = _FakeManager()
    manager.endpoints = {"primary": fake}

    sleeps: list[float] = []
    with patch.object(base, "get_endpoint_manager", lambda: manager):
        with patch("time.sleep", side_effect=sleeps.append):
            answer, _ = base.call_endpoint([{"role": "user", "content": "hi"}], model="mock-model")

    assert answer is None
    assert sleeps[0] == 120
    out = capfd.readouterr().out
    assert "LOCAL health latch" in out
    assert "No alternate endpoints available" in out
