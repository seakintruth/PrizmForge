"""v1 boxed benchmark package (docs/benchmark_v1.md, docs/TODO.md §12.2)."""

from harness.benchmark.driver import run_benchmark, run_trial
from harness.benchmark.tasks import (
    BenchTask,
    ContentAssertion,
    load_default_tasks,
    load_task_manifest,
)

__all__ = [
    "BenchTask",
    "ContentAssertion",
    "load_default_tasks",
    "load_task_manifest",
    "run_benchmark",
    "run_trial",
]
