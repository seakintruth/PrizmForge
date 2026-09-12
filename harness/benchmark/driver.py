"""Sequential driver for the v1 boxed benchmark (docs/benchmark_v1.md §4).

Runs each canonical task ``k`` times back-to-back against the shared DB writer,
tagging every trial as a §12.1 rollout, verifying the content contract, and
emitting ``runs/<iter>/results.json`` with pass@1 + failure-mode split.
"""

from __future__ import annotations

import json
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from harness.benchmark.config import use_bench_config
from harness.benchmark.tasks import BenchTask
from harness.fingerprint import create_rollout, failure_mode_mix, finalize_rollout, latest_rollout
from harness.verify import FAILED, Verdict, record_verdict, verify_trial


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


def scrub_governed_store(fixture_paths) -> None:
    """Soft-delete governed files/lines not part of the upcoming fixture.

    Trials of one iteration share a single DB (and its task/rollout rows are
    the iteration's evidence), but the *content* governed for non-fixture paths
    must not carry over: a file a previous trial's agent created could
    otherwise satisfy the next trial's `contains`/`absent` assertions.
    """
    fixture_paths = {str(p) for p in fixture_paths}
    if not fixture_paths:
        return
    from file_editing.db import get_db_connection

    placeholders = ",".join("?" * len(fixture_paths))
    params = list(fixture_paths)
    with get_db_connection() as conn:
        conn.execute(
            f"UPDATE file_lines SET is_deleted = 1 WHERE file_id IN (SELECT file_id FROM files WHERE file_path NOT IN ({placeholders}))",  # noqa: S608 - static "?" placeholders, values parameterized
            params,
        )
        conn.execute(
            f"UPDATE files SET is_deleted = 1 WHERE file_path NOT IN ({placeholders})",  # noqa: S608 - static "?" placeholders, values parameterized
            params,
        )


@contextmanager
def _iteration_db(bench_dir: Path):
    """Pin one DB per benchmark iteration (unless an outer actor pinned it).

    With per-trial project dirs, the config-derived DB would move per trial.
    Pin ``PRIZMFORGE_DB_PATH`` to ``<bench_dir>/.PrizmForge/agents.db`` for the
    run when nothing external already pinned it, so rollouts/verdicts aggregate
    per iteration while each trial still starts from a scrubbed store.
    """
    import os

    pinned = os.environ.get("PRIZMFORGE_DB_PATH")
    if pinned:
        yield Path(pinned)
        return

    db_path = bench_dir / ".PrizmForge" / "agents.db"
    from core.db import init_db

    os.environ["PRIZMFORGE_DB_PATH"] = str(db_path)
    try:
        init_db()
        yield db_path
    finally:
        if os.environ.get("PRIZMFORGE_DB_PATH") == str(db_path):
            del os.environ["PRIZMFORGE_DB_PATH"]


def _task_status(task_id: str) -> str | None:
    from core.db_connection import get_db_connection

    try:
        with get_db_connection() as conn:
            row = conn.execute("SELECT status FROM tasks WHERE id = ?", (task_id,)).fetchone()
            return str(row[0]) if row else None
    except Exception:
        return None


def run_trial(
    task: BenchTask,
    iteration: int,
    trial: int,
    max_turns: int,
    project_dir: str | Path,
    *,
    trial_timeout_s: float | None = None,
) -> dict[str, Any]:
    """Run one task instance in an isolated trial dir; returns the result dict.

    ``project_dir`` is a fresh per-trial workspace (caller creates it). Before
    writing fixtures the shared iteration DB is scrubbed of any non-fixture
    governed content. When ``trial_timeout_s`` is set, the task cycle runs on a
    daemon thread and is abandoned (and recorded ``timed_out``) past the bound
    — a bounding guard for a genuinely hung run, not a clean cancel.
    """
    from workflow.task_runner import run_task_cycle

    task_id = f"{task.task_id}_i{iteration}_t{trial}"
    scrub_governed_store(task.fixture)
    write_fixtures(task, project_dir)
    create_rollout(task_id, iteration=iteration)

    def _cycle() -> None:
        try:
            run_task_cycle(task_id, task.seed, max_turns=max_turns)
        except KeyboardInterrupt:
            raise
        except Exception as e:
            print(f"   ⚠️  run_task_cycle raised for {task_id}: {e}")

    overran = False
    if trial_timeout_s:
        import threading

        worker = threading.Thread(target=_cycle, daemon=True)
        worker.start()
        worker.join(timeout=trial_timeout_s)
        overran = worker.is_alive()
    else:
        _cycle()

    finalize_rollout(task_id, "timed_out" if overran else (_task_status(task_id) or "failed"))
    rollout = latest_rollout(task_id)
    if overran:
        verdict = Verdict(FAILED, note="status:trial-timeout", component_hint="task_contract")
    else:
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
    trial_timeout_s: float | None = None,
    iteration_timeout_s: float | None = None,
) -> dict[str, Any]:
    """Run the benchmark; returns the aggregated results dict (also persisted).

    One bench dir (random subdir of ``project_dir``) hosts one iteration: a
    single pinned DB aggregates the trial rollouts/verdicts, while every trial
    gets a fresh project subdir and a scrubbed governed store (no cross-trial
    leakage of agent-created files). ``trial_timeout_s`` / ``iteration_timeout_s``
    bound a hung run; the config is swapped to a hermetic bench config for the
    duration.
    """
    base = Path(project_dir) if project_dir else prepare_workspace(Path("."))
    bench_dir = prepare_workspace(base)

    deadline = time.monotonic() + iteration_timeout_s if iteration_timeout_s else None
    capped = False

    all_trials: list[dict[str, Any]] = []
    per_task: list[dict[str, Any]] = []
    passed = 0
    total = 0

    with _iteration_db(bench_dir):
        for task in tasks:
            task_rows: list[dict[str, Any]] = []
            for t in range(1, max(1, task.k) + 1):
                if deadline and time.monotonic() > deadline:
                    capped = True
                    break
                trial_dir = prepare_workspace(bench_dir)
                with use_bench_config(trial_dir):
                    tr = run_trial(
                        task,
                        iteration,
                        t,
                        max_turns,
                        trial_dir,
                        trial_timeout_s=trial_timeout_s,
                    )
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
                    "timed_out": sum(1 for r in task_rows if "timed_out" in r["note"]),
                    "trials": task_rows,
                }
            )
            if capped:
                break

        mix = failure_mode_mix(iteration)
        results: dict[str, Any] = {
            "iteration": iteration,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "max_turns": max_turns,
            "trial_timeout_s": trial_timeout_s,
            "iteration_timeout_s": iteration_timeout_s,
            "capped": capped,
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
