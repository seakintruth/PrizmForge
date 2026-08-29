"""Tests for the shell-based developer agent (workflow/shell_developer.py).

Covers response parsing, change→operation mapping, worktree lifecycle/change
collection against a real git repository, and the end-to-end turn through the
Reviewer gate with mocked LLM responses.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from workflow import shell_developer as sd


# =========================================================================
# Pure helpers
# =========================================================================
def test_extract_bash_command_returns_last_block():
    response = "thinking...\n```bash\necho one\n```\nmore\n```bash\necho two\n```"
    assert sd.extract_bash_command(response) == "echo two"


def test_extract_bash_command_none_when_missing():
    assert sd.extract_bash_command("no command here") is None
    assert sd.extract_bash_command("") is None


def test_extract_finish_returns_summary_without_token():
    response = f"{sd.FINISH_TOKEN}\nAdded a feature and ran tests."
    summary = sd.extract_finish(response)
    assert summary == "Added a feature and ran tests."


def test_extract_finish_absent():
    assert sd.extract_finish("still working ```bash\necho hi\n```") is None


def test_change_to_operation_mapping():
    created = sd.change_to_operation({"status": "A", "path": "new.py", "new_content": "a\nb\n"})
    assert created["type"] == "create_file"
    assert created["target_file_path"] == "new.py"
    assert created["initial_content"] == ["a", "b"]

    modified = sd.change_to_operation({"status": "M", "path": "old.py", "new_content": "x=1\n"})
    assert modified["type"] == "full_replace"
    assert modified["new_content"] == "x=1\n"

    deleted = sd.change_to_operation({"status": "D", "path": "gone.py"})
    assert deleted["type"] == "delete_file"
    assert deleted["target_file_path"] == "gone.py"

    # Skipped entries have no governed equivalent.
    assert sd.change_to_operation({"status": "S", "path": "big.bin"}) is None


# =========================================================================
# Worktree lifecycle (real git)
# =========================================================================
@pytest.fixture
def git_project(tmp_path):
    """A minimal git repository standing in for project_directory."""
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "app.py").write_text("VALUE = 1\n")
    run = subprocess.run(
        ["git", "init", "-q"],
        cwd=str(proj),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert run.returncode == 0, run.stderr
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=str(proj), capture_output=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=str(proj), capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=str(proj), capture_output=True)
    commit = subprocess.run(
        ["git", "commit", "-qm", "init"],
        cwd=str(proj),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert commit.returncode == 0, commit.stderr
    return proj


def test_worktree_create_collect_cleanup(git_project, tmp_path):
    wt = sd.ShellWorktree(git_project, parent_dir=str(tmp_path / "scratch"))
    cwd = wt.create()
    try:
        assert cwd.is_dir()

        # Simulate an agent session: modify tracked file, add a new one.
        (cwd / "app.py").write_text("VALUE = 42\n")
        (cwd / "brand_new.py").write_text("print('hi')\n")

        changes = {c["path"]: c for c in wt.collect_changes()}
        assert set(changes) == {"app.py", "brand_new.py"}
        assert changes["app.py"]["status"] == "M"
        assert changes["app.py"]["new_content"] == "VALUE = 42\n"
        assert changes["brand_new.py"]["status"] == "A"
        assert "-VALUE = 1" in changes["app.py"]["diff"]
    finally:
        wt.cleanup()

    assert not (tmp_path / "scratch").exists() or not list((tmp_path / "scratch").glob("**/wt"))


def test_worktree_requires_git_repo(tmp_path):
    plain = tmp_path / "not_a_repo"
    plain.mkdir()
    wt = sd.ShellWorktree(plain)
    with pytest.raises(RuntimeError, match="git repository"):
        wt.create()


# =========================================================================
# End-to-end turn with mocked LLM + reviewer
# =========================================================================
@pytest.fixture
def shell_env(isolated_project, monkeypatch):
    """Config isolation plus captured call_endpoint/call_agent scripts."""
    project = Path(isolated_project["project"])
    subprocess.run(["git", "init", "-q"], cwd=str(project), capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=str(project), capture_output=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=str(project), capture_output=True)
    (project / "app.py").write_text("VALUE = 1\n")
    subprocess.run(["git", "add", "-A"], cwd=str(project), capture_output=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=str(project), capture_output=True)

    state = {"llm_calls": 0, "reviewer_prompts": [], "llm_script": None}
    default_llm_script = [
        "```bash\nprintf 'VALUE = 42\\n' > app.py\n```",
        f"Done editing.\n{sd.FINISH_TOKEN}\nBumped VALUE to 42.",
    ]

    def fake_call_endpoint(messages, **kwargs):
        script = state["llm_script"] or default_llm_script
        idx = min(state["llm_calls"], len(script) - 1)
        state["llm_calls"] += 1
        return script[idx], 10

    def fake_call_agent(agent_name, prompt, task_id, *args, **kwargs):
        state["reviewer_prompts"].append((agent_name, prompt))
        return json.dumps({"decision": kwargs.pop("decision", "APPROVE"), "reason": "ok", "suggestions": []})

    monkeypatch.setattr(sd, "call_endpoint", fake_call_endpoint)
    monkeypatch.setattr("agents.base.call_agent", fake_call_agent)
    return {"project": project, "state": state}


def test_turn_success_materializes_approved_proposal(shell_env, isolated_project):
    progress = {"edit_failures": 0}
    result = sd.run_shell_developer_turn(
        task_id="T-shell-1",
        instructions="Set VALUE to 42",
        user_command="Set VALUE to 42",
        conversation_context=[],
        model_choice=None,
        progress=progress,
        decision={},
        current_turn=1,
    )

    assert result["status"] == "success", result
    assert result["proposal_ids"]
    assert progress["files_modified"] == 1
    assert progress["materialize_successes"] == 1

    agent_name, prompt = shell_env["state"]["reviewer_prompts"][0]
    assert agent_name == "reviewer"
    assert "-VALUE = 1" in prompt or "+VALUE = 42" in prompt


def test_turn_rejection_reports_rejected_status(shell_env, monkeypatch):
    def rejecting_reviewer(agent_name, prompt, task_id, *args, **kwargs):
        return json.dumps({"decision": "REJECT", "reason": "unsafe", "suggestions": ["do better"]})

    monkeypatch.setattr("agents.base.call_agent", rejecting_reviewer)

    progress = {"edit_failures": 0}
    result = sd.run_shell_developer_turn(
        task_id="T-shell-2",
        instructions="Set VALUE to 42",
        user_command="Set VALUE to 42",
        conversation_context=[],
        model_choice=None,
        progress=progress,
        decision={},
        current_turn=1,
    )

    assert result["status"] == "rejected"
    assert progress.get("files_modified", 0) == 0


# =========================================================================
# Reviewer gate fail-closed behavior (review fix #1)
# =========================================================================
def test_turn_fails_closed_when_reviewer_unavailable(shell_env, monkeypatch):
    monkeypatch.setattr("agents.base.call_agent", lambda *a, **k: None)

    progress = {"edit_failures": 0}
    result = sd.run_shell_developer_turn(
        task_id="T-shell-dead",
        instructions="Set VALUE to 42",
        user_command="Set VALUE to 42",
        conversation_context=[],
        model_choice=None,
        progress=progress,
        decision={},
        current_turn=1,
    )

    assert result["status"] == "rejected"
    assert progress.get("files_modified", 0) == 0


def test_turn_fails_closed_on_non_json_verdict(shell_env, monkeypatch):
    def sloppy_reviewer(agent_name, prompt, task_id, *args, **kwargs):
        return "Looks good to me, approving!"

    monkeypatch.setattr("agents.base.call_agent", sloppy_reviewer)

    progress = {"edit_failures": 0}
    result = sd.run_shell_developer_turn(
        task_id="T-shell-garbage",
        instructions="Set VALUE to 42",
        user_command="Set VALUE to 42",
        conversation_context=[],
        model_choice=None,
        progress=progress,
        decision={},
        current_turn=1,
    )

    assert result["status"] == "rejected"
    assert progress.get("files_modified", 0) == 0


def test_turn_fails_closed_on_invalid_decision_value(shell_env, monkeypatch):
    def odd_reviewer(agent_name, prompt, task_id, *args, **kwargs):
        return json.dumps({"decision": "MAYBE", "reason": "unclear"})

    monkeypatch.setattr("agents.base.call_agent", odd_reviewer)

    result = sd.run_shell_developer_turn(
        task_id="T-shell-maybe",
        instructions="Set VALUE to 42",
        user_command="Set VALUE to 42",
        conversation_context=[],
        model_choice=None,
        progress={"edit_failures": 0},
        decision={},
        current_turn=1,
    )
    assert result["status"] == "rejected"


# =========================================================================
# Finish/command precedence (review fix #6)
# =========================================================================
def test_finish_with_final_command_defers_then_finishes(shell_env, isolated_project):
    shell_env["state"]["llm_script"] = [
        f"Running final check.\n```bash\nprintf 'VALUE = 42\\n' > app.py\n```\n{sd.FINISH_TOKEN}\nAll done.",
        f"{sd.FINISH_TOKEN}\nBumped VALUE to 42 after final check.",
    ]

    result = sd.run_shell_developer_turn(
        task_id="T-shell-defer",
        instructions="Set VALUE to 42",
        user_command="Set VALUE to 42",
        conversation_context=[],
        model_choice=None,
        progress={"edit_failures": 0},
        decision={},
        current_turn=1,
    )

    # First reply must NOT finish: its bash command runs first (2 LLM calls total).
    assert shell_env["state"]["llm_calls"] == 2, result
    assert result["status"] == "success", result
    assert result.get("session_exit") == "Finished"


# =========================================================================
# W1 (soak recompute): early-exit sessions must still materialize WIP edits
# =========================================================================
def test_early_exit_step_limit_materializes_wip_changes(shell_env, isolated_project):
    # Every reply is a bash command and never a FINISH token → the session is
    # stopped by the step limit with edits parked in the worktree. W1: those
    # edits must still go through the reviewer gate and materialize, and the
    # real exit status ("LimitsExceeded") comes back so the loop-guard sees it.
    shell_env["state"]["llm_script"] = ["Touch app.py only.\n```bash\nprintf 'VALUE = 42\\n' > app.py\n```"]

    progress = {"edit_failures": 0}
    result = sd.run_shell_developer_turn(
        task_id="T-shell-w1",
        instructions="Set VALUE to 42",
        user_command="Set VALUE to 42",
        conversation_context=[],
        model_choice=None,
        progress=progress,
        decision={},
        current_turn=1,
    )

    assert result["status"] == "success", result
    assert result.get("session_exit") == "LimitsExceeded"
    assert progress.get("files_modified") == 1
    assert progress.get("materialize_successes") == 1


# =========================================================================
# P9 (merged residual): a mixed gate turn is an error, not a success
# =========================================================================
def test_mixed_gate_turn_reports_error_not_success(shell_env, isolated_project, monkeypatch):
    shell_env["state"]["llm_script"] = [
        "```bash\nprintf 'VALUE = 42\\n' > app.py\n```",
        "```bash\nprintf 'x = 1\\n' > new.py\n```",
        f"{sd.FINISH_TOKEN}\nBoth files written.",
    ]

    def mixed_reviewer(agent_name, prompt, task_id, *args, **kwargs):
        if "new.py" in (prompt or ""):
            return json.dumps({"decision": "REJECT", "reason": "do not add new.py", "suggestions": []})
        return json.dumps({"decision": "APPROVE", "reason": "ok", "suggestions": []})

    monkeypatch.setattr("agents.base.call_agent", mixed_reviewer)

    progress = {"edit_failures": 0}
    result = sd.run_shell_developer_turn(
        task_id="T-shell-p9",
        instructions="Write both files",
        user_command="Write both files",
        conversation_context=[],
        model_choice=None,
        progress=progress,
        decision={},
        current_turn=1,
    )

    # app.py landed (success); new.py was rejected (rejected) → MIXED.
    assert result["status"] == "error", result
    assert result.get("session_exit") == "Finished"
    assert set(result.get("gates", [])) == {"success", "rejected"}
    assert progress.get("materialize_successes") == 1


# =========================================================================
# Worktree base fidelity + collection guards (review fixes #2/#4/#5)
# =========================================================================
class _FakeCursor:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _FakeConn:
    """Minimal stand-in for get_db_connection(): read-only rows, no-op writes."""

    def __init__(self, select_rows):
        self._select_rows = select_rows

    def execute(self, _sql, params=None):
        return _FakeCursor(self._select_rows)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_worktree_syncs_governed_db_state(git_project, tmp_path, monkeypatch):
    """Uncommitted governed content must be visible in the session worktree."""
    import core.file_operations

    monkeypatch.setattr(
        core.file_operations,
        "get_file_content_from_db",
        lambda p: "VALUE = 42\n" if p == "app.py" else None,
    )
    monkeypatch.setattr(sd, "get_db_connection", lambda **kw: _FakeConn([("app.py", 0), ("gone.py", 1)]))

    wt = sd.ShellWorktree(git_project, parent_dir=str(tmp_path / "scratch"))
    try:
        cwd = wt.create()
        # HEAD holds VALUE = 1; governed DB says 42 — the overlay must win.
        assert (cwd / "app.py").read_text() == "VALUE = 42\n"
    finally:
        wt.cleanup()


def test_collect_changes_exclude_sync_drift(git_project, tmp_path, monkeypatch):
    """Pre-existing DB/HEAD drift must not be re-proposed as agent work."""
    import core.file_operations

    monkeypatch.setattr(
        core.file_operations,
        "get_file_content_from_db",
        lambda p: "VALUE = 42\n" if p == "app.py" else None,
    )
    monkeypatch.setattr(sd, "get_db_connection", lambda **kw: _FakeConn([("app.py", 0)]))

    wt = sd.ShellWorktree(git_project, parent_dir=str(tmp_path / "scratch"))
    try:
        cwd = wt.create()
        # Sync overwrote app.py (DB drift vs HEAD); agent only adds a new file.
        assert (cwd / "app.py").read_text() == "VALUE = 42\n"
        (cwd / "brand_new.py").write_text("print('hi')\n")

        changes = wt.collect_changes()
        assert [c["path"] for c in changes] == ["brand_new.py"]
        # Drifted file keeps its governed content on disk (not reverted to HEAD).
        assert (cwd / "app.py").read_text() == "VALUE = 42\n"
    finally:
        wt.cleanup()


def test_max_file_bytes_config_respected(git_project, tmp_path, capsys):
    wt = sd.ShellWorktree(git_project, parent_dir=str(tmp_path / "scratch"), max_file_bytes=10)
    try:
        cwd = wt.create()
        (cwd / "big.txt").write_text("x" * 100)
        changes = wt.collect_changes()
        assert len(changes) == 1 and changes[0]["status"] == "S"
        assert changes[0]["new_content"] == ""
        assert "oversize" in capsys.readouterr().out
    finally:
        wt.cleanup()


def test_out_of_scope_changes_warned_and_excluded(tmp_path, capsys):
    repo = tmp_path / "repo"
    sub = repo / "sub"
    sub.mkdir(parents=True)
    (sub / "app.py").write_text("A = 1\n")
    (repo / "outside.py").write_text("O = 1\n")
    for args in (
        ["git", "init", "-q"],
        ["git", "config", "user.email", "t@example.com"],
        ["git", "config", "user.name", "Tester"],
        ["git", "add", "-A"],
        ["git", "commit", "-qm", "init"],
    ):
        subprocess.run(args, cwd=str(repo), capture_output=True, timeout=30)

    wt = sd.ShellWorktree(sub, parent_dir=str(tmp_path / "scratch"))
    try:
        cwd = wt.create()
        (cwd / "app.py").write_text("A = 2\n")
        (wt.path / "outside.py").write_text("O = 2\n")

        changes = wt.collect_changes()
        assert [c["path"] for c in changes] == ["app.py"]
        out = capsys.readouterr().out
        assert "outside the project directory" in out
        assert "outside.py" in out
    finally:
        wt.cleanup()


def test_from_config_validates_on_test_failure(monkeypatch, capsys):
    monkeypatch.setattr(
        sd,
        "get_config",
        lambda: {"shell_developer": {"on_test_failure": "propose"}},
    )
    cfg = sd.ShellDeveloperConfig.from_config()
    assert cfg.on_test_failure == "discard"
    assert "invalid" in capsys.readouterr().out

    monkeypatch.setattr(
        sd,
        "get_config",
        lambda: {"shell_developer": {"on_test_failure": "propose_anyway"}},
    )
    assert sd.ShellDeveloperConfig.from_config().on_test_failure == "propose_anyway"


# =========================================================================
# Feedback addressing maps to materialized files only (review fix #3)
# =========================================================================
def test_feedback_addressed_only_for_materialized_files(shell_env, isolated_project):
    from core.db_connection import get_db_connection

    with get_db_connection() as conn:
        cur = conn.execute("""
            INSERT INTO agent_feedback (agent_name, file_path, priority, category, message, addressed)
            VALUES ('critic', 'app.py', 'HIGH', 'style', 'fix app.py', 0)
            """)
        fb_app = cur.lastrowid
        cur = conn.execute("""
            INSERT INTO agent_feedback (agent_name, file_path, priority, category, message, addressed)
            VALUES ('critic', 'other.py', 'LOW', 'style', 'fix other.py', 0)
            """)
        fb_other = cur.lastrowid

    result = sd.run_shell_developer_turn(
        task_id="T-shell-fb",
        instructions="Set VALUE to 42",
        user_command="Set VALUE to 42",
        conversation_context=[],
        model_choice=None,
        progress={"edit_failures": 0},
        # "not-a-number" simulates orchestrator hallucination; must be skipped
        # without breaking the addressing pass.
        decision={"addressing_feedback_ids": [fb_app, "not-a-number", fb_other]},
        current_turn=1,
    )
    assert result["status"] == "success", result

    with get_db_connection() as conn:
        rows = {r[0]: r[1] for r in conn.execute("SELECT id, addressed FROM agent_feedback").fetchall()}
    assert rows[fb_app] == 1
    assert rows[fb_other] == 0
