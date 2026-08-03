"""Hybrid symbol index: sqlite file_symbols + JSON context."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def test_parse_python_symbols_basic():
    from core.symbol_index import parse_python_symbols

    src = "class A:\n    def m(self):\n        pass\n\ndef f():\n    pass\n"
    syms = parse_python_symbols(src, "pkg/mod.py")
    kinds = {s.kind for s in syms}
    assert "class" in kinds
    assert "function" in kinds
    assert "method" in kinds
    assert any(s.qualname.endswith(".A.m") for s in syms)


def test_upsert_and_fetch(temp_db):
    from core.db import init_db
    from core.symbol_index import (
        upsert_file_symbols,
        fetch_symbol_rows,
        format_symbol_json,
    )

    init_db()
    n = upsert_file_symbols("app.py", "def main():\n    return 1\n")
    assert n >= 1
    rows = fetch_symbol_rows(file_paths=["app.py"], limit=10)
    assert rows
    assert rows[0]["name"] == "main"
    blob = format_symbol_json(rows, max_rows=5)
    data = json.loads(blob)
    assert isinstance(data, list)
    assert data[0]["qualname"]


def test_upsert_replaces_stale(temp_db):
    from core.db import init_db
    from core.symbol_index import upsert_file_symbols, fetch_symbol_rows

    init_db()
    upsert_file_symbols("x.py", "def old():\n    pass\n")
    upsert_file_symbols("x.py", "def new():\n    pass\n")
    rows = fetch_symbol_rows(file_paths=["x.py"])
    names = {r["name"] for r in rows}
    assert "new" in names
    assert "old" not in names


def test_json_context_block(temp_db):
    from core.db import init_db
    from core.symbol_index import upsert_file_symbols
    from core.index_context import load_symbol_json_context, build_index_context_block

    init_db()
    upsert_file_symbols("svc.py", "class Svc:\n    def run(self):\n        pass\n")
    block = load_symbol_json_context(file_paths=["svc.py"], max_rows=20)
    assert "Svc" in block
    assert "json" in block.lower() or "[" in block
    combined = build_index_context_block(file_paths=["svc.py"], max_rows=20)
    assert "Svc" in combined
