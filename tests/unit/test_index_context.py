"""Structural index context blocks for agents."""

from __future__ import annotations


def test_load_symbol_json_context_after_upsert(temp_db):
    from core.index_context import load_symbol_json_context
    from core.symbol_index import upsert_file_symbols

    upsert_file_symbols(
        "pkg/mod.py",
        "class Widget:\n    def render(self):\n        return 1\n\ndef helper():\n    pass\n",
    )
    block = load_symbol_json_context(file_paths=["pkg/mod.py"], max_rows=20)
    assert block
    assert "Widget" in block or "helper" in block or "symbol" in block.lower()


def test_load_index_text_missing_returns_empty(tmp_path):
    from core.index_context import load_index_text

    text = load_index_text(project_directory=str(tmp_path / "empty_proj"))
    assert text == ""


def test_load_index_text_reads_markdown(tmp_path):
    from core.index_context import load_index_text

    base = tmp_path / "proj" / ".PrizmForge" / "indexes"
    base.mkdir(parents=True)
    (base / "INDEX.md").write_text("# Project Index\n\n- app.py\n", encoding="utf-8")
    text = load_index_text(project_directory=str(tmp_path / "proj"))
    assert "app.py" in text


def test_load_index_text_named_variant(tmp_path):
    from core.index_context import load_index_text

    base = tmp_path / "proj" / ".PrizmForge" / "indexes"
    base.mkdir(parents=True)
    (base / "index_production.md").write_text("# prod symbols\n", encoding="utf-8")
    text = load_index_text(which="production", project_directory=str(tmp_path / "proj"))
    assert "prod symbols" in text


def test_load_index_text_raises_on_unknown_which(tmp_path):
    import pytest

    from core.index_context import load_index_text

    with pytest.raises(ValueError, match="Unknown index which"):
        load_index_text(which="bogus", project_directory=str(tmp_path / "proj"))
