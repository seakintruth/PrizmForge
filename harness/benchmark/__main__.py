"""CLI entry: ``python -m harness.benchmark`` (docs/benchmark_v1.md §5)."""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="harness.benchmark", description="§12.2 v1 boxed benchmark")
    parser.add_argument("--iter", type=int, required=True, help="benchmark iteration number")
    parser.add_argument("--max-turns", type=int, default=5, help="max turns per trial")
    parser.add_argument("--tasks", type=Path, default=None, help="tasks.json path (default: package manifest)")
    parser.add_argument("--project-dir", type=Path, default=None, help="base dir for the bench workspace")
    parser.add_argument("--trial-timeout", type=float, default=None, help="per-trial wall-clock bound (seconds)")
    parser.add_argument("--iteration-timeout", type=float, default=None, help="hard per-iteration bound (seconds)")
    args = parser.parse_args(argv)

    from harness.benchmark.driver import _fmt, run_benchmark
    from harness.benchmark.tasks import load_default_tasks, load_task_manifest

    if args.tasks is not None:
        tasks = load_task_manifest(args.tasks)["tasks"]
    else:
        tasks = load_default_tasks()

    project_dir = args.project_dir or Path(tempfile.mkdtemp(prefix="harness-bench-"))
    results = run_benchmark(
        iteration=args.iter,
        tasks=tasks,
        max_turns=args.max_turns,
        project_dir=project_dir,
        trial_timeout_s=args.trial_timeout,
        iteration_timeout_s=args.iteration_timeout,
    )
    print(_fmt(results))
    return 0 if results["pass@1"] == 1.0 else 1


if __name__ == "__main__":
    sys.exit(main())
