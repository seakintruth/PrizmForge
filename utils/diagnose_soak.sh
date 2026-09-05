#!/usr/bin/env bash
# Diagnose the most recent PrizmForge soak target database and shell-developer
# trajectory files.
#
# Default discovery:
#   <source-repo>/../PrizmForge-Soak/SoakN-target/PrizmForge/.PrizmForge/agents.db
#
# Examples:
#   ./utils/diagnose_soak.sh
#   ./utils/diagnose_soak.sh --task task_001
#   ./utils/diagnose_soak.sh --soak 3
#   ./utils/diagnose_soak.sh --soak-root /c/path/to/PrizmForge-Soak
#   ./utils/diagnose_soak.sh --db /c/path/to/agents.db
#   ./utils/diagnose_soak.sh --python /c/git/programs/Python31209/python.exe

set -u -o pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_REPO="$(cd "${SOURCE_REPO:-$SCRIPT_DIR/..}" && pwd)"

QUERY_SCRIPT="${SCRIPT_DIR}/query_developer_responses.py"
SOAK_ROOT="${SOAK_ROOT:-$SOURCE_REPO/../PrizmForge-Soak}"

PYTHON_EXEC="${PYTHON_EXEC:-python3}"
TASK_ID="${TASK_ID:-task_001}"
LIMIT=100
TRAJECTORY_LIMIT=10
SOAK_N=""
DB_PATH=""

usage() {
  cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Diagnose the newest PrizmForge soak target by default.

Options:
  -p, --python PATH         Python interpreter to use.
  -d, --db PATH             Explicit agents.db path; bypasses soak discovery.
  -s, --soak NUMBER         Query a specific SoakN target.
      --soak-root PATH      Root containing SoakN / SoakN-target directories.
  -t, --task TASK_ID        Task identifier to inspect. Default: task_001.
  -l, --limit NUMBER        Limit errors and lifecycle events. Default: 100.
      --trajectory-limit N  Most-recent trajectory files to inspect. Default: 10.
  -h, --help                Show this help.

Examples:
  ./utils/diagnose_soak.sh
  ./utils/diagnose_soak.sh --soak 3 --task task_001
  ./utils/diagnose_soak.sh --trajectory-limit 20
  ./utils/diagnose_soak.sh --python /c/git/programs/Python31209/python.exe
EOF
}

require_value() {
  local option="$1"
  local value="${2:-}"

  [[ -n "$value" && ! "$value" =~ ^- ]] || {
    echo "Error: $option requires a value." >&2
    exit 2
  }
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -p|--python)
      require_value "$1" "${2:-}"
      PYTHON_EXEC="$2"
      shift 2
      ;;
    -d|--db)
      require_value "$1" "${2:-}"
      DB_PATH="$2"
      shift 2
      ;;
    -s|--soak)
      require_value "$1" "${2:-}"
      SOAK_N="$2"
      shift 2
      ;;
    --soak-root)
      require_value "$1" "${2:-}"
      SOAK_ROOT="$2"
      shift 2
      ;;
    -t|--task)
      require_value "$1" "${2:-}"
      TASK_ID="$2"
      shift 2
      ;;
    -l|--limit)
      require_value "$1" "${2:-}"
      [[ "$2" =~ ^[0-9]+$ ]] || {
        echo "Error: --limit must be numeric." >&2
        exit 2
      }
      LIMIT="$2"
      shift 2
      ;;
    --trajectory-limit)
      require_value "$1" "${2:-}"
      [[ "$2" =~ ^[0-9]+$ ]] || {
        echo "Error: --trajectory-limit must be numeric." >&2
        exit 2
      }
      TRAJECTORY_LIMIT="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Error: unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

# Accept C:\... paths when run from Git Bash.
case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*)
    for var_name in PYTHON_EXEC SOAK_ROOT DB_PATH; do
      value="${!var_name}"

      if [[ -n "$value" \
         && "$value" =~ ^[A-Za-z]:[\\/].* ]] \
         && command -v cygpath >/dev/null 2>&1; then
        printf -v "$var_name" '%s' "$(cygpath -u "$value")"
      fi
    done
    ;;
esac

find_latest_soak_db() {
  local max_soak=-1
  local soak_number
  local candidate
  local directory

  shopt -s nullglob

  for directory in "$SOAK_ROOT"/Soak[0-9]*-target; do
    [[ -d "$directory" ]] || continue

    if [[ "$(basename "$directory")" =~ ^Soak([0-9]+)-target$ ]]; then
      soak_number="${BASH_REMATCH[1]}"
      candidate="$directory/PrizmForge/.PrizmForge/agents.db"

      if [[ -f "$candidate" ]] && (( soak_number > max_soak )); then
        max_soak="$soak_number"
        DB_PATH="$candidate"
      fi
    fi
  done

  if (( max_soak < 0 )); then
    return 1
  fi

  SOAK_N="$max_soak"
  return 0
}

find_specific_soak_db() {
  [[ "$SOAK_N" =~ ^[0-9]+$ ]] || {
    echo "Error: soak number must be numeric, got: $SOAK_N" >&2
    exit 2
  }

  DB_PATH="$SOAK_ROOT/Soak${SOAK_N}-target/PrizmForge/.PrizmForge/agents.db"

  [[ -f "$DB_PATH" ]] || {
    echo "Error: Soak${SOAK_N} target database was not found:" >&2
    echo "  $DB_PATH" >&2
    exit 1
  }
}

if [[ -z "$DB_PATH" ]]; then
  if [[ -n "$SOAK_N" ]]; then
    find_specific_soak_db
  elif ! find_latest_soak_db; then
    echo "Error: no soak target database found under:" >&2
    echo "  $SOAK_ROOT" >&2
    echo "Pass --db PATH, --soak NUMBER, or --soak-root PATH." >&2
    exit 1
  fi
fi

[[ -f "$QUERY_SCRIPT" ]] || {
  echo "Error: query utility not found: $QUERY_SCRIPT" >&2
  exit 1
}

[[ -f "$DB_PATH" ]] || {
  echo "Error: database not found: $DB_PATH" >&2
  exit 1
}

# Force UTF-8 output from the native Windows Python interpreter, including when
# stdout is redirected to a report file from Git Bash.
export PYTHONUTF8=1
export PYTHONIOENCODING="utf-8"

if ! "$PYTHON_EXEC" -c "import sys" >/dev/null 2>&1; then
  echo "Error: Python interpreter could not be run: $PYTHON_EXEC" >&2
  exit 1
fi

run_query() {
  local title="$1"
  shift

  echo
  echo "================================================================================"
  echo "🔎 $title"
  echo "================================================================================"

  if ! "$PYTHON_EXEC" "$QUERY_SCRIPT" --db "$DB_PATH" "$@"; then
    echo "⚠️  Query failed; continuing." >&2
  fi
}

inspect_trajectories() {
  local trajectory_dir
  trajectory_dir="$(dirname "$DB_PATH")/shell_trajectories"

  echo
  echo "================================================================================"
  echo "🐺 DEEP SHELL-DEVELOPER TRAJECTORY INVESTIGATION"
  echo "================================================================================"
  echo "Directory: $trajectory_dir"
  echo "Task:      $TASK_ID"
  echo "Limit:     $TRAJECTORY_LIMIT"

  if [[ ! -d "$trajectory_dir" ]]; then
    echo "No shell_trajectories directory found."
    return 0
  fi

  "$PYTHON_EXEC" - "$trajectory_dir" "$TASK_ID" "$TRAJECTORY_LIMIT" "$SOURCE_REPO" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

trajectory_dir = Path(sys.argv[1])
task_id = sys.argv[2]
limit = int(sys.argv[3])
source_repo = sys.argv[4] if len(sys.argv) > 4 else str(Path(__file__).parent.parent)
sys.path.insert(0, source_repo)

files = sorted(
    trajectory_dir.glob(f"{task_id}-*.json"),
    key=lambda path: path.stat().st_mtime,
    reverse=True,
)[:limit]

TEXT_KEYS = {
    "response",
    "content",
    "text",
    "output",
    "message",
    "assistant_response",
    "model_response",
    "completion",
}

STATUS_KEYS = {
    "status",
    "exit_reason",
    "error",
    "error_type",
    "failure_reason",
    "result",
    "finished",
    "model",
    "session_id",
    "steps",
}

if not files:
    print(f"No trajectory files found for task: {task_id}")
    raise SystemExit(0)

def walk(value: Any, path: str = "root"):
    yield path, value

    if isinstance(value, dict):
        for key, child in value.items():
            yield from walk(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk(child, f"{path}[{index}]")

def truncate(text: str, width: int = 1800) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()

    if len(text) > width:
        return text[:width] + "\n... [truncated]"

    return text

def classify_protocol(text: str) -> str:
    from workflow.shell_protocol import classify_shell_reply

    category = classify_shell_reply(text)
    mapping = {
        "VALID_BASH_BLOCK": "HAS_BASH_BLOCK",
        "UNTERMINATED_BASH_BLOCK": "UNTERMINATED_BASH_BLOCK",
        "VALID_FINISH_SESSION": "HAS_FINISH_TOKEN",
        "PROSE_OR_UNSUPPORTED_FORMAT": "PROSE_OR_UNSUPPORTED_FORMAT",
    }

    markers = [mapping.get(category, category)]
    lower = text.lower()

    if "repeatedformaterror" in lower:
        markers.append("FORMAT_ERROR_TEXT")

    if "no file changes" in lower:
        markers.append("NO_FILE_CHANGES_TEXT")

    return ", ".join(markers)

print(f"Found {len(files)} most-recent trajectory file(s).")

for file_path in reversed(files):
    print()
    print("=" * 80)
    print(f"TRAJECTORY: {file_path.name}")
    print("=" * 80)

    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"Could not parse JSON: {exc}")
        continue

    print("\nSession metadata:")
    found_metadata = False

    for path, value in walk(data):
        key = path.rsplit(".", 1)[-1].lower()

        if key in STATUS_KEYS and not isinstance(value, (dict, list)):
            print(f"  {path}: {str(value)[:300]}")
            found_metadata = True

    if not found_metadata:
        print("  No recognized status metadata fields found.")

    replies: list[tuple[str, str]] = []

    for path, value in walk(data):
        key = path.rsplit(".", 1)[-1].lower()

        if key in TEXT_KEYS and isinstance(value, str) and value.strip():
            replies.append((path, value))

    if not replies:
        print("\nNo response/content/message fields found.")
        continue

    print(f"\nCandidate response fields: {len(replies)}")

    for number, (path, text) in enumerate(replies[-6:], start=1):
        print()
        print(f"[{number}] JSON path: {path}")
        print(f"Protocol classification: {classify_protocol(text)}")
        print("Response:")

        for line in truncate(text).splitlines():
            print(f"  {line}")

print()
print("=" * 80)
print("TRAJECTORY INTERPRETATION")
print("=" * 80)
print("HAS_BASH_BLOCK       Expected ```bash protocol was emitted.")
print("HAS_FINISH_TOKEN     Expected <finish> completion protocol was emitted.")
print("NON_BASH_CODE_FENCE  Model used a code fence your parser may reject.")
print("NO_PROTOCOL_MARKER   Model likely returned prose, JSON, XML, or another format.")
PY
}

echo "================================================================================"
echo "PrizmForge Soak Diagnostic"
echo "================================================================================"
echo "Source repo: $SOURCE_REPO"
echo "Soak root:   $SOAK_ROOT"
echo "Selected:    Soak${SOAK_N:-custom database}"
echo "Database:    $DB_PATH"
echo "Task:        $TASK_ID"
echo "Python:      $PYTHON_EXEC"

inspect_trajectories

run_query \
  "Full diagnostic for selected task" \
  --diagnostic \
  --task "$TASK_ID"

run_query \
  "Developer responses — inspect for missing bash blocks or <finish>" \
  --responses \
  --agent developer \
  --task "$TASK_ID"

run_query \
  "All responses for selected task" \
  --responses \
  --task "$TASK_ID"

run_query \
  "Shell protocol errors: RepeatedFormatError" \
  --errors \
  --keyword "RepeatedFormatError" \
  --limit "$LIMIT"

run_query \
  "Developer sessions that finished with no changes" \
  --errors \
  --keyword "produced no file changes" \
  --limit "$LIMIT"

run_query \
  "SQLite lock failures" \
  --errors \
  --keyword "database is locked" \
  --limit "$LIMIT"

run_query \
  "Recent HIGH errors" \
  --errors HIGH \
  --limit "$LIMIT"

run_query \
  "Edit proposals" \
  --proposals

run_query \
  "File write/materialization log" \
  --write-log

run_query \
  "Edit lifecycle events" \
  --events \
  --limit "$LIMIT"

run_query \
  "Open feedback backlog" \
  --sql "SELECT * FROM agent_feedback WHERE addressed = 0"

run_query \
  "Open feedback for selected task" \
  --sql "SELECT * FROM agent_feedback WHERE addressed = 0 AND task_id = '${TASK_ID}'"

run_query \
  "Model and endpoint health" \
  --model-health

echo
echo "================================================================================"
echo "Diagnostic complete."
echo "================================================================================"