"""§12.3 trajectory-corpus pipeline: clean → Debugger-analyze → aggregate.

Emits the §4.1 layered layout under ``runs/<iter>/``:

    cleaned/<task_id>.jsonl      # base64-drop + consecutive-dedup frames
    analysis/<task_id>.md        # per-task Debugger report (grounded claims)
    overview.md                  # benchmark-level aggregation (entry point)
    index.json                   # drill-down map: overview -> tasks -> traces

The raw ``shell_trajectories`` (``raw_dir``) stay untouched. `results.json`
verdicts are cross-referenced when available: the driver writes rollout task
ids as ``<base>_i<iter>_t<trial>``, so per-trial verdicts map onto the corpus.

CLI: ``python -m harness.corpus --iter N --raw <dir> --runs <runs/iter_N>``
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from harness.cleaning import clean_task_into, group_raw_by_task
from harness.debugger import DebuggerReport, render_analysis_md, run_producer


def _trial_task_ids(results: dict[str, Any] | None, iteration: int) -> dict[str, str]:
    """Flatten results.json trials into ``{rollout_task_id: verdict}``."""
    flat: dict[str, str] = {}
    for task in (results or {}).get("tasks") or []:
        task_id = str(task.get("task_id") or "")
        for trial in task.get("trials") or []:
            t = int(trial.get("trial") or 0)
            rollout_id = f"{task_id}_i{iteration}_t{t}"
            flat[rollout_id] = str(trial.get("verdict") or "")
    return flat


def load_results(path: str | Path | None) -> dict[str, Any] | None:
    if not path:
        return None
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return None


def _aggregate_counts(reports: dict[str, DebuggerReport]):
    passed = sum(1 for r in reports.values() if r.passed)
    failed = sum(1 for r in reports.values() if r.passed is False)
    unknown = sum(1 for r in reports.values() if r.passed is None)
    return {"reports": len(reports), "passed": passed, "failed": failed, "unknown": unknown}


def _group_failures(reports: dict[str, DebuggerReport]) -> dict[str, list[str]]:
    by_hint: dict[str, list[str]] = {}
    for task_id, report in reports.items():
        if report.passed is not False:
            continue
        for rc in report.root_causes:
            by_hint.setdefault(rc.component_hint, []).append(task_id)
    return {hint: sorted(tasks) for hint, tasks in by_hint.items()}


def _group_successes(reports: dict[str, DebuggerReport]) -> dict[str, list[str]]:
    by_pattern: dict[str, list[str]] = {}
    for task_id, report in reports.items():
        if report.passed is not True:
            continue
        for pattern in report.success_patterns:
            tag = pattern[:80]
            by_pattern.setdefault(tag, []).append(task_id)
    return {pattern: sorted(tasks) for pattern, tasks in by_pattern.items()}


def render_overview_md(
    iteration: int,
    reports: dict[str, DebuggerReport],
    verdicts: dict[str, str],
) -> str:
    counts = _aggregate_counts(reports)
    lines = [
        f"# Benchmark iteration {iteration} — trajectory corpus overview",
        "",
        f"- reports: {counts['reports']}",
        f"- passed: {counts['passed']}",
        f"- failed: {counts['failed']}",
        f"- unknown: {counts['unknown']}",
        "",
    ]

    failures = _group_failures(reports)
    if failures:
        lines += ["## Failing tasks by component_hint", ""]
        for hint in sorted(failures):
            lines.append(f"### {hint}")
            for task_id in failures[hint]:
                lines.append(f"- [{task_id}](analysis/{task_id}.md)")
        lines += [""]

    successes = _group_successes(reports)
    if successes:
        lines += ["## Passing tasks by success pattern", ""]
        for pattern in sorted(successes):
            lines.append(f"### {pattern}")
            for task_id in successes[pattern]:
                lines.append(f"- [{task_id}](analysis/{task_id}.md)")
        lines += [""]

    lines += ["## All tasks", "", "| task | debugger passed | verdict |", "|---|---|---|"]
    for task_id in sorted(reports):
        report = reports[task_id]
        verdict = verdicts.get(task_id) or ""
        passed = "unknown" if report.passed is None else str(report.passed).lower()
        label = f"[{task_id}](analysis/{task_id}.md)"
        lines.append(f"| {label} | {passed} | {verdict} |")
    lines += ["", "Drill down: [index.json](index.json) -> tasks -> raw traces.", ""]
    return "\n".join(lines)


def render_index_json(
    iteration: int,
    reports: dict[str, DebuggerReport],
    raw_by_task: dict[str, list[Path]],
    verdicts: dict[str, str],
    generated_at: str,
) -> dict[str, Any]:
    tasks: dict[str, Any] = {}
    for task_id, report in reports.items():
        causes = [rc.component_hint for rc in report.root_causes]
        tasks[task_id] = {
            "passed": report.passed,
            "verdict": verdicts.get(task_id),
            "component_hints": sorted(set(causes)) or None,
            "analysis": f"analysis/{task_id}.md",
            "cleaned": f"cleaned/{task_id}.jsonl",
            "raw": [p.name for p in raw_by_task.get(task_id, [])],
            "inference_error": report.inference_error or None,
        }
    return {
        "iteration": iteration,
        "entry": "overview.md",
        "generated_at": generated_at,
        "tasks": tasks,
    }


def produce_corpus(
    iteration: int,
    *,
    raw_dir: str | Path,
    runs_dir: str | Path,
    results: dict[str, Any] | None = None,
    llm: Callable[..., tuple[str | None, int]] | None = None,
    model: str | None = None,
    max_workers: int = 4,
) -> dict[str, Any]:
    """Run the clean → analyze → aggregate pipeline; returns artifact summary.

    ``llm`` defaults to the real ``agents.base.call_endpoint``; tests inject a
    stub. Raw trajectory files are never modified.
    """
    runs_path = Path(runs_dir)
    cleaned_dir = runs_path / "cleaned"
    analysis_dir = runs_path / "analysis"
    cleaned_dir.mkdir(parents=True, exist_ok=True)
    analysis_dir.mkdir(parents=True, exist_ok=True)

    raw_by_task = group_raw_by_task(raw_dir)
    frames_by_task: dict[str, list[dict[str, Any]]] = {}
    for task_id, raw_files in raw_by_task.items():
        frames_by_task[task_id] = clean_task_into(task_id, raw_files, cleaned_dir)

    reports = run_producer(frames_by_task, llm=llm, model=model, max_workers=max_workers)

    for task_id, report in reports.items():
        (analysis_dir / f"{task_id}.md").write_text(render_analysis_md(task_id, report), encoding="utf-8")

    verdicts = _trial_task_ids(results, iteration)
    generated_at = datetime.now(timezone.utc).isoformat()

    (runs_path / "overview.md").write_text(render_overview_md(iteration, reports, verdicts), encoding="utf-8")
    (runs_path / "index.json").write_text(
        json.dumps(render_index_json(iteration, reports, raw_by_task, verdicts, generated_at), indent=2),
        encoding="utf-8",
    )

    return {
        "iteration": iteration,
        "runs_dir": str(runs_path),
        "cleaned": len(frames_by_task),
        "analysis": len(reports),
        "overview": str(runs_path / "overview.md"),
        "index": str(runs_path / "index.json"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="harness.corpus", description="§12.3 trajectory corpus")
    parser.add_argument("--iter", type=int, required=True, help="benchmark iteration number")
    parser.add_argument("--raw", type=Path, required=True, help="raw shell_trajectories dir")
    parser.add_argument("--runs", type=Path, required=True, help="runs/<iter> dir (emitted into)")
    parser.add_argument("--results", type=Path, default=None, help="results.json for verdict cross-ref")
    parser.add_argument("--model", type=str, default=None, help="model ref for the Debugger")
    parser.add_argument("--max-workers", type=int, default=4, help="parallel Debugger workers")
    args = parser.parse_args(argv)

    summary = produce_corpus(
        args.iter,
        raw_dir=args.raw,
        runs_dir=args.runs,
        results=load_results(args.results),
        model=args.model,
        max_workers=args.max_workers,
    )
    print(
        f"corpus iter={summary['iteration']}: cleaned={summary['cleaned']} "
        f"analysis={summary['analysis']} overview={summary['overview']} index={summary['index']}"
    )
    return 0 if summary["analysis"] else 1


if __name__ == "__main__":
    sys.exit(main())
