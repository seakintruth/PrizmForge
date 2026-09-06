"""ROADMAP §8.1a: TokenBudget is per endpoint, not a process singleton.

Company Gemini and public Gemini do not share a 4h bucket. Burning A must
still spend B; burning both must stop once without recursive call_endpoint.
"""

from __future__ import annotations

import json
import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from core.token_budget import TokenBudget, format_token_budget, token_cap_for_endpoint, token_daily_cap_for_endpoint


def _resp(status: int, body: dict):
    m = MagicMock()
    m.status_code = status
    m.headers = {"Content-Type": "application/json"}
    m.json.return_value = body
    m.raise_for_status = MagicMock()
    m.text = json.dumps(body)
    return m


class _Health:
    def __init__(self):
        self.status = SimpleNamespace(value="healthy")
        self.failures: list[object] = []
        self._available = True

    def is_available(self):
        return self._available

    def time_until_available(self):
        return 0 if self._available else 30

    def mark_success(self):
        self._available = True
        self.status = SimpleNamespace(value="healthy")

    def mark_failure(self, status, cooldown_minutes=None, **kwargs):
        self.failures.append((getattr(status, "value", status), cooldown_minutes))
        if getattr(status, "value", status) == "token_exhausted":
            self._available = False
            self.status = SimpleNamespace(value="token_exhausted")


class _Ep:
    def __init__(self, name: str):
        self.name = name
        self.base_url = f"http://{name}.example/v1/chat/completions"
        self.rate_limit_per_minute = 10
        self.health = _Health()

    def extract_response(self, data):
        return data["choices"][0]["message"]["content"]


class _TwoEndpointManager:
    def __init__(self, a: _Ep, b: _Ep):
        self.a = a
        self.b = b
        self.endpoints = {a.name: a, b.name: b}
        self.fallback_calls: list[str] = []

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
        other = self.b if endpoint.name == self.a.name else self.a
        if exclude and other.name in exclude:
            return None
        model = "model-b" if other is self.b else "model-a"
        return (model, other)


@pytest.fixture
def budget_env(monkeypatch, tmp_path):
    import agents.base as base

    db_path = str(tmp_path / "agents.db")
    cfg = {
        "token_budget": {"max_tokens_per_4h": 100_000, "max_tokens_per_day": 200_000},
        "proxy": {},
        "default_model": "model-a",
        "endpoints": {
            "gemini": {"token_budget": {"max_tokens_per_4h": 50, "max_tokens_per_day": 80}},
            "beta_company": {"token_budget": {"max_tokens_per_4h": 80_000, "max_tokens_per_day": 200_000}},
        },
    }
    monkeypatch.setattr(base, "get_config", lambda: cfg)
    monkeypatch.setattr(base, "get_db_path", lambda: db_path)
    monkeypatch.setattr("core.token_budget.get_db_connection", _memory_conn_factory(db_path))
    base._rate_limiter = None
    base._token_budgets = {}
    return base, cfg, db_path


def _memory_conn_factory(db_path: str):
    """TokenBudget opens connections via get_db_connection; allow missing tables."""
    import sqlite3
    from contextlib import contextmanager

    @contextmanager
    def _conn(**kwargs):
        path = kwargs.get("db_path") or db_path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        c = sqlite3.connect(path)
        try:
            c.execute("CREATE TABLE IF NOT EXISTS token_log (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, tokens_used INTEGER, endpoint_name TEXT)")
            yield c
            c.commit()
        finally:
            c.close()

    return _conn


def test_format_token_budget_never_prints_bare_0m():
    assert "0M / 0M" not in format_token_budget(0, 0)
    assert format_token_budget(450_000, 500_000) == "450k / 500k"
    text = format_token_budget(0, 50)
    assert "0M" not in text
    assert "endpoint=" not in text


def test_get_token_budget_keys_by_endpoint_name(budget_env):
    """get_token_budget() cannot ignore endpoint.name."""
    base, _cfg, _db = budget_env
    a = base.get_token_budget("gemini")
    b = base.get_token_budget("beta_company")
    global_b = base.get_token_budget()
    assert a is not b
    assert a.endpoint_name == "gemini"
    assert b.endpoint_name == "beta_company"
    assert a.max_tokens == 50
    assert b.max_tokens == 80_000
    assert global_b.max_tokens == 100_000
    assert a.max_tokens_per_day == 80
    assert b.max_tokens_per_day == 200_000
    assert global_b.max_tokens_per_day == 200_000
    assert base.get_token_budget("gemini") is a


def test_can_spend_print_includes_endpoint(budget_env, capsys):
    base, _cfg, _db = budget_env
    budget = base.get_token_budget("gemini")
    budget.add_usage(50)
    assert budget.can_spend(10) is False
    out = capsys.readouterr().out
    assert "Token budget exceeded:" in out
    assert "endpoint=gemini" in out
    assert "0M / 0M" not in out


def test_burn_a_next_call_spends_b(budget_env, capfd):
    base, _cfg, _db = budget_env
    a = _Ep("gemini")
    b = _Ep("beta_company")
    mgr = _TwoEndpointManager(a, b)
    base.get_token_budget("gemini").add_usage(50)

    posts: list[str] = []

    def _post(url, **kwargs):
        posts.append(url)
        return _resp(200, {"choices": [{"message": {"content": "from-b"}}]})

    outcomes: list[dict] = []
    sleeps: list[float] = []
    with patch.object(base, "get_endpoint_manager", lambda: mgr):
        with patch.object(base, "record_model_outcome", lambda model_ref, endpoint=None, **kw: outcomes.append({"model": model_ref, **kw})):
            with patch("agents.base.post_json", side_effect=_post):
                with patch("time.sleep", side_effect=sleeps.append):
                    answer, _tokens = base.call_endpoint([{"role": "user", "content": "hi"}], model="gemini/model-a")

    assert answer == "from-b"
    assert posts == [b.base_url]
    assert mgr.fallback_calls == ["gemini"]
    assert base.get_token_budget("beta_company").get_used() > 0
    assert base.get_token_budget("gemini").get_used() == 50
    assert a.health.failures and a.health.failures[0][0] == "token_exhausted"
    assert not b.health.failures
    out = capfd.readouterr().out
    assert "endpoint=gemini" in out
    assert "0M / 0M" not in out
    assert not any(o.get("kind") == "key_locked" for o in outcomes)


def test_burn_both_one_token_budget_outcome_no_recursion(budget_env):
    base, cfg, _db = budget_env
    cfg["endpoints"]["beta_company"]["token_budget"]["max_tokens_per_4h"] = 50
    base._token_budgets = {}
    a = _Ep("gemini")
    b = _Ep("beta_company")
    mgr = _TwoEndpointManager(a, b)
    base.get_token_budget("gemini").add_usage(50)
    base.get_token_budget("beta_company").add_usage(50)

    outcomes: list[dict] = []
    sleeps: list[float] = []
    with patch.object(base, "get_endpoint_manager", lambda: mgr):
        with patch.object(base, "record_model_outcome", lambda model_ref, endpoint=None, **kw: outcomes.append({"model": model_ref, **kw})):
            with patch("agents.base.post_json", side_effect=AssertionError("must not POST when both budgets are dead")):
                with patch("time.sleep", side_effect=sleeps.append):
                    answer, tokens = base.call_endpoint([{"role": "user", "content": "hi"}], model="gemini/model-a")

    assert answer is None
    assert tokens == 0
    assert len(mgr.fallback_calls) <= 4
    kinds = [o.get("kind") for o in outcomes]
    assert "token_budget" in kinds
    assert kinds.count("token_budget") == 1


def test_in_memory_usage_is_endpoint_local(tmp_path):
    db = str(tmp_path / "t.db")
    a = TokenBudget(db, max_tokens_per_4h=1000, endpoint_name="a")
    b = TokenBudget(db, max_tokens_per_4h=1000, endpoint_name="b")
    a.add_usage(400)
    assert a.get_used() == 400
    assert b.get_used() == 0
    assert a.can_spend(700) is False
    assert b.can_spend(700) is True


def test_daily_cap_blocks_when_4h_still_has_room(tmp_path):
    db = str(tmp_path / "t.db")
    budget = TokenBudget(db, max_tokens_per_4h=10_000, endpoint_name="a", max_tokens_per_day=100)
    budget.add_usage(90)
    assert budget.remaining() >= 1000
    assert budget.can_spend(20) is False
    assert budget.can_spend(5) is True


def test_daily_cap_is_per_endpoint(tmp_path):
    db = str(tmp_path / "t.db")
    a = TokenBudget(db, max_tokens_per_4h=10_000, endpoint_name="a", max_tokens_per_day=100)
    b = TokenBudget(db, max_tokens_per_4h=10_000, endpoint_name="b", max_tokens_per_day=100)
    a.add_usage(100)
    assert a.can_spend(1) is False
    assert b.can_spend(50) is True


def test_token_caps_read_nested_and_top_level():
    cfg = {
        "token_budget": {"max_tokens_per_4h": 9, "max_tokens_per_day": 90},
        "endpoints": {
            "openrouter": {"token_budget": {"max_tokens_per_4h": 3, "max_tokens_per_day": 30}},
            "opencode": {},
        },
    }
    assert token_cap_for_endpoint(cfg, "openrouter") == 3
    assert token_daily_cap_for_endpoint(cfg, "openrouter") == 30
    assert token_cap_for_endpoint(cfg, "opencode") == 9
    assert token_daily_cap_for_endpoint(cfg, "opencode") == 90
    assert token_cap_for_endpoint(cfg, None) == 9
    assert token_daily_cap_for_endpoint(cfg, None) == 90


def test_example_config_has_per_endpoint_4h_and_daily_budgets():
    from pathlib import Path

    data = json.loads(Path("example_config.json").read_text(encoding="utf-8"))
    top = data["token_budget"]
    assert int(top["max_tokens_per_4h"]) > 0
    assert int(top["max_tokens_per_day"]) > 0
    endpoints = data["endpoints"]
    assert endpoints
    for name, ep in endpoints.items():
        tb = ep["token_budget"]
        assert int(tb["max_tokens_per_4h"]) > 0, name
        assert int(tb["max_tokens_per_day"]) > 0, name
        assert int(tb["max_tokens_per_day"]) >= int(tb["max_tokens_per_4h"]), name
    assert token_cap_for_endpoint(data, "openrouter") == data["endpoints"]["openrouter"]["token_budget"]["max_tokens_per_4h"]
    assert token_daily_cap_for_endpoint(data, "opencode") == data["endpoints"]["opencode"]["token_budget"]["max_tokens_per_day"]
    assert token_cap_for_endpoint(data, "openrouter") != token_cap_for_endpoint(data, "opencode")
