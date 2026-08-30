"""Hermetic coverage for model catalog / assign / prompt helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.models_catalog import (
    assign_agents,
    assign_tier,
    catalog_path,
    ensure_registered,
    fetch_catalog,
    models_url,
    parse_model_ids,
    prompt_text,
    set_prompt_text,
    validate_assignments,
)


def _cfg(tmp_path: Path) -> dict:
    proj = tmp_path / "proj"
    proj.mkdir()
    return {
        "_config_dir": str(tmp_path),
        "project_directory": str(proj),
        "default_endpoint": "openrouter",
        "default_model": "openrouter/stealth/ox-alpha",
        "endpoints": {
            "openrouter": {
                "base_url": "https://openrouter.example/v1/chat/completions",
                "models": {"stealth/ox-alpha": {}, "openai/gpt-4o-mini": {}},
            },
            "opencode": {
                "base_url": "https://opencode.example/v1/chat/completions",
                "models": {"big-pick": {}},
            },
        },
        "agent_model_preferences": {
            "developer": "openrouter/stealth/ox-alpha",
            "jr_reviewer": "openrouter/openai/gpt-4o-mini",
        },
        "_api_keys": {"openrouter": {"api_key": "sk-test"}},
    }


def test_models_url_from_chat_completions():
    assert models_url("https://api.example/v1/chat/completions") == "https://api.example/v1/models"
    assert models_url("https://api.example/v1/models") == "https://api.example/v1/models"
    assert models_url("https://api.example/v1") == "https://api.example/v1/models"


def test_parse_model_ids_openai_shape():
    ids = parse_model_ids({"data": [{"id": "stealth/ox-alpha"}, {"id": "openai/gpt-4o"}, "ignored"]})
    assert ids == ["stealth/ox-alpha", "openai/gpt-4o"]


def test_fetch_catalog_uses_injector_and_persists(tmp_path):
    cfg = _cfg(tmp_path)

    def fake_fetch(url, headers, proxies):
        assert "Authorization" in headers
        if "openrouter" in url:
            return 200, {"data": [{"id": "stealth/ox-alpha"}, {"id": "new/from-wire"}]}
        return 404, {"error": "nope"}

    catalog = fetch_catalog(cfg, fetcher=fake_fetch, persist=True)
    assert catalog["endpoints"]["openrouter"]["ok"] is True
    assert "new/from-wire" in catalog["endpoints"]["openrouter"]["models"]
    assert catalog["endpoints"]["opencode"]["ok"] is False
    saved = json.loads(catalog_path(cfg).read_text(encoding="utf-8"))
    assert saved["endpoints"]["openrouter"]["models"][-1] == "new/from-wire"


def test_assign_known_ref(tmp_path):
    raw = _cfg(tmp_path)
    assign_agents(raw, ["reviewer"], "openrouter/stealth/ox-alpha")
    assert raw["agent_model_preferences"]["reviewer"] == "openrouter/stealth/ox-alpha"


def test_assign_unknown_without_register_raises(tmp_path):
    raw = _cfg(tmp_path)
    with pytest.raises(ValueError, match="Unknown model"):
        assign_agents(raw, ["developer"], "openrouter/not-in-config")


def test_assign_from_catalog_requires_register(tmp_path):
    raw = _cfg(tmp_path)
    catalog = {"endpoints": {"openrouter": {"ok": True, "models": ["brand-new"]}}}
    with pytest.raises(ValueError, match="--register"):
        assign_agents(raw, ["developer"], "openrouter/brand-new", catalog=catalog)


def test_assign_register_adds_stub(tmp_path):
    raw = _cfg(tmp_path)
    catalog = {"endpoints": {"openrouter": {"ok": True, "models": ["brand-new"]}}}
    assign_agents(raw, ["developer", "reviewer"], "openrouter/brand-new", register=True, catalog=catalog)
    assert raw["endpoints"]["openrouter"]["models"]["brand-new"]["description"]
    assert raw["agent_model_preferences"]["developer"] == "openrouter/brand-new"
    assert raw["agent_model_preferences"]["reviewer"] == "openrouter/brand-new"


def test_assign_tier_cheap(tmp_path):
    raw = _cfg(tmp_path)
    assign_tier(raw, "cheap", "openrouter/openai/gpt-4o-mini")
    assert raw["agent_model_preferences"]["jr_reviewer"] == "openrouter/openai/gpt-4o-mini"
    assert raw["agent_model_preferences"]["archivist"] == "openrouter/openai/gpt-4o-mini"
    assert raw["agent_model_preferences"]["developer"] == "openrouter/stealth/ox-alpha"


def test_validate_flags_unknown_and_missing_prompt(tmp_path):
    cfg = _cfg(tmp_path)
    cfg["agent_model_preferences"]["ghost"] = "openrouter/nope"
    problems = validate_assignments(cfg, prompts={"developer": {"system_prompt": "x"}})
    assert any("ghost" in p for p in problems)
    assert any("jr_reviewer" in p and "missing" in p for p in problems)


def test_validate_clean(tmp_path):
    cfg = _cfg(tmp_path)
    prompts = {name: {"system_prompt": "ok"} for name in cfg["agent_model_preferences"]}
    assert validate_assignments(cfg, prompts=prompts) == []


def test_ensure_registered_rejects_unknown_endpoint(tmp_path):
    raw = _cfg(tmp_path)
    with pytest.raises(ValueError, match="Unknown endpoint"):
        ensure_registered(raw, "missing/foo")


def test_prompt_roundtrip():
    prompts = {"reviewer": {"role": "R", "system_prompt": "old"}}
    assert prompt_text(prompts, "reviewer") == "old"
    set_prompt_text(prompts, "reviewer", "new gate rules")
    assert prompts["reviewer"]["system_prompt"] == "new gate rules"
    set_prompt_text(prompts, "new_agent", "hello")
    assert prompt_text(prompts, "new_agent") == "hello"
