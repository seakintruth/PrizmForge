"""
Tests for model resolution with support for duplicate model names across endpoints.

Uses an in-memory config only — never depends on the user's config.json.
"""

from __future__ import annotations

import pytest

from core.endpoint_manager import EndpointManager


@pytest.fixture
def resolution_config() -> dict:
    """Minimal config: same bare model name on two endpoints + agent prefs."""
    return {
        "default_endpoint": "gemini",
        "default_model": "gemini/gemini-3.1-pro-preview",
        "api_key": "test-key-not-placeholder",
        "gemini_key": "gemini-secret",
        "beta_key": "beta-secret",
        "endpoints": {
            "gemini": {
                "base_url": "http://gemini.example/v1/chat/completions",
                "api_key_name": "gemini_key",
                "priority": 10,
                "include_model_in_payload": True,
                "models": {
                    "gemini-3.7-flash": {
                        "max_output_tokens": 8192,
                        "max_context_tokens": 128000,
                        "temperature": 0.7,
                    },
                    "gemini-3.1-pro-preview": {
                        "max_output_tokens": 16384,
                        "max_context_tokens": 1000000,
                        "temperature": 0.5,
                    },
                },
            },
            "beta_genai": {
                "base_url": "http://beta.example/v1/chat/completions",
                "api_key_name": "beta_key",
                "priority": 20,
                "include_model_in_payload": True,
                "models": {
                    # Same bare name as under gemini — tests disambiguation
                    "gemini-3.7-flash": {
                        "max_output_tokens": 4096,
                        "max_context_tokens": 64000,
                        "temperature": 0.9,
                    },
                },
            },
        },
        "agent_model_preferences": {
            "developer": "gemini/gemini-3.7-flash",
            "orchestrator": "gemini/gemini-3.1-pro-preview",
            "jr_reviewer": "beta_genai/gemini-3.7-flash",
        },
        "resource_controller": {
            "model_downgrades": {
                "default_model": "gemini/gemini-3.7-flash",
                "critical": {
                    "developer": "gemini/gemini-3.7-flash",
                },
            }
        },
        "fallback_settings": {"enabled": True},
    }


@pytest.fixture
def manager(resolution_config) -> EndpointManager:
    return EndpointManager(resolution_config)


# =============================================================================
# BASIC RESOLUTION TESTS
# =============================================================================


def test_list_all_model_references(manager):
    """Should return all models in endpoint/model format."""
    refs = manager.list_all_model_references()
    assert "gemini/gemini-3.7-flash" in refs
    assert "beta_genai/gemini-3.7-flash" in refs
    assert "gemini/gemini-3.1-pro-preview" in refs


def test_get_models_for_endpoint(manager):
    """Should return models scoped to a specific endpoint."""
    gemini_models = manager.get_models_for_endpoint("gemini")
    beta_models = manager.get_models_for_endpoint("beta_genai")

    assert "gemini-3.7-flash" in gemini_models
    assert "gemini-3.1-pro-preview" in gemini_models
    assert "gemini-3.7-flash" in beta_models
    assert "gemini-3.1-pro-preview" not in beta_models


def test_model_reference_exists(manager):
    """Should correctly detect existing model references (bare and full)."""
    assert manager.model_reference_exists("gemini-3.7-flash") is True
    assert manager.model_reference_exists("gemini/gemini-3.7-flash") is True
    assert manager.model_reference_exists("beta_genai/gemini-3.7-flash") is True
    assert manager.model_reference_exists("nonexistent/model") is False
    assert manager.model_reference_exists("") is False


# =============================================================================
# NORMALIZE + AGENT PREFERENCE TESTS
# =============================================================================


def test_normalize_full_reference(manager):
    choice = manager.normalize_model_reference("gemini/gemini-3.1-pro-preview")
    assert choice.endpoint_name == "gemini"
    assert choice.model_name == "gemini-3.1-pro-preview"


def test_normalize_bare_name_prefers_default_endpoint(manager):
    choice = manager.normalize_model_reference("gemini-3.7-flash")
    assert choice.model_name == "gemini-3.7-flash"
    assert choice.endpoint_name == "gemini"  # default_endpoint


def test_normalize_none_returns_default_endpoint(manager):
    choice = manager.normalize_model_reference(None)
    assert choice.endpoint_name == "gemini"
    assert choice.model_name is None


def test_resolve_agent_model_full_pref(manager):
    """resolve_agent_model should honor endpoint/model preferences."""
    choice = manager.resolve_agent_model("developer")
    assert choice.model_name == "gemini-3.7-flash"
    assert choice.endpoint_name == "gemini"

    jr = manager.resolve_agent_model("jr_reviewer")
    assert jr.model_name == "gemini-3.7-flash"
    assert jr.endpoint_name == "beta_genai"


def test_resolve_unknown_agent_falls_back(manager):
    choice = manager.resolve_agent_model("no_such_agent")
    assert choice.endpoint_name == "gemini"
    assert choice.model_name is None


# =============================================================================
# ENDPOINT + MODEL LOOKUP TESTS
# =============================================================================


def test_get_endpoint_for_model_bare_uses_default(manager):
    endpoint = manager.get_endpoint_for_model("gemini-3.7-flash")
    assert endpoint is not None
    assert endpoint.name == "gemini"


def test_get_endpoint_for_model_full_ref(manager):
    endpoint = manager.get_endpoint_for_model("beta_genai/gemini-3.7-flash")
    assert endpoint is not None
    assert endpoint.name == "beta_genai"


def test_get_model_config_bare_and_full(manager):
    bare = manager.get_model_config("gemini-3.7-flash")
    assert bare.get("max_output_tokens") == 8192  # gemini (default) copy

    full_beta = manager.get_model_config("beta_genai/gemini-3.7-flash")
    assert full_beta.get("max_output_tokens") == 4096

    scoped = manager.get_model_config("gemini-3.7-flash", endpoint_name="beta_genai")
    assert scoped.get("max_output_tokens") == 4096


def test_get_model_config_missing_returns_empty(manager):
    assert manager.get_model_config("no-such-model") == {}


# =============================================================================
# VALIDATION & EDGE CASES
# =============================================================================


def test_validate_model_known_returns_bare(manager):
    assert manager.validate_model("gemini-3.7-flash") == "gemini-3.7-flash"
    assert manager.validate_model("gemini/gemini-3.1-pro-preview") == "gemini-3.1-pro-preview"


def test_validate_model_unknown_returns_fallback(manager):
    result = manager.validate_model("nonexistent-model-xyz")
    assert result is not None
    assert result in manager._model_to_endpoints


def test_validate_model_empty_returns_none(manager):
    assert manager.validate_model("") is None
    assert manager.validate_model(None) is None


def test_build_payload_strips_full_ref_to_bare(manager):
    ep = manager.endpoints["gemini"]
    payload = manager.build_payload(
        ep,
        "gemini/gemini-3.7-flash",
        messages=[{"role": "user", "content": "hi"}],
    )
    assert payload["model"] == "gemini-3.7-flash"


def test_full_model_resolution_flow(manager):
    """End-to-end: agent pref → normalize → endpoint → config."""
    choice = manager.resolve_agent_model("orchestrator")
    assert choice.model_name == "gemini-3.1-pro-preview"
    assert choice.endpoint_name == "gemini"

    endpoint = manager.endpoints[choice.endpoint_name]
    assert endpoint.name == "gemini"

    model_config = manager.get_model_config(choice.model_name, choice.endpoint_name)
    assert model_config.get("max_context_tokens") == 1000000

    bare = manager.validate_model(f"{choice.endpoint_name}/{choice.model_name}")
    assert bare == "gemini-3.1-pro-preview"
