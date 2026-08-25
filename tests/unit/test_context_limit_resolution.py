"""Model context limits must resolve through the nested endpoints config."""

from core.context_manager import ContextManager
from core.endpoint_manager import EndpointManager


def _patch_env(monkeypatch, cfg):
    monkeypatch.setattr("core.context_manager.get_config", lambda: cfg)
    monkeypatch.setattr(
        "core.endpoint_manager.get_endpoint_manager",
        lambda: EndpointManager(cfg),
    )


def test_resolves_nested_endpoint_model(monkeypatch):
    cfg = {
        "default_endpoint": "ep",
        "default_model": "ep/foo/bar",
        "endpoints": {"ep": {"models": {"foo/bar": {"max_context_tokens": 200_000, "max_output_tokens": 16_000}}}},
        "models": {},
    }
    _patch_env(monkeypatch, cfg)
    cm = ContextManager()
    limit = cm.get_model_context_limit("ep/foo/bar")
    expected = int((200_000 - 16_000) * 0.85)
    assert limit == expected


def test_no_warning_for_known_model_without_explicit_limit(monkeypatch, capsys):
    """A known model lacking max_context_tokens silently gets the default."""
    cfg = {
        "default_endpoint": "ep",
        "endpoints": {"ep": {"models": {"m1": {}}}},
        "models": {},
    }
    _patch_env(monkeypatch, cfg)
    cm = ContextManager()
    assert cm.get_model_context_limit("ep/m1") == cm.default_context_limit
    out = capsys.readouterr().out
    assert "Unknown model" not in out


def test_unknown_model_still_warns(monkeypatch, capsys):
    """Genuinely unknown references keep the warning (config typo detector)."""
    cfg = {
        "default_endpoint": "ep",
        "endpoints": {"ep": {"models": {"m1": {}}}},
        "models": {},
    }
    _patch_env(monkeypatch, cfg)
    cm = ContextManager()
    assert cm.get_model_context_limit("ep/nope") == cm.default_context_limit
    assert "Unknown model" in capsys.readouterr().out
