"""
Target-repo structural index context for agents.

Preference order:
1. SQLite ``file_symbols`` → JSON slices (hybrid plan source of truth)
2. Markdown ``.PrizmForge/indexes/*.md`` fallback (export view)

Refresh: rebuild symbols (+ optional Markdown export) after init / materialize.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Sequence
from pathlib import Path

DEFAULT_MAX_CHARS = 24_000
_last_refresh_mono: float = 0.0
_MIN_REFRESH_INTERVAL_SEC = 2.0

logger = logging.getLogger(__name__)


def indexes_dir(project_directory: str | None = None) -> Path:
    if project_directory is None:
        from core.config import get_config

        project_directory = get_config().get("project_directory", "./project")
    return Path(project_directory).expanduser().resolve() / ".PrizmForge" / "indexes"


def load_index_text(
    *,
    which: str = "combined",
    project_directory: str | None = None,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> str:
    """Load Markdown index export (fallback / human view)."""
    names = {
        "combined": "INDEX.md",
        "production": "index_production.md",
        "test": "index_tests.md",
        "markdown": "index_docs.md",
        "docs": "index_docs.md",
    }
    if which not in names:
        raise ValueError(f"Unknown index which={which!r}; expected one of: {', '.join(sorted(names))}")
    base = indexes_dir(project_directory)
    path = base / names[which]
    if not path.is_file():
        return ""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        logger.warning("Could not read index %s: %s", path, e)
        return ""
    if max_chars and len(text) > max_chars:
        return text[:max_chars] + f"\n\n... truncated ({len(text)} chars total; see {path})\n"
    return text


def load_symbol_json_context(
    *,
    file_paths: Sequence[str] | None = None,
    max_rows: int = 80,
    path_prefix: str | None = None,
    label: str = "Structural symbols (JSON)",
) -> str:
    """Primary agent context: JSON table from sqlite file_symbols."""
    try:
        from core.symbol_index import fetch_symbol_rows, format_symbol_context_block
    except ImportError as e:
        logger.warning("symbol_index unavailable for JSON context: %s", e)
        return ""
    rows = fetch_symbol_rows(
        file_paths=file_paths,
        path_prefix=path_prefix,
        limit=max_rows,
    )
    return format_symbol_context_block(rows, max_rows=max_rows, label=label)


def build_index_context_block(
    *,
    project_directory: str | None = None,
    max_chars: int = 8_000,
    max_rows: int = 80,
    file_paths: Sequence[str] | None = None,
    label: str = "Target repository structural index",
) -> str:
    """
    JSON-first symbol slice; Markdown INDEX fallback if DB empty.
    """
    json_block = load_symbol_json_context(
        file_paths=file_paths,
        max_rows=max_rows,
        label=f"{label} (JSON)",
    )
    if json_block.strip():
        if max_chars and len(json_block) > max_chars:
            return json_block[:max_chars] + "\n... truncated\n"
        return json_block

    body = load_index_text(
        which="combined",
        project_directory=project_directory,
        max_chars=max_chars,
    )
    if not body.strip():
        return f"**{label}:** not available. Run CLI `init` to build `file_symbols` and/or `.PrizmForge/indexes/INDEX.md`.\n"
    return f"**{label}** (Markdown fallback):\n\n{body}\n"


def index_paths_summary(project_directory: str | None = None) -> dict[str, str]:
    base = indexes_dir(project_directory)
    out = {}
    for name in ("INDEX.md", "index_production.md", "index_tests.md", "index_docs.md"):
        p = base / name
        if p.is_file():
            out[name] = str(p)
    return out


def refresh_target_indexes(
    *,
    project_directory: str | None = None,
    full_dump: bool = False,
    force: bool = False,
    symbols_only: bool = False,
) -> dict:
    """
    Rebuild sqlite symbols (always) and optional Markdown export.

    Throttled unless force=True. Non-fatal at call sites.
    """
    global _last_refresh_mono
    now = time.monotonic()
    if not force and (now - _last_refresh_mono) < _MIN_REFRESH_INTERVAL_SEC:
        return {"status": "skipped", "reason": "throttled"}

    if project_directory is None:
        from core.config import get_config

        project_directory = get_config().get("project_directory", "./project")
    root = str(Path(project_directory).expanduser().resolve())

    result: dict = {"status": "ok"}
    try:
        from core.symbol_index import rebuild_project_symbols

        result["symbols"] = rebuild_project_symbols(root)
    except Exception as e:
        result["symbols_error"] = str(e)

    if not symbols_only:
        try:
            from utils.consolidate import generate_target_indexes

            out = str(Path(root) / ".PrizmForge" / "indexes")
            result["markdown"] = generate_target_indexes(root, out, full_dump=full_dump)
        except Exception as e:
            result["markdown_error"] = str(e)

    _last_refresh_mono = time.monotonic()
    return result


def refresh_file_symbols(file_path: str, content: str) -> int:
    """Incremental: upsert symbols for one relative path after materialize."""
    from core.symbol_index import upsert_file_symbols

    return upsert_file_symbols(file_path, content)
