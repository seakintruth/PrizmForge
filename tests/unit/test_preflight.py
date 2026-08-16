"""Unattended preflight and CLI mode config contracts."""

from __future__ import annotations

from pathlib import Path


def test_preflight_ok_in_test_mode(tmp_path, monkeypatch):
    from core.preflight import preflight_unattended

    project = tmp_path / "proj"
    project.mkdir()
    cfg = {
        "cli_mode": {"mode": "unattended"},
        "project_directory": str(project),
        "llm": {"test_mode": True},
        "endpoints": {
            "mock": {"api_key_name": "mock_key", "base_url": "http://localhost"},
        },
    }
    monkeypatch.setenv("PRIZMFORGE_TEST_MODE", "1")
    ok, errors = preflight_unattended(cfg)
    assert ok is True
    assert errors == []


def test_preflight_fails_without_keys_outside_test_mode(tmp_path, monkeypatch):
    from core.preflight import preflight_unattended

    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.delenv("PRIZMFORGE_TEST_MODE", raising=False)
    cfg = {
        "cli_mode": {"mode": "unattended"},
        "project_directory": str(project),
        "llm": {"test_mode": False},
        "endpoints": {
            "gemini": {"api_key_name": "gemini_key", "base_url": "https://example.invalid"},
        },
        # no gemini_key value and no api_key.json → should fail
    }
    ok, errors = preflight_unattended(cfg)
    assert ok is False
    assert any("API key" in e or "api key" in e.lower() for e in errors)


def test_preflight_skips_non_unattended_mode(tmp_path):
    from core.preflight import preflight_unattended

    ok, errors = preflight_unattended({"cli_mode": {"mode": "semi_attended"}})
    assert ok is True
    assert errors == []


def test_unattended_config_seed_queue_order():
    from core.cli_modes import UnattendedConfig

    cfg = {
        "cli_mode": {
            "unattended": {
                "seed_task": "first",
                "seed_tasks": ["second", "third"],
                "max_duration_hours": 1.5,
                "min_idle_minutes": 30,
                "exit_on_preflight_failure": True,
            }
        }
    }
    uc = UnattendedConfig.from_config(cfg)
    assert uc.max_duration_hours == 1.5
    assert uc.min_idle_minutes == 30.0
    assert uc.exit_on_preflight_failure is True
    assert uc._seed_queue == ["first", "second", "third"]
