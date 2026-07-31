#!/usr/bin/env python3
"""
Export the PrizmForge project to a zip archive (includes ``report/``).

Pipeline (default)
------------------
1. Run ``utils/consolidate.py`` so indexes and ``project_review.md`` are fresh
   (each generated file starts with a ``Generated: <UTC>`` timestamp).
2. Pack the project tree into a zip next to the project directory.

Output
------
Default path: ``<parent-of-project>/<project-folder-name>.zip``

Example::

    /path/to/artifacts/PrizmForge-multi-agent/     # project
    /path/to/artifacts/PrizmForge-multi-agent.zip  # archive

The archive root entry is ``PrizmForge-multi-agent/...`` unless ``--flat``.

Included
--------
- Source, tests, configs, docs
- ``report/`` (INDEX, split indexes, project_review, plans, archived plans)

Excluded
--------
``__pycache__``, ``.pytest_cache``, ``.git``, venvs, ``*.pyc``, coverage,
SQLite WAL/journal sidecars, accidental ``C:`` path artifacts, etc.

Usage
-----
::

    python utils/export_project_zip.py
    python utils/export_project_zip.py --skip-consolidate
    python utils/export_project_zip.py --out /path/to/out.zip
    python utils/export_project_zip.py --flat
    python utils/export_project_zip.py --allow-fail
    python -m utils.export_project_zip

Options
-------
--root PATH           Project root (default: directory with config.json)
--out PATH            Zip path (default: sibling of project dir)
--flat                Do not prefix paths with the project folder name
--skip-consolidate    Skip regenerate of report/ before packing
--allow-fail          Write zip even if consolidate fails

Tests are not run by this script; use ``bash utils/run_fast_tests.sh`` or pytest.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

SKIP_DIR_NAMES = {
    "__pycache__",
    ".pytest_cache",
    ".git",
    ".mypy_cache",
    ".ruff_cache",
    "htmlcov",
    "venv",
    ".venv",
    "node_modules",
    ".tox",
    "dist",
    "build",
    "exports",
}

SKIP_SUFFIXES = {
    ".pyc",
    ".pyo",
    ".db-journal",
    ".db-wal",
    ".db-shm",
}

SKIP_FILE_NAMES = {
    ".coverage",
    ".DS_Store",
}


def discover_project_root(start: Path | None = None) -> Path:
    """Directory containing config.json (walk up from start or this file)."""
    candidates: list[Path] = []
    if start is not None:
        candidates.append(start.resolve())
    candidates.append(Path.cwd().resolve())
    here = Path(__file__).resolve().parent
    candidates.append(here)
    candidates.append(here.parent)

    seen: set[Path] = set()
    for base in candidates:
        cur = base
        for _ in range(12):
            if cur in seen:
                break
            seen.add(cur)
            if (cur / "config.json").is_file():
                return cur
            if cur.parent == cur:
                break
            cur = cur.parent
    return Path.cwd().resolve()


def should_skip(path: Path, root: Path) -> bool:
    try:
        rel_parts = path.relative_to(root).parts
    except ValueError:
        return True
    if any(p in SKIP_DIR_NAMES for p in rel_parts):
        return True
    if path.suffix in SKIP_SUFFIXES:
        return True
    if path.name in SKIP_FILE_NAMES:
        return True
    if any(p.startswith("C:") or p == "C:" for p in rel_parts):
        return True
    return False


def run_consolidate(project_root: Path) -> int:
    script = project_root / "utils" / "consolidate.py"
    if not script.is_file():
        print(f"WARNING: consolidate.py not found at {script}", file=sys.stderr)
        return 1
    print("Running consolidate.py ...")
    proc = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(project_root),
    )
    if proc.returncode != 0:
        print(f"ERROR: consolidate failed (exit {proc.returncode})", file=sys.stderr)
    else:
        print("OK: consolidate complete")
    return proc.returncode


def export_zip(
    project_root: Path,
    out_path: Path,
    *,
    include_name_prefix: bool = True,
) -> dict:
    project_root = project_root.resolve()
    out_path = out_path.resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    prefix = project_root.name if include_name_prefix else ""
    count = 0
    report_count = 0
    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(project_root.rglob("*")):
            if not path.is_file():
                continue
            if should_skip(path, project_root):
                continue
            rel = path.relative_to(project_root).as_posix()
            if path.resolve() == out_path:
                continue
            if rel.startswith("report/"):
                report_count += 1
            arc = f"{prefix}/{rel}" if prefix else rel
            zf.write(path, arcname=arc)
            count += 1

    size = out_path.stat().st_size
    return {
        "path": str(out_path),
        "files": count,
        "report_files": report_count,
        "bytes": size,
        "root": str(project_root),
        "when": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Consolidate and export PrizmForge to zip (includes report/)"
    )
    parser.add_argument(
        "--root",
        default=None,
        help="Project root (default: discover via config.json)",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Output zip path (default: <parent>/<project-name>.zip)",
    )
    parser.add_argument(
        "--flat",
        action="store_true",
        help="Omit top-level project folder name inside the zip",
    )
    parser.add_argument(
        "--skip-consolidate",
        action="store_true",
        help="Do not run utils/consolidate.py before zip",
    )
    parser.add_argument(
        "--allow-fail",
        action="store_true",
        help="Still write the zip if consolidate fails",
    )
    args = parser.parse_args(argv)

    root = Path(args.root).resolve() if args.root else discover_project_root()
    if not (root / "config.json").is_file():
        print(f"WARNING: No config.json under {root} — continuing", file=sys.stderr)

    if args.out:
        out = Path(args.out)
    else:
        out = root.parent / f"{root.name}.zip"

    if not args.skip_consolidate:
        rc = run_consolidate(root)
        if rc != 0 and not args.allow_fail:
            return rc

    print(f"Exporting {root}")
    print(f"  -> {out}")
    result = export_zip(root, out, include_name_prefix=not args.flat)
    print(f"OK: Wrote {result['path']}")
    print(f"  Files: {result['files']} (report/: {result['report_files']})")
    print(
        f"  Size:  {result['bytes']:,} bytes "
        f"({result['bytes'] / 1024 / 1024:.2f} MB)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
