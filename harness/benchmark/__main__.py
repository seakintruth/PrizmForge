"""CLI entry: ``python -m harness.benchmark`` (docs/benchmark_v1.md §5, §13.7/§14.6)."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path


def _load_endpoints(path: str | None) -> dict:
    """Read the live endpoint config from a JSON file ({} when absent)."""
    if not path:
        return {}
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="harness.benchmark", description="§12.2 boxed benchmark")
    parser.add_argument("--iter", type=int, required=True, help="benchmark iteration number")
    parser.add_argument("--max-turns", type=int, default=5, help="max turns per trial")
    parser.add_argument("--tasks", type=Path, default=None, help="tasks.json path (default: package manifest)")
    parser.add_argument("--project-dir", type=Path, default=None, help="base dir for the bench workspace")
    parser.add_argument("--trial-timeout", type=float, default=None, help="per-trial wall-clock bound (seconds)")
    parser.add_argument("--iteration-timeout", type=float, default=None, help="hard per-iteration bound (seconds)")
    parser.add_argument(
        "--endpoints-json",
        type=Path,
        default=None,
        help="JSON file of live endpoint config (replaces the hermetic endpoints:{})",
    )
    parser.add_argument("--model", default=None, help="model name used for live trials")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="validate the manifest + an isolated DB; no LLM calls",
    )
    args = parser.parse_args(argv)

    from harness.benchmark.driver import _fmt_short, run_benchmark
    from harness.benchmark.tasks import load_default_tasks, load_task_manifest

    if args.tasks is not None:
        tasks = load_task_manifest(args.tasks)["tasks"]
    else:
        tasks = load_default_tasks()

    endpoints = _load_endpoints(str(args.endpoints_json) if args.endpoints_json else None)

    project_dir = args.project_dir or Path(tempfile.mkdtemp(prefix="harness-bench-"))
    results = run_benchmark(
        iteration=args.iter,
        tasks=tasks,
        max_turns=args.max_turns,
        project_dir=project_dir,
        trial_timeout_s=args.trial_timeout,
        iteration_timeout_s=args.iteration_timeout,
        endpoints=endpoints or None,
        model=args.model,
        dry_run=args.dry_run,
    )
    print(_fmt_short(results))
    if results.get("dry_run"):
        return 0
    return 0 if results["pass@1"] == 1.0 else 1


if __name__ == "__main__":
    sys.exit(main())
