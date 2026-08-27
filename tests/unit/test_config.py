"""Unit coverage for core.config pure helpers (path normalize, find, validate)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from core.config import (
    ensure_project_directory,
    find_config_file,
    get_package_root,
    get_repo_root,
    load_config,
    normalize_path,
    validate_config,
)

# ---------------------------------------------------------------------------
# normalize_path
# ---------------------------------------------------------------------------


def test_normalize_path_empty_returns_dot():
    p = normalize_path("")
    assert p == Path(".") or p == Path(".").resolve()


def test_normalize_path_absolute_unix(tmp_path):
    target = tmp_path / "abs_target"
    target.mkdir()
    result = normalize_path(str(target))
    assert result.is_absolute()
    assert result == target.resolve()


def test_normalize_path_relative_uses_package_root_by_default():
    result = normalize_path("rel_dir")
    assert result == (get_package_root() / "rel_dir").resolve()


def test_normalize_path_relative_respects_base(tmp_path):
    forge = tmp_path / "PrizmForge"
    forge.mkdir()
    result = normalize_path("../HumanHaunt", base=forge)
    assert result == (tmp_path / "HumanHaunt").resolve()


def test_normalize_path_home_expand(monkeypatch, tmp_path):
    """expanduser is deterministic when HOME/USERPROFILE point at tmp_path.

    POSIX uses HOME; Windows uses USERPROFILE (HOME alone is ignored).
    """
    home = str(tmp_path)
    monkeypatch.setenv("HOME", home)
    monkeypatch.setenv("USERPROFILE", home)
    if os.name == "nt":
        drive, tail = os.path.splitdrive(home)
        if drive:
            monkeypatch.setenv("HOMEDRIVE", drive)
            monkeypatch.setenv("HOMEPATH", tail if tail.startswith("\\") else "\\" + tail.lstrip("\\/"))
    (tmp_path / "home_file").write_text("x", encoding="utf-8")
    result = normalize_path("~/home_file")
    assert result == (tmp_path / "home_file").resolve()


def test_normalize_path_mixed_slashes(tmp_path, monkeypatch):
    """On Windows backslash is a separator; on POSIX it is a literal character.
    Path() already normalizes forward slashes on every platform."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "b").mkdir()
    result = normalize_path("a/b", base=tmp_path)
    assert result == (tmp_path / "a" / "b").resolve()
    if os.name == "nt":
        result_bs = normalize_path("a\\b", base=tmp_path)
        assert result_bs == (tmp_path / "a" / "b").resolve()


# ---------------------------------------------------------------------------
# find_config_file
# ---------------------------------------------------------------------------


def test_find_config_file_in_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = tmp_path / "config.json"
    cfg.write_text("{}")
    found = find_config_file("config.json")
    assert found == cfg


def test_find_config_file_in_parent(tmp_path, monkeypatch):
    parent = tmp_path
    child = tmp_path / "subdir"
    child.mkdir()
    (parent / "config.json").write_text("{}")
    monkeypatch.chdir(child)
    found = find_config_file("config.json")
    assert found == parent / "config.json"


def test_find_config_file_defaults_to_package_root_when_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    found = find_config_file("no_such_config_xyz.json")
    assert found == get_package_root() / "no_such_config_xyz.json"
    assert not found.exists()


# ---------------------------------------------------------------------------
# get_repo_root / ensure_project_directory / load_config path anchor
# ---------------------------------------------------------------------------


def test_get_repo_root_falls_back_to_package_root(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from core import config as cfg_mod

    monkeypatch.setattr(cfg_mod, "find_config_file", lambda name: tmp_path / name)
    root = get_repo_root()
    assert root == get_package_root()


def test_get_repo_root_from_config_location(tmp_path, monkeypatch):
    (tmp_path / "config.json").write_text(json.dumps({"project_directory": "./project"}))
    monkeypatch.chdir(tmp_path)
    root = get_repo_root()
    assert root == tmp_path.resolve()


def test_load_config_project_directory_ignores_cwd(tmp_path, monkeypatch):
    """../HumanHaunt must resolve from config.json's directory, not the caller's cwd."""
    forge = tmp_path / "PrizmForge"
    utils = forge / "utils"
    haunt = tmp_path / "HumanHaunt"
    forge.mkdir()
    utils.mkdir()
    haunt.mkdir()
    cfg_path = forge / "config.json"
    cfg_path.write_text(json.dumps({"project_directory": "../HumanHaunt"}), encoding="utf-8")
    monkeypatch.chdir(utils)

    loaded = load_config(str(cfg_path))
    assert Path(loaded["project_directory"]) == haunt.resolve()


def test_ensure_project_directory_creates(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.json").write_text(json.dumps({"project_directory": "./my_proj"}))
    from core import config as cfg_mod

    def fake_get():
        return {"project_directory": str(tmp_path / "my_proj")}

    monkeypatch.setattr(cfg_mod, "get_config", fake_get)
    path = ensure_project_directory()
    assert path.exists()
    assert path.is_dir()
    assert path.name == "my_proj"


def test_ensure_project_directory_absolute(tmp_path, monkeypatch):
    from core import config as cfg_mod

    abs_proj = tmp_path / "abs_project"
    monkeypatch.setattr(
        cfg_mod,
        "get_config",
        lambda: {"project_directory": str(abs_proj)},
    )
    path = ensure_project_directory()
    assert path == abs_proj.resolve()
    assert path.exists()


# ---------------------------------------------------------------------------
# validate_config
# ---------------------------------------------------------------------------


def test_validate_config_requires_project_directory():
    with pytest.raises(ValueError, match="project_directory"):
        validate_config({})


def test_validate_config_rejects_non_string_project_directory():
    with pytest.raises(ValueError, match="project_directory"):
        validate_config({"project_directory": 123})


def test_validate_config_accepts_minimal(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.json").write_text("{}")
    cfg = {"project_directory": str(tmp_path / "proj")}
    validate_config(cfg)
    assert (tmp_path / "proj").exists()


def test_validate_config_rejects_unknown_file_editing_method(tmp_path):
    with pytest.raises(ValueError, match=r"file_editing\.method"):
        validate_config(
            {
                "project_directory": str(tmp_path / "p"),
                "file_editing": {"method": "telepathy"},
            }
        )


def test_validate_config_rejects_bad_preferred_modes(tmp_path):
    with pytest.raises(ValueError, match="preferred_modes"):
        validate_config(
            {
                "project_directory": str(tmp_path / "p"),
                "file_editing": {"preferred_modes": []},
            }
        )


def test_validate_config_rejects_unknown_preferred_mode(tmp_path):
    with pytest.raises(ValueError, match="unknown modes"):
        validate_config(
            {
                "project_directory": str(tmp_path / "p"),
                "file_editing": {"preferred_modes": ["guid", "warp"]},
            }
        )


def test_validate_config_rejects_bad_threshold(tmp_path):
    with pytest.raises(ValueError, match="small_file_threshold_lines"):
        validate_config(
            {
                "project_directory": str(tmp_path / "p"),
                "file_editing": {"small_file_threshold_lines": 0},
            }
        )


def test_validate_config_accepts_known_modes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.json").write_text("{}")
    cfg = {
        "project_directory": str(tmp_path / "ok"),
        "file_editing": {
            "method": "guid",
            "preferred_modes": ["guid", "find_replace"],
            "fallback_order": ["guid", "diff", "find_replace", "full_replace"],
            "small_file_threshold_lines": 180,
        },
        "content_safety": {
            "disallow_binary_content": True,
            "blocked_extensions": [".exe", ".bin"],
        },
    }
    validate_config(cfg)


def test_validate_config_rejects_bad_content_safety_type(tmp_path):
    with pytest.raises(ValueError, match="content_safety"):
        validate_config(
            {
                "project_directory": str(tmp_path / "p"),
                "content_safety": "not-a-dict",
            }
        )


def test_validate_config_rejects_non_bool_disallow_binary(tmp_path):
    with pytest.raises(ValueError, match="disallow_binary_content"):
        validate_config(
            {
                "project_directory": str(tmp_path / "p"),
                "content_safety": {"disallow_binary_content": "yes"},
            }
        )


# ---------------------------------------------------------------------------
# validate_config: slashed model IDs (OpenRouter-style 'vendor/model' IDs)
# ---------------------------------------------------------------------------


def _slashed_cfg(tmp_path) -> dict:
    return {
        "project_directory": str(tmp_path / "p"),
        "default_endpoint": "openrouter",
        "default_model": "openrouter/stealth/ox-alpha",
        "endpoints": {
            "openrouter": {
                "base_url": "https://openrouter.example/v1/chat/completions",
                "models": {
                    "stealth/ox-alpha": {},
                    "openai/gpt-4o": {},
                },
            },
            "backup": {
                "base_url": "https://backup.example/v1/chat/completions",
                "models": {
                    "openai/gpt-4o": {},
                },
            },
        },
        "agent_model_preferences": {
            "orchestrator": "openrouter/stealth/ox-alpha",
            "developer": "backup/openai/gpt-4o",
        },
        "resource_controller": {
            "model_downgrades": {
                "critical": {"developer": "openai/gpt-4o"},
            }
        },
    }


def test_validate_config_accepts_slashed_model_ids(tmp_path):
    cfg = _slashed_cfg(tmp_path)
    validate_config(cfg)


def test_validate_config_accepts_bare_slashed_model_id(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.json").write_text("{}")
    cfg = _slashed_cfg(tmp_path)
    cfg["default_model"] = "stealth/ox-alpha"
    validate_config(cfg)


def test_validate_config_rejects_unknown_slashed_reference(tmp_path):
    cfg = _slashed_cfg(tmp_path)
    cfg["agent_model_preferences"]["reviewer"] = "openrouter/no/such-model"
    with pytest.raises(ValueError, match="unknown or ambiguous model reference"):
        validate_config(cfg)


def test_validate_config_rejects_ambiguous_bare_id_without_prefix(tmp_path):
    cfg = _slashed_cfg(tmp_path)
    cfg["default_model"] = "backup/openai/gpt-4o"
    validate_config(cfg)
