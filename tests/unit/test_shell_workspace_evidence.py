"""ROADMAP §2 / §8.2: fail-closed initial-workspace evidence.

A model may not FINISH_EDIT_SESSION before a closed bash evidence command has
run in the worktree and shown workflow/__init__.py. Otherwise the session
aborts with shell_workspace_validation_failed.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

from workflow import shell_developer as sd

EVIDENCE_REPLY = "```bash\npwd && git rev-parse --show-toplevel && ls -la\n```"
A1_FINISH_WITHOUT_BASH = "FINISH_EDIT_SESSION\nworkflow/__init__.py does not exist. The repository appears to be empty. Please upload the files."


class _FakeWorktree:
    def __init__(self, exit_code: int = 0, output: str = "", commands: list | None = None):
        self._exit_code = exit_code
        self._output = output
        self.commands = commands if commands is not None else []
        self.path = Path("/work/pf-shelldev-fake")

    def working_dir(self):
        return self.path

    def run_command(self, command, timeout=120):
        self.commands.append(command)
        return self._exit_code, self._output

    def run_test_command(self, command, timeout=600):
        return 0, "ok"


def _session(script: list[str], wt: _FakeWorktree | None = None, **cfg):
    session = sd.ShellDeveloperSession(
        sd.ShellDeveloperConfig(step_limit=cfg.pop("step_limit", 8), max_consecutive_format_errors=3, **cfg),
        worktree=wt or _FakeWorktree(output="/work/wt\n/work/wt\nworkflow/\nworkflow/__init__.py\n"),
        task_id="T-evidence",
    )
    state = {"i": 0}

    def fake_llm(self):
        if state["i"] >= len(script):
            return None
        text = script[state["i"]]
        state["i"] += 1
        return text

    session._llm = fake_llm.__get__(session, type(session))
    return session


def _git_repo(root: Path, with_marker: bool = True) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=str(root), capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=str(root), capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=str(root), capture_output=True, check=True)
    if with_marker:
        wf = root / "workflow"
        wf.mkdir()
        (wf / "__init__.py").write_text("# marker\n")
    (root / "README.md").write_text("seed\n")
    subprocess.run(["git", "add", "-A"], cwd=str(root), capture_output=True, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=str(root), capture_output=True, check=True)
    return root


def test_finish_before_evidence_is_rejected():
    """A-1 turn 1: finish-without-bash claiming missing workflow/__init__.py must not complete."""
    session = _session([A1_FINISH_WITHOUT_BASH, A1_FINISH_WITHOUT_BASH], step_limit=3)
    result = session.run("Inspect workflow/__init__.py")
    assert result.exit_status != "Finished"
    assert result.evidence_ok is False
    injects = [m["content"] for m in result.messages if m.get("role") == "user"]
    assert any("Do not ask the user to upload files" in c for c in injects)
    assert any("Command stdout is the repository" in c for c in injects)


def test_evidence_command_runs_and_captures_output():
    wt = _FakeWorktree(output="/work/pf-shelldev-abc\n/work/pf-shelldev-abc\ndrwxr-xr-x workflow\nworkflow/__init__.py\n")
    session = _session([EVIDENCE_REPLY, f"{sd.FINISH_TOKEN}\nno change"], wt=wt)
    result = session.run("task")
    assert result.evidence_ran is True
    assert result.evidence_ok is True
    assert result.exit_status == "Finished"
    assert wt.commands
    assert "test -f workflow/__init__.py" in wt.commands[0]
    assert result.evidence["marker_found"] is True
    assert "workflow/__init__.py" in result.evidence["output_excerpt"]
    assert result.evidence["exit_code"] == 0
    assert result.evidence["cwd"]


def test_empty_worktree_fails_workspace_validation():
    wt = _FakeWorktree(exit_code=1, output="/work/empty\n/work/empty\n")
    session = _session([EVIDENCE_REPLY], wt=wt)
    result = session.run("task")
    assert result.exit_status == "WorkspaceValidationFailed"
    assert "workflow/__init__.py" in result.summary
    assert result.evidence_ok is False


def test_validation_failure_publishes_event(monkeypatch):
    events = []
    monkeypatch.setattr(sd, "publish_event", lambda *a, **kw: events.append((a, kw)))
    wt = _FakeWorktree(exit_code=1, output="empty\n")
    session = _session([EVIDENCE_REPLY], wt=wt)
    session.run("task")
    types = [a[0] for a, _ in events]
    assert "shell_workspace_validation_failed" in types


def test_correct_worktree_exposes_marker(tmp_path):
    repo = _git_repo(tmp_path / "repo", with_marker=True)
    wt = sd.ShellWorktree(repo)
    wt.create()
    try:
        cmd = sd.evidence_command()
        code, out = wt.run_command(cmd, timeout=30)
        assert code == 0
        assert "workflow/__init__.py" in out
        assert str(wt.working_dir()) in out.splitlines()[0] or out.splitlines()[0]
        git_root = out.splitlines()[1]
        assert Path(git_root).resolve() == wt.path.resolve()
    finally:
        wt.cleanup()


def test_empty_temporary_directory_fails_real_evidence(tmp_path):
    repo = _git_repo(tmp_path / "empty", with_marker=False)
    wt = sd.ShellWorktree(repo)
    wt.create()
    try:
        code, out = wt.run_command(sd.evidence_command(), timeout=30)
        assert code != 0
        parsed = sd.parse_evidence_output(out, code, sd.WORKSPACE_MARKER_DEFAULT)
        assert parsed["marker_found"] is False
    finally:
        wt.cleanup()


def test_worktree_path_is_not_parent_repository(tmp_path):
    repo = _git_repo(tmp_path / "repo", with_marker=True)
    wt = sd.ShellWorktree(repo)
    wt.create()
    try:
        code, out = wt.run_command("pwd && git rev-parse --show-toplevel", timeout=30)
        assert code == 0
        lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
        cwd, git_root = Path(lines[0]).resolve(), Path(lines[1]).resolve()
        assert cwd != repo.resolve()
        assert git_root != repo.resolve()
        assert git_root == wt.path.resolve()
    finally:
        wt.cleanup()


def test_run_command_uses_worktree_cwd(tmp_path):
    repo = _git_repo(tmp_path / "repo", with_marker=True)
    wt = sd.ShellWorktree(repo)
    wt.create()
    try:
        cwd_used = {}

        real_run = subprocess.run

        def spy_run(*args, **kwargs):
            cwd_used["cwd"] = kwargs.get("cwd")
            return real_run(*args, **kwargs)

        with patch("workflow.shell_developer.subprocess.run", side_effect=spy_run):
            wt.run_command("pwd", timeout=15)
        assert cwd_used["cwd"] == str(wt.working_dir())
        # Windows-style path must still be passed as the worktree dir, not the parent.
        assert Path(cwd_used["cwd"]).resolve() == wt.working_dir().resolve()
    finally:
        wt.cleanup()


def test_non_evidence_bash_is_not_executed_before_evidence():
    wt = _FakeWorktree(output="/work/wt\n/work/wt\nworkflow/__init__.py\n")
    session = _session(["```bash\necho should-not-run\n```", EVIDENCE_REPLY, f"{sd.FINISH_TOKEN}\nok"], wt=wt)
    result = session.run("task")
    assert "echo should-not-run" not in wt.commands
    assert any("test -f workflow/__init__.py" in c for c in wt.commands)
    assert result.evidence_ok is True


def test_prompt_keeps_upload_and_stdout_contract():
    prompt = sd.SYSTEM_PROMPT.format(finish_token=sd.FINISH_TOKEN)
    assert "Do not ask the user to upload files" in prompt
    assert "Command stdout is the repository" in prompt
    assert sd.EVIDENCE_PROMPT_COMMAND in prompt
    inject = sd.evidence_inject_message()
    assert "Do not ask the user to upload files" in inject
    assert "test -f" not in inject  # prompt stays the shorter form; loop adds the marker test
