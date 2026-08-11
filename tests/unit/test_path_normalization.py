"""
tests/unit/test_path_normalization.py

Unit tests for path containment and materialization path normalization
against the configured project_directory (file_editing/writer.py).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def project_env(monkeypatch, tmp_path):
    """Isolated project directory + temp DB for writer tests."""
    proj = tmp_path / "PrizmForge_Experimental"
    proj.mkdir()
    (proj / "workflow").mkdir()
    (proj / "workflow" / "task_runner.py").write_text("# original\nprint('hi')\n")

    db_path = tmp_path / "test.db"
    monkeypatch.setenv("PRIZMFORGE_DB_PATH", str(db_path))

    from core.db import init_db

    init_db()

    from core import config as config_mod

    original = config_mod.get_config

    def fake_config():
        try:
            cfg = dict(original())
        except Exception:
            cfg = {}
        cfg["project_directory"] = str(proj)
        cfg["git"] = False
        cfg["git_auto_commit"] = False
        return cfg

    monkeypatch.setattr(config_mod, "get_config", fake_config)

    return {"project": proj, "db": db_path, "tmp": tmp_path}


class TestResolveContainedPath:
    def test_relative_path_resolves_inside_project(self, project_env):
        from file_editing.writer import _resolve_contained_path

        proj = project_env["project"]
        resolved = _resolve_contained_path("workflow/task_runner.py", proj)
        assert resolved == (proj / "workflow" / "task_runner.py").resolve()
        assert resolved.relative_to(proj.resolve())

    def test_absolute_path_inside_project_accepted(self, project_env):
        from file_editing.writer import _resolve_contained_path

        proj = project_env["project"]
        abs_inside = str((proj / "workflow" / "task_runner.py").resolve())
        resolved = _resolve_contained_path(abs_inside, proj)
        assert resolved == Path(abs_inside)

    def test_absolute_path_outside_project_rejected(self, project_env):
        from file_editing.writer import _resolve_contained_path

        proj = project_env["project"]
        # Simulate the production bug: absolute path pointing at the *source* repo
        outside = project_env["tmp"] / "PrizmForge" / "workflow" / "task_runner.py"
        outside.parent.mkdir(parents=True)
        outside.write_text("# wrong tree\n")

        with pytest.raises(ValueError, match="escapes project directory"):
            _resolve_contained_path(str(outside), proj)

    def test_traversal_rejected(self, project_env):
        from file_editing.writer import _resolve_contained_path

        proj = project_env["project"]
        with pytest.raises(ValueError, match="escapes"):
            _resolve_contained_path("../../etc/passwd", proj)


class TestWriteFileToDiskContainment:
    def test_writes_relative_path(self, project_env):
        from file_editing.writer import write_file_to_disk

        result = write_file_to_disk("workflow/task_runner.py", "print('updated')\n")
        assert result["status"] == "success"
        written = Path(result["file_path"])
        assert written.read_text() == "print('updated')\n"
        # Must be inside the experimental project, not the source tree
        assert "PrizmForge_Experimental" in str(written)

    def test_rejects_outside_absolute(self, project_env):
        from file_editing.writer import write_file_to_disk

        outside = project_env["tmp"] / "PrizmForge" / "workflow" / "task_runner.py"
        outside.parent.mkdir(parents=True, exist_ok=True)

        result = write_file_to_disk(str(outside), "pwned\n")
        assert result["status"] == "error"
        assert "escape" in result["message"].lower()


class TestMaterializePathNormalizationLogic:
    """
    Unit-test the exact normalization sequence used inside materialize_proposal
    without exercising the full proposal / apply pipeline.
    """

    def test_normalize_written_path_to_relative(self, project_env):
        """After write_file_to_disk, resolve + relative_to yields a clean project-relative path."""
        from file_editing.writer import _resolve_contained_path, write_file_to_disk

        proj = project_env["project"].resolve()

        res = write_file_to_disk("workflow/task_runner.py", "print('normalized')\n")
        assert res["status"] == "success"

        written_path = res["file_path"]
        resolved = _resolve_contained_path(written_path, proj)
        rel = str(resolved.relative_to(proj)).replace("\\", "/")

        assert not Path(rel).is_absolute()
        assert rel == "workflow/task_runner.py"
        assert "PrizmForge_Experimental" not in rel

    def test_outside_absolute_cannot_normalize_for_index_or_git(self, project_env):
        """
        An absolute path from the source PrizmForge tree must raise, so
        materialize_proposal will skip symbol refresh / git rather than
        operating on the wrong tree.
        """
        from file_editing.writer import _resolve_contained_path

        proj = project_env["project"].resolve()
        outside = project_env["tmp"] / "PrizmForge" / "workflow" / "task_runner.py"
        outside.parent.mkdir(parents=True, exist_ok=True)
        outside.write_text("# wrong\n")

        with pytest.raises(ValueError, match="escapes project directory"):
            _resolve_contained_path(str(outside), proj)

    def test_git_add_args_use_relative_path_and_project_cwd(self, project_env):
        """
        Simulate the git block in materialize_proposal: cwd must be project_dir
        and the pathspec must be relative.
        """
        from file_editing.writer import _resolve_contained_path, write_file_to_disk

        proj = project_env["project"].resolve()
        res = write_file_to_disk("workflow/task_runner.py", "print('git')\n")
        assert res["status"] == "success"

        resolved = _resolve_contained_path(res["file_path"], proj)
        rel = str(resolved.relative_to(proj)).replace("\\", "/")

        git_calls = []

        def fake_run(cmd, **kwargs):
            git_calls.append({"cmd": list(cmd), "cwd": kwargs.get("cwd")})
            return MagicMock(returncode=0)

        with patch("subprocess.run", side_effect=fake_run):
            import subprocess

            subprocess.run(["git", "add", "--", rel], cwd=str(proj), check=False, timeout=10)
            subprocess.run(
                ["git", "commit", "-m", "[PrizmForge] Agent edit via proposal deadbeef"],
                cwd=str(proj),
                check=False,
                timeout=10,
            )

        assert git_calls[0]["cmd"] == ["git", "add", "--", "workflow/task_runner.py"]
        assert Path(git_calls[0]["cwd"]).resolve() == proj
        assert git_calls[1]["cmd"][0:2] == ["git", "commit"]
        assert Path(git_calls[1]["cwd"]).resolve() == proj
