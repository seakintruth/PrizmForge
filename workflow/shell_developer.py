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
import re
import shlex
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agents.base import call_agent, call_endpoint
from core.config import get_config
from core.db_connection import get_db_connection
from core.db_helpers import post_message
from core.events import publish_event
from file_editing.undo import snapshot_before_apply
from file_editing.writer import materialize_proposal
from workflow.git_failure import record_git_failure
from workflow.proposal_builder import create_proposal_from_developer_output, update_proposal_status

FINISH_TOKEN = "FINISH_EDIT_SESSION"
BASH_BLOCK_RE = re.compile(r"```bash\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)
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

Protocol for every reply:
- Think briefly, then emit exactly ONE bash command inside a ```bash fenced block. \
It will be executed with the project copy as the working directory.
- Use commands to inspect files, apply edits, and run the project's tests or linters.
- Prefer small, verifiable steps. After editing, run relevant tests to check your work.
- When the task is fully done and verified, reply with {finish_token} on its own line \
followed by a short summary of what changed. Do not emit a bash block in that final reply.

Never attempt to interact outside this working copy; changes outside it are discarded."""


def build_instance_prompt(task_text: str) -> str:
    return f"TASK:\n{task_text}\n\nBegin by inspecting the relevant files, then implement the change and verify it."


# =========================================================================
# Response parsing
# =========================================================================
def extract_bash_command(response: str) -> str | None:
    """Return the last ```bash fenced command in the response, if any."""
    matches = BASH_BLOCK_RE.findall(response or "")
    for block in reversed(matches):
        cmd = block.strip()
        if cmd:
            return cmd
    return None


def extract_finish(response: str) -> str | None:
    """Return the finish summary when FINISH_EDIT_SESSION is present."""
    if FINISH_TOKEN not in (response or ""):
        return None
    summary_lines = [line for line in response.splitlines() if FINISH_TOKEN not in line]
    return "\n".join(summary_lines).strip()


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
            self._sub_rel = Path(".")

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
        reported. Deleted files are reported so the caller can warn; there is
        currently no governed delete operation, so deletions are skipped at
        proposal time.
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
                    item["diff"] = (diff_p.stdout or "")[:20_000]
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

    def _llm(self) -> str | None:
        text, _tokens = call_endpoint(
            self.messages,
            task_id=self.task_id,
            agent_name="developer",
            model=self.cfg.model,
        )
        return text

    def _observation(self, exit_code: int, output: str) -> dict:
        trimmed = output
        if len(trimmed) > self.cfg.max_output_chars:
            cut = len(trimmed) - self.cfg.max_output_chars
            trimmed = f"...[{cut} chars truncated]...\n{trimmed[-self.cfg.max_output_chars :]}"
        return {
            "role": "user",
            "content": f"[exit code {exit_code}]\n{trimmed}" if trimmed else f"[exit code {exit_code}, no output]",
        }

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
                r.summary = "LLM endpoint unavailable or token budget exhausted"
                break
            self.messages.append({"role": "assistant", "content": response})

            summary = extract_finish(response)
            command = extract_bash_command(response)

            if summary is not None and command is not None:
                # The model tried to run a final command AND finish in one reply
                # (e.g. "run tests, then FINISH"). Since verification depends on the
                # worktree state the command produces, execute it first and defer the
                # finish; force-finish if the model keeps pairing them.
                self._deferred_finish_count += 1
                exit_code, output = self.wt.run_command(command, self._effective_command_timeout())
                self.messages.append(self._observation(exit_code, output))
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
                break

            if command is None:
                consecutive_format_errors += 1
                if self.cfg.max_consecutive_format_errors > 0 and consecutive_format_errors >= self.cfg.max_consecutive_format_errors:
                    r.exit_status = "RepeatedFormatError"
                    r.summary = "no ```bash block or finish token in consecutive replies"
                    break
                self.messages.append(
                    {
                        "role": "user",
                        "content": (f"FormatError: reply must contain either a single ```bash fenced command or the token {FINISH_TOKEN} with a summary."),
                    }
                )
                continue

            consecutive_format_errors = 0
            exit_code, output = self.wt.run_command(command, self._effective_command_timeout())
            self.messages.append(self._observation(exit_code, output))

        # Optional post-session verification against the edited worktree.
        if r.exit_status == "Finished" and self.cfg.test_command:
            code, output = self.wt.run_test_command(self.cfg.test_command, self.cfg.test_timeout_seconds)
            r.test_exit_code = code
            r.test_output = output[-self.cfg.max_output_chars :]
        return r

    def serialize(self) -> dict:
        last = self.messages[-1] if self.messages else {}
        return {
            "trajectory_format": "prizmforge-shell-developer-1.0",
            "exit_status": self.result.exit_status,
            "submission_summary": self.result.summary,
            "model_stats": {"api_calls": self.result.n_model_calls},
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
    # D / S / anything else: no governed equivalent — caller warns.
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
PROPOSED UNIFIED DIFF (applied in isolated copy)
--------------------------------------------------
{diff_text[:8000] or "(no textual diff available — see payload)"}

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
- REJECT if the change appears truncated, removes large amounts of existing code without clear justification, or introduces obvious errors.
- APPROVE only when the change is coherent and the resulting file would still be valid.
"""

    progress["reviewer_calls"] = progress.get("reviewer_calls", 0) + 1
    reviewer_response = call_agent("reviewer", reviewer_prompt, task_id)

    # Fail closed: shell-session diffs originate from arbitrary bash execution,
    # so a missing or unparseable verdict must REJECT, never auto-approve.
    decision_result: str
    reason: str
    suggestions: list[Any]
    if not reviewer_response or not str(reviewer_response).strip():
        decision_result = "REJECT"
        reason = "Reviewer unavailable (empty response) - failing closed"
        suggestions = []
        print("   ⚠️ Reviewer returned no response; rejecting proposal (fail closed)")
    else:
        try:
            decision_data = json.loads(reviewer_response)
            decision_result = str(decision_data.get("decision", "")).upper()
            reason = decision_data.get("reason", "")
            suggestions = decision_data.get("suggestions") or []
            if decision_result not in ("APPROVE", "REJECT"):
                raise ValueError(f"invalid decision value {decision_result!r}")
        except Exception as e:
            decision_result = "REJECT"
            reason = f"Reviewer returned an unparseable verdict ({e}) - failing closed"
            suggestions = []
            print("   ⚠️ Reviewer response was not valid JSON; rejecting proposal (fail closed)")

    if suggestions:
        suggestion_text = "\n".join([f"- {s}" for s in suggestions])
        post_message(
            "reviewer",
            "prioritizer",
            f"Suggestions from Reviewer for Proposal {proposal_id}:\n{suggestion_text}",
            task_id,
            "MEDIUM",
        )

    if decision_result == "REJECT":
        print(f"   ❌ Reviewer rejected proposal {proposal_id}: {reason}")
        update_proposal_status(proposal_id, "rejected")
        _log_rejection_feedback(task_id, target_file_path, proposal_id, reason, suggestions)
        publish_event(
            "proposal.rejected",
            source="reviewer",
            task_id=task_id,
            proposal_id=proposal_id,
            payload={"reason": reason},
        )
        post_message(
            "reviewer",
            "orchestrator",
            f"Proposal {proposal_id} REJECTED.\nReason: {reason}",
            task_id,
            "HIGH",
        )
        return "rejected"

    print(f"   ✅ Reviewer approved proposal {proposal_id}")
    update_proposal_status(proposal_id, "approved")
    publish_event("proposal.approved", source="reviewer", task_id=task_id, proposal_id=proposal_id)
    snapshot_before_apply(proposal_id)
    mat = materialize_proposal(proposal_id)

    if mat.get("status") == "git_failed":
        record_git_failure(mat, task_id, proposal_id)
    elif mat.get("status") == "success":
        publish_event(
            "edit.materialized",
            source="writer",
            task_id=task_id,
            proposal_id=proposal_id,
            payload=mat if isinstance(mat, dict) else {},
        )
        progress["files_modified"] = progress.get("files_modified", 0) + 1
        progress["materialize_successes"] = progress.get("materialize_successes", 0) + 1
        progress["last_file_change"] = current_turn
    else:
        publish_event(
            "edit.failed",
            source="writer",
            task_id=task_id,
            proposal_id=proposal_id,
            payload=mat if isinstance(mat, dict) else {},
        )
        progress["edit_failures"] = progress.get("edit_failures", 0) + 1
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


def _log_rejection_feedback(
    task_id: str,
    target_file_path: str,
    proposal_id: str,
    reason: str,
    suggestions: list[str],
) -> None:
    try:
        with get_db_connection() as conn:
            conn.execute(
                """
                INSERT INTO agent_feedback
                (task_id, file_path, agent_name, message, suggestion,
                 priority, category, addressed, timestamp)
                VALUES (?, ?, 'reviewer', ?, ?, 'HIGH', 'review_rejection', 0, ?)
                """,
                (
                    task_id,
                    target_file_path,
                    f"Proposal {proposal_id} REJECTED: {reason}",
                    "; ".join(suggestions) if suggestions else None,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
    except Exception as e:  # feedback logging must never break the gate
        print(f"   ⚠️ Failed to log reviewer rejection to feedback table: {e}")


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
        return {"status": "error", "message": str(e)}

    print(f"   🐚 Shell developer session (step_limit={cfg.step_limit}, verify={'yes' if cfg.test_command else 'no'})")
    progress["developer_calls"] = progress.get("developer_calls", 0) + 1

    task_text = instructions or user_command
    addressing_ids = decision.get("addressing_feedback_ids") or []

    try:
        result = session.run(task_text)
        print(f"   🐚 Session exit: {result.exit_status} after {result.n_model_calls} model calls")

        _save_trajectory(task_id, current_turn, session)

        if result.exit_status != "Finished":
            progress["edit_failures"] = progress.get("edit_failures", 0) + 1
            post_message(
                "developer",
                "orchestrator",
                f"Shell developer session ended early ({result.exit_status}): {result.summary}",
                task_id,
                "HIGH",
            )
            return {"status": "error", "message": f"session {result.exit_status}: {result.summary}"}

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
            progress["edit_failures"] = progress.get("edit_failures", 0) + 1
            return {"status": "error", "message": "session finished but produced no file changes"}

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

        # Only mark feedback addressed when the file it targets actually landed;
        # skipped (deletion/oversize) or rejected changes must stay open.
        materialized_paths = {p for p, s in gates_by_path.items() if s == "success"}
        _mark_feedback_addressed(addressing_ids, materialized_paths)

        overall = "success" if "success" in statuses else ("rejected" if "rejected" in statuses else "error")
        return {
            "status": overall,
            "proposal_ids": proposal_ids,
            "session_exit": result.exit_status,
            "gates": statuses,
        }
    finally:
        worktree.cleanup()


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
