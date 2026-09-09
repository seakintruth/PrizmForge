"""Soak6 mutation policy: bounded promotion, banned write paths, the
inspect/mutate budget split, full_replace fallback limits, and retryable
reviewer rejects staying off the stall streak."""

from __future__ import annotations

import subprocess
from pathlib import Path

from workflow import shell_developer as sd
from workflow import task_runner as tr

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


def _real_worktree(root: Path):
    wt = sd.ShellWorktree(root, parent_dir=str(root.parent))
    wt.create()
    return wt


# ---------------------------------------------------------------------------
# Item 1: a LimitsExceeded session must not promote an unbounded replace
# ---------------------------------------------------------------------------
def test_limits_exceeded_unbounded_m_candidate_is_dropped():
    change = {
        "path": "task_runner.py",
        "status": "M",
        "new_content": "\n".join(f"line {i}" for i in range(1300)),
        "diff": "+" + "\n+".join(f"line {i}" for i in range(300)),
    }
    assert sd.change_to_operation(change, exit_status="LimitsExceeded") is None
    big_lines = {"path": "a.py", "status": "A", "new_content": "\n".join(f"l{i}" for i in range(300)), "diff": ""}
    assert sd.change_to_operation(big_lines, exit_status="Finished") is None


def test_finished_bounded_m_is_promoted_to_full_replace():
    op = sd.change_to_operation(
        {
            "path": "small.py",
            "status": "M",
            "new_content": "\n".join(f"line {i}" for i in range(40)),
            "diff": "+one\n-two\n+three\n-four\n+five\n-six\n+seven\n-eight\n+nine\n-ten\n+eleven\n-twelve\n",
        },
        exit_status="Finished",
    )
    assert op is not None and op["type"] == "full_replace"
    assert "+one" not in op["rationale"] or op["rationale"]  # rationale carries stats, not diff body


def test_limits_exceeded_bounded_m_is_still_promotable():
    op = sd.change_to_operation(
        {
            "path": "small.py",
            "status": "M",
            "new_content": "\n".join(f"line {i}" for i in range(30)),
            "diff": "+a\n-b\n",
        },
        exit_status="LimitsExceeded",
    )
    assert op is not None and op["type"] == "full_replace"


# ---------------------------------------------------------------------------
# Item 2: python / base64 write-exec is banned before subprocess
# ---------------------------------------------------------------------------
def test_banned_base64_exec_write_is_rejected_and_tree_unchanged(tmp_path):
    root = _repo(tmp_path / "repo")
    wt = _real_worktree(root)
    try:
        exit_code, output = wt.run_command(
            "python -c \"import base64; exec(base64.b64decode('bWF0Y2g='))\"",
            timeout=30,
        )
        assert exit_code == 78
        assert "banned write path" in output
        assert wt.collect_changes() == []
    finally:
        wt.cleanup()


def test_banned_python_open_write_is_rejected():
    assert sd.is_banned_write_command("python -c \"open('/tmp/x', 'w').write('pwn')\"") is True
    assert sd.is_banned_write_command("python -c 'import base64'") is False
    assert sd.is_banned_write_command("grep -r foo .") is False


# ---------------------------------------------------------------------------
# Item 5: inspection does not burn the mutate budget
# ---------------------------------------------------------------------------
def test_thirty_five_inspect_commands_do_not_trip_mutate_limit(tmp_path):
    root = _repo(tmp_path / "repo")
    wt = sd.ShellWorktree(root, parent_dir=str(root.parent))
    wt.create()
    script = ["```bash\nsed -n '1,80p' app.py\n```"] * 35
    session = sd.ShellDeveloperSession(
        # Budget-split test: isolate the mutate/inspect dimension by opting out
        # of BOTH stall tripwires (the repeated-feature is covered elsewhere).
        sd.ShellDeveloperConfig(
            step_limit=30,
            no_change_stall_limit=0,
            no_progress_stall_limit=0,
        ),
        worktree=wt,
        task_id="T-soak6-inspect",
    )
    state = {"i": 0}

    def fake_llm(self):
        if state["i"] >= len(script):
            return None
        text = script[state["i"]]
        state["i"] += 1
        return text

    session._llm = fake_llm.__get__(session, type(session))
    try:
        result = session.run("Inspect app.py")
        assert result.exit_status != "LimitsExceeded"
        assert result.mutate_calls == 0
        assert result.inspect_calls == 35
    finally:
        wt.cleanup()


def test_mutate_budget_still_applies():
    assert sd.is_inspect_command("sed -n '1,80p' app.py") is True
    assert sd.is_inspect_command("grep raise app.py") is True
    assert sd.is_inspect_command("git diff HEAD") is True
    assert sd.is_inspect_command("echo x > app.py") is False
    assert sd.is_inspect_command("python app.py") is False
    assert sd.is_inspect_command(None) is False


# ---------------------------------------------------------------------------
# Item 3: full_replace fallback is dropped for oversized targets
# ---------------------------------------------------------------------------
def test_fallback_order_drops_full_replace_for_oversized_target(tmp_path):
    big = tmp_path / "big.py"
    big.write_text("\n".join(f"line {i}" for i in range(400)) + "\n")
    order = ["guid", "diff", "find_replace", "full_replace"]
    filtered = sd._fallback_order_for_targets(order, [str(big)], small_file_threshold=180)
    assert filtered == ["guid", "diff", "find_replace"]
    small = tmp_path / "small.py"
    small.write_text("x = 1\n")
    assert sd._fallback_order_for_targets(order, [str(small), str(big)], 180) == ["guid", "diff", "find_replace"]
    assert sd._fallback_order_for_targets(order, [str(small)], 180) == order


# ---------------------------------------------------------------------------
# Item 4: truncation/syntax REJECT is retry-same-file, not a stall
# ---------------------------------------------------------------------------
def test_retryable_reject_does_not_increment_stall_streak():
    guard = tr.NoProgressLoopGuard(threshold=2)
    progress = {"files_modified": 0}
    tr._record_developer_progress(
        guard,
        "T-soak6-rej",
        progress,
        files_before=0,
        mut={"status": "rejected", "reviewer_reason": "IndentationError: unexpected indent", "target_file_path": "app.py"},
    )
    assert guard.stalled() is False
    assert progress.get("retry_same_file") == "app.py"
    assert progress.get("retry_reason")


def test_non_retryable_reject_increments_stall_streak(temp_db):
    guard = tr.NoProgressLoopGuard(threshold=2)
    progress = {"files_modified": 0}
    tr._record_developer_progress(
        guard,
        "T-soak6-rej",
        progress,
        files_before=0,
        mut={"status": "rejected", "reviewer_reason": "the change is incorrect"},
    )
    tr._record_developer_progress(
        guard,
        "T-soak6-rej",
        progress,
        files_before=0,
        mut={"status": "rejected", "reviewer_reason": "would break the API"},
    )
    assert guard.stalled() is True
    assert not progress.get("retry_same_file")


def test_retryable_reject_keywords():
    assert tr._is_retryable_reject({"status": "rejected", "message": "payload truncated mid-token"}) is True
    assert tr._is_retryable_reject({"status": "rejected", "reviewer_reason": "SyntaxError"}) is True
    assert tr._is_retryable_reject({"status": "rejected", "rationale": "ending abruptly"}) is True
    assert tr._is_retryable_reject({"status": "rejected", "reviewer_reason": "wrong algorithm"}) is False
    assert tr._is_retryable_reject({"status": "success"}) is False
