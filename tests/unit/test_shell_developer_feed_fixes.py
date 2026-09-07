"""Soak16 feed fixes: in-worktree edit primitive, change-state observations,
stall tripwire, and the task-fiability pre-flight."""

from __future__ import annotations

import subprocess
from pathlib import Path

from workflow import shell_developer as sd

FINISH = sd.FINISH_TOKEN


def _repo(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=str(root), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=str(root), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=str(root), check=True, capture_output=True)
    wf = root / "workflow"
    wf.mkdir()
    (wf / "__init__.py").write_text("# marker\n")
    (root / "app.py").write_text("def greet():\n    return 'old'\n")
    subprocess.run(["git", "add", "-A"], cwd=str(root), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=str(root), check=True, capture_output=True)
    return root


def _real_session(root: Path, script: list[str], **cfg):
    """Build a session against a REAL disposable worktree of ``root``."""
    wt = sd.ShellWorktree(root, parent_dir=str(root.parent))
    wt.create()
    session = sd.ShellDeveloperSession(
        sd.ShellDeveloperConfig(
            step_limit=cfg.pop("step_limit", 8),
            max_consecutive_format_errors=cfg.pop("max_consecutive_format_errors", 3),
            **cfg,
        ),
        worktree=wt,
        task_id="T-feedfix",
    )
    state = {"i": 0}

    def fake_llm(self):
        if state["i"] >= len(script):
            return None
        text = script[state["i"]]
        state["i"] += 1
        return text

    session._llm = fake_llm.__get__(session, type(session))
    return session, wt, state


REPLACE_EDIT = "```edit app.py\nOLD:\n    return 'old'\nNEW:\n    return 'new'\n```"


def _app_text(wt) -> str:
    return (wt.working_dir() / "app.py").read_text()


# ---------------------------------------------------------------------------
# Edit primitive
# ---------------------------------------------------------------------------
def test_edit_block_replace_applies_edit_and_observes_state(tmp_path):
    root = _repo(tmp_path / "repo")
    session, wt, state = _real_session(
        root,
        [REPLACE_EDIT, f"{FINISH}\nFixed greet to return 'new'."],
    )
    try:
        result = session.run("Change app.py greet to return 'new'")
        assert result.exit_status == "Finished"
        assert state["i"] == 2
        assert _app_text(wt) == "def greet():\n    return 'new'\n"
        assert result.commands_executed >= 1
        user = [m["content"] for m in result.messages if m.get("role") == "user"]
        assert any("$ ```edit app.py```" in c for c in user)
        assert any("[worktree changes since baseline]" in c for c in user)
        assert any("app.py" in c and "workflow/__init__.py" not in c for c in user)
        assert any("[diff for newly changed paths (capped)]" in c for c in user)
    finally:
        wt.cleanup()


def test_edit_block_full_replace(tmp_path):
    root = _repo(tmp_path / "repo")
    full = "```edit app.py\nmode: full\nCONTENT:\ndef greet():\n    return 'full'\n```"
    session, wt, _state = _real_session(root, [full, f"{FINISH}\nwhole file replaced"])
    try:
        result = session.run("Rewrite app.py completely")
        assert result.exit_status == "Finished"
        assert _app_text(wt) == "def greet():\n    return 'full'"
    finally:
        wt.cleanup()


def test_edit_old_not_found_reports_error_then_recovers(tmp_path):
    root = _repo(tmp_path / "repo")
    wrong = "```edit app.py\nOLD:\n    return 'nope'\nNEW:\n    return 'new'\n```"
    session, wt, _state = _real_session(root, [wrong, REPLACE_EDIT, f"{FINISH}\ndone"])
    try:
        result = session.run("Change app.py greet to return 'new'")
        assert result.exit_status == "Finished"
        user = [m["content"] for m in result.messages if m.get("role") == "user"]
        assert any("edit OLD section not found in app.py" in c for c in user)
        assert _app_text(wt) == "def greet():\n    return 'new'\n"
    finally:
        wt.cleanup()


def test_edit_ambiguous_old_fails(tmp_path):
    root = _repo(tmp_path / "repo")
    (root / "app.py").write_text("x = 1\nx = 1\n")
    subprocess.run(["git", "add", "-A"], cwd=str(root), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-qm", "dup"], cwd=str(root), check=True, capture_output=True)
    ambiguous = "```edit app.py\nOLD:\nx = 1\nNEW:\nx = 2\n```"
    session, wt, _state = _real_session(root, [ambiguous])
    try:
        result = session.run("Edit app.py")
        assert result.exit_status != "Finished"
        user = [m["content"] for m in result.messages if m.get("role") == "user"]
        assert any("ambiguous in app.py" in c for c in user)
        assert "x = 1\nx = 1\n" in _app_text(wt)
    finally:
        wt.cleanup()


def test_edit_path_traversal_rejected(tmp_path):
    root = _repo(tmp_path / "repo")
    escape = "```edit ../evil.txt\nOLD:\na\nNEW:\nb\n```"
    session, wt, _state = _real_session(root, [escape])
    try:
        result = session.run("Inspect app.py")
        user = [m["content"] for m in result.messages if m.get("role") == "user"]
        assert any("edit target path is invalid" in c for c in user)
        assert not (root.parent / "evil.txt").exists()
    finally:
        wt.cleanup()


def test_chat_edit_row_applies_edit(tmp_path):
    root = _repo(tmp_path / "repo")
    chat_row = (
        '{"thought": "apply edit", "step": 2, '
        '"edit": {"path": "app.py", "mode": "replace", '
        '"old": "return \'old\'", "new": "return \'chat\'"}, "finish": false}'
    )
    script = [
        chat_row,
        '{"thought": "done", "step": 3, "command": null, "finish": true, "summary": "Edited via chat row"}',
    ]
    session, wt, _state = _real_session(root, script, model="company/gemini-3.1-pro-preview@api.genai.mil")
    session._resolve_developer_model = lambda: "company/gemini-3.1-pro-preview@api.genai.mil"  # type: ignore[method-assign]
    try:
        result = session.run("Change greet to return 'chat'")
        assert session.chat_mode is True
        assert result.exit_status == "Finished"
        assert _app_text(wt) == "def greet():\n    return 'chat'\n"
        assert len(session.steps) == 2  # evidence seed + executed edit row
        assert session.steps[1]["changed"] == ["app.py"]
        assert "diff" in session.steps[1]
    finally:
        wt.cleanup()


# ---------------------------------------------------------------------------
# Stall tripwire
# ---------------------------------------------------------------------------
def test_stall_tripwire_fires_on_repeated_failing_command(tmp_path):
    root = _repo(tmp_path / "repo")
    fail = "```bash\nfalse\n```"
    session, wt, _state = _real_session(root, [fail, fail, fail], no_change_stall_limit=2, step_limit=10)
    try:
        result = session.run("Inspect app.py")
        assert result.exit_status == "Stalled"
        assert "stalled" in result.summary.lower()
        assert result.n_model_calls <= 3
    finally:
        wt.cleanup()


def test_stall_tripwire_does_not_fire_on_unique_successful_steps(tmp_path):
    root = _repo(tmp_path / "repo")
    cmds = ["echo a", "echo b", "echo c", "echo d"]
    session, wt, _state = _real_session(
        root,
        [f"```bash\n{c}\n```" for c in cmds],
        no_change_stall_limit=6,
        step_limit=4,
    )
    try:
        result = session.run("Inspect app.py")
        assert result.exit_status == "LimitsExceeded"
        assert "stalled" not in result.summary.lower()
    finally:
        wt.cleanup()


def test_research_session_finish_does_not_stall(tmp_path):
    root = _repo(tmp_path / "repo")
    session, wt, _state = _real_session(
        root,
        ["```bash\nsed -n '1,80p' app.py\n```", f"{FINISH}\nInspected; no safe change."],
        no_change_stall_limit=2,
    )
    try:
        result = session.run("Review app.py")
        assert result.exit_status == "Finished"
        assert "stalled" not in result.summary.lower()
    finally:
        wt.cleanup()


# ---------------------------------------------------------------------------
# Change-state tallier (real worktree)
# ---------------------------------------------------------------------------
def test_change_state_since_baseline_reports_agent_change(tmp_path):
    root = _repo(tmp_path / "repo")
    wt = sd.ShellWorktree(root, parent_dir=str(root.parent))
    wt.create()
    try:
        (wt.working_dir() / "app.py").write_text("def greet():\n    return 'changed'\n")
        lines, dtext = wt.change_state_since_baseline()
        assert any(ln.startswith("M") and "app.py" in ln for ln in lines)
        assert "+    return 'changed'" in dtext
    finally:
        wt.cleanup()


# ---------------------------------------------------------------------------
# Task-fiability pre-flight
# ---------------------------------------------------------------------------
def test_task_is_targeted_by_seed_file(tmp_path):
    root = _repo(tmp_path / "repo")
    wt = sd.ShellWorktree(root, parent_dir=str(root.parent))
    wt.create()
    try:
        assert sd._task_is_targeted("Change app.py greet to return 'new'", {}, wt, "workflow/__init__.py") is True
        assert sd._task_is_targeted("Review the TODO priorities", {}, wt, "workflow/__init__.py") is False
    finally:
        wt.cleanup()


def test_task_is_targeted_by_decision():
    assert sd._task_is_targeted("Do something", {"files_needed": ["app.py"]}) is True
    assert sd._task_is_targeted("Do something", {"addressing_feedback_ids": [3]}) is True
    assert sd._task_is_targeted("Do something", {}) is False


def test_exploratory_cap_and_note(tmp_path):
    root = _repo(tmp_path / "repo")
    session, wt, _state = _real_session(
        root,
        ["```bash\nfalse\n```"],
        step_limit=30,
        no_change_stall_limit=0,
        task_scope="auto",
        explore_step_cap=3,
    )
    try:
        session.cfg.fiability = "exploratory"
        session.cfg.step_limit = 3
        result = session.run("evaluate the overall architecture")
        assert result.exit_status in ("Stalled", "LimitsExceeded", "LlmUnavailable")
        user = [m["content"] for m in result.messages if m.get("role") == "user"]
        assert any("exploration task" in c for c in user)
    finally:
        wt.cleanup()
