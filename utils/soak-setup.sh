#!/usr/bin/env bash
# Start the next PrizmForge soak (see docs/soak_runbook.md).
#
# Soak state lives OUTSIDE the PrizmForge source repo, one directory above it,
# under PrizmForge-Soak/ by default (override with SOAK_ROOT or --soak-root).
# Keeping it out of the repo avoids a git-ignored-path collision with the
# mini-swe shell developer: the edit target must be its own git repository for
# git-worktree change collection to work.
#
# Layout (under SOAK_ROOT = <repo>/../PrizmForge-Soak by default):
#   <repo>/utils/soak-setup.sh
#   <parent>/PrizmForge-Soak/SoakN/PrizmForge          controller (runs ./main.py)
#   <parent>/PrizmForge-Soak/SoakN-target/PrizmForge   edit target
#
# Controller config.json is rewritten to:
#   "project_directory": "../../SoakN-target/PrizmForge"
#
# The source repo's .git history IS copied into each soak, and .PrizmForge/,
# .prizmforge/, shell_trajectories/, sqlite DB files and caches are excluded —
# so a soak starts with fresh process + analytics state (the target generates
# its own .PrizmForge/agents.db at runtime) but keeps full git history. The
# source repo must be clean (no tracked, uncommitted changes) so the copied
# tree matches HEAD. Each soak side gets its own branch (soak/N /
# soak/N-target) at HEAD; the target's repo is what the shell developer's
# worktree machinery needs to collect and materialize governed edits. main.py
# stdout stays on the terminal (default buffering).
#
# Starting SoakN purges previous soaks (Soak1..SoakN-1) down to their
# analytics component (.PrizmForge/ with agents.db + reports + indexes) only.
#
# After copy: cd <SOAK_ROOT>/SoakN/PrizmForge, git checkout -b soak/N, ./main.py
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
SOAK_ROOT="${SOAK_ROOT:-$SOURCE_REPO/../PrizmForge-Soak}"


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
      SOAK_ROOT="${SOAK_ROOT:-$SOURCE_REPO/../PrizmForge-Soak}"
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
# analytics component only, so SOAK_ROOT never accumulates full repo copies.
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

# A soak copy is only consistent with its git history if the source repo's
# working tree matches HEAD. Since we now copy the source's .git, require the
# source to be clean (ignoring untracked files — config.json / api_key.json and
# analytics/caches are git-ignored and expected) so every soak starts with a
# clean `git status`, matching HEAD.
check_clean_source() {
  local dirty
  dirty="$(git -C "$SOURCE_REPO" status --porcelain | grep -v '^??' || true)"
  if [[ -n "$dirty" ]]; then
    echo "Source repo has uncommitted (tracked) changes; a soak would start with a working" >&2
    echo "tree that does not match HEAD, so the copied .git history would be inconsistent." >&2
    echo "Commit or stash before starting a soak:" >&2
    echo "$dirty" >&2
    exit 1
  fi
}

if [[ $DRY_RUN -eq 1 ]]; then
  echo "[dry-run] would require source repo $SOURCE_REPO to be clean (no tracked, uncommitted changes)"
  echo "[dry-run] would purge prior soaks (Soak< $SOAK_N) down to analytics (.PrizmForge) only"
  echo "[dry-run] would copy source → controller and target"
  echo "[dry-run]   copying .git/ history + working tree (excluding analytics/caches); then branch soak/N / soak/N-target at HEAD"
  echo "[dry-run] would set $CONTROLLER_CFG project_directory = $REL_PROJECT"
  echo "[dry-run] would cd $CONTROLLER && ./main.py (stdout → terminal)"
  exit 0
fi

check_clean_source

mkdir -p "$SOAK_ROOT" "$TARGET_ROOT"

purge_previous_soaks "$SOAK_N"
archive_current_soak

copy_tree() {
  local src="$1" dest="$2"
  mkdir -p "$(dirname "$dest")"
  # Copy the working tree PLUS the source repo's .git (so soaks start with the
  # true history and a HEAD that matches the copied tree — the caller enforces a
  # clean source before this runs). Never copy .soak, analytics state or caches;
  # those are generated fresh per soak.
  if command -v rsync >/dev/null 2>&1; then
    rsync -a --delete \
      --exclude '.soak/' \
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
    rm -rf "$dest/.soak" "$dest/.PrizmForge" "$dest/.prizmforge"
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

# init_repo <dir> <branch> <label>: give a soak copy its OWN working branch at
# the source's HEAD. The .git history is copied from the source (see copy_tree +
# check_clean_source), so this just creates/checks out the soak branch. A repo is
# required for the mini-swe shell developer's git-worktree machinery to collect &
# materialize governed edits (without it, git rev-parse falls through to an
# enclosing repo where the target is git-ignored and edits are silently lost).
init_soak_repo() {
  local dir="$1" branch="$2" label="$3"
  (
    cd "$dir"
    if [[ ! -d .git ]]; then
      echo "ERROR: $label has no .git (copy_tree should have copied it from $SOURCE_REPO)" >&2
      exit 1
    fi
    git -c user.name="PrizmForge Soak$SOAK_N" -c user.email="soak@local" \
      checkout -q -b "$branch"
  )
}

init_soak_repo "$CONTROLLER" "$SOAK_BRANCH" "controller"
init_soak_repo "$TARGET" "${SOAK_BRANCH}-target" "target"

echo
echo "Soak${SOAK_N} ready at $CONTROLLER (branch $SOAK_BRANCH)"
echo "Soak${SOAK_N} target ready at $TARGET (branch ${SOAK_BRANCH}-target)"

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
