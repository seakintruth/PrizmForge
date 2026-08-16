"""Deterministic unit coverage for core.endpoint_manager failure boundaries."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from core.endpoint_manager import (
    EndpointConfig,
    EndpointHealth,
    EndpointManager,
    EndpointStatus,
)


@pytest.fixture
def ep_config() -> dict:
    """Minimal multi-endpoint config with no live keys or network."""
    return {
        "default_endpoint": "primary",
        "api_key": "test-key-not-placeholder",
        "primary_key": "primary-secret",
        "endpoints": {
            "primary": {
                "base_url": "http://primary.example/v1/chat/completions",
                "api_key_name": "primary_key",
                "priority": 10,
                "rate_limit_per_minute": 60,
                "include_model_in_payload": True,
                "response_path": ["choices", 0, "message", "content"],
            },
            "secondary": {
                "base_url": "http://secondary.example/v1/chat/completions",
                "api_key_name": "api_key",
                "priority": 20,
                "rate_limit_per_minute": 30,
                "include_model_in_payload": False,
            },
        },
        "models": {
            "model-a": {
                "endpoint": "primary",
                "max_output_tokens": 2048,
                "temperature": 0.2,
            },
            "model-b": {
                "endpoint": "secondary",
                "max_output_tokens": 1024,
                "temperature": 0.7,
            },
        },
        "fallback_settings": {"enabled": True},
    }


@pytest.fixture
def manager(ep_config) -> EndpointManager:
    return EndpointManager(ep_config)


# ---------------------------------------------------------------------------
# EndpointConfig
# ---------------------------------------------------------------------------


def test_endpoint_config_fields():
    cfg = EndpointConfig(
        "openai",
        {
            "base_url": "https://api.openai.com/v1/chat/completions",
            "api_key_name": "OPENAI_API_KEY",
            "priority": 5,
            "rate_limit_per_minute": 100,
        },
    )
    assert cfg.name == "openai"
    assert cfg.base_url.startswith("https://")
    assert cfg.api_key_name == "OPENAI_API_KEY"
    assert cfg.priority == 5
    assert cfg.rate_limit_per_minute == 100
    assert cfg.include_model_in_payload is True  # default


def test_extract_response_default_path():
    cfg = EndpointConfig("test", {})
    data = {"choices": [{"message": {"content": "Hello from model"}}]}
    assert cfg.extract_response(data) == "Hello from model"


def test_extract_response_custom_path():
    cfg = EndpointConfig(
        "gemini",
        {"response_path": ["candidates", 0, "content", "parts", 0, "text"]},
    )
    data = {
        "candidates": [
            {"content": {"parts": [{"text": "Gemini says hi"}]}}
        ]
    }
    assert cfg.extract_response(data) == "Gemini says hi"


# ---------------------------------------------------------------------------
# EndpointStatus / EndpointHealth (in-memory; DB load/save swallow errors)
# ---------------------------------------------------------------------------


def test_endpoint_status_values():
    assert EndpointStatus.HEALTHY.value == "healthy"
    assert EndpointStatus.RATE_LIMITED.value == "rate_limited"
    assert EndpointStatus.TOKEN_EXHAUSTED.value == "token_exhausted"
    assert EndpointStatus.KEY_LOCKED.value == "key_locked"
    assert EndpointStatus.SERVER_ERROR.value == "server_error"
    assert EndpointStatus.UNAVAILABLE.value == "unavailable"


def test_health_starts_healthy():
    h = EndpointHealth()  # no name → no DB load
    assert h.status == EndpointStatus.HEALTHY
    assert h.is_available() is True
    assert h.time_until_available() == 0
    assert h.error_count == 0
    assert h.consecutive_failures == 0


def test_mark_failure_sets_cooldown():
    h = EndpointHealth()
    h.mark_failure(EndpointStatus.RATE_LIMITED)
    assert h.status == EndpointStatus.RATE_LIMITED
    assert h.error_count == 1
    assert h.consecutive_failures == 1
    assert h.unavailable_until is not None
    # default rate-limit cooldown is 2 minutes
    assert h.unavailable_until > datetime.now()
    assert h.is_available() is False
    assert h.time_until_available() > 0


def test_mark_failure_token_exhausted_longer_cooldown():
    h = EndpointHealth()
    h.mark_failure(EndpointStatus.TOKEN_EXHAUSTED)
    assert h.status == EndpointStatus.TOKEN_EXHAUSTED
    # 15 minute default
    delta = h.unavailable_until - datetime.now()
    assert delta >= timedelta(minutes=14)


def test_mark_failure_key_locked_cooldown():
    h = EndpointHealth()
    h.mark_failure(EndpointStatus.KEY_LOCKED)
    delta = h.unavailable_until - datetime.now()
    assert delta >= timedelta(minutes=29)


def test_mark_failure_custom_cooldown():
    h = EndpointHealth()
    h.mark_failure(EndpointStatus.SERVER_ERROR, cooldown_minutes=1)
    delta = h.unavailable_until - datetime.now()
    assert timedelta(seconds=30) < delta < timedelta(minutes=2)


def test_mark_success_clears_failure():
    h = EndpointHealth()
    h.mark_failure(EndpointStatus.SERVER_ERROR)
    assert h.is_available() is False
    h.mark_success()
    assert h.status == EndpointStatus.HEALTHY
    assert h.error_count == 0
    assert h.consecutive_failures == 0
    assert h.unavailable_until is None
    assert h.is_available() is True


def test_expired_cooldown_is_available():
    h = EndpointHealth()
    h.mark_failure(EndpointStatus.RATE_LIMITED, cooldown_minutes=1)
    # Force expiry in the past
    h.unavailable_until = datetime.now() - timedelta(seconds=5)
    assert h.is_available() is True
    assert h.time_until_available() == 0


# ---------------------------------------------------------------------------
# EndpointManager — selection, payload, keys, fallback
# ---------------------------------------------------------------------------


def test_manager_loads_endpoints_and_models(manager):
    assert "primary" in manager.endpoints
    assert "secondary" in manager.endpoints
    assert "model-a" in manager.models
    assert "model-b" in manager.models
    assert manager.default_endpoint.name == "primary"


def test_manager_skips_model_with_unknown_endpoint(ep_config):
    ep_config["models"]["orphan"] = {"endpoint": "does-not-exist"}
    m = EndpointManager(ep_config)
    assert "orphan" not in m.models


def test_get_endpoint_for_model(manager):
    ep = manager.get_endpoint_for_model("model-a")
    assert ep.name == "primary"
    ep2 = manager.get_endpoint_for_model("model-b")
    assert ep2.name == "secondary"


def test_get_endpoint_for_unknown_model_uses_default(manager):
    ep = manager.get_endpoint_for_model("no-such-model")
    assert ep.name == "primary"


def test_get_endpoint_for_none_uses_default(manager):
    ep = manager.get_endpoint_for_model(None)
    assert ep.name == "primary"


def test_get_model_config(manager):
    cfg = manager.get_model_config("model-a")
    assert cfg["max_output_tokens"] == 2048
    assert cfg["temperature"] == 0.2
    assert manager.get_model_config("missing") == {}


def test_get_api_key_specific_name(manager):
    ep = manager.endpoints["primary"]
    assert manager.get_api_key(ep) == "primary-secret"


def test_get_api_key_falls_back_to_generic(manager):
    ep = manager.endpoints["secondary"]
    assert manager.get_api_key(ep) == "test-key-not-placeholder"


def test_get_api_key_rejects_placeholder():
    cfg = {
        "api_key": "YOUR_GEMINI_API_KEY_HERE",
        "endpoints": {
            "g": {
                "base_url": "http://x",
                "api_key_name": "api_key",
            }
        },
        "models": {},
    }
    m = EndpointManager(cfg)
    with pytest.raises(ValueError, match="API key not configured"):
        m.get_api_key(m.endpoints["g"])


def test_get_api_key_rejects_missing():
    cfg = {
        "endpoints": {"g": {"base_url": "http://x", "api_key_name": "missing_key"}},
        "models": {},
    }
    m = EndpointManager(cfg)
    with pytest.raises(ValueError, match="API key not configured"):
        m.get_api_key(m.endpoints["g"])


def test_build_payload_includes_model_when_configured(manager):
    ep = manager.endpoints["primary"]
    payload = manager.build_payload(
        ep,
        "model-a",
        messages=[{"role": "user", "content": "hi"}],
    )
    assert payload["model"] == "model-a"
    assert payload["messages"][0]["content"] == "hi"
    assert payload["max_tokens"] == 2048
    assert payload["temperature"] == 0.2


def test_build_payload_omits_model_when_disabled(manager):
    ep = manager.endpoints["secondary"]
    payload = manager.build_payload(
        ep,
        "model-b",
        messages=[{"role": "user", "content": "hi"}],
        max_tokens=99,
        temperature=0.9,
    )
    assert "model" not in payload
    assert payload["max_tokens"] == 99
    assert payload["temperature"] == 0.9


def test_build_payload_defaults_without_model(manager):
    ep = manager.endpoints["primary"]
    payload = manager.build_payload(ep, None, messages=[])
    assert "model" not in payload
    assert payload["max_tokens"] == 16384  # hard default
    assert payload["temperature"] == 0.5


def test_validate_model_known(manager):
    assert manager.validate_model("model-a") == "model-a"


def test_validate_model_unknown_falls_back_to_first(manager):
    result = manager.validate_model("does-not-exist")
    assert result in ("model-a", "model-b")


def test_validate_model_empty_returns_none(manager):
    assert manager.validate_model("") is None
    assert manager.validate_model(None) is None


def test_validate_model_no_models_registered():
    m = EndpointManager({"endpoints": {}, "models": {}})
    assert m.validate_model("anything") is None


def test_get_available_endpoints_sorted_by_priority(manager):
    available = manager.get_available_endpoints()
    names = [ep.name for ep in available]
    assert names == ["primary", "secondary"]  # priority 10 then 20


def test_get_available_endpoints_excludes_cooldown(manager):
    manager.endpoints["primary"].health.mark_failure(
        EndpointStatus.RATE_LIMITED, cooldown_minutes=5
    )
    available = manager.get_available_endpoints()
    names = [ep.name for ep in available]
    assert "primary" not in names
    assert "secondary" in names


def test_get_fallback_model(manager):
    primary = manager.endpoints["primary"]
    result = manager.get_fallback_model(primary)
    assert result is not None
    model_name, ep = result
    assert model_name == "model-b"
    assert ep.name == "secondary"


def test_get_fallback_model_disabled(ep_config):
    ep_config["fallback_settings"] = {"enabled": False}
    m = EndpointManager(ep_config)
    assert m.get_fallback_model(m.endpoints["primary"]) is None


def test_get_fallback_model_none_when_all_down(manager):
    for ep in manager.endpoints.values():
        ep.health.mark_failure(EndpointStatus.UNAVAILABLE, cooldown_minutes=10)
    assert manager.get_fallback_model(manager.endpoints["primary"]) is None


def test_get_health_summary_shape(manager):
    summary = manager.get_health_summary()
    assert "primary" in summary
    assert "secondary" in summary
    for name, info in summary.items():
        assert "status" in info
        assert "available" in info
        assert "error_count" in info
        assert "consecutive_failures" in info
        assert info["status"] == "healthy"
        assert info["available"] is True


def test_get_health_summary_reflects_failure(manager):
    manager.endpoints["primary"].health.mark_failure(EndpointStatus.SERVER_ERROR)
    summary = manager.get_health_summary()
    assert summary["primary"]["status"] == "server_error"
    assert summary["primary"]["available"] is False
    assert summary["primary"]["error_count"] == 1
    assert summary["primary"]["seconds_until_available"] > 0
