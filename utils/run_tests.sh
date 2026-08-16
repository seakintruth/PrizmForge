#!/usr/bin/env bash

# Test suite runner for PrizmForge
#
# Two orthogonal markers drive scheduling (see pytest.ini):
#   slow   — long-running; excluded from --normal; may still use -j N
#   serial — isolation required; always -j 1; included in --normal when not slow
#
# --batched runs sequential *batches* (process groups). That is not the same
# as @pytest.mark.serial (per-test worker isolation).

set -euo pipefail

cd "$(dirname "$0")/.."
REPO_ROOT="$(pwd)"

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
TEST_MODE="quick"
PARALLEL_JOBS="auto"
BATCHED=0
BATCH_FILTER=""
PER_TEST_TIMEOUT=30
REPORT_DIR=".PrizmForge/reports"
DURATIONS_N=50

# Transitional path list: isolation-heavy modules forced into the serial batch
# even if a file has not yet been annotated with @pytest.mark.serial.
# Prefer markers; keep this list short and delete entries as markers land.
SERIAL_PATHS=(
  "tests/unit/test_hardening.py"
  "tests/unit/test_task_runner.py"
)

show_help() {
  cat << EOF
Usage: $(basename "$0") [OPTIONS] [-- [PYTEST_ARGS]]

Markers (orthogonal):
  @pytest.mark.slow     long-running → excluded from --normal
  @pytest.mark.serial   isolation    → always -j 1 (still in --normal if not slow)

Options:
  -p, --python PATH     Python executable (default: .venv or python3)
  -j, --jobs NUM        xdist workers for parallel batches (batched default: 2)
  -q, --quick           Fast-gate subset (default)
  -n, --normal          All tests except @pytest.mark.slow (serial-but-fast included)
  -f, --full            Complete suite including slow
  -s, --only-slow       Only @pytest.mark.slow
  -b, --batched         Sequential batches with per-batch logs
      --batch NAME      unit|integration|root|serial|slow-parallel|slow-serial
      --timeout SEC     Per-test timeout (default: ${PER_TEST_TIMEOUT}; 0 disables)
  -h, --help            Show this help

Batch matrix (--batched):
  unit / integration / root   not slow and not serial     (-j N)
  serial                      serial and not slow         (-j 1, in --normal)
                              + SERIAL_PATHS safety net
  slow-parallel               slow and not serial         (-j N, full/only-slow)
  slow-serial                 slow and serial             (-j 1, full/only-slow)
EOF
}

PYTEST_EXTRA_ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    -p|--python)
      [[ -n "${2:-}" && ! "$2" =~ ^- ]] || { echo "Error: $1 needs a path" >&2; exit 1; }
      PYTHON_EXEC="$2"; shift 2 ;;
    -j|--jobs)
      [[ -n "${2:-}" && ! "$2" =~ ^- ]] || { echo "Error: $1 needs a worker count" >&2; exit 1; }
      PARALLEL_JOBS="$2"; shift 2 ;;
    -q|--quick) TEST_MODE="quick"; shift ;;
    -n|--normal) TEST_MODE="normal"; shift ;;
    -f|--full) TEST_MODE="full"; shift ;;
    -s|--only-slow) TEST_MODE="slow"; shift ;;
    -b|--batched) BATCHED=1; shift ;;
    --batch)
      [[ -n "${2:-}" && ! "$2" =~ ^- ]] || { echo "Error: --batch needs a name" >&2; exit 1; }
      BATCH_FILTER="$2"; BATCHED=1; shift 2 ;;
    --timeout)
      [[ -n "${2:-}" && ! "$2" =~ ^- ]] || { echo "Error: --timeout needs seconds" >&2; exit 1; }
      PER_TEST_TIMEOUT="$2"; shift 2 ;;
    -h|--help) show_help; exit 0 ;;
    --) shift; PYTEST_EXTRA_ARGS+=("$@"); break ;;
    *) PYTEST_EXTRA_ARGS+=("$1"); shift ;;
  esac
done

if [[ "$BATCHED" -eq 1 && "$TEST_MODE" == "quick" ]]; then
  echo "Note: --batched with --quick is a no-op; running quick gate as a single invocation."
  BATCHED=0
fi
if [[ "$BATCHED" -eq 1 && "$PARALLEL_JOBS" == "auto" ]]; then
  PARALLEL_JOBS=2
fi

mkdir -p "$REPORT_DIR"
STAMP="$(date +%Y%m%d_%H%M%S)"
SUMMARY_FILE="${REPORT_DIR}/pytest-full-summary-${STAMP}.txt"
export PRIZMFORGE_REPORT_STAMP="$STAMP"
# Unbuffered Python so xdist worker failures flush into the log file under Git Bash.
export PYTHONUNBUFFERED=1
rm -f "${REPORT_DIR}/test-durations-latest.json"

path_exists() { [[ -e "$1" ]]; }

# Run pytest with stdout+stderr written to log_file, then echo the log to the
# terminal. Avoids `cmd | tee` pipe buffering / PIPESTATUS quirks on MSYS.
run_pytest_capture() {
  local log_file="$1"
  shift
  set +e
  "$@" >"$log_file" 2>&1
  local rc=$?
  set -e
  # Always surface the log on the controlling terminal (even on failure).
  cat "$log_file" || true
  return "$rc"
}

run_pytest_once() {
  local batch_name="$1"
  local jobs="$2"
  shift 2
  local targets=("$@")
  local log_file="${REPORT_DIR}/pytest-batch-${batch_name}-${STAMP}.log"
  local duration_file="${REPORT_DIR}/test-durations-${batch_name}-${STAMP}.json"
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
  echo "DUR:   ${duration_file}"
  echo "============================================================"
  local start_ts end_ts rc duration
  start_ts="$(date +%s)"
  PRIZMFORGE_BATCH_NAME="$batch_name" \
  PRIZMFORGE_DURATION_REPORT="$duration_file" \
  PRIZMFORGE_REPORT_STAMP="$STAMP" \
  run_pytest_capture "$log_file" \
    "$PYTHON_EXEC" -u -m pytest \
      "${targets[@]}" \
      "${xdist[@]}" \
      "${timeout_args[@]}" \
      --durations="$DURATIONS_N" \
      -q --tb=short \
      "${PYTEST_EXTRA_ARGS[@]}"
  rc=$?
  end_ts="$(date +%s)"
  duration="$((end_ts - start_ts))"
  local status="PASS"
  [[ "$rc" -eq 0 ]] || status="FAIL"
  local pytest_line
  pytest_line="$(grep -E 'passed|failed|error|skipped' "$log_file" | tail -1 || true)"
  {
    echo "[${STAMP}] batch=${batch_name} status=${status} exit=${rc} duration_s=${duration} jobs=${jobs}"
    echo "  log=${log_file}"
    echo "  durations=${duration_file}"
    echo "  targets=${targets[*]}"
    [[ -n "$pytest_line" ]] && echo "  result=${pytest_line}"
  } | tee -a "$SUMMARY_FILE"
  return "$rc"
}

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
      ) ;;
    normal) targets=("tests/" "-m" "not slow") ;;
    full) targets=("tests/") ;;
    slow) targets=("tests/" "-m" "slow") ;;
  esac
  local jobs="$PARALLEL_JOBS"
  if [[ "$jobs" != "1" && "$TEST_MODE" != "quick" ]]; then
    echo "Note: non-batched mode may schedule @pytest.mark.serial under xdist."
    echo "      Prefer: $0 --${TEST_MODE} --batched -j ${jobs}"
  fi
  local xdist=()
  if [[ "$jobs" != "1" && "$jobs" != "auto" ]]; then
    xdist=(-n "$jobs" --dist loadfile)
  elif [[ "$jobs" == "auto" ]]; then
    xdist=(-n auto --dist loadfile)
  fi
  local timeout_args=()
  if [[ -n "$PER_TEST_TIMEOUT" && "$PER_TEST_TIMEOUT" != "0" ]]; then
    timeout_args=(--timeout="$PER_TEST_TIMEOUT" --timeout-method=thread)
  fi
  local log_file="${REPORT_DIR}/pytest-${TEST_MODE}-${STAMP}.log"
  local duration_file="${REPORT_DIR}/test-durations-${TEST_MODE}-${STAMP}.json"
  echo "Running mode=${TEST_MODE} jobs=${jobs} python=${PYTHON_EXEC} log=${log_file}"
  PRIZMFORGE_BATCH_NAME="$TEST_MODE" \
  PRIZMFORGE_DURATION_REPORT="$duration_file" \
  PRIZMFORGE_REPORT_STAMP="$STAMP" \
  run_pytest_capture "$log_file" \
    "$PYTHON_EXEC" -u -m pytest \
      "${targets[@]}" "${xdist[@]}" "${timeout_args[@]}" \
      --durations="$DURATIONS_N" -q --tb=short \
      "${PYTEST_EXTRA_ARGS[@]}"
  local rc=$?
  { echo "exit=${rc} log=${log_file}"; echo "durations=${duration_file}"; } | tee -a "$SUMMARY_FILE"
  echo "Durations: ${REPORT_DIR}/test-durations-latest.json"
  echo "Analyze:   $PYTHON_EXEC utils/analyze_test_durations.py"
  return "$rc"
}

should_run_batch() {
  local name="$1"
  [[ -z "$BATCH_FILTER" || "$BATCH_FILTER" == "$name" ]]
}

run_batched() {
  local overall_rc=0
  local jobs_small="$PARALLEL_JOBS"
  [[ "$jobs_small" == "auto" ]] && jobs_small=2
  local jobs_integration="$jobs_small"
  if [[ "$TEST_MODE" == "full" ]]; then
    jobs_integration=1
  fi
  local run_normal_batches=0 run_slow_batches=0
  case "$TEST_MODE" in
    normal) run_normal_batches=1 ;;
    full) run_normal_batches=1; run_slow_batches=1 ;;
    slow) run_slow_batches=1 ;;
  esac

  echo "Batched run mode=${TEST_MODE} parallel_jobs=${jobs_small} integration_jobs=${jobs_integration}"
  echo "Summary file: ${SUMMARY_FILE}"
  echo "Axes: slow=duration gate | serial=isolation (-j 1)"
  echo "Batches continue after failure."

  local ignore_serial=()
  local p
  for p in "${SERIAL_PATHS[@]}"; do
    path_exists "$p" && ignore_serial+=("--ignore=${p}")
  done

  if should_run_batch unit && [[ "$run_normal_batches" -eq 1 ]]; then
    if path_exists tests/unit; then
      if ! run_pytest_once unit "$jobs_small" \
        "tests/unit" "-m" "not slow and not serial" "${ignore_serial[@]}"; then
        overall_rc=1
      fi
    fi
  fi

  if should_run_batch integration && [[ "$run_normal_batches" -eq 1 ]]; then
    if path_exists tests/integration; then
      if ! run_pytest_once integration "$jobs_integration" \
        "tests/integration" "-m" "not slow and not serial" "${ignore_serial[@]}"; then
        overall_rc=1
      fi
    fi
  fi

  if should_run_batch root && [[ "$run_normal_batches" -eq 1 ]]; then
    local root_args=() f base skip
    for f in tests/*.py; do
      [[ -f "$f" ]] || continue
      base="$(basename "$f")"
      [[ "$base" == "conftest.py" || "$base" == "__init__.py" ]] && continue
      skip=0
      for p in "${SERIAL_PATHS[@]}"; do
        [[ "$f" == "$p" ]] && skip=1 && break
      done
      [[ "$skip" -eq 1 ]] && continue
      root_args+=("$f")
    done
    if [[ ${#root_args[@]} -gt 0 ]]; then
      if ! run_pytest_once root "$jobs_small" \
        "${root_args[@]}" "-m" "not slow and not serial"; then
        overall_rc=1
      fi
    fi
  fi

  if should_run_batch serial && [[ "$run_normal_batches" -eq 1 ]]; then
    local serial_args=("tests/" "-m" "serial and not slow")
    # Path safety net (modules not yet marked serial still run here at -j 1)
    for p in "${SERIAL_PATHS[@]}"; do
      path_exists "$p" && serial_args+=("$p")
    done
    if ! run_pytest_once serial 1 "${serial_args[@]}"; then
      overall_rc=1
    fi
  fi

  if should_run_batch slow-parallel && [[ "$run_slow_batches" -eq 1 ]]; then
    if ! run_pytest_once slow-parallel "$jobs_small" \
      "tests/" "-m" "slow and not serial"; then
      overall_rc=1
    fi
  fi

  if should_run_batch slow-serial && [[ "$run_slow_batches" -eq 1 ]]; then
    if ! run_pytest_once slow-serial 1 \
      "tests/" "-m" "slow and serial"; then
      overall_rc=1
    fi
  fi

  echo ""
  echo "============================================================"
  echo "Batched run complete. overall_exit=${overall_rc}"
  echo "Summary: ${SUMMARY_FILE}"
  echo "Durations: ${REPORT_DIR}/test-durations-latest.json"
  echo "Analyze:   $PYTHON_EXEC utils/analyze_test_durations.py"
  echo "============================================================"
  return "$overall_rc"
}

if [[ "$BATCHED" -eq 1 ]]; then
  run_batched
  exit $?
else
  run_single_invocation
  exit $?
fi
