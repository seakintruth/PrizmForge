"""
Repo "environment card" (UNATTENDED_CLOSED_LOOP_CAPABILITIES §7.3).

Short machine-readable repo facts injected into developer context whenever the
attended loop writes through git. Kept small and dependency-free so any agent
phase can call it cheaply on every prompt build.
"""

from __future__ import annotations

from pathlib import Path


def detect_pre_commit_hook(project_dir: str) -> bool:
    """True when the repo enforces pre-commit hooks (framework config or .git hook)."""
    root = Path(project_dir)
    if (root / ".pre-commit-config.yaml").exists():
        return True
    hook = root / ".git" / "hooks" / "pre-commit"
    return hook.exists()


def build_repo_env_card(project_dir: str, git_enabled: bool) -> str:
    """Render the env card for developer/orchestrator system context."""
    lines = [f"Git commit-on-write: {'enabled' if git_enabled else 'disabled'}"]
    hook = detect_pre_commit_hook(project_dir)
    if git_enabled and hook:
        lines.append(
            "Pre-commit hooks are enforced on commit (ruff/format/lint). Ensure every edit is lint-clean; fix hook-reported files before claiming success."
        )
    elif git_enabled:
        lines.append("No pre-commit hooks detected.")
    return "\n".join(lines)
