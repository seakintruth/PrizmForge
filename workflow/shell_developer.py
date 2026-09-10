"""Shell-based Developer agent (mini-swe-agent style, native port).

Derived from the architecture of mini-swe-agent (https://github.com/SWE-agent/mini-swe-agent,
MIT License, Copyright (c) SWE-agent contributors). The control loop, fenced-command
protocol, and finish-sentinel concepts are adapted here; the implementation is native
to PrizmForge and routes every LLM call through call_endpoint() so rate limiting,
token budgeting, endpoint health, and fallback governance still apply.

Flow:
  1. A disposable ``git worktree`` of the project is created for the session.
  2. The model edits files by emitting ```bash fenced commands that run inside the
     worktree (real shell access — it can read, write, and run tests).
  3. When finished, changed files are converted into governed EditPayload proposals
     (create_file / full_replace) and pushed through the standard Reviewer gate and
     materialize_proposal() pipeline. Nothing touches the governed tree without an
     approved proposal.

Chat-capable models (chat_capable endpoint flag, or Gemini
Enterprise chat) are driven with the chat-JSON-table protocol instead of bash
fences: the session maintains an append-only JSON table of executed steps and
asks the model to complete the NEXT row (command or finish). The parser in
``workflow.shell_protocol`` treats both forms identically. A shell turn that
errors falls back to an ``edit_payload`` mutation in the same turn.

The legacy structured EditPayload developer path remains available via
``config.developer.implementation = "edit_payload"``.
"""

from __future__ import annotations

import json
import re
import shlex
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from agents.base import call_endpoint
from agents.worker_utils import foreground_session_guard
from core.archival import archive_raw_response
from core.config import get_config
from core.db_connection import get_db_connection
from core.db_helpers import post_message
from core.events import publish_event
from core.model_health import record_model_outcome
from file_editing.undo import snapshot_before_apply
from file_editing.writer import materialize_proposal
from workflow import shell_protocol
from workflow.proposal_builder import create_proposal_from_developer_output, update_proposal_status
from workflow.reviewer_gate import handle_reviewer_rejection, post_reviewer_suggestions, request_review_verdict

FINISH_TOKEN = shell_protocol.FINISH_TOKEN
BASH_BLOCK_RE = shell_protocol.BASH_BLOCK_RE
MAX_RATIONALE_CHARS = 3000
WORKSPACE_MARKER_DEFAULT = "workflow/__init__.py"
EVIDENCE_PROMPT_COMMAND = "pwd && git rev-parse --show-toplevel && ls -la"

# Soak6 mutation policy: a shell session may only promote bounded, coherent
# changes to governed proposals, and inspect commands must not burn the write
# budget.
FULL_REPLACE_MAX_LINES = 200
SHELL_PROMOTE_MAX_DIFF_LINES = 80
INSPECT_STEP_CAP = 40  # extra budget; does not burn step_limit (mutate budget)


def _fallback_order_for_targets(
    fallback_order: list[str],
    targets: list[str],
    small_file_threshold: int,
) -> list[str]:
    """Never offer full_replace on a file over FULL_REPLACE_MAX_LINES.

    Soak6: the edit_payload fallback ended its chain in full_replace, which
    handed the reviewer truncated whole-file content for oversized targets.
    Read each target on disk; if any exceeds the cap (bounded by the configured
    small-file threshold), drop full_replace from the fallback chain entirely.
    """
    cap = min(small_file_threshold, FULL_REPLACE_MAX_LINES)
    too_big = False
    for rel in targets:
        try:
            text = Path(rel).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if text.count("\n") + 1 > cap:
            too_big = True
            break
    if not too_big:
        return list(fallback_order)
    stripped = [m for m in fallback_order if m != "full_replace"]
    print(f"   ⚠️  Skipping full_replace fallback ({cap}+ line target)")
    return stripped or ["guid", "diff", "find_replace"]


# =========================================================================
# Configuration
# =========================================================================
@dataclass
class ShellDeveloperConfig:
    step_limit: int = 30
    wall_time_limit_minutes: int = 20
    command_timeout_seconds: int = 120
    test_timeout_seconds: int = 600
    max_output_chars: int = 6000
    max_file_bytes: int = 512_000
    max_consecutive_format_errors: int = 3
    test_command: str = ""
    on_test_failure: str = "discard"  # "discard" | "propose_anyway"
    model: str | None = None
    llm_failure_max_retries: int = 3
    llm_retry_backoff_seconds: int = 15
    worktree_parent: str = ""  # empty → system temp dir
    workspace_marker: str = WORKSPACE_MARKER_DEFAULT
    # Chat-JSON-table protocol mode. "auto" -> enabled for models flagged
    # chat_capable in endpoint config or that resolve onto Gemini Enterprise
    # chat. "on" forces it for every model; "off" disables it
    # (falling back to the historical bash-fence-only protocol).
    json_table: str = "auto"
    # Stall tripwire: a step with no worktree change that repeats an already
    # executed command OR exited non-zero counts toward the stall. When the
    # counter reaches no_change_stall_limit the session exits "Stalled"
    # instead of burning to the step limit (Soak16: 30 calls, 0 edits).
    # 0 disables the tripwire.
    no_change_stall_limit: int = 6
    # No-progress tripwire: ANY step that leaves the worktree unchanged (even a
    # novel command) counts toward no_progress_stall_limit; when it fires the
    # session exits "NoProgress". Closes the Soak18 gap where a discovery loop
    # circled the tree with novel grep/cat steps forever (no_change_stall_limit
    # only counted repeated/failing actions). 0 disables.
    no_progress_stall_limit: int = 10
    # Task-fiability pre-flight. "auto": an untargeted task ("review the
    # TODO list") gets its step_limit capped to explore_step_cap so it cannot
    # burn a full session hunting a file. "strict": an untargeted task
    # short-circuits before any LLM call.
    task_scope: str = "auto"
    explore_step_cap: int = 12
    # Internal: computed by the turn entry point (not read from config) so the
    # prompt can tell the model when the task is exploratory, not mutation-led.
    fiability: str = "targeted"  # "targeted" | "exploratory"

    @classmethod
    def from_config(cls) -> ShellDeveloperConfig:
        cfg = get_config().get("shell_developer", {}) or {}
        instance = cls(
            step_limit=int(cfg.get("step_limit", 30)),
            wall_time_limit_minutes=int(cfg.get("wall_time_limit_minutes", 20)),
            command_timeout_seconds=int(cfg.get("command_timeout_seconds", 120)),
            test_timeout_seconds=int(cfg.get("test_timeout_seconds", 600)),
            max_output_chars=int(cfg.get("max_output_chars", 6000)),
            max_file_bytes=int(cfg.get("max_file_bytes", 512_000)),
            max_consecutive_format_errors=int(cfg.get("max_consecutive_format_errors", 3)),
            test_command=str(cfg.get("test_command", "") or ""),
            on_test_failure=str(cfg.get("on_test_failure", "discard") or "discard"),
            model=cfg.get("model") or None,
            llm_failure_max_retries=int(cfg.get("llm_failure_max_retries", 3)),
            llm_retry_backoff_seconds=int(cfg.get("llm_retry_backoff_seconds", 15)),
            worktree_parent=str(cfg.get("worktree_parent", "") or ""),
            workspace_marker=str(cfg.get("workspace_marker") or WORKSPACE_MARKER_DEFAULT),
            json_table=str(cfg.get("json_table", "auto") or "auto"),
            no_change_stall_limit=int(cfg.get("no_change_stall_limit", 6) or 6),
            no_progress_stall_limit=int(cfg.get("no_progress_stall_limit", 10) or 10),
            task_scope=str(cfg.get("task_scope", "auto") or "auto"),
            explore_step_cap=int(cfg.get("explore_step_cap", 12) or 12),
        )
        if instance.on_test_failure not in ("discard", "propose_anyway"):
            print(f"   ⚠️ shell_developer.on_test_failure={instance.on_test_failure!r} is invalid; using 'discard' (fail closed)")
            instance.on_test_failure = "discard"
        if instance.json_table not in ("auto", "on", "off"):
            print(f"   ⚠️ shell_developer.json_table={instance.json_table!r} is invalid; using 'auto'")
            instance.json_table = "auto"
        if instance.no_change_stall_limit < 0:
            print(f"   ⚠️ shell_developer.no_change_stall_limit={instance.no_change_stall_limit} is invalid; using 6")
            instance.no_change_stall_limit = 6
        if instance.no_progress_stall_limit < 0:
            print(f"   ⚠️ shell_developer.no_progress_stall_limit={instance.no_progress_stall_limit} is invalid; using 10")
            instance.no_progress_stall_limit = 10
        if instance.task_scope not in ("auto", "strict"):
            print(f"   ⚠️ shell_developer.task_scope={instance.task_scope!r} is invalid; using 'auto'")
            instance.task_scope = "auto"
        if instance.explore_step_cap < 0:
            print(f"   ⚠️ shell_developer.explore_step_cap={instance.explore_step_cap} is invalid; using 12")
            instance.explore_step_cap = 12
        return instance


# =========================================================================
# Prompts (adapted from mini-swe-agent's system/instance templates)
# =========================================================================
SYSTEM_PROMPT = """You are the Developer agent of an autonomous software engineering system.

You are working in a disposable copy of the project repository. Your job is to complete \
the given task by editing files directly with shell commands, then verifying your work.

RESPONSE FORMAT — REQUIRED:
- Apply file edits with the edit block primitive instead of sed/heredoc. The harness
  applies it directly to the file (no shell quoting, no escaping issues):
    ```edit path/to/file.py
    OLD:
    <exact lines currently in the file>
    NEW:
    <replacement lines>
    ```
  Use `mode: full` + `CONTENT:` to replace a whole file:
    ```edit path/to/file.py
    mode: full
    CONTENT:
    <full new file contents>
    ```
  The OLD section must match the file exactly (whitespace included). If your edit
  is rejected, read the file and resend with the exact current content.
- Otherwise think briefly, then emit EXACTLY ONE bash command inside a single ```bash fenced block. \
It will be executed with the project copy as the working directory.
- Use commands to inspect files, apply edits, and run the project's tests or linters.
- Prefer small, verifiable steps. After editing, run relevant tests to check your work.
- When the task is fully done and verified, reply with {finish_token} as the first line \
followed by a short summary of what changed. Do not emit a bash block or edit block in that final reply.
- A closed bash block looks exactly like this (opening line, the command, closing line):

```bash
sed -n '1,80p' path/to/file.py
```

Never attempt to interact outside this working copy; changes outside it are discarded."""


_SEED_PATH_RE = re.compile(r"[\w./-]+\.\w+")

# Version-like / domain-like tokens harvested from seed prose (gemini-3.1,
# v1.2) are not file targets. A suffix that is purely numeric
# (…\.3.1) is a version; multi-part dot tokens with no slash and no known code
# extension (….mil) are domains. Neither should abort or drive the inspect path.
_VERSIONISH_EXT_RE = re.compile(r"\.\d+(\.\w+)*$")

# Extensions that make a bare token (no path separator) look like a real
# target file rather than a domain / prose artifact.
_SEED_KNOWN_EXTENSIONS = frozenset(
    [
        ".py",
        ".pyw",
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".json",
        ".jsonc",
        ".md",
        ".rst",
        ".txt",
        ".toml",
        ".yaml",
        ".yml",
        ".ini",
        ".cfg",
        ".conf",
        ".sh",
        ".bash",
        ".sql",
        ".html",
        ".css",
        ".xml",
        ".go",
        ".rs",
        ".c",
        ".cpp",
        ".h",
        ".hpp",
        ".java",
        ".lock",
        ".svg",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
    ]
)

_NO_SHELL_FINISH_MARKERS = (
    "upload files",
    "upload the files",
    "please upload",
    "no filesystem",
    "do not have shell",
    "don't have shell",
    "no shell access",
    "gemini enterprise",
    "conversational assistant",
    "conversational ai",
    "i cannot execute",
    "cannot run shell",
    "no access to the file system",
    "no access to your filesystem",
    "automated script runner",
    "i operate as a conversational",
)

_ENTERPRISE_CHAT_MARKERS = ""


def build_instance_prompt(task_text: str, *, explore_note: bool = False, discovery_note: str = "") -> str:
    base = (
        f"TASK:\n{task_text}\n\n"
        "Begin by inspecting the relevant files, then implement the change and verify it. "
        "If the task target file does not exist, do NOT create or guess a task-named path. "
        f"Unless you can find a safe, in-repo change that directly satisfies the task, reply "
        f"with only {FINISH_TOKEN} as the first line and a clear summary of why no safe change was made."
    )
    if explore_note:
        base += (
            "\n\nThis task does not name a concrete file target, so treat it as an exploration "
            "task with a limited budget: briefly inspect the repo for a change that directly "
            f"satisfies it, and if none exists, reply with {FINISH_TOKEN} and a short summary "
            "of what you inspected and why no change was warranted."
        )
    if discovery_note:
        base += f"\n\n{discovery_note}"
    return base


def build_inspect_prompt(
    task_text: str,
    evidence: dict[str, Any],
    target_path: str | None,
    explore_note: bool = False,
    discovery_note: str = "",
) -> str:
    listing = (evidence.get("output_excerpt") or "").strip()
    header = f"Workspace listing (already executed, exit 0):\n{listing}\n\n"
    if target_path:
        return (
            f"{header}Target file: {target_path}\n\n"
            f"{build_instance_prompt(task_text, explore_note=explore_note, discovery_note=discovery_note)}\n"
            "Reply with exactly one closed bash block or ```edit block. First command must be:\n"
            f"sed -n '1,80p' {target_path}"
        )
    return (
        f"{header}{build_instance_prompt(task_text, explore_note=explore_note, discovery_note=discovery_note)}\n"
        "Reply with exactly one closed bash block or ```edit block. Inspect the relevant files first."
    )


# Chat-JSON-table protocol prompts. Chat-tuned models (Gemini Enterprise chat,
# any endpoint whose model config flags chat_capable) resist naked bash fences
# but follow structured schema completion well. The session passes it an
# append-only JSON table of executed steps and asks it to complete the NEXT
# row; the parser takes that last row as the next command (or finish).
CHAT_SYSTEM_PROMPT = """You are the Developer agent of an autonomous software engineering system.

You are working in a disposable copy of the project repository. Your job is to complete \
the given task by editing files directly with shell commands, then verifying your work.

RESPONSE FORMAT — REQUIRED:
- Interact with the file system ONLY through bash commands you emit, OR through
  the structured edit action (see below).
- Apply file edits with the structured edit action instead of sed/heredoc — the
  harness applies it directly to the file:
    {{ "thought": "why", "step": <n>, "edit": {{
      "path": "path/to/file.py",
      "mode": "replace",
      "old": "<exact lines currently in the file>",
      "new": "<replacement lines>"
    }} }}
  Use `"mode": "full"` + `"new"` (no `"old"`) to replace a whole file. The old
  text must match the file exactly (whitespace included); if rejected, read the
  file and resend with the exact current content.
- You are shown a JSON table of the steps executed so far (command, exit code,
  output). Do NOT repeat past steps. Complete the NEXT row of that table.
- Reply with EXACTLY ONE JSON object (no markdown fences, no prose before or
  after unless asked) with this shape:
    {{
      "thought": "why you are running this command",
      "step": <next step number>,
      "command": "<exact bash command to run>",
      "finish": false,
      "summary": null
    }}
- Use commands to inspect files, apply edits, and run the project's tests or linters.
- Prefer small, verifiable steps. After editing, run relevant tests to check your work.
- When the task is fully done and verified, emit instead:
    {{
      "thought": "Verification complete",
      "step": <next step number>,
      "command": null,
      "finish": true,
      "summary": "<concise summary of what changed>"
    }}
- The command must be a single bash command (you may chain with &&). It will be
  executed in the disposable copy. You will see its exit code and output as the
  next table row.

Never attempt to interact outside this working copy; changes outside it are discarded."""


def build_chat_prompt(
    task_text: str,
    evidence: dict[str, Any],
    target_path: str | None,
    steps: list[dict[str, Any]],
    explore_note: bool = False,
    discovery_note: str = "",
) -> str:
    """Build the chat-mode user prompt: JSON table of past steps + the next-row
    instruction. Mirrors build_inspect_prompt but asks the model to complete the
    awaiting step of an append-only JSON table (chat-JSON-table protocol)."""
    task_block = build_instance_prompt(task_text, explore_note=explore_note, discovery_note=discovery_note)
    if not steps:
        listing = (evidence.get("output_excerpt") or "").strip()
        header = f"Workspace listing (already executed, exit 0):\n{listing}\n\n"
        body = header + task_block
    else:
        table = json.dumps(steps, indent=2)
        body = f"Steps executed so far:\n```json\n{table}\n```\n\n{task_block}"
    if target_path:
        body += f"\n\nTarget file: {target_path}\nFirst command must be:\nsed -n '1,80p' {target_path}"
    body += (
        "\n\nOutput the JSON object for the next step (an edit action or a "
        "command — never both in one row; step " + str((steps[-1]["step"] if steps else 0) + 1) + ") awaiting execution:"
    )
    return body


def _chat_table_mode(cfg: ShellDeveloperConfig | None, model_ref: str | None) -> bool:
    """Decide whether a session should use the chat-JSON-table protocol.

    ``json_table`` config knob: "on" forces, "off" disables, "auto" (default)
    enables when the resolved model is flagged chat_capable in endpoint config
    or resolves onto Gemini Enterprise chat — the models that
    refuse naked bash fences. Never raises.
    """
    mode = cfg.json_table if cfg is not None else "auto"
    if mode == "on":
        return True
    if mode == "off":
        return False
    if not model_ref:
        return False
    # Per-model capability flag in endpoint config (endpoints.<ep>.models.<name>).
    try:
        from core.endpoint_manager import get_endpoint_manager

        mgr = get_endpoint_manager()
    except Exception:
        mgr = None
    chat_capable = False
    if mgr is not None:
        try:
            chat_capable = bool((mgr.get_model_config(model_ref) or {}).get("chat_capable"))
        except Exception:
            chat_capable = False
    if chat_capable:
        return True
    # Existing Enterprise-chat detection keeps the Soak5 fix: those models get
    # the JSON-table protocol instead of a hard abort.
    return is_enterprise_chat_developer(model_ref, _enterprise_chat_base_url(model_ref))


def _seed_path_candidates(task_text: str) -> list[str]:
    """File-like tokens from the seed, longest-first.

    Drops ``..`` / absolute candidates and version/domain-like tokens
    (gemini-3.1, v1.2) that seed prose will otherwise harvest.
    Mirrors ``parallel_workers._resolve_seed_target_path`` (longest-wins, then
    an in-repo existence check) so a false-positive token cannot abort the
    session (PR #122 review).
    """
    found = sorted(set(_SEED_PATH_RE.findall(task_text or "")), key=len, reverse=True)
    return [c for c in found if not _versionish_or_invalid(c)]


def _versionish_or_invalid(candidate: str) -> bool:
    """True when a seed token must not be treated as a target path."""
    if "/" in candidate:
        # reject explicit parent escapes or absolute paths inside a path token
        if candidate.startswith("/") or any(part == ".." for part in candidate.split("/")):
            return True
        return False
    # A bare token with a purely-numeric version suffix (3.1) or a non-code,
    # multi-dot domain shape is not a file target.
    if _VERSIONISH_EXT_RE.search(candidate):
        return True
    if candidate.count(".") >= 2 and Path(candidate).suffix.lower() not in _SEED_KNOWN_EXTENSIONS:
        return True
    return False


def _file_exists_on_disk(worktree: Any | None, rel_path: str | None) -> bool:
    """True only when ``rel_path`` resolves to a real file inside the worktree.

    Soak17 §11.1: a ``files_needed`` / addressed-feedback target counts only
    when it exists on disk. ``resolve_seed_target_path`` already does this for
    seed text; this is the decision-list counterpart.
    """
    if not rel_path:
        return False
    root = None
    if worktree is not None:
        try:
            root = Path(worktree.working_dir())
        except Exception:
            root = Path(getattr(worktree, "path", "") or "")
            if not str(root):
                root = None
    if root is None or not root.is_dir():
        return False
    try:
        return (root / rel_path).is_file()
    except (OSError, TypeError, ValueError):
        return False


def _feedback_file_path_for_id(feedback_id) -> str | None:
    """Resolve an addressed feedback id to its ``file_path`` (None on miss).

    Mirrors task_runner's fallback-target lookup so a targeted session is only
    chosen when the feedback's file actually exists on disk (§11.1).
    """
    try:
        fid = int(feedback_id)
    except (TypeError, ValueError):
        return None
    try:
        with get_db_connection() as conn:
            row = conn.execute("SELECT file_path FROM agent_feedback WHERE id = ? LIMIT 1", (fid,)).fetchone()
    except Exception:
        return None
    if not row or not row[0]:
        return None
    return str(row[0])


_DISCOVERY_KEYWORDS = "todo|idea|plan|roadmap|backlog"


def _discovery_glob_note(named: str) -> str:
    """Soak17 §11.1: generic exploration hint when a seed names no existing file.

    No hard-coded repo names — the model is pointed at a case-insensitive glob
    over ``*.md`` / ``*.markdown`` matching discovery keywords, then asked to
    complete the task against what it finds or finish with a summary.
    """
    return (
        f"The named target ({named}) does not exist in this workspace. Treat this as an "
        f"exploration task: locate the intended document with a case-insensitive glob of "
        f"`{_DISCOVERY_KEYWORDS}` over `*.md` / `*.markdown`, then either make a safe "
        "in-repo change that directly satisfies the task or finish with a summary of what "
        "you inspected and why no change was warranted."
    )


def _path_like_seed_candidate(candidate: str) -> bool:
    """True when the token is plausibly a real in-repo target path: it has a
    path separator, or a bare-token code/doc extension. Only such a surviving
    candidate warrants the documented §10.4.2 'target missing' abort; a
    version/domain token or a bare prose artifact does not."""

    def _part_ok(part: str) -> bool:
        return part not in ("", ".", "..") and not _VERSIONISH_EXT_RE.search(part)

    parts = (candidate or "").split("/")
    if not parts:
        return False
    if any(not _part_ok(p) for p in parts):
        return False
    if candidate.startswith("/"):
        return False
    # A bare token is a target only when it carries a known code/doc extension.
    if "/" not in candidate:
        return Path(candidate).suffix.lower() in _SEED_KNOWN_EXTENSIONS
    return True


def resolve_seed_target_path(task_text: str, worktree: Any | None = None, marker: str = WORKSPACE_MARKER_DEFAULT) -> str | None:
    candidates = _seed_path_candidates(task_text)
    root = None
    if worktree is not None:
        try:
            root = Path(worktree.working_dir())
        except Exception:
            root = Path(getattr(worktree, "path", "") or "")
            if not str(root):
                root = None
    if root is not None and root.is_dir():
        for candidate in candidates:
            try:
                if (root / candidate).is_file():
                    return candidate
            except (OSError, TypeError, ValueError):
                continue
        return None
    return candidates[0] if candidates else None


def command_touches_target(command: str | None, target: str | None) -> bool:
    if not command or not target or is_evidence_command(command):
        return False
    return target in command


def _parse_name_status(lines: list[str]) -> list[tuple[str, str]]:
    """[(code, path)] from git --name-status lines ("M<tab>path"). Robust to
    spaces in paths (path is everything after the first tab) and renames."""
    pairs: list[tuple[str, str]] = []
    for line in lines:
        line = line.strip()
        if not line or line[0] not in "AMDR":
            continue
        parts = line.split("\t")
        code = parts[0][0]
        path = parts[1] if len(parts) > 1 else parts[0][1:].strip()
        if not path or code.startswith("R"):
            continue
        pairs.append((code, path))
    return pairs


def _safe_edit_target(workdir: str, raw_path: str) -> Path | None:
    """Resolve a model-supplied edit path that must stay inside the worktree."""
    if not raw_path or raw_path.startswith(("/", "\\")):
        return None
    if ".." in Path(raw_path).parts:
        return None
    root = Path(workdir)
    full = (root / raw_path).resolve()
    root_res = root.resolve()
    if full != root_res and root_res not in full.parents:
        return None
    return full


def _worktree_change_state(wt: Any) -> tuple[list[str], str]:
    """The worktree's change-state feed, safe against test doubles without git."""
    change = getattr(wt, "change_state_since_baseline", None)
    if change is None:
        return [], ""
    try:
        return change()
    except Exception:
        return [], ""


def finish_claims_no_shell(summary: str | None) -> bool:
    low = (summary or "").lower()
    return any(marker in low for marker in _NO_SHELL_FINISH_MARKERS)


def is_enterprise_chat_developer(model_ref: str | None, base_url: str = "") -> bool:
    blob = f"{model_ref or ''} {base_url or ''}".lower()
    return any(marker in blob for marker in _ENTERPRISE_CHAT_MARKERS)


def _enterprise_chat_base_url(model_ref: str | None) -> str:
    try:
        from core.endpoint_manager import get_endpoint_manager

        mgr = get_endpoint_manager()
        ep_name = (model_ref or "").split("/", 1)[0]
        ep = mgr.endpoints.get(ep_name) if ep_name else None
        return str(getattr(ep, "base_url", "") or "") if ep is not None else ""
    except Exception:
        return ""


# =========================================================================
# Response parsing
# =========================================================================
def extract_bash_command(response: str) -> str | None:
    """Return the last ```bash fenced command in the response, if any.

    A lone unterminated opening fence is recovered first (see
    ``shell_protocol.normalize_shell_reply``) so a truncated reply can still be
    executed rather than wasting a format-error retry.
    """
    return shell_protocol.extract_bash_command(response)


def extract_finish(response: str) -> str | None:
    """Return the finish summary when FINISH_EDIT_SESSION is present."""
    return shell_protocol.extract_finish(response)


def classify_shell_reply(response: str) -> str:
    """Classify a reply into a protocol category (shared trajectory/classifier)."""
    return shell_protocol.classify_shell_reply(response)


def evidence_command(marker: str = WORKSPACE_MARKER_DEFAULT) -> str:
    return f"{EVIDENCE_PROMPT_COMMAND} && test -f {marker} && echo {marker}"


def is_evidence_command(command: str | None) -> bool:
    cmd = command or ""
    if "git rev-parse --show-toplevel" not in cmd:
        return False
    if re.search(r"\becho\b", cmd, re.I) and "shell access" in cmd.lower():
        return False
    return True


def is_inspect_command(command: str | None) -> bool:
    """Classify one model bash command as read-only inspection vs a mutation.

    Inspection (`sed -n`, `grep`, `ls`, git log/diff/status, ...) must not burn
    the session's `step_limit` mutate budget (Soak6: 30 calls of sed/cat/git
    diff exhausted the session with zero edits). Any redirect, `python`,
    `base64`, `tee`, `rm`, `mv`, or `cp` is treated as a write.
    """
    if not command:
        return False
    first = command.strip().splitlines()[0].strip()
    # single-purpose readers; any redirect / python / tee is a write
    if any(tok in first for tok in (">", ">>", "tee ", "python", "base64", "rm ", "mv ", "cp ")):
        return False
    heads = (
        "sed -n",
        "nl ",
        "wc -l",
        "grep ",
        "rg ",
        "cat ",
        "head ",
        "tail ",
        "git diff",
        "git status",
        "git log",
        "git rev-parse",
        "git show",
        "ls ",
        "ls\t",
        "pwd",
        "find ",
    )
    return first.startswith(heads) or first in ("ls", "pwd", "git status", "git diff")


_BANNED_WRITE = (
    "base64.b64decode",
    "base64 -d",
    "base64 --decode",
    "exec(",
    "compile(",
    ";exec",
)


def is_banned_write_command(command: str | None) -> bool:
    """Block python/base64 write-exec paths that bypass the edit primitive."""
    if not command:
        return False
    if "python" in command and any(tok in command for tok in _BANNED_WRITE):
        return True
    if "python -c" in command and ("open(" in command and any(m in command for m in ("'w'", '"w"', "'wb'", '"wb"'))):
        return True
    return False


def augment_evidence_command(command: str, marker: str = WORKSPACE_MARKER_DEFAULT) -> str:
    cmd = (command or "").rstrip()
    test_bit = f"test -f {marker}"
    echo_bit = f"echo {marker}"
    if test_bit not in cmd:
        cmd = f"{cmd} && {test_bit}"
    if echo_bit not in cmd:
        cmd = f"{cmd} && {echo_bit}"
    return cmd


def parse_evidence_output(output: str, exit_code: int, marker: str, cwd: str = "") -> dict[str, Any]:
    lines = [ln.strip() for ln in (output or "").splitlines() if ln.strip()]
    git_root = lines[1] if len(lines) >= 2 else ""
    marker_found = marker in (output or "")
    return {
        "cwd": lines[0] if lines else cwd,
        "git_root": git_root,
        "exit_code": exit_code,
        "output_excerpt": (output or "")[:2000],
        "marker": marker,
        "marker_found": marker_found,
        "task_path_exists": marker_found,
    }


def evidence_inject_message(marker: str = WORKSPACE_MARKER_DEFAULT) -> str:
    return (
        "Do not ask the user to upload files or provide repository contents. "
        "You have shell access to the project checkout. "
        "Command stdout is the repository. "
        "You have a real shell in a disposable worktree; emit the evidence command now. "
        f"Do not reply with {FINISH_TOKEN} yet.\n"
        f"```bash\n{EVIDENCE_PROMPT_COMMAND}\n```"
    )


# =========================================================================
# Worktree isolation
# =========================================================================
class ShellWorktree:
    """Disposable git worktree of the project for one developer session."""

    def __init__(self, project_directory: Path, parent_dir: str = "", max_file_bytes: int = 512_000):
        self.project_directory = project_directory.resolve()
        self._parent = Path(parent_dir) if parent_dir else Path(tempfile.gettempdir())
        self.max_file_bytes = max_file_bytes
        self.path: Path | None = None
        self.repo_root: Path | None = None
        self._sub_rel: Path = Path(".")
        self._added = False
        # Tree recorded right after the governed-state overlay; collect_changes()
        # diffs against it so pre-existing DB/HEAD drift is not re-proposed as
        # agent work.
        self._baseline_tree: str | None = None

    def _git(self, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", *args],
            cwd=str(cwd or self.project_directory),
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )

    def create(self) -> Path:
        root_proc = self._git("rev-parse", "--show-toplevel")
        if root_proc.returncode != 0:
            raise RuntimeError(f"shell developer requires '{self.project_directory}' to be inside a git repository")
        self.repo_root = Path(root_proc.stdout.strip()).resolve()
        try:
            self._sub_rel = self.project_directory.relative_to(self.repo_root)
        except ValueError:
            # git rev-parse resolves a repo that contains project_directory, so
            # this is defensive only; fall back to repo root.
            self._sub_rel = Path(".")
        # Refuse a target that the resolved repo explicitly ignores. This is the
        # soak bug: a target under the enclosing repo but git-ignored (e.g.
        # .soak/) cannot be staged by git worktree + collect_changes(), so
        # governed edits there would be silently lost while the developer burns
        # quota producing nothing. Fail loud instead.
        ign = self._git("check-ignore", "-q", str(self.project_directory))
        if ign.returncode == 0:
            raise RuntimeError(
                f"shell developer: project_directory '{self.project_directory}' is git-ignored by "
                f"repository '{self.repo_root}'. git cannot track changes to an ignored path, so "
                f"governed edits would never be collected. Remove the path from .gitignore or point "
                f"project_directory at a tracked, inside-repo location."
            )
        self._parent.mkdir(parents=True, exist_ok=True)
        workdir = Path(tempfile.mkdtemp(prefix="pf-shelldev-", dir=str(self._parent)))
        self.path = workdir / "wt"

        add = self._git("worktree", "add", "--detach", str(self.path), "HEAD", cwd=self.repo_root)
        if add.returncode != 0:
            raise RuntimeError(f"failed to create worktree: {add.stderr.strip()}")
        self._added = True

        cwd = self.working_dir()
        cwd.mkdir(parents=True, exist_ok=True)
        self.sync_governed_state()
        self._snapshot_baseline()
        return cwd

    def _snapshot_baseline(self) -> None:
        """Stage the post-sync worktree and record its tree as the change baseline.

        sync_governed_state() may write DB content that differs from HEAD (uncommitted
        materializations from earlier turns). Diffing against HEAD would surface that
        drift as agent-authored changes and re-propose files the model never touched,
        so collect_changes() compares against this baseline instead.
        """
        assert self.path is not None
        add = self._git("add", "-A", cwd=self.path)
        if add.returncode != 0:
            print(f"   ⚠️ Could not stage baseline snapshot: {add.stderr.strip()}")
            return
        tree = self._git("write-tree", cwd=self.path)
        if tree.returncode == 0 and tree.stdout.strip():
            self._baseline_tree = tree.stdout.strip()

    def sync_governed_state(self) -> int:
        """Overlay governed DB content onto the fresh HEAD worktree.

        Materialized proposals live in the governed DB / working tree and are not
        guaranteed to be committed; branching from HEAD alone could hand the agent
        stale file versions, so its full_replace payloads would carry stale-base
        content while the Reviewer compares against DB content. This rewrites every
        tracked non-deleted governed file with its DB content and removes
        DB-deleted files, making the session base match governed state exactly.
        """
        from core.file_operations import get_file_content_from_db

        try:
            with get_db_connection() as conn:
                rows = conn.execute("SELECT file_path, is_deleted FROM files WHERE has_been_written_to_disk = 1").fetchall()
        except Exception as e:
            print(f"   ⚠️ Shell developer: could not read governed state for base sync: {e}")
            return 0

        base = self.working_dir()
        synced = removed = failed = 0
        for file_path, is_deleted in rows:
            rel = str(file_path)
            if is_deleted:
                target = base / rel
                if target.exists():
                    try:
                        target.unlink()
                        removed += 1
                    except OSError:
                        failed += 1
                continue
            content = get_file_content_from_db(rel)
            if content is None:
                continue
            target = base / rel
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
                synced += 1
            except OSError:
                failed += 1
        if synced or removed or failed:
            print(f"   🔄 Governed base sync: {synced} written, {removed} removed, {failed} failed")
        return synced

    def working_dir(self) -> Path:
        assert self.path is not None
        return self.path / self._sub_rel if str(self._sub_rel) != "." else self.path

    def run_command(self, command: str, timeout: int) -> tuple[int, str]:
        """Run one agent bash command inside the worktree working directory."""
        if is_banned_write_command(command):
            return (
                78,
                "banned write path: python -c / base64-exec is not allowed. "
                "Use the edit primitive (OLD/NEW or mode=full on a file under "
                f"{FULL_REPLACE_MAX_LINES} lines) or a closed sed/python rewrite "
                "of a bounded hunk.",
            )
        try:
            proc = subprocess.run(
                command,
                shell=True,
                cwd=str(self.working_dir()),
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )
            out = ((proc.stdout or "") + (proc.stderr or "")).strip()
            return proc.returncode, out
        except subprocess.TimeoutExpired:
            return 124, f"[command timed out after {timeout}s]"
        except Exception as e:  # report any execution failure to the model
            return 1, f"[command execution error: {e}]"

    def run_test_command(self, command: str, timeout: int) -> tuple[int, str]:
        argv = shlex.split(command)
        try:
            proc = subprocess.run(
                argv,
                cwd=str(self.working_dir()),
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )
            out = ((proc.stdout or "") + (proc.stderr or "")).strip()
            return proc.returncode, out
        except subprocess.TimeoutExpired:
            return 124, f"[test command timed out after {timeout}s]"
        except FileNotFoundError:
            return 127, f"[test command not found: {argv[0] if argv else command}]"

    def collect_changes(self) -> list[dict[str, Any]]:
        """Return [{path, status, new_content, diff}] for tracked+untracked changes.

        Paths are relative to the project directory (repo subdirectory aware).
        Changes are collected against the post-sync baseline tree (falling back to
        HEAD when no baseline was recorded), so only agent-authored work is
        reported. Deleted files are reported and mapped to the governed
        delete_file operation at proposal time.
        """
        assert self.path is not None
        add = self._git("add", "-A", cwd=self.path)
        if add.returncode != 0:
            raise RuntimeError(f"failed to stage worktree changes: {add.stderr.strip()}")

        base = self._baseline_tree or "HEAD"
        status = self._git("diff", "--cached", "--name-status", "-z", base, cwd=self.path)
        if status.returncode != 0:
            raise RuntimeError(f"failed to diff worktree: {status.stderr.strip()}")

        tokens = [t for t in status.stdout.split("\0") if t]
        changes: list[dict[str, Any]] = []
        i = 0
        while i < len(tokens):
            entry = tokens[i]
            code = entry[0] if entry else "M"
            src = tokens[i + 1] if i + 1 < len(tokens) else ""
            i += 2
            # For renames (R), content and diff live at the destination path.
            effective = src
            if code.startswith("R"):
                effective = tokens[i] if i < len(tokens) else src
                i += 1
            if not effective:
                continue

            rel = self._strip_sub(effective)
            if rel is None:
                print(f"   ⚠️ Skipping change outside the project directory ({self.project_directory}): {effective}")
                continue

            item: dict[str, Any] = {"path": rel, "status": "A" if code.startswith("R") else code, "new_content": "", "diff": ""}
            if item["status"] == "D":
                changes.append(item)
                continue
            if item["status"] in ("A", "M"):
                target = self.path / effective
                try:
                    raw = target.read_bytes()
                    if len(raw) > self.max_file_bytes:
                        print(f"   ⚠️ Skipping oversize file ({len(raw)} bytes > {self.max_file_bytes}): {rel}")
                        changes.append({**item, "status": "S"})
                        continue
                    item["new_content"] = raw.decode("utf-8", errors="replace")
                    diff_p = self._git("diff", "--cached", base, "--", effective, cwd=self.path)
                    item["diff"] = (diff_p.stdout or "")[:48_000]
                except OSError:
                    changes.append({**item, "status": "S"})
                    continue
                changes.append(item)
        return changes

    def change_state_since_baseline(self, paths: list[str] | None = None) -> tuple[list[str], str]:
        """(name-status lines, capped unified diff) for agent changes since baseline.

        Stages the worktree (like collect_changes) and diffs the index against
        the recorded baseline tree, so only agent-authored work is reported.
        Used for the observation change-state feed and the stall tripwire.
        Any failure (including test doubles without a real git binary) is
        treated as "no reportable changes".
        """
        assert self.path is not None
        try:
            add = self._git("add", "-A", cwd=self.path)
            if add.returncode != 0:
                return [], ""
            base = self._baseline_tree or "HEAD"
            if paths:
                st = self._git("diff", "--cached", "--name-status", base, "--", *paths, cwd=self.path)
                diff = self._git("diff", "--cached", base, "--", *paths, cwd=self.path)
            else:
                st = self._git("diff", "--cached", "--name-status", base, cwd=self.path)
                diff = self._git("diff", "--cached", base, cwd=self.path)
            lines = [line for line in st.stdout.splitlines() if line.strip()]
            dtext = (diff.stdout or "")[:4000] if diff.returncode == 0 else ""
            return lines, dtext
        except Exception:
            return [], ""

    def _strip_sub(self, repo_relative: str) -> str | None:
        if str(self._sub_rel) == ".":
            return repo_relative
        prefix = self._sub_rel.as_posix() + "/"
        if repo_relative.startswith(prefix):
            return repo_relative[len(prefix) :]
        if repo_relative == self._sub_rel.as_posix():
            return repo_relative
        return None  # change outside the configured project directory

    def cleanup(self) -> None:
        if not self._added or self.path is None:
            return
        try:
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(self.path)],
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                timeout=60,
            )
        finally:
            subprocess.run(
                ["git", "worktree", "prune"],
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                timeout=30,
            )
        self._added = False


# =========================================================================
# Session loop (mini-swe-agent style query/execute cycle)
# =========================================================================
@dataclass
class SessionResult:
    exit_status: str = ""
    summary: str = ""
    n_model_calls: int = 0
    test_exit_code: int | None = None
    test_output: str = ""
    messages: list[dict] = field(default_factory=list)
    # Soak10 follow-up: transport-level LLM call accounting (including internal
    # retries) so the trajectory can say how many calls FAILED and why.
    llm_attempts: int = 0
    llm_failure_kinds: dict[str, int] = field(default_factory=dict)
    last_llm_failure: dict[str, Any] | None = None
    evidence_ran: bool = False
    evidence_ok: bool = False
    evidence: dict[str, Any] = field(default_factory=dict)
    commands_executed: int = 0
    target_inspected: bool = False
    # Soak6 mutate/inspect split: inspection commands run against
    # INSPECT_STEP_CAP (they do NOT burn step_limit); every other executed
    # step counts against the mutate budget.
    mutate_calls: int = 0
    inspect_calls: int = 0
    # Seed-resolved task target (populated by run()); surfaced on the mutation
    # result so a failed shell turn's fallback can name this file.
    target_path: str | None = None


# Failure kinds that a bounded backoff+retry cannot fix — give up immediately
# instead of burning retries (mirrors call_endpoint's own handling).
PERMANENT_FAILURE_KINDS = {"key_locked", "unauthorized", "token_exhausted", "bad_payload", "misconfig"}


def _recent_failure_kind(model_ref: str | None, max_age_s: int = 30) -> str:
    """Return the failure kind the most recent model-health event recorded for
    a model reference (or "" if none). call_endpoint writes every failure
    synchronously before returning None, so this classifies the None instead of
    guessing whether it was rate-limiting, a latch, or a token budget."""
    _kind, _detail = _recent_failure(model_ref, max_age_s)
    return _kind


def _recent_failure_detail(model_ref: str | None, max_age_s: int = 30) -> str:
    """Return the body-excerpt detail the most recent model-health failure
    recorded for a model reference (or "" if none). call_endpoint stores the
    dumped body here, so prefer it over a stub (PR #122 review)."""
    _kind, detail = _recent_failure(model_ref, max_age_s)
    return detail


def _recent_failure(model_ref: str | None, max_age_s: int = 30) -> tuple[str, str]:
    """Shared read of the latest ok=0 model-health row: (kind, detail)."""
    if not model_ref:
        return "", ""
    try:
        with get_db_connection() as conn:
            cutoff = (datetime.now() - timedelta(seconds=max_age_s)).isoformat(timespec="seconds")
            row = conn.execute(
                "SELECT kind, detail FROM model_health_events WHERE model_ref = ? AND ok = 0 AND ts >= ? ORDER BY ts DESC LIMIT 1",
                (model_ref, cutoff),
            ).fetchone()
            if not row:
                return "", ""
            return str(row[0] or ""), str(row[1] or "")
    except Exception:
        return "", ""


class ShellDeveloperSession:
    def __init__(
        self,
        config: ShellDeveloperConfig,
        worktree: ShellWorktree,
        task_id: str,
    ):
        self.cfg = config
        self.wt = worktree
        self.task_id = task_id
        self.messages: list[dict] = []
        self.result = SessionResult()
        self._start = time.time()
        self._deferred_finish_count = 0
        self.target_path: str | None = None
        # Soak17 §11.1: generic discovery hint injected into the prompt when a
        # seed names no existing file (exploratory downgrade), else "".
        self.discovery_note: str = ""
        # Stall tripwire bookkeeping: normalized commands already executed and
        # the current no-change streak. A step counts toward the streak only
        # when the worktree is unchanged AND the command repeated an already
        # executed command OR exited non-zero.
        self._executed_command_counts: dict[str, int] = {}
        self._no_change_steps = 0
        self._no_progress_steps = 0
        self._last_fed_change_key: frozenset[str] = frozenset()
        # Chat-JSON-table protocol: executed steps (append-only) and whether the
        # session drives the model with a JSON step table instead of bash fences.
        self.steps: list[dict[str, Any]] = []
        self.chat_mode = False
        # Resolved model ref ("endpoint/model") actually used for LLM calls;
        # set on the first _llm call (cfg.model may be None).
        self.resolved_model: str | None = None

    def _resolve_developer_model(self) -> str | None:
        """Resolve the model for this session exactly like call_agent does
        (agents/base.py:819-856): explicit override > resource-controller
        throttle override > agent_model_preferences. Unknown overrides are
        ignored rather than trusted blindly, so the shell session rides the
        same model the other agents are currently using (Soak10 follow-up)."""
        from core.endpoint_manager import get_endpoint_manager

        endpoint_mgr = get_endpoint_manager()
        override = self.cfg.model
        if not override:
            try:
                from agents.resource_controller_worker import get_resource_controller

                rc_override = get_resource_controller().get_model_override("developer")
                if rc_override:
                    override = rc_override
                    print(f"  🎛️  Resource controller: using {rc_override} for developer shell")
            except Exception as e:
                print(f"  ⚠️  Resource controller model override check failed: {e}")

        if override and not endpoint_mgr.model_reference_exists(override):
            print(f"  ⚠️  Ignoring unknown model override {override!r} for developer shell; using configured preference")
            override = None

        choice = endpoint_mgr.normalize_model_reference(override) if override else endpoint_mgr.resolve_agent_model("developer")
        if choice.endpoint_name and choice.model_name:
            return f"{choice.endpoint_name}/{choice.model_name}"
        return choice.model_name

    def _llm(self) -> str | None:
        """Call the LLM with bounded, failure-kind-aware retries (Soak10 follow-up).

        call_endpoint already retries per-endpoint and falls back across
        endpoints; this layer adds a session-level retry so a single transient
        failure (rate-limit / 5xx / timeout / health latch) cannot kill the
        session. The kind recorded in model_health_events decides whether a
        short backoff + retry is worthwhile; permanent kinds (bad key, ...)
        give up immediately. token_budget is endpoint-local: retry while any
        reachable endpoint still has 4h room. The model is re-resolved between
        attempts so retries follow the resource-controller's current steering.
        """
        for attempt in range(self.cfg.llm_failure_max_retries + 1):
            model_ref = self._resolve_developer_model() or self.cfg.model
            self.resolved_model = model_ref
            text, _tokens = call_endpoint(
                self.messages,
                task_id=self.task_id,
                agent_name="developer",
                model=model_ref,
            )
            self.result.llm_attempts += 1
            if text:
                return text
            kind = _recent_failure_kind(model_ref) or "unknown"
            if kind == "unknown":
                excerpt = _recent_failure_detail(model_ref) or "(empty or unparsed body)"
                print(f"   ⚠️  Empty/policy LLM body from {model_ref}: {excerpt}")
                record_model_outcome(model_ref, ok=False, kind="unknown", detail=excerpt)
                self.result.last_llm_failure = {
                    "kind": kind,
                    "model_ref": model_ref,
                    "attempt": attempt + 1,
                    "body_excerpt": excerpt,
                }
            self.result.llm_failure_kinds[kind] = self.result.llm_failure_kinds.get(kind, 0) + 1
            if self.result.last_llm_failure is None or self.result.last_llm_failure.get("attempt") != attempt + 1:
                self.result.last_llm_failure = {"kind": kind, "model_ref": model_ref, "attempt": attempt + 1}
            if kind in PERMANENT_FAILURE_KINDS or attempt >= self.cfg.llm_failure_max_retries:
                break
            if kind == "token_budget":
                # Endpoint-local: give up only when every reachable bucket is dead.
                from agents.base import any_token_budget_remaining

                if not any_token_budget_remaining(1):
                    break
            backoff_s = max(int(self.cfg.llm_retry_backoff_seconds) * (attempt + 1), 1)
            print(f"   ⏳ Shell developer LLM failure ({kind}); backing off {backoff_s}s (attempt {attempt + 1}/{self.cfg.llm_failure_max_retries + 1})")
            time.sleep(backoff_s)
        return None

    def _observation(self, exit_code: int, output: str, command: str | None = None, thought: str | None = None) -> dict:
        trimmed = output
        if len(trimmed) > self.cfg.max_output_chars:
            cut = len(trimmed) - self.cfg.max_output_chars
            trimmed = f"...[{cut} chars truncated]...\n{trimmed[-self.cfg.max_output_chars :]}"
        change_lines, dtext = _worktree_change_state(self.wt)
        pairs = _parse_name_status(change_lines)
        new_key = frozenset(path for _code, path in pairs)
        newly_changed = sorted(new_key - self._last_fed_change_key)
        self._last_fed_change_key = new_key
        if self.chat_mode:
            row: dict[str, Any] = {
                "step": len(self.steps) + 1,
                "thought": thought,
                "command": command,
                "exit_code": exit_code,
                "output": trimmed,
            }
            if change_lines:
                row["changed"] = [path for _code, path in pairs]
            if newly_changed and dtext:
                row["diff"] = dtext[-4000:]
            self.steps.append(row)
            table = json.dumps(self.steps, indent=2)
            content = f"```json\n{table}\n```\n\nOutput the JSON object for the next step (step {len(self.steps) + 1}) awaiting execution:"
            return {"role": "user", "content": content}
        body = ""
        if command:
            body += f"$ {command}\n"
        body += trimmed
        if change_lines:
            body += "\n\n[worktree changes since baseline]\n" + "\n".join(change_lines)
        if newly_changed and dtext:
            body += f"\n\n[diff for newly changed paths (capped)]\n{dtext}"
        if body.strip():
            return {"role": "user", "content": f"[exit code {exit_code}]\n{body}"}
        return {"role": "user", "content": f"[exit code {exit_code}, no output]"}

    def _record_step(
        self,
        *,
        response: str,
        command: str | None,
        command_exit_code: int | None,
        response_format_status: str | None,
        step_number: int,
        error_reason: str | None = None,
    ) -> None:
        """Archive one shell developer step for observability (Pass 1 Phase 3.1)."""
        prompt = ""
        for message in reversed(self.messages):
            if message.get("role") == "user":
                prompt = message.get("content", "") or ""
                break
        valid = response_format_status in (
            shell_protocol.VALID_BASH_BLOCK,
            shell_protocol.VALID_EDIT_BLOCK,
            shell_protocol.VALID_FINISH_SESSION,
        )
        try:
            archive_raw_response(
                task_id=self.task_id,
                agent_name="developer",
                prompt=str(prompt)[-4000:],
                response=str(response)[-8000:],
                parse_success=valid,
                parse_error=error_reason,
                model=self.resolved_model,
                step_number=step_number,
                response_format_status=response_format_status,
                command=command if command_exit_code is not None else None,
                command_exit_code=command_exit_code,
            )
            if command is not None and command_exit_code is not None:
                _publish_shell_event(
                    "shell_command_executed",
                    task_id=self.task_id,
                    payload={
                        "step_number": step_number,
                        "command": command,
                        "exit_code": command_exit_code,
                        "format": response_format_status,
                    },
                )
        except Exception as e:
            print(f"   ⚠️  Shell step archival skipped: {e}")

    def _emit_command_failed_if_needed(self, exit_code: int, command: str, step_number: int) -> None:
        if exit_code != 0:
            _publish_shell_event(
                "shell_command_failed",
                task_id=self.task_id,
                payload={"command": command, "exit_code": exit_code, "step_number": step_number},
            )

    def _record_model_health(self, *, ok: bool, kind: str) -> None:
        """Record one shell-session model-health outcome (never raises)."""
        try:
            record_model_outcome(self.resolved_model, ok=ok, kind=kind)
        except Exception as e:
            print(f"   ⚠️  Model-health record skipped: {e}")

    def _effective_command_timeout(self) -> int:
        """Cap one bash command by the remaining wall-clock budget.

        Limits are otherwise only checked before each LLM call; without this a
        single long command could blow past wall_time_limit_minutes.
        """
        timeout = self.cfg.command_timeout_seconds
        if self.cfg.wall_time_limit_minutes > 0:
            remaining_s = int(self.cfg.wall_time_limit_minutes * 60 - (time.time() - self._start))
            if remaining_s < timeout:
                return max(remaining_s, 1)
        return timeout

    def _run_worktree_command(self, command: str) -> tuple[int, str]:
        """Run a bash command in the worktree and count it as an executed command."""
        exit_code, output = self.wt.run_command(command, self._effective_command_timeout())
        self.result.commands_executed += 1
        return exit_code, output

    def _guard_step_limits(self, command: str | None) -> bool:
        """Count one executed model step and enforce the Soak6 budget split.

        Inspection commands (`sed -n`, `grep`, `ls`, git log/diff/status, ...)
        run against INSPECT_STEP_CAP; everything else (edits, writes, python)
        burns the `step_limit` mutate budget. Returns True when a limit was
        reached and the session should break.
        """
        r = self.result
        if command is not None and is_inspect_command(command):
            r.inspect_calls += 1
        else:
            r.mutate_calls += 1
        if self.cfg.step_limit > 0 and r.mutate_calls >= self.cfg.step_limit:
            r.exit_status = "LimitsExceeded"
            r.summary = f"mutate step limit ({self.cfg.step_limit}) reached"
            return True
        if r.inspect_calls >= INSPECT_STEP_CAP:
            r.exit_status = "LimitsExceeded"
            r.summary = f"inspect step cap ({INSPECT_STEP_CAP}) reached"
            return True
        return False

    def _apply_edit_payload(self, payload: dict[str, Any]) -> tuple[int, str]:
        """Apply a structured edit payload to the worktree in-process (no shell).

        Returns (0, message) on success or (1, message) on failure. OLD-not-found
        includes a head excerpt so the model can resend exact content.
        """
        full = _safe_edit_target(str(self.wt.working_dir()), str(payload.get("path") or ""))
        path = payload.get("path") or ""
        if full is None:
            return 1, f"edit target path is invalid (must be relative and inside the worktree): {path!r}"
        try:
            content = full.read_text(encoding="utf-8")
        except FileNotFoundError:
            return 1, f"edit target does not exist: {path}"
        except OSError as e:
            return 1, f"cannot read edit target {path}: {e}"
        new_text = str(payload.get("new") or "")
        if str(payload.get("mode") or "").lower() in ("full", "content"):
            try:
                full.write_text(new_text, encoding="utf-8")
            except OSError as e:
                return 1, f"cannot write edit target {path}: {e}"
            self.result.commands_executed += 1
            return 0, f"replaced {path} with {len(new_text)} chars"
        old_text = str(payload.get("old") or "")
        if not old_text:
            return 1, f"edit {path} is missing the OLD section (or OLD is empty); resend with exact current content"
        count = content.count(old_text)
        if count == 0:
            head = content[:600]
            return 1, f"edit OLD section not found in {path} (0 matches). Current file head:\n{head}"
        if count > 1:
            return 1, f"edit OLD section is ambiguous in {path}: matched {count} occurrences (need exactly 1)"
        try:
            full.write_text(content.replace(old_text, new_text, 1), encoding="utf-8")
        except OSError as e:
            return 1, f"cannot write edit target {path}: {e}"
        self.result.commands_executed += 1
        return 0, f"applied edit to {path}"

    def _normalize_stall_key(self, action: str) -> str:
        return " ".join(action.split())

    def _note_step_outcome(self, exit_code: int, action: str) -> bool:
        """Tripwire bookkeeping for one executed step. Returns True only when a
        tripwire fires with the tree unchanged:
        - no_change_stall_limit: the step repeated an already-executed action or
          exited non-zero (repeated/failing no-change steps);
        - no_progress_stall_limit: ANY no-change step, novel or not, so a
          discovery loop circling the tree with fresh greps also terminates
          instead of burning to the step limit (Soak18).
        Any worktree change resets both streaks."""
        if self.cfg.no_change_stall_limit <= 0 and self.cfg.no_progress_stall_limit <= 0:
            return False
        change_lines, _dtext = _worktree_change_state(self.wt)
        if change_lines:
            self._no_change_steps = 0
            self._no_progress_steps = 0
            return False
        key = self._normalize_stall_key(action)
        self._executed_command_counts[key] = self._executed_command_counts.get(key, 0) + 1
        repeated = self._executed_command_counts[key] > 1
        if repeated or exit_code != 0:
            self._no_change_steps += 1
            if self.cfg.no_change_stall_limit > 0 and self._no_change_steps >= self.cfg.no_change_stall_limit:
                return True
        if self.cfg.no_progress_stall_limit > 0:
            self._no_progress_steps += 1
            if self._no_progress_steps >= self.cfg.no_progress_stall_limit:
                return True
        return False

    def _mark_stalled(self, action: str, step_number: int) -> None:
        r = self.result
        if self._no_progress_steps >= self.cfg.no_progress_stall_limit and self.cfg.no_progress_stall_limit > 0:
            r.exit_status = "NoProgress"
            r.summary = (
                f"no tree change or edit across {self._no_progress_steps} consecutive steps "
                f"(no_progress_stall_limit={self.cfg.no_progress_stall_limit}) around action {action!r} — stopping"
            )
            _publish_shell_event(
                "shell_spinning",
                task_id=self.task_id,
                payload={
                    "action": action,
                    "step_number": step_number,
                    "no_progress_steps": self._no_progress_steps,
                },
            )
            print(f"   ⏹ {r.summary}")
            return
        r.exit_status = "Stalled"
        r.summary = (
            f"stalled after {self._no_change_steps} consecutive no-change steps "
            f"(no_change_stall_limit={self.cfg.no_change_stall_limit}) around repeatedly executed/failing action {action!r}"
        )
        _publish_shell_event(
            "shell_stalled",
            task_id=self.task_id,
            payload={"action": action, "step_number": step_number, "no_change_steps": self._no_change_steps},
        )
        print(f"   ❌ {r.summary}")

    def _run_in_process_evidence(self) -> bool:
        """Execute workspace evidence before any LLM call. Returns False on abort."""
        r = self.result
        marker = self.cfg.workspace_marker
        cmd = evidence_command(marker)
        try:
            exit_code, output = self.wt.run_command(cmd, self._effective_command_timeout())
        except Exception as e:
            exit_code, output = 1, str(e)
        try:
            cwd = str(self.wt.working_dir())
        except Exception:
            cwd = ""
        evidence = parse_evidence_output(output, exit_code, marker, cwd=cwd)
        r.evidence = evidence
        r.evidence_ran = True
        if exit_code == 0 and evidence.get("marker_found"):
            r.evidence_ok = True
            return True
        r.exit_status = "WorkspaceValidationFailed"
        r.summary = f"shell developer workspace validation failed: expected {marker} under project root but it was not found"
        print(f"   ❌ {r.summary}")
        _publish_shell_event(
            "shell_workspace_validation_failed",
            task_id=self.task_id,
            payload=evidence,
        )
        return False

    def _mark_target_inspected(self, command: str | None) -> None:
        if not command or is_evidence_command(command):
            return
        if self.target_path is None or command_touches_target(command, self.target_path):
            self.result.target_inspected = True

    def _reject_finish(self, response: str, reason: str) -> None:
        self.messages.append({"role": "user", "content": reason})
        self._record_step(
            response=response,
            command=None,
            command_exit_code=None,
            response_format_status=shell_protocol.VALID_FINISH_SESSION,
            step_number=self.result.n_model_calls,
        )

    def run(self, task_text: str) -> SessionResult:  # noqa: C901
        r = self.result
        r.messages = self.messages
        resolved = self._resolve_developer_model() or self.cfg.model
        self.chat_mode = _chat_table_mode(self.cfg, resolved)
        if not self._run_in_process_evidence():
            return r
        self.target_path = resolve_seed_target_path(task_text, self.wt, self.cfg.workspace_marker)
        named = _seed_path_candidates(task_text)
        try:
            root = Path(self.wt.working_dir())
        except Exception:
            root = None
        if named and root is not None and root.is_dir() and self.target_path is None and _path_like_seed_candidate(named[0]):
            # Soak17 §11.1: a seed that resolves to no existing file must not
            # hard-abort the session. Downgrade to an exploration session with a
            # generic discovery hint and raise a target_missing event. The
            # target_path stays None so _mark_target_inspected rewards any
            # inspection command.
            self.discovery_note = _discovery_glob_note(named[0])
            r.summary = f"target missing after evidence: {named[0]} (downgraded to exploration)"
            print(f"   🔭 {r.summary}")
            _publish_shell_event(
                "shell_target_missing",
                task_id=self.task_id,
                payload={**r.evidence, "reason": "target_missing", "target": named[0]},
            )
            self.cfg.fiability = "exploratory"
            if 0 < self.cfg.explore_step_cap < self.cfg.step_limit:
                self.cfg.step_limit = self.cfg.explore_step_cap
        # Seed the JSON step table with the in-process evidence step (chat mode).
        if self.chat_mode:
            excerpt = (r.evidence.get("output_excerpt") or "").strip()
            self.steps.append(
                {
                    "step": 1,
                    "thought": "Workspace validation (evidence)",
                    "command": evidence_command(self.cfg.workspace_marker),
                    "exit_code": 0,
                    "output": excerpt,
                }
            )
        if self.chat_mode:
            self.messages.append({"role": "system", "content": CHAT_SYSTEM_PROMPT})
            self.messages.append(
                {
                    "role": "user",
                    "content": build_chat_prompt(
                        task_text,
                        r.evidence,
                        self.target_path,
                        self.steps,
                        explore_note=self.cfg.fiability == "exploratory",
                        discovery_note=self.discovery_note,
                    ),
                }
            )
        else:
            self.messages.append({"role": "system", "content": SYSTEM_PROMPT.format(finish_token=FINISH_TOKEN)})
            self.messages.append(
                {
                    "role": "user",
                    "content": build_inspect_prompt(
                        task_text,
                        r.evidence,
                        self.target_path,
                        explore_note=self.cfg.fiability == "exploratory",
                        discovery_note=self.discovery_note,
                    ),
                }
            )

        consecutive_format_errors = 0
        while True:
            elapsed_min = (time.time() - self._start) / 60
            if self.cfg.wall_time_limit_minutes > 0 and elapsed_min >= self.cfg.wall_time_limit_minutes:
                r.exit_status = "TimeExceeded"
                r.summary = f"wall-clock limit ({self.cfg.wall_time_limit_minutes}m) reached"
                break
            # Hard model-call safety ceiling (mutate budget + inspect cap). The
            # real budget split is enforced per-step in _guard_step_limits; this
            # only bounds pathological loops that never run a command.
            if self.cfg.step_limit > 0 and r.n_model_calls >= self.cfg.step_limit + INSPECT_STEP_CAP:
                r.exit_status = "LimitsExceeded"
                r.summary = f"model-call safety ceiling ({self.cfg.step_limit + INSPECT_STEP_CAP}) reached"
                break

            # Operator console heartbeats (read view): a turn begins and the
            # model call is awaited; _record_step later closes the loop with
            # shell_command_executed. These are append-only and non-mutating.
            hb_step = r.n_model_calls + 1
            _publish_shell_event(
                "shell_turn_start",
                task_id=self.task_id,
                payload={"step_number": hb_step, "model_ref": self.resolved_model},
            )
            _publish_shell_event(
                "shell_model_call_started",
                task_id=self.task_id,
                payload={"step_number": hb_step, "model_ref": self.resolved_model},
            )
            response = self._llm()
            r.n_model_calls += 1
            if not response:
                r.exit_status = "LlmUnavailable"
                if r.last_llm_failure:
                    r.summary = (
                        "LLM endpoint unavailable after "
                        f"{r.last_llm_failure['attempt']} attempt(s) "
                        f"(kind={r.last_llm_failure['kind']}, model={r.last_llm_failure.get('model_ref')})"
                    )
                else:
                    r.summary = "LLM endpoint unavailable or token budget exhausted"
                break
            self.messages.append({"role": "assistant", "content": response})

            summary = extract_finish(response)
            command = extract_bash_command(response)
            edit = shell_protocol.extract_edit_payload(response)

            is_protocol_valid = command is not None or summary is not None or edit is not None
            self._record_model_health(ok=is_protocol_valid, kind="protocol_valid" if is_protocol_valid else "protocol_invalid")

            if edit is not None:
                # In-worktree edit primitive (Soak16 feed fix): applied by the
                # harness directly to the file, so edits never depend on shell
                # quoting. Takes priority over any co-present bash command.
                action = f"```edit {edit['path'] if edit.get('path') else '?'}```"
                exit_code, output = self._apply_edit_payload(edit)
                self.result.target_inspected = True
                self._record_model_health(ok=True, kind="command_executed")
                self._record_model_health(ok=exit_code == 0, kind="command_success")
                self._record_step(
                    response=response,
                    command=action,
                    command_exit_code=exit_code,
                    response_format_status=shell_protocol.VALID_EDIT_BLOCK,
                    step_number=r.n_model_calls,
                )
                user_msg = self._observation(exit_code, output, action, None)
                self.messages.append(user_msg)
                self._emit_command_failed_if_needed(exit_code, action, r.n_model_calls)
                if self._guard_step_limits(None):
                    break
                if self._note_step_outcome(exit_code, action):
                    self._mark_stalled(action, r.n_model_calls)
                    break
                continue

            if summary is not None and command is not None:
                # The model tried to run a final command AND finish in one reply
                # (e.g. "run tests, then FINISH"). Since verification depends on the
                # worktree state the command produces, execute it first and defer the
                # finish; force-finish if the model keeps pairing them.
                self._deferred_finish_count += 1
                exit_code, output = self._run_worktree_command(command)
                action = shell_protocol.extract_chat_table_action(response)
                self.messages.append(self._observation(exit_code, output, command, (action or {}).get("thought")))
                self._emit_command_failed_if_needed(exit_code, command, r.n_model_calls)
                self._record_model_health(ok=True, kind="command_executed")
                self._record_model_health(ok=exit_code == 0, kind="command_success")
                self._record_step(
                    response=response,
                    command=command,
                    command_exit_code=exit_code,
                    response_format_status=shell_protocol.VALID_BASH_BLOCK,
                    step_number=r.n_model_calls,
                )
                self._mark_target_inspected(command)
                if self._guard_step_limits(command):
                    break
                if self._note_step_outcome(exit_code, command):
                    self._mark_stalled(command, r.n_model_calls)
                    break
                if self._deferred_finish_count >= 3 and r.target_inspected and not finish_claims_no_shell(summary):
                    r.exit_status = "Finished"
                    r.summary = f"[finish forced after {self._deferred_finish_count} deferred finishes] {summary}"
                    break
                self.messages.append(
                    {
                        "role": "user",
                        "content": (
                            "Your previous reply contained both a bash command and a finish decision. "
                            "The command has been executed (result above). If the task is now complete, "
                            'reply with the JSON finish object ({... "command": null, "finish": true}).'
                            if self.chat_mode
                            else f"Your previous reply contained both a bash command and {FINISH_TOKEN}. "
                            "The command has been executed (result above). If the task is now "
                            f"complete, reply again with only {FINISH_TOKEN} and a summary."
                        ),
                    }
                )
                continue

            if summary is not None:
                if not r.target_inspected:
                    target = self.target_path or "the target file"
                    reason = (
                        "The finish decision is not allowed until one non-evidence command against "
                        f"{target} has run. Emit a JSON step object with a command that inspects it."
                        if self.chat_mode
                        else f"{FINISH_TOKEN} is not allowed until one non-evidence command against {target} has run."
                    )
                    self._reject_finish(response, reason)
                    continue
                if finish_claims_no_shell(summary):
                    _publish_shell_event(
                        "shell_session_no_mutation",
                        task_id=self.task_id,
                        payload={"reason": "finish_denies_shell", "step_number": r.n_model_calls},
                    )
                    target = self.target_path or "the target file"
                    reason = (
                        f"The finish summary cannot claim there is no shell after evidence ran. Inspect {target}."
                        if self.chat_mode
                        else f"{FINISH_TOKEN} after evidence cannot claim there is no shell. Inspect {target}."
                    )
                    self._reject_finish(response, reason)
                    continue
                r.exit_status = "Finished"
                r.summary = summary
                self._record_step(
                    response=response,
                    command=None,
                    command_exit_code=None,
                    response_format_status=shell_protocol.VALID_FINISH_SESSION,
                    step_number=r.n_model_calls,
                )
                break

            if command is None:
                consecutive_format_errors += 1
                diag = shell_protocol.diagnose_shell_reply(response)
                print(f"   ⚠️  Shell protocol (reason={diag['reason']})")
                event_type = {
                    "prose_or_unsupported_format": "shell_protocol_prose_response",
                    "unterminated_bash_fence": "shell_protocol_unterminated_fence",
                    "finish_token_inside_command_block": "shell_protocol_invalid_finish",
                }.get(diag["reason"], "shell_protocol_prose_response")
                _publish_shell_event(
                    event_type,
                    task_id=self.task_id,
                    payload={"reason": diag["reason"], "step_number": r.n_model_calls},
                )
                self._record_step(
                    response=response,
                    command=None,
                    command_exit_code=None,
                    response_format_status=shell_protocol.classify_shell_reply(response),
                    step_number=r.n_model_calls,
                    error_reason=diag["reason"],
                )
                if self.cfg.max_consecutive_format_errors > 0 and consecutive_format_errors >= self.cfg.max_consecutive_format_errors:
                    r.exit_status = "RepeatedFormatError"
                    r.summary = f"no ```bash block or finish token in consecutive replies (reason={diag['reason']})"
                    _publish_shell_event(
                        "shell_protocol_repeated_format_error",
                        task_id=self.task_id,
                        payload={"reason": diag["reason"], "step_number": r.n_model_calls},
                    )
                    break
                expected = "the JSON step-table object {thought, step, command, edit, finish, summary}" if self.chat_mode else diag["expected"]
                must_msg = (
                    "reply must contain the JSON step-table object for the next step"
                    if self.chat_mode
                    else f"reply must contain either a single ```bash fenced command or the token {FINISH_TOKEN} with a summary"
                )
                self.messages.append(
                    {
                        "role": "user",
                        "content": (f"FormatError (reason={diag['reason']}): {must_msg}. Expected: {expected}."),
                    }
                )
                continue

            consecutive_format_errors = 0
            exit_code, output = self._run_worktree_command(command)
            self._mark_target_inspected(command)
            action = shell_protocol.extract_chat_table_action(response)
            self.messages.append(self._observation(exit_code, output, command, (action or {}).get("thought")))
            self._emit_command_failed_if_needed(exit_code, command, r.n_model_calls)
            self._record_model_health(ok=True, kind="command_executed")
            self._record_model_health(ok=exit_code == 0, kind="command_success")
            self._record_step(
                response=response,
                command=command,
                command_exit_code=exit_code,
                response_format_status=shell_protocol.classify_shell_reply(response),
                step_number=r.n_model_calls,
            )
            if self._guard_step_limits(command):
                break
            if self._note_step_outcome(exit_code, command):
                self._mark_stalled(command, r.n_model_calls)
                break

        # Optional post-session verification against the edited worktree.
        if r.exit_status == "Finished" and self.cfg.test_command:
            code, output = self.wt.run_test_command(self.cfg.test_command, self.cfg.test_timeout_seconds)
            r.test_exit_code = code
            r.test_output = output[-self.cfg.max_output_chars :]
        self._record_model_health(ok=r.exit_status == "Finished", kind="session_outcome")
        return r

    def serialize(self) -> dict:
        last = self.messages[-1] if self.messages else {}
        failed_calls = sum(self.result.llm_failure_kinds.values())
        return {
            "trajectory_format": "prizmforge-shell-developer-1.0",
            "exit_status": self.result.exit_status,
            "submission_summary": self.result.summary,
            "model_stats": {
                "api_calls": self.result.llm_attempts or self.result.n_model_calls,
                "llm_attempts": self.result.llm_attempts,
                "resolved_model": self.resolved_model,
                "successful_calls": max(self.result.llm_attempts - failed_calls, 0),
                "failed_calls": failed_calls,
                "failure_kinds": dict(self.result.llm_failure_kinds),
            },
            "last_llm_failure": self.result.last_llm_failure,
            "workspace_evidence": dict(self.result.evidence),
            "commands_executed": self.result.commands_executed,
            "verification": {
                "test_command": self.cfg.test_command,
                "test_exit_code": self.result.test_exit_code,
                "test_output_tail": self.result.test_output[-2000:],
            },
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "messages": self.messages,
            "last_extra": {k: v for k, v in last.items() if k != "content"},
        }


# =========================================================================
# Changes → governed operations
# =========================================================================
def change_to_operation(change: dict[str, Any], *, exit_status: str = "") -> dict | None:
    """Map one collected change into an EditPayload operation dict (or None to skip).

    Soak6: a shell session must never promote an unbounded/truncated whole-file
    replace to the governed reviewer. `M` changes are only promotable when the
    proposed content stays under FULL_REPLACE_MAX_LINES and the diff stays under
    SHELL_PROMOTE_MAX_DIFF_LINES — and a `LimitsExceeded` session is never the
    vehicle for a promotion that just handed the reviewer a cut payload.
    """
    status = change.get("status")
    path = change.get("path", "")
    content = change.get("new_content", "") or ""
    diff_text = change.get("diff", "") or ""
    line_count = content.count("\n") + (1 if content and not content.endswith("\n") else 0)
    diff_lines = sum(1 for ln in diff_text.splitlines() if ln.startswith(("+", "-")) and not ln.startswith(("+++", "---")))

    if status == "A":
        if line_count > FULL_REPLACE_MAX_LINES:
            return None
        return {
            "type": "create_file",
            "target_file_path": path,
            "initial_content": content.splitlines(),
            "rationale": "Create file (shell developer session)",
        }
    if status == "M":
        bounded = line_count <= FULL_REPLACE_MAX_LINES and diff_lines <= SHELL_PROMOTE_MAX_DIFF_LINES
        if exit_status == "LimitsExceeded" and not bounded:
            return None  # drop; do not hand reviewer a huge replace born of a capped session
        if not bounded:
            return None
        return {
            "type": "full_replace",
            "new_content": content,
            "rationale": f"Full replace (shell session, {line_count} lines, {diff_lines} diff lines)",
        }
    if status == "D":
        return {"type": "delete_file", "target_file_path": path, "rationale": "Delete file (shell developer session)"}
    # S / anything else: no governed equivalent — caller warns.
    return None


def _build_rationale(result: SessionResult, change: dict, test_command: str) -> str:
    parts = [f"Shell developer session ({result.exit_status})."]
    if result.summary:
        parts.append(f"Summary: {result.summary[:800]}")
    if result.test_exit_code is not None:
        parts.append(f"Verification `{test_command}` exit={result.test_exit_code}.")
    diff_head = (change.get("diff") or "")[:MAX_RATIONALE_CHARS]
    if diff_head:
        parts.append(f"Diff excerpt:\n{diff_head}")
    rationale = "\n\n".join(parts)
    return rationale[:3197] + "..." if len(rationale) > 3200 else rationale


def _bounded(text: str, cap: int) -> str:
    """Truncate *text* to at most *cap* characters, never splitting a line mid-token.

    When truncating, cut on a newline boundary and append an explicit marker so a
    downstream reviewer can tell the payload is bounded rather than malformed. A
    truncated unified diff cut mid-token (e.g. ``retry_after.same_en``) looks like a
    corrupt edit and causes legitimate changes to be rejected.
    """
    if len(text) <= cap:
        return text
    cut = text[:cap]
    nl = cut.rfind("\n")
    if nl != -1:
        cut = cut[: nl + 1]
    return f"{cut}...\n[TRUNCATED: content exceeds {cap} chars — see the full proposed content section above]"


# =========================================================================
# Reviewer gate + materialization (mirrors workflow/developer_edit.py semantics)
# =========================================================================
def _gate_and_materialize(
    *,
    proposal_id: str,
    payload_dict: dict,
    target_file_path: str,
    diff_text: str,
    result: SessionResult,
    fallback_used: bool,
    task_id: str,
    progress: dict,
    current_turn: int,
) -> str:
    original_content = _read_current_file(target_file_path)

    # Option A: for a full-replace operation the unified diff of the whole file
    # can exceed the prompt budget and be cut mid-token, which makes an otherwise
    # valid edit look corrupt and gets rejected. Instead show the reviewer the
    # complete proposed content next to the (already-complete) original, so it
    # can verify coherence. Other operations keep the unified diff, bounded safely.
    ops = (payload_dict or {}).get("operations") or []
    is_full_replace = len(ops) == 1 and ops[0].get("type") == "full_replace"
    new_content = ops[0].get("new_content", "") if is_full_replace else ""

    # Option B: never split a token mid-word; truncate on a newline boundary and
    # mark the cut explicitly so the reviewer can tell truncated-from-bounded.
    if is_full_replace and new_content:
        proposed_section = (
            "PROPOSED FULL CONTENT (complete replacement)\n"
            "--------------------------------------------------\n"
            f"```python\n{_bounded(new_content, 32_000)}\n```"
        )
    else:
        proposed_section = (
            "PROPOSED UNIFIED DIFF (applied in isolated copy)\n"
            "--------------------------------------------------\n"
            f"{_bounded(diff_text, 8000) or '(no textual diff available — see payload)'}"
        )

    reviewer_prompt = f"""You are the safety gate for a governed code-editing system.

**File under review:** `{target_file_path}`
**Edit source:** shell developer session (verified working copy)
**Fallback used:** {fallback_used}

--------------------------------------------------
ORIGINAL FILE CONTENT (before any change)
--------------------------------------------------
```python
{original_content}
```

--------------------------------------------------
{proposed_section}

--------------------------------------------------
VERIFICATION EVIDENCE
--------------------------------------------------
Exit status: {result.exit_status}
{_test_evidence(result)}

--------------------------------------------------
INSTRUCTIONS
--------------------------------------------------
Decide whether this change is safe and correct to apply.

Respond with ONLY valid JSON in this exact shape:
{{
"decision": "APPROVE" | "REJECT",
"reason": "concise explanation",
"suggestions": ["optional", "list", "of", "improvements"]
}}

Rules:
- REJECT if the change removes large amounts of existing code without clear justification, or introduces obvious errors.
- APPROVE only when the change is coherent and the resulting file would still be valid.
- If the content above is marked [TRUNCATED], treat it as bounded (not corrupt); base your verdict on the full proposed content shown in the same section.
"""

    # Fail closed (shared with developer_edit - see workflow/reviewer_gate.py).
    # Shell-session diffs originate from arbitrary bash execution, so a missing
    # or unparseable verdict must REJECT, never auto-approve. A ``None``
    # transport failure and a semantic REJECT are never retried; only one
    # same-prompt retry is allowed on an empty/unparseable verdict.
    verdict = request_review_verdict(reviewer_prompt, task_id)
    # residual P10: count actual plays (the gate may retry once internally)
    progress["reviewer_calls"] = progress.get("reviewer_calls", 0) + verdict.calls_used
    post_reviewer_suggestions(proposal_id, task_id, verdict.suggestions)

    if verdict.rejected:
        print(f"   ❌ Reviewer rejected proposal {proposal_id}: {verdict.reason}")
        handle_reviewer_rejection(
            proposal_id=proposal_id,
            target_file_path=target_file_path,
            task_id=task_id,
            reason=verdict.reason,
            suggestions=verdict.suggestions,
        )
        return "rejected", verdict.reason

    print(f"   ✅ Reviewer approved proposal {proposal_id}")
    update_proposal_status(proposal_id, "approved")
    publish_event("proposal.approved", source="reviewer", task_id=task_id, proposal_id=proposal_id)
    snapshot_before_apply(proposal_id)
    mat = materialize_proposal(proposal_id)

    from workflow.post_materialize import apply_materialize_outcome

    mat_status = apply_materialize_outcome(mat, task_id=task_id, progress=progress)
    if mat_status == "success":
        progress["last_file_change"] = current_turn
    elif mat_status not in ("success", "git_failed"):
        print(f"   ⚠️  Materialize status: {mat}")
    return mat.get("status", "error"), ""


def _test_evidence(result: SessionResult) -> str:
    if result.test_exit_code is None:
        return "No post-session verification command was configured."
    tail = result.test_output[-1500:]
    return f"Test command exit code: {result.test_exit_code}\nOutput tail:\n{tail}"


def _read_current_file(file_path: str) -> str:
    from core.file_operations import get_file_content_from_db

    return get_file_content_from_db(file_path) or ""


def _gate_and_materialize_changes(
    *,
    changes: list[dict],
    result: SessionResult,
    cfg: ShellDeveloperConfig,
    task_id: str,
    progress: dict,
    current_turn: int,
) -> tuple[list[str], list[str], dict[str, str]]:
    """Change → governed proposal → reviewer gate → materialize.

    Extracted from the turn entry point to keep its branch count under the
    complexity ceiling; each change is proposed, gated, and materialized
    independently so one rejected/error gate cannot block the rest.
    """
    statuses: list[str] = []
    proposal_ids: list[str] = []
    gates_by_path: dict[str, str] = {}
    rejected_reasons: dict[str, str] = {}

    for change in changes:
        op = change_to_operation(change, exit_status=result.exit_status)
        if op is None:
            print(f"   ⚠️ Skipping unsupported change ({change.get('status')}): {change.get('path')}")
            continue

        payload_dict = {
            "target_file_path": change["path"],
            "summary": f"Shell developer edit: {change['path']}",
            "operations": [op],
            "rationale": _build_rationale(result, change, cfg.test_command),
        }
        prop = create_proposal_from_developer_output(
            payload_dict,
            proposed_by_agent_id=1,
            target_file_path=change["path"],
            selected_mode="shell_session",
            fallback_used=False,
            final_mode=op["type"],
            task_id=task_id,
        )
        if prop.get("status") != "success":
            progress["edit_failures"] = progress.get("edit_failures", 0) + 1
            print(f"   ❌ Proposal creation failed for {change['path']}: {prop}")
            continue

        proposal_ids.append(prop["proposal_id"])
        print(f"   📦 Proposal created: {prop['proposal_id']} ({change['path']})")
        gate, reject_reason = _gate_and_materialize(
            proposal_id=prop["proposal_id"],
            payload_dict=payload_dict,
            target_file_path=change["path"],
            diff_text=change.get("diff", ""),
            result=result,
            fallback_used=False,
            task_id=task_id,
            progress=progress,
            current_turn=current_turn,
        )
        statuses.append(gate)
        gates_by_path[change["path"]] = gate
        if gate == "rejected" and reject_reason:
            rejected_reasons[change["path"]] = reject_reason

    return statuses, proposal_ids, gates_by_path, rejected_reasons


def _publish_shell_event(event_type: str, *, task_id: str, payload: dict) -> None:
    """Publish one shell observability event (guarded, never raises)."""
    try:
        publish_event(event_type, source="shell_developer", task_id=task_id, payload=payload)
    except Exception as e:
        print(f"   ⚠️  Shell event publish skipped ({event_type}): {e}")


def _session_mut_fields(result: SessionResult) -> dict[str, Any]:
    """Fields the orchestrator uses to decide re-dispatch vs infra-neutral."""
    return {
        "session_exit": result.exit_status,
        "commands_executed": result.commands_executed,
        "evidence_ok": result.evidence_ok,
        "evidence_ran": result.evidence_ran,
        "target_path": result.target_path,
    }


def _handle_session_without_changes(
    *,
    task_id: str,
    result: SessionResult,
    progress: dict,
) -> None:
    """Record observability + messaging when a session produced no file changes."""
    progress["edit_failures"] = progress.get("edit_failures", 0) + 1
    if result.exit_status == "Finished":
        _publish_shell_event(
            "shell_session_no_mutation",
            task_id=task_id,
            payload={"exit_status": result.exit_status, "summary": result.summary},
        )
    else:
        post_message(
            "developer",
            "orchestrator",
            f"Shell developer session ended early ({result.exit_status}): {result.summary}",
            task_id,
            "HIGH",
        )


# =========================================================================
# Public turn entry point (mirrors run_developer_mutation contract)
# =========================================================================
def _task_is_targeted(
    task_text: str,
    decision: dict[str, Any],
    worktree: Any | None = None,
    marker: str = WORKSPACE_MARKER_DEFAULT,
) -> bool:
    """Task-fiability pre-flight: the decision names a *concrete existing* file.

    A file is only a target when it exists on disk. Phantom ``files_needed`` /
    ``addressing_feedback_ids`` entries (e.g. a TODO.md/ROADMAP.md the tidy step
    never created) must not force a targeted session that then hard-aborts on a
    missing target (Soak17 §11.1). Honoring the evidence-only chat row (step 1,
    Soak16) is not a target."""
    if resolve_seed_target_path(task_text, worktree, marker):
        return True
    for rel in decision.get("files_needed") or []:
        if _file_exists_on_disk(worktree, rel):
            return True
    for fid in decision.get("addressing_feedback_ids") or []:
        path = _feedback_file_path_for_id(fid)
        if path and _file_exists_on_disk(worktree, path):
            return True
    return False


def run_shell_developer_turn(  # noqa: C901
    *,
    task_id: str,
    instructions: str,
    user_command: str,
    conversation_context: list | None,  # parity with legacy signature
    model_choice: str | None,
    progress: dict,
    decision: dict,
    current_turn: int,
) -> dict[str, Any]:
    """Run one shell-based developer turn end-to-end (session → proposals → gate)."""
    cfg = ShellDeveloperConfig.from_config()
    if cfg.model is None:
        cfg.model = model_choice

    config = get_config()
    project_dir = Path(config.get("project_directory", ".")).resolve()

    worktree = ShellWorktree(project_dir, parent_dir=cfg.worktree_parent, max_file_bytes=cfg.max_file_bytes)
    session = ShellDeveloperSession(cfg, worktree, task_id)
    try:
        resolved = session._resolve_developer_model() or cfg.model
        if _chat_table_mode(cfg, resolved):
            print(f"   🗨️  Chat-JSON-table protocol for shell developer model {resolved}")
    except Exception as e:
        print(f"   ⚠️  Developer model capability check skipped: {e}")

    try:
        worktree.create()
    except RuntimeError as e:
        print(f"   ❌ Shell developer: {e}")
        progress["edit_failures"] = progress.get("edit_failures", 0) + 1
        _publish_shell_event(
            "shell_workspace_validation_failed",
            task_id=task_id,
            payload={"message": str(e)},
        )
        return {
            "status": "error",
            "message": str(e),
            "session_exit": "WorkspaceValidationFailed",
            "commands_executed": 0,
            "evidence_ok": False,
            "evidence_ran": False,
        }

    print(f"   🐚 Shell developer session (step_limit={cfg.step_limit}, verify={'yes' if cfg.test_command else 'no'})")
    progress["developer_calls"] = progress.get("developer_calls", 0) + 1

    task_text = instructions or user_command
    addressing_ids = decision.get("addressing_feedback_ids") or []

    # Task-fiability pre-flight (Soak16 feed fix): an untargeted task must not
    # burn a full session hunting a file. "strict" short-circuits before any
    # LLM call; "auto" caps the step budget and flags the session exploratory.
    targeted = _task_is_targeted(task_text, decision, worktree, cfg.workspace_marker)
    if not targeted and cfg.task_scope == "strict":
        print("   ⛔ Task-fiability pre-flight: task not targeted at any file (strict task_scope); skipping shell session")
        _publish_shell_event(
            "shell_task_untargeted_skipped",
            task_id=task_id,
            payload={"reason": "strict_scope", "task": task_text[:300]},
        )
        worktree.cleanup()
        return {
            "status": "error",
            "message": "task not targeted at any file; strict task_scope skipped the shell session",
            "session_exit": "UntargetedTask",
            "commands_executed": 0,
            "evidence_ok": False,
            "evidence_ran": False,
            "target_path": None,
        }
    if not targeted:
        cfg.fiability = "exploratory"
        if 0 < cfg.explore_step_cap < cfg.step_limit:
            print(f"   🔭 Task not targeted at a file; exploratory session step budget capped at {cfg.explore_step_cap}")
            cfg.step_limit = cfg.explore_step_cap

    # W6 (soak recompute): during a developer session the shell worktree is the
    # source of truth; background reviewers scanning the same files would rack
    # up competing feedback and burn tokens mid-session. Pause feedback agents
    # for the duration (lane isolation) and restore the previous stance after.
    # Never touches support workers (they are exempt inside set_active_agents).
    # c9 (soak recompute): support workers (prioritizer/archivist/reporter) back
    # off via foreground_session_guard() around session.run, so they stop
    # streaming 48k-110k-char archive prompts / reposting feedback into the same
    # rate-limited endpoint the developer depends on.
    lane_pool = None
    previous_filter = None
    bg_cfg = config.get("background_agents", {}) or {}
    if bg_cfg.get("lane_isolation_during_developer", True) and config.get("background_agents_enabled", True):
        try:
            from agents.parallel_workers import get_agent_pool

            lane_pool = get_agent_pool()
            if not getattr(lane_pool, "running", False) or not hasattr(lane_pool, "set_active_agents"):
                lane_pool = None
            else:
                previous_filter = getattr(lane_pool, "active_agents_filter", None)
                lane_pool.set_active_agents([])
                print("   🔀 Lane isolation: background feedback agents paused during developer session")
        except Exception as e:
            lane_pool = None
            print(f"   ⚠️  Lane isolation setup skipped: {e}")

    try:
        with foreground_session_guard():
            result = session.run(task_text)
        print(f"   🐺 Session exit: {result.exit_status} after {result.n_model_calls} model calls")

        _save_trajectory(task_id, current_turn, session)

        if result.exit_status == "WorkspaceValidationFailed":
            progress["edit_failures"] = progress.get("edit_failures", 0) + 1
            return {
                "status": "error",
                "message": result.summary or "shell workspace validation failed",
                **_session_mut_fields(result),
            }

        # W1 (soak recompute, 2026-08-29): an early-exiting session
        # (step_limit, user signal, transport failure) must still materialize
        # the edits already parked in its worktree - the diff evidence the
        # reviewer gate exists to judge. Rerunning the identical prompt
        # previously produced the identical early exit, stranding the edits
        # forever; now they are rescued the same way a Finished session's are.
        # The real exit status is preserved in the return so the orchestrator
        # loop-guard still sees it.
        if result.test_exit_code is not None and result.test_exit_code != 0:
            print(f"   ❌ Verification failed (exit {result.test_exit_code}); policy={cfg.on_test_failure}")
            if cfg.on_test_failure != "propose_anyway":
                progress["edit_failures"] = progress.get("edit_failures", 0) + 1
                publish_event(
                    "edit.verification_failed",
                    source="shell_developer",
                    task_id=task_id,
                    payload={"test_exit_code": result.test_exit_code},
                )
                return {
                    "status": "test_failed",
                    "message": f"post-session verification failed (exit {result.test_exit_code})",
                    "test_output_tail": result.test_output[-2000:],
                    **_session_mut_fields(result),
                }

        changes = worktree.collect_changes()
        if not changes:
            _handle_session_without_changes(
                task_id=task_id,
                result=result,
                progress=progress,
            )
            return {
                "status": "error",
                "message": (
                    "session finished but produced no file changes" if result.exit_status == "Finished" else f"session {result.exit_status}: {result.summary}"
                ),
                **_session_mut_fields(result),
            }

        statuses, proposal_ids, gates_by_path, rejected_reasons = _gate_and_materialize_changes(
            changes=changes,
            result=result,
            cfg=cfg,
            task_id=task_id,
            progress=progress,
            current_turn=current_turn,
        )

        # Soak6: a LimitsExceeded session whose only edits were unbounded diff
        # candidates is dropped wholesale — no proposal, and a distinct message
        # so the orchestrator can distinguish it from a genuine edit failure.
        if result.exit_status == "LimitsExceeded" and not proposal_ids:
            print("   ⛔ LimitsExceeded with no bounded promotable diff; not creating proposals")
            progress["edit_failures"] = progress.get("edit_failures", 0) + 1
            return {
                "status": "error",
                "message": "limits_exceeded_unbounded_diff: session hit the limit with no bounded promotable diff",
                **_session_mut_fields(result),
            }

        # Only mark feedback addressed when the file it targets actually landed;
        # skipped (deletion/oversize) or rejected changes must stay open.
        materialized_paths = {p for p, s in gates_by_path.items() if s == "success"}
        _mark_feedback_addressed(addressing_ids, materialized_paths)

        # P9 (merged residual): the turn is a "success" only when EVERY gated
        # change landed. A single rejected/error gate flips a mixed turn to
        # "error" - a half-applied session must never count as a win for the
        # orchestrator's success accounting.
        if statuses and all(s == "success" for s in statuses):
            overall = "success"
        elif any(s == "success" for s in statuses):
            overall = "error"
        elif any(s == "rejected" for s in statuses):
            overall = "rejected"
        else:
            overall = "error"

        return {
            "status": overall,
            "proposal_ids": proposal_ids,
            "gates": statuses,
            "reviewer_reason": "; ".join(rejected_reasons.values()) or None,
            "target_file_path": next(iter(rejected_reasons), None),
            **_session_mut_fields(result),
        }
    finally:
        worktree.cleanup()
        if lane_pool is not None:
            try:
                lane_pool.set_active_agents(previous_filter)
                print("   🔀 Lane isolation lifted: background feedback agents resumed")
            except Exception as e:
                print(f"   ⚠️  Lane isolation restore failed: {e}")


def _mark_feedback_addressed(addressing_ids: list[Any], materialized_paths: set[str]) -> None:
    """Mark agent_feedback rows addressed only when their file actually materialized.

    Non-numeric IDs (orchestrator hallucination) are skipped with a warning instead
    of aborting the addressing pass.
    """
    if not addressing_ids or not materialized_paths:
        return
    valid_ids: list[int] = []
    for raw_id in addressing_ids:
        try:
            valid_ids.append(int(raw_id))
        except (TypeError, ValueError):
            print(f"   ⚠️ Ignoring non-numeric feedback id from orchestrator: {raw_id!r}")
            continue
    if not valid_ids:
        return
    placeholders = ",".join("?" * len(valid_ids))
    with get_db_connection() as conn:
        rows = conn.execute(
            f"SELECT id, file_path FROM agent_feedback WHERE id IN ({placeholders})",
            valid_ids,
        ).fetchall()
        for fb_id, fb_file_path in rows:
            fb_path = str(fb_file_path or "").removeprefix("./")
            if fb_path in materialized_paths:
                conn.execute(
                    """
                    UPDATE agent_feedback
                    SET addressed = 1, addressed_by = 'developer', addressed_at = ?
                    WHERE id = ?
                    """,
                    (datetime.now(timezone.utc).isoformat(), fb_id),
                )


def _save_trajectory(task_id: str, current_turn: int, session: ShellDeveloperSession) -> None:
    """Persist the session trajectory next to the governed DB for audit (RMF artifact)."""
    try:
        from core.db import get_db_path

        out_dir = Path(get_db_path()).parent / "shell_trajectories"
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = out_dir / f"{task_id}-turn{current_turn}-{stamp}.json"
        path.write_text(json.dumps(session.serialize(), indent=2))
        print(f"   🧾 Trajectory saved: {path}")
    except Exception as e:  # trajectory saving must never break mutation
        print(f"   ⚠️ Could not save shell developer trajectory: {e}")
