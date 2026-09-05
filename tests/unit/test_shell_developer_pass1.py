"""Pass 1 tests: shell protocol handling (Phases 1-2).

Phases 1.2/1.3/1.4/1.5 (example-driven prompt contract, unterminated-fence
normalizer, missing-file safety, structured parser diagnostics) and Phase 2
(worktree/cwd verification) are validated here against the session loop and the
exported parsing helpers.
"""

from __future__ import annotations

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
def test_format_error_diagnostic_reason_recorded():
    # Driving a session into a format error surfaces a structured reason in the
    # exit summary (the observable protocol-diagnostics contract).
    session = _session_with_replies(["This is just prose, no command and no finish."])
    session.cfg.max_consecutive_format_errors = 1
    session.cfg.step_limit = 5
    result = session.run("task")
    assert result.exit_status == "RepeatedFormatError"
    assert "reason=prose_or_unsupported_format" in result.summary


def test_format_error_correction_message_carries_reason_below_threshold():
    # Below the consecutive-error threshold the model is corrected with the
    # structured reason; only on the final error does the session exit.
    session = _session_with_replies(["This is just prose, no command and no finish."])
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
        if not script:
            return None
        idx = min(state["calls"], len(script) - 1)
        state["calls"] += 1
        return script[idx]

    session._llm = fake_llm.__get__(session, type(session))


class _FakeWorktree:
    def run_command(self, command, timeout=120):
        return 0, "ok"

    def run_test_command(self, command, timeout=600):
        return 0, "ok"
