"""Canonical task manifest loader for the boxed benchmark (docs/benchmark_v1.md).

Schema v2 (docs/TODO.md §14.2) adds optional terminal-class fields on top of the
v1 content contract: ``kind``, ``repo {url, commit}``, ``setup`` and
``verifier {command, timeout}``. Every one of them is folded into
``rendered_json`` / ``rendered_contract`` / ``contract_hash`` so the §12.1
rollout fingerprint stays truthful when a task's environment or grading
surface changes.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

#: Manifest schema version understood by this loader (tasks.json says ≤ 2).
SUPPORTED_SCHEMA_VERSION = 2

#: Task kinds.
KIND_CONTENT = "content"
KIND_TERMINAL = "terminal"
SUPPORTED_KINDS = frozenset({KIND_CONTENT, KIND_TERMINAL})


@dataclass(frozen=True)
class ContentAssertion:
    file_path: str
    fragment: str
    mode: str = "contains"  # contains | exact | absent | new


@dataclass(frozen=True)
class RepoRef:
    """A pinned git snapshot. ``commit`` is required for determinism."""

    url: str
    commit: str

    def as_dict(self) -> dict[str, str]:
        return {"url": self.url, "commit": self.commit}


@dataclass(frozen=True)
class Verifier:
    """Command-mode grading: the trial passes iff the command exits 0."""

    command: str
    timeout: int = 60

    def as_dict(self) -> dict[str, Any]:
        return {"command": self.command, "timeout": self.timeout}


@dataclass(frozen=True)
class BenchTask:
    task_id: str
    seed: str
    fixture: dict[str, str]
    contract: tuple[ContentAssertion, ...]
    k: int = 2
    kind: str = KIND_CONTENT
    repo: RepoRef | None = None
    setup: tuple[str, ...] = ()
    verifier: Verifier | None = None
    #: Optional per-task run budget (None → driver defaults). Folded into the
    #: fingerprint because they bound how much work a trial may do.
    max_turns: int | None = None
    timeout_s: float | None = None

    @property
    def is_terminal(self) -> bool:
        return self.kind == KIND_TERMINAL

    def rendered_json(self) -> str:
        """Stable rendered entry (contract_hash input)."""
        return json.dumps(
            {
                "task_id": self.task_id,
                "kind": self.kind,
                "seed": self.seed,
                "k": self.k,
                "fixture": self.fixture,
                "repo": self.repo.as_dict() if self.repo else None,
                "setup": list(self.setup),
                "verifier": self.verifier.as_dict() if self.verifier else None,
                "max_turns": self.max_turns,
                "timeout_s": self.timeout_s,
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

    def rendered_contract(self) -> str:
        """Rollout-fingerprint input for the grading surface only.

        Distinguishes a contract/verifier change from a cosmetic seed edit so
        the §12.1 fingerprint reflects what actually grades the trial.
        """
        return json.dumps(
            {
                "verifier": self.verifier.as_dict() if self.verifier else None,
                "timeout_s": self.timeout_s,
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


def _parse_repo(raw: dict[str, Any] | None) -> RepoRef | None:
    if raw is None:
        return None
    url = str(raw.get("url", "")).strip()
    commit = str(raw.get("commit", "")).strip()
    if not url:
        raise ValueError("repo.url is required when repo is present")
    if not commit:
        raise ValueError(f"repo.commit is required for {url!r} — a pinned commit is what makes a repo fixture deterministic; refusing an unpinned snapshot")
    return RepoRef(url=url, commit=commit)


def _parse_verifier(raw: dict[str, Any] | None) -> Verifier | None:
    if raw is None:
        return None
    command = str(raw.get("command", "")).strip()
    if not command:
        raise ValueError("verifier.command is required when verifier is present")
    return Verifier(command=command, timeout=int(raw.get("timeout", 60)))


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
    kind = str(raw.get("kind") or KIND_CONTENT)
    if kind not in SUPPORTED_KINDS:
        raise ValueError(f"unsupported task kind {kind!r} (supported: {sorted(SUPPORTED_KINDS)})")
    setup = tuple(str(s) for s in (raw.get("setup") or []))
    max_turns_raw = raw.get("max_turns")
    timeout_raw = raw.get("timeout_s")
    task = BenchTask(
        task_id=str(raw["task_id"]),
        seed=str(raw["seed"]),
        fixture=fixture,
        contract=contract,
        k=int(raw.get("k") or default_k),
        kind=kind,
        repo=_parse_repo(raw.get("repo")),
        setup=setup,
        verifier=_parse_verifier(raw.get("verifier")),
        max_turns=int(max_turns_raw) if max_turns_raw is not None else None,
        timeout_s=float(timeout_raw) if timeout_raw is not None else None,
    )
    if task.is_terminal and not task.repo and not task.fixture:
        raise ValueError(f"terminal task {task.task_id!r} needs a repo or fixture — a terminal seed reaches a shell only when a target file exists")
    if task.is_terminal and not task.verifier and not contract:
        raise ValueError(f"terminal task {task.task_id!r} has no grading surface — add a verifier command or a content contract")
    return task


def load_task_manifest(path: str | Path) -> dict[str, Any]:
    """Load tasks.json → ``{schema_version, default_k, tasks: [BenchTask, ...]}``."""
    tasks_path = Path(path)
    raw = json.loads(tasks_path.read_text(encoding="utf-8"))
    schema_version = int(raw.get("schema_version", SUPPORTED_SCHEMA_VERSION))
    if schema_version > SUPPORTED_SCHEMA_VERSION:
        raise ValueError(
            f"tasks.json schema_version {schema_version} is newer than the "
            f"supported {SUPPORTED_SCHEMA_VERSION} — refusing to run an "
            f"unvalidated manifest: {tasks_path}"
        )
    default_k = int(raw.get("default_k", 2))
    tasks = [parse_bench_task(t, default_k) for t in raw.get("tasks") or []]
    if not tasks:
        raise ValueError(f"No tasks in manifest: {tasks_path}")
    return {"schema_version": schema_version, "default_k": default_k, "tasks": tasks}


def default_manifest_path() -> Path:
    return Path(__file__).resolve().parent / "tasks.json"


def load_default_tasks() -> list[BenchTask]:
    return load_task_manifest(default_manifest_path())["tasks"]
