"""Git integration"""
import subprocess
from pathlib import Path
from core.config import get_config

def git_init():
    """Initialize git repo"""
    config = get_config()
    if not config.get("git"):
        return False
    
    project_dir = Path(config.get("project_directory", "./project"))
    
    try:
        result = subprocess.run(
            ["git", "init"],
            cwd=project_dir,
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print(f"✅ Git initialized in {project_dir}")
            return True
    except Exception as e:
        print(f"⚠️  Git init failed: {e}")
    
    return False

def git_commit(file_path: str, message: str) -> str:
    """Commit a file"""
    config = get_config()
    if not config.get("git") or not config.get("git_auto_commit"):
        return None
    
    project_dir = Path(config.get("project_directory", "./project"))
    
    try:
        # Add file
        subprocess.run(
            ["git", "add", file_path],
            cwd=project_dir,
            capture_output=True,
            check=True,
            timeout=10
        )
        
        # Commit
        result = subprocess.run(
            ["git", "commit", "-m", message],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            # Get commit hash
            hash_result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=project_dir,
                capture_output=True,
                text=True,
                check=True,
                timeout=5
            )
            commit_hash = hash_result.stdout.strip()
            print(f"  📦 Git commit: {commit_hash[:7]}")
            return commit_hash
        else:
            # ✅ FIX: Make commit failures more visible
            print(f"\n{'='*60}")
            print(f"⚠️  GIT COMMIT FAILED for {file_path}")
            print(f"{'='*60}")
            print(f"Error: {result.stderr}")
            print(f"Stdout: {result.stdout}")
            print(f"File will be modified but NOT version controlled!")
            print(f"{'='*60}\n")
            return None
    
    except subprocess.TimeoutExpired:
        print(f"\n⚠️  GIT TIMEOUT: {file_path} - git command took too long\n")
        return None
    except Exception as e:
        print(f"\n⚠️  GIT ERROR: {file_path} - {e}\n")
        return None
    
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
            timeout=5
        )
        
        if result.returncode == 0:
            # Git repo exists and is valid
            print(f"✅ Git repository detected: {project_dir}")
            return True
        else:
            # Not a git repo - initialize it
            print(f"\n⚠️  Not a git repository. Initializing...")
            init_result = subprocess.run(
                ["git", "init"],
                cwd=project_dir,
                capture_output=True,
                text=True,
                timeout=5
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
                    print(f"   📝 Created .gitignore")
                
                return True
            else:
                print(f"❌ Git init failed: {init_result.stderr}")
                return False
                
    except FileNotFoundError:
        print(f"❌ Git command not found. Install git to enable version control.")
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
            timeout=5
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
            timeout=5
        )
        
        if result.returncode != 0:
            return []
        
        commits = []
        for line in result.stdout.split('\n'):
            if line.strip():
                parts = line.split('|', 2)
                if len(parts) == 3:
                    commits.append({
                        'hash': parts[0],
                        'message': parts[1],
                        'when': parts[2]
                    })
        return commits
    except Exception:
        return []