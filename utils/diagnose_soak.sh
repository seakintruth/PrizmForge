#!/usr/bin/env bash
# Diagnose the most recent PrizmForge soak target database and shell-developer
# trajectory files. Also writes the mutation-path SQL pack used after Soak6.
#
# Python resolution matches utils/run_tests.sh:
#   $PYTHON_EXEC, then .venv/bin/python, then .venv/Scripts/python.exe
#
# Default discovery:
#   <source-repo>/../PrizmForge-Soak/SoakN-target/PrizmForge/.PrizmForge/agents.db
#
# Examples:
#   ./utils/diagnose_soak.sh
#   ./utils/diagnose_soak.sh --soak 6
#   ./utils/diagnose_soak.sh --export-only
#   ./utils/diagnose_soak.sh --db ../PrizmForge-Soak/Soak6-target/PrizmForge/.PrizmForge/agents.db

set -u -o pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_REPO="$(cd "${SOURCE_REPO:-$SCRIPT_DIR/..}" && pwd)"

QUERY_SCRIPT="${SCRIPT_DIR}/query_developer_responses.py"
SOAK_ROOT="${SOAK_ROOT:-$SOURCE_REPO/../PrizmForge-Soak}"

PYTHON_EXEC="${PYTHON_EXEC:-}"
TASK_ID="${TASK_ID:-task_001}"
LIMIT=100
TRAJECTORY_LIMIT=10
SOAK_N=""
DB_PATH=""
EXPORT_DIR="${EXPORT_DIR:-$SOURCE_REPO/docs/soak-artifacts}"
EXPORT_ONLY=0
NO_EXPORT=0
NO_TRAJECTORIES=0

usage() {
  cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Diagnose the newest PrizmForge soak target by default.
Uses the repo .venv interpreter the same way utils/run_tests.sh does.

Options:
  -p, --python PATH         Python interpreter (default: .venv or python3).
  -d, --db PATH             Explicit agents.db path; bypasses soak discovery.
  -s, --soak NUMBER         Query a specific SoakN target.
      --soak-root PATH      Root containing SoakN / SoakN-target directories.
  -t, --task TASK_ID        Task identifier to inspect. Default: task_001.
  -l, --limit NUMBER        Limit errors and lifecycle events. Default: 100.
      --trajectory-limit N  Most-recent trajectory files to inspect. Default: 10.
      --export-dir PATH     Directory for SQL pack files.
                            Default: docs/soak-artifacts
      --export-only         Write every section to docs/soak-artifacts; no console dump.
      --no-export           Skip writing docs/soak-artifacts/*.txt
      --no-trajectories     Skip trajectory JSON walk.
  -h, --help                Show this help.

Examples:
  ./utils/diagnose_soak.sh
  ./utils/diagnose_soak.sh --soak 6 --task task_001
  ./utils/diagnose_soak.sh --export-only --soak 6
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

resolve_python() {
  if [[ -n "${PYTHON_EXEC:-}" ]]; then
    printf '%s\n' "$PYTHON_EXEC"
    return
  fi
  if [[ -x "${SOURCE_REPO}/.venv/bin/python" ]]; then
    printf '%s\n' "${SOURCE_REPO}/.venv/bin/python"
    return
  fi
  if [[ -x "${SOURCE_REPO}/.venv/Scripts/python.exe" ]]; then
    printf '%s\n' "${SOURCE_REPO}/.venv/Scripts/python.exe"
    return
  fi
  if [[ -n "${VIRTUAL_ENV:-}" ]]; then
    if [[ -x "${VIRTUAL_ENV}/bin/python" ]]; then
      printf '%s\n' "${VIRTUAL_ENV}/bin/python"
      return
    fi
    if [[ -x "${VIRTUAL_ENV}/Scripts/python.exe" ]]; then
      printf '%s\n' "${VIRTUAL_ENV}/Scripts/python.exe"
      return
    fi
  fi
  printf '%s\n' "python3"
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
    --export-dir)
      require_value "$1" "${2:-}"
      EXPORT_DIR="$2"
      shift 2
      ;;
    --export-only)
      EXPORT_ONLY=1
      shift
      ;;
    --no-export)
      NO_EXPORT=1
      shift
      ;;
    --no-trajectories)
      NO_TRAJECTORIES=1
      shift
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
    for var_name in PYTHON_EXEC SOAK_ROOT DB_PATH EXPORT_DIR; do
      value="${!var_name}"

      if [[ -n "$value" \
         && "$value" =~ ^[A-Za-z]:[\\/].* ]] \
         && command -v cygpath >/dev/null 2>&1; then
        printf -v "$var_name" '%s' "$(cygpath -u "$value")"
      fi
    done
    ;;
esac

PYTHON_EXEC="$(resolve_python)"

# Default: highest SoakN-target that has an agents.db.
find_latest_soak_db() {
  local max_soak=-1
  local soak_number
  local candidate
  local directory

  shopt -s nullglob

  for directory in "$SOAK_ROOT"/Soak[0-9]*-target; do
    [[ -d "$directory" ]] || continue
    [[ "$(basename "$directory")" =~ ^Soak([0-9]+)-target$ ]] || continue
    soak_number="${BASH_REMATCH[1]}"

    candidate=""
    if [[ -f "$directory/PrizmForge/.PrizmForge/agents.db" ]]; then
      candidate="$directory/PrizmForge/.PrizmForge/agents.db"
    elif [[ -f "$directory/PrizmForge/.prizmforge/agents.db" ]]; then
      candidate="$directory/PrizmForge/.prizmforge/agents.db"
    fi

    if [[ -n "$candidate" ]] && (( soak_number > max_soak )); then
      max_soak="$soak_number"
      DB_PATH="$candidate"
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
  if [[ ! -f "$DB_PATH" ]]; then
    DB_PATH="$SOAK_ROOT/Soak${SOAK_N}-target/PrizmForge/.prizmforge/agents.db"
  fi

  [[ -f "$DB_PATH" ]] || {
    echo "Error: Soak${SOAK_N} target database was not found under:" >&2
    echo "  $SOAK_ROOT/Soak${SOAK_N}-target/PrizmForge/.PrizmForge/agents.db" >&2
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

# Force UTF-8 from native Windows Python, including redirected files.
export PYTHONUTF8=1
export PYTHONIOENCODING="utf-8"

if ! "$PYTHON_EXEC" -X utf8 -c "import sys" >/dev/null 2>&1; then
  echo "Error: Python interpreter could not be run: $PYTHON_EXEC" >&2
  exit 1
fi

py() {
  "$PYTHON_EXEC" -X utf8 "$@"
}

write_section() {
  local slug="$1"
  local dest="$EXPORT_DIR/${slug}.txt"
  shift

  mkdir -p "$EXPORT_DIR"
  if [[ "$NO_EXPORT" -eq 1 ]]; then
    "$@"
    return $?
  fi

  set +e
  "$@" >"$dest" 2>&1
  local rc=$?
  set -u -o pipefail
  echo "  $dest"
  if [[ "$EXPORT_ONLY" -eq 0 ]]; then
    cat "$dest" || true
  fi
  return "$rc"
}

run_query() {
  local slug="$1"
  local title="$2"
  shift 2

  echo
  echo "================================================================================"
  echo "QUERY: $title"
  echo "================================================================================"

  if ! write_section "$slug" py "$QUERY_SCRIPT" --db "$DB_PATH" "$@"; then
    echo "WARNING: query failed; continuing." >&2
  fi
}

export_sql() {
  local name="$1"
  local sql="$2"
  local dest="$EXPORT_DIR/${name}.txt"

  mkdir -p "$EXPORT_DIR"
  echo "  $dest"
  if ! py "$QUERY_SCRIPT" --sql "$sql" --db "$DB_PATH" >"$dest" 2>&1; then
    echo "WARNING: $name failed (see $dest)." >&2
  fi
}

export_mutation_pack() {
  echo
  echo "================================================================================"
  echo "EXPORT mutation SQL pack -> $EXPORT_DIR"
  echo "================================================================================"

  mkdir -p "$EXPORT_DIR"

  export_sql "00_tables" \
    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"

  export_sql "00_pragma_tasks" \
    "PRAGMA table_info(tasks);"

  export_sql "00_pragma_archive" \
    "PRAGMA table_info(agent_responses_archive);"

  export_sql "00_pragma_proposals" \
    "PRAGMA table_info(edit_proposals);"

  export_sql "01_funnel" \
    "SELECT (SELECT COUNT(*) FROM tasks) AS tasks, (SELECT COUNT(*) FROM agent_responses_archive WHERE agent_name='developer') AS developer_replies, (SELECT COUNT(*) FROM agent_responses_archive WHERE agent_name='developer' AND command IS NOT NULL AND TRIM(command)<>'') AS replies_with_command, (SELECT COUNT(*) FROM agent_responses_archive WHERE agent_name='developer' AND command_exit_code=0) AS commands_ok, (SELECT COUNT(*) FROM edit_proposals) AS proposals, (SELECT COUNT(*) FROM edit_proposals WHERE status='applied') AS applied, (SELECT COUNT(*) FROM file_write_log) AS writes, (SELECT COUNT(*) FROM file_modifications) AS file_mods;"

  export_sql "02_proposals" \
    "SELECT substr(proposal_id,1,8) AS pid, target_file_path, status, selected_mode, final_mode, fallback_used, created_at, substr(replace(replace(coalesce(rationale,''), char(10), ' '), char(13), ''),1,160) AS rationale FROM edit_proposals ORDER BY created_at;"

  export_sql "03_reviewer_heads" \
    "SELECT id, timestamp, task_id, parse_success, length(response) AS resp_len, substr(replace(replace(coalesce(response,''), char(10), ' | '), char(13), ''),1,280) AS resp_head FROM agent_responses_archive WHERE agent_name='reviewer' ORDER BY timestamp;"

  export_sql "04_developer_protocol" \
    "SELECT coalesce(response_format_status,'(null)') AS format_status, coalesce(parse_error,'(null)') AS parse_error, parse_success, COUNT(*) AS n, ROUND(AVG(length(response)),1) AS avg_resp, ROUND(AVG(length(prompt)),1) AS avg_prompt FROM agent_responses_archive WHERE agent_name='developer' GROUP BY 1,2,3 ORDER BY n DESC;"

  export_sql "05_command_buckets" \
    "SELECT SUM(CASE WHEN command LIKE '%git rev-parse%' OR command LIKE '%ls -la%' THEN 1 ELSE 0 END) AS evidence_cmds, SUM(CASE WHEN command LIKE '%sed -n%' OR command LIKE '%nl %' THEN 1 ELSE 0 END) AS inspect_cmds, SUM(CASE WHEN lower(command) LIKE '%echo%shell%' OR lower(command) LIKE '%no shell%' THEN 1 ELSE 0 END) AS refusal_echo, SUM(CASE WHEN command LIKE '%git rev-parse%' OR command LIKE '%ls -la%' OR command LIKE '%sed -n%' OR command LIKE '%nl %' OR lower(command) LIKE '%echo%shell%' THEN 0 WHEN command IS NOT NULL AND trim(command)<>'' THEN 1 ELSE 0 END) AS other_cmds, COUNT(*) AS cmd_rows FROM agent_responses_archive WHERE agent_name='developer' AND command IS NOT NULL AND trim(command)<>'';"

  export_sql "05b_command_samples" \
    "SELECT id, timestamp, task_id, command_exit_code, substr(replace(replace(coalesce(command,''), char(10), ' '), char(13), ''),1,120) AS cmd FROM agent_responses_archive WHERE agent_name='developer' AND command IS NOT NULL AND trim(command)<>'' ORDER BY timestamp;"

  export_sql "06_events" \
    "SELECT type, COUNT(*) AS n FROM events WHERE type LIKE 'shell%' OR type LIKE 'edit.%' OR type LIKE '%stall%' OR type LIKE '%latch%' OR type LIKE '%proposal%' GROUP BY type ORDER BY n DESC;"

  export_sql "07_tasks" \
    "SELECT * FROM tasks ORDER BY id;"

  export_sql "08_open_feedback" \
    "SELECT id, priority, addressed, task_id, substr(replace(replace(coalesce(message,''), char(10), ' '), char(13), ''),1,160) AS msg FROM agent_feedback WHERE addressed=0 ORDER BY id;"

  export_sql "09_agent_counts" \
    "SELECT agent_name, COUNT(*) AS n, SUM(CASE WHEN parse_success=1 THEN 1 ELSE 0 END) AS parse_ok FROM agent_responses_archive GROUP BY agent_name ORDER BY n DESC;"

  export_sql "10_model_health" \
    "SELECT model_ref, kind, ok, COUNT(*) AS n FROM model_health_events GROUP BY model_ref, kind, ok ORDER BY n DESC;"

  echo "Export complete."
}

inspect_trajectories() {
  local trajectory_dir
  trajectory_dir="$(dirname "$DB_PATH")/shell_trajectories"

  echo
  echo "================================================================================"
  echo "SHELL-DEVELOPER TRAJECTORIES"
  echo "================================================================================"
  echo "Directory: $trajectory_dir"
  echo "Task:      $TASK_ID"
  echo "Limit:     $TRAJECTORY_LIMIT"

  if [[ ! -d "$trajectory_dir" ]]; then
    echo "No shell_trajectories directory found."
    return 0
  fi

  py - "$trajectory_dir" "$TASK_ID" "$TRAJECTORY_LIMIT" "$SOURCE_REPO" <<'PY'
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
    "exit_status",
    "commands_executed",
    "submission_summary",
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
print("HAS_BASH_BLOCK       Expected bash protocol was emitted.")
print("HAS_FINISH_TOKEN     Expected FINISH_EDIT_SESSION protocol was emitted.")
print("NO_PROTOCOL_MARKER   Model likely returned prose, JSON, or another format.")
PY
}

mkdir -p "$EXPORT_DIR"

{
  echo "================================================================================"
  echo "PrizmForge Soak Diagnostic"
  echo "================================================================================"
  echo "Source repo: $SOURCE_REPO"
  echo "Soak root:   $SOAK_ROOT"
  echo "Selected:    Soak${SOAK_N:-custom database}"
  echo "Database:    $DB_PATH"
  echo "Task:        $TASK_ID"
  echo "Python:      $PYTHON_EXEC"
  echo "Export dir:  $EXPORT_DIR"
} | tee "$EXPORT_DIR/00_header.txt"

if [[ "$NO_EXPORT" -eq 0 ]]; then
  export_mutation_pack
fi

if [[ "$NO_TRAJECTORIES" -eq 0 ]]; then
  echo
  echo "================================================================================"
  echo "SHELL-DEVELOPER TRAJECTORIES"
  echo "================================================================================"
  if ! write_section 30_trajectories inspect_trajectories; then
    echo "WARNING: trajectory inspect failed; continuing." >&2
  fi
fi

run_query 20_diagnostic \
  "Full diagnostic for selected task" \
  --diagnostic \
  --task "$TASK_ID"

run_query 21_developer_responses \
  "Developer responses" \
  --responses \
  --agent developer \
  --task "$TASK_ID"

run_query 22_all_responses \
  "All responses for selected task" \
  --responses \
  --task "$TASK_ID"

run_query 23_repeated_format \
  "Shell protocol errors: RepeatedFormatError" \
  --errors \
  --keyword "RepeatedFormatError" \
  --limit "$LIMIT"

run_query 24_no_file_changes \
  "Developer sessions that finished with no changes" \
  --errors \
  --keyword "produced no file changes" \
  --limit "$LIMIT"

run_query 25_sqlite_locked \
  "SQLite lock failures" \
  --errors \
  --keyword "database is locked" \
  --limit "$LIMIT"

run_query 26_high_errors \
  "Recent HIGH errors" \
  --errors HIGH \
  --limit "$LIMIT"

run_query 27_proposals \
  "Edit proposals" \
  --proposals

run_query 28_write_log \
  "File write/materialization log" \
  --write-log

run_query 29_events \
  "Edit lifecycle events" \
  --events \
  --limit "$LIMIT"

run_query 31_open_feedback \
  "Open feedback backlog" \
  --sql "SELECT * FROM agent_feedback WHERE addressed = 0"

run_query 32_open_feedback_task \
  "Open feedback for selected task" \
  --sql "SELECT * FROM agent_feedback WHERE addressed = 0 AND task_id = '${TASK_ID}'"

run_query 33_model_health \
  "Model and endpoint health" \
  --model-health

echo
echo "================================================================================"
echo "Diagnostic complete."
echo "SQL pack: $EXPORT_DIR"
echo "================================================================================"