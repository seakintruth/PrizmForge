#!/usr/bin/env bash
# Start the next in-repo PrizmForge soak (see docs/soak_runbook.md).
#
# Layout (all under the project, gitignored via .soak/):
#   <repo>/utils/soak-setup.sh
#   <repo>/.soak/SoakN/PrizmForge          controller (runs ./main.py)
#   <repo>/.soak/SoakN-target/PrizmForge   edit target
#
# Controller config.json is rewritten to:
#   "project_directory": "../../SoakN-target/PrizmForge"
#
# Copies EXCLUDE .soak/, .git/, .PrizmForge/ and .prizmforge/,
# shell_trajectories/, sqlite DB files and caches — a soak always starts
# with fresh process + analytics state (the target generates its own
# .PrizmForge/agents.db at runtime). main.py stdout stays on the terminal
# (default buffering).
#
# Starting SoakN purges previous soaks (Soak1..SoakN-1) down to their
# analytics component (.PrizmForge/ with agents.db + reports + indexes) only.
#
# After copy: cd .soak/SoakN/PrizmForge, git checkout -b soak/N, ./main.py
#
# Usage (from anywhere; paths resolve from this script):
#   ./utils/soak-setup.sh              # next unused N, then start main.py
#   ./utils/soak-setup.sh 10           # explicit N
#   ./utils/soak-setup.sh --dry-run    # print plan only
#   ./utils/soak-setup.sh --no-run     # copy + branch, do not start main.py
#   ./utils/soak-setup.sh 10 --force   # overwrite existing Soak10 trees
#   SOURCE_REPO=/path ./utils/soak-setup.sh --dry-run   # override source
#   SOAK_ROOT=/path ./utils/soak-setup.sh --dry-run     # override soak root

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_REPO="$(cd "${SOURCE_REPO:-$SCRIPT_DIR/..}" && pwd)"
SOAK_ROOT="${SOAK_ROOT:-$SOURCE_REPO/.soak}"

DRY_RUN=0
FORCE=0
NO_RUN=0
SOAK_N=""

usage() {
  sed -n '2,28p' "$0"
  exit "${1:-0}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help) usage 0 ;;
    --dry-run) DRY_RUN=1; shift ;;
    --no-run) NO_RUN=1; shift ;;
    --force) FORCE=1; shift ;;
    --source)
      SOURCE_REPO="$(cd "$2" && pwd)"
      SOAK_ROOT="${SOAK_ROOT:-$SOURCE_REPO/.soak}"
      shift 2
      ;;
    --soak-root)
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

next_soak_number() {
  local max=0 base n
  shopt -s nullglob
  for d in "$SOAK_ROOT"/Soak[0-9]*; do
    [[ -d "$d" ]] || continue
    base="$(basename "$d")"
    if [[ "$base" =~ ^Soak([0-9]+)$ ]]; then
      n="${BASH_REMATCH[1]}"
      if (( n > max )); then
        max=$n
      fi
    fi
  done
  echo $((max + 1))
}

# Retain the analytics component (.PrizmForge / .prizmforge) of a copied
# container in place; remove everything else in it.
purge_container() {
  local container="$1" keep tmp
  [[ -d "$container" ]] || return 0
  keep=""
  [[ -d "$container/.prizmforge" ]] && keep="$container/.prizmforge"
  [[ -z "$keep" && -d "$container/.PrizmForge" ]] && keep="$container/.PrizmForge"
  if [[ -n "$keep" ]]; then
    # Keep dir temporally OUTSIDE the container: rm -rf of the container
    # must not delete the retained analytics component.
    tmp="$SOAK_ROOT/.retain-$$-$(basename "$container")"
    mv "$keep" "$tmp"
    rm -rf "$container"
    mkdir -p "$container"
    mv "$tmp" "$keep"
  else
    rm -rf "$container"
  fi
}

# Reduce every earlier soak (Soak1..SoakN-1, controller + target) to its
# analytics component only, so .soak/ never accumulates full repo copies.
purge_previous_soaks() {
  local current="$1" d base k
  shopt -s nullglob
  for d in "$SOAK_ROOT"/Soak[0-9]*; do
    [[ -d "$d" ]] || continue
    base="$(basename "$d")"
    [[ "$base" =~ ^Soak([0-9]+)(-target)?$ ]] || continue
    k="${BASH_REMATCH[1]}"
    if (( k >= current )); then
      continue
    fi
    echo "Purging prior soak $base → retaining analytics (.PrizmForge) only"
    purge_container "$d/PrizmForge"
  done
}

# On --force, shelter the current soak's analytics before we overwrite it.
archive_current_soak() {
  [[ $FORCE -eq 1 ]] || return 0
  local d label keep dest
  for d in "$CONTROLLER" "$TARGET"; do
    [[ -d "$d" ]] || continue
    label="$(basename "$(dirname "$d")")"
    keep=""
    [[ -d "$d/.prizmforge" ]] && keep="$d/.prizmforge"
    [[ -z "$keep" && -d "$d/.PrizmForge" ]] && keep="$d/.PrizmForge"
    if [[ -n "$keep" ]]; then
      dest="$SOAK_ROOT/archive/$label/$(basename "$d")/.PrizmForge"
      echo "Archiving previous $label analytics → $dest"
      mkdir -p "$(dirname "$dest")"
      mv "$keep" "$dest"
    fi
    rm -rf "$d"
  done
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

[[ -d "$SOURCE_REPO" ]] || { echo "Source repo not found: $SOURCE_REPO" >&2; exit 1; }
[[ -f "$SOURCE_REPO/config.json" ]] || {
  echo "Source has no config.json: $SOURCE_REPO/config.json" >&2
  exit 1
}
[[ -f "$SOURCE_REPO/main.py" ]] || {
  echo "Source has no main.py: $SOURCE_REPO/main.py" >&2
  exit 1
}

if [[ -e "$CONTROLLER" || -e "$TARGET_ROOT" ]]; then
  if [[ $FORCE -eq 0 ]]; then
    echo "Soak${SOAK_N} already exists under $SOAK_ROOT. Pass --force to overwrite, or pick another number." >&2
    exit 1
  fi
fi

if [[ $DRY_RUN -eq 1 ]]; then
  echo "[dry-run] would purge prior soaks (Soak< $SOAK_N) down to analytics (.PrizmForge) only"
  echo "[dry-run] would copy source → controller and target"
  echo "[dry-run]   excluding .soak/, .git/, .PrizmForge/, .prizmforge/, shell_trajectories/, *.db*, caches"
  echo "[dry-run] would set $CONTROLLER_CFG project_directory = $REL_PROJECT"
  echo "[dry-run] would cd $CONTROLLER && git checkout -b $SOAK_BRANCH"
  echo "[dry-run] would run ./main.py (stdout → terminal)"
  exit 0
fi

mkdir -p "$SOAK_ROOT" "$TARGET_ROOT"

purge_previous_soaks "$SOAK_N"
archive_current_soak

copy_tree() {
  local src="$1" dest="$2"
  mkdir -p "$(dirname "$dest")"
  # Never copy .soak, .git, analytics state or caches into a soak — this is
  # how the layout stays flat and every soak starts with fresh state.
  if command -v rsync >/dev/null 2>&1; then
    rsync -a --delete \
      --exclude '.soak/' \
      --exclude '.git/' \
      --exclude '.PrizmForge/' \
      --exclude '.prizmforge/' \
      --exclude 'shell_trajectories/' \
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
    rm -rf "$dest/.soak" "$dest/.git" "$dest/.PrizmForge" "$dest/.prizmforge"
    find "$dest" -type d \
      \( -name .PrizmForge -o -name .prizmforge -o -name shell_trajectories \) \
      -prune -exec rm -rf {} +
    find "$dest" -type f \
      \( -name '*.db' -o -name '*.db-wal' -o -name '*.db-shm' \) -delete
  fi
}

echo "Copying controller..."
copy_tree "$SOURCE_REPO" "$CONTROLLER"
echo "Copying target..."
copy_tree "$SOURCE_REPO" "$TARGET"

python3 - "$CONTROLLER_CFG" "$REL_PROJECT" <<'PY'
import json
import sys
from pathlib import Path

cfg_path = Path(sys.argv[1])
rel = sys.argv[2]
data = json.loads(cfg_path.read_text(encoding="utf-8"))
data["project_directory"] = rel
cfg_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
print(f"Set project_directory → {rel}")
PY

python3 - "$CONTROLLER_CFG" "$CONTROLLER" <<'PY'
import json
import sys
from pathlib import Path

cfg = Path(sys.argv[1])
base = Path(sys.argv[2])
rel = json.loads(cfg.read_text(encoding="utf-8"))["project_directory"]
resolved = (base / rel).resolve()
if not resolved.is_dir():
    raise SystemExit(f"project_directory does not resolve: {rel} → {resolved}")
print(f"Resolved target: {resolved}")
PY

cd "$CONTROLLER"

if [[ ! -d .git ]]; then
  echo "Creating a fresh soak snapshot commit (no repo history copied)"
  git init -q -b main 2>/dev/null || { git init -q; git branch -m main 2>/dev/null || true; }
  git add -A >/dev/null
  git -c user.name="PrizmForge Soak$SOAK_N" -c user.email="soak@local" \
    commit -m "Soak${SOAK_N} snapshot" >/dev/null
fi

if git show-ref --verify --quiet "refs/heads/${SOAK_BRANCH}"; then
  git checkout -q "$SOAK_BRANCH"
else
  git checkout -q -b "$SOAK_BRANCH"
fi

echo
echo "Soak${SOAK_N} ready at $CONTROLLER (branch $SOAK_BRANCH)"

if [[ $NO_RUN -eq 1 ]]; then
  echo "Skipping ./main.py (--no-run)."
  echo "  cd $CONTROLLER && ./main.py"
  exit 0
fi

if [[ ! -f ./main.py ]]; then
  echo "No ./main.py in $CONTROLLER" >&2
  exit 1
fi

if [[ -x .venv/bin/python ]]; then
  echo "Starting .venv/bin/python ./main.py"
  exec .venv/bin/python ./main.py
fi

chmod +x ./main.py 2>/dev/null || true
echo "Starting ./main.py"
exec ./main.py
