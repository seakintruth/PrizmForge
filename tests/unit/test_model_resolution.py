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


# =============================================================================
# SLASHED MODEL-ID TESTS (model IDs that themselves contain '/')
# =============================================================================


@pytest.fixture
def slashed_config() -> dict:
    """Config where model IDs contain slashes, as with OpenRouter-style IDs."""
    return {
        "default_endpoint": "openrouter",
        "default_model": "openrouter/stealth/ox-alpha",
        "_api_keys": {"openrouter": {"api_key": "or-secret"}},
        "endpoints": {
            "openrouter": {
                "base_url": "https://openrouter.example/v1/chat/completions",
                "priority": 10,
                "include_model_in_payload": True,
                "models": {
                    "stealth/ox-alpha": {},
                    "openai/gpt-4o": {"max_output_tokens": 4096},
                    "nvidia/nemotron-3-ultra-550b-a55b:free": {},
                },
            },
            # Second endpoint hosting an IDENTICAL slashed model ID
            "backup": {
                "base_url": "https://backup.example/v1/chat/completions",
                "priority": 20,
                "include_model_in_payload": True,
                "models": {
                    "openai/gpt-4o": {"max_output_tokens": 1024},
                },
            },
        },
        "agent_model_preferences": {
            "orchestrator": "openrouter/stealth/ox-alpha",
            "developer": "backup/openai/gpt-4o",
        },
        "fallback_settings": {"enabled": True},
    }


@pytest.fixture
def slashed_manager(slashed_config) -> EndpointManager:
    return EndpointManager(slashed_config)


def test_slashed_id_full_reference_parses_endpoint_and_full_id(slashed_manager):
    """'endpoint/vendor/model' must split into endpoint + FULL model ID."""
    choice = slashed_manager.normalize_model_reference("openrouter/stealth/ox-alpha")
    assert choice.endpoint_name == "openrouter"
    assert choice.model_name == "stealth/ox-alpha"  # NOT 'stealth'


def test_slashed_id_bare_reference_resolves_via_default_endpoint(slashed_manager):
    """A bare slashed ID resolves against the default endpoint."""
    choice = slashed_manager.normalize_model_reference("stealth/ox-alpha")
    assert choice.endpoint_name == "openrouter"
    assert choice.model_name == "stealth/ox-alpha"


def test_validate_model_preserves_slashed_id(slashed_manager):
    """validate_model must return the FULL ID for API payloads — not the last segment."""
    assert slashed_manager.validate_model("openrouter/stealth/ox-alpha") == "stealth/ox-alpha"
    assert slashed_manager.validate_model("stealth/ox-alpha") == "stealth/ox-alpha"
    assert slashed_manager.validate_model("nvidia/nemotron-3-ultra-550b-a55b:free") == ("nvidia/nemotron-3-ultra-550b-a55b:free")


def test_build_payload_sends_full_slashed_id(slashed_manager):
    """Regression: payload previously sent only the LAST path segment ('ox-alpha')."""
    ep = slashed_manager.endpoints["openrouter"]
    payload = slashed_manager.build_payload(
        ep,
        "openrouter/stealth/ox-alpha",
        messages=[{"role": "user", "content": "hi"}],
    )
    assert payload["model"] == "stealth/ox-alpha"


def test_build_payload_bare_slashed_id_keeps_whole_id(slashed_manager):
    ep = slashed_manager.endpoints["openrouter"]
    payload = slashed_manager.build_payload(
        ep,
        "openai/gpt-4o",  # bare (no known endpoint prefix)
        messages=[{"role": "user", "content": "hi"}],
    )
    assert payload["model"] == "openai/gpt-4o"


def test_identical_slashed_ids_on_two_endpoints_differentiate(slashed_manager):
    """Same model ID on two endpoints: explicit prefix picks the right one."""
    orch = slashed_manager.resolve_agent_model("orchestrator")
    assert (orch.endpoint_name, orch.model_name) == ("openrouter", "stealth/ox-alpha")

    dev = slashed_manager.resolve_agent_model("developer")
    assert (dev.endpoint_name, dev.model_name) == ("backup", "openai/gpt-4o")

    # Endpoint lookup honors each explicit prefix
    assert slashed_manager.get_endpoint_for_model("openrouter/openai/gpt-4o").name == "openrouter"
    assert slashed_manager.get_endpoint_for_model("backup/openai/gpt-4o").name == "backup"


def test_identical_slashed_ids_scoped_config_lookup(slashed_manager):
    """get_model_config with explicit endpoint_name wins over default endpoint."""
    default_copy = slashed_manager.get_model_config("openai/gpt-4o")
    assert default_copy.get("max_output_tokens") == 4096  # openrouter (default)

    backup_copy = slashed_manager.get_model_config("backup/openai/gpt-4o")
    assert backup_copy.get("max_output_tokens") == 1024

    scoped = slashed_manager.get_model_config("openai/gpt-4o", endpoint_name="backup")
    assert scoped.get("max_output_tokens") == 1024


def test_slashed_id_model_reference_exists(slashed_manager):
    assert slashed_manager.model_reference_exists("openrouter/stealth/ox-alpha")
    assert slashed_manager.model_reference_exists("stealth/ox-alpha")
    assert slashed_manager.model_reference_exists("backup/openai/gpt-4o")
    # First segment looks like a vendor, not a real endpoint → whole string is the ID
    assert slashed_manager.model_reference_exists("vendor/nonexistent-model") is False


def test_unknown_first_segment_treated_as_model_id(slashed_manager):
    """'vendor/model' where 'vendor' is NOT a configured endpoint must not error."""
    choice = slashed_manager.normalize_model_reference("some-vendor/some-model")
    assert choice.endpoint_name in (None, "openrouter")  # unresolved or default
    # It must NOT be truncated to endpoint='some-vendor'
    assert choice.endpoint_name != "some-vendor"


def test_get_endpoint_for_model_slashed_bare_uses_default(slashed_manager):
    endpoint = slashed_manager.get_endpoint_for_model("openai/gpt-4o")
    assert endpoint is not None and endpoint.name == "openrouter"


# =============================================================================
# LLM-SUPPLIED MODEL OVERRIDES MUST BE VALIDATED
# =============================================================================


def test_hallucinated_model_override_is_rejected(slashed_manager):
    """LLMs parrot example values from prompts (e.g. schema examples).

    An override naming a model that doesn't exist must be detectable so
    callers can ignore it instead of silently falling back mid-call.
    """
    hallucinated = "gemini-3.1-pro-preview"
    assert slashed_manager.model_reference_exists(hallucinated) is False
    # And the valid configured default still resolves.
    assert slashed_manager.model_reference_exists("openrouter/stealth/ox-alpha") is True


def test_call_agent_ignores_unknown_model_override(slashed_config):
    """call_agent must not use an unknown override; it falls back to prefs.

    We can't call call_agent without network, but we can verify the guard
    logic: an invalid override normalizes through the same path and would
    be rejected before reaching validate_model's fallback warning.
    """
    from unittest.mock import patch

    manager = EndpointManager(slashed_config)
    with (
        patch("core.config.get_config", return_value=slashed_config),
        patch(
            "core.endpoint_manager.get_endpoint_manager",
            return_value=manager,
        ),
    ):
        from agents.base import call_agent  # noqa: F401  (import sanity)

        bad_override = "gemini-3.1-pro-preview"
        # The guard condition used in call_agent:
        should_ignore = bad_override and not manager.model_reference_exists(bad_override)
        assert should_ignore is True

        good_override = "openrouter/stealth/ox-alpha"
        should_ignore_good = good_override and not manager.model_reference_exists(good_override)
        assert should_ignore_good is False
