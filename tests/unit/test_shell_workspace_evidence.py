"""ROADMAP §10: in-process workspace evidence and Soak4 mutation-path gates."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

from workflow import shell_developer as sd

EVIDENCE_REPLY = "```bash\npwd && git rev-parse --show-toplevel && ls -la\n```"
A1_FINISH_WITHOUT_BASH = "FINISH_EDIT_SESSION\nworkflow/__init__.py does not exist. The repository appears to be empty. Please upload the files."
ENTERPRISE_REFUSAL = "As Gemini Enterprise, I operate as a conversational AI. I do not support the automated script runner protocol. Please upload files."


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
        sd.ShellDeveloperConfig(
            step_limit=cfg.pop("step_limit", 8),
            max_consecutive_format_errors=cfg.pop("max_consecutive_format_errors", 3),
            **cfg,
        ),
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
    return session, state


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


def test_in_process_evidence_runs_before_any_llm():
    wt = _FakeWorktree(output="/work/pf-shelldev-abc\n/work/pf-shelldev-abc\ndrwxr-xr-x workflow\nworkflow/__init__.py\n")
    session, state = _session([f"{sd.FINISH_TOKEN}\nno change"], wt=wt)
    result = session.run("task")
    assert result.evidence_ran is True
    assert result.evidence_ok is True
    assert result.n_model_calls >= 1
    assert state["i"] >= 1
    assert wt.commands
    assert "test -f workflow/__init__.py" in wt.commands[0]
    assert result.evidence["marker_found"] is True
    user = [m["content"] for m in result.messages if m.get("role") == "user"]
    assert any("Workspace listing (already executed, exit 0)" in c for c in user)
    assert not any("Do not ask the user to upload files" in c for c in user)
    assert not any("You have a real shell" in c for c in user)


def test_in_process_evidence_failure_does_not_call_llm():
    wt = _FakeWorktree(exit_code=1, output="/work/empty\n/work/empty\n")
    session, state = _session([EVIDENCE_REPLY, f"{sd.FINISH_TOKEN}\nok"], wt=wt)
    result = session.run("task")
    assert result.exit_status == "WorkspaceValidationFailed"
    assert result.evidence_ok is False
    assert state["i"] == 0
    assert result.n_model_calls == 0
    assert "workflow/__init__.py" in result.summary


def test_validation_failure_publishes_event(monkeypatch):
    events = []
    monkeypatch.setattr(sd, "publish_event", lambda *a, **kw: events.append((a, kw)))
    wt = _FakeWorktree(exit_code=1, output="empty\n")
    session, _ = _session([EVIDENCE_REPLY], wt=wt)
    session.run("task")
    types = [a[0] for a, _ in events]
    assert "shell_workspace_validation_failed" in types


def test_enterprise_refusal_is_format_error_without_evidence_inject():
    session, _ = _session([ENTERPRISE_REFUSAL, ENTERPRISE_REFUSAL, ENTERPRISE_REFUSAL], max_consecutive_format_errors=3)
    result = session.run("Inspect workflow/task_runner.py")
    assert result.exit_status == "RepeatedFormatError"
    assert result.evidence_ok is True
    user = [m["content"] for m in result.messages if m.get("role") == "user"]
    assert not any("```bash\npwd && git rev-parse" in c for c in user)


def test_finish_claiming_no_filesystem_after_evidence_is_rejected(monkeypatch):
    events = []
    monkeypatch.setattr(sd, "publish_event", lambda *a, **kw: events.append((a, kw)))
    session, _ = _session(
        [
            "```bash\nsed -n '1,80p' workflow/task_runner.py\n```",
            A1_FINISH_WITHOUT_BASH,
            f"{sd.FINISH_TOKEN}\nInspected target; no safe change.",
        ]
    )
    result = session.run("Inspect workflow/task_runner.py")
    assert result.exit_status == "Finished"
    types = [a[0] for a, _ in events]
    assert "shell_session_no_mutation" in types
    assert result.summary == "Inspected target; no safe change."


def test_echo_shell_access_is_not_evidence():
    assert sd.is_evidence_command('echo "I do not have shell access"') is False
    assert sd.is_evidence_command("pwd && git rev-parse --show-toplevel && ls -la") is True


def test_inspect_target_command_runs_after_in_process_evidence():
    wt = _FakeWorktree(output="/work/wt\n/work/wt\nworkflow/__init__.py\n")
    session, _ = _session(
        [
            "```bash\nsed -n '1,80p' workflow/task_runner.py\n```",
            f"{sd.FINISH_TOKEN}\nok",
        ],
        wt=wt,
    )
    result = session.run("Inspect workflow/task_runner.py")
    assert result.evidence_ok is True
    assert result.target_inspected is True
    assert any("sed -n '1,80p' workflow/task_runner.py" in c for c in wt.commands)
    assert result.exit_status == "Finished"


def test_finish_before_target_inspect_is_rejected():
    session, _ = _session([A1_FINISH_WITHOUT_BASH, f"{sd.FINISH_TOKEN}\nno change"], step_limit=3)
    result = session.run("Inspect workflow/task_runner.py")
    assert result.exit_status != "Finished"
    assert result.target_inspected is False
    assert result.evidence_ok is True


def test_system_prompt_has_no_shell_sermon():
    prompt = sd.SYSTEM_PROMPT.format(finish_token=sd.FINISH_TOKEN)
    assert "Do not ask the user to upload files" not in prompt
    assert "You have shell access" not in prompt
    assert "Command stdout is the repository" not in prompt
    assert sd.EVIDENCE_PROMPT_COMMAND not in prompt


def test_enterprise_chat_model_runs_chat_table_protocol():
    """PR #123: an Enterprise-chat developer must NOT hard-abort. It enters the
    chat-JSON-table protocol: the evidence row seeds the step table, the model
    completes the next row (command), then the finish row ends the session."""
    script = [
        '{"thought": "Inspect the target", "step": 2, "command": "sed -n \'1,80p\' workflow/task_runner.py", "finish": false}',
        '{"thought": "Verified", "step": 3, "command": null, "finish": true, "summary": "Reviewed target"}',
    ]
    session, state = _session(script, model="company/gemini-3.1-pro-preview@api.genai.mil")
    session._resolve_developer_model = lambda: "company/gemini-3.1-pro-preview@api.genai.mil"  # type: ignore[method-assign]
    result = session.run("Inspect workflow/task_runner.py")
    assert session.chat_mode is True
    assert state["i"] == 2
    assert result.exit_status == "Finished"
    assert result.n_model_calls == 2
    assert result.commands_executed == 1
    assert result.target_inspected is True
    assert len(session.steps) == 2  # evidence seed + executed command
    assert session.steps[0]["step"] == 1
    assert session.steps[1]["step"] == 2
    assert session.steps[1]["command"] == "sed -n '1,80p' workflow/task_runner.py"
    assert result.summary == "Reviewed target"


def test_resolved_enterprise_model_runs_chat_table_protocol_when_cfg_null():
    """PR #123: even with a null cfg.model, a resolved genai.mil developer uses
    the chat-JSON-table protocol instead of the historical hard abort."""
    script = [
        '{"thought": "Inspect", "step": 2, "command": "sed -n \'1,80p\' workflow/task_runner.py", "finish": false}',
        '{"thought": "Done", "step": 3, "command": null, "finish": true, "summary": "ok"}',
    ]
    session, state = _session(script)
    session._resolve_developer_model = lambda: "company/gemini-3.1-pro-preview@api.genai.mil"  # type: ignore[method-assign]
    result = session.run("Inspect workflow/task_runner.py")
    assert session.chat_mode is True
    assert state["i"] == 2
    assert result.exit_status == "Finished"
    assert result.n_model_calls == 2


def test_chat_table_mode_can_be_disabled_via_config():
    """PR #123: json_table='off' keeps the historical bash-fence protocol even
    for an Enterprise-chat developer model."""
    script = [
        "```bash\nsed -n '1,80p' workflow/task_runner.py\n```",
        f"{sd.FINISH_TOKEN}\nok",
    ]
    session, state = _session(script, model="company/gemini-3.1-pro-preview@api.genai.mil", json_table="off")
    session._resolve_developer_model = lambda: "company/gemini-3.1-pro-preview@api.genai.mil"  # type: ignore[method-assign]
    result = session.run("Inspect workflow/task_runner.py")
    assert session.chat_mode is False
    assert state["i"] == 2
    assert result.exit_status == "Finished"


def test_correct_worktree_exposes_marker(tmp_path):
    repo = _git_repo(tmp_path / "repo", with_marker=True)
    wt = sd.ShellWorktree(repo)
    wt.create()
    try:
        cmd = sd.evidence_command()
        code, out = wt.run_command(cmd, timeout=30)
        assert code == 0
        assert "workflow/__init__.py" in out
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
        assert Path(cwd_used["cwd"]).resolve() == wt.working_dir().resolve()
    finally:
        wt.cleanup()


# ---------------------------------------------------------------------------
# PR #122: seed-path tokens harvested from prose must not latch developer.
# Only a path-like surviving candidate may trigger the §10.4.2 missing-target
# abort; version/domain tokens (gemini-3.1, api.genai.mil) resolve to None and
# the session proceeds with the inspect prompt (target_path=None).
# ---------------------------------------------------------------------------
class _RealDirWorktree(_FakeWorktree):
    def __init__(self, root: Path):
        super().__init__(exit_code=0, output="/work/wt\n/work/wt\nworkflow/\nworkflow/__init__.py\n")
        self.path = root

    def working_dir(self):
        return self.path


def test_seed_path_candidate_filter_drops_version_and_domain_tokens():
    assert sd._seed_path_candidates("update gemini-3.1 for api.genai.mil v1.2") == []
    assert sd._seed_path_candidates("inspect workflow/task_runner.py") == ["workflow/task_runner.py"]
    assert sd._seed_path_candidates("fix bug in config.json") == ["config.json"]
    assert "api.genai.mil" not in sd._seed_path_candidates("see docs/config.json on api.genai.mil")


def test_path_like_seed_candidate_discriminates_targets_from_prose():
    assert sd._path_like_seed_candidate("workflow/task_runner.py") is True
    assert sd._path_like_seed_candidate("config.json") is True
    assert sd._path_like_seed_candidate("docs/README.md") is True
    assert sd._path_like_seed_candidate("api.genai.mil") is False
    assert sd._path_like_seed_candidate("gemini-3.1") is False
    assert sd._path_like_seed_candidate("../etc/passwd") is False
    assert sd._path_like_seed_candidate("/etc/hosts") is False


def test_version_token_in_seed_prose_does_not_abort(tmp_path):
    root = tmp_path / "wt"
    root.mkdir()
    session, _ = _session(
        ["```bash\necho hi\n```", f"{sd.FINISH_TOKEN}\nok"],
        wt=_RealDirWorktree(root),
    )
    result = session.run("update gemini-3.1 notes for api.genai.mil v1.2")
    assert result.exit_status != "WorkspaceValidationFailed"
    assert result.evidence_ok is True
    assert session.target_path is None


def test_missing_path_like_target_downgrades_to_exploration(tmp_path, monkeypatch):
    """Soak17 §11.1: a seed naming no existing file no longer aborts — it
    downgrades to an exploration session with a generic discovery hint and
    raises a target_missing event (no hard-coded repo names)."""
    events = []
    monkeypatch.setattr(sd, "publish_event", lambda *a, **kw: events.append((a, kw)))
    root = tmp_path / "wt"
    root.mkdir()
    session, _ = _session(
        [],
        wt=_RealDirWorktree(root),
    )
    result = session.run("Inspect workflow/task_runner.py")
    assert result.exit_status != "WorkspaceValidationFailed"
    assert session.target_path is None
    assert session.cfg.fiability == "exploratory"
    user = [m["content"] for m in result.messages if m.get("role") == "user"]
    hint = " ".join(user)
    assert "does not exist in this workspace" in hint
    assert "todo|idea|plan|roadmap|backlog" in hint
    assert "PrizmForge" not in hint
    types = [a[0] for a, _ in events]
    assert "shell_target_missing" in types
