"""Git integration"""

import subprocess
from pathlib import Path

from core.config import get_config

# Hook budget: this repo's own pre-commit (black/isort/ruff/flake8/mypy)
# routinely exceeds a 10s shell default. A short timeout would make every
# real hook run report stage=timeout with empty stderr and hide the cause.
_GIT_ADD_TIMEOUT_S = 120
_GIT_COMMIT_TIMEOUT_S = 120
_GIT_HASH_TIMEOUT_S = 5


def git_init():
    """Initialize git repo"""
    config = get_config()
    if not config.get("git"):
        return False

    project_dir = Path(config.get("project_directory", "./project"))

    try:
        result = subprocess.run(["git", "init"], cwd=project_dir, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ Git initialized in {project_dir}")
            return True
    except Exception as e:
        print(f"⚠️  Git init failed: {e}")

    return False


def git_commit(file_path: str, message: str) -> dict:
    """
    Commit a file, returning a structured outcome.

    Returns dict with:
        ok (bool)         — True only if add+commit+rev-parse all succeeded
        attempted (bool)  — False when git is disabled (distinct from failure)
        code (int|None)   — failing command's return code
        stage (str)       — which git step failed: add | commit | rev-parse | timeout
        stdout / stderr   — captured output (hook excerpts for feedback)
        file_path (str)
        commit_hash (str|None) — on success
    """
    config = get_config()
    if not config.get("git") or not config.get("git_auto_commit"):
        return {"ok": False, "attempted": False, "code": None, "stage": "disabled", "stdout": "", "stderr": "", "file_path": file_path, "commit_hash": None}

    project_dir = Path(config.get("project_directory", "./project"))

    def _failure(stage: str, code=None, stdout="", stderr="") -> dict:
        print(f"\n⚠️  GIT {stage.upper()} FAILED for {file_path}\n  stderr: {stderr[:500]}\n")
        return {
            "ok": False,
            "attempted": True,
            "code": code,
            "stage": stage,
            "stdout": stdout or "",
            "stderr": stderr or "",
            "file_path": file_path,
            "commit_hash": None,
        }

    try:
        # Add file (-- guards against a path that begins with a flag)
        try:
            subprocess.run(
                ["git", "add", "--", file_path],
                cwd=project_dir,
                capture_output=True,
                text=True,
                timeout=_GIT_ADD_TIMEOUT_S,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            return _failure("add", e.returncode, getattr(e, "stdout", "") or "", getattr(e, "stderr", "") or "")
        except subprocess.TimeoutExpired:
            return _failure("timeout", None)

        # Commit (pre-commit hooks run inside this step)
        result = subprocess.run(
            ["git", "commit", "-m", message],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=_GIT_COMMIT_TIMEOUT_S,
        )

        if result.returncode != 0:
            return _failure("commit", result.returncode, result.stdout, result.stderr)

        # Get commit hash
        hash_result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            check=True,
            timeout=_GIT_HASH_TIMEOUT_S,
        )
        commit_hash = hash_result.stdout.strip()
        print(f"  📦 Git commit: {commit_hash[:7]}")
        return {
            "ok": True,
            "attempted": True,
            "code": 0,
            "stage": "commit",
            "stdout": result.stdout or "",
            "stderr": result.stderr or "",
            "file_path": file_path,
            "commit_hash": commit_hash,
        }

    except subprocess.TimeoutExpired:
        return _failure("timeout", None)
    except Exception as e:
        return _failure("error", None, stderr=str(e))


def ensure_git_initialized() -> bool:
    """
    Ensure git repo is initialized, run git init if not
    Returns True if git is available and initialized
    """
    config = get_config()
    if not config.get("git"):
        return False

    project_dir = Path(config.get("project_directory", "./project"))

    try:
        # Check if git repo exists
        result = subprocess.run(
            ["git", "status"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode == 0:
            # Git repo exists and is valid
            print(f"✅ Git repository detected: {project_dir}")
            return True
        else:
            # Not a git repo - initialize it
            print("\n⚠️  Not a git repository. Initializing...")
            init_result = subprocess.run(
                ["git", "init"],
                cwd=project_dir,
                capture_output=True,
                text=True,
                timeout=5,
            )

            if init_result.returncode == 0:
                print(f"✅ Git initialized: {project_dir}")

                # Create initial .gitignore
                gitignore_path = project_dir / ".gitignore"
                if not gitignore_path.exists():
                    gitignore_content = """# PrizmForge data directory
.PrizmForge/

# Python
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
*.so
*.egg
*.egg-info/
dist/
build/
venv/
.venv/

# IDEs
.vscode/
.idea/
*.swp
*.swo
"""
                    gitignore_path.write_text(gitignore_content)
                    print("   📝 Created .gitignore")

                # Initial commit
                try:
                    # Add all files
                    add_result = subprocess.run(
                        ["git", "add", "."],
                        cwd=project_dir,
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )

                    if add_result.returncode == 0:
                        # Commit initial state
                        commit_result = subprocess.run(
                            [
                                "git",
                                "commit",
                                "-m",
                                "Initial commit - PrizmForge project initialization",
                            ],
                            cwd=project_dir,
                            capture_output=True,
                            text=True,
                            timeout=10,
                        )

                        if commit_result.returncode == 0:
                            # Get commit hash
                            hash_result = subprocess.run(
                                ["git", "rev-parse", "--short", "HEAD"],
                                cwd=project_dir,
                                capture_output=True,
                                text=True,
                                timeout=5,
                            )
                            commit_hash = hash_result.stdout.strip()
                            print(f"   📦 Initial commit: {commit_hash}")
                        else:
                            print(f"   ⚠️  Initial commit failed: {commit_result.stderr}")
                    else:
                        print(f"   ⚠️  git add failed: {add_result.stderr}")

                except subprocess.TimeoutExpired:
                    print("   ⚠️  Initial commit timed out")
                except Exception as e:
                    print(f"   ⚠️  Initial commit error: {e}")

                return True
            else:
                print(f"❌ Git init failed: {init_result.stderr}")
                return False

    except FileNotFoundError:
        print("❌ Git command not found. Install git to enable version control.")
        return False
    except Exception as e:
        print(f"❌ Git check failed: {e}")
        return False


def git_status() -> str:
    """Get git status output"""
    config = get_config()
    if not config.get("git"):
        return "Git disabled in config"

    project_dir = Path(config.get("project_directory", "./project"))

    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout if result.returncode == 0 else f"Error: {result.stderr}"
    except Exception as e:
        return f"Error: {e}"


def git_log(count: int = 10) -> list:
    """Get recent git commits"""
    config = get_config()
    if not config.get("git"):
        return []

    project_dir = Path(config.get("project_directory", "./project"))

    try:
        result = subprocess.run(
            ["git", "log", f"-{count}", "--pretty=format:%h|%s|%ar"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode != 0:
            return []

        commits = []
        for line in result.stdout.split("\n"):
            if line.strip():
                parts = line.split("|", 2)
                if len(parts) == 3:
                    commits.append({"hash": parts[0], "message": parts[1], "when": parts[2]})
        return commits
    except Exception:
        return []
