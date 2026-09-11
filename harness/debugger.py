"""Debugger producer for §12.3 (HARNESS_EVOLUTION_DESIGN §4.3).

A support-layer worker (the ``parallel_workers`` pattern) that consumes the
cleaned trajectory corpus and emits a grounded per-task report. Every root
cause names an evidence file and a ``component_hint`` from the fixed enum
(`harness.verify.COMPONENT_HINTS`), so the Evolve Agent can attribute a
failure to the harness without blaming a flaky endpoint (Soak18 confound).

The LLM interaction is one-shot per task: the cleaned frames are sampled into
a bounded prompt, the model returns a JSON report (see ``DEBUGGER_PROMPT``),
which is parsed and enum-validated. Any failure degrades to a report with an
explicit ``inference_error`` — never fabricated evidence.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any

from harness.verify import COMPONENT_HINTS

DEBUGGER_PROMPT = """You are the Agent Debugger. Read {task_id}'s cleaned trajectory frames below.
Produce ONLY a JSON report with exactly these keys:
- task_id: string
- passed: true or false
- root_causes: [ {{ "evidence_file": string, "inferred_root_cause": string, "component_hint": string }} ]
- success_patterns: [ string ]

component_hint must be one of: harness_prompt | tool | middleware | skill | memory |
subagent | worktree | endpoint | task_contract | parallel_worker | database | verifier.

Ground every claim in a file path present in the frames. Do not speculate past the evidence."""

_HINT_LIST = " | ".join(sorted(COMPONENT_HINTS))

DEFAULT_MAX_FRAMES = 24
DEFAULT_MAX_CONTENT = 2000


@dataclass(frozen=True)
class RootCause:
    evidence_file: str
    inferred_root_cause: str
    component_hint: str

    def __post_init__(self) -> None:
        if not self.component_hint or self.component_hint not in COMPONENT_HINTS:
            raise ValueError(f"unknown component_hint: {self.component_hint!r}")


@dataclass(frozen=True)
class DebuggerReport:
    task_id: str
    passed: bool | None = None
    root_causes: tuple[RootCause, ...] = ()
    success_patterns: tuple[str, ...] = ()
    inference_error: str = ""


def _extract_json(text: str) -> dict[str, Any] | None:
    """Best-effort JSON extraction tolerating ```json fences and prose."""
    if not text:
        return None
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        obj = json.loads(text[start : end + 1])
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def parse_report(task_id: str, text: str) -> DebuggerReport:
    """Parse + validate a Debugger LLM response; never raises."""
    obj = _extract_json(text)
    if obj is None:
        return DebuggerReport(task_id, inference_error="unparseable_report")
    passed = obj.get("passed")
    if isinstance(passed, bool):
        pass_bool = passed
    else:
        presented = str(passed).strip().lower() if passed is not None else ""
        pass_bool = presented == "true" if presented in {"true", "false"} else None

    root_causes: list[RootCause] = []
    invalid_hints: set[str] = set()
    for rc in obj.get("root_causes") or []:
        if not isinstance(rc, dict):
            continue
        hint = str(rc.get("component_hint") or "")
        if hint not in COMPONENT_HINTS:
            invalid_hints.add(hint)
            continue
        root_causes.append(
            RootCause(
                evidence_file=str(rc.get("evidence_file") or ""),
                inferred_root_cause=str(rc.get("inferred_root_cause") or ""),
                component_hint=hint,
            )
        )

    success_patterns = tuple(str(p) for p in (obj.get("success_patterns") or []) if str(p).strip())

    report = DebuggerReport(
        task_id=task_id,
        passed=pass_bool,
        root_causes=tuple(root_causes),
        success_patterns=success_patterns,
    )
    if invalid_hints:
        return DebuggerReport(
            task_id=task_id,
            passed=pass_bool,
            root_causes=tuple(root_causes),
            success_patterns=success_patterns,
            inference_error=f"invalid_component_hints:{','.join(sorted(invalid_hints))}",
        )
    if obj.get("task_id") and str(obj.get("task_id")) != task_id:
        return DebuggerReport(
            task_id=task_id,
            passed=pass_bool,
            root_causes=tuple(root_causes),
            success_patterns=success_patterns,
            inference_error=f"task_id_mismatch:{obj.get('task_id')}",
        )
    return report


def sample_frames(
    frames: list[dict[str, Any]],
    *,
    max_frames: int = DEFAULT_MAX_FRAMES,
    max_content: int = DEFAULT_MAX_CONTENT,
) -> list[dict[str, Any]]:
    """Bound the Debugger prompt: cap frame count and per-frame content size."""
    sampled = list(frames[:max_frames])
    for idx, frame in enumerate(sampled):
        content = frame.get("content") or ""
        if len(content) > max_content:
            truncated = dict(frame)
            truncated["content"] = content[:max_content] + "\n...[truncated]"
            sampled[idx] = truncated
    return sampled


def render_debugger_messages(
    task_id: str,
    frames: list[dict[str, Any]],
    *,
    max_frames: int = DEFAULT_MAX_FRAMES,
    max_content: int = DEFAULT_MAX_CONTENT,
) -> list[dict[str, str]]:
    system = DEBUGGER_PROMPT.replace("{task_id}", task_id)
    sampled = sample_frames(frames, max_frames=max_frames, max_content=max_content)
    lines = []
    for frame in sampled:
        role = frame.get("role") or "?"
        turn = frame.get("turn") or 0
        lines.append(f"[{role} turn {turn}]\n{frame.get('content') or ''}")
    user = "\n\n".join(lines) if lines else "(no frames)"
    return [
        {"role": "system", "content": system + f"\n\nVALID component_hints: {_HINT_LIST}"},
        {"role": "user", "content": user},
    ]


def _default_llm(messages: list[dict], model: str | None, task_id: str, agent_name: str):
    from agents.base import call_endpoint

    return call_endpoint(
        messages,
        model=model,
        task_id=task_id,
        agent_name=agent_name,
    )


def analyze_task(
    task_id: str,
    frames: list[dict[str, Any]],
    *,
    model: str | None = None,
    llm: Callable[..., tuple[str | None, int]] | None = None,
) -> DebuggerReport:
    """Analyze one task's cleaned frames via the Debugger model call.

    ``llm`` mirrors ``call_endpoint``'s signature and is injectable for tests.
    Never raises: LLM / parse failures become ``inference_error`` reports.
    """
    messages = render_debugger_messages(task_id, frames)
    try:
        text, _tokens = (llm or _default_llm)(
            messages,
            model=model,
            task_id=f"debugger:{task_id}",
            agent_name="debugger",
        )
    except Exception as e:
        return DebuggerReport(task_id, inference_error=f"llm_error:{type(e).__name__}:{e}")
    if not text or not text.strip():
        return DebuggerReport(task_id, inference_error="empty_llm_response")
    return parse_report(task_id, text)


def run_producer(
    frames_by_task: dict[str, list[dict[str, Any]]],
    *,
    model: str | None = None,
    llm: Callable[..., tuple[str | None, int]] | None = None,
    max_workers: int = 4,
) -> dict[str, DebuggerReport]:
    """Analyze every task in parallel (support-worker pattern, order preserved)."""
    reports: dict[str, DebuggerReport] = {}
    if not frames_by_task:
        return reports
    with ThreadPoolExecutor(max_workers=max(max_workers, 1)) as pool:
        futures = {pool.submit(analyze_task, task_id, frames, model=model, llm=llm): task_id for task_id, frames in frames_by_task.items()}
        for future in as_completed(futures):
            reports[futures[future]] = future.result()
    return {task_id: reports[task_id] for task_id in frames_by_task}


def render_analysis_md(task_id: str, report: DebuggerReport) -> str:
    """Per-task markdown where every claim carries a file path + component_hint."""
    lines = [
        f"# {task_id}",
        "",
        f"- passed: {report.passed if report.passed is not None else 'unknown'}",
    ]
    if report.inference_error:
        lines += ["- inference_error: " + report.inference_error]
    lines += [""]

    if report.root_causes:
        lines += ["## Root causes", ""]
        for rc in report.root_causes:
            evidence = rc.evidence_file or "(no evidence file)"
            lines += [
                f"- **{rc.component_hint}** — {rc.inferred_root_cause}",
                f"  - evidence: `{evidence}`",
            ]
        lines += [""]
    if report.success_patterns:
        lines += ["## Success patterns", ""]
        for pattern in report.success_patterns:
            lines += [f"- {pattern}"]
        lines += [""]

    lines += [f"[cleaned corpus](cleaned/{task_id}.jsonl)", ""]
    return "\n".join(lines)
