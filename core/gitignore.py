"""
core/gitignore.py
Gitignore-aware file filtering for PrizmForge.

Respects the project's .gitignore exactly like Git does.
"""

from __future__ import annotations

from pathlib import Path

import pathspec

_gitignore_spec_cache: pathspec.PathSpec | None = None
_project_root_cache: Path | None = None


def load_gitignore_spec(project_root: Path | None = None) -> pathspec.PathSpec | None:
    """
    Load and cache the .gitignore file from the project root.
    Supports the standard gitwildmatch syntax used by Git.
    """
    global _gitignore_spec_cache, _project_root_cache

    if project_root is None:
        from core.config import get_repo_root

        project_root = get_repo_root()

    if _project_root_cache == project_root and _gitignore_spec_cache is not None:
        return _gitignore_spec_cache

    gitignore_file = Path(project_root) / ".gitignore"
    if not gitignore_file.exists():
        _gitignore_spec_cache = None
        _project_root_cache = project_root
        return None

    try:
        with open(gitignore_file, encoding="utf-8") as f:
            lines = f.readlines()

        spec = pathspec.PathSpec.from_lines("gitwildmatch", lines)
        _gitignore_spec_cache = spec
        _project_root_cache = project_root
        return spec
    except Exception:
        _gitignore_spec_cache = None
        return None


def should_ignore_by_gitignore(
    file_path: str | Path,
    project_root: Path | None = None,
    gitignore_spec: pathspec.PathSpec | None = None,
) -> bool:
    """
    Return True if the given path should be ignored according to .gitignore rules.

    This correctly handles:
        .github/
        .mypy_cache/
        .pytest_cache/
        .ruff_cache/
        __pycache__/
        *.log
        reports/
        etc.
    """
    if gitignore_spec is None:
        gitignore_spec = load_gitignore_spec(project_root)
        if gitignore_spec is None:
            return False

    try:
        if project_root is None:
            from core.config import get_repo_root

            project_root = get_repo_root()

        rel_path = Path(file_path).resolve().relative_to(Path(project_root).resolve())
    except (ValueError, OSError):
        return True  # Outside project root or invalid path → ignore

    # pathspec expects POSIX-style relative paths
    posix_path = rel_path.as_posix()
    return gitignore_spec.match_file(posix_path)
