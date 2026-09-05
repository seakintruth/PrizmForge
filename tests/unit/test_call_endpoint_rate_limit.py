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
from typing import ClassVar
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
            status=SimpleNamespace(value=EndpointStatus.HEALTHY.value),
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


def test_429_with_invalid_retry_after_header_defaults_120(call_endpoint_env, monkeypatch):
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
    # Invalid header falls back to the 429 status default (120s)
    assert sleeps[0] == 120


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
    # ROADMAP §6.2: the dump is printed once when the latch is set, not on
    # every skip. A skipped call shows a compact one-liner instead.
    assert "s left" in out
    assert "Last HTTP dump from when this latch was set:" not in out
    assert "body: prior" not in out
    assert answer is None
    assert sleeps[0] == 120  # 272s wait clamped to the 30..120 backoff window


class _LatchesAfterFailureHealth(SimpleNamespace):
    def __init__(self):
        super().__init__(
            parked=[],
            _latched=False,
            status=SimpleNamespace(value="rate_limited"),
        )

    def is_available(self):
        return not self._latched

    def time_until_available(self):
        return 272 if self._latched else 0

    def mark_success(self):
        self._latched = False

    def mark_failure(self, status, cooldown_minutes=None, **kwargs):
        self._latched = True
        self.parked.append((status, cooldown_minutes))


def test_429_dump_prints_once_per_latch_then_skip_is_one_line(call_endpoint_env, capfd):
    """ROADMAP §6.2: the HTTP dump appears once when the latch is SET; a later
    call under the same latch prints only the compact one-liner (no reprint)."""
    base = call_endpoint_env
    health = _LatchesAfterFailureHealth()
    fake = _FakeEndpoint()
    fake.health = health
    manager = _FakeManager()
    manager.endpoints = {"primary": fake}

    scripted = [
        _resp(429, {"error": {"message": "free-models-per-day daily quota. Add 10 credits to unlock more."}}),
    ]

    sleeps: list[float] = []
    with patch.object(base, "get_endpoint_manager", lambda: manager):
        with patch("agents.base.post_json", side_effect=scripted):
            with patch("time.sleep", side_effect=sleeps.append):
                # 1st call: 429 sets the latch -> dump prints once.
                ans1, _ = base.call_endpoint([{"role": "user", "content": "hi"}], model="mock-model")
                # 2nd call: same latch -> skip path, no dump reprint.
                ans2, _ = base.call_endpoint([{"role": "user", "content": "hi"}], model="mock-model")

    assert ans1 is None and ans2 is None
    assert health.parked  # 429 recorded a failure (latch set)
    out = capfd.readouterr().out
    assert "free-models-per-day" in out  # the dump did print on the set
    assert out.count("HTTP 429") == 1  # ...one dump, once, across both calls
    assert "Last HTTP dump from when this latch was set:" not in out
    assert "skipped (LOCAL health latch" in out  # second call used the one-liner


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


class _FallbackManager(_FakeManager):
    def __init__(self):
        super().__init__()
        self.fallback_ep = _FakeEndpoint()
        self.fallback_ep.name = "fallback"

    def get_fallback_model(self, endpoint):
        return ("fallback-model", self.fallback_ep)


# =====================================================================
# §0.0 short retry-after 429/503 policy
# =====================================================================


def test_503_retry_after_90_retries_same_and_succeeds(call_endpoint_env):
    base = call_endpoint_env
    scripted = [
        _resp(503, {}, headers={"Retry-After": "90"}),
        _resp(200, {"choices": [{"message": {"content": "recovered 503"}}]}),
    ]

    sleeps: list[float] = []
    with patch("agents.base.post_json", side_effect=scripted):
        with patch("time.sleep", side_effect=sleeps.append):
            answer, _ = base.call_endpoint([{"role": "user", "content": "hi"}], model="mock-model")

    assert answer == "recovered 503"
    assert len(sleeps) == 1
    assert sleeps[0] == 90  # honored advertised wait; retry succeeded same endpoint


def test_429_retry_after_42534_falls_back_no_sleep(call_endpoint_env, capfd):
    base = call_endpoint_env
    manager = _FallbackManager()
    scripted = [
        _resp(429, {}, headers={"Retry-After": "42534"}),
        _resp(200, {"choices": [{"message": {"content": "fb ok 429"}}]}),
    ]

    sleeps: list[float] = []
    with patch.object(base, "get_endpoint_manager", lambda: manager):
        with patch("agents.base.post_json", side_effect=scripted):
            with patch("time.sleep", side_effect=sleeps.append):
                answer, _ = base.call_endpoint([{"role": "user", "content": "hi"}], model="mock-model")

    assert answer == "fb ok 429"
    assert sleeps == []  # no long sleep
    assert "cooldown too long" in capfd.readouterr().out


def test_503_retry_after_600_retries_once(call_endpoint_env):
    base = call_endpoint_env
    scripted = [
        _resp(503, {}, headers={"Retry-After": "600"}),
        _resp(200, {"choices": [{"message": {"content": "recovered 600"}}]}),
    ]

    sleeps: list[float] = []
    with patch("agents.base.post_json", side_effect=scripted):
        with patch("time.sleep", side_effect=sleeps.append):
            answer, _ = base.call_endpoint([{"role": "user", "content": "hi"}], model="mock-model")

    assert answer == "recovered 600"
    assert sleeps == [600]


def test_503_retry_after_601_falls_back_no_wait(call_endpoint_env, capfd):
    base = call_endpoint_env
    manager = _FallbackManager()
    scripted = [
        _resp(503, {}, headers={"Retry-After": "601"}),
        _resp(200, {"choices": [{"message": {"content": "fb ok 601"}}]}),
    ]

    sleeps: list[float] = []
    with patch.object(base, "get_endpoint_manager", lambda: manager):
        with patch("agents.base.post_json", side_effect=scripted):
            with patch("time.sleep", side_effect=sleeps.append):
                answer, _ = base.call_endpoint([{"role": "user", "content": "hi"}], model="mock-model")

    assert answer == "fb ok 601"
    assert sleeps == []
    assert "cooldown too long" in capfd.readouterr().out


def test_503_no_header_default_300_retries_once(call_endpoint_env):
    base = call_endpoint_env
    scripted = [
        _resp(503, {}, headers={}),
        _resp(200, {"choices": [{"message": {"content": "recovered default 300"}}]}),
    ]

    sleeps: list[float] = []
    with patch("agents.base.post_json", side_effect=scripted):
        with patch("time.sleep", side_effect=sleeps.append):
            answer, _ = base.call_endpoint([{"role": "user", "content": "hi"}], model="mock-model")

    assert answer == "recovered default 300"
    assert sleeps == [300]


def test_503_retry_then_second_503_falls_back(call_endpoint_env, capfd):
    base = call_endpoint_env
    manager = _FallbackManager()
    scripted = [
        _resp(503, {}, headers={"Retry-After": "90"}),
        _resp(503, {}, headers={"Retry-After": "90"}),
        _resp(200, {"choices": [{"message": {"content": "fb ok retry"}}]}),
    ]

    sleeps: list[float] = []
    with patch.object(base, "get_endpoint_manager", lambda: manager):
        with patch("agents.base.post_json", side_effect=scripted):
            with patch("time.sleep", side_effect=sleeps.append):
                answer, _ = base.call_endpoint([{"role": "user", "content": "hi"}], model="mock-model")

    assert answer == "fb ok retry"
    assert len(sleeps) == 1  # one 90s wait, then the same-endpoint retry failed -> fallback
    assert "same-endpoint retry exhausted" in capfd.readouterr().out


def test_503_http_date_retry_after_honored(call_endpoint_env):
    base = call_endpoint_env
    later = time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime(time.time() + 45))
    scripted = [
        _resp(503, {}, headers={"Retry-After": later}),
        _resp(200, {"choices": [{"message": {"content": "recovered http-date"}}]}),
    ]

    sleeps: list[float] = []
    with patch("agents.base.post_json", side_effect=scripted):
        with patch("time.sleep", side_effect=sleeps.append):
            answer, _ = base.call_endpoint([{"role": "user", "content": "hi"}], model="mock-model")

    assert answer == "recovered http-date"
    assert 40 <= sleeps[0] <= 60


def test_500_retries_with_legacy_backoff_not_503_default(call_endpoint_env):
    """500 must use the OTHER-5xx exponential backoff, not fall through to
    raise_for_status()/UNAVAILABLE, and not pick up the 503 default 300s wait."""
    base = call_endpoint_env
    scripted = [
        _resp(500, {}),
        _resp(200, {"choices": [{"message": {"content": "recovered 500"}}]}),
    ]

    sleeps: list[float] = []
    with patch("agents.base.post_json", side_effect=scripted):
        with patch("time.sleep", side_effect=sleeps.append):
            answer, _ = base.call_endpoint([{"role": "user", "content": "hi"}], model="mock-model")

    assert answer == "recovered 500"
    assert len(sleeps) == 1
    # Legacy backoff is 2**attempt + fractional jitter -> [1.0, 2.0), NOT the
    # 503 default 300s (or any recorded model failure before the retry).
    assert 1.0 <= sleeps[0] < 2.0


def test_502_falls_back_after_retries_exhausted(call_endpoint_env, capfd):
    """Other-5xx codes (502) exhaust per-attempt backoff then fall back rather
    than being swallowed as UNAVAILABLE by raise_for_status()."""
    base = call_endpoint_env
    manager = _FallbackManager()
    scripted = [
        _resp(502, {}),
        _resp(502, {}),
        _resp(502, {}),
        _resp(200, {"choices": [{"message": {"content": "fb ok 502"}}]}),
    ]

    sleeps: list[float] = []
    with patch.object(base, "get_endpoint_manager", lambda: manager):
        with patch("agents.base.post_json", side_effect=scripted):
            with patch("time.sleep", side_effect=sleeps.append):
                answer, _ = base.call_endpoint([{"role": "user", "content": "hi"}], model="mock-model")

    assert answer == "fb ok 502"
    # Attempts 0/1 sleep the legacy backoff; attempt 2 (last) falls back.
    assert len(sleeps) == 2
    assert all(1.0 <= s < 8.0 for s in sleeps)
    out = capfd.readouterr().out
    assert "Server unreachable. Falling back to" in out
    assert "unexpected error" not in out


def test_concurrent_agents_observe_shared_latch_bound_backoff(call_endpoint_env, capfd):
    """While a 503 latch (~590s) is active, another agent observes the shared
    latch and sleeps a bounded backoff, not the full remaining wait."""
    base = call_endpoint_env
    fake = _FakeEndpoint()
    fake.health = SimpleNamespace(
        is_available=lambda: False,
        status=SimpleNamespace(value="server_error"),
        time_until_available=lambda: 590,
        last_http_dump=None,
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
    assert sleeps == [120]  # 590s remaining clamped to the 30..120 window
    assert "LOCAL health latch" in capfd.readouterr().out


def test_latched_primary_falls_back_to_healthy_endpoint(call_endpoint_env, capfd):
    """ROADMAP §6.1: a latched primary must fall back to a healthy endpoint
    (same path as a live POST) instead of printing 'no alternate' — the skip
    branch only reports no-alternate once EVERY candidate is latched."""
    base = call_endpoint_env
    primary_latched = _FakeEndpoint()
    primary_latched.health = SimpleNamespace(
        is_available=lambda: False,
        status=SimpleNamespace(value="server_error"),
        time_until_available=lambda: 272,
        last_http_dump=None,
        mark_success=lambda: None,
        mark_failure=lambda *a, **k: None,
    )
    fallback_healthy = _FakeEndpoint()
    fallback_healthy.name = "fallback"

    class _SkipFallbackManager:
        endpoints: ClassVar[dict] = {"primary": primary_latched, "fallback": fallback_healthy}

        def normalize_model_reference(self, raw):
            if raw == "fallback-model":
                return SimpleNamespace(endpoint_name="fallback", model_name="fallback-model")
            return SimpleNamespace(endpoint_name="primary", model_name="mock-model")

        def validate_model(self, ref):
            return ref.split("/")[-1]

        def build_payload(self, endpoint, model_name, messages, max_tokens, temperature):
            return {"model": model_name, "messages": messages, "max_tokens": max_tokens or 512, "temperature": temperature or 0.0}

        def get_api_key(self, endpoint):
            return "test-key-not-placeholder"

        def get_fallback_model(self, endpoint):
            if endpoint.name == "primary":
                return ("fallback-model", fallback_healthy)
            return None  # fallback is healthy; no further fallback

    scripted = [
        _resp(200, {"choices": [{"message": {"content": "fb ok via skip"}}]}),
    ]

    sleeps: list[float] = []
    with patch.object(base, "get_endpoint_manager", lambda: _SkipFallbackManager()):
        with patch("agents.base.post_json", side_effect=scripted):
            with patch("time.sleep", side_effect=sleeps.append):
                answer, _ = base.call_endpoint([{"role": "user", "content": "hi"}], model="mock-model")

    assert answer == "fb ok via skip"
    assert sleeps == []  # healthy fallback => no cooldown sleep
    out = capfd.readouterr().out
    assert "LOCAL health latch" in out
    assert "→ Falling back to fallback/fallback-model" in out
    assert "No alternate endpoints available" not in out


def test_successful_retry_does_not_record_failure(call_endpoint_env):
    base = call_endpoint_env
    outcomes: list[dict] = []

    def _capture(*args, **kwargs):
        outcomes.append({"args": args, "kwargs": kwargs})

    scripted = [
        _resp(503, {}, headers={"Retry-After": "5"}),
        _resp(200, {"choices": [{"message": {"content": "ok after 503"}}]}),
    ]
    sleeps: list[float] = []
    with patch.object(base, "record_model_outcome", side_effect=_capture):
        with patch("agents.base.post_json", side_effect=scripted):
            with patch("time.sleep", side_effect=sleeps.append):
                answer, _ = base.call_endpoint([{"role": "user", "content": "hi"}], model="mock-model")

    assert answer == "ok after 503"
    assert len(outcomes) == 1
    assert outcomes[0]["kwargs"].get("ok") is True
    assert all(kw.get("ok") is not False for kw in outcomes[0] for kw in [outcomes[0]["kwargs"]])


def test_token_budget_overflow_no_fallback_records_failure(call_endpoint_env, monkeypatch):
    """Soak10 follow-up: the token-budget carve-out must record a model-health
    failure so the shell developer can classify (not guess) the None return."""
    base = call_endpoint_env
    outcomes: list[dict] = []

    class _NoBudget:
        def can_spend(self, tokens):
            return False

    monkeypatch.setattr(base, "get_token_budget", lambda: _NoBudget())
    monkeypatch.setattr(base, "record_model_outcome", lambda model_ref, endpoint=None, **kw: outcomes.append({"model": model_ref, **kw}))

    answer, _ = base.call_endpoint([{"role": "user", "content": "hi"}], model="mock-model")

    assert answer is None
    assert outcomes and outcomes[0]["ok"] is False
    assert outcomes[0]["kind"] == "token_budget"


def test_all_parked_no_alternate_records_failure(call_endpoint_env, monkeypatch, capfd):
    """Soak10 follow-up: the all-latched no-alternate path must record a
    model-health failure (this was the silent None-return the soak hit)."""
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

    outcomes: list[dict] = []
    monkeypatch.setattr(base, "record_model_outcome", lambda model_ref, endpoint=None, **kw: outcomes.append({"model": model_ref, **kw}))

    sleeps: list[float] = []
    with patch.object(base, "get_endpoint_manager", lambda: manager):
        with patch("time.sleep", side_effect=sleeps.append):
            answer, _ = base.call_endpoint([{"role": "user", "content": "hi"}], model="mock-model")

    assert answer is None
    assert outcomes and outcomes[0]["ok"] is False
    assert outcomes[0]["kind"] == "no_alternate_endpoint"
    assert "No alternate endpoints available" in capfd.readouterr().out
