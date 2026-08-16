"""Symbol index rebuild must stay inside configured project_directory."""

from __future__ import annotations


def test_rebuild_only_indexes_configured_project(temp_db, tmp_path, monkeypatch):
    from core import config as config_mod
    from core.db_connection import get_db_connection
    from core.symbol_index import rebuild_project_symbols

    project = tmp_path / "Experimental"
    other = tmp_path / "SourceTree"
    project.mkdir()
    other.mkdir()
    (project / "app.py").write_text("def in_project():\n    return 1\n", encoding="utf-8")
    (other / "secret.py").write_text("def outside():\n    return 2\n", encoding="utf-8")

    monkeypatch.setattr(
        config_mod,
        "get_config",
        lambda: {"project_directory": str(project), "git": False},
    )

    result = rebuild_project_symbols(str(project))
    assert result.get("status") != "error"
    assert result.get("files", 0) >= 1

    with get_db_connection() as conn:
        paths = [r[0] for r in conn.execute("SELECT DISTINCT file_path FROM file_symbols").fetchall()]
    joined = " ".join(paths).replace("\\", "/")
    assert "secret.py" not in joined
    assert any("app.py" in p.replace("\\", "/") for p in paths)


def test_upsert_symbols_for_single_file(temp_db):
    from core.db_connection import get_db_connection
    from core.symbol_index import upsert_file_symbols

    n = upsert_file_symbols("mod.py", "class Foo:\n    def bar(self):\n        pass\n")
    assert n >= 2
    with get_db_connection() as conn:
        kinds = {r[0] for r in conn.execute("SELECT kind FROM file_symbols WHERE file_path = 'mod.py'").fetchall()}
    assert "class" in kinds
    assert "method" in kinds
