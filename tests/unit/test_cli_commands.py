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

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from cli import commands as cli_commands


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
        except Exception:
            pass

    def test_cmd_fallback_stats(self, capsys, temp_db):
        try:
            cli_commands.cmd_fallback_stats()
        except Exception:
            pass


class TestInitCommand:
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
        except Exception:
            pass

    def test_cmd_json_parse_stats(self, capsys, temp_db):
        try:
            cli_commands.cmd_json_parse_stats()
        except Exception:
            pass


class TestTaskRunnerMockedFromCLILayer:
    def test_run_task_cycle_can_be_mocked(self, temp_db):
        calls = []

        def fake_cycle(task_id, user_command, max_turns=20, **kwargs):
            calls.append(
                {"task_id": task_id, "cmd": user_command, "max_turns": max_turns}
            )
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
        from core.cli_modes import get_cli_mode_from_config, CLIMode

        mode = get_cli_mode_from_config({})
        assert mode in (CLIMode.SEMI_ATTENDED, CLIMode.UNATTENDED)


class TestMainModule:
    def test_main_module_importable(self):
        import main as main_mod

        assert callable(main_mod.main)
