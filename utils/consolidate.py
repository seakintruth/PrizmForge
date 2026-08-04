#!/usr/bin/env python3
"""
Build structural code indexes and optional full source consolidation.

Writes under ``report/`` (or ``--out-dir`` / target ``.PrizmForge/indexes``):

+-------------------------+----------------------------------------------+
| File                    | Contents                                     |
+=========================+==============================================+
| INDEX.md                | Combined production + tests + docs indexes   |
| index_production.md     | Modules, classes, functions (AST)            |
| index_tests.md          | Test symbols                                 |
| index_docs.md           | Markdown headings                            |
| project_review.md       | Indexes + full file dump (default mode)      |
+-------------------------+----------------------------------------------+

Every generated file begins with::

    Generated: YYYY-MM-DDTHH:MM:SSZ

Path discovery
--------------
Project root is the directory containing ``config.json``, found by walking
upward from cwd (not from a sandbox copy of the script such as ``/box/script.py``).
That avoids writing to ``/report`` on Android Quick Edit and similar hosts.

``report/`` is not re-indexed as source (see ``IGNORED_DIRS``).

Usage
-----
::

    python utils/consolidate.py
    python -m utils.consolidate
    python utils/consolidate.py --indexes-only
    python utils/consolidate.py --target --indexes-only
    python utils/consolidate.py --root /path/to/tree --out-dir ./report

Options
-------
--root PATH       Tree to scan (default: discovered PrizmForge root)
--out-dir PATH    Where to write indexes / review
--indexes-only    INDEX + splits only (no full source dump)
--target          Use config ``project_directory``; write under
                  ``<root>/.PrizmForge/indexes``
--full            Also emit full ``project_review.md`` when using target/indexes-only

Related: ``utils/export_project_zip.py`` runs consolidate then packs the repo
(including ``report/``) into a sibling zip.
"""

from __future__ import annotations

import ast
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

IGNORED_DIRS = {
    "report",  # generated reviews/indexes; do not re-index
    ".git",
    "__pycache__",
    "venv",
    ".venv",
    "env",
    "ENV",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "htmlcov",
    "dist",
    "build",
    "exports",
    "node_modules",
    "C:",
}

IGNORED_FILES = {
    "api_key.json",
    "project_review.md",
    "INDEX.md",
    "index_production.md",
    "index_tests.md",
    "index_docs.md",
}

PRODUCTION_TOP = {
    "agents",
    "cli",
    "core",
    "file_editing",
    "workflow",
    "utils",
    "audit",
    "agent_schemas",
}

PRODUCTION_ROOT_FILES = {
    "main.py",
    "interactive.py",
}

TEST_TOP = {"tests"}


@dataclass
class PySymbol:
    kind: str
    name: str
    lineno: int
    qualname: str


@dataclass
class FileIndex:
    path: str
    kind: str
    symbols: List[PySymbol] = field(default_factory=list)
    sections: List[Tuple[int, str, str]] = field(default_factory=list)


def _should_skip_dir(name: str) -> bool:
    if name in IGNORED_DIRS:
        return True
    if name.startswith(".") and name not in {".github"}:
        return True
    return False


def classify_path(rel: str) -> str:
    """Classify relative path for indexing.

    For target repos (not only PrizmForge layout): any non-test .py is production.
    """
    parts = Path(rel).parts
    if not parts:
        return "other"
    if parts[0] in TEST_TOP or "/tests/" in f"/{rel}/" or rel.startswith("tests/"):
        return "test"
    if rel.endswith(".md"):
        return "markdown"
    if rel.endswith(".py"):
        return "production"
    if parts[0] in PRODUCTION_TOP:
        return "production"
    if Path(rel).name in PRODUCTION_ROOT_FILES:
        return "production"
    if rel.endswith((".json", ".sh")) and parts[0] in PRODUCTION_TOP:
        return "production"
    return "other"


def parse_python_symbols(source: str, module_path: str) -> List[PySymbol]:
    symbols: List[PySymbol] = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return symbols

    mod_name = module_path.replace("\\", "/").replace("/", ".")
    if mod_name.endswith(".py"):
        mod_name = mod_name[:-3]
    symbols.append(PySymbol("module", mod_name, 1, mod_name))

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            q = f"{mod_name}.{node.name}"
            symbols.append(PySymbol("class", node.name, node.lineno, q))
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    symbols.append(PySymbol("method", item.name, item.lineno, f"{q}.{item.name}"))
        elif isinstance(node, ast.FunctionDef):
            symbols.append(PySymbol("function", node.name, node.lineno, f"{mod_name}.{node.name}"))
        elif isinstance(node, ast.AsyncFunctionDef):
            symbols.append(
                PySymbol(
                    "async_function",
                    node.name,
                    node.lineno,
                    f"{mod_name}.{node.name}",
                )
            )
    return symbols


_MD_HEADER = re.compile(r"^(#{1,6})\s+(.*)$")


def parse_markdown_sections(source: str) -> List[Tuple[int, str, str]]:
    sections: List[Tuple[int, str, str]] = []
    for i, line in enumerate(source.splitlines(), start=1):
        m = _MD_HEADER.match(line.strip())
        if m:
            sections.append((len(m.group(1)), m.group(2).strip(), f"L{i}"))
    return sections


def collect_indexes(root_dir: str) -> Dict[str, List[FileIndex]]:
    buckets: Dict[str, List[FileIndex]] = {
        "production": [],
        "test": [],
        "markdown": [],
        "other": [],
    }
    root = Path(root_dir)

    for dirpath, dirnames, filenames in os.walk(root_dir):
        dirnames[:] = [d for d in dirnames if not _should_skip_dir(d)]
        for name in filenames:
            if name in IGNORED_FILES:
                continue
            path = Path(dirpath) / name
            rel = str(path.relative_to(root)).replace("\\", "/")
            if rel == "report/project_review.md":
                continue

            kind = classify_path(rel)
            entry = FileIndex(path=rel, kind=kind)

            if name.endswith(".py"):
                try:
                    text = path.read_text(encoding="utf-8")
                except Exception:
                    text = ""
                entry.symbols = parse_python_symbols(text, rel)
                buckets[kind if kind in buckets else "other"].append(entry)
            elif name.endswith(".md"):
                try:
                    text = path.read_text(encoding="utf-8")
                except Exception:
                    text = ""
                entry.sections = parse_markdown_sections(text)
                buckets["markdown"].append(entry)
            elif name.endswith((".json", ".sh")) and kind == "production":
                buckets["production"].append(entry)
            elif name.endswith((".json", ".sh")):
                buckets["other"].append(entry)

    for k in buckets:
        buckets[k].sort(key=lambda e: e.path)
    return buckets


def _write_production_index(out, files: List[FileIndex]) -> None:
    out.write("## Index: Production code\n\n")
    out.write(
        "Modules, classes, and top-level functions/methods under "
        "agents/, cli/, core/, file_editing/, workflow/, utils/, and root entrypoints.\n\n"
    )
    for entry in files:
        out.write(f"### `{entry.path}`\n\n")
        if not entry.symbols:
            out.write("_No Python symbols (or non-Python file)._\n\n")
            continue
        out.write("| Kind | Qualname | Line |\n")
        out.write("|------|----------|------|\n")
        for sym in entry.symbols:
            if sym.kind == "module":
                continue
            out.write(f"| {sym.kind} | `{sym.qualname}` | {sym.lineno} |\n")
        out.write("\n")


def _write_test_index(out, files: List[FileIndex]) -> None:
    out.write("## Index: Test suite\n\n")
    out.write("Test modules and discovered test callables / helpers.\n\n")
    for entry in files:
        out.write(f"### `{entry.path}`\n\n")
        tests = [
            s
            for s in entry.symbols
            if s.kind != "module" and (s.name.startswith("test_") or s.name.startswith("Test") or ".test_" in s.qualname)
        ]
        others = [s for s in entry.symbols if s.kind != "module" and s not in tests]
        if tests:
            out.write("**Tests / test classes**\n\n")
            out.write("| Kind | Qualname | Line |\n|------|----------|------|\n")
            for sym in tests:
                out.write(f"| {sym.kind} | `{sym.qualname}` | {sym.lineno} |\n")
            out.write("\n")
        if others:
            out.write("**Other symbols**\n\n")
            out.write("| Kind | Qualname | Line |\n|------|----------|------|\n")
            for sym in others:
                out.write(f"| {sym.kind} | `{sym.qualname}` | {sym.lineno} |\n")
            out.write("\n")
        if not tests and not others:
            out.write("_No symbols parsed._\n\n")


def _write_markdown_index(out, files: List[FileIndex]) -> None:
    out.write("## Index: Markdown documentation\n\n")
    out.write("Doc files and heading sections (`#` … `######`).\n\n")
    for entry in files:
        out.write(f"### `{entry.path}`\n\n")
        if not entry.sections:
            out.write("_No headings found._\n\n")
            continue
        out.write("| Level | Section | Line |\n|-------|---------|------|\n")
        for level, title, loc in entry.sections:
            line = loc[1:] if loc.startswith("L") else loc
            out.write(f"| H{level} | {title} | {line} |\n")
        out.write("\n")


def write_index_files(root_dir: str, report_dir: str, indexes: dict) -> dict:
    """Write standalone index markdown files (no full source dump)."""
    report = Path(report_dir)
    report.mkdir(parents=True, exist_ok=True)
    written = {}

    combined_path = report / "INDEX.md"
    with combined_path.open("w", encoding="utf-8") as out:
        out.write(f"Generated: {_generation_stamp()}\n\n")
        out.write("# PrizmForge Code Indexes\n\n")
        out.write(f"Root: `{os.path.abspath(root_dir)}`\n\n")
        out.write("Lightweight context files (no full source dump). Regenerate with `python utils/consolidate.py`.\n\n")
        out.write("## Contents\n\n")
        out.write("- [Production](#index-production-code)\n")
        out.write("- [Tests](#index-test-suite)\n")
        out.write("- [Docs](#index-markdown-documentation)\n\n")
        out.write("---\n\n")
        _write_production_index(out, indexes["production"])
        out.write("---\n\n")
        _write_test_index(out, indexes["test"])
        out.write("---\n\n")
        _write_markdown_index(out, indexes["markdown"])
    written["combined"] = str(combined_path.resolve())

    for filename, title, writer, key in (
        (
            "index_production.md",
            "Production code index",
            _write_production_index,
            "production",
        ),
        ("index_tests.md", "Test suite index", _write_test_index, "test"),
        (
            "index_docs.md",
            "Markdown documentation index",
            _write_markdown_index,
            "markdown",
        ),
    ):
        p = report / filename
        with p.open("w", encoding="utf-8") as out:
            out.write(f"Generated: {_generation_stamp()}\n\n")
            out.write(f"# {title}\n\n")
            out.write(f"Root: `{os.path.abspath(root_dir)}`\n\n")
            out.write("Standalone index for context (no full source dump).\n\n")
            writer(out, indexes[key])
        written[key] = str(p.resolve())

    return written


def generate_target_indexes(
    root_dir: str,
    out_dir: str,
    *,
    full_dump: bool = False,
) -> dict:
    """
    Build standalone indexes for a target repository (e.g. project_directory).

    Writes into out_dir (typically ``<project>/.PrizmForge/indexes``):
      INDEX.md, index_production.md, index_tests.md, index_docs.md

    If full_dump is True, also writes project_review.md (large).
    """
    root_dir = os.path.abspath(root_dir)
    out_dir = os.path.abspath(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    indexes = collect_indexes(root_dir)
    written = write_index_files(root_dir, out_dir, indexes)
    if full_dump:
        consolidate_project(
            root_dir,
            output_filename=os.path.join(out_dir, "project_review.md"),
            write_indexes=False,
        )
        written["full"] = os.path.join(out_dir, "project_review.md")
    pointer = Path(out_dir) / "README.md"
    pointer.write_text(
        "\n".join(
            [
                f"Generated: {_generation_stamp()}",
                "",
                "# Target repository indexes",
                "",
                "Generated on init for agent/human context.",
                "",
                "- `INDEX.md` — combined (prefer this for LLM context)",
                "- `index_production.md` — source modules/symbols",
                "- `index_tests.md` — tests",
                "- `index_docs.md` — markdown headings",
                "",
                "Regenerate via CLI `init`.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    written["readme"] = str(pointer)
    return written


def consolidate_project(
    root_dir: str,
    output_filename: str = "project_review.md",
    *,
    write_indexes: bool = True,
) -> None:
    valid_extensions = (".py", ".json", ".sh", ".md")
    output_basename = os.path.basename(output_filename)
    ignored_files = set(IGNORED_FILES) | {output_basename}

    out_abs = os.path.abspath(output_filename)
    report_dir = os.path.dirname(out_abs) or "."
    # Guard: refuse absolute root paths like /report (sandbox __file__ pitfall)
    if report_dir in ("/", "\\") or report_dir.rstrip("/\\") in ("", "report") and out_abs.startswith("/report"):
        report_dir = os.path.join(os.path.abspath(os.getcwd()), "report")
        out_abs = os.path.join(report_dir, os.path.basename(output_filename))
        output_filename = out_abs
    try:
        os.makedirs(report_dir, exist_ok=True)
    except PermissionError as e:
        fallback = os.path.join(os.path.abspath(os.getcwd()), "report")
        print(f"⚠️  Cannot create {report_dir!r} ({e}); using {fallback!r}")
        report_dir = fallback
        out_abs = os.path.join(report_dir, os.path.basename(output_filename))
        output_filename = out_abs
        os.makedirs(report_dir, exist_ok=True)

    indexes = collect_indexes(root_dir)

    index_paths = {}
    if write_indexes:
        index_paths = write_index_files(root_dir, report_dir, indexes)

    with open(output_filename, "w", encoding="utf-8") as outfile:
        outfile.write(f"Generated: {_generation_stamp()}\n\n")
        outfile.write(f"# Project Review: {os.path.abspath(root_dir)}\n\n")
        outfile.write("Generated by `utils/consolidate.py`. Indexes first, then full file dump.\n\n")
        if index_paths:
            outfile.write("**Standalone indexes (preferred for LLM context):**\n\n")
            outfile.write("- Combined: `report/INDEX.md`\n")
            outfile.write("- Production: `report/index_production.md`\n")
            outfile.write("- Tests: `report/index_tests.md`\n")
            outfile.write("- Docs: `report/index_docs.md`\n\n")
        outfile.write("## Table of contents\n\n")
        outfile.write("1. [Index: Production code](#index-production-code)\n")
        outfile.write("2. [Index: Test suite](#index-test-suite)\n")
        outfile.write("3. [Index: Markdown documentation](#index-markdown-documentation)\n")
        outfile.write("4. [Full file contents](#full-file-contents)\n\n")
        outfile.write("---\n\n")

        _write_production_index(outfile, indexes["production"])
        outfile.write("---\n\n")
        _write_test_index(outfile, indexes["test"])
        outfile.write("---\n\n")
        _write_markdown_index(outfile, indexes["markdown"])
        outfile.write("---\n\n")

        outfile.write("## Full file contents\n\n")

        for root, dirs, files in os.walk(root_dir):
            dirs[:] = [d for d in dirs if not _should_skip_dir(d)]
            for file in sorted(files):
                if not file.endswith(valid_extensions) or file in ignored_files:
                    continue
                file_path = os.path.join(root, file)
                relative_path = os.path.relpath(file_path, root_dir).replace("\\", "/")
                if relative_path.endswith("report/project_review.md"):
                    continue
                if relative_path.startswith("report/index_") or relative_path == "report/INDEX.md":
                    continue

                if file.endswith(".py"):
                    lang = "python"
                elif file.endswith(".json"):
                    lang = "json"
                elif file.endswith(".sh"):
                    lang = "bash"
                else:
                    lang = "markdown"

                outfile.write(f"### File: `{relative_path}`\n\n")
                outfile.write(f"```{lang}\n")
                try:
                    with open(file_path, "r", encoding="utf-8") as infile:
                        outfile.write(infile.read())
                except Exception as e:
                    outfile.write(f"[Error reading file: {e}]")
                outfile.write("\n```\n\n---\n\n")

    print(f"✅ Consolidation complete! Created: {out_abs}")
    print(
        f"   Indexes — production: {len(indexes['production'])}, "
        f"tests: {len(indexes['test'])}, markdown: {len(indexes['markdown'])}"
    )
    if index_paths:
        print("   Standalone index files:")
        for k, v in index_paths.items():
            print(f"     - {k}: {v}")


def _generation_stamp() -> str:
    """UTC timestamp line for generated index/report files."""
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def discover_project_root(start: Optional[str | None] = None) -> str:
    """
    Find PrizmForge root (directory containing config.json).

    Android Quick Edit / some hosts copy the script to a sandbox path
    (e.g. /box/script.py). In that case ``__file__/..`` is ``/`` and must
    not be used for output (PermissionError on ``/report``).

    Search order:
    1. Explicit start (if it contains config.json)
    2. Walk upward from cwd
    3. Walk upward from ``__file__`` (skipped if under known sandboxes)
    4. cwd
    """

    def _has_config(d: str) -> bool:
        return os.path.isfile(os.path.join(d, "config.json"))

    candidates = []
    if start:
        candidates.append(os.path.abspath(start))
    cwd = os.path.abspath(os.getcwd())
    candidates.append(cwd)

    script = os.path.abspath(__file__)
    script_dir = os.path.dirname(script)
    # Only trust script location if not clearly a throwaway sandbox
    if not any(script_dir == m or script_dir.startswith(m + os.sep) for m in ("/box",)):
        candidates.append(script_dir)
        candidates.append(os.path.abspath(os.path.join(script_dir, "..")))

    seen = set()
    for base in candidates:
        cur = base
        for _ in range(12):
            if cur in seen:
                break
            seen.add(cur)
            if _has_config(cur):
                return cur
            parent = os.path.dirname(cur)
            if parent == cur:
                break
            cur = parent

    # Last resort: cwd (writable on phone if user opened the project folder)
    return cwd


if __name__ == "__main__":
    import argparse

    forge_root = discover_project_root()
    report_dir = os.path.join(forge_root, "report")
    # Never write to filesystem root (e.g. /report when script lived in /box)
    if report_dir in ("/report", "\\report") or os.path.dirname(report_dir) in (
        "/",
        "\\",
    ):
        report_dir = os.path.join(os.path.abspath(os.getcwd()), "report")
        forge_root = os.path.abspath(os.getcwd())

    parser = argparse.ArgumentParser(description="Build code indexes and/or full consolidation report")
    parser.add_argument(
        "--root",
        default=None,
        help="Tree to index (default: PrizmForge root, or project_directory with --target)",
    )
    parser.add_argument(
        "--target",
        action="store_true",
        help="Use config project_directory as --root and write under <root>/.PrizmForge/indexes",
    )
    parser.add_argument(
        "--out-dir",
        default=None,
        help="Directory for index files (default: report/ or .PrizmForge/indexes)",
    )
    parser.add_argument(
        "--indexes-only",
        action="store_true",
        help="Write INDEX.md + split indexes only (no full source dump)",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Also write full project_review.md dump",
    )
    args = parser.parse_args()

    root = args.root
    if args.target or root is None and args.indexes_only:
        try:
            from core.config import get_config

            cfg = get_config()
            if args.target or root is None:
                root = root or cfg.get("project_directory") or forge_root
        except Exception:
            root = root or forge_root
    root = os.path.abspath(root or forge_root)

    if args.target:
        out_dir = args.out_dir or os.path.join(root, ".PrizmForge", "indexes")
    else:
        out_dir = args.out_dir or report_dir

    if args.indexes_only and not args.full:
        written = generate_target_indexes(root, out_dir, full_dump=False)
        print(f"✅ Indexes only → {out_dir}")
        for k, v in written.items():
            print(f"   - {k}: {v}")
    else:
        # Full consolidation to out_dir/project_review.md (indexes always written unless indexes-only false with only full)
        out_review = os.path.join(out_dir if args.target else report_dir, "project_review.md")
        if args.target:
            generate_target_indexes(root, out_dir, full_dump=bool(args.full))
        else:
            consolidate_project(root, output_filename=out_review, write_indexes=True)
