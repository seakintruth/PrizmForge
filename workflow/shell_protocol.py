"""Shell developer reply protocol: classification, normalization, diagnostics.

Centralizes the pass-1 shell protocol handling so the session loop, the
trajectory classifier (utils/diagnose_soak.sh) and the unit tests all agree on
one canonical completion token and strict Bash-fence rules.

The canonical completion token is ``FINISH_EDIT_SESSION``. Competing forms
(e.g. ``<finish>``) are intentionally not treated as valid completions.

A reply is a *valid* Bash command block only when, after stripping, it starts
with a `` ```bash`` opening line and ends with a closing `` ``` `` line:

    text.strip().startswith("```bash\\n") and text.strip().endswith("\\n```")
"""

from __future__ import annotations

import json
import re
from typing import Any

FINISH_TOKEN = "FINISH_EDIT_SESSION"

# Matches a *properly closed* bash fence: ```bash ... ``` .
BASH_BLOCK_RE = re.compile(r"```bash\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)

# Classification labels (shared with the trajectory classifier).
VALID_BASH_BLOCK = "VALID_BASH_BLOCK"
UNTERMINATED_BASH_BLOCK = "UNTERMINATED_BASH_BLOCK"
VALID_FINISH_SESSION = "VALID_FINISH_SESSION"
PROSE_OR_UNSUPPORTED_FORMAT = "PROSE_OR_UNSUPPORTED_FORMAT"


def is_valid_bash_block(text: str | None) -> bool:
    """True only for a strictly closed bash fence (open + close)."""
    stripped = (text or "").strip()
    return stripped.startswith("```bash\n") and stripped.endswith("\n```")


def is_unterminated_bash_block(text: str | None) -> bool:
    """True for an opening bash fence that is never closed (and not otherwise valid)."""
    stripped = (text or "").strip()
    if is_valid_bash_block(text):
        return False
    return stripped.startswith("```bash") and not stripped.endswith("```")


def extract_chat_table_action(response: str | None) -> dict[str, Any] | None:  # noqa: C901
    """Extract the next command or finish decision from a chat JSON table response.

    Supports:
    - Direct JSON object: {"thought": "...", "command": "...", "finish": false}
    - JSON list/table: [{"step": 1, ...}, {"step": 2, "command": "..."}] -> takes last entry
    - Nested dictionary: {"steps": [...], ...} or {"table": [...]} -> takes last entry
    """
    if not response or not response.strip():
        return None

    text = response.strip()

    data = None
    # 1. Try markdown json block
    json_match = re.search(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL | re.IGNORECASE)
    if json_match:
        try:
            data = json.loads(json_match.group(1).strip())
        except Exception:
            data = None

    # 2. Try raw JSON extraction bounded by outer braces or brackets
    if data is None:
        first_brace = text.find("{")
        first_bracket = text.find("[")
        if first_brace != -1 and (first_bracket == -1 or first_brace < first_bracket):
            last_brace = text.rfind("}")
            if last_brace != -1 and last_brace > first_brace:
                try:
                    data = json.loads(text[first_brace : last_brace + 1])
                except Exception:
                    data = None
        elif first_bracket != -1:
            last_bracket = text.rfind("]")
            if last_bracket != -1 and last_bracket > first_bracket:
                try:
                    data = json.loads(text[first_bracket : last_bracket + 1])
                except Exception:
                    data = None

    # 3. Fallback to core.json_parser
    if data is None:
        try:
            from core.json_parser import JSONParser

            res = JSONParser().parse(text)
            if res.success and res.data:
                data = res.data
        except Exception:
            data = None

    if not data:
        return None

    # 4. Extract candidate dict
    candidate = None
    if isinstance(data, list):
        candidate = data[-1] if data else None
    elif isinstance(data, dict):
        for key in ("steps", "table", "history", "actions", "step_table"):
            if isinstance(data.get(key), list) and data[key]:
                candidate = data[key][-1]
                break
        if candidate is None:
            candidate = data

    if not isinstance(candidate, dict):
        return None

    # 5. Check for finish vs command
    is_finish = (
        candidate.get("finish") is True
        or str(candidate.get("action", "")).lower() in ("finish", "done", "complete")
        or str(candidate.get("command", "")).strip() == FINISH_TOKEN
    )
    if is_finish:
        summary = candidate.get("summary") or candidate.get("thought") or candidate.get("message") or "Task completed"
        return {
            "type": "finish",
            "summary": str(summary).strip(),
            "thought": candidate.get("thought"),
        }

    command = candidate.get("command") or candidate.get("cmd") or candidate.get("bash")
    if isinstance(command, str) and command.strip():
        cmd = command.strip()
        if cmd == FINISH_TOKEN:
            summary = candidate.get("summary") or candidate.get("thought") or "Task completed"
            return {
                "type": "finish",
                "summary": str(summary).strip(),
                "thought": candidate.get("thought"),
            }
        return {
            "type": "command",
            "command": cmd,
            "thought": candidate.get("thought"),
        }

    return None


def classify_shell_reply(text: str | None) -> str:
    """Classify a shell developer reply into one protocol category.

    Ordering matters: a finished session must not be misread as a command block,
    and a strictly valid block must not be demoted because it also mentions a
    fence elsewhere. Supports both bash blocks and JSON table actions.
    """
    reply = (text or "").strip()

    # 1. A strictly closed bash fence wins outright - even if the finish token
    #    is buried inside it (`` ```bash\nFINISH_EDIT_SESSION\n``` `` is a
    #    command block whose only content is the token, not a finish reply).
    if is_valid_bash_block(reply):
        return VALID_BASH_BLOCK

    # 2. Prose wrapped around a properly closed block still carries an
    #    executable command (the missing-file-claim safety case). Classify on
    #    the raw reply (no normalization) so a genuinely unterminated fence is
    #    not mistaken for a valid one.
    if extract_bash_command(reply, normalize=False) is not None:
        return VALID_BASH_BLOCK

    # 3. A lone opening fence that was never closed (and could not otherwise
    #    execute) is the unterminated case.
    if is_unterminated_bash_block(reply):
        return UNTERMINATED_BASH_BLOCK
    if "```bash" in reply.lower():
        return UNTERMINATED_BASH_BLOCK

    # 4. Finish only when the first non-empty line is exactly the token.
    #    An essay that merely *mentions* FINISH_EDIT_SESSION is prose (Soak4).
    if is_canonical_finish(reply):
        return VALID_FINISH_SESSION

    # 5. Check if chat table action is finish or command
    action = extract_chat_table_action(reply)
    if action:
        if action.get("type") == "finish":
            return VALID_FINISH_SESSION
        if action.get("type") == "command":
            return VALID_BASH_BLOCK

    return PROSE_OR_UNSUPPORTED_FORMAT


def _first_nonempty_line(text: str) -> str:
    for line in (text or "").splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def is_canonical_finish(text: str | None) -> bool:
    """True when the first non-empty line is exactly FINISH_EDIT_SESSION."""
    reply = (text or "").strip()
    if not reply:
        return False
    if is_valid_bash_block(reply) or is_unterminated_bash_block(reply):
        return False
    if extract_bash_command(reply, normalize=False) is not None:
        return False
    if "```bash" in reply.lower():
        return False
    return _first_nonempty_line(reply) == FINISH_TOKEN


def normalize_shell_reply(reply: str | None) -> str:
    """Conservatively repair a lone unterminated bash fence.

    Only repairs a reply that is *exactly* an opening fence with a non-empty
    single command and no embedded fence. Does NOT auto-repair prose mixed with
    commands, multiple fences, empty commands, XML/JSON tool calls, or finish
    tokens inside command blocks.
    """
    text = (reply or "").strip()

    if text.startswith("```bash\n") and not text.endswith("\n```"):
        after = text[len("```bash\n") :]
        command = after.strip()
        if command and "```" not in command:
            return f"```bash\n{command}\n```"

    return reply or ""


def diagnose_shell_reply(response: str | None) -> dict:
    """Return structured invalid-format reasons for a non-executable reply.

    Shape:
        {"reason": str, "response_excerpt": str, "expected": str}

    The session loop logs this when a reply yields no command and no finish.
    """
    text = (response or "").strip()
    excerpt = text[:240]

    classified = classify_shell_reply(text)
    if FINISH_TOKEN in text and classified != VALID_FINISH_SESSION:
        if is_unterminated_bash_block(text) or (classified == UNTERMINATED_BASH_BLOCK):
            return {
                "reason": "unterminated_bash_fence",
                "response_excerpt": excerpt,
                "expected": "closed_bash_block_or_finish_token",
            }
        if is_valid_bash_block(text) or classified == VALID_BASH_BLOCK:
            return {
                "reason": "finish_token_inside_command_block",
                "response_excerpt": excerpt,
                "expected": "closed_bash_block_or_finish_token",
            }

    if is_unterminated_bash_block(text):
        return {
            "reason": "unterminated_bash_fence",
            "response_excerpt": excerpt,
            "expected": "closed_bash_block_or_finish_token",
        }

    return {
        "reason": "prose_or_unsupported_format",
        "response_excerpt": excerpt,
        "expected": "closed_bash_block_or_finish_token",
    }


def extract_bash_command(response: str | None, *, normalize: bool = True) -> str | None:
    """Return the last valid bash command (from ```bash block OR JSON table)."""
    reply = response or ""
    if normalize:
        reply = normalize_shell_reply(reply)
    matches = BASH_BLOCK_RE.findall(reply)
    for block in reversed(matches):
        cmd = block.strip()
        if cmd and not cmd.strip() == FINISH_TOKEN:
            return cmd

    action = extract_chat_table_action(reply)
    if action and action.get("type") == "command":
        return action.get("command")

    return None


def extract_finish(response: str | None) -> str | None:
    """Return the finish summary (from FINISH_EDIT_SESSION token OR JSON table).

    The token is only honored as a finish when it is not buried inside a
    command block (`` ```bash\nFINISH_EDIT_SESSION\n``` `` is a command whose
    content happens to be the token, not a session completion). An essay that
    only mentions the token is not a finish (Soak4).
    """
    reply = (response or "").strip()
    if is_canonical_finish(reply):
        summary_lines = [line for line in reply.splitlines() if line.strip() != FINISH_TOKEN]
        return "\n".join(summary_lines).strip()

    action = extract_chat_table_action(reply)
    if action and action.get("type") == "finish":
        return action.get("summary")

    return None
