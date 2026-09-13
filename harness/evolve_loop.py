"""Harness Evolve loop (§12.5, docs/HARNESS_EVOLUTION_DESIGN.md).

The Evolve Agent drives the *same* governed pipeline as a developer edit:
propose one harness- scoped change through `create_proposal_from_developer_output`
→ mandatory reviewer gate → `snapshot_before_apply` + `materialize_proposal`.
Guardrails keep the loop honest: edits must target ``harness/`` only; ``runs/``,
endpoint/model config and the ``system_prompt/`` seed prompts are read-only;
a ~RC-style edit budget gates the loop; manifests + task outcomes make each
edit falsifiable and `run_evolve_reverts` executes the §5.3 rollback rule.

The prompt personality is mounted from ``harness/system_prompt/evolve.md`` at
runtime (single prompt-assembly path) instead of a static ``agent_prompts.json``
entry; the loader falls back to the legacy prompts dict when the file is absent.
"""

from __future__ import annotations

import itertools
import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agents.base import call_agent
from core.config import get_agent_prompts, get_config
from file_editing.undo import snapshot_before_apply
from file_editing.writer import materialize_proposal
from workflow.proposal_builder import create_proposal_from_developer_output, update_proposal_status
from workflow.reviewer_gate import ReviewerVerdict, handle_reviewer_rejection, request_review_verdict

from .evolve import (
    edit_verdicts,
    outcomes_from_results,
    read_change_manifest,
    record_change_manifest,
    record_iteration_outcomes,
    revert_candidates,
    write_manifest_file,
)

HARNESS_DIR = "harness"
SYSTEM_PROMPT_DIR = f"{HARNESS_DIR}/system_prompt"
READONLY_PREFIXES = ("runs/",)
READONLY_PATHS = frozenset({"config.json", "agent_prompts.json", "endpoints.json"})

_PLACEHOLDER_RE = re.compile(r"\{\{(\w+)\}\}")
_INCLUDE_RE = re.compile(r"\{\{include:([\w./\-]+)\}\}")


@dataclass
class EvolveBudget:
    """~RC-style edit budget: cap logical edits and total tokens per loop."""

    max_edits: int = 1
    max_tokens: int = 0
    edits_used: int = 0
    tokens_used: int = 0

    def spend(self, tokens: int = 0) -> None:
        self.edits_used += 1
        self.tokens_used += max(0, int(tokens))

    def __str__(self) -> str:
        token_lim = "unlimited" if not self.max_tokens else f"{self.max_tokens}"
        return f"edits: {self.edits_used}/{self.max_edits} used, tokens: {self.tokens_used}/{token_lim}"

    @property
    def exhausted(self) -> bool:
        if self.max_edits and self.edits_used >= self.max_edits:
            return True
        if self.max_tokens and self.tokens_used >= self.max_tokens:
            return True
        return False


@dataclass
class EvolveResult:
    """Outcome of one `run_evolve_iteration` step."""

    iteration: int
    status: str = "error"
    proposal_id: str | None = None
    target_file_path: str | None = None
    message: str = ""
    reviewer_decision: str | None = None
    materialize_status: str | None = None
    commit: str | None = None
    outcomes_recorded: int = 0
    manifest_recorded: bool = False
    budget: EvolveBudget | None = None


def load_evolve_config(config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Read the ``evolve`` section of the app config (all keys optional)."""
    cfg = config or get_config()
    evo = cfg.get("evolve") or {}
    return {
        "enabled": bool(evo.get("enabled", False)),
        "max_edits_per_iteration": int(evo.get("max_edits_per_iteration") or 1),
        "max_tokens_per_iteration": int(evo.get("max_tokens_per_iteration") or 0),
    }


def budget_from_config(config: dict[str, Any] | None = None) -> EvolveBudget:
    evo = load_evolve_config(config)
    return EvolveBudget(
        max_edits=evo["max_edits_per_iteration"],
        max_tokens=evo["max_tokens_per_iteration"],
    )


def is_evolve_readonly_path(rel_path: str) -> bool:
    p = rel_path.replace("\\", "/").strip()
    return p.startswith(READONLY_PREFIXES) or p in READONLY_PATHS


def validate_evolve_target(rel_path: str, *, deleting: bool = False) -> tuple[bool, str]:
    """Guardrail: Evolve edits target ``harness/`` only, never read-only paths.

    Seed prompt files under ``system_prompt/`` may be edited but never deleted.
    """
    if not rel_path or not isinstance(rel_path, str):
        return False, "empty target path"
    p = rel_path.replace("\\", "/").strip()
    if not p or p.startswith("/") or p.startswith("~"):
        return False, "absolute paths are not editable"
    parts = [part for part in p.split("/") if part not in ("", ".")]
    if not parts or any(part == ".." for part in parts):
        return False, "target escapes the workspace"
    p = "/".join(parts)
    if not (p.startswith(HARNESS_DIR + "/") or p == HARNESS_DIR):
        return False, "Evolve edits must target harness/ only"
    if is_evolve_readonly_path(p):
        return False, "path is read-only for Evolve edits"
    if deleting and p.startswith(SYSTEM_PROMPT_DIR + "/"):
        return False, "seed prompt files are non-deletable"
    return True, "ok"


def resolve_harness_prompt(
    role: str,
    *,
    context: dict[str, Any] | None = None,
    prompt_root: str | Path | None = None,
) -> str:
    """Harness mount loader: assemble ``system_prompt/<role>.md`` at runtime.

    ``{{key}}`` placeholders are filled from ``context``; ``{{include:<file>}}``
    inlines a sibling file under the prompt root. When no markdown file exists
    the loader falls back to the legacy ``agent_prompts.json`` system prompt so
    the rest of the harness keeps one, truthful prompt-assembly story.
    """
    seed_root = Path(prompt_root) if prompt_root else Path(SYSTEM_PROMPT_DIR).resolve()
    seed = seed_root / f"{role}.md"
    ctx = context or {}

    if seed.is_file():
        text = seed.read_text(encoding="utf-8")
        for _depth in range(5):

            def inline(match: re.Match) -> str:
                child = seed_root / match.group(1)
                return child.read_text(encoding="utf-8") if child.is_file() else ""

            replaced = _INCLUDE_RE.sub(inline, text)
            if replaced == text:
                break
            text = replaced
        return _PLACEHOLDER_RE.sub(lambda m: str(ctx.get(m.group(1), "")), text)

    prompts = get_agent_prompts()
    system_prompt = (prompts.get(role) or {}).get("system_prompt", "")
    return _PLACEHOLDER_RE.sub(lambda m: str(ctx.get(m.group(1), "")), system_prompt)


def _approx_tokens(text: str) -> int:
    return max(0, len(text or "") // 4)


def build_evidence_context(iteration: int, results: dict[str, Any] | None = None) -> str:
    """Deterministic evidence digest: outcomes + verdicts + pending reverts."""
    lines: list[str] = []
    outcomes = []
    try:
        outcomes = outcomes_from_results(results) if results and results.get("tasks") else []
    except Exception:
        outcomes = []
    if not outcomes:
        try:
            from .evolve import load_task_outcomes

            outcomes = load_task_outcomes(iteration) or []
        except Exception:
            outcomes = []

    passed = [str(o["task_id"]) for o in outcomes if o["passed"]]
    failed = [str(o["task_id"]) for o in outcomes if not o["passed"]]
    tokens = sum(int(o.get("tokens") or 0) for o in outcomes)
    lines.append(f"Iteration {iteration}: {len(passed)} passed, {len(failed)} failed, {tokens} tokens")
    if passed:
        lines.append("passing tasks: " + ", ".join(sorted(passed)))
    if failed:
        lines.append("failing tasks: " + ", ".join(sorted(failed)))

    if iteration > 1:
        verdicts: list[dict[str, Any]] = []
        candidates: list[dict[str, Any]] = []
        try:
            verdicts = edit_verdicts(iteration - 1, iteration) or []
        except Exception:
            verdicts = []
        for v in verdicts:
            lines.append(
                f"edit {v.get('edit_id')}: precision {v.get('precision')} "
                f"({v.get('fixes_confirmed')}/{v.get('fixes_predicted')} predicted fixes {v.get('confirmed') or []})"
            )
        try:
            candidates = revert_candidates(iteration - 1, iteration) or []
        except Exception:
            candidates = []
        for c in candidates:
            lines.append(f"pending revert {c.get('edit_id')}: {c.get('action')}")
    return "\n".join(lines)


def build_evolve_prompt(
    iteration: int,
    *,
    evidence: str | None = None,
    results: dict[str, Any] | None = None,
    budget: EvolveBudget | None = None,
    prompt_root: str | Path | None = None,
) -> str:
    context = {
        "evidence": evidence or build_evidence_context(iteration, results),
        "budget": str(budget or budget_from_config()),
        "iteration": iteration,
    }
    return resolve_harness_prompt("evolve", context=context, prompt_root=prompt_root)


def _default_propose(
    *,
    iteration: int,
    evidence: str,
    budget: EvolveBudget | None,
    task_id: str | None,
    prompt_root: str | Path | None,
) -> dict[str, Any] | None:
    task_id = task_id or f"evolve-{iteration}"
    prompt = build_evolve_prompt(iteration, evidence=evidence, budget=budget, prompt_root=prompt_root)
    response = call_agent("developer", prompt, task_id)
    if not response:
        return None
    return {"developer_output": response, "target_file_path": None}


def _default_reviewer(
    *,
    target_file_path: str,
    proposal_id: str,
    task_id: str,
    predicted_fixes: list[str] | None = None,
    predicted_regressions: list[str] | None = None,
    rationale: str | None = None,
) -> ReviewerVerdict:
    reviewer_prompt = f"""You are the reviewer gate for a harness evolution edit.
File under review: `{target_file_path}`
Proposal: {proposal_id}
Proposed rationale: {rationale or ""}
Predicted fixes: {predicted_fixes or []}
Predicted regressions: {predicted_regressions or []}
HARNESS POLICY: the edit must be scoped to harness/, one logical change per
commit. Approve only when the change is minimal, safe, and grounded in the
proposal rationale.
Return JSON: {{"decision": "APPROVE"|"REJECT", "reason": "...", "suggestions": [...]}}."""
    return request_review_verdict(reviewer_prompt, task_id)


def run_evolve_iteration(
    iteration: int,
    *,
    results: dict[str, Any] | None = None,
    propose: Callable[..., Any] | None = None,
    reviewer: Callable[..., Any] | None = None,
    budget: EvolveBudget | None = None,
    task_id: str | None = None,
    prompt_root: str | Path | None = None,
    record_outcomes: bool = True,
) -> EvolveResult:
    """One evolve step: outcomes → evidence → propose → gate → apply → manifest.

    The reviewer gate is mandatory and cannot be disabled by config; the
    ``reviewer``/``propose`` params exist only for hermetic test injection.
    """
    res = EvolveResult(iteration=iteration)
    results = results or {}
    if record_outcomes and results.get("tasks"):
        res.outcomes_recorded = record_iteration_outcomes(iteration, results)

    budget = budget or budget_from_config()
    res.budget = budget
    if budget.exhausted:
        res.status = "budget_exhausted"
        res.message = "edit budget exhausted; loop needs a new window"
        return res

    evidence = build_evidence_context(iteration, results)
    propose_fn = propose or _default_propose
    try:
        proposal_data = propose_fn(
            iteration=iteration,
            evidence=evidence,
            budget=budget,
            task_id=task_id,
            prompt_root=prompt_root,
        )
    except Exception as exc:  # a propose defect must never crash the loop
        res.status = "error"
        res.message = f"propose failed: {exc}"
        return res
    if not proposal_data:
        res.status = "no_target"
        res.message = "proposer produced no edit"
        return res

    target = proposal_data.get("target_file_path")
    if not target:
        res.status = "no_target"
        res.message = "proposer produced no target_file_path"
        return res
    ok, reason = validate_evolve_target(target)
    if not ok:
        res.status = "blocked"
        res.message = reason
        return res

    developer_output = proposal_data.get("developer_output")
    if not developer_output:
        res.status = "error"
        res.message = "proposer produced no developer_output"
        return res
    rationale = proposal_data.get("rationale")
    predicted_fixes = [str(f) for f in (proposal_data.get("predicted_fixes") or [])]
    predicted_regressions = [str(r) for r in (proposal_data.get("predicted_regressions") or [])]
    root_cause = proposal_data.get("inferred_root_cause")

    action_task_id = task_id or f"evolve-{iteration}"
    prop = create_proposal_from_developer_output(
        developer_output,
        proposed_by_agent_id=1,
        target_file_path=target,
        rationale=rationale,
        task_id=action_task_id,
    )
    if prop.get("status") != "success":
        res.status = "error"
        res.message = f"proposal creation failed: {prop.get('message')}"
        return res

    proposal_id = prop["proposal_id"]
    res.proposal_id = proposal_id
    res.target_file_path = target

    review_fn = reviewer or _default_reviewer
    verdict = review_fn(
        target_file_path=target,
        proposal_id=proposal_id,
        task_id=action_task_id,
        predicted_fixes=predicted_fixes,
        predicted_regressions=predicted_regressions,
        rationale=rationale,
    )
    if verdict is None:
        verdict = ReviewerVerdict(decision="REJECT", reason="Reviewer gate unavailable - failing closed", infra_reject=True)
    res.reviewer_decision = verdict.decision
    if verdict.rejected:
        handle_reviewer_rejection(
            proposal_id=proposal_id,
            target_file_path=target,
            task_id=action_task_id,
            reason=verdict.reason,
            suggestions=verdict.suggestions,
        )
        res.status = "rejected"
        res.message = verdict.reason or "rejected by reviewer"
        return res

    update_proposal_status(proposal_id, "approved")
    snapshot_before_apply(proposal_id)
    mat = materialize_proposal(proposal_id)
    res.materialize_status = mat.get("status")
    landed = mat.get("status") in ("success", "lint_failed", "git_failed")
    if landed:
        res.commit = _latest_commit_sha()
        res.status = "applied"
        res.message = f"applied via proposal {proposal_id}"
        res.manifest_recorded = _record_edit_manifest(
            iteration,
            edit={
                "edit_id": proposal_id,
                "target_file": target,
                "commit": res.commit,
                "rationale": rationale,
                "predicted_fixes": predicted_fixes,
                "predicted_regressions": predicted_regressions,
                "inferred_root_cause": root_cause,
            },
        )
        budget.spend(
            tokens=_approx_tokens(str(developer_output))
            + _approx_tokens(str(rationale))
            + _approx_tokens(str(predicted_fixes))
            + _approx_tokens(str(predicted_regressions))
        )
    else:
        res.status = "error"
        res.message = f"materialize failed ({mat.get('status')})"
    return res


def _record_edit_manifest(iteration: int, *, edit: dict[str, Any]) -> bool:
    """Append one edit to the iteration manifest (DB + JSON file)."""
    try:
        manifest = read_change_manifest(iteration) or {"iteration": int(iteration), "edits": []}
        if not isinstance(manifest, dict):
            manifest = {"iteration": int(iteration), "edits": []}
        edits = manifest.setdefault("edits", [])
        edits.append(edit)
        record_change_manifest(iteration, manifest)
        write_manifest_file(iteration, manifest)
        return True
    except Exception:
        return False


def _latest_commit_sha() -> str | None:
    """Best-effort HEAD sha of the workspace the evolve edit landed in."""
    try:
        project_dir = Path(get_config().get("project_directory", "."))
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if proc.returncode == 0:
            return proc.stdout.strip() or None
    except Exception:
        return None
    return None


def run_evolve_reverts(
    prior_iter: int,
    cur_iter: int,
    *,
    executor: Callable[[dict[str, Any]], bool] | None = None,
    workspace: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Execute §5.3 rollback candidates: ``git revert`` by default, injectable."""
    candidates = revert_candidates(prior_iter, cur_iter) or []
    workspace = Path(workspace or get_config().get("project_directory", "."))
    results: list[dict[str, Any]] = []
    for candidate in candidates:
        action = candidate.get("action") or ""
        if executor is not None:
            ok = bool(executor(candidate))
            detail = "injected executor"
        elif action.startswith("git revert"):
            sha = candidate.get("commit")
            ok = bool(sha) and _git_revert(workspace, sha)
            detail = f"git revert {sha}" if sha else "no commit recorded"
        else:
            ok = False
            detail = "undo_proposal executor not wired"
        results.append({**candidate, "ok": ok, "detail": detail, "workspace": str(workspace)})
    return results


def _git_revert(workspace: Path, sha: str) -> bool:
    try:
        proc = subprocess.run(
            ["git", "revert", "--no-edit", sha],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=60,
        )
        return proc.returncode == 0
    except Exception:
        return False


def run_evolve_session(
    iterations: list[int] | tuple[int, ...],
    *,
    run_benchmark_fn: Callable[..., Any] | None = None,
    tasks: Any = None,
    propose: Callable[..., Any] | None = None,
    reviewer: Callable[..., Any] | None = None,
    budget: EvolveBudget | None = None,
    task_id: str | None = None,
    prompt_root: str | Path | None = None,
    enabled_check: bool = True,
) -> dict[str, Any]:
    """A full evolve session: bench iteration t → evolve → bench t+1 → reverts.

    Honors the ``evolve.enabled`` config gate unless ``enabled_check=False``
    (tests). ``run_benchmark_fn`` defaults to the benchmark driver's
    ``run_benchmark`` (task fixture set via ``tasks``).
    """
    cfg = load_evolve_config()
    if enabled_check and not cfg["enabled"]:
        return {"status": "disabled", "message": "evolve.enabled is false"}

    if run_benchmark_fn is None:
        from .benchmark.driver import run_benchmark as _driver_run

        run_benchmark_fn = _driver_run

    budget = budget or budget_from_config(cfg)
    iter_list = sorted(int(i) for i in iterations)
    steps: list[EvolveResult] = []
    results_by_iter: dict[int, dict[str, Any]] = {}
    for it in iter_list:
        if budget.exhausted:
            break
        r = run_benchmark_fn(it, tasks) if tasks is not None else run_benchmark_fn(it)
        results_by_iter[it] = r or {}
        step = run_evolve_iteration(
            it,
            results=results_by_iter[it],
            propose=propose,
            reviewer=reviewer,
            budget=budget,
            task_id=task_id,
            prompt_root=prompt_root,
        )
        steps.append(step)

    reverts: list[dict[str, Any]] = []
    if len(iter_list) >= 2:
        for a, b in itertools.pairwise(iter_list):
            reverts.extend(run_evolve_reverts(a, b))

    return {
        "status": "ok",
        "iterations": iter_list,
        "results_by_iter": results_by_iter,
        "steps": [vars(s) for s in steps],
        "reverts": reverts,
        "budget": vars(budget),
    }
