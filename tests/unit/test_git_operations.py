"""
Tests for Workstream A (git/pre-commit closed loop) — RED phase.

Target behavior per docs/UNATTENDED_CLOSED_LOOP_PLAN.md §3:
- git operations return a structured GitResult (ok, code, stdout, stderr)
- failures are data, not just console prints
"""

from __future__ import annotations

import subprocess
from unittest.mock import patch

import pytest


@pytest.fixture
def git_enabled_config(tmp_path, monkeypatch):
    """Minimal config with git enabled, project dir in tmp.

    Patches utils.git_operations.get_config directly (its local binding),
    matching how tests/conftest.py isolates config for other modules.
    """
    project = tmp_path / "project"
    project.mkdir()
    cfg = {
        "git": True,
        "git_auto_commit": True,
        "project_directory": str(project),
    }
    import utils.git_operations as git_ops

    monkeypatch.setattr(git_ops, "get_config", lambda: cfg)
    return project


class TestGitCommitStructuredOutcome:
    """git_commit() must return a structured result, not None on failure."""

    def test_commit_success_returns_ok_result(self, git_enabled_config):
        from utils.git_operations import git_commit

        with patch("utils.git_operations.subprocess.run") as run:
            run.side_effect = [
                subprocess.CompletedProcess([], 0),  # git add
                subprocess.CompletedProcess([], 0, stdout="", stderr=""),  # commit
                subprocess.CompletedProcess([], 0, stdout="abc123def\n", stderr=""),  # rev-parse
            ]
            result = git_commit("src/app.py", "test message")

        assert isinstance(result, dict), f"expected dict, got {type(result)}"
        assert result["ok"] is True
        assert result["code"] == 0
        assert result["commit_hash"] == "abc123def"

    def test_commit_hook_failure_returns_failure_data(self, git_enabled_config):
        """Hook failure must produce structured failure data, not None."""
        from utils.git_operations import git_commit

        with patch("utils.git_operations.subprocess.run") as run:
            run.side_effect = [
                subprocess.CompletedProcess([], 0),  # git add ok
                subprocess.CompletedProcess(
                    [],
                    1,
                    stdout="ruff failed\nF401 unused import\n",
                    stderr="pre-commit hook failed",
                ),
            ]
            result = git_commit("src/broken.py", "test message")

        assert isinstance(result, dict)
        assert result["ok"] is False
        assert result["code"] == 1
        assert "F401" in result["stdout"]
        assert "pre-commit" in result["stderr"]
        assert result["file_path"] == "src/broken.py"

    def test_git_add_failure_returns_failure_data(self, git_enabled_config):
        """`git add` refusal (e.g. gitignored path) is a failure, not an exception."""
        from utils.git_operations import git_commit

        error = subprocess.CalledProcessError(128, "git add")
        error.stderr = "The following paths are ignored by one of your .gitignore files"
        with patch("utils.git_operations.subprocess.run") as run:
            run.side_effect = [error]
            result = git_commit("config.json", "test message")

        assert isinstance(result, dict)
        assert result["ok"] is False
        assert "gitignore" in result["stderr"]

    def test_timeout_returns_failure_data(self, git_enabled_config):
        from utils.git_operations import git_commit

        with patch("utils.git_operations.subprocess.run") as run:
            run.side_effect = subprocess.TimeoutExpired(cmd="git add", timeout=10)
            result = git_commit("src/slow.py", "test message")

        assert isinstance(result, dict)
        assert result["ok"] is False
        assert "timeout" in result["stage"].lower()

    def test_disabled_git_returns_not_attempted(self, monkeypatch, tmp_path):
        """Git disabled → explicit 'not attempted', distinct from failure."""

        import utils.git_operations as git_ops

        monkeypatch.setattr(
            git_ops,
            "get_config",
            lambda: {"git": False, "git_auto_commit": False},
        )
        result = git_ops.git_commit("src/x.py", "msg")

        assert isinstance(result, dict)
        assert result["ok"] is False
        assert result.get("attempted") is False

