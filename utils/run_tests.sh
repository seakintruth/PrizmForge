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

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
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
DURATIONS_N=50

show_help() {
  cat << EOF
Usage: $(basename "$0") [OPTIONS] [-- [PYTEST_ARGS]]

Test suite runner for PrizmForge.

Markers (orthogonal):
  @pytest.mark.slow     long-running → excluded from --normal
  @pytest.mark.serial   isolation    → always -j 1 (still in --normal if not slow)

Options:
  -p, --python PATH     Path to Python executable
                        (default: .venv if present, else python3)
  -j, --jobs NUM        xdist workers for *parallel* batches (default: auto;
                        batched defaults to 2). serial / slow-serial always use 1.
  -q, --quick           Fast-gate subset (default)
  -n, --normal          All tests except @pytest.mark.slow
                        (includes serial-but-fast tests at -j 1)
  -f, --full            Complete suite including slow tests
  -s, --only-slow       Only @pytest.mark.slow (parallel + serial slow batches)
  -b, --batched         Sequential batches with per-batch logs (recommended for
                        --full / --normal on 16GB machines)
      --batch NAME      With --batched, run only one batch:
                        unit|integration|root|serial|slow-parallel|slow-serial
      --timeout SEC     Per-test timeout seconds (default: ${PER_TEST_TIMEOUT}; 0 disables)
  -h, --help            Show this help

Batch layout (--batched):
  unit            tests/unit/            -m 'not slow and not serial'   (-j N)
  integration     tests/integration/     -m 'not slow and not serial'   (-j N;
                                          under --full forced -j 1 for host OOM)
  root            tests/*.py             -m 'not slow and not serial'   (-j N)
  serial          tests/                 -m 'serial and not slow'       (-j 1)
                  ↑ included in --normal
  slow-parallel   tests/                 -m 'slow and not serial'       (-j N;
                                          --full / --only-slow only)
  slow-serial     tests/                 -m 'slow and serial'           (-j 1;
                                          --full / --only-slow only)

Each batch writes:
  ${REPORT_DIR}/pytest-batch-<name>-<timestamp>.log
  ${REPORT_DIR}/pytest-full-summary-<timestamp>.txt

Failed batches do not stop later batches; final exit code is non-zero if any
batch failed.

Examples:
  $0
  $0 --normal --batched -j 2
  $0 --full --batched -j 2
  $0 --only-slow --batched --batch slow-parallel
  $0 --full --batched --batch serial -j 1
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
rm -f "${REPORT_DIR}/test-durations-latest.json"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

path_exists() { [[ -e "$1" ]]; }

run_pytest_once() {
  # Args: batch_name jobs target1 [target2 ...]
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
  set +e
  PRIZMFORGE_BATCH_NAME="$batch_name" \
  PRIZMFORGE_DURATION_REPORT="$duration_file" \
  PRIZMFORGE_REPORT_STAMP="$STAMP" \
  "$PYTHON_EXEC" -m pytest \
    "${targets[@]}" \
    "${xdist[@]}" \
    "${timeout_args[@]}" \
    --durations="$DURATIONS_N" \
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
      )
      ;;
    normal)
      # serial-but-fast stays in normal; only duration gate is slow
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
  # Non-batched --normal/--full with -j N still risks running serial tests under
  # xdist. Prefer --batched for memory-safe runs. When not batched, force -j 1
  # if the expression can include serial tests and jobs > 1 — warn only.
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
  set +e
  PRIZMFORGE_BATCH_NAME="$TEST_MODE" \
  PRIZMFORGE_DURATION_REPORT="$duration_file" \
  PRIZMFORGE_REPORT_STAMP="$STAMP" \
  "$PYTHON_EXEC" -m pytest \
    "${targets[@]}" \
    "${xdist[@]}" \
    "${timeout_args[@]}" \
    --durations="$DURATIONS_N" \
    -q --tb=line \
    "${PYTEST_EXTRA_ARGS[@]}" \
    2>&1 | tee "$log_file"
  local rc="${PIPESTATUS[0]}"
  set -e
  {
    echo "exit=${rc} log=${log_file}"
    echo "durations=${duration_file}"
  } | tee -a "$SUMMARY_FILE"
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

  # Host-level policy: under --full, integration parallel batch is forced serial
  # (-j 1) to avoid xdist node deaths on ~16GB hosts. This is not @pytest.mark.serial.
  local jobs_integration="$jobs_small"
  if [[ "$TEST_MODE" == "full" ]]; then
    jobs_integration=1
  fi

  local run_normal_batches=0
  local run_slow_batches=0
  case "$TEST_MODE" in
    normal) run_normal_batches=1 ;;
    full)   run_normal_batches=1; run_slow_batches=1 ;;
    slow)   run_slow_batches=1 ;;
  esac

  echo "Batched run mode=${TEST_MODE} parallel_jobs=${jobs_small} integration_jobs=${jobs_integration}"
  echo "Summary file: ${SUMMARY_FILE}"
  echo "Axes: slow=duration gate | serial=isolation (-j 1)"
  echo "Batches continue after failure."

  # ---- parallel: unit ----
  if should_run_batch unit && [[ "$run_normal_batches" -eq 1 ]]; then
    if path_exists tests/unit; then
      if ! run_pytest_once unit "$jobs_small" \
        "tests/unit" "-m" "not slow and not serial"; then
        overall_rc=1
      fi
    fi
  fi

  # ---- parallel: integration ----
  if should_run_batch integration && [[ "$run_normal_batches" -eq 1 ]]; then
    if path_exists tests/integration; then
      if ! run_pytest_once integration "$jobs_integration" \
        "tests/integration" "-m" "not slow and not serial"; then
        overall_rc=1
      fi
    fi
  fi

  # ---- parallel: root tests/*.py ----
  if should_run_batch root && [[ "$run_normal_batches" -eq 1 ]]; then
    local root_args=()
    local f base
    for f in tests/*.py; do
      [[ -f "$f" ]] || continue
      base="$(basename "$f")"
      [[ "$base" == "conftest.py" || "$base" == "__init__.py" ]] && continue
      root_args+=("$f")
    done
    if [[ ${#root_args[@]} -gt 0 ]]; then
      if ! run_pytest_once root "$jobs_small" \
        "${root_args[@]}" "-m" "not slow and not serial"; then
        overall_rc=1
      fi
    fi
  fi

  # ---- serial (not slow): stays in --normal ----
  if should_run_batch serial && [[ "$run_normal_batches" -eq 1 ]]; then
    if ! run_pytest_once serial 1 \
      "tests/" "-m" "serial and not slow"; then
      overall_rc=1
    fi
  fi

  # ---- slow + parallelizable ----
  if should_run_batch slow-parallel && [[ "$run_slow_batches" -eq 1 ]]; then
    if ! run_pytest_once slow-parallel "$jobs_small" \
      "tests/" "-m" "slow and not serial"; then
      overall_rc=1
    fi
  fi

  # ---- slow + serial ----
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
