"""
Structural symbol index: AST extract → sqlite file_symbols.

Source of truth for agent path/symbol context (JSON slices).
Markdown INDEX remains an optional export view.
"""

from __future__ import annotations

import ast
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from core.db_connection import get_db_connection


@dataclass
class Symbol:
    kind: str
    name: str
    qualname: str
    lineno: int


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_python_symbols(source: str, module_path: str) -> List[Symbol]:
    """Extract top-level classes, functions, and methods from Python source."""
    symbols: List[Symbol] = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return symbols

    mod_name = module_path.replace("\\", "/").replace("/", ".")
    if mod_name.endswith(".py"):
        mod_name = mod_name[:-3]

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            q = f"{mod_name}.{node.name}"
            symbols.append(Symbol("class", node.name, q, node.lineno))
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    symbols.append(
                        Symbol("method", item.name, f"{q}.{item.name}", item.lineno)
                    )
        elif isinstance(node, ast.FunctionDef):
            symbols.append(
                Symbol("function", node.name, f"{mod_name}.{node.name}", node.lineno)
            )
        elif isinstance(node, ast.AsyncFunctionDef):
            symbols.append(
                Symbol(
                    "async_function",
                    node.name,
                    f"{mod_name}.{node.name}",
                    node.lineno,
                )
            )
    return symbols


def upsert_file_symbols(file_path: str, source: str) -> int:
    """
    Replace all symbols for file_path with those parsed from source.
    Returns number of rows written.
    """
    rel = file_path.replace("\\", "/")
    symbols = parse_python_symbols(source, rel)
    now = _utc_now()
    with get_db_connection() as conn:
        conn.execute("DELETE FROM file_symbols WHERE file_path = ?", (rel,))
        for sym in symbols:
            conn.execute(
                """
                INSERT INTO file_symbols (file_path, kind, name, qualname, lineno, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (rel, sym.kind, sym.name, sym.qualname, sym.lineno, now),
            )
        conn.commit()
    return len(symbols)


def delete_file_symbols(file_path: str) -> None:
    rel = file_path.replace("\\", "/")
    with get_db_connection() as conn:
        conn.execute("DELETE FROM file_symbols WHERE file_path = ?", (rel,))
        conn.commit()


def rebuild_project_symbols(
    project_directory: Optional[str] = None,
    *,
    max_files: Optional[int] = None,
) -> Dict[str, Any]:
    """Walk project_directory and rebuild file_symbols for text Python files."""
    from core.config import get_config
    from core.file_operations import should_ignore_file, is_text_file

    if project_directory is None:
        project_directory = get_config().get("project_directory", "./project")
    root = Path(project_directory).expanduser().resolve()
    if not root.is_dir():
        return {
            "status": "error",
            "message": f"not a directory: {root}",
            "files": 0,
            "symbols": 0,
        }

    files_n = 0
    symbols_n = 0
    errors = 0
    for dirpath, dirnames, filenames in os.walk(root):
        # skip VCS / venv / our metadata
        dirnames[:] = [
            d
            for d in dirnames
            if d
            not in {
                ".git",
                "__pycache__",
                ".venv",
                "venv",
                "node_modules",
                ".PrizmForge",
            }
            and not d.startswith(".")
        ]
        for name in filenames:
            if not name.endswith(".py"):
                continue
            full = Path(dirpath) / name
            try:
                rel = str(full.relative_to(root)).replace("\\", "/")
            except ValueError:
                continue
            if should_ignore_file(rel):
                continue
            if not is_text_file(rel):
                continue
            # skip tests path classification optional — still index tests for prioritizer
            try:
                text = full.read_text(encoding="utf-8")
            except Exception:
                errors += 1
                continue
            try:
                n = upsert_file_symbols(rel, text)
                files_n += 1
                symbols_n += n
            except Exception:
                errors += 1
            if max_files is not None and files_n >= max_files:
                break
        if max_files is not None and files_n >= max_files:
            break
    return {"status": "ok", "files": files_n, "symbols": symbols_n, "errors": errors}


def fetch_symbol_rows(
    *,
    file_paths: Optional[Sequence[str]] = None,
    kinds: Optional[Sequence[str]] = None,
    path_prefix: Optional[str] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """Query file_symbols with optional filters."""
    clauses = []
    params: List[Any] = []
    if file_paths:
        placeholders = ",".join("?" * len(file_paths))
        clauses.append(f"file_path IN ({placeholders})")
        params.extend([p.replace("\\", "/") for p in file_paths])
    if kinds:
        placeholders = ",".join("?" * len(kinds))
        clauses.append(f"kind IN ({placeholders})")
        params.extend(list(kinds))
    if path_prefix:
        clauses.append("file_path LIKE ?")
        params.append(path_prefix.replace("\\", "/").rstrip("/") + "%")
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (
        f"SELECT file_path, kind, name, qualname, lineno FROM file_symbols{where} "
        f"ORDER BY file_path, lineno LIMIT ?"
    )
    params.append(int(limit))
    try:
        with get_db_connection() as conn:
            rows = conn.execute(sql, params).fetchall()
    except Exception:
        return []
    out = []
    for r in rows:
        # sqlite Row or tuple
        if hasattr(r, "keys"):
            out.append(
                {
                    "file_path": r["file_path"],
                    "kind": r["kind"],
                    "name": r["name"],
                    "qualname": r["qualname"],
                    "lineno": r["lineno"],
                }
            )
        else:
            out.append(
                {
                    "file_path": r[0],
                    "kind": r[1],
                    "name": r[2],
                    "qualname": r[3],
                    "lineno": r[4],
                }
            )
    return out


def format_symbol_json(rows: List[Dict[str, Any]], *, max_rows: int = 80) -> str:
    """Compact JSON array for agent prompts."""
    import json

    slice_rows = rows[:max_rows]
    return json.dumps(slice_rows, ensure_ascii=False, separators=(",", ":"))


def format_symbol_context_block(
    rows: List[Dict[str, Any]],
    *,
    max_rows: int = 80,
    label: str = "Structural symbols (JSON)",
) -> str:
    if not rows:
        return ""
    body = format_symbol_json(rows, max_rows=max_rows)
    return f"**{label}:**\n```json\n{body}\n```\n"
