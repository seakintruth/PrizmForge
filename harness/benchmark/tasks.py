"""Canonical task manifest loader for the v1 boxed benchmark (docs/benchmark_v1.md)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ContentAssertion:
    file_path: str
    fragment: str
    mode: str = "contains"  # contains | exact | absent


@dataclass(frozen=True)
class BenchTask:
    task_id: str
    seed: str
    fixture: dict[str, str]
    contract: tuple[ContentAssertion, ...]
    k: int = 2

    def rendered_json(self) -> str:
        """Stable rendered entry (contract_hash input)."""
        return json.dumps(
            {
                "task_id": self.task_id,
                "seed": self.seed,
                "k": self.k,
                "fixture": self.fixture,
                "contract": [
                    {
                        "file_path": a.file_path,
                        "fragment": a.fragment,
                        "mode": a.mode,
                    }
                    for a in self.contract
                ],
            },
            sort_keys=True,
            separators=(",", ":"),
        )

    @property
    def contract_hash(self) -> str:
        return hashlib.sha256(self.rendered_json().encode("utf-8")).hexdigest()


def parse_bench_task(raw: dict[str, Any], default_k: int = 2) -> BenchTask:
    contract = tuple(
        ContentAssertion(
            file_path=str(a.get("file_path", "")),
            fragment=str(a.get("fragment", "")),
            mode=str(a.get("mode", "contains")),
        )
        for a in raw.get("contract") or []
    )
    fixture = {str(k): str(v) for k, v in (raw.get("fixture") or {}).items()}
    return BenchTask(
        task_id=str(raw["task_id"]),
        seed=str(raw["seed"]),
        fixture=fixture,
        contract=contract,
        k=int(raw.get("k") or default_k),
    )


def load_task_manifest(path: str | Path) -> dict[str, Any]:
    """Load tasks.json → ``{default_k, tasks: [BenchTask, ...]}``."""
    tasks_path = Path(path)
    raw = json.loads(tasks_path.read_text(encoding="utf-8"))
    default_k = int(raw.get("default_k", 2))
    tasks = [parse_bench_task(t, default_k) for t in raw.get("tasks") or []]
    if not tasks:
        raise ValueError(f"No tasks in manifest: {tasks_path}")
    return {"default_k": default_k, "tasks": tasks}


def default_manifest_path() -> Path:
    return Path(__file__).resolve().parent / "tasks.json"


def load_default_tasks() -> list[BenchTask]:
    return load_task_manifest(default_manifest_path())["tasks"]
