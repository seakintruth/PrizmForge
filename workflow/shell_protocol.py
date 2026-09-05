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

import re

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
    return stripped.startswith("```bash\n") and not is_valid_bash_block(text)


def classify_shell_reply(text: str | None) -> str:
    """Classify a shell developer reply into one protocol category.

    Ordering matters: a finished session must not be misread as a command block,
    and a strictly valid block must not be demoted because it also mentions a
    fence elsewhere.
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

    # 4. Otherwise the canonical completion token is the finish signal.
    if FINISH_TOKEN in reply:
        return VALID_FINISH_SESSION

    return PROSE_OR_UNSUPPORTED_FORMAT


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

    if FINISH_TOKEN in text and not classify_shell_reply(text) == VALID_FINISH_SESSION:
        if is_unterminated_bash_block(text):
            return {
                "reason": "unterminated_bash_fence",
                "response_excerpt": excerpt,
                "expected": "closed_bash_block_or_finish_token",
            }
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
    """Return the last valid bash fenced command, after optional normalization."""
    reply = response or ""
    if normalize:
        reply = normalize_shell_reply(reply)
    matches = BASH_BLOCK_RE.findall(reply)
    for block in reversed(matches):
        cmd = block.strip()
        if cmd and not cmd.strip() == FINISH_TOKEN:
            return cmd
    return None


def extract_finish(response: str | None) -> str | None:
    """Return the finish summary when the canonical token is present.

    The token is only honored as a finish when it is not buried inside a
    command block (`` ```bash\nFINISH_EDIT_SESSION\n``` `` is a command whose
    content happens to be the token, not a session completion).
    """
    reply = (response or "").strip()
    if FINISH_TOKEN not in reply:
        return None
    if is_valid_bash_block(reply) or is_unterminated_bash_block(reply):
        return None
    summary_lines = [line for line in reply.splitlines() if FINISH_TOKEN not in line]
    return "\n".join(summary_lines).strip()
