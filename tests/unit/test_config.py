"""Unit coverage for core.config pure helpers (path normalize, find, validate)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.config import (
    ensure_project_directory,
    find_config_file,
    get_repo_root,
    normalize_path,
    validate_config,
)

# ---------------------------------------------------------------------------
# normalize_path
# ---------------------------------------------------------------------------


def test_normalize_path_empty_returns_dot():
    assert normalize_path("") == Path(".").resolve() or normalize_path("") == Path(".")
    # Implementation returns Path(".") then may resolve; accept either resolved or relative
    p = normalize_path("")
    assert p == Path(".") or p == Path(".").resolve()


def test_normalize_path_absolute_unix(tmp_path):
    target = tmp_path / "abs_target"
    target.mkdir()
    result = normalize_path(str(target))
    assert result.is_absolute()
    assert result == target.resolve()


def test_normalize_path_relative_resolves_to_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "rel_dir").mkdir()
    result = normalize_path("rel_dir")
    assert result == (tmp_path / "rel_dir").resolve()


def test_normalize_path_home_expand(monkeypatch, tmp_path):
    # Point HOME at tmp so expanduser is deterministic
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / "home_file").write_text("x")
    result = normalize_path("~/home_file")
    assert result == (tmp_path / "home_file").resolve()


def test_normalize_path_mixed_slashes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "b").mkdir()
    result = normalize_path("a\\b")  # backslash on Unix still works via Path
    assert result == (tmp_path / "a" / "b").resolve()


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


def test_find_config_file_defaults_to_cwd_when_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    found = find_config_file("no_such_config_xyz.json")
    assert found == tmp_path / "no_such_config_xyz.json"
    assert not found.exists()


# ---------------------------------------------------------------------------
# get_repo_root / ensure_project_directory
# ---------------------------------------------------------------------------


def test_get_repo_root_falls_back_to_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # No config.json in search path → cwd
    root = get_repo_root()
    assert root == tmp_path.resolve()


def test_get_repo_root_from_config_location(tmp_path, monkeypatch):
    (tmp_path / "config.json").write_text(json.dumps({"project_directory": "./project"}))
    monkeypatch.chdir(tmp_path)
    root = get_repo_root()
    assert root == tmp_path.resolve()


def test_ensure_project_directory_creates(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.json").write_text(json.dumps({"project_directory": "./my_proj"}))
    # Patch get_config to avoid full load_config side effects
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
    (tmp_path / "config.json").write_text("{}")  # for get_repo_root
    cfg = {"project_directory": str(tmp_path / "proj")}
    # Should not raise; creates the directory
    validate_config(cfg)
    assert (tmp_path / "proj").exists()


def test_validate_config_rejects_unknown_file_editing_method():
    with pytest.raises(ValueError, match="file_editing.method"):
        validate_config(
            {
                "project_directory": "./p",
                "file_editing": {"method": "telepathy"},
            }
        )


def test_validate_config_rejects_bad_preferred_modes():
    with pytest.raises(ValueError, match="preferred_modes"):
        validate_config(
            {
                "project_directory": "./p",
                "file_editing": {"preferred_modes": []},
            }
        )


def test_validate_config_rejects_unknown_preferred_mode():
    with pytest.raises(ValueError, match="unknown modes"):
        validate_config(
            {
                "project_directory": "./p",
                "file_editing": {"preferred_modes": ["guid", "warp"]},
            }
        )


def test_validate_config_rejects_bad_threshold():
    with pytest.raises(ValueError, match="small_file_threshold_lines"):
        validate_config(
            {
                "project_directory": "./p",
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
    validate_config(cfg)  # must not raise


def test_validate_config_rejects_bad_content_safety_type():
    with pytest.raises(ValueError, match="content_safety"):
        validate_config(
            {
                "project_directory": "./p",
                "content_safety": "not-a-dict",
            }
        )


def test_validate_config_rejects_non_bool_disallow_binary():
    with pytest.raises(ValueError, match="disallow_binary_content"):
        validate_config(
            {
                "project_directory": "./p",
                "content_safety": {"disallow_binary_content": "yes"},
            }
        )
