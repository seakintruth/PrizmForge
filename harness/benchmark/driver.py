"""Sequential driver for the v1 boxed benchmark (docs/benchmark_v1.md §4).

Runs each canonical task ``k`` times back-to-back against the shared DB writer,
tagging every trial as a §12.1 rollout, verifying the content contract, and
emitting ``runs/<iter>/results.json`` with pass@1 + failure-mode split.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from harness.benchmark.config import use_bench_config
from harness.benchmark.tasks import BenchTask
from harness.fingerprint import create_rollout, failure_mode_mix, finalize_rollout, latest_rollout
from harness.verify import record_verdict, verify_trial


def _mkdtemp(base: str | Path) -> Path:
    import tempfile

    Path(base).mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix="bench-", dir=str(base)))


def prepare_workspace(base: str | Path) -> Path:
    """Create a fresh bench project dir for one benchmark iteration."""
    return _mkdtemp(base)


def write_fixtures(task: BenchTask, project_dir: str | Path) -> None:
    """Write fixture files to disk and into the governed DB (per-trial base)."""
    from file_editing.writer import initialize_file_lines

    for rel_path, content in task.fixture.items():
        f = Path(project_dir) / rel_path
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(content, encoding="utf-8")
        initialize_file_lines(rel_path, content)


def _task_status(task_id: str) -> str | None:
    from core.db_connection import get_db_connection

    try:
        with get_db_connection() as conn:
            row = conn.execute("SELECT status FROM tasks WHERE id = ?", (task_id,)).fetchone()
            return str(row[0]) if row else None
    except Exception:
        return None


def run_trial(task: BenchTask, iteration: int, trial: int, max_turns: int, project_dir: str | Path) -> dict[str, Any]:
    """Run one task instance; returns the trial result dict."""
    from workflow.task_runner import run_task_cycle

    task_id = f"{task.task_id}_i{iteration}_t{trial}"
    write_fixtures(task, project_dir)
    create_rollout(task_id, iteration=iteration)

    try:
        run_task_cycle(task_id, task.seed, max_turns=max_turns)
    except KeyboardInterrupt:
        raise
    except Exception as e:
        print(f"   ⚠️  run_task_cycle raised for {task_id}: {e}")

    finalize_rollout(task_id, _task_status(task_id) or "failed")
    rollout = latest_rollout(task_id)
    verdict = verify_trial(task, rollout)
    if rollout is not None:
        record_verdict(int(rollout["rollout_id"]), verdict, task.contract_hash)

    return {
        "trial": trial,
        "verdict": verdict.verdict,
        "note": verdict.note,
        "tokens": rollout.get("tokens") if rollout else None,
        "infra_abort": rollout.get("infra_abort") if rollout else 0,
    }


def run_benchmark(
    iteration: int,
    tasks: list[BenchTask],
    *,
    max_turns: int = 5,
    project_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Run the benchmark; returns the aggregated results dict (also persisted).

    Sequences trials one per rollout row tagged with ``iteration``. The config
    is temporarily swapped to a hermetic bench config for the duration.
    """
    base = Path(project_dir) if project_dir else prepare_workspace(Path("."))
    bench_dir = prepare_workspace(base)

    all_trials: list[dict[str, Any]] = []
    per_task: list[dict[str, Any]] = []
    passed = 0
    total = 0

    with use_bench_config(bench_dir):
        for task in tasks:
            task_rows: list[dict[str, Any]] = []
            for t in range(1, max(1, task.k) + 1):
                tr = run_trial(task, iteration, t, max_turns, bench_dir)
                task_rows.append(tr)
                all_trials.append(tr)
                total += 1
                if tr["verdict"] == "passed":
                    passed += 1
            per_task.append(
                {
                    "task_id": task.task_id,
                    "k": len(task_rows),
                    "passed": sum(1 for r in task_rows if r["verdict"] == "passed"),
                    "infra_aborted": sum(1 for r in task_rows if r["verdict"] == "infra_aborted"),
                    "trials": task_rows,
                }
            )

    mix = failure_mode_mix(iteration)
    results: dict[str, Any] = {
        "iteration": iteration,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "max_turns": max_turns,
        "pass@1": round(passed / total, 4) if total else 0.0,
        "passed_trials": passed,
        "total_trials": total,
        "failure_mode_mix": mix,
        "tasks": per_task,
    }

    runs_dir = bench_dir / "runs" / f"iter_{iteration}"
    runs_dir.mkdir(parents=True, exist_ok=True)
    results["runs_dir"] = str(runs_dir)
    (runs_dir / "results.json").write_text(json.dumps(results, indent=2, sort_keys=True), encoding="utf-8")
    return results


def _fmt(results: dict[str, Any]) -> str:
    lines = [
        f"iteration    : {results['iteration']}",
        f"pass@1       : {results['pass@1']:.2%} ({results['passed_trials']}/{results['total_trials']})",
        f"mix rollouts : {results['failure_mode_mix'].get('rollouts', 0)}",
        f"mix passed   : {results['failure_mode_mix'].get('passed', 0)}",
        f"mix infra    : {results['failure_mode_mix'].get('infra_aborted', 0)}",
    ]
    return "\n".join(lines)
