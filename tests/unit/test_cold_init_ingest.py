"""ROADMAP §1: cold-soak SQLite ingest uses one writer, init pragmas, executemany."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from cli import commands as cli_commands
from core import config as core_config
from file_editing.writer import initialize_file_lines


def _project(tmp_path: Path, n: int = 3) -> Path:
    root = tmp_path / "proj"
    root.mkdir()
    for i in range(n):
        (root / f"f{i}.py").write_text(f"x = {i}\n", encoding="utf-8")
    return root


def test_initialize_file_lines_executemany_reconstructs(temp_db):
    from core.file_operations import get_file_content_from_db

    body = "a = 1\nb = 2\nc = 3\n"
    result = initialize_file_lines("init/demo.py", body)
    assert result["status"] == "success"
    assert result["line_count"] == 4  # trailing newline → extra empty line
    assert get_file_content_from_db("init/demo.py") == body


def test_cmd_init_does_not_use_file_editing_db_connection(tmp_path, monkeypatch, temp_db, capsys):
    project = _project(tmp_path)

    def boom(*_a, **_k):
        raise AssertionError("file_editing.db.get_db_connection must not be used on init")

    monkeypatch.setattr("file_editing.db.get_db_connection", boom)
    monkeypatch.setattr(
        core_config,
        "get_config",
        lambda: {"project_directory": str(project), "git": False, "background_agents_enabled": False},
    )
    monkeypatch.setattr("cli.commands.get_config", lambda: {"project_directory": str(project), "git": False})

    cli_commands.cmd_init()
    out = capsys.readouterr().out
    assert "Indexed:" in out or "index" in out.lower()


def test_cmd_init_restores_runtime_pragmas(tmp_path, monkeypatch, temp_db):
    from core.db_connection import get_db_connection

    project = _project(tmp_path, n=2)
    monkeypatch.setattr(
        "cli.commands.get_config",
        lambda: {"project_directory": str(project), "git": False},
    )
    monkeypatch.setattr(
        core_config,
        "get_config",
        lambda: {"project_directory": str(project), "git": False},
    )
    cli_commands.cmd_init()

    with get_db_connection() as conn:
        journal = str(conn.execute("PRAGMA journal_mode").fetchone()[0]).lower()
        sync = str(conn.execute("PRAGMA synchronous").fetchone()[0]).lower()
    assert journal == "delete"
    assert sync not in {"off", "0"}


def test_cmd_init_does_not_open_per_file_writers(tmp_path, monkeypatch, temp_db):
    """cmd_init must pass conn= so file_operations does not open a writer per file."""
    project = _project(tmp_path, n=4)
    monkeypatch.setattr(
        "cli.commands.get_config",
        lambda: {"project_directory": str(project), "git": False},
    )
    monkeypatch.setattr(
        core_config,
        "get_config",
        lambda: {"project_directory": str(project), "git": False},
    )

    def boom(*_a, **_k):
        raise AssertionError("per-file get_db_connection must not run during init")

    monkeypatch.setattr("core.file_operations.get_db_connection", boom)
    monkeypatch.setattr("file_editing.db.get_db_connection", boom)
    cli_commands.cmd_init()


def test_cmd_init_hash_skip_second_pass(tmp_path, monkeypatch, temp_db, capsys):
    project = _project(tmp_path, n=2)
    cfg = {"project_directory": str(project), "git": False}
    monkeypatch.setattr("cli.commands.get_config", lambda: cfg)
    monkeypatch.setattr(core_config, "get_config", lambda: cfg)
    cli_commands.cmd_init()
    capsys.readouterr()
    with patch("file_editing.writer._initialize_lines_impl") as impl:
        impl.return_value = {"status": "success", "file_id": 1, "line_count": 1}
        cli_commands.cmd_init()
        assert impl.call_count == 0
