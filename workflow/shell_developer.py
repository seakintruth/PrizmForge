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

The legacy structured EditPayload developer path remains available via
``config.developer.implementation = "edit_payload"``.
"""

from __future__ import annotations

import json
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
        )
        if instance.on_test_failure not in ("discard", "propose_anyway"):
            print(f"   ⚠️ shell_developer.on_test_failure={instance.on_test_failure!r} is invalid; using 'discard' (fail closed)")
            instance.on_test_failure = "discard"
        return instance


# =========================================================================
# Prompts (adapted from mini-swe-agent's system/instance templates)
# =========================================================================
SYSTEM_PROMPT = """You are the Developer agent of an autonomous software engineering system.

You are working in a disposable copy of the project repository. Your job is to complete \
the given task by editing files directly with shell commands, then verifying your work.

RESPONSE FORMAT — REQUIRED:
- Think briefly, then emit EXACTLY ONE bash command inside a single ```bash fenced block. \
It will be executed with the project copy as the working directory.
- Use commands to inspect files, apply edits, and run the project's tests or linters.
- Prefer small, verifiable steps. After editing, run relevant tests to check your work.
- When the task is fully done and verified, reply with {finish_token} on its own line \
followed by a short summary of what changed. Do not emit a bash block in that final reply.
- A closed bash block looks exactly like this (opening line, the command, closing line):

```bash
pwd && ls -la
```

- Your FIRST command must always be the initial-workspace evidence command below:
  pwd && git rev-parse --show-toplevel && ls -la
  This proves which directory you are in and that the repository root is reachable before \
you touch anything.

Never attempt to interact outside this working copy; changes outside it are discarded."""


def build_instance_prompt(task_text: str) -> str:
    return (
        f"TASK:\n{task_text}\n\n"
        "Begin by inspecting the relevant files, then implement the change and verify it. "
        "If the task target file does not exist, do NOT create or guess a task-named path. "
        f"Unless you can find a safe, in-repo change that directly satisfies the task, reply "
        f"with only {FINISH_TOKEN} and a clear summary of why no safe change was made."
    )


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
            text=True,
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
        try:
            proc = subprocess.run(
                command,
                shell=True,
                cwd=str(self.working_dir()),
                capture_output=True,
                text=True,
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
                text=True,
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


# Failure kinds that a bounded backoff+retry cannot fix — give up immediately
# instead of burning retries (mirrors call_endpoint's own handling).
PERMANENT_FAILURE_KINDS = {"key_locked", "unauthorized", "token_budget", "token_exhausted", "bad_payload"}


def _recent_failure_kind(model_ref: str | None, max_age_s: int = 30) -> str:
    """Return the failure kind the most recent model-health event recorded for
    a model reference (or "" if none). call_endpoint writes every failure
    synchronously before returning None, so this classifies the None instead of
    guessing whether it was rate-limiting, a latch, or a token budget."""
    if not model_ref:
        return ""
    try:
        with get_db_connection() as conn:
            cutoff = (datetime.now() - timedelta(seconds=max_age_s)).isoformat(timespec="seconds")
            row = conn.execute(
                "SELECT kind FROM model_health_events WHERE model_ref = ? AND ok = 0 AND ts >= ? ORDER BY ts DESC LIMIT 1",
                (model_ref, cutoff),
            ).fetchone()
            return str(row[0]) if row else ""
    except Exception:
        return ""


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
        short backoff + retry is worthwhile; permanent kinds (bad key, token
        budget, ...) give up immediately. The model is re-resolved between
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
            self.result.llm_failure_kinds[kind] = self.result.llm_failure_kinds.get(kind, 0) + 1
            self.result.last_llm_failure = {"kind": kind, "model_ref": model_ref, "attempt": attempt + 1}
            if kind in PERMANENT_FAILURE_KINDS or attempt >= self.cfg.llm_failure_max_retries:
                break
            backoff_s = max(int(self.cfg.llm_retry_backoff_seconds) * (attempt + 1), 1)
            print(f"   ⏳ Shell developer LLM failure ({kind}); backing off {backoff_s}s (attempt {attempt + 1}/{self.cfg.llm_failure_max_retries + 1})")
            time.sleep(backoff_s)
        return None

    def _observation(self, exit_code: int, output: str) -> dict:
        trimmed = output
        if len(trimmed) > self.cfg.max_output_chars:
            cut = len(trimmed) - self.cfg.max_output_chars
            trimmed = f"...[{cut} chars truncated]...\n{trimmed[-self.cfg.max_output_chars :]}"
        return {
            "role": "user",
            "content": f"[exit code {exit_code}]\n{trimmed}" if trimmed else f"[exit code {exit_code}, no output]",
        }

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
        valid = response_format_status in (shell_protocol.VALID_BASH_BLOCK, shell_protocol.VALID_FINISH_SESSION)
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
                command=command,
                command_exit_code=command_exit_code,
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

    def run(self, task_text: str) -> SessionResult:
        r = self.result
        r.messages = self.messages
        self.messages.append({"role": "system", "content": SYSTEM_PROMPT.format(finish_token=FINISH_TOKEN)})
        self.messages.append({"role": "user", "content": build_instance_prompt(task_text)})

        consecutive_format_errors = 0
        while True:
            elapsed_min = (time.time() - self._start) / 60
            if self.cfg.step_limit > 0 and r.n_model_calls >= self.cfg.step_limit:
                r.exit_status = "LimitsExceeded"
                r.summary = f"step limit ({self.cfg.step_limit}) reached"
                break
            if self.cfg.wall_time_limit_minutes > 0 and elapsed_min >= self.cfg.wall_time_limit_minutes:
                r.exit_status = "TimeExceeded"
                r.summary = f"wall-clock limit ({self.cfg.wall_time_limit_minutes}m) reached"
                break

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

            is_protocol_valid = command is not None or summary is not None
            self._record_model_health(ok=is_protocol_valid, kind="protocol_valid" if is_protocol_valid else "protocol_invalid")

            if summary is not None and command is not None:
                # The model tried to run a final command AND finish in one reply
                # (e.g. "run tests, then FINISH"). Since verification depends on the
                # worktree state the command produces, execute it first and defer the
                # finish; force-finish if the model keeps pairing them.
                self._deferred_finish_count += 1
                exit_code, output = self.wt.run_command(command, self._effective_command_timeout())
                self.messages.append(self._observation(exit_code, output))
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
                if self._deferred_finish_count >= 3:
                    r.exit_status = "Finished"
                    r.summary = f"[finish forced after {self._deferred_finish_count} deferred finishes] {summary}"
                    break
                self.messages.append(
                    {
                        "role": "user",
                        "content": (
                            f"Your previous reply contained both a bash command and {FINISH_TOKEN}. "
                            "The command has been executed (result above). If the task is now "
                            f"complete, reply again with only {FINISH_TOKEN} and a summary."
                        ),
                    }
                )
                continue

            if summary is not None:
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
                self.messages.append(
                    {
                        "role": "user",
                        "content": (
                            f"FormatError (reason={diag['reason']}): reply must contain either a single "
                            f"```bash fenced command or the token {FINISH_TOKEN} with a summary. "
                            f"Expected: {diag['expected']}."
                        ),
                    }
                )
                continue

            consecutive_format_errors = 0
            exit_code, output = self.wt.run_command(command, self._effective_command_timeout())
            self.messages.append(self._observation(exit_code, output))
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
def change_to_operation(change: dict[str, Any]) -> dict | None:
    """Map one collected change into an EditPayload operation dict (or None to skip)."""
    status = change.get("status")
    path = change.get("path", "")
    content = change.get("new_content", "")

    if status == "A":
        return {
            "type": "create_file",
            "target_file_path": path,
            "initial_content": content.splitlines(),
            "rationale": "Create file (shell developer session)",
        }
    if status == "M":
        return {"type": "full_replace", "new_content": content, "rationale": "Full replace (shell developer session)"}
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
        return "rejected"

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
    return mat.get("status", "error")


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

    for change in changes:
        op = change_to_operation(change)
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
        gate = _gate_and_materialize(
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

    return statuses, proposal_ids, gates_by_path


def _publish_shell_event(event_type: str, *, task_id: str, payload: dict) -> None:
    """Publish one shell observability event (guarded, never raises)."""
    try:
        publish_event(event_type, source="shell_developer", task_id=task_id, payload=payload)
    except Exception as e:
        print(f"   ⚠️  Shell event publish skipped ({event_type}): {e}")


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
def run_shell_developer_turn(
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
        worktree.create()
    except RuntimeError as e:
        print(f"   ❌ Shell developer: {e}")
        progress["edit_failures"] = progress.get("edit_failures", 0) + 1
        _publish_shell_event(
            "shell_workspace_validation_failed",
            task_id=task_id,
            payload={"message": str(e)},
        )
        return {"status": "error", "message": str(e)}

    print(f"   🐚 Shell developer session (step_limit={cfg.step_limit}, verify={'yes' if cfg.test_command else 'no'})")
    progress["developer_calls"] = progress.get("developer_calls", 0) + 1

    task_text = instructions or user_command
    addressing_ids = decision.get("addressing_feedback_ids") or []

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
            }

        statuses, proposal_ids, gates_by_path = _gate_and_materialize_changes(
            changes=changes,
            result=result,
            cfg=cfg,
            task_id=task_id,
            progress=progress,
            current_turn=current_turn,
        )

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
            "session_exit": result.exit_status,
            "gates": statuses,
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
