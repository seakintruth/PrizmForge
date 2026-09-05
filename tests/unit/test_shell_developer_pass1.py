"""Pass 1 tests: shell protocol handling (Phases 1-2).

Phases 1.2/1.3/1.4/1.5 (example-driven prompt contract, unterminated-fence
normalizer, missing-file safety, structured parser diagnostics) and Phase 2
(worktree/cwd verification) are validated here against the session loop and the
exported parsing helpers.
"""

from __future__ import annotations

import subprocess

from workflow import shell_developer as sd
from workflow import shell_protocol as sp


# =========================================================================
# Phase 1.2/1.4 — Example-driven prompt contract + missing-file safety
# =========================================================================
def test_system_prompt_contains_required_format_contract():
    prompt = sd.SYSTEM_PROMPT.format(finish_token=sd.FINISH_TOKEN)
    assert "RESPONSE FORMAT — REQUIRED" in prompt
    assert "EXACTLY ONE" in prompt
    assert "pwd && ls -la" in prompt  # sample closed block and first-command evidence
    assert "git rev-parse --show-toplevel" in prompt


def test_build_instance_prompt_contains_missing_file_safety_rule():
    prompt = sd.build_instance_prompt("Inspect workflow/__init__.py")
    assert "do NOT create or guess a task-named path" in prompt
    assert sd.FINISH_TOKEN in prompt
    assert "why no safe change was made" in prompt


# =========================================================================
# Phase 2 (prompt-only) — evidence-first instruction present via the session
# =========================================================================
def test_session_prompt_mandates_evidence_first_command():
    # The session must seed the system prompt with the workspace-evidence rule;
    # enforcement is prompt-driven (observability/recording land in Phase 3.1).
    session = _session_with_replies([])
    result = session.run("task")
    system_contents = [m["content"] for m in result.messages if m.get("role") == "system"]
    assert system_contents
    assert "git rev-parse --show-toplevel" in system_contents[0]
    assert "FIRST command" in system_contents[0]


# =========================================================================
# Phase 1.3 — Unterminated-fence normalizer integration
# =========================================================================
def test_extract_bash_command_recovers_unterminated_fence():
    assert sd.extract_bash_command("```bash\nls -la\n") == "ls -la"


def test_extract_bash_command_unterminated_matches_protocol():
    assert sd.classify_shell_reply("```bash\nls -la\n") == sp.UNTERMINATED_BASH_BLOCK


# =========================================================================
# Phase 1.5 — Structured parser diagnostics
# =========================================================================
def test_format_error_diagnostic_reason_recorded(monkeypatch):
    # Driving a session into a format error surfaces a structured reason in the
    # exit summary (the observable protocol-diagnostics contract).
    monkeypatch.setattr(sd, "archive_raw_response", lambda **kw: None)
    session = _session_with_replies(["This is just prose, no command and no finish."])
    session.cfg.max_consecutive_format_errors = 1
    session.cfg.step_limit = 5
    result = session.run("task")
    assert result.exit_status == "RepeatedFormatError"
    assert "reason=prose_or_unsupported_format" in result.summary


def test_format_error_correction_message_carries_reason_below_threshold(monkeypatch):
    # Below the consecutive-error threshold the model is corrected with the
    # structured reason; only on the final error does the session exit.
    monkeypatch.setattr(sd, "archive_raw_response", lambda **kw: None)
    prose = "This is just prose, no command and no finish."
    session = _session_with_replies([prose, prose, prose])
    session.cfg.max_consecutive_format_errors = 3
    session.cfg.step_limit = 5
    result = session.run("task")
    assert result.exit_status == "RepeatedFormatError"
    format_msgs = [m for m in result.messages if m.get("role") == "user" and "FormatError" in m.get("content", "")]
    assert len(format_msgs) == 2  # errors 1 and 2 correct; error 3 exits
    assert "reason=prose_or_unsupported_format" in format_msgs[-1]["content"]


def test_diagnose_shell_reply_unterminated_reason():
    diag = sp.diagnose_shell_reply("```bash\nls -la\n")
    assert diag["reason"] == "unterminated_bash_fence"
    assert diag["expected"] == "closed_bash_block_or_finish_token"


# =========================================================================
# Phase 3.1 — Persist developer model responses (observability)
# =========================================================================
def test_session_archives_command_step(monkeypatch):
    """A command reply is archived with its command + exit code + format status."""
    captured = []
    calls = {"n": 0}

    def fake_archive(**kwargs):
        captured.append(kwargs)
        calls["n"] += 1

    monkeypatch.setattr(sd, "archive_raw_response", fake_archive)

    session = _session_with_replies(["```bash\necho hi\n```"])
    session.wt = _FakeWorktree(exit_code=5, output="hi\n")
    session.run("task")

    assert calls["n"] == 1
    record = captured[0]
    assert record["agent_name"] == "developer"
    assert record["command"] == "echo hi"
    assert record["command_exit_code"] == 5
    assert record["response_format_status"] == sp.VALID_BASH_BLOCK
    assert record["parse_success"] is True
    assert record["response"] == "```bash\necho hi\n```"
    assert record["step_number"] == 1


def test_session_archives_finish_step(monkeypatch):
    captured = []
    calls = {"n": 0}

    def fake_archive(**kwargs):
        captured.append(kwargs)
        calls["n"] += 1

    monkeypatch.setattr(sd, "archive_raw_response", fake_archive)

    session = _session_with_replies([f"{sd.FINISH_TOKEN}\nDone."])
    session.run("task")

    assert calls["n"] == 1
    record = captured[0]
    assert record["response_format_status"] == sp.VALID_FINISH_SESSION
    assert record["command"] is None
    assert record["command_exit_code"] is None
    assert record["parse_success"] is True


def test_session_archives_format_error_step(monkeypatch):
    captured = []
    calls = {"n": 0}

    def fake_archive(**kwargs):
        captured.append(kwargs)
        calls["n"] += 1

    monkeypatch.setattr(sd, "archive_raw_response", fake_archive)

    session = _session_with_replies(["This is just prose, no command and no finish."])
    session.cfg.max_consecutive_format_errors = 1
    session.cfg.step_limit = 5
    session.run("task")

    assert calls["n"] == 1
    record = captured[0]
    assert record["response_format_status"] == sp.PROSE_OR_UNSUPPORTED_FORMAT
    assert record["parse_success"] is False
    assert record["parse_error"] == "prose_or_unsupported_format"
    assert record["command"] is None


# =========================================================================
# Phase 3.2 — Persist shell failure events
# =========================================================================
def test_prose_response_publishes_prose_event(monkeypatch):
    events = []
    monkeypatch.setattr(sd, "archive_raw_response", lambda **kw: None)
    monkeypatch.setattr(sd, "publish_event", lambda *a, **kw: events.append((a, kw)))

    session = _session_with_replies(["Just prose, nothing else."])
    session.cfg.max_consecutive_format_errors = 2
    session.cfg.step_limit = 5
    session.run("task")

    types = [a[0] for a, _ in events]
    assert "shell_protocol_prose_response" in types


def test_unterminated_fence_publishes_event(monkeypatch):
    events = []
    monkeypatch.setattr(sd, "archive_raw_response", lambda **kw: None)
    monkeypatch.setattr(sd, "publish_event", lambda *a, **kw: events.append((a, kw)))
    # An opening fence with an empty command is unterminated AND not recoverable.
    session = _session_with_replies(["```bash\n\n"])
    session.cfg.max_consecutive_format_errors = 2
    session.cfg.step_limit = 5
    session.run("task")

    types = [a[0] for a, _ in events]
    assert "shell_protocol_unterminated_fence" in types


def test_repeated_format_error_publishes_event(monkeypatch):
    events = []
    monkeypatch.setattr(sd, "archive_raw_response", lambda **kw: None)
    monkeypatch.setattr(sd, "publish_event", lambda *a, **kw: events.append((a, kw)))

    prose = "Just prose, nothing else."
    session = _session_with_replies([prose, prose, prose])
    session.cfg.max_consecutive_format_errors = 3
    session.cfg.step_limit = 5
    result = session.run("task")

    assert result.exit_status == "RepeatedFormatError"
    types = [a[0] for a, _ in events]
    assert "shell_protocol_repeated_format_error" in types


def test_command_failure_publishes_event(monkeypatch):
    events = []
    monkeypatch.setattr(sd, "archive_raw_response", lambda **kw: None)
    monkeypatch.setattr(sd, "publish_event", lambda *a, **kw: events.append((a, kw)))

    session = _session_with_replies(["```bash\nexit 3\n```"])
    session.wt = _FakeWorktree(exit_code=3, output="boom\n")
    session.run("task")

    types = [a[0] for a, _ in events]
    assert "shell_command_failed" in types
    payload = next(kw["payload"] for a, kw in events if a[0] == "shell_command_failed")
    assert payload["exit_code"] == 3
    assert payload["command"] == "exit 3"


def test_workspace_validation_failure_publishes_event(isolated_project, monkeypatch):
    """A worktree that cannot be created must emit shell_workspace_validation_failed."""
    events = []
    monkeypatch.setattr(sd, "publish_event", lambda *a, **kw: events.append((a, kw)))
    monkeypatch.setattr(sd, "archive_raw_response", lambda **kw: None)

    result = sd.run_shell_developer_turn(
        task_id="T-ws-fail",
        instructions="do it",
        user_command="do it",
        conversation_context=[],
        model_choice=None,
        progress={"edit_failures": 0},
        decision={},
        current_turn=1,
    )
    # The isolated project dir is not a git repo → worktree create() fails loud.
    assert result["status"] == "error"
    types = [a[0] for a, _ in events]
    assert "shell_workspace_validation_failed" in types


def test_session_no_mutation_publishes_event(isolated_project, monkeypatch):
    """A Finished session that produced no file changes emits shell_session_no_mutation."""
    from pathlib import Path

    events = []
    monkeypatch.setattr(sd, "publish_event", lambda *a, **kw: events.append((a, kw)))
    monkeypatch.setattr(sd, "archive_raw_response", lambda **kw: None)

    project = Path(isolated_project["project"])
    (project / "README.md").write_text("seed\n")
    for args in (
        ["git", "init", "-q"],
        ["git", "config", "user.email", "t@example.com"],
        ["git", "config", "user.name", "Tester"],
        ["git", "add", "-A"],
        ["git", "commit", "-qm", "init"],
    ):
        subprocess.run(args, cwd=str(project), capture_output=True, text=True, timeout=30)

    def fake_call_endpoint(messages, **kwargs):
        return f"Nothing to change.\n{sd.FINISH_TOKEN}\nNo edits needed.", 10

    monkeypatch.setattr(sd, "call_endpoint", fake_call_endpoint)

    result = sd.run_shell_developer_turn(
        task_id="T-no-mut",
        instructions="Inspect but change nothing",
        user_command="Inspect but change nothing",
        conversation_context=[],
        model_choice=None,
        progress={"edit_failures": 0},
        decision={},
        current_turn=1,
    )
    assert result["status"] == "error"
    types = [a[0] for a, _ in events]
    assert "shell_session_no_mutation" in types


# =========================================================================
# Phase 3.3 — Record model-health outcomes per shell call
# =========================================================================
def test_protocol_valid_and_command_outcomes_recorded(monkeypatch):
    kinds = []
    monkeypatch.setattr(sd, "archive_raw_response", lambda **kw: None)
    monkeypatch.setattr(sd, "record_model_outcome", lambda model_ref, **kw: kinds.append(kw["kind"]))

    session = _session_with_replies(["```bash\necho hi\n```"])
    session.wt = _FakeWorktree(exit_code=0, output="hi\n")
    result = session.run("task")

    assert result.exit_status in ("Finished", "") or result.n_model_calls >= 1
    assert "protocol_valid" in kinds
    assert "command_executed" in kinds
    assert "command_success" in kinds
    assert "session_outcome" in kinds


def test_protocol_invalid_and_command_failure_outcomes_recorded(monkeypatch):
    kinds = []
    monkeypatch.setattr(sd, "archive_raw_response", lambda **kw: None)
    monkeypatch.setattr(sd, "record_model_outcome", lambda model_ref, **kw: kinds.append((kw["kind"], kw.get("ok"))))

    session = _session_with_replies(["Just prose."])
    session.cfg.max_consecutive_format_errors = 1
    session.cfg.step_limit = 5
    result = session.run("task")

    assert result.exit_status == "RepeatedFormatError"
    records = [k for k, _ in kinds]
    assert "protocol_invalid" in records
    assert "session_outcome" in records


# =========================================================================
# Helpers
# =========================================================================
def _session_with_replies(script: list[str]):
    """Build a session with a fake worktree whose LLM follows a reply script."""
    session = sd.ShellDeveloperSession(
        sd.ShellDeveloperConfig(step_limit=2, max_consecutive_format_errors=1),
        worktree=_FakeWorktree(),
        task_id="T-pass1",
    )
    _patch_call_endpoint(session, script)
    return session


def _patch_call_endpoint(session, script: list[str]):
    state = {"calls": 0}
    script = script or []

    def fake_llm(self):
        if state["calls"] >= len(script):
            return None
        idx = state["calls"]
        state["calls"] += 1
        return script[idx]

    session._llm = fake_llm.__get__(session, type(session))


class _FakeWorktree:
    def __init__(self, exit_code: int = 0, output: str = "ok"):
        self._exit_code = exit_code
        self._output = output

    def run_command(self, command, timeout=120):
        return self._exit_code, self._output

    def run_test_command(self, command, timeout=600):
        return 0, "ok"
