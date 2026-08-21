"""Deterministic unit coverage for core.endpoint_manager."""

from __future__ import annotations

import pytest

from core.endpoint_manager import (
    EndpointConfig,
    EndpointHealth,
    EndpointManager,
    EndpointStatus,
)


@pytest.fixture
def ep_config() -> dict:
    """Minimal multi-endpoint config using the new nested model structure."""
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
                "models": {
                    "model-a": {
                        "max_output_tokens": 2048,
                        "max_context_tokens": 8192,
                        "temperature": 0.2,
                    }
                },
            },
            "secondary": {
                "base_url": "http://secondary.example/v1/chat/completions",
                "api_key_name": "api_key",
                "priority": 20,
                "rate_limit_per_minute": 30,
                "include_model_in_payload": False,
                "models": {
                    "model-b": {
                        "max_output_tokens": 1024,
                        "max_context_tokens": 4096,
                        "temperature": 0.7,
                    }
                },
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
    assert cfg.include_model_in_payload is True


def test_extract_response_default_path():
    cfg = EndpointConfig("test", {})
    data = {"choices": [{"message": {"content": "Hello from model"}}]}
    assert cfg.extract_response(data) == "Hello from model"


def test_extract_response_custom_path():
    cfg = EndpointConfig(
        "gemini",
        {"response_path": ["candidates", 0, "content", "parts", 0, "text"]},
    )
    data = {"candidates": [{"content": {"parts": [{"text": "Gemini says hi"}]}}]}
    assert cfg.extract_response(data) == "Gemini says hi"


# ---------------------------------------------------------------------------
# EndpointStatus / EndpointHealth
# ---------------------------------------------------------------------------


def test_endpoint_status_values():
    assert EndpointStatus.HEALTHY.value == "healthy"
    assert EndpointStatus.RATE_LIMITED.value == "rate_limited"
    assert EndpointStatus.TOKEN_EXHAUSTED.value == "token_exhausted"
    assert EndpointStatus.KEY_LOCKED.value == "key_locked"
    assert EndpointStatus.SERVER_ERROR.value == "server_error"
    assert EndpointStatus.UNAVAILABLE.value == "unavailable"


def test_health_starts_healthy():
    h = EndpointHealth()
    assert h.status == EndpointStatus.HEALTHY
    assert h.is_available() is True


def test_mark_failure_sets_cooldown():
    h = EndpointHealth()
    h.mark_failure(EndpointStatus.RATE_LIMITED)
    assert h.status == EndpointStatus.RATE_LIMITED
    assert h.is_available() is False
    assert h.time_until_available() > 0


def test_mark_success_clears_failure():
    h = EndpointHealth()
    h.mark_failure(EndpointStatus.SERVER_ERROR)
    h.mark_success()
    assert h.status == EndpointStatus.HEALTHY
    assert h.error_count == 0
    assert h.consecutive_failures == 0
    assert h.is_available() is True


# ---------------------------------------------------------------------------
# EndpointManager
# ---------------------------------------------------------------------------


def test_manager_loads_endpoints_and_models(manager):
    assert "primary" in manager.endpoints
    assert "secondary" in manager.endpoints
    assert manager.model_reference_exists("model-a")
    assert manager.model_reference_exists("model-b")
    assert manager.default_endpoint.name == "primary"


def test_get_endpoint_for_model(manager):
    ep = manager.get_endpoint_for_model("model-a")
    assert ep.name == "primary"

    ep2 = manager.get_endpoint_for_model("model-b")
    assert ep2.name == "secondary"


def test_get_endpoint_for_unknown_model_uses_default(manager):
    ep = manager.get_endpoint_for_model("no-such-model")
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


def test_build_payload_includes_model_when_configured(manager):
    ep = manager.endpoints["primary"]
    payload = manager.build_payload(ep, "model-a", messages=[{"role": "user", "content": "hi"}])
    assert payload["model"] == "model-a"
    assert payload["max_tokens"] == 2048


def test_build_payload_omits_model_when_disabled(manager):
    ep = manager.endpoints["secondary"]
    payload = manager.build_payload(ep, "model-b", messages=[{"role": "user", "content": "hi"}], max_tokens=99)
    assert "model" not in payload
    assert payload["max_tokens"] == 99


def test_validate_model_known(manager):
    assert manager.validate_model("model-a") == "model-a"


def test_validate_model_unknown_returns_fallback(manager):
    """Unknown models fall back to the first available model (with warning)."""
    result = manager.validate_model("does-not-exist")
    assert result is not None
    assert result in manager._model_to_endpoints


def test_validate_model_empty_returns_none(manager):
    assert manager.validate_model("") is None
    assert manager.validate_model(None) is None


def test_get_available_endpoints_sorted_by_priority(manager):
    available = manager.get_available_endpoints()
    names = [ep.name for ep in available]
    assert names[0] == "primary"  # lower priority number = higher priority


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


def test_get_health_summary_shape(manager):
    summary = manager.get_health_summary()
    assert "primary" in summary
    assert "secondary" in summary
    assert summary["primary"]["status"] == "healthy"
