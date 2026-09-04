#!/usr/bin/env bash
# Start the next PrizmForge soak.
#
# Usage:
#   ./utils/soak-setup.sh [SOAK_NUMBER] [OPTIONS]
#
# Options:
#   -p, --python PATH   Python interpreter to use for config edits and main.py.
#                       Git Bash accepts either C:\path\python.exe or /c/path/python.exe.
#   --dry-run           Print the plan without copying or running.
#   --no-run            Create soak trees but do not start main.py.
#   --force             Overwrite an existing soak number, archiving analytics.
#   --source PATH       Override the source repository.
#   --soak-root PATH    Override the soak-state root directory.
#   -h, --help          Show this help.
#
# Environment:
#   SOURCE_REPO=/path   Override source repository.
#   SOAK_ROOT=/path     Override soak root.
#   PYTHON_EXEC=/path   Default Python interpreter; overridden by --python.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_REPO="$(cd "${SOURCE_REPO:-$SCRIPT_DIR/..}" && pwd)"
SOAK_ROOT="${SOAK_ROOT:-$SOURCE_REPO/../PrizmForge-Soak}"

DRY_RUN=0
FORCE=0
NO_RUN=0
SOAK_N=""
PYTHON_EXEC="${PYTHON_EXEC:-}"

usage() {
  sed -n '2,20p' "$0"
  exit "${1:-0}"
}

require_option_value() {
  local option="$1" value="${2:-}"
  [[ -n "$value" && ! "$value" =~ ^- ]] || {
    echo "Error: ${option} needs a value." >&2
    exit 1
  }
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      usage 0
      ;;
    -p|--python)
      require_option_value "$1" "${2:-}"
      PYTHON_EXEC="$2"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --no-run)
      NO_RUN=1
      shift
      ;;
    --force)
      FORCE=1
      shift
      ;;
    --source)
      require_option_value "$1" "${2:-}"
      SOURCE_REPO="$(cd "$2" && pwd)"
      SOAK_ROOT="${SOAK_ROOT:-$SOURCE_REPO/../PrizmForge-Soak}"
      shift 2
      ;;
    --soak-root)
      require_option_value "$1" "${2:-}"
      SOAK_ROOT="$2"
      shift 2
      ;;
    -*)
      echo "Unknown flag: $1" >&2
      usage 1
      ;;
    *)
      if [[ -n "$SOAK_N" ]]; then
        echo "Unexpected extra argument: $1" >&2
        usage 1
      fi
      SOAK_N="$1"
      shift
      ;;
  esac
done

# Convert C:\... paths into /c/... paths when running in Git Bash/MSYS.
case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*)
    if [[ -n "$PYTHON_EXEC" \
       && "$PYTHON_EXEC" =~ ^[A-Za-z]:[\\/].* ]] \
       && command -v cygpath >/dev/null 2>&1; then
      PYTHON_EXEC="$(cygpath -u "$PYTHON_EXEC")"
    fi
    ;;
esac

PYTHON_BIN="${PYTHON_EXEC:-python3}"

if ! "$PYTHON_BIN" -c "import sys" >/dev/null 2>&1; then
  echo "Error: Python interpreter could not be executed: $PYTHON_BIN" >&2
  echo "Example:" >&2
  echo "  ./utils/soak-setup.sh --python '/c/git/programs/Python31209/python.exe'" >&2
  exit 1
fi

next_soak_number() {
  local max=0 base n d
  shopt -s nullglob

  for d in "$SOAK_ROOT"/Soak[0-9]*; do
    [[ -d "$d" ]] || continue
    base="$(basename "$d")"

    if [[ "$base" =~ ^Soak([0-9]+)$ ]]; then
      n="${BASH_REMATCH[1]}"
      (( n > max )) && max="$n"
    fi
  done

  echo $((max + 1))
}

# Remove all copied source files but retain the analytics directory, if present.
purge_container() {
  local container="$1" keep="" temp

  [[ -d "$container" ]] || return 0

  [[ -d "$container/.prizmforge" ]] && keep="$container/.prizmforge"
  [[ -z "$keep" && -d "$container/.PrizmForge" ]] && keep="$container/.PrizmForge"

  if [[ -n "$keep" ]]; then
    temp="$SOAK_ROOT/.retain-$$-$(basename "$container")"
    mv "$keep" "$temp"
    rm -rf "$container"
    mkdir -p "$container"
    mv "$temp" "$keep"
  else
    rm -rf "$container"
  fi
}

purge_previous_soaks() {
  local current="$1" d base n

  shopt -s nullglob
  for d in "$SOAK_ROOT"/Soak[0-9]*; do
    [[ -d "$d" ]] || continue
    base="$(basename "$d")"

    [[ "$base" =~ ^Soak([0-9]+)(-target)?$ ]] || continue
    n="${BASH_REMATCH[1]}"

    if (( n < current )); then
      echo "Purging prior soak $base; retaining analytics only."
      purge_container "$d/PrizmForge"
    fi
  done
}

archive_current_soak() {
  local d label keep dest

  [[ "$FORCE" -eq 1 ]] || return 0

  for d in "$CONTROLLER" "$TARGET"; do
    [[ -d "$d" ]] || continue

    label="$(basename "$(dirname "$d")")"
    keep=""
    [[ -d "$d/.prizmforge" ]] && keep="$d/.prizmforge"
    [[ -z "$keep" && -d "$d/.PrizmForge" ]] && keep="$d/.PrizmForge"

    if [[ -n "$keep" ]]; then
      dest="$SOAK_ROOT/archive/$label/$(basename "$d")/.PrizmForge"
      echo "Archiving analytics: $label -> $dest"
      mkdir -p "$(dirname "$dest")"
      mv "$keep" "$dest"
    fi

    rm -rf "$d"
  done
}

check_clean_source() {
  local dirty

  dirty="$(git -C "$SOURCE_REPO" status --porcelain | grep -v '^??' || true)"

  if [[ -n "$dirty" ]]; then
    echo "Error: source repo has tracked, uncommitted changes." >&2
    echo "Commit or stash them before starting a soak:" >&2
    echo "$dirty" >&2
    exit 1
  fi
}

copy_tree() {
  local src="$1" dest="$2"

  mkdir -p "$(dirname "$dest")"

  if command -v rsync >/dev/null 2>&1; then
    rsync -a --delete \
      --exclude '.soak/' \
      --exclude '.PrizmForge/' \
      --exclude '.prizmforge/' \
      --exclude 'shell_trajectories/' \
      --exclude '.venv/' \
      --exclude '__pycache__/' \
      --exclude '.pytest_cache/' \
      --exclude '.mypy_cache/' \
      --exclude '.ruff_cache/' \
      --exclude '*.pyc' \
      --exclude '*.db' \
      --exclude '*.db-wal' \
      --exclude '*.db-shm' \
      "$src"/ "$dest"/
  else
    rm -rf "$dest"
    mkdir -p "$dest"
    cp -a "$src"/. "$dest"/

    rm -rf \
      "$dest/.soak" \
      "$dest/.PrizmForge" \
      "$dest/.prizmforge" \
      "$dest/.venv"

    find "$dest" -type d \
      \( -name .PrizmForge -o -name .prizmforge -o -name shell_trajectories \) \
      -prune -exec rm -rf {} +

    find "$dest" -type f \
      \( -name '*.db' -o -name '*.db-wal' -o -name '*.db-shm' \) \
      -delete
  fi
}

init_soak_repo() {
  local dir="$1" branch="$2" label="$3"

  (
    cd "$dir"

    if [[ ! -d ".git" ]]; then
      echo "Error: $label has no .git directory." >&2
      exit 1
    fi

    git \
      -c user.name="PrizmForge Soak${SOAK_N}" \
      -c user.email="soak@local" \
      checkout -q -B "$branch"
  )
}

if [[ -z "$SOAK_N" ]]; then
  SOAK_N="$(next_soak_number)"
fi

if ! [[ "$SOAK_N" =~ ^[0-9]+$ ]]; then
  echo "Soak number must be an integer, got: $SOAK_N" >&2
  exit 1
fi

CONTROLLER="$SOAK_ROOT/Soak${SOAK_N}/PrizmForge"
TARGET_ROOT="$SOAK_ROOT/Soak${SOAK_N}-target"
TARGET="$TARGET_ROOT/PrizmForge"
REL_PROJECT="../../Soak${SOAK_N}-target/PrizmForge"
CONTROLLER_CFG="$CONTROLLER/config.json"
SOAK_BRANCH="soak/${SOAK_N}"

echo "Source:      $SOURCE_REPO"
echo "Soak root:   $SOAK_ROOT"
echo "Controller:  $CONTROLLER"
echo "Target:      $TARGET"
echo "Config path: $REL_PROJECT"
echo "Git branch:  $SOAK_BRANCH"
echo "Python:      $PYTHON_BIN"

[[ -d "$SOURCE_REPO" ]] || {
  echo "Source repo not found: $SOURCE_REPO" >&2
  exit 1
}

[[ -f "$SOURCE_REPO/config.json" ]] || {
  echo "Source has no config.json: $SOURCE_REPO/config.json" >&2
  exit 1
}

[[ -f "$SOURCE_REPO/main.py" ]] || {
  echo "Source has no main.py: $SOURCE_REPO/main.py" >&2
  exit 1
}

if [[ -e "$CONTROLLER" || -e "$TARGET_ROOT" ]] && [[ "$FORCE" -eq 0 ]]; then
  echo "Soak${SOAK_N} already exists. Pass --force or choose another number." >&2
  exit 1
fi

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "[dry-run] would require a clean source repository."
  echo "[dry-run] would purge earlier soak source copies, retaining analytics."
  echo "[dry-run] would copy source to controller and target."
  echo "[dry-run] would set project_directory to: $REL_PROJECT"
  echo "[dry-run] would run: $PYTHON_BIN ./main.py"
  exit 0
fi

check_clean_source

mkdir -p "$SOAK_ROOT" "$TARGET_ROOT"
purge_previous_soaks "$SOAK_N"
archive_current_soak

echo "Copying controller..."
copy_tree "$SOURCE_REPO" "$CONTROLLER"

echo "Copying target..."
copy_tree "$SOURCE_REPO" "$TARGET"

"$PYTHON_BIN" - "$CONTROLLER_CFG" "$REL_PROJECT" <<'PY'
import json
import sys
from pathlib import Path

config_path = Path(sys.argv[1])
project_directory = sys.argv[2]

config = json.loads(config_path.read_text(encoding="utf-8"))
config["project_directory"] = project_directory
config_path.write_text(
    json.dumps(config, indent=2) + "\n",
    encoding="utf-8",
)

print(f"Set project_directory -> {project_directory}")
PY

"$PYTHON_BIN" - "$CONTROLLER_CFG" "$CONTROLLER" <<'PY'
import json
import sys
from pathlib import Path

config_path = Path(sys.argv[1])
controller = Path(sys.argv[2])

project_directory = json.loads(
    config_path.read_text(encoding="utf-8")
)["project_directory"]

target = (controller / project_directory).resolve()

if not target.is_dir():
    raise SystemExit(
        f"project_directory does not resolve: "
        f"{project_directory} -> {target}"
    )

print(f"Resolved target: {target}")
PY

init_soak_repo "$CONTROLLER" "$SOAK_BRANCH" "controller"
init_soak_repo "$TARGET" "${SOAK_BRANCH}-target" "target"

echo
echo "Soak${SOAK_N} ready at $CONTROLLER (branch $SOAK_BRANCH)"
echo "Soak${SOAK_N} target ready at $TARGET (branch ${SOAK_BRANCH}-target)"

if [[ "$NO_RUN" -eq 1 ]]; then
  echo "Skipping main.py (--no-run)."
  echo "  cd \"$CONTROLLER\" && \"$PYTHON_BIN\" ./main.py"
  exit 0
fi

cd "$CONTROLLER"

[[ -f "./main.py" ]] || {
  echo "No ./main.py in $CONTROLLER" >&2
  exit 1
}

echo "Starting $PYTHON_BIN ./main.py"
exec "$PYTHON_BIN" ./main.py