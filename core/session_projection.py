"""Session projection (§16.3): prune payloads, keep structure, rehydrate.

Long-running developer sessions (OpenCode / Claude Code pattern) stay capable
by changing the *projection* sent to the model, not by stuffing the window:

- **Never replay old stdout.** The chat-JSON-table prompt re-serializes the
  append-only step table every turn. ``project_step_table`` keeps every step's
  identity (step id + one-line result + content hash) but stubs old bulky
  stdout to ``[stdout omitted, hash=...]``; the last 2-3 turns (the "hot
  tail") ride verbatim.
- **Prune the transcript, keep structure.** Old oversized observation
  messages in the running chat are degraded to digest stubs while system
  prompt, the launch prompt, small protocol nudges, and the hot tail stay
  intact.
- **Only ``emergency_compact`` when the window is actually near its reserve**
  (OpenCode buffer / Claude ~16% headroom): a tool-less one-shot summarizer
  writes a structured brief (goal, files, decisions, blockers, next command)
  to a single anchored ``archived_context`` row and the transcript is rebuilt
  from that checkpoint + the hot tail. Summaries are never stacked.
- Raw payloads are never deleted: `shell_trajectories` and
  `agent_responses_archive` keep the verbatim bodies.

No new dependencies. ``archived_context`` already exists (SCHEMA_VERSION 5).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from core.context_manager import get_context_manager
from core.db_connection import get_db_connection
from core.token_estimator import estimate_messages

#: Last N assistant/observation turns that are always delivered verbatim.
HOT_TAIL_TURNS = 3
#: Maximum one-line step-result width.
RESULT_CHARS = 200
#: sha256 prefix length printed in stdout stubs.
OMIT_HASH_CHARS = 10
#: Trigger the emergency compact before 100% of the usable window (16% reserve).
COMPACT_RESERVE_RATIO = 0.16
#: Only observation bodies larger than this are eligible for stubbing.
MIN_OBSERVATION_BYTES = 800

_STEP_TABLE_MARKER = "Output the JSON object for the next step"
#: Start of the bash-fence observation message produced by _observation.
_EXIT_MARKER = "[exit code"
_OMITTED_TEXT = "[stdout omitted, hash=...] rehydrate via shell_trajectories / agent_responses_archive"
#: JSON keys Annex to the checkpoint brief.
_BRIEF_KEYS = ("goal", "files", "decisions", "blockers", "next_command")


# ---------------------------------------------------------------------------
# Step-table projection
# ---------------------------------------------------------------------------
def stdout_digest(text: str) -> str:
    """Short content hash for a stdout stub (deterministic, 10 hex chars)."""
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:OMIT_HASH_CHARS]


def _trim(text: str, n: int = RESULT_CHARS) -> str:
    text = (text or "").strip()
    if len(text) <= n:
        return text
    return text[: n - 3].rstrip() + "..."


def _one_line_result(row: dict[str, Any]) -> str:
    pieces = [f"exit {row.get('exit_code', '?')}"]
    out = (row.get("output") or "").strip()
    if out:
        last = next((ln.strip() for ln in reversed(out.splitlines()) if ln.strip()), "")
        if last:
            pieces.append(f"last output line: {_trim(last)}")
    changed = row.get("changed") or []
    if changed:
        pieces.append(f"changed {len(changed)} path(s)")
    return " | ".join(pieces)


def project_step_table(
    steps: list[dict[str, Any]],
    *,
    hot_tail_turns: int = HOT_TAIL_TURNS,
) -> list[dict[str, Any]]:
    """View of the step table for the next prompt.

    Every row keeps its identity (step id, command, exit code) and a compact
    one-line result; rows older than the hot tail get their bulk ``output`` /
    ``diff`` replaced by a digest stub. The last ``hot_tail_turns`` rows stay
    verbatim. Returns a new list -- the input (the raw append-only table) is
    never mutated.
    """
    projected: list[dict[str, Any]] = []
    tail_start = max(0, len(steps) - hot_tail_turns)
    for i, row in enumerate(steps):
        if not isinstance(row, dict):
            continue
        out: dict[str, Any] = {"step": row.get("step", i + 1)}
        if row.get("thought") is not None:
            out["thought"] = _trim(str(row["thought"]), n=160)
        if row.get("command") is not None:
            out["command"] = row["command"]
        out["exit_code"] = row.get("exit_code")
        if i < tail_start:
            out["result"] = _one_line_result(row)
            out["stdout"] = f"[stdout omitted, hash={stdout_digest(row.get('output') or '')}]"
            if row.get("changed"):
                out["changed"] = row["changed"]
        else:
            if row.get("output") is not None:
                out["output"] = row["output"]
            if row.get("changed"):
                out["changed"] = row["changed"]
            if row.get("diff"):
                out["diff"] = row["diff"]
        projected.append(out)
    return projected


def format_step_table_message(steps: list[dict[str, Any]], *, hot_tail_turns: int = HOT_TAIL_TURNS) -> str:
    """Chat-mode table message: projected JSON table + the awaiting-step row."""
    table = json.dumps(project_step_table(steps, hot_tail_turns=hot_tail_turns), indent=2)
    next_step = (steps[-1]["step"] if steps else 0) + 1
    return f"```json\n{table}\n```\n\nOutput the JSON object for the next step (step {next_step}) awaiting execution:"


# ---------------------------------------------------------------------------
# Transcript pruning (keep structure, digest old payloads)
# ---------------------------------------------------------------------------
def _is_observation_like(content: str) -> bool:
    return _STEP_TABLE_MARKER in content or _EXIT_MARKER in content or "```json" in content


def _observation_indexes(messages: list[dict[str, Any]]) -> list[int]:
    return [i for i, m in enumerate(messages) if m.get("role") == "user" and _is_observation_like(str(m.get("content", "")))]


def prune_messages(
    messages: list[dict[str, Any]],
    *,
    hot_tail_turns: int = HOT_TAIL_TURNS,
    min_observation_bytes: int = MIN_OBSERVATION_BYTES,
) -> list[dict[str, Any]]:
    """Degrade oversized old observation payloads in a running chat transcript.

    Keeps verbatim: the system prompt, the launch (first user) prompt, small
    protocol nudges (FormatError, finish rejection), and the last
    ``hot_tail_turns`` observations. Older observation messages larger than
    ``min_observation_bytes`` are replaced with a digest stub so raw stdout
    cannot replay on every call. Returns the same list object when nothing
    changed (cheap no-op for short sessions).
    """
    if not messages:
        return messages
    obs = _observation_indexes(messages)
    if not obs:
        return messages
    tail_start = obs[-hot_tail_turns] if len(obs) > hot_tail_turns else 0
    first_user_i = next((i for i, m in enumerate(messages) if m.get("role") == "user"), None)

    changed = False
    projected: list[dict[str, Any]] = []
    for i, msg in enumerate(messages):
        if i == 0 and msg.get("role") == "system":
            projected.append(msg)
            continue
        if i < tail_start and i != first_user_i and msg.get("role") == "user" and _is_observation_like(str(msg.get("content", ""))):
            content = str(msg.get("content", ""))
            if len(content) >= min_observation_bytes:
                code = ""
                for line in content.splitlines()[:3]:
                    if line.startswith(_EXIT_MARKER):
                        code = line[len(_EXIT_MARKER) :].split("]")[0].strip()
                        break
                stub = f"[exit code {code}] {_OMITTED_TEXT}" if code else _OMITTED_TEXT
                projected.append({"role": "user", "content": stub})
                changed = True
                continue
        projected.append(msg)
    return projected if changed else messages


# ---------------------------------------------------------------------------
# Emergency compact (only near the reserve) + anchored context checkpoint
# ---------------------------------------------------------------------------
def would_exceed_reserve(
    messages: list[dict[str, Any]],
    model_ref: str | None,
    *,
    reserve_ratio: float = COMPACT_RESERVE_RATIO,
) -> tuple[bool, int, int]:
    """Return ``(over_reserve, estimated_used, usable_limit)`` for this chat.

    The usable window already subtracts the model's output headroom
    (``core.context_manager._usable_context``); the reserve keeps ~16% on top
    so the summarizer itself has room to run.
    """
    try:
        limit = int(get_context_manager().get_model_context_limit(model_ref))
    except Exception:
        limit = 100_000
    used = estimate_messages(messages)
    trigger = max(int(limit * (1 - reserve_ratio)), len(messages) + 8)
    return used >= trigger, used, limit


def build_structural_brief(task_text: str, steps_count: int) -> dict[str, Any]:
    """No-LLM fallback brief: goal captured from the task row, plus step count."""
    return {
        "goal": _trim(task_text or "", n=600),
        "files": "",
        "decisions": f"steps executed so far: {steps_count}",
        "blockers": "",
        "next_command": "",
    }


def _csv(value: Any) -> str:
    """Render a brief list/str field as a single-line CSV-ish string."""
    if isinstance(value, list):
        return "; ".join(str(v) for v in value)
    return str(value or "")


def format_context_checkpoint(brief: dict[str, Any]) -> str:
    """Render the SESSION CHECKPOINT user message (structured brief)."""
    lines = [
        "[SESSION CHECKPOINT - context before the hot tail was compacted. Rehydrated from the task row; "
        "raw payloads remain on disk (shell_trajectories / agent_responses_archive).]"
    ]
    for key in _BRIEF_KEYS:
        val = brief.get(key)
        if val is not None and val != "":
            lines.append(f"- {key.replace('_', ' ').title()}: {val}")
    return "\n".join(lines)


def upsert_context_checkpoint(
    task_id: str,
    *,
    summary: str = "",
    key_decisions: str = "",
    files_modified: str = "",
    turn_range: str = "",
    message_count: int = 0,
) -> int:
    """Anchor ONE checkpoint row per task on ``archived_context``.

    Task checkpoints are never stacked: the second compact of the same task
    updates the same anchored row instead of appending another.
    """
    now = datetime.now(timezone.utc).isoformat()
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT id FROM archived_context WHERE task_id = ? ORDER BY id LIMIT 1",
            (task_id,),
        ).fetchone()
        if row is not None:
            conn.execute(
                """
                UPDATE archived_context
                   SET turn_range = ?, summary = ?, key_decisions = ?,
                       files_modified = ?, archived_at = ?, original_message_count = ?
                 WHERE id = ?
                """,
                (turn_range, summary, key_decisions, files_modified, now, message_count, row[0]),
            )
            return int(row[0])
        conn.execute(
            """
            INSERT INTO archived_context
                (task_id, turn_range, summary, key_decisions, files_modified, archived_at, original_message_count)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (task_id, turn_range, summary, key_decisions, files_modified, now, message_count),
        )
        return int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])


def read_context_checkpoint(task_id: str) -> dict[str, Any] | None:
    """Rehydrate the latest checkpoint for a task (or None)."""
    try:
        with get_db_connection() as conn:
            row = conn.execute(
                """
                SELECT turn_range, summary, key_decisions, files_modified, archived_at, original_message_count
                  FROM archived_context WHERE task_id = ? ORDER BY id DESC LIMIT 1
                """,
                (task_id,),
            ).fetchone()
    except Exception:
        return None
    if row is None:
        return None
    return {
        "turn_range": row[0],
        "summary": row[1],
        "key_decisions": row[2],
        "files_modified": row[3],
        "archived_at": row[4],
        "original_message_count": row[5],
    }


def rebuild_messages_after_compact(
    messages: list[dict[str, Any]],
    brief: dict[str, Any],
    *,
    hot_tail_turns: int = HOT_TAIL_TURNS,
    protocol_prompt: str | None = None,
) -> list[dict[str, Any]]:
    """Rebuild the transcript from DB-backed anchors: system prompt (protocol),
    checkpoint brief, launch prompt (task/target/evidence), then the hot tail.

    Protocol instructions always come back from the caller (system prompt),
    never from a summary, so the bash/edit protocol survives any compact.
    """
    if not messages:
        return list(messages)
    system = protocol_prompt
    if system is None and messages[0].get("role") == "system":
        system = str(messages[0].get("content", ""))
    launch = messages[0]
    if messages[0].get("role") == "system" and len(messages) > 1:
        launch = messages[1]

    obs = _observation_indexes(messages)
    if obs:
        start = obs[-hot_tail_turns] if len(obs) > hot_tail_turns else 0
    else:
        start = max(0, len(messages) - hot_tail_turns)

    rebuilt: list[dict[str, Any]] = []
    if system:
        rebuilt.append({"role": "system", "content": system})
    rebuilt.append({"role": "user", "content": format_context_checkpoint(brief)})
    rebuilt.append(dict(launch))
    rebuilt.extend(messages[start:])
    return rebuilt


def maybe_compact_session(
    *,
    messages: list[dict[str, Any]],
    task_id: str,
    task_text: str,
    model_ref: str | None = None,
    steps_count: int = 0,
    summarize_cb: Callable[[list[dict[str, Any]], str], dict[str, Any]] | None = None,
    reserve_ratio: float = COMPACT_RESERVE_RATIO,
    hot_tail_turns: int = HOT_TAIL_TURNS,
    protocol_prompt: str | None = None,
) -> list[dict[str, Any]]:
    """Compact only when the window is actually near the reserve.

    The one-shot summarizer is injected (default: a structural brief). The
    brief is anchored to ``archived_context`` (upsert, never stacked) and the
    transcript is rebuilt: system/launch/checkpoint/hot-tail. Below the
    reserve this returns ``messages`` unchanged.
    """
    over, _used, _limit = would_exceed_reserve(messages, model_ref, reserve_ratio=reserve_ratio)
    if not over:
        return messages
    columns = [m.get("role") for m in messages]
    turn_range = f"steps 1-{max(steps_count, 1)}"
    if summarize_cb is None:
        brief = build_structural_brief(task_text, steps_count)
    else:
        brief = summarize_cb(messages, task_text) or build_structural_brief(task_text, steps_count)
    upsert_context_checkpoint(
        task_id,
        summary=str(brief.get("goal") or ""),
        key_decisions=_csv(brief.get("decisions")),
        files_modified=_csv(brief.get("files")),
        turn_range=turn_range,
        message_count=len(columns),
    )
    return rebuild_messages_after_compact(
        messages,
        brief,
        hot_tail_turns=hot_tail_turns,
        protocol_prompt=protocol_prompt,
    )
