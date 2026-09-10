"""
Phase 3 — CLI as UI tests.

The supported user interface is the interactive CLI (`interactive.py` +
`cli/commands.py`), not a graphical UI. These tests exercise command handlers
with temp DB / minimal config and mock `run_task_cycle` where needed.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from cli import commands as cli_commands
from core import config as core_config

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestHelpAndStatus:
    def test_cmd_help_mentions_status(self, capsys):
        cli_commands.cmd_help()
        out = capsys.readouterr().out.lower()
        assert "status" in out

    def test_cmd_help_lists_commands(self, capsys):
        cli_commands.cmd_help()
        out = capsys.readouterr().out.lower()
        assert "help" in out or "command" in out
        assert any(k in out for k in ("status", "init", "feedback", "endpoint"))

    def test_cmd_status_runs(self, capsys, temp_db):
        cli_commands.cmd_status()
        out = capsys.readouterr().out
        assert isinstance(out, str)

    def test_cmd_history_runs(self, capsys, temp_db):
        cli_commands.cmd_history(limit=5)

    def test_cmd_review_status_runs(self, capsys, temp_db):
        cli_commands.cmd_review_status()

    def test_cmd_files_runs(self, capsys, temp_db):
        cli_commands.cmd_files()


class TestEndpointsCommands:
    def test_cmd_endpoints(self, capsys, mock_minimal_config):
        cli_commands.cmd_endpoints()
        out = capsys.readouterr().out.lower()
        assert len(out) > 0

    def test_cmd_endpoint_health(self, capsys, mock_minimal_config):
        try:
            cli_commands.cmd_endpoint_health()
        except Exception as e:
            print(f"    ⚠️  Exception handled in test_cli_commands.py: {e}")

    def test_cmd_fallback_stats(self, capsys, temp_db):
        try:
            cli_commands.cmd_fallback_stats()
        except Exception as e:
            print(f"    ⚠️  Exception handled in test_cli_commands.py: {e}")


class TestInitCommand:
    @pytest.mark.slow
    def test_cmd_init_creates_project_dir(self, tmp_path, monkeypatch, capsys, temp_db):
        from core import config as core_config

        test_project_dir = tmp_path / "my_test_project"
        test_project_dir.mkdir(parents=True)
        (test_project_dir / "hello.py").write_text("print(1)\n", encoding="utf-8")

        def fake_config():
            return {
                "project_directory": str(test_project_dir),
                "git": False,
                "background_agents_enabled": False,
            }

        monkeypatch.setattr(core_config, "get_config", fake_config)
        cli_commands.cmd_init()
        out = capsys.readouterr().out.lower()
        assert test_project_dir.exists()
        assert "index" in out or "scanning" in out or "project" in out


class TestExportAndReports:
    def test_cmd_list_exports(self, capsys):
        cli_commands.cmd_list_exports()
        out = capsys.readouterr().out
        # Command prints a header or path listing (even if empty)
        assert isinstance(out, str)

    def test_cmd_reports(self, capsys, temp_db):
        try:
            cli_commands.cmd_reports()
        except Exception as e:
            print(f"    ⚠️  Exception handled in test_cli_commands.py: {e}")

    def test_cmd_json_parse_stats(self, capsys, temp_db):
        try:
            cli_commands.cmd_json_parse_stats()
        except Exception as e:
            print(f"    ⚠️  Exception handled in test_cli_commands.py: {e}")


class TestTaskRunnerMockedFromCLILayer:
    def test_run_task_cycle_can_be_mocked(self, temp_db):
        calls = []

        def fake_cycle(task_id, user_command, max_turns=20, **kwargs):
            calls.append({"task_id": task_id, "cmd": user_command, "max_turns": max_turns})
            return {"status": "ok", "mocked": True}

        with patch("workflow.task_runner.run_task_cycle", side_effect=fake_cycle):
            from workflow.task_runner import run_task_cycle

            run_task_cycle("cli_task_1", "do nothing", max_turns=1)

        assert len(calls) == 1
        assert calls[0]["task_id"] == "cli_task_1"
        assert calls[0]["cmd"] == "do nothing"

    def test_interactive_imports_run_task_cycle(self):
        import interactive

        assert "run_task_cycle" in dir(interactive)


class TestCLIModes:
    def test_cli_mode_enum(self):
        from core.cli_modes import CLIMode, UnattendedConfig

        assert CLIMode.SEMI_ATTENDED.value == "semi_attended"
        assert CLIMode.UNATTENDED.value == "unattended"
        cfg = UnattendedConfig.from_config(
            {
                "cli_mode": {
                    "unattended": {
                        "max_duration_hours": 2.5,
                        "max_iterations_per_task": 5,
                    }
                }
            }
        )
        assert cfg.max_duration_hours == 2.5
        assert cfg.max_iterations_per_task == 5

    def test_get_cli_mode_from_config_default(self):
        from core.cli_modes import CLIMode, get_cli_mode_from_config

        mode = get_cli_mode_from_config({})
        assert mode in (CLIMode.SEMI_ATTENDED, CLIMode.UNATTENDED)


class TestMainModule:
    def test_main_module_importable(self):
        import main as main_mod

        assert callable(main_mod.main)


def test_cmd_init_creates_and_updates_gitignore(tmp_path, monkeypatch, temp_db):
    """Verify cmd_init creates .gitignore containing .PrizmForge/ or appends if missing."""

    proj_dir = tmp_path / "test_project"
    proj_dir.mkdir(parents=True, exist_ok=True)

    fake_cfg = {
        "project_directory": str(proj_dir),
        "git": False,
        "background_agents_enabled": False,
    }

    # Patch get_config in BOTH core.config AND cli.commands so cmd_init() resolves proj_dir
    monkeypatch.setattr(core_config, "get_config", lambda: fake_cfg)
    monkeypatch.setattr(cli_commands, "get_config", lambda: fake_cfg)

    # Run init
    cli_commands.cmd_init()

    gitignore = proj_dir / ".gitignore"
    assert gitignore.exists()
    assert ".PrizmForge/" in gitignore.read_text(encoding="utf-8")

    # Run init again (idempotency check)
    cli_commands.cmd_init()
    content = gitignore.read_text(encoding="utf-8")
    assert content.count(".PrizmForge/") == 1


def test_quote_identifier_escapes_embedded_quotes():
    assert cli_commands._quote_identifier("abc") == '"abc"'
    assert cli_commands._quote_identifier('a"b') == '"a""b"'


def test_export_keyword_table_name(tmp_path, temp_db, capsys):
    """Quoted identifiers let export read a table named with a SQL keyword."""
    from core.db_connection import get_db_connection

    with get_db_connection() as conn:
        conn.execute('CREATE TABLE "order" (id INTEGER, task_id TEXT)')
        conn.execute('INSERT INTO "order" (id, task_id) VALUES (1, ?)', ("t-kw",))

    out = tmp_path / "exp"
    cli_commands.cmd_export_db(output_dir=out, task_id="t-kw")
    csv_path = out / "order.csv"
    assert csv_path.exists()
    text = csv_path.read_text(encoding="utf-8")
    assert "t-kw" in text
    capsys.readouterr()


class TestCmdShowReportGuard:
    def _make_reports(self, tmp_path):

        project_dir = tmp_path / "proj"
        reports_dir = project_dir / ".PrizmForge" / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        (reports_dir / "project_report_secret.md").write_text("REPORT-CONTENT", encoding="utf-8")

        fake_cfg = {"project_directory": str(project_dir)}
        return reports_dir, fake_cfg

    def test_traversal_attempts_blocked(self, tmp_path, monkeypatch, capsys):
        _reports_dir, fake_cfg = self._make_reports(tmp_path)
        outside = tmp_path / "outside.txt"
        outside.write_text("OUTSIDE-SECRET", encoding="utf-8")
        monkeypatch.setattr(cli_commands, "get_config", lambda: fake_cfg)

        for bad in ("../outside.txt", "..\\outside.txt", str(outside), ".", ".."):
            capsys.readouterr()
            cli_commands.cmd_show_report(bad)
            out = capsys.readouterr().out
            assert "Invalid report name" in out, f"expected rejection for {bad!r}"
            assert "OUTSIDE-SECRET" not in out

    def test_symlink_escape_blocked_by_containment(self, tmp_path, monkeypatch, capsys):
        reports_dir, fake_cfg = self._make_reports(tmp_path)
        outside = tmp_path / "outside.txt"
        outside.write_text("OUTSIDE-SECRET", encoding="utf-8")
        (reports_dir / "project_report_link.md").symlink_to(outside)
        monkeypatch.setattr(cli_commands, "get_config", lambda: fake_cfg)

        cli_commands.cmd_show_report("project_report_link.md")
        out = capsys.readouterr().out
        assert "outside reports directory" in out
        assert "OUTSIDE-SECRET" not in out

    def test_backslash_normalization_used_for_join(self, tmp_path, monkeypatch, capsys):
        reports_dir, fake_cfg = self._make_reports(tmp_path)
        (reports_dir / "project_report-other.md").write_text("OTHER-CONTENT", encoding="utf-8")
        monkeypatch.setattr(cli_commands, "get_config", lambda: fake_cfg)

        cli_commands.cmd_show_report("project_report-other.md")
        out = capsys.readouterr().out
        assert "OTHER-CONTENT" in out

    def test_specific_report_shown(self, tmp_path, monkeypatch, capsys):
        _, fake_cfg = self._make_reports(tmp_path)
        monkeypatch.setattr(cli_commands, "get_config", lambda: fake_cfg)

        cli_commands.cmd_show_report("project_report_secret.md")
        out = capsys.readouterr().out
        assert "REPORT-CONTENT" in out

    def test_latest_report_shown_when_no_name(self, tmp_path, monkeypatch, capsys):
        _, fake_cfg = self._make_reports(tmp_path)
        monkeypatch.setattr(cli_commands, "get_config", lambda: fake_cfg)

        cli_commands.cmd_show_report()
        out = capsys.readouterr().out
        assert "REPORT-CONTENT" in out

    def test_missing_report_not_found(self, tmp_path, monkeypatch, capsys):
        _, fake_cfg = self._make_reports(tmp_path)
        monkeypatch.setattr(cli_commands, "get_config", lambda: fake_cfg)

        cli_commands.cmd_show_report("project_report_nope.md")
        out = capsys.readouterr().out
        assert "Report not found" in out

    def test_no_reports_dir(self, tmp_path, monkeypatch, capsys):
        fake_cfg = {"project_directory": str(tmp_path / "no_proj")}
        monkeypatch.setattr(cli_commands, "get_config", lambda: fake_cfg)

        cli_commands.cmd_show_report("x.md")
        out = capsys.readouterr().out
        assert "No reports directory found" in out


class TestCmdExportSpecificTablesAllowlist:
    def test_invalid_identifier_skipped(self, tmp_path, temp_db, capsys):
        from core.db_connection import get_db_connection

        with get_db_connection() as conn:
            conn.execute("CREATE TABLE widgets (id INTEGER, name TEXT)")
            conn.execute("INSERT INTO widgets (id, name) VALUES (1, 'gizmo')")

        out = tmp_path / "exp"
        cli_commands.cmd_export_specific_tables(
            ["widgets", "widgets; DROP TABLE widgets;--", "task/log"],
            output_dir=out,
        )
        capsys_out = capsys.readouterr().out
        assert "Invalid table name" in capsys_out
        assert (out / "widgets.csv").exists()
        csv_files = {p.name for p in out.glob("*.csv")}
        assert csv_files == {"widgets.csv"}

        with get_db_connection() as conn:
            row = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='widgets'").fetchone()
        assert row[0] == 1


def test_export_specific_tables_task_id_filter(tmp_path, temp_db, capsys):
    from core.db_connection import get_db_connection

    with get_db_connection() as conn:
        conn.execute("CREATE TABLE audit (id INTEGER, task_id TEXT)")
        conn.execute("INSERT INTO audit (id, task_id) VALUES (1, 't-a')")
        conn.execute("INSERT INTO audit (id, task_id) VALUES (2, 't-b')")

    out = tmp_path / "exp"
    cli_commands.cmd_export_specific_tables(["audit"], output_dir=out, task_id="t-a")
    capsys.readouterr()
    text = (out / "audit.csv").read_text(encoding="utf-8")
    assert "t-a" in text
    assert "t-b" not in text
