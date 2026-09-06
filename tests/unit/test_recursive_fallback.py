"""ROADMAP §8.1: recursive fallback must terminate.

A-1 died with RecursionError in call_endpoint ↔ get_fallback_model ↔
is_available. These tests pin the four acceptance cases:

1. A key-locked, B healthy → one fallback, B invoked.
2. Both locked → no infinite loop.
3. A↔B budget/latch ping-pong cannot exceed depth.
4. _all_endpoints_latched / is_available do not recurse even with the
   freeze reentrancy guard forced off.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from core.endpoint_manager import EndpointHealth, EndpointManager, EndpointStatus


@pytest.fixture(autouse=True)
def _isolate_freeze_registry():
    from agents.worker_utils import set_support_frozen
    from core import endpoint_manager as epm

    epm._clear_managers_registry()
    set_support_frozen(False)
    yield
    epm._clear_managers_registry()
    set_support_frozen(False)


@pytest.fixture
def ep_config() -> dict:
    return {
        "default_endpoint": "primary",
        "_api_keys": {
            "primary": {"api_key": "primary-secret"},
            "secondary": {"api_key": "secondary-secret"},
        },
        "endpoints": {
            "primary": {
                "base_url": "http://primary.example/v1/chat/completions",
                "api_key_name": "primary_key",
                "priority": 10,
                "models": {"model-a": {"max_output_tokens": 2048}},
            },
            "secondary": {
                "base_url": "http://secondary.example/v1/chat/completions",
                "api_key_name": "api_key",
                "priority": 20,
                "models": {"model-b": {"max_output_tokens": 1024}},
            },
        },
        "fallback_settings": {"enabled": True},
    }


def _resp(status: int, body: dict, headers: dict | None = None):
    m = MagicMock()
    m.status_code = status
    m.headers = headers or {"Content-Type": "application/json"}
    m.json.return_value = body
    m.raise_for_status = MagicMock()
    m.text = json.dumps(body)
    return m


class _Health:
    def __init__(self, available: bool = True, status: str = "healthy", wait: int = 30):
        self._available = available
        self.status = SimpleNamespace(value=status)
        self._wait = wait
        self.last_http_dump = None
        self.failures: list[object] = []

    def is_available(self):
        return self._available

    def time_until_available(self):
        return 0 if self._available else self._wait

    def mark_success(self):
        self._available = True
        self.status = SimpleNamespace(value="healthy")

    def mark_failure(self, status, cooldown_minutes=None, **kwargs):
        self._available = False
        self.status = SimpleNamespace(value=getattr(status, "value", status))
        self.failures.append((status, cooldown_minutes))


class _Ep:
    def __init__(self, name: str, available: bool = True, status: str = "healthy"):
        self.name = name
        self.base_url = f"http://{name}.example/v1/chat/completions"
        self.rate_limit_per_minute = 10
        self.health = _Health(available=available, status=status)

    def extract_response(self, data):
        return data["choices"][0]["message"]["content"]


class _PingPongManager:
    """Always offers the other endpoint as fallback (the A-1 storm shape)."""

    def __init__(self, a: _Ep, b: _Ep):
        self.a = a
        self.b = b
        self.endpoints = {a.name: a, b.name: b}
        self.fallback_calls: list[str] = []
        self.depth = 0
        self.max_depth = 0

    def normalize_model_reference(self, raw):
        raw = str(raw or "")
        if raw in ("model-b", f"{self.b.name}/model-b") or self.b.name in raw:
            return SimpleNamespace(endpoint_name=self.b.name, model_name="model-b")
        return SimpleNamespace(endpoint_name=self.a.name, model_name="model-a")

    def validate_model(self, ref):
        return str(ref).split("/")[-1]

    def build_payload(self, endpoint, model_name, messages, max_tokens, temperature):
        return {
            "model": model_name,
            "messages": messages,
            "max_tokens": max_tokens or 512,
            "temperature": temperature or 0.0,
        }

    def get_api_key(self, endpoint):
        return f"key-{endpoint.name}"

    def get_fallback_model(self, endpoint, exclude=None):
        self.fallback_calls.append(endpoint.name)
        self.depth += 1
        self.max_depth = max(self.max_depth, self.depth)
        assert self.depth < 12, "fallback ping-pong exceeded bounded depth"
        other = self.b if endpoint.name == self.a.name else self.a
        if exclude and other.name in exclude:
            self.depth -= 1
            return None
        self.depth -= 1
        model = "model-b" if other is self.b else "model-a"
        return (model, other)


@pytest.fixture
def call_env(monkeypatch):
    import agents.base as base

    monkeypatch.setattr(
        base,
        "get_config",
        lambda: {
            "token_budget": {"max_tokens_per_4h": 10_000_000},
            "proxy": {},
            "default_model": "model-a",
        },
    )
    base._rate_limiter = None
    base._token_budget = None
    base._token_budgets = {}
    return base


def test_key_locked_falls_back_once_to_healthy_b(call_env, capfd):
    """§8.1 test 1: A 401 / key-locked, B healthy → one fallback, B invoked."""
    base = call_env
    a = _Ep("gemini")
    b = _Ep("beta_company")
    mgr = _PingPongManager(a, b)
    outcomes: list[dict] = []

    scripted = [
        _resp(401, {"error": {"type": "unauthorized", "message": "API KEY LOCKED"}}),
        _resp(200, {"choices": [{"message": {"content": "from-b"}}]}),
    ]
    posts: list[str] = []

    def _post(url, **kwargs):
        posts.append(url)
        return scripted.pop(0)

    sleeps: list[float] = []
    with patch.object(base, "get_endpoint_manager", lambda: mgr):
        with patch.object(base, "record_model_outcome", lambda model_ref, endpoint=None, **kw: outcomes.append({"model": model_ref, **kw})):
            with patch("agents.base.post_json", side_effect=_post):
                with patch("time.sleep", side_effect=sleeps.append):
                    answer, _ = base.call_endpoint([{"role": "user", "content": "hi"}], model="gemini/model-a")

    assert answer == "from-b"
    assert posts == [a.base_url, b.base_url]
    assert mgr.fallback_calls == ["gemini"]
    out = capfd.readouterr().out
    assert "falling back to beta_company" in out.lower()
    assert any(o.get("kind") == "unauthorized" for o in outcomes)
    assert not any(o.get("kind") == "no_alternate_endpoint" for o in outcomes)


def test_both_locked_does_not_infinite_loop(call_env, capfd):
    """§8.1 test 2: both endpoints latched → bounded stop, no RecursionError."""
    base = call_env
    a = _Ep("gemini", available=False, status="key_locked")
    b = _Ep("beta_company", available=False, status="key_locked")
    a.health._wait = 400
    b.health._wait = 400
    mgr = _PingPongManager(a, b)
    outcomes: list[dict] = []

    def boom(*args, **kwargs):
        raise AssertionError("latched endpoints must not call the API")

    sleeps: list[float] = []
    with patch.object(base, "get_endpoint_manager", lambda: mgr):
        with patch.object(base, "record_model_outcome", lambda model_ref, endpoint=None, **kw: outcomes.append({"model": model_ref, **kw})):
            with patch("agents.base.post_json", side_effect=boom):
                with patch("time.sleep", side_effect=sleeps.append):
                    answer, tokens = base.call_endpoint([{"role": "user", "content": "hi"}], model="gemini/model-a")

    assert answer is None
    assert tokens == 0
    assert len(mgr.fallback_calls) <= 4
    assert mgr.max_depth < 12
    assert sleeps and all(30 <= s <= 120 for s in sleeps)
    assert any(o.get("kind") == "no_alternate_endpoint" for o in outcomes)
    assert "No alternate endpoints available" in capfd.readouterr().out


def test_budget_ping_pong_cannot_exceed_depth(call_env):
    """§8.1 test 3: A↔B budget miss must not recurse without a seen set."""
    base = call_env
    a = _Ep("gemini")
    b = _Ep("beta_company")
    mgr = _PingPongManager(a, b)

    class _NoBudget:
        def can_spend(self, tokens, endpoint=None, **kwargs):
            return False

        def add_usage(self, tokens):
            raise AssertionError("budget-dead call must not spend")

    outcomes: list[dict] = []
    sleeps: list[float] = []
    with patch.object(base, "get_endpoint_manager", lambda: mgr):
        with patch.object(base, "get_token_budget", lambda endpoint=None: _NoBudget()):
            with patch.object(base, "record_model_outcome", lambda model_ref, endpoint=None, **kw: outcomes.append({"model": model_ref, **kw})):
                with patch("agents.base.post_json", side_effect=AssertionError("must not POST when budget is dead")):
                    with patch("time.sleep", side_effect=sleeps.append):
                        answer, tokens = base.call_endpoint([{"role": "user", "content": "hi"}], model="gemini/model-a")

    assert answer is None
    assert tokens == 0
    assert len(mgr.fallback_calls) <= 4
    assert mgr.max_depth < 12
    assert outcomes
    assert {o.get("kind") for o in outcomes} <= {"token_budget", "no_alternate_endpoint"}


def test_latch_ping_pong_cannot_exceed_depth(call_env):
    """§8.1 test 3 (latch): skip-path A↔B fallback must terminate via seen."""
    base = call_env
    a = _Ep("gemini", available=False, status="rate_limited")
    b = _Ep("beta_company", available=False, status="rate_limited")
    mgr = _PingPongManager(a, b)
    sleeps: list[float] = []
    with patch.object(base, "get_endpoint_manager", lambda: mgr):
        with patch("time.sleep", side_effect=sleeps.append):
            answer, _ = base.call_endpoint([{"role": "user", "content": "hi"}], model="gemini/model-a")
    assert answer is None
    assert len(mgr.fallback_calls) <= 4
    assert sleeps


def test_is_available_does_not_call_sync_support_freeze(monkeypatch):
    """§8.1 test 4: is_available must not re-enter _sync_support_freeze."""
    import core.endpoint_manager as epm

    monkeypatch.setattr(
        epm,
        "_sync_support_freeze",
        lambda: (_ for _ in ()).throw(AssertionError("is_available must not call _sync_support_freeze")),
    )
    h = EndpointHealth()
    assert h.is_available() is True
    h.unavailable_until = None
    assert h.is_available() is True


def test_all_endpoints_latched_does_not_call_is_available(ep_config):
    """§8.1 test 4: _all_endpoints_latched reads unavailable_until only."""
    import core.endpoint_manager as epm

    m = EndpointManager(ep_config)
    epm._register_manager(m)
    for ep in m.endpoints.values():

        def _boom(_self=ep):
            raise AssertionError("_all_endpoints_latched must not call is_available")

        ep.health.is_available = _boom  # type: ignore[method-assign]
    assert epm._all_endpoints_latched() is False
    m.endpoints["primary"].health.mark_failure(EndpointStatus.KEY_LOCKED)
    m.endpoints["secondary"].health.mark_failure(EndpointStatus.KEY_LOCKED)
    assert epm._all_endpoints_latched() is True


def test_sync_freeze_does_not_recurse_when_guard_forced_off(monkeypatch, ep_config):
    """§8.1 test 4: even with _freeze_syncing forced off, the call graph is acyclic."""
    import core.endpoint_manager as epm

    monkeypatch.setattr(epm, "_freeze_syncing", False)

    class _AlwaysOpen:
        def __enter__(self):
            epm._freeze_syncing = False
            return self

        def __exit__(self, *args):
            epm._freeze_syncing = False

    monkeypatch.setattr(epm, "_freeze_syncing_lock", _AlwaysOpen())
    m = EndpointManager(ep_config)
    epm._register_manager(m)
    m.endpoints["primary"].health.mark_failure(EndpointStatus.RATE_LIMITED)
    epm._sync_support_freeze()
    epm._sync_support_freeze()
    assert epm._all_endpoints_latched() is False


def test_log_fallback_swallows_recursion_error(monkeypatch):
    """Telemetry must not take the process down on a deep fallback stack."""
    from core.fallback_stats import log_fallback

    def boom(*_a, **_k):
        raise RecursionError("maximum recursion depth exceeded")

    monkeypatch.setattr("core.fallback_stats.get_db_connection", boom)
    log_fallback("gemini", "beta_company", "key_locked", "t1", "developer")


def test_get_fallback_model_skips_seen_endpoints(ep_config):
    m = EndpointManager(ep_config)
    primary = m.endpoints["primary"]
    result = m.get_fallback_model(primary)
    assert result is not None
    assert result[1].name == "secondary"
    none = m.get_fallback_model(primary, exclude={"secondary"})
    assert none is None
