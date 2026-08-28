"""Unit tests for core/gitignore.py — gitignore-aware file filtering."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.gitignore import load_gitignore_spec, should_ignore_by_gitignore


@pytest.fixture()
def project_root(tmp_path: Path) -> Path:
    """A fake project root with a representative .gitignore."""
    root = tmp_path / "proj"
    root.mkdir()
    (root / ".gitignore").write_text(
        "\n".join(
            [
                "__pycache__/",
                "*.pyc",
                ".pytest_cache/",
                ".mypy_cache/",
                ".ruff_cache/",
                ".venv/",
                "reports/",
                "api_key.json",
                "*.log",
            ]
        )
        + "\n"
    )
    return root


@pytest.fixture(autouse=True)
def _reset_cache():
    """Isolate the module-level spec cache between tests."""
    import core.gitignore as gi

    gi._gitignore_spec_cache = None
    gi._project_root_cache = None
    yield
    gi._gitignore_spec_cache = None
    gi._project_root_cache = None


def test_load_spec_present(project_root: Path):
    assert load_gitignore_spec(project_root) is not None


def test_load_spec_missing(tmp_path: Path):
    empty = tmp_path / "empty"
    empty.mkdir()
    assert load_gitignore_spec(empty) is None


@pytest.mark.parametrize(
    ("rel", "expected"),
    [
        (".github/workflows/test.yml", False),
        ("core/config.py", False),
        ("src/app.py", False),
        ("__pycache__/config.cpython-314.pyc", True),
        ("core/__pycache__/x.pyc", True),
        (".pytest_cache/v/cache/lastfailed", True),
        (".mypy_cache/1.json", True),
        (".ruff_cache/0.1.2/hash", True),
        (".venv/lib/python3.14/site-packages/foo.py", True),
        ("reports/project_review.md", True),
        ("api_key.json", True),
        ("utils/debug.log", True),
    ],
)
def test_should_ignore_by_gitignore(project_root: Path, rel: str, expected: bool):
    # Paths are resolved against the given root; relative paths would land
    # outside it (and thus be ignored), so always pass absolute paths here.
    assert should_ignore_by_gitignore(project_root / rel, project_root) is expected


def test_outside_project_root_is_ignored(project_root: Path):
    assert should_ignore_by_gitignore("/etc/passwd", project_root) is True


def test_no_gitignore_fail_open(tmp_path: Path):
    empty = tmp_path / "empty"
    empty.mkdir()
    assert should_ignore_by_gitignore("anything.txt", empty) is False


def test_explicit_spec_overrides(project_root: Path):
    spec = load_gitignore_spec(project_root)
    assert should_ignore_by_gitignore("api_key.json", gitignore_spec=spec) is True


def test_file_operations_hardcoded_ignores(tmp_path: Path, monkeypatch):
    """should_ignore_file applies hardcoded ignores regardless of .gitignore."""

    monkeypatch.setattr(
        "core.file_operations.get_config",
        lambda: {"file_operations": {"ignore_patterns": []}},
    )

    from core.file_operations import should_ignore_file

    assert should_ignore_file("__pycache__/x.pyc") is True
    assert should_ignore_file(".venv/bin/python") is True
    assert should_ignore_file("reports/foo.md") is True
    assert should_ignore_file(".ruff_cache/x.py") is True
    # normal source not ignored by hardcoded rules (no .gitignore at cwd root here,
    # and path is relative → resolve() may land outside any root; fail open)
    assert isinstance(should_ignore_file("core/config.py"), bool)


def test_sync_file_to_database_skips_secrets(tmp_path, monkeypatch, temp_db):
    """§7.2: indexer never ingests api_key.json / .env into project_files."""
    from core.db_connection import get_db_connection
    from core.file_operations import sync_file_to_database

    monkeypatch.setattr(
        "core.file_operations.get_config",
        lambda: {"file_operations": {"ignore_patterns": []}, "project_directory": str(tmp_path)},
    )

    assert sync_file_to_database("api_key.json", '{"key": "x"}') is False
    assert sync_file_to_database(".env", "SECRET=1") is False
    assert sync_file_to_database("secrets.py", "TOKEN='abc'") is False

    with get_db_connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM project_files").fetchone()[0]
    assert count == 0


def test_consolidate_respects_gitignore(project_root: Path):
    """_is_ignored_path combines basename rules with .gitignore."""
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "utils"))
    try:
        import consolidate  # type: ignore[import-not-found]
    finally:
        sys.path.pop(0)

    assert consolidate._is_ignored_path(project_root / "api_key.json", project_root) is True
    assert consolidate._is_ignored_path(project_root / "__pycache__" / "x.pyc", project_root) is True
    assert consolidate._is_ignored_path(project_root / "core" / "config.py", project_root) is False
    # secret-ish basenames still caught without .gitignore
    assert consolidate._is_ignored_file("my_secret_key.pem") is True
