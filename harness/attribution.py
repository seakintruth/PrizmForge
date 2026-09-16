"""§12.6 P3 attribution — single-component swaps (docs/TODO.md §12.6).

The Evolve loop proves a harness component moves behavior; attribution isolates
WHICH component moved pass@1. Each variant re-runs the same benchmark tasks with
one labelled config overlay (the "swap"), and this module records baseline vs
swap pass@1 + delta + the harness fingerprint so ``H_best <- H_t`` tracking has
a standalone artifact before any live loop.

Swap targets (docs/HARNESS_EVOLUTION_DESIGN.md §7): ``+ memory`` / ``+ tool`` /
``+ middleware`` / ``+ system_prompt``. The component *content* is produced by
the Evolve loop on disk (``harness/memory/*.md`` etc.); the attribution harness
owns the measurement + per-variant labelling, threaded into the bench config via
``run_benchmark(config_overrides=...)``. Until a component mount is real, a swap
still exercises the recording + delta path deterministically.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

#: Swap component vocabulary (subset of harness/verify.py COMPONENT_HINTS that
#: §12.6 ablates; endpoint/task_contract etc. are not operator swap targets).
SWAP_COMPONENTS: frozenset[str] = frozenset({"memory", "tool", "middleware", "system_prompt"})

DEFAULT_ATTRIBUTION_DIR = "harness/attribution"


@dataclass(frozen=True)
class SwapSpec:
    """One labelled config overlay (the "component" of the ablation)."""

    label: str
    component: str
    overrides: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.component not in SWAP_COMPONENTS:
            raise ValueError(f"unsupported swap component {self.component!r} (supported: {sorted(SWAP_COMPONENTS)})")
        if not self.label:
            raise ValueError("swap label is required")


def _variant_iteration(base_iteration: int, index: int) -> int:
    """Variant iteration number = baseline iteration + rank, so the per-variant
    ``runs/iter_<n>/`` dirs (and any rollout rows on a shared DB) stay distinct.
    """
    return base_iteration + index


def _default_run_benchmark(**kwargs: Any) -> dict[str, Any]:
    from harness.benchmark.driver import run_benchmark

    return run_benchmark(**kwargs)


def _summarize(iteration: int, results: dict[str, Any]) -> dict[str, Any]:
    """Reduce a run_benchmark results dict to the attribution-visible slice."""
    return {
        "iteration": iteration,
        "pass@1": results.get("pass@1", 0.0),
        "passed_trials": results.get("passed_trials", 0),
        "total_trials": results.get("total_trials", 0),
        "model": results.get("model"),
        "endpoint": results.get("endpoint"),
        "failure_mode_mix": results.get("failure_mode_mix"),
        "tasks": [
            {
                "task_id": t.get("task_id"),
                "passed": t.get("passed"),
                "k": t.get("k"),
            }
            for t in (results.get("tasks") or [])
        ],
    }


def run_attribution(
    iteration: int,
    tasks: list[Any],
    swaps: list[SwapSpec],
    *,
    run_benchmark_fn: Callable[..., dict[str, Any]] | None = None,
    project_dir: str | Path | None = None,
    max_turns: int = 5,
    endpoints: dict[str, Any] | None = None,
    model: str | None = None,
    record_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Measure baseline + per-swap pass@1, record, and return the attribution.

    Runs the baseline benchmark at ``iteration``, then one benchmark per swap at
    ``iteration + rank``. Variant runs reuse the same tasks and its config
    overlay is passed as ``config_overrides`` (default: a config key that names
    the swap so the record proves the overlay travelled). The attribution JSON
    is written under ``record_dir`` (default ``harness/attribution/``) with the
    harness fingerprint so results are comparable across runs/commits.
    """
    run = run_benchmark_fn or _default_run_benchmark

    from harness.fingerprint import compute_harness_fingerprint

    fingerprint = compute_harness_fingerprint()

    baseline = run(
        iteration=iteration,
        tasks=tasks,
        max_turns=max_turns,
        project_dir=project_dir,
        endpoints=endpoints,
        model=model,
    )
    base_pass1 = float(baseline.get("pass@1") or 0.0)

    variant_rows: list[dict[str, Any]] = []
    for index, swap in enumerate(swaps, start=1):
        var_iter = _variant_iteration(iteration, index)
        overlay = dict(swap.overrides or {})
        overlay.setdefault("attribution", {"label": swap.label, "component": swap.component})
        results = run(
            iteration=var_iter,
            tasks=tasks,
            max_turns=max_turns,
            project_dir=project_dir,
            endpoints=endpoints,
            model=model,
            config_overrides=overlay,
        )
        swapped = float(results.get("pass@1") or 0.0)
        variant_rows.append(
            {
                "label": swap.label,
                "component": swap.component,
                "overrides": swap.overrides,
                **_summarize(var_iter, results),
                "delta": round(swapped - base_pass1, 4),
                "better_than_baseline": swapped > base_pass1,
            }
        )

    record: dict[str, Any] = {
        "iteration": iteration,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "harness_tag": fingerprint.get("harness_tag"),
        "prompt_hash": fingerprint.get("prompt_hash"),
        "model": model or baseline.get("model"),
        "endpoint": baseline.get("endpoint"),
        "max_turns": max_turns,
        "baseline": _summarize(iteration, baseline),
        "swaps": variant_rows,
        "best": (max(variant_rows, key=lambda v: v["pass@1"]) if variant_rows else None),
    }

    out_dir = Path(record_dir) if record_dir else Path(DEFAULT_ATTRIBUTION_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"attribution-{iteration}.json").write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return record
