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

pytestmark = pytest.mark.serial


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


def test_large_file_m_change_promotes_hunk_not_full_replace(git_project, tmp_path):
    # Soak32 §19.1: a 180+ line file (over FULL_REPLACE_MAX_LINES) must never be
    # promoted as full_replace; the worktree git-diff hunk is the payload instead.
    import ast

    big = git_project / "big.py"
    orig = "def _trim(self):\n    value = self.raw\n    return value\n\n" + "".join(f"def fn{num}():\n    return {num}  # {num:04d}\n\n" for num in range(120))
    big.write_text(orig)
    subprocess.run(["git", "add", "-A"], cwd=str(git_project), capture_output=True)
    commit = subprocess.run(["git", "commit", "-qm", "add big module"], cwd=str(git_project), capture_output=True)
    assert commit.returncode == 0, commit.stderr

    wt = sd.ShellWorktree(git_project, parent_dir=str(tmp_path / "scratch"))
    cwd = wt.create()
    try:
        edited = (cwd / "big.py").read_text().replace("    value = self.raw\n", '    """Docstring for _trim."""\n    value = self.raw\n')
        (cwd / "big.py").write_text(edited)

        (changes,) = wt.collect_changes()
        assert changes["path"] == "big.py"
        assert changes["status"] == "M"

        op = sd.change_to_operation(changes)
        assert op is not None
        assert op["type"] == "apply_diff", op  # diff hunk, never full_replace
        assert "target_file_path" not in op and "new_content" not in op

        # The hunk applies cleanly back onto the base and the result parses.
        from file_editing.editing import _apply_unified_diff

        applied = _apply_unified_diff(orig.splitlines(keepends=True), (op["diff"] or "").splitlines(keepends=True))
        assert applied is not None, f"diff was: {op['diff']!r}"
        ast.parse("".join(applied))
        assert '"""Docstring for _trim."""' in "".join(applied)
    finally:
        wt.cleanup()


def test_empty_diff_large_m_is_noop_not_unsupported():
    # Soak32 §19.1: an empty normalized diff on an over-cap M has nothing to
    # promote — it is a no-op, and the caller must not treat it as unsupported.
    op = sd.change_to_operation({"status": "M", "path": "big.py", "new_content": "x\n" * 250, "diff": "   \n"})
    assert op is None


def test_bounded_keeps_short_text_untouched():
    assert sd._bounded("hello world", 100) == "hello world"


def test_bounded_cuts_on_newline_boundary_with_marker():
    # Content longer than the cap ends mid-line; _bounded must never split a
    # token and must flag the cut explicitly so a reviewer treats it as bounded
    # rather than corrupt.
    text = "line one\nline two\nline three midword\n"
    result = sd._bounded(text, 15)
    assert not result.lstrip().startswith("...")  # the cut text comes first
    assert "[TRUNCATED" in result
    # The visible prefix must end at a newline (no partially-rendered token).
    prefix = result.split("...\n[TRUNCATED")[0]
    assert prefix.endswith("\n")


def test_bounded_no_newline_inside_cut_adds_marker_without_fake_token():
    # A giant single-line token: there is no newline to cut at, so we must not
    # present a mid-token fragment as if it were the whole token.
    result = sd._bounded("x" * 1000, 20)
    assert "[TRUNCATED" in result
    # The returned prefix is a strict prefix of the input (never augmented mid-token).
    assert result.startswith("x" * 20)


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


def test_worktree_fails_loud_when_project_outside_repo(tmp_path):
    # project_directory lives outside ANY git repository: the first guard
    # (rev-parse fails) must fail loud instead of editing a tree git cannot
    # track.
    plain = tmp_path / "not_a_repo"
    plain.mkdir()
    wt = sd.ShellWorktree(plain)
    with pytest.raises(RuntimeError, match="git repository"):
        wt.create()


def test_worktree_fails_loud_when_project_gitignored(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=str(repo), capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=str(repo), capture_output=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=str(repo), capture_output=True)
    (repo / "app.py").write_text("VALUE = 1\n")
    (repo / ".gitignore").write_text("ignored_dir/\n")
    subprocess.run(["git", "add", "-A"], cwd=str(repo), capture_output=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=str(repo), capture_output=True)

    ignored = repo / "ignored_dir"
    ignored.mkdir()
    (ignored / "app.py").write_text("VALUE = 2\n")

    wt = sd.ShellWorktree(ignored)
    with pytest.raises(RuntimeError, match="git-ignored"):
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
    (project / "workflow").mkdir(exist_ok=True)
    (project / "workflow" / "__init__.py").write_text("# marker\n")
    subprocess.run(["git", "add", "-A"], cwd=str(project), capture_output=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=str(project), capture_output=True)

    state = {"llm_calls": 0, "reviewer_prompts": [], "llm_script": None}
    default_llm_script = [
        "```bash\nprintf 'VALUE = 42\\n' > app.py\n```",
        f"{sd.FINISH_TOKEN}\nBumped VALUE to 42.",
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
    # full_replace surfaces the complete proposed content (Option A) rather than
    # a unified diff, so check for the new content rather than +/- diff markers.
    assert "PROPOSED FULL CONTENT" in prompt
    assert "VALUE = 42" in prompt
    # Small files fit the cap: complete content, no truncation marker line.
    assert "[TRUNCATED: content exceeds" not in prompt


def test_soak32_turn_overcap_module_produces_hunk_proposal(shell_env, isolated_project, monkeypatch):
    # Soak32 §19.1/§19.2 end-to-end: the worktree edits a 200+ line module via
    # the ```edit primitive, FINISHes, and the turn promotes exactly ONE governed
    # proposal from the git-diff hunk (apply_diff) — NOT a full_replace and NOT a
    # second legacy developer call.
    project = Path(isolated_project["project"])
    core = project / "core"
    core.mkdir(exist_ok=True)
    target = core / "session_projection.py"
    filler = "".join(f"def _fill{num}():\n    return {num}  # {num:04d}\n\n" for num in range(100))
    target.write_text("def _trim(self):\n    value = self.raw\n    return value\n\ndef _one_line_result(self):\n    return self.result.one_line\n\n" + filler)
    subprocess.run(["git", "add", "-A"], cwd=str(project), capture_output=True)
    commit = subprocess.run(["git", "commit", "-qm", "add session_projection module"], cwd=str(project), capture_output=True)
    assert commit.returncode == 0, commit.stderr

    # Seed the governed store exactly as project indexing would, so the
    # apply_diff hunk can reconstruct base content for the reviewer/materialize.
    from file_editing.writer import initialize_file_lines

    seeded = initialize_file_lines("core/session_projection.py", target.read_text())
    assert seeded["status"] == "success", seeded

    edit_trim = (
        "```edit core/session_projection.py\n"
        "mode: replace\n"
        "OLD:\n"
        "def _trim(self):\n"
        "    value = self.raw\n"
        "NEW:\n"
        "def _trim(self):\n"
        '    """Docstring for _trim."""\n'
        "    value = self.raw\n"
        "```"
    )
    edit_one_line = (
        "```edit core/session_projection.py\n"
        "mode: replace\n"
        "OLD:\n"
        "def _one_line_result(self):\n"
        "    return self.result.one_line\n"
        "NEW:\n"
        "def _one_line_result(self):\n"
        '    """Docstring for _one_line_result."""\n'
        "    return self.result.one_line\n"
        "```"
    )
    shell_env["state"]["llm_script"] = [edit_trim, edit_one_line, f"{sd.FINISH_TOKEN}\nAdded docstrings to both defs."]

    progress = {"edit_failures": 0}
    result = sd.run_shell_developer_turn(
        task_id="T-soak32-1",
        instructions="Add docstrings to _trim and _one_line_result in core/session_projection.py",
        user_command="Add docstrings to _trim and _one_line_result in core/session_projection.py",
        conversation_context=[],
        model_choice=None,
        progress=progress,
        decision={},
        current_turn=1,
    )

    assert result["status"] == "success", result
    assert len(result["proposal_ids"]) == 1, result  # one proposal, no invalid_operation/empty_operations re-dispatch
    assert result["session_exit"] == "Finished"
    assert progress["files_modified"] == 1
    agent_name, prompt = shell_env["state"]["reviewer_prompts"][0]
    assert agent_name == "reviewer"
    # §19.3: the reviewer sees the uniform diff hunk of the worktree, not a
    # model-authored whole-file body.
    assert "PROPOSED UNIFIED DIFF" in prompt
    assert "PROPOSED FULL CONTENT" not in prompt
    assert '"""Docstring for _trim."""' in prompt
    assert '"""Docstring for _one_line_result."""' in prompt


def test_soak32_310f7ae6_fabricated_syntax_reject_does_not_block(shell_env, isolated_project, monkeypatch):
    # §19.3 regression (Soak32 `310f7ae6`): the worktree diff ast.parses, but the
    # reviewer invented a syntax failure (`text or "")`) and rejected. The gate
    # must check the PROPOSED content against ast.parse, treat the disproven
    # claim as invalid reviewer JSON, and retry once — not permanently reject a
    # compilable hunk on a fabricated syntax story.
    import json as _json

    project = Path(isolated_project["project"])
    core = project / "core"
    core.mkdir(exist_ok=True)
    target = core / "session_projection.py"
    filler = "".join(f"def _fill{num}():\n    return {num}  # {num:04d}\n\n" for num in range(100))
    target.write_text("def _trim(self):\n    value = self.raw\n    return value\n\ndef _one_line_result(self):\n    return self.result.one_line\n\n" + filler)
    subprocess.run(["git", "add", "-A"], cwd=str(project), capture_output=True)
    commit = subprocess.run(["git", "commit", "-qm", "add session_projection module"], cwd=str(project), capture_output=True)
    assert commit.returncode == 0, commit.stderr
    from file_editing.writer import initialize_file_lines

    seeded = initialize_file_lines("core/session_projection.py", target.read_text())
    assert seeded["status"] == "success", seeded

    edit_trim = (
        "```edit core/session_projection.py\n"
        "mode: replace\n"
        "OLD:\n"
        "def _trim(self):\n"
        "    value = self.raw\n"
        "NEW:\n"
        "def _trim(self):\n"
        '    """Docstring for _trim."""\n'
        "    value = self.raw\n"
        "```"
    )
    shell_env["state"]["llm_script"] = [
        edit_trim,
        f"{sd.FINISH_TOKEN}\nAdded a docstring to _trim.",
    ]

    reviewer_calls = []

    def fake_call_agent(agent_name, prompt, task_id, *args, **kwargs):
        reviewer_calls.append(agent_name)
        if agent_name != "reviewer":
            return "APPROVE"
        if len(reviewer_calls) == 1:
            return _json.dumps(
                {
                    "decision": "REJECT",
                    "reason": 'Syntax error: the file cannot be parsed — `text or "")` broken string near _trim.',
                    "suggestions": [],
                }
            )
        return _json.dumps({"decision": "APPROVE", "reason": "hunk parses cleanly", "suggestions": []})

    monkeypatch.setattr("agents.base.call_agent", fake_call_agent)

    progress = {"edit_failures": 0}
    result = sd.run_shell_developer_turn(
        task_id="T-soak32-310f7ae6",
        instructions="Add a docstring to _trim in core/session_projection.py",
        user_command="Add a docstring to _trim in core/session_projection.py",
        conversation_context=[],
        model_choice=None,
        progress=progress,
        decision={},
        current_turn=1,
    )

    # The fabricated syntax claim must NOT block materialize.
    assert result["status"] == "success", result
    assert len(result["proposal_ids"]) == 1, result
    assert progress["files_modified"] == 1
    # The gate retried the disproven claim once and approved the real hunk.
    assert sum(1 for a in reviewer_calls if a == "reviewer") == 2


def test_gate_presents_full_content_for_full_replace(shell_env):
    # A full-replace of a large file must reach the reviewer as complete proposed
    # content, never as a unified diff cut mid-token (which previously caused
    # spurious "truncated" rejections). Very large files are bounded, not corrupt:
    # the cut lands on a newline boundary and is explicitly marked.
    big_content = "".join(f"section {i}\n" + "x" * 2000 + "\n" for i in range(200))
    payload = {
        "target_file_path": "app.py",
        "operations": [{"type": "full_replace", "new_content": big_content}],
    }
    result = sd.SessionResult(exit_status="Finished", summary="rewrote app.py", messages=[])

    sd._gate_and_materialize(
        proposal_id="P-full-replace",
        payload_dict=payload,
        target_file_path="app.py",
        diff_text="(raw diff, far larger than any prompt cap)",
        result=result,
        fallback_used=False,
        task_id="T-full-replace",
        progress={},
        current_turn=1,
    )

    agent_name, prompt = shell_env["state"]["reviewer_prompts"][0]
    assert agent_name == "reviewer"
    assert "PROPOSED FULL CONTENT" in prompt
    assert "PROPOSED UNIFIED DIFF" not in prompt  # full content replaces the diff
    # The leading section is present; the cut is explicitly marked as bounded.
    assert "section 0" in prompt
    assert "[TRUNCATED: content exceeds" in prompt


def test_gate_keeps_unified_diff_for_non_full_replace(shell_env):
    # Non-full-replace ops (e.g. create_file) still surface the unified diff.
    payload = {
        "target_file_path": "new_file.py",
        "operations": [{"type": "create_file", "initial_content": ["print('hello')"], "target_file_path": "new_file.py"}],
    }
    result = sd.SessionResult(exit_status="Finished", summary="added file", messages=[])

    sd._gate_and_materialize(
        proposal_id="P-create",
        payload_dict=payload,
        target_file_path="new_file.py",
        diff_text="--- a/new_file.py\n+++ b/new_file.py\n@@ -1 +1 @@\n+print('hello')",
        result=result,
        fallback_used=False,
        task_id="T-create",
        progress={},
        current_turn=1,
    )

    agent_name, prompt = shell_env["state"]["reviewer_prompts"][0]
    assert agent_name == "reviewer"
    assert "PROPOSED UNIFIED DIFF" in prompt
    assert "PROPOSED FULL CONTENT" not in prompt


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

    # Paired command+finish is deferred, then a real finish (2 LLM calls).
    assert shell_env["state"]["llm_calls"] == 2, result
    assert result["status"] == "success", result
    assert result.get("session_exit") == "Finished"


# =========================================================================
# W1 (soak recompute): early-exit sessions must still materialize WIP edits
# =========================================================================
def test_early_exit_step_limit_materializes_wip_changes(shell_env, isolated_project, monkeypatch):
    from core.config import get_config

    cfg = get_config()
    sh = dict(cfg.get("developer", {}).get("shell_developer", {}) or {})
    sh["step_limit"] = 2
    sh["task_scope"] = "auto"
    sh["no_progress_stall_limit"] = 0
    monkeypatch.setitem(cfg.setdefault("developer", {}), "shell_developer", sh)

    shell_env["state"]["llm_script"] = [
        "Touch app.py only.\n```bash\nprintf 'VALUE = 42\\n' > app.py\n```",
    ]

    progress = {"edit_failures": 0}
    result = sd.run_shell_developer_turn(
        task_id="T-shell-w1",
        instructions="Set VALUE to 42 in app.py",  # path → targeted, not exploratory
        user_command="Set VALUE to 42 in app.py",
        conversation_context=[],
        model_choice=None,
        progress=progress,
        decision={"target_file": "app.py"},  # drop if your decision schema uses another key
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


# =========================================================================
# §15.4 operator console echo (echo_stdout)
# =========================================================================
def test_from_config_echo_stdout_parse(monkeypatch):
    def cfg_with(value):
        return {"shell_developer": {"echo_stdout": value}}

    monkeypatch.setattr(sd, "get_config", lambda: cfg_with(True))
    assert sd.ShellDeveloperConfig.from_config().echo_stdout is True
    monkeypatch.setattr(sd, "get_config", lambda: cfg_with("false"))
    assert sd.ShellDeveloperConfig.from_config().echo_stdout is False
    monkeypatch.setattr(sd, "get_config", lambda: cfg_with("on"))
    assert sd.ShellDeveloperConfig.from_config().echo_stdout is True
    monkeypatch.setattr(sd, "get_config", lambda: cfg_with(None))
    assert sd.ShellDeveloperConfig.from_config().echo_stdout is True
    monkeypatch.setattr(sd, "get_config", lambda: {})
    assert sd.ShellDeveloperConfig.from_config().echo_stdout is True


def test_from_config_no_progress_stall_limit_parse(monkeypatch):
    monkeypatch.setattr(sd, "get_config", lambda: {"shell_developer": {"no_progress_stall_limit": 23}})
    assert sd.ShellDeveloperConfig.from_config().no_progress_stall_limit == 23
    monkeypatch.setattr(sd, "get_config", lambda: {"shell_developer": {"no_progress_stall_limit": "0"}})
    assert sd.ShellDeveloperConfig.from_config().no_progress_stall_limit == 0
    monkeypatch.setattr(sd, "get_config", lambda: {"shell_developer": {"no_progress_stall_limit": None}})
    assert sd.ShellDeveloperConfig.from_config().no_progress_stall_limit == 10
    monkeypatch.setattr(sd, "get_config", lambda: {})
    assert sd.ShellDeveloperConfig.from_config().no_progress_stall_limit == 10


# =========================================================================
# Exploratory-session budget (Soak30: every-third capping + stall exemption)
# =========================================================================
def test_budget_steps_ceil_third_in_exploratory():
    cfg = sd.ShellDeveloperConfig()
    session = object.__new__(sd.ShellDeveloperSession)
    session.cfg = cfg
    cfg.fiability = "exploratory"
    assert [session._budget_steps(n) for n in (0, 1, 2, 3, 4, 6, 9, 10)] == [0, 1, 1, 1, 2, 2, 3, 4]
    cfg.fiability = "targeted"
    assert [session._budget_steps(n) for n in (1, 2, 9)] == [1, 2, 9]


def test_echo_stdout_prints_command_and_output(shell_env, capsys):
    shell_env["state"]["llm_script"] = [
        "```bash\nprintf 'PROBE=1\\n' >> app.py && echo shell-echo-marker\n```",
        f"{sd.FINISH_TOKEN}\nLooked around.",
    ]
    result = sd.run_shell_developer_turn(
        task_id="T-echo-on",
        instructions="Look around",
        user_command="Look around",
        conversation_context=[],
        model_choice=None,
        progress={"edit_failures": 0},
        decision={},
        current_turn=1,
    )
    assert result["status"] == "success", result
    out = capsys.readouterr().out
    assert "💻 [step 1] $ printf 'PROBE=1" in out
    assert "shell-echo-marker" in out
    assert "Session exit:" in out


def test_echo_stdout_disabled_keeps_console_quiet(shell_env, monkeypatch, capsys):
    shell_env["state"]["llm_script"] = [
        "```bash\nprintf 'PROBE=2\\n' >> app.py && echo shell-echo-marker\n```",
        f"{sd.FINISH_TOKEN}\nLooked around.",
    ]
    quiet = {"shell_developer": {"echo_stdout": False}}
    monkeypatch.setattr(sd, "get_config", lambda: quiet)
    result = sd.run_shell_developer_turn(
        task_id="T-echo-off",
        instructions="Look around",
        user_command="Look around",
        conversation_context=[],
        model_choice=None,
        progress={"edit_failures": 0},
        decision={},
        current_turn=1,
    )
    assert result["status"] == "success", result
    out = capsys.readouterr().out
    assert "💻" not in out
    assert "shell-echo-marker" not in out


def test_echo_console_block_truncates_long_output():
    output = "".join(f"line {i}\n" for i in range(sd.ECHO_MAX_LINES + 25))
    block = sd._echo_console_block(output)
    assert f"line {sd.ECHO_MAX_LINES - 1}" in block
    assert "line " + str(sd.ECHO_MAX_LINES) not in block
    assert f"[{25} more lines" in block
    # Empty output renders nothing (exit-code-only steps stay one-liners).
    assert sd._echo_console_block("") == ""
    assert sd._echo_console_block("\n\n") == ""


# =========================================================================
# Symbol-index feed config (Soak31)
# =========================================================================
def test_from_config_symbol_map_defaults_true_and_parses(monkeypatch):
    monkeypatch.setattr(sd, "get_config", lambda: {"shell_developer": {}})
    assert sd.ShellDeveloperConfig.from_config().symbol_map is True

    monkeypatch.setattr(sd, "get_config", lambda: {"shell_developer": {"symbol_map": False}})
    assert sd.ShellDeveloperConfig.from_config().symbol_map is False

    monkeypatch.setattr(
        sd,
        "get_config",
        lambda: {"shell_developer": {"symbol_map": "false"}},
    )
    assert sd.ShellDeveloperConfig.from_config().symbol_map is False


def test_from_config_symbol_map_tolerates_string_truthy(monkeypatch):
    for raw in ("true", "yes", "on", "1"):
        monkeypatch.setattr(sd, "get_config", lambda raw=raw: {"shell_developer": {"symbol_map": raw}})
        assert sd.ShellDeveloperConfig.from_config().symbol_map is True


# =========================================================================
# Symbol-aware opening read (Soak31 review: no forced line-1 head read)
# =========================================================================
def test_build_first_read_command_symbol_aware():
    assert sd.build_first_read_command("app.py", 65) == "sed -n '65,+40p' app.py"
    assert sd.build_first_read_command("app.py", None) == "sed -n '1,80p' app.py"
    assert sd.build_first_read_command(None, 65) == ""


def test_inspect_prompt_does_not_force_line1_when_symbol_known():
    prompt = sd.build_inspect_prompt(
        "fix greet",
        {"output_excerpt": ""},
        "app.py",
        symbol_line=65,
    )
    assert "sed -n '65,+40p' app.py" in prompt
    assert "sed -n '1,80p'" not in prompt


def test_inspect_prompt_keeps_head_read_without_symbol_line():
    prompt = sd.build_inspect_prompt(
        "fix greet",
        {"output_excerpt": ""},
        "app.py",
    )
    assert "sed -n '1,80p' app.py" in prompt


def test_chat_prompt_does_not_force_line1_when_symbol_known():
    prompt = sd.build_chat_prompt(
        "fix greet",
        {"output_excerpt": ""},
        "app.py",
        [],
        symbol_line=72,
    )
    assert "sed -n '72,+40p' app.py" in prompt
    assert "sed -n '1,80p'" not in prompt


def test_chat_prompt_keeps_head_read_without_symbol_line():
    prompt = sd.build_chat_prompt(
        "fix greet",
        {"output_excerpt": ""},
        "app.py",
        [],
    )
    assert "sed -n '1,80p' app.py" in prompt
