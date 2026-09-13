"""
tests/integration/test_benchmark_driver_cycle.py

End-to-end coverage for the §12.2 boxed benchmark (docs/benchmark_v1.md):
a real ``run_benchmark`` over crafted tasks with a mocked LLM proves the
run_task_cycle → rollout → verifier → results.json pipeline, including a
genuine FAIL(content) case (task "passed" but governed content unchanged).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

pytestmark = pytest.mark.slow


@pytest.fixture
def bench_env(temp_db, tmp_path):
    project_dir = tmp_path / "bench"
    project_dir.mkdir()

    try:
        from agents.parallel_workers import get_agent_pool

        pool = get_agent_pool()
        if getattr(pool, "running", False):
            pool.stop()
    except Exception:
        pass

    yield project_dir

    try:
        from agents.parallel_workers import get_agent_pool

        get_agent_pool().stop()
    except Exception:
        pass


def _rename_task(k: int = 1):
    from harness.benchmark.tasks import parse_bench_task

    return parse_bench_task(
        {
            "task_id": "t01_rename_constant",
            "seed": "Rename OLD to NEW in app.py",
            "fixture": {"app.py": "value = OLD\n"},
            "contract": [{"file_path": "app.py", "fragment": "value = NEW\n", "mode": "contains"}],
            "k": k,
        }
    )


def _solve_responses(mock_llm) -> None:
    mock_llm.set_responses(
        "orchestrator",
        [
            json.dumps(
                {
                    "next_agent": "developer",
                    "instructions": "Rename OLD to NEW in app.py",
                    "files_needed": ["app.py"],
                    "reasoning": "rename",
                }
            ),
            json.dumps({"next_agent": "complete", "instructions": "done", "reasoning": "finished"}),
            json.dumps({"next_agent": "complete", "instructions": "done", "reasoning": "finished"}),
            json.dumps({"next_agent": "complete", "instructions": "done", "reasoning": "finished"}),
        ],
    )
    mock_llm.set_responses(
        "developer",
        [
            "FILES_NEEDED: app.py\nPLAN: rename",
            json.dumps(
                {
                    "target_file_path": "app.py",
                    "summary": "rename OLD to NEW",
                    "rationale": "Consistent spec for the application constant",
                    "operations": [
                        {
                            "type": "find_replace",
                            "find": "OLD",
                            "replace": "NEW",
                            "rationale": "Consistent spec for the constant",
                        }
                    ],
                }
            ),
        ],
    )
    mock_llm.set_response(
        "reviewer",
        json.dumps({"decision": "APPROVE", "reason": "safe", "suggestions": []}),
    )


def _noop_responses(mock_llm) -> None:
    """Orchestrator completes immediately — no edits, no files touched."""
    mock_llm.set_responses(
        "orchestrator",
        [
            json.dumps({"next_agent": "complete", "instructions": "done", "reasoning": "nothing to do"}),
            json.dumps({"next_agent": "complete", "instructions": "done", "reasoning": "nothing to do"}),
            json.dumps({"next_agent": "complete", "instructions": "done", "reasoning": "nothing to do"}),
        ],
    )


def test_run_benchmark_solves_task(mock_llm, bench_env):
    """The full pipeline labels a solved trial 'passed' with pass@1 == 1.0."""
    from harness.benchmark.driver import run_benchmark

    _solve_responses(mock_llm)

    with mock_llm.patch_call_agent():
        results = run_benchmark(
            iteration=21,
            tasks=[_rename_task(k=1)],
            max_turns=3,
            project_dir=bench_env,
        )

    assert results["total_trials"] == 1
    assert results["passed_trials"] == 1
    assert results["pass@1"] == 1.0
    trial = results["tasks"][0]["trials"][0]
    assert trial["verdict"] == "passed"
    assert trial["note"] == "content_ok"

    results_file = Path(results["runs_dir"]) / "results.json"
    assert results_file.exists()
    on_disk = json.loads(results_file.read_text(encoding="utf-8"))
    assert on_disk["pass@1"] == 1.0


def test_run_benchmark_fails_when_content_untouched(mock_llm, bench_env):
    """Even a task the orchestrator 'completes' with no edit FAILS(content)."""
    from harness.benchmark.driver import run_benchmark

    _noop_responses(mock_llm)

    with mock_llm.patch_call_agent():
        results = run_benchmark(
            iteration=22,
            tasks=[_rename_task(k=1)],
            max_turns=3,
            project_dir=bench_env,
        )

    assert results["total_trials"] == 1
    assert results["passed_trials"] == 0
    assert results["pass@1"] == 0.0
    trial = results["tasks"][0]["trials"][0]
    assert trial["verdict"] == "failed"
    assert trial["note"] == "content:app.py:contains"


def _leak_task(k: int = 1):
    from harness.benchmark.tasks import parse_bench_task

    return parse_bench_task(
        {
            "task_id": "t10_create_leak",
            "seed": "Create leak.py with a secret module",
            "fixture": {"app.py": "value = OLD\n"},
            "contract": [{"file_path": "leak.py", "fragment": "secret = 1", "mode": "contains"}],
            "k": k,
        }
    )


def _absent_leak_task(k: int = 1):
    """Noop task whose only assertion is that the leaked path must NOT exist."""
    from harness.benchmark.tasks import parse_bench_task

    return parse_bench_task(
        {
            "task_id": "t11_absent_leak",
            "seed": "Do nothing to leak.py",
            "fixture": {"app.py": "value = OLD\n"},
            "contract": [{"file_path": "leak.py", "fragment": "secret = 1", "mode": "absent"}],
            "k": k,
        }
    )


def _leak_responses(mock_llm) -> None:
    """Trial 1 creates leak.py via a governed create_file op."""
    mock_llm.set_responses(
        "orchestrator",
        [
            json.dumps(
                {
                    "next_agent": "developer",
                    "instructions": "Create leak.py with a secret module",
                    "files_needed": ["app.py"],
                    "reasoning": "leak",
                }
            ),
            json.dumps({"next_agent": "complete", "instructions": "done", "reasoning": "finished"}),
            json.dumps({"next_agent": "complete", "instructions": "done", "reasoning": "finished"}),
            json.dumps({"next_agent": "complete", "instructions": "done", "reasoning": "finished"}),
        ],
    )
    mock_llm.set_responses(
        "developer",
        [
            "FILES_NEEDED: app.py\nPLAN: create",
            json.dumps(
                {
                    "target_file_path": "app.py",
                    "summary": "create leak module",
                    "rationale": "Leak module for trial-isolation test",
                    "operations": [
                        {
                            "type": "create_file",
                            "target_file_path": "leak.py",
                            "initial_content": ["secret = 1"],
                            "rationale": "leak",
                        }
                    ],
                }
            ),
        ],
    )
    mock_llm.set_response(
        "reviewer",
        json.dumps({"decision": "APPROVE", "reason": "safe", "suggestions": []}),
    )


def test_trials_are_isolated_from_previous_agent_files(mock_llm, bench_env):
    """A file one trial's agent creates must not satisfy the next trial.

    Trial 1 proves leak.py exists (contains passes); trial 2 asserts the same
    path must be absent. Isolation (fresh per-trial project dir + scrubbed
    governed store) makes trial 2 pass; without it the leftover leak.py would
    fail the `absent` assertion.
    """
    from harness.benchmark.driver import run_benchmark

    _leak_responses(mock_llm)  # orchestrator keeps returning 'complete' → trial 2 is a noop

    with mock_llm.patch_call_agent():
        results = run_benchmark(
            iteration=23,
            tasks=[_leak_task(k=1), _absent_leak_task(k=1)],
            max_turns=3,
            project_dir=bench_env,
        )

    assert results["total_trials"] == 2
    per_task = {t["task_id"]: t for t in results["tasks"]}
    leak_trial = per_task["t10_create_leak"]["trials"][0]
    assert leak_trial["verdict"] == "passed", leak_trial
    absent_trial = per_task["t11_absent_leak"]["trials"][0]
    assert absent_trial["verdict"] == "passed", absent_trial
    assert absent_trial["note"] == "content_ok"
