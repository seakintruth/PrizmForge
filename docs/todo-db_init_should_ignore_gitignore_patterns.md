
---

### 1. New file: `core/gitignore.py`

Create this file exactly as shown:

```python
"""
core/gitignore.py
Gitignore-aware file filtering for PrizmForge.

Respects the project's .gitignore exactly like Git does.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pathspec


_gitignore_spec_cache: Optional[pathspec.PathSpec] = None
_project_root_cache: Optional[Path] = None


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
```

---

### 2. Integration Patches

#### A. `core/file_operations.py` (Main sync path)

Add near the top with other imports:

```python
from core.gitignore import should_ignore_by_gitignore, load_gitignore_spec
```

Then **replace** your current `should_ignore_file()` function with this improved version:

```python
def should_ignore_file(path: str) -> bool:
    """Return True if the file should be ignored (hardcoded + .gitignore)."""
    p = Path(path)

    # Hardcoded safety ignores (always applied)
    hardcoded = {
        ".git",
        "__pycache__",
        ".venv",
        "venv",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        "node_modules",
        "build",
        "dist",
        ".PrizmForge",
        "reports",
    }
    if any(part in hardcoded for part in p.parts):
        return True

    # Respect .gitignore
    try:
        if should_ignore_by_gitignore(path):
            return True
    except Exception:
        pass  # Fail open on any error

    return False
```

Also update `sync_file_to_database()` to use it early:

```python
def sync_file_to_database(file_path: str, ...) -> dict:
    if should_ignore_file(file_path):
        return {"status": "ignored", "reason": "gitignore or hardcoded ignore"}
    ...
```

#### B. `core/symbol_index.py`

In `rebuild_project_symbols()`, wrap the file walk:

```python
from core.gitignore import should_ignore_by_gitignore

def rebuild_project_symbols(...) -> int:
    ...
    for py_file in root.rglob("*.py"):
        if should_ignore_by_gitignore(py_file):
            continue
        ...
```

#### C. `utils/consolidate.py`

Replace the existing `_is_ignored_file()` function with:

```python
from core.gitignore import should_ignore_by_gitignore


def _is_ignored_file(path: Path, project_root: Path) -> bool:
    """Check both hardcoded ignores and .gitignore."""
    ignored_dirs = {
        ".git",
        ".github",
        "__pycache__",
        ".venv",
        "venv",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        "node_modules",
        "build",
        "dist",
        ".PrizmForge",
        "reports",
    }
    if any(part in ignored_dirs for part in path.parts):
        return True

    return should_ignore_by_gitignore(path, project_root)
```

Then update `collect_indexes()` and `classify_path()` to call this function.

---

### 3. Add dependency

Add to both `requirements.txt` and `requirements-dev.txt`:

```txt
pathspec>=0.12.1
```

Then run:

```bash
pip install pathspec
# or
python -m pip install -r requirements.txt -r requirements-dev.txt
```

---

### Verification

After applying the changes, run:

```bash
python -c "
from core.gitignore import load_gitignore_spec, should_ignore_by_gitignore
from core.config import get_repo_root
root = get_repo_root()
print('Loaded .gitignore:', load_gitignore_spec(root) is not None)
print('.github ignored:', should_ignore_by_gitignore('.github/workflows/test.yml'))
print('.pytest_cache ignored:', should_ignore_by_gitignore('.pytest_cache/v/cache/lastfailed'))
print('src/app.py ignored:', should_ignore_by_gitignore('src/app.py'))
"
```

You should see `.github` and `.pytest_cache` correctly ignored, while normal source files are not.

---

Would you like me to also generate a small test for this new functionality (`tests/unit/test_gitignore.py`)?