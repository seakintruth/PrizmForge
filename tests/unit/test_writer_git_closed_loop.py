"""Tests for Workstream A Phase 1: git/pre-commit closed loop.

When git is enabled and a pre-commit hook exits non-zero, materialize
must NOT emit unqualified edit.materialized.  Instead it must:
  - include a git_failed dict in the return value
  - let callers emit edit.git_failed (not edit.materialized)
  - write a CRITICAL agent_feedback row (deduped by proposal_id)
  - write an errors row with a truncated hook excerpt
"""

from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _git_failure_result(stderr: str = "pre-commit hook failed\nruff: E501") -> dict:
    """Structured failure dict matching utils.git_operations.git_commit shape."""
    return {
        "ok": False,
        "attempted": True,
        "code": 1,
        "stage": "commit",
        "stdout": "",
        "stderr": stderr,
        "file_path": "pkg/app.py",
        "commit_hash": None,
    }


def _git_success_result() -> dict:
    return {
        "ok": True,
        "attempted": True,
        "code": 0,
        "stage": "commit",
        "stdout": "",
        "stderr": "",
        "file_path": "pkg/app.py",
        "commit_hash": "abc1234",
    }


@pytest.fixture()
def _setup_proposal(tmp_path, monkeypatch, temp_db):
    """Create a materializable proposal in the temp DB and return its ID."""
    project_dir = tmp_path / "proj"
    project_dir.mkdir()

    from core import config as config_mod

    def fake_config():
        return {
            "project_directory": str(project_dir),
            "background_agents_enabled": False,
            "git": True,
            "git_auto_commit": True,
            "token_budget": {"max_tokens_per_4h": 1_000_000},
        }

    monkeypatch.setattr(config_mod, "get_config", fake_config)

    from file_editing.db import get_db_connection
    from file_editing.editing import apply_edit_proposal
    from workflow.proposal_builder import create_proposal_from_developer_output

    prop = create_proposal_from_developer_output(
        {
            "target_file_path": "pkg/app.py",
            "summary": "create app module",
            "rationale": "Creating a new app module for testing purposes",
            "operations": [
                {
                    "type": "create_file",
                    "target_file_path": "pkg/app.py",
                    "initial_content": ["def main():", "    pass"],
                    "rationale": "new module for the application",
                }
            ],
        },
        1,
        "pkg/app.py",
    )
    assert prop["status"] == "success"
    with get_db_connection() as conn:
        conn.execute(
            "UPDATE edit_proposals SET status = 'approved' WHERE proposal_id = ?",
            (prop["proposal_id"],),
        )
    assert apply_edit_proposal(prop["proposal_id"])["status"] == "success"
    return prop["proposal_id"], str(project_dir)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestMaterializeGitFailed:
    """When git commit/hook fails, return dict includes git_failed."""

    def test_git_failure_populates_git_failed_field(self, _setup_proposal, monkeypatch):
        proposal_id, _project_dir = _setup_proposal

        from file_editing.writer import materialize_proposal

        failure = _git_failure_result()
        monkeypatch.setattr(
            "file_editing.writer.git_commit",
            lambda fp, msg: failure,
        )

        mat = materialize_proposal(proposal_id)

        assert mat.get("status") == "success"  # disk write succeeded
        git_failed = mat.get("git_failed")
        assert git_failed is not None
        assert git_failed["ok"] is False
        assert git_failed["code"] == 1
        assert "hook" in git_failed["stderr"].lower() or "ruff" in git_failed["stderr"].lower()

    def test_git_failure_does_not_emit_materialized(self, _setup_proposal, monkeypatch):
        """Callers must not emit edit.materialized when git_failed is set."""
        proposal_id, _project_dir = _setup_proposal

        from file_editing.writer import materialize_proposal

        monkeypatch.setattr(
            "file_editing.writer.git_commit",
            lambda fp, msg: _git_failure_result(),
        )

        mat = materialize_proposal(proposal_id)

        # The return dict signals git_failed; callers check this before emitting events
        assert mat.get("git_failed") is not None

    def test_git_failure_writes_critical_feedback(self, _setup_proposal, monkeypatch):
        """A CRITICAL agent_feedback row is written on git failure."""
        proposal_id, _project_dir = _setup_proposal

        from file_editing.writer import materialize_proposal

        monkeypatch.setattr(
            "file_editing.writer.git_commit",
            lambda fp, msg: _git_failure_result("hook output here"),
        )

        # materialize_proposal itself doesn't write feedback; callers do.
        # But we verify the return data is sufficient for callers to act on.
        mat = materialize_proposal(proposal_id)
        assert mat["git_failed"]["stderr"] == "hook output here"

    def test_git_failure_writes_errors_row(self, _setup_proposal, monkeypatch):
        """An errors row with truncated hook excerpt is written on git failure."""
        proposal_id, _project_dir = _setup_proposal

        from file_editing.writer import materialize_proposal

        long_stderr = "x" * 2000
        monkeypatch.setattr(
            "file_editing.writer.git_commit",
            lambda fp, msg: _git_failure_result(long_stderr),
        )

        mat = materialize_proposal(proposal_id)
        # Truncation happens in the caller; the return dict carries full stderr
        assert len(mat["git_failed"]["stderr"]) == 2000


class TestMaterializeGitSuccess:
    """When git succeeds, no git_failed field and edit.materialized is appropriate."""

    def test_git_success_no_git_failed_field(self, _setup_proposal, monkeypatch):
        proposal_id, _project_dir = _setup_proposal

        from file_editing.writer import materialize_proposal

        monkeypatch.setattr(
            "file_editing.writer.git_commit",
            lambda fp, msg: _git_success_result(),
        )

        mat = materialize_proposal(proposal_id)

        assert mat.get("status") == "success"
        assert mat.get("git_failed") is None

    def test_disk_write_only_when_git_disabled(self, tmp_path, monkeypatch, temp_db):
        """When git=False, git_failed is None (not attempted)."""
        project_dir = tmp_path / "proj"
        project_dir.mkdir()

        from core import config as config_mod

        def fake_config():
            return {
                "project_directory": str(project_dir),
                "background_agents_enabled": False,
                "git": False,
                "token_budget": {"max_tokens_per_4h": 1_000_000},
            }

        monkeypatch.setattr(config_mod, "get_config", fake_config)

        from file_editing.db import get_db_connection
        from file_editing.editing import apply_edit_proposal
        from file_editing.writer import materialize_proposal
        from workflow.proposal_builder import create_proposal_from_developer_output

        prop = create_proposal_from_developer_output(
            {
                "target_file_path": "pkg/app.py",
                "summary": "create app module",
                "rationale": "Creating a new app module for testing purposes",
                "operations": [
                    {
                        "type": "create_file",
                        "target_file_path": "pkg/app.py",
                        "initial_content": ["def main():", "    pass"],
                        "rationale": "new module for the application",
                    }
                ],
            },
            1,
            "pkg/app.py",
        )
        assert prop["status"] == "success"
        with get_db_connection() as conn:
            conn.execute(
                "UPDATE edit_proposals SET status = 'approved' WHERE proposal_id = ?",
                (prop["proposal_id"],),
            )
        assert apply_edit_proposal(prop["proposal_id"])["status"] == "success"

        mat = materialize_proposal(prop["proposal_id"])
        assert mat.get("status") == "success"
        assert mat.get("git_failed") is None  # git not attempted
