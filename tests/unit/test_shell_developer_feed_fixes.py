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


def test_task_is_targeted_by_decision(tmp_path):
    """Soak17 §11.1: files_needed / addressed feedback count only when the file
    exists on disk; phantom names no longer force a targeted session."""
    root = _repo(tmp_path / "repo")
    wt = sd.ShellWorktree(root, parent_dir=str(root.parent))
    wt.create()
    try:
        assert sd._task_is_targeted("Do something", {"files_needed": ["app.py"]}, wt, "workflow/__init__.py") is True
        assert sd._task_is_targeted("Do something", {"files_needed": ["app.py", "TODO.md"]}, wt, "workflow/__init__.py") is True
        assert sd._task_is_targeted("Do something", {"files_needed": ["TODO.md"]}, wt, "workflow/__init__.py") is False
        assert sd._task_is_targeted("Do something", {}) is False
    finally:
        wt.cleanup()


def test_task_is_targeted_by_feedback_id_resolves_real_file(tmp_path, temp_db):
    """addressing_feedback_ids resolve to file_path and only target an existing file."""
    from core.db_connection import get_db_connection

    root = _repo(tmp_path / "repo")
    wt = sd.ShellWorktree(root, parent_dir=str(root.parent))
    wt.create()
    try:
        with get_db_connection() as conn:
            conn.execute(
                "INSERT INTO agent_feedback (id, agent_name, file_path, priority, category, message, addressed, timestamp) "
                "VALUES (1, 'reviewer', 'app.py', 'P2', 'edit', 'fix greet', 0, 0)"
            )
            conn.execute(
                "INSERT INTO agent_feedback (id, agent_name, file_path, priority, category, message, addressed, timestamp) "
                "VALUES (2, 'reviewer', 'TODO.md', 'P2', 'edit', 'fix plan', 0, 0)"
            )
        marker = "workflow/__init__.py"
        assert sd._task_is_targeted("Do something", {"addressing_feedback_ids": [1]}, wt, marker) is True
        assert sd._task_is_targeted("Do something", {"addressing_feedback_ids": [2]}, wt, marker) is False
        assert sd._task_is_targeted("Do something", {"addressing_feedback_ids": [999]}, wt, marker) is False
    finally:
        wt.cleanup()


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


def test_no_progress_stall_skipped_for_exploratory_session(tmp_path):
    # Soak30: a "review the TODOs" exploration session read 10 files with zero
    # writes and died on no_progress_stall_limit=10 before it could decide there
    # was nothing to change. Exploratory sessions must read freely; the thinned
    # step budget is the only cap.
    root = _repo(tmp_path / "repo")
    script = [
        "```bash\nsed -n '1,3p' app.py\n```",
        "```bash\ngrep return app.py\n```",
        "```bash\nls app.py\n```",
        f"{FINISH}\nInspected; no safe change.",
    ]
    session, wt, _state = _real_session(
        root,
        script,
        step_limit=8,
        no_change_stall_limit=6,
        no_progress_stall_limit=2,
        fiability="exploratory",
    )
    try:
        result = session.run("Review app.py")
        assert result.exit_status == "Finished"
        assert "NoProgress" not in result.summary
    finally:
        wt.cleanup()


def test_no_progress_stall_still_fires_for_mutation_session(tmp_path):
    # The Soak18 discovery-loop guard stays for mutation sessions: novel
    # no-change steps accumulate and exit "NoProgress".
    root = _repo(tmp_path / "repo")
    script = [
        "```bash\nsed -n '1,3p' app.py\n```",
        "```bash\ngrep return app.py\n```",
        "```bash\nls app.py\n```",
    ]
    session, wt, _state = _real_session(
        root,
        script,
        step_limit=8,
        no_change_stall_limit=6,
        no_progress_stall_limit=2,
        fiability="targeted",
    )
    try:
        result = session.run("Review app.py")
        assert result.exit_status == "NoProgress"
    finally:
        wt.cleanup()


def test_exploratory_counts_every_third_step_toward_caps(tmp_path):
    # Exploratory sessions count every third step toward the mutate budget, so
    # step_limit=4 tolerates all 10 raw probes (ceil(10/3)=4) before
    # LimitsExceeded; a 1:1 mutation session would have died at raw step 4.
    root = _repo(tmp_path / "repo")
    script = [f"```bash\necho probe{i}\n```" for i in range(10)]
    session, wt, _state = _real_session(
        root,
        script,
        step_limit=4,
        no_change_stall_limit=0,
        no_progress_stall_limit=0,
        fiability="exploratory",
    )
    try:
        result = session.run("Review app.py")
        assert result.exit_status == "LimitsExceeded"
        assert result.mutate_calls == 10  # raw, not thinned
    finally:
        wt.cleanup()


# ---------------------------------------------------------------------------
# Symbol-index feed (Soak31): inline target symbols + worktree map file
# ---------------------------------------------------------------------------
def test_build_symbol_context_block_inlines_target_symbols(temp_db):
    from core.db_connection import get_db_connection

    with get_db_connection() as conn:
        conn.execute(
            "INSERT INTO file_symbols (file_path, kind, name, qualname, lineno, updated_at) VALUES"
            "('core/session_projection.py', 'function', '_trim', '_trim', 65, 'x'),"
            "('core/session_projection.py', 'function', '_one_line_result', '_one_line_result', 72, 'x')"
        )
    block = sd.build_symbol_context_block("core/session_projection.py")
    assert "_trim@65" in block
    assert "_one_line_result@72" in block
    assert "core/session_projection.py" in block


def test_build_symbol_context_block_points_at_map(tmp_path):
    block = sd.build_symbol_context_block("app.py", map_path=".PrizmForge/indexes/index_symbols.md")
    assert ".PrizmForge/indexes/index_symbols.md" in block
    assert "grep" in block


def test_build_symbol_context_block_tolerates_missing_db():
    assert sd.build_symbol_context_block("nope.py") == ""


def test_write_worktree_symbol_map_writes_greppable_map(tmp_path, temp_db):
    from core.db_connection import get_db_connection

    with get_db_connection() as conn:
        conn.execute("INSERT INTO file_symbols (file_path, kind, name, qualname, lineno, updated_at) VALUES('app.py', 'function', 'greet', 'greet', 2, 'x')")
    root = _repo(tmp_path / "repo")
    wt = sd.ShellWorktree(root, parent_dir=str(root.parent))
    wt.create()
    try:
        rel = sd.write_worktree_symbol_map(wt)
        assert rel == ".PrizmForge/indexes/index_symbols.md"
        text = (wt.working_dir() / rel).read_text()
        assert "path | kind | qualname | lineno" in text
        assert "app.py | function | greet | 2" in text
    finally:
        wt.cleanup()


def test_write_worktree_symbol_map_empty_db_returns_empty(tmp_path):
    root = _repo(tmp_path / "repo")
    wt = sd.ShellWorktree(root, parent_dir=str(root.parent))
    wt.create()
    try:
        assert sd.write_worktree_symbol_map(wt) == ""
    finally:
        wt.cleanup()


def test_run_injects_symbol_context_when_symbol_map_enabled(tmp_path, temp_db):
    from core.db_connection import get_db_connection

    with get_db_connection() as conn:
        conn.execute("INSERT INTO file_symbols (file_path, kind, name, qualname, lineno, updated_at) VALUES('app.py', 'function', 'greet', 'greet', 2, 'x')")
    root = _repo(tmp_path / "repo")
    session, wt, _state = _real_session(root, ["```bash\nfalse\n```"])
    try:
        result = session.run("fix the greet function in app.py")
        user = [m["content"] for m in result.messages if m.get("role") == "user"]
        joined = "\n".join(user)
        assert "greet@2" in joined
        assert ".PrizmForge/indexes/index_symbols.md" in joined
        # Regression (Soak31 review): with a known target symbol line the first
        # command must start the read at the definition line, not force line 1.
        assert "sed -n '2,+40p' app.py" in joined
        assert "sed -n '1,80p' app.py" not in joined
        map_file = wt.working_dir() / ".PrizmForge/indexes/index_symbols.md"
        assert map_file.exists()
    finally:
        wt.cleanup()


def test_run_symbol_context_keeps_head_read_when_no_symbols(tmp_path, temp_db):
    # No file_symbols rows for the target (empty DB) -> no symbol line known,
    # so the opening-read fallback stays the plain head read.
    root = _repo(tmp_path / "repo")
    session, wt, _state = _real_session(root, ["```bash\nfalse\n```"])
    try:
        result = session.run("fix the greet function in app.py")
        user = [m["content"] for m in result.messages if m.get("role") == "user"]
        joined = "\n".join(user)
        assert "sed -n '1,80p' app.py" in joined
        assert "greet@2" not in joined
    finally:
        wt.cleanup()


def test_run_skips_symbol_context_when_symbol_map_disabled(tmp_path, temp_db):
    from core.db_connection import get_db_connection

    with get_db_connection() as conn:
        conn.execute("INSERT INTO file_symbols (file_path, kind, name, qualname, lineno, updated_at) VALUES('app.py', 'function', 'greet', 'greet', 2, 'x')")
    root = _repo(tmp_path / "repo")
    session, wt, _state = _real_session(root, ["```bash\nfalse\n```"], symbol_map=False)
    try:
        result = session.run("fix the greet function in app.py")
        user = [m["content"] for m in result.messages if m.get("role") == "user"]
        joined = "\n".join(user)
        assert "greet@2" not in joined
        assert ".PrizmForge/indexes/index_symbols.md" not in joined
    finally:
        wt.cleanup()
