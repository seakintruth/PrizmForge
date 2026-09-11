"""Bench config: install a hermetic get_config for the duration of a run.

Mirrors the integration-test technique (``_install_cycle_config``): swap
``core.config.get_config`` and every module-local ``get_config`` binding for a
function returning a bench config (fresh project dir, background agents off,
mock default endpoint), then restore on exit.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Any


def bench_config(project_dir: str | Path) -> dict[str, Any]:
    """Config used for benchmark trials (single-writer, no background LLM)."""
    return {
        "project_directory": str(project_dir),
        "background_agents_enabled": False,
        "file_editing": {
            "preferred_modes": ["find_replace", "full_replace"],
            "fallback_order": ["find_replace", "full_replace"],
            "small_file_threshold_lines": 180,
        },
        "endpoints": {},
        "git": True,
        "token_budget": {"max_tokens_per_4h": 1_000_000},
        "default_model": "mock-model",
        "default_iteration_minutes": 1,
        "min_iterations_before_complete": 1,
        "background_agents": {},
        "background_feeder": {},
    }


#: Modules holding a module-level ``from core.config import get_config`` binding.
_CONFIG_BINDING_MODULES = (
    "core.config",
    "workflow.task_runner",
    "workflow.developer_edit",
    "workflow.edit_mode_selector",
    "agents.orchestrator",
    "agents.base",
    "agents.parallel_workers",
    "agents.reporter_worker",
    "agents.resource_controller_worker",
    "agents.archivist_worker",
    "file_editing.writer",
)


@contextmanager
def use_bench_config(project_dir: str | Path):
    """Install bench_config() as get_config everywhere, then restore."""
    import importlib

    cfg = bench_config(project_dir)
    originals: dict[str, Any] = {}
    modules: dict[str, Any] = {}

    for dotted in _CONFIG_BINDING_MODULES:
        try:
            modules[dotted] = importlib.import_module(dotted)
        except Exception:
            continue
    for dotted, mod in modules.items():
        if not hasattr(mod, "get_config"):
            continue
        originals[dotted] = mod.get_config
        mod.get_config = lambda _cfg=cfg: _cfg

    try:
        yield cfg
    finally:
        for dotted, original in originals.items():
            try:
                modules[dotted].get_config = original
            except Exception:
                pass
