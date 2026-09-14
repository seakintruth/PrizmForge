"""§16.3 session projection: payload prune, hot tail, reserve compact + checkpoint.

Exit-criterion proxy kept here: a long chat session's final prompt must not
re-send turn-1 stdout on the last turn, while the raw append-only step table
still holds the verbatim payload.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from core.db import get_db_path
from core.session_projection import (
    build_structural_brief,
    format_context_checkpoint,
    format_step_table_message,
    maybe_compact_session,
    project_step_table,
    prune_messages,
    read_context_checkpoint,
    rebuild_messages_after_compact,
    upsert_context_checkpoint,
    would_exceed_reserve,
)
from workflow import shell_developer as sd

FINISH = sd.FINISH_TOKEN


def _step(
    n: int,
    *,
    output: str = "ok",
    command: str = "echo hi",
    exit_code: int = 0,
    changed: list | None = None,
    diff: str = "",
) -> dict:
    row = {"step": n, "thought": f"thought {n}", "command": command, "exit_code": exit_code, "output": output}
    if changed:
        row["changed"] = changed
    if diff:
        row["diff"] = diff
    return row


class TestStepTableProjection:
    def test_digest_stable_and_sensitive(self):
        from core.session_projection import stdout_digest

        assert stdout_digest("abc") == stdout_digest("abc")
        assert stdout_digest("abc") != stdout_digest("abd")
        assert len(stdout_digest("anything")) == 10

    def test_stubs_old_keeps_hot_tail_verbatim(self):
        big = "LINE\n" * 500
        steps = [
            _step(1, output=big, command="ls -la"),
            _step(2, output=big, command="cat app.py", changed=["app.py"], diff="+x\n-y\n"),
            _step(3, output="tail"),
            _step(4, output="tail2"),
        ]
        projected = project_step_table(steps, hot_tail_turns=3)
        assert len(projected) == 4
        # Old step (index 0) is stubbed: identity + result + hash, no payload.
        old = projected[0]
        assert old["step"] == 1 and old["command"] == "ls -la"
        assert "stdout omitted, hash=" in old["stdout"]
        assert "exit 0" in old["result"]
        assert "output" not in old
        # Hot tail (last 3) rides verbatim, payload included.
        assert projected[1]["output"] == big
        assert projected[1]["diff"] == "+x\n-y\n"
        assert projected[2]["output"] == "tail"
        assert projected[3]["output"] == "tail2"
        # Input is never mutated.
        assert steps[0]["output"] == big

    def test_no_mutation_and_empty(self):
        steps = [_step(1, output="a")]
        out = project_step_table(steps)
        assert out is not steps  # new projection list
        assert out[0] is not steps[0]  # copies, not references
        assert steps[0]["output"] == "a"
        assert project_step_table([]) == []

    def test_all_verbatim_when_within_tail(self):
        steps = [_step(1, output="a"), _step(2, output="b")]
        projected = project_step_table(steps, hot_tail_turns=3)
        assert projected[0]["output"] == "a"
        assert "stdout omitted" not in projected[0]

    def test_format_message_next_step(self):
        steps = [_step(1, output="a"), _step(2, output="b")]
        msg = format_step_table_message(steps)
        assert "step 3" in msg
        assert "Output the JSON object for the next step" in msg
        assert "```json" in msg


class TestPruneMessages:
    def _transcript(self) -> list[dict]:
        big = "X" * 3000
        return [
            {"role": "system", "content": "PROTOCOL"},
            {"role": "user", "content": "Task launch --- evidence listing --- ```json\n[]\n```"},
            {"role": "assistant", "content": '{"step":1}'},
            {"role": "user", "content": "```json\n{}\n```\n\nOutput the JSON object for the next step (step 2) awaiting execution:" + big},
            {"role": "assistant", "content": '{"step":2}'},
            {"role": "user", "content": "```json\n{}\n```\n\nOutput the JSON object for the next step (step 3) awaiting execution:"},
        ]

    def test_keeps_system_launch_and_tail(self):
        msgs = self._transcript()
        pruned = prune_messages(msgs, hot_tail_turns=2)
        assert pruned[0]["content"] == "PROTOCOL"
        assert "Task launch" in str(pruned[1]["content"])  # launch verbatim
        # Hot tail (last 2 observations) preserved verbatim with payload.
        assert any("X" * 3000 in str(m.get("content", "")) for m in pruned)

    def test_stubs_oversized_old_observation(self):
        msgs = self._transcript()
        pruned = prune_messages(msgs, hot_tail_turns=1)
        obs_contents = [str(m["content"]) for m in pruned if m.get("role") == "user"]
        stub = [c for c in obs_contents if "stdout omitted" in c]
        assert stub, "the 3000-char observation must be stubbed"
        assert all(len(c) < 400 for c in stub)

    def test_short_session_untouched_reference(self):
        msgs = [{"role": "user", "content": "one observation only --- Output the JSON object for the next step"}]
        assert prune_messages(msgs) is msgs

    def test_small_nudges_not_stubbed(self):
        msgs = [
            {"role": "system", "content": "s"},
            {"role": "user", "content": "launch"},
            {"role": "assistant", "content": "a1"},
            {"role": "user", "content": "FormatError: reply must contain the JSON step-table object"},
            {"role": "assistant", "content": "a2"},
            {"role": "user", "content": "another FormatError: finish not allowed yet"},
        ]
        pruned = prune_messages(msgs, hot_tail_turns=2)
        assert pruned is msgs  # nothing was big enough to stub


class TestCompactReserve:
    def test_would_exceed_reserve(self):
        assert would_exceed_reserve([], None)[0] is False
        giant = [{"role": "user", "content": "A big payload is repeated here. " * 40000}]
        over, used, limit = would_exceed_reserve(giant, None)
        assert over is True
        assert used > 0 and limit > 0

    def test_below_reserve_returns_unchanged(self, temp_db):
        calls: list = []

        def summarize(messages, task_text):
            calls.append(messages)
            return build_structural_brief(task_text, 0)

        msgs = [{"role": "system", "content": "s"}, {"role": "user", "content": "launch"}]
        out = maybe_compact_session(
            messages=msgs,
            task_id="T-proj",
            task_text="do the thing",
            model_ref=None,
            summarize_cb=summarize,
            reserve_ratio=0.16,
        )
        assert out is msgs
        assert not calls

    def test_compact_at_reserve_anchors_checkpoint(self, temp_db):
        giant = [{"role": "user", "content": "AAAA " * 100000}]

        def summarize(messages, task_text):
            return {
                "goal": "the goal",
                "files": ["app.py"],
                "decisions": ["use sed"],
                "blockers": ["libc missing"],
                "next_command": "cat app.py",
            }

        out = maybe_compact_session(
            messages=giant,
            task_id="T-anchor",
            task_text="goal task",
            model_ref=None,
            steps_count=7,
            summarize_cb=summarize,
        )
        assert out is not giant
        joined = "\n".join(str(m.get("content", "")) for m in out)
        assert "SESSION CHECKPOINT" in joined
        assert "the goal" in joined
        # Anchored checkpoint is persisted (one row), rehydratable.
        ckpt = read_context_checkpoint("T-anchor")
        assert ckpt is not None
        assert ckpt["summary"] == "the goal"
        assert ckpt["original_message_count"] == 1


class TestContextCheckpoint:
    def test_upsert_never_stacks(self, temp_db):
        upsert_context_checkpoint("T-upsert", summary="first", turn_range="steps 1-5", message_count=5)
        upsert_context_checkpoint("T-upsert", summary="second", turn_range="steps 1-9", message_count=9)
        import sqlite3

        conn = sqlite3.connect(get_db_path())
        rows = conn.execute("SELECT summary, turn_range, original_message_count FROM archived_context WHERE task_id = ?", ("T-upsert",)).fetchall()
        conn.close()
        assert len(rows) == 1
        assert rows[0][0] == "second"
        assert rows[0][2] == 9
        ckpt = read_context_checkpoint("T-upsert")
        assert ckpt["summary"] == "second"

    def test_rebuild_keeps_protocol_launch_and_hot_tail(self):
        msgs = [
            {"role": "system", "content": "RESPONSE FORMAT — REQUIRED protocol"},
            {"role": "user", "content": "launch task + evidence"},
            {"role": "assistant", "content": '{"step":1}'},
            {"role": "user", "content": "```json\n{}\n```\n\nOutput the JSON object for the next step (step 2) awaiting execution:" + "Z" * 3000},
            {"role": "assistant", "content": '{"step":2}'},
            {"role": "user", "content": "```json\n{}\n```\n\nOutput the JSON object for the next step (step 3) awaiting execution:"},
        ]
        brief = {"goal": "goal", "files": [], "decisions": [], "blockers": [], "next_command": ""}
        rebuilt = rebuild_messages_after_compact(msgs, brief, hot_tail_turns=1, protocol_prompt="PINNED-PROTOCOL")
        contents = [str(m.get("content", "")) for m in rebuilt]
        assert "PINNED-PROTOCOL" in contents[0]
        assert "SESSION CHECKPOINT" in contents[1]
        assert "launch task" in contents[2]
        # Only the hot-tail observation survives; the old 3000-char body is gone.
        assert contents[-1].startswith("```json") and "Output the JSON object for the next step (step 3)" in contents[-1]
        assert "Z" * 3000 not in contents

    def test_format_checkpoint_labels(self):
        text = format_context_checkpoint({"goal": "g", "files": ["a"], "decisions": [], "blockers": "", "next_command": ""})
        assert "Goal: g" in text
        assert "SESSION CHECKPOINT" in text


# ---------------------------------------------------------------------------
# Integration: 30-step no-replay proxy via a real worktree chat session
# ---------------------------------------------------------------------------
def _repo(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=str(root), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=str(root), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=str(root), check=True, capture_output=True)
    (root / "workflow").mkdir()
    (root / "workflow" / "__init__.py").write_text("# marker\n")
    (root / "app.py").write_text("def greet():\n    return 'old'\n")
    subprocess.run(["git", "add", "-A"], cwd=str(root), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=str(root), check=True, capture_output=True)
    return root


def _chat_row(step: int, command: str | None = None, **extra) -> str:
    row = {"thought": f"step {step}", "step": step, "command": command, "finish": False, "summary": None}
    row.update(extra)
    return json.dumps(row)


def test_chat_session_does_not_replay_turn_one_stdout(tmp_path):
    root = _repo(tmp_path / "repo")
    edit_row = {
        "thought": "edit",
        "step": 5,
        "command": None,
        "finish": False,
        "summary": None,
        "edit": {"path": "app.py", "mode": "replace", "old": "return 'old'", "new": "return 'new'"},
    }
    script = [
        _chat_row(2, "python3 -c \"print('REPLAY-X'*400)\""),
        _chat_row(3, "echo b"),
        _chat_row(4, "echo c"),
        json.dumps(edit_row),
        _chat_row(6, "cat app.py"),
        _chat_row(7, "echo g"),
        _chat_row(8, "echo h"),
        _chat_row(9, "echo i"),
        _chat_row(10, None, finish=True, summary="greet now returns 'new'"),
    ]
    wt = sd.ShellWorktree(root, parent_dir=str(root.parent))
    wt.create()
    session = sd.ShellDeveloperSession(
        sd.ShellDeveloperConfig(step_limit=20, json_table="on"),
        worktree=wt,
        task_id="T-noreplay",
    )
    state = {"i": 0}

    def fake_llm(_self):
        if state["i"] >= len(script):
            return None
        text = script[state["i"]]
        state["i"] += 1
        return text

    session._llm = fake_llm.__get__(session, type(session))
    try:
        result = session.run("Change app.py greet to return 'new'")
        assert session.chat_mode is True
        assert result.exit_status == "Finished"
        assert state["i"] == 9
        # Raw append-only table keeps the verbatim payload for audit.
        assert "REPLAY-X" in session.steps[1]["output"]
        # The final model-facing table prompt must NOT replay turn-1 stdout (only a
        # stub + one-line result remain; the full payload is stubbed).
        final = [str(m["content"]) for m in session.messages if m.get("role") == "user"][-1]
        from core.session_projection import stdout_digest

        raw = session.steps[1]["output"]
        assert ("REPLAY-X" * 400) not in final
        assert f"hash={stdout_digest(raw)}" in final
        # Protocol instructions survive (system prompt never pruned).
        assert "RESPONSE FORMAT" in session.messages[0]["content"]
    finally:
        wt.cleanup()
