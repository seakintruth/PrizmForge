"""§12.6 P3 attribution: baseline vs single-component swap deltas.

Benchmark runs are scripted (no LLM) — the JSON record, iteration numbering,
label plumbing, and delta math are what this pins.
"""

from __future__ import annotations

import json

import pytest

from harness.attribution import SwapSpec, run_attribution


def _scripted_results(iteration: int, pass1: float, n_tasks: int = 2) -> dict:
    return {
        "iteration": iteration,
        "pass@1": pass1,
        "passed_trials": round(pass1 * n_tasks),
        "total_trials": n_tasks,
        "model": "mock-model",
        "endpoint": "mock-model",
        "failure_mode_mix": {"rollouts": n_tasks, "passed": round(pass1 * n_tasks), "infra_aborted": 0},
        "tasks": [{"task_id": f"t0{idx}", "passed": 1 if idx < round(pass1 * n_tasks) else 0, "k": 1} for idx in range(n_tasks)],
    }


def _make_fake_runner():
    calls: list[dict] = []

    def runner(**kwargs):
        iteration = kwargs["iteration"]
        calls.append(kwargs)
        pass1 = {10: 0.5, 11: 0.5, 12: 1.0}[iteration]
        return _scripted_results(iteration, pass1, n_tasks=2)

    return runner, calls


class _Task:
    def __init__(self, task_id: str = "t"):
        self.task_id = task_id


def test_run_attribution_baseline_and_swap_deltas(tmp_path):
    runner, calls = _make_fake_runner()
    record = run_attribution(
        10,
        [_Task("a"), _Task("b")],
        [
            SwapSpec("mem-v1", "memory", {"memory": {"lessons": ["x"]}}),
            SwapSpec("tool-rename", "tool", {"attribution_tool": {"enabled": True}}),
        ],
        run_benchmark_fn=runner,
        record_dir=tmp_path,
    )

    # Two variants ran at baseline + rank.
    assert [c["iteration"] for c in calls] == [10, 11, 12]
    assert record["baseline"]["pass@1"] == 0.5
    assert record["swaps"][0]["label"] == "mem-v1"
    assert record["swaps"][0]["component"] == "memory"
    assert record["swaps"][0]["pass@1"] == 0.5
    assert record["swaps"][0]["delta"] == 0.0
    assert not record["swaps"][0]["better_than_baseline"]
    assert record["swaps"][1]["label"] == "tool-rename"
    assert record["swaps"][1]["component"] == "tool"
    assert record["swaps"][1]["delta"] == 0.5
    assert record["swaps"][1]["better_than_baseline"]
    assert record["best"]["label"] == "tool-rename"

    # The config overlay travelled with the attribution label attached.
    assert calls[1]["config_overrides"]["attribution"] == {"label": "mem-v1", "component": "memory"}
    assert calls[1]["config_overrides"]["memory"] == {"lessons": ["x"]}
    assert calls[2]["config_overrides"]["attribution"] == {"label": "tool-rename", "component": "tool"}

    # Baseline call carried no overlay.
    assert "config_overrides" not in calls[0] or not calls[0].get("config_overrides")

    # Record JSON on disk with fingerprint keys.
    path = tmp_path / "attribution-10.json"
    assert path.is_file()
    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert on_disk["harness_tag"]
    assert on_disk["prompt_hash"]
    assert on_disk["baseline"]["pass@1"] == 0.5
    assert len(on_disk["swaps"]) == 2


def test_run_attribution_all_swap_components_allowed():
    for component in ("memory", "tool", "middleware", "system_prompt"):
        SwapSpec(f"{component}-v1", component)
    with pytest.raises(ValueError):
        SwapSpec("bad", "endpoint")


def test_swap_requires_label():
    with pytest.raises(ValueError):
        SwapSpec("", "memory")


def test_run_attribution_no_swaps_still_records_baseline(tmp_path):
    runner, calls = _make_fake_runner()
    record = run_attribution(10, [_Task("a")], [], run_benchmark_fn=runner, record_dir=tmp_path)
    assert [c["iteration"] for c in calls] == [10]
    assert record["swaps"] == []
    assert record["best"] is None
    assert (tmp_path / "attribution-10.json").is_file()
