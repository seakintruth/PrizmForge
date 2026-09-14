"""Repo fixtures for §14 terminal-class benchmark tasks (docs/TODO.md §14.2).

A pinned ``repo {url, commit}`` overrides the trial workdir with a disposable
git snapshot. The clone is materialized from a shared mirror cache (so trials
don't each hit the origin), checked out detached at the pinned commit, and the
tree ingested into the governed DB under the same byte/file caps as
:class:`workflow.shell_developer.ShellWorktree`. The origin is never written
to; everything lives in the per-bench scratch area.
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Any

#: Matches ShellWorktree.max_file_bytes (512 KB); larger files are skipped.
MAX_REPO_FILE_BYTES = 512_000
#: Per-task cap on ingested governed files.
MAX_REPO_FILES = 200


class RepoFixtureError(RuntimeError):
    """Raised when a repo fixture cannot be materialized (never guess)."""


def _slug(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


def _run_git(
    args: list[str],
    *,
    cwd: Path | None = None,
    timeout: int = 180,
) -> subprocess.CompletedProcess:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as e:
        raise RepoFixtureError(f"git {args[0]} timed out after {timeout}s") from e
    if proc.returncode != 0:
        raise RepoFixtureError(f"git {args[0]} failed: {((proc.stderr or '').strip() or (proc.stdout or '').strip())[:400]}")
    return proc


def _ensure_mirror(url: str, cache_dir: Path, timeout: int = 360) -> Path:
    """Return a mirror clone shared across trials, refreshed from ``url``.

    Reads from the origin only (``clone`` / ``fetch``); never pushes.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    mirror = cache_dir / f"{_slug(url)}.git"
    if mirror.exists():
        _run_git(["-C", str(mirror), "fetch", "--force", "--tags", "origin"], timeout=timeout)
    else:
        _run_git(["clone", "--mirror", url, str(mirror)], timeout=timeout)
    return mirror


def clone_repo(
    url: str,
    commit: str,
    dest: Path,
    *,
    cache_dir: Path | None = None,
    timeout: int = 180,
) -> Path:
    """Materialize ``url @ commit`` as a detached checkout under ``dest``.

    Returns the checkout workdir (a git repo, so ShellWorktree can branch from
    it). ``commit`` is pinned for determinism; an unpinned/bad ref fails loudly.
    """
    checkout = dest / "checkout"
    if checkout.exists():
        raise RepoFixtureError(f"clone destination already exists: {checkout}")

    source: str | Path = url
    if cache_dir is not None:
        source = _ensure_mirror(url, cache_dir, timeout=timeout)
    dest.mkdir(parents=True, exist_ok=True)
    _run_git(["clone", "--no-checkout", str(source), str(checkout)], timeout=timeout)
    try:
        _run_git(["-C", str(checkout), "checkout", "--detach", commit], timeout=timeout)
    except RepoFixtureError:
        # The pinned commit may be a tag/ref only present upstream (a fresh
        # mirror fetch should have pulled it); surface the actual error.
        raise
    return checkout


def run_setup_commands(commands: list[str] | tuple[str, ...], cwd: str | Path, timeout: int = 120) -> None:
    """Run the task's one-time ``setup`` bash list inside the checkout.

    Fails loudly on any non-zero exit — a task whose setup cannot run is
    misconfigured, not worth benchmarking blind. Never writes outside ``cwd``.
    """
    base = Path(cwd)
    for cmd in commands:
        try:
            proc = subprocess.run(
                cmd,
                shell=True,
                cwd=str(base),
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as e:
            raise RepoFixtureError(f"setup command timed out after {timeout}s: {cmd}") from e
        if proc.returncode != 0:
            tail = ((proc.stderr or "") + (proc.stdout or ""))[-300:]
            raise RepoFixtureError(f"setup command failed ({proc.returncode}): {cmd}\n{tail}")


def ensure_git_baseline(workdir: str | Path) -> None:
    """Turn a plain trial dir into a committed git repo for ShellWorktree.

    The shell developer branches a worktree from HEAD, so the trial workspace
    must be a git repo with at least one commit. Fixture files are written
    before this call so the baseline commit carries them.
    """
    base = Path(workdir)
    _run_git(["init", "-q", str(base)])
    try:
        _run_git(["-C", str(base), "config", "user.email", "bench@local"])
        _run_git(["-C", str(base), "config", "user.name", "bench"])
    except RepoFixtureError:
        # identity config is best-effort (repo may already be configured)
        pass
    _run_git(["-C", str(base), "add", "-A"])
    _run_git(["-C", str(base), "commit", "-qm", "baseline", "--allow-empty"])


def materialize_terminal_task(task: Any, trial_dir: str | Path, cache_dir: str | Path) -> Path:
    """Clone a terminal task's repo + run its setup; returns the checkout workdir.

    The checkout is the trial's project directory: the ShellWorktree derives
    from it, the verifier command runs in it, and ``ingest_tree_to_governed``
    reads its tree under byte/file caps.
    """
    if not (task.is_terminal and task.repo):
        return Path(trial_dir)
    checkout = clone_repo(task.repo.url, task.repo.commit, Path(trial_dir), cache_dir=Path(cache_dir))
    if task.setup:
        run_setup_commands(list(task.setup), checkout)
    return checkout


def ingest_tree_to_governed(
    root: str | Path,
    *,
    max_file_bytes: int = MAX_REPO_FILE_BYTES,
    max_files: int = MAX_REPO_FILES,
) -> list[str]:
    """Ingest the checkout tree into the governed DB (files + file_lines).

    Bounded by ``max_file_bytes`` (oversize skipped, like ShellWorktree) and
    ``max_files`` (hard cap on governed surface). Returns the list of ingested
    relative paths — the caller uses it as the fixture-path set so the trial
    scrub keeps exactly this tree.
    """
    from file_editing.writer import initialize_file_lines

    root_path = Path(root)
    ingested: list[str] = []
    for file in sorted(root_path.rglob("*")):
        if not file.is_file():
            continue
        if len(ingested) >= max_files:
            print(f"   ⚠️ repo fixture: capped governed ingest at {max_files} files; skipping {file}")
            continue
        rel = file.relative_to(root_path).as_posix()
        if ".git" in Path(rel).parts:
            continue
        raw = file.read_bytes()
        if len(raw) > max_file_bytes:
            print(f"   ⚠️ repo fixture: skipping oversize file ({len(raw)} bytes > {max_file_bytes}): {rel}")
            continue
        try:
            content = raw.decode("utf-8")
        except UnicodeDecodeError:
            print(f"   ⚠️ repo fixture: skipping non-utf8 file: {rel}")
            continue
        initialize_file_lines(rel, content)
        ingested.append(rel)
    return ingested


def fixture_paths_for_task(task: Any, workdir: str | Path) -> list[str]:
    """Return the governed fixture-path set for a task's trial.

    Content tasks use the manifest fixture keys; repo tasks use whatever was
    actually ingested from the checkout (reflecting the byte/file caps).
    """
    if task.is_terminal and task.repo:
        return ingest_tree_to_governed(workdir)
    return list(task.fixture)
