#!/usr/bin/env bash

# Test suite runner for PrizmForge
# Supports quick / normal / full / slow, optional sequential batching for
# memory-safe full runs on ~16GB hosts.

set -euo pipefail

cd "$(dirname "$0")/.."
REPO_ROOT="$(pwd)"

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
# Resolve Python: explicit PYTHON_EXEC env > project .venv > active venv > python3
resolve_python() {
  if [[ -n "${PYTHON_EXEC:-}" ]]; then
    printf '%s\n' "$PYTHON_EXEC"
    return
  fi
  if [[ -x "${REPO_ROOT}/.venv/bin/python" ]]; then
    printf '%s\n' "${REPO_ROOT}/.venv/bin/python"
    return
  fi
  if [[ -x "${REPO_ROOT}/.venv/Scripts/python.exe" ]]; then
    printf '%s\n' "${REPO_ROOT}/.venv/Scripts/python.exe"
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

PYTHON_EXEC="$(resolve_python)"
TEST_MODE="quick"       # quick | normal | full | slow
PARALLEL_JOBS="auto"    # auto | 1 | N
BATCHED=0               # 0 = single pytest invocation; 1 = sequential batches
BATCH_FILTER=""         # optional: run only this batch name when BATCHED=1
PER_TEST_TIMEOUT=30     # seconds; requires pytest-timeout
REPORT_DIR=".PrizmForge/reports"

# Heavy files: own batch, always serial (-j 1) to avoid SQLite / fixture OOM
HEAVY_TARGETS=(
  "tests/test_governed_editing.py"
  "tests/unit/test_hardening.py"
  "tests/unit/test_task_runner.py"
  "tests/unit/test_parallel_workers.py"
  "tests/unit/test_worker_lifecycle.py"
  "tests/integration/test_unattended_with_mock.py"
)

show_help() {
  cat << EOF
Usage: $(basename "$0") [OPTIONS] [-- [PYTEST_ARGS]]

Test suite runner for PrizmForge.

Options:
  -p, --python PATH     Path to Python executable
                        (default: .venv if present, else python3)
  -j, --jobs NUM        xdist workers (default: auto; batched defaults to 2;
                        heavy, slow, and full-mode integration always use 1)
  -q, --quick           Fast-gate subset (default)
  -n, --normal          All tests under tests/ except @pytest.mark.slow
  -f, --full            Complete suite including slow tests
  -s, --only-slow       Only @pytest.mark.slow
  -b, --batched         Sequential batches with per-batch logs (recommended for
                        --full / --normal on 16GB machines)
      --batch NAME      With --batched, run only one batch (unit|heavy|integration|root|slow)
      --timeout SEC     Per-test timeout seconds (default: ${PER_TEST_TIMEOUT}; 0 disables;
                        needs pytest-timeout)
  -h, --help            Show this help

Batch layout (--batched with --normal or --full):
  unit         tests/unit/ excluding heavy files  (small -j, not slow)
  heavy        concurrency-heavy targets          (serial -j 1, not slow)
  integration  tests/integration/ excluding heavy (small -j under normal;
               serial -j 1 under --full; not slow)
  root         tests/*.py root files not in heavy (small -j, not slow)
  slow         @pytest.mark.slow only             (serial -j 1; --full and --only-slow)

Under --full --batched:
  - slow tests are NEVER mixed into parallel batches; they run only in the
    final serial "slow" batch.
  - the integration batch is forced serial (-j 1) to avoid xdist worker
    deaths (node down / exit 120) seen on ~16GB hosts.

Each batch writes:
  ${REPORT_DIR}/pytest-batch-<name>-<timestamp>.log
  ${REPORT_DIR}/pytest-full-summary-<timestamp>.txt  (append summary lines)

Failed batches do not stop later batches; final exit code is non-zero if any
batch failed.

Examples:
  # Quick gate (uses .venv automatically after ./utils/setup.sh)
  $0

  # Memory-safe full suite
  $0 --full --batched -j 2

  # Override interpreter
  $0 -p /usr/bin/python3.12 --normal

  # Only the heavy serial batch
  $0 --full --batched --batch heavy -j 1

  # Only slow tests (serial)
  $0 --only-slow --batched --batch slow -j 1

  # Re-run last failures (pytest built-in)
  $0 --full --batched -- --lf
EOF
}

# ---------------------------------------------------------------------------
# Args
# ---------------------------------------------------------------------------
PYTEST_EXTRA_ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    -p|--python)
      [[ -n "${2:-}" && ! "$2" =~ ^- ]] || { echo "Error: $1 needs a path" >&2; exit 1; }
      PYTHON_EXEC="$2"
      shift 2
      ;;
    -j|--jobs)
      [[ -n "${2:-}" && ! "$2" =~ ^- ]] || { echo "Error: $1 needs a worker count" >&2; exit 1; }
      PARALLEL_JOBS="$2"
      shift 2
      ;;
    -q|--quick)   TEST_MODE="quick";  shift ;;
    -n|--normal)  TEST_MODE="normal"; shift ;;
    -f|--full)    TEST_MODE="full";   shift ;;
    -s|--only-slow) TEST_MODE="slow"; shift ;;
    -b|--batched) BATCHED=1; shift ;;
    --batch)
      [[ -n "${2:-}" && ! "$2" =~ ^- ]] || { echo "Error: --batch needs a name" >&2; exit 1; }
      BATCH_FILTER="$2"
      BATCHED=1
      shift 2
      ;;
    --timeout)
      [[ -n "${2:-}" && ! "$2" =~ ^- ]] || { echo "Error: --timeout needs seconds" >&2; exit 1; }
      PER_TEST_TIMEOUT="$2"
      shift 2
      ;;
    -h|--help) show_help; exit 0 ;;
    --)
      shift
      PYTEST_EXTRA_ARGS+=("$@")
      break
      ;;
    *)
      PYTEST_EXTRA_ARGS+=("$1")
      shift
      ;;
  esac
done

# Batched only makes sense for normal/full/slow
if [[ "$BATCHED" -eq 1 && "$TEST_MODE" == "quick" ]]; then
  echo "Note: --batched with --quick is a no-op; running quick gate as a single invocation."
  BATCHED=0
fi

# Default small worker count when batched and user left auto
if [[ "$BATCHED" -eq 1 && "$PARALLEL_JOBS" == "auto" ]]; then
  PARALLEL_JOBS=2
fi

mkdir -p "$REPORT_DIR"
STAMP="$(date +%Y%m%d_%H%M%S)"
SUMMARY_FILE="${REPORT_DIR}/pytest-full-summary-${STAMP}.txt"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

path_exists() { [[ -e "$1" ]]; }

# Append -m filter for parallel/heavy batches.
# normal + full: exclude slow (slow runs in its own serial batch under full).
# slow mode: only slow tests.
# Prefer explicit array append over nameref so Git Bash / older bash still
# show "-m not slow" in the BATCH targets line.
append_batch_marker() {
  local -n _batch_args="$1"
  case "$TEST_MODE" in
    normal|full)
      _batch_args+=("-m" "not slow")
      ;;
    slow)
      _batch_args+=("-m" "slow")
      ;;
  esac
}

run_pytest_once() {
  # Args: batch_name jobs target1 [target2 ...]
  local batch_name="$1"
  local jobs="$2"
  shift 2
  local targets=("$@")

  local log_file="${REPORT_DIR}/pytest-batch-${batch_name}-${STAMP}.log"
  local xdist=()
  if [[ "$jobs" != "1" ]]; then
    xdist=(-n "$jobs" --dist loadfile)
  fi

  local timeout_args=()
  if [[ -n "$PER_TEST_TIMEOUT" && "$PER_TEST_TIMEOUT" != "0" ]]; then
    timeout_args=(--timeout="$PER_TEST_TIMEOUT" --timeout-method=thread)
  fi

  echo ""
  echo "============================================================"
  echo "BATCH: ${batch_name}  jobs=${jobs}  targets=${targets[*]}"
  echo "LOG:   ${log_file}"
  echo "============================================================"

  local start_ts end_ts rc duration
  start_ts="$(date +%s)"
  set +e
  "$PYTHON_EXEC" -m pytest \
    "${targets[@]}" \
    "${xdist[@]}" \
    "${timeout_args[@]}" \
    -q --tb=line \
    "${PYTEST_EXTRA_ARGS[@]}" \
    2>&1 | tee "$log_file"
  rc="${PIPESTATUS[0]}"
  set -e
  end_ts="$(date +%s)"
  duration="$((end_ts - start_ts))"

  local status="PASS"
  [[ "$rc" -eq 0 ]] || status="FAIL"

  local pytest_line
  pytest_line="$(grep -E 'passed|failed|error|skipped' "$log_file" | tail -1 || true)"

  {
    echo "[${STAMP}] batch=${batch_name} status=${status} exit=${rc} duration_s=${duration} jobs=${jobs}"
    echo "  log=${log_file}"
    echo "  targets=${targets[*]}"
    [[ -n "$pytest_line" ]] && echo "  result=${pytest_line}"
  } | tee -a "$SUMMARY_FILE"

  return "$rc"
}

# ---------------------------------------------------------------------------
# Non-batched path (original behavior + timeout + log)
# ---------------------------------------------------------------------------
run_single_invocation() {
  local targets=()
  case "$TEST_MODE" in
    quick)
      targets=(
        "tests/unit/test_edit_contracts.py"
        "tests/integration/test_prizmforge_architecture.py"
        "tests/integration/test_golden_path.py"
        "tests/integration/test_run_task_cycle.py"
        "tests/unit/test_events_undo.py"
        "tests/unit/test_hardening.py"
        "tests/unit/test_developer_edit_helpers.py"
        "tests/unit/test_llm_mocks.py"
      )
      ;;
    normal)
      targets=("tests/" "-m" "not slow")
      ;;
    full)
      targets=("tests/")
      ;;
    slow)
      targets=("tests/" "-m" "slow")
      ;;
  esac

  local jobs="$PARALLEL_JOBS"
  local xdist=()
  if [[ "$jobs" != "1" ]]; then
    xdist=(-n "$jobs" --dist loadfile)
  fi
  local timeout_args=()
  if [[ -n "$PER_TEST_TIMEOUT" && "$PER_TEST_TIMEOUT" != "0" ]]; then
    timeout_args=(--timeout="$PER_TEST_TIMEOUT" --timeout-method=thread)
  fi

  local log_file="${REPORT_DIR}/pytest-${TEST_MODE}-${STAMP}.log"
  echo "Running mode=${TEST_MODE} jobs=${jobs} python=${PYTHON_EXEC} log=${log_file}"
  set +e
  "$PYTHON_EXEC" -m pytest \
    "${targets[@]}" \
    "${xdist[@]}" \
    "${timeout_args[@]}" \
    -q --tb=line \
    "${PYTEST_EXTRA_ARGS[@]}" \
    2>&1 | tee "$log_file"
  local rc="${PIPESTATUS[0]}"
  set -e
  echo "exit=${rc} log=${log_file}" | tee -a "$SUMMARY_FILE"
  return "$rc"
}

# ---------------------------------------------------------------------------
# Batched path
# ---------------------------------------------------------------------------
should_run_batch() {
  local name="$1"
  [[ -z "$BATCH_FILTER" || "$BATCH_FILTER" == "$name" ]]
}

run_batched() {
  local overall_rc=0
  local jobs_small="$PARALLEL_JOBS"
  [[ "$jobs_small" == "auto" ]] && jobs_small=2

  # Under --full, integration is forced serial to avoid xdist node deaths
  # (node down / exit 120) observed on ~16GB hosts after long runs.
  local jobs_integration="$jobs_small"
  if [[ "$TEST_MODE" == "full" ]]; then
    jobs_integration=1
  fi

  echo "Batched run mode=${TEST_MODE} small_jobs=${jobs_small} integration_jobs=${jobs_integration} heavy_jobs=1 slow_jobs=1"
  echo "Summary file: ${SUMMARY_FILE}"
  echo "Batches continue after failure."
  if [[ "$TEST_MODE" == "full" ]]; then
    echo "Note: --full excludes @pytest.mark.slow from parallel/heavy batches;"
    echo "      slow tests run only in the final serial 'slow' batch."
    echo "Note: --full forces the integration batch to serial (-j 1)."
  fi

  # ---- unit (light) ----
  if should_run_batch unit; then
    if path_exists tests/unit; then
      local unit_args=("tests/unit")
      local h
      for h in "${HEAVY_TARGETS[@]}"; do
        if [[ "$h" == tests/unit/* ]]; then
          unit_args+=("--ignore=${h}")
        fi
      done
      append_batch_marker unit_args
      if ! run_pytest_once unit "$jobs_small" "${unit_args[@]}"; then
        overall_rc=1
      fi
    fi
  fi

  # ---- heavy (serial) ----
  if should_run_batch heavy; then
    local heavy_args=()
    local h
    for h in "${HEAVY_TARGETS[@]}"; do
      path_exists "$h" && heavy_args+=("$h")
    done
    if [[ ${#heavy_args[@]} -gt 0 ]]; then
      append_batch_marker heavy_args
      if ! run_pytest_once heavy 1 "${heavy_args[@]}"; then
        overall_rc=1
      fi
    fi
  fi

  # ---- integration (serial under --full; small -j under --normal) ----
  if should_run_batch integration; then
    if path_exists tests/integration; then
      local int_args=("tests/integration")
      for h in "${HEAVY_TARGETS[@]}"; do
        if [[ "$h" == tests/integration/* ]]; then
          int_args+=("--ignore=${h}")
        fi
      done
      append_batch_marker int_args
      if ! run_pytest_once integration "$jobs_integration" "${int_args[@]}"; then
        overall_rc=1
      fi
    fi
  fi

  # ---- root tests/*.py (not heavy) ----
  if should_run_batch root; then
    local root_args=()
    local f
    for f in tests/*.py; do
      [[ -f "$f" ]] || continue
      local base
      base="$(basename "$f")"
      [[ "$base" == "conftest.py" || "$base" == "__init__.py" ]] && continue
      local skip=0
      for h in "${HEAVY_TARGETS[@]}"; do
        [[ "$f" == "$h" ]] && skip=1 && break
      done
      [[ "$skip" -eq 1 ]] && continue
      root_args+=("$f")
    done
    if [[ ${#root_args[@]} -gt 0 ]]; then
      append_batch_marker root_args
      if ! run_pytest_once root "$jobs_small" "${root_args[@]}"; then
        overall_rc=1
      fi
    fi
  fi

  # ---- slow-only batch (serial) ----
  # Under --full: all @pytest.mark.slow live here only (not in parallel batches).
  # Under --only-slow / --batch slow: this is the whole run.
  if should_run_batch slow && [[ "$TEST_MODE" == "slow" || "$TEST_MODE" == "full" || "$BATCH_FILTER" == "slow" ]]; then
    if ! run_pytest_once slow 1 "tests/" "-m" "slow"; then
      overall_rc=1
    fi
  fi

  echo ""
  echo "============================================================"
  echo "Batched run complete. overall_exit=${overall_rc}"
  echo "Summary: ${SUMMARY_FILE}"
  echo "============================================================"
  return "$overall_rc"
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if [[ "$BATCHED" -eq 1 ]]; then
  run_batched
  exit $?
else
  run_single_invocation
  exit $?
fi
