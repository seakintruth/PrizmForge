"""Workstream E §7.2: secret files and caches excluded from agent-visible files."""

from __future__ import annotations

import pytest

from core.file_operations import is_secret_path, should_ignore_file


@pytest.mark.parametrize(
    "path",
    [
        "api_key.json",
        "config/api_key_local.json",
        ".env",
        ".env.local",
        "credentials.json",
        "secrets.py",
    ],
)
def test_is_secret_path_detects_secrets(path):
    assert is_secret_path(path) is True


@pytest.mark.parametrize(
    "path",
    ["app.py", "src/models/user.py", "docs/readme.md", "main.c"],
)
def test_is_secret_path_allows_normal_source(path):
    assert is_secret_path(path) is False


def test_should_ignore_file_blocks_cache_and_state(mock_minimal_config):
    assert should_ignore_file(".ruff_cache/x.py") is True
    assert should_ignore_file(".PrizmForge/agents.db") is True
    assert should_ignore_file("app/__pycache__/mod.py") is True
    assert should_ignore_file("src/app.py") is False
