"""Workstream E: environment card surfaces git/hook constraints (plan §7.3)."""

from __future__ import annotations

from core.repo_env import build_repo_env_card, detect_pre_commit_hook


def test_detect_pre_commit_hook_framework_config(tmp_path):
    (tmp_path / ".pre-commit-config.yaml").write_text("repos: []\n")
    assert detect_pre_commit_hook(str(tmp_path)) is True


def test_detect_pre_commit_hook_git_dir(tmp_path):
    hooks = tmp_path / ".git" / "hooks"
    hooks.mkdir(parents=True)
    (hooks / "pre-commit").write_text("#!/bin/sh\nruff check --fix\n")
    assert detect_pre_commit_hook(str(tmp_path)) is True


def test_detect_no_hook(tmp_path):
    assert detect_pre_commit_hook(str(tmp_path)) is False


def test_card_disabled_git(tmp_path):
    card = build_repo_env_card(str(tmp_path), git_enabled=False)
    assert "Git commit-on-write: disabled" in card
    assert "Pre-commit" not in card


def test_card_enabled_with_hook(tmp_path):
    (tmp_path / ".pre-commit-config.yaml").write_text("repos: []\n")
    card = build_repo_env_card(str(tmp_path), git_enabled=True)
    assert "Git commit-on-write: enabled" in card
    assert "Pre-commit hooks are enforced" in card


def test_card_enabled_without_hook(tmp_path):
    card = build_repo_env_card(str(tmp_path), git_enabled=True)
    assert "No pre-commit hooks detected" in card


def test_developer_prompt_includes_env_card(temp_db, tmp_path, monkeypatch):
    """The governed developer prompt surfaces the env card when git is enabled."""
    import core.config as config_mod
    from workflow.developer_edit import _build_generation_prompt

    original_get_config = config_mod.get_config

    def _cfg():
        c = dict(original_get_config())
        c["git"] = True
        c["git_auto_commit"] = True
        c["project_directory"] = str(tmp_path)
        return c

    config_mod.get_config = _cfg
    try:
        (tmp_path / ".pre-commit-config.yaml").write_text("repos: []\n")
        prompt = _build_generation_prompt(
            instructions="Change app.py",
            edit_method="find_replace",
            files_content=[],
            requested_files=["app.py"],
            task_id="t_env",
        )
        assert "**Repository environment:**" in prompt
        assert "Git commit-on-write: enabled" in prompt
        assert "Pre-commit hooks are enforced" in prompt
    finally:
        config_mod.get_config = original_get_config
