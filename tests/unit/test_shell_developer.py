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

    # Deletions and skipped entries have no governed equivalent.
    assert sd.change_to_operation({"status": "D", "path": "gone.py"}) is None
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

    state = {"llm_calls": 0, "reviewer_prompts": []}
    llm_script = [
        "```bash\nprintf 'VALUE = 42\\n' > app.py\n```",
        f"Done editing.\n{sd.FINISH_TOKEN}\nBumped VALUE to 42.",
    ]

    def fake_call_endpoint(messages, **kwargs):
        idx = min(state["llm_calls"], len(llm_script) - 1)
        state["llm_calls"] += 1
        return llm_script[idx], 10

    def fake_call_agent(agent_name, prompt, task_id, *args, **kwargs):
        state["reviewer_prompts"].append((agent_name, prompt))
        return json.dumps({"decision": kwargs.pop("decision", "APPROVE"), "reason": "ok", "suggestions": []})

    monkeypatch.setattr(sd, "call_endpoint", fake_call_endpoint)
    monkeypatch.setattr(sd, "call_agent", fake_call_agent)
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

    monkeypatch.setattr(sd, "call_agent", rejecting_reviewer)

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
