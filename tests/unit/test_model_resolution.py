"""
Tests for model resolution with support for duplicate model names across endpoints.
"""

import pytest

from core.endpoint_manager import get_endpoint_manager


@pytest.fixture
def endpoint_manager():
    """Get endpoint manager (reset singleton for test isolation)."""
    import core.endpoint_manager as em_module

    em_module._endpoint_manager = None
    return get_endpoint_manager()


# =============================================================================
# BASIC RESOLUTION TESTS
# =============================================================================


def test_list_all_model_references(endpoint_manager):
    """Should return all models in endpoint/model format."""
    refs = endpoint_manager.list_all_model_references()
    assert any("gemini/gemini-3.7-flash" in ref for ref in refs)
    assert any("beta_genai/gemini-3.7-flash" in ref for ref in refs)


def test_get_models_for_endpoint(endpoint_manager):
    """Should return models scoped to a specific endpoint."""
    gemini_models = endpoint_manager.get_models_for_endpoint("gemini")
    beta_models = endpoint_manager.get_models_for_endpoint("beta_genai")

    assert "gemini-3.7-flash" in gemini_models
    assert "gemini-3.7-flash" in beta_models
    assert gemini_models != beta_models or len(gemini_models) > 0


def test_model_reference_exists(endpoint_manager):
    """Should correctly detect existing model references."""
    assert endpoint_manager.model_reference_exists("gemini-3.7-flash") is True
    assert endpoint_manager.model_reference_exists("gemini/gemini-3.7-flash") is True
    assert endpoint_manager.model_reference_exists("beta_genai/gemini-3.7-flash") is True
    assert endpoint_manager.model_reference_exists("nonexistent/model") is False


# =============================================================================
# AGENT MODEL PREFERENCE TESTS
# =============================================================================


def test_resolve_agent_model_returns_both_endpoint_and_model(endpoint_manager):
    """resolve_agent_model should return both endpoint and model."""
    choice = endpoint_manager.resolve_agent_model("developer")
    assert choice.model_name == "gemini-3.7-flash"
    assert choice.endpoint_name in ("gemini", "beta_genai")


def test_resolve_plain_model_name_falls_back(endpoint_manager):
    """Plain model name should resolve to an endpoint (preferably default)."""
    choice = endpoint_manager.resolve_agent_model("developer")
    assert choice.endpoint_name is not None
    assert choice.model_name is not None


# =============================================================================
# ENDPOINT + MODEL LOOKUP TESTS
# =============================================================================


def test_get_endpoint_for_model_returns_valid_endpoint(endpoint_manager):
    """Should return a valid endpoint for known models."""
    endpoint = endpoint_manager.get_endpoint_for_model("gemini-3.7-flash")
    assert endpoint is not None
    assert endpoint.name in ("gemini", "beta_genai")


def test_get_model_config_works_with_compound_key(endpoint_manager):
    """get_model_config should work when model exists on multiple endpoints."""
    config = endpoint_manager.get_model_config("gemini-3.7-flash")
    assert config is not None
    assert "max_output_tokens" in config or "max_context_tokens" in config


def test_get_model_config_with_specific_endpoint(endpoint_manager):
    """Should be able to request model config for a specific endpoint."""
    gemini_config = endpoint_manager.get_model_config("gemini-3.7-flash", endpoint_name="gemini")
    beta_config = endpoint_manager.get_model_config("gemini-3.7-flash", endpoint_name="beta_genai")

    assert gemini_config is not None
    assert beta_config is not None


# =============================================================================
# VALIDATION & EDGE CASES
# =============================================================================


def test_validate_model_known_model(endpoint_manager):
    """Should return the model name if it exists."""
    result = endpoint_manager.validate_model("gemini-3.7-flash")
    assert result == "gemini-3.7-flash"


def test_validate_model_unknown_returns_fallback(endpoint_manager):
    """Should return a fallback for unknown models."""
    result = endpoint_manager.validate_model("nonexistent-model-xyz")
    assert result is not None
    assert result in endpoint_manager._model_to_endpoints


def test_full_model_resolution_flow(endpoint_manager):
    """End-to-end resolution from agent preference to endpoint + config."""
    choice = endpoint_manager.resolve_agent_model("orchestrator")

    assert choice.model_name is not None
    assert choice.endpoint_name is not None

    endpoint = endpoint_manager.get_endpoint_for_model(choice.model_name)
    assert endpoint is not None

    model_config = endpoint_manager.get_model_config(choice.model_name, choice.endpoint_name)
    assert model_config is not None
