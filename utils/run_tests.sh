#!/usr/bin/env bash

# Test suite runner for PrizmForge (Parallelized Edition)

set -euo pipefail

cd "$(dirname "$0")/.."

# Default configuration
PYTHON_EXEC="python3"
TEST_MODE="quick"   # Modes: quick (default), normal, full, slow
PARALLEL_JOBS="auto" # Default: auto-detect CPU cores for parallel execution

# Help documentation
show_help() {
  cat << EOF
Usage: $(basename "$0") [OPTIONS] [-- [PYTEST_ARGS]]

Test suite runner for PrizmForge.

Options:
  -p, --python PATH    Path to Python executable (default: python3)
  -j, --jobs NUM       Number of parallel workers (default: auto, or 1 for single-threaded)
  -q, --quick          Run the fast-gate test subset (default).
  -n, --normal         Run the standard test suite under tests/, excluding slow tests (-m "not slow").
  -f, --full           Run the complete test suite under tests/, including all slow tests.
  -s, --only-slow      Run ONLY tests marked as @pytest.mark.slow (-m "slow").
  -h, --help           Display this help message and exit.

Test Modes:
  --quick (default)   Runs fast-gate core unit and integration test files:
                      - tests/unit/test_edit_contracts.py
                      - tests/integration/test_prizmforge_architecture.py
                      - tests/integration/test_golden_path.py
                      - tests/integration/test_run_task_cycle.py
                      - tests/unit/test_events_undo.py
                      - tests/unit/test_hardening.py
                      - tests/unit/test_developer_edit_helpers.py
                      - tests/unit/test_llm_mocks.py
  --normal            Runs all tests in tests/, skipping @pytest.mark.slow (-m "not slow").
  --full              Runs all tests in tests/ without skipping any tests.
  --only-slow         Runs ONLY tests marked with @pytest.mark.slow (-m "slow").

Examples:
  # Run quick gate in parallel using auto-detected CPU cores
  $0 -p C:\\git\\programs\\Python31209\\python.exe

  # Run ONLY slow tests in parallel
  $0 -p C:\\git\\programs\\Python31209\\python.exe --only-slow

  # Run ONLY slow tests using 4 parallel workers
  $0 -p C:\\git\\programs\\Python31209\\python.exe -s -j 4
EOF
}

# Parse command line arguments
PYTEST_EXTRA_ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    -p|--python)
      if [[ -n "${2:-}" && ! "$2" =~ ^- ]]; then
        PYTHON_EXEC="$2"
        shift 2
      else
        echo "Error: Option $1 requires a non-empty argument." >&2
        exit 1
      fi
      ;;
    -j|--jobs)
      if [[ -n "${2:-}" && ! "$2" =~ ^- ]]; then
        PARALLEL_JOBS="$2"
        shift 2
      else
        echo "Error: Option $1 requires a worker count." >&2
        exit 1
      fi
      ;;
    -q|--quick)
      TEST_MODE="quick"
      shift
      ;;
    -n|--normal)
      TEST_MODE="normal"
      shift
      ;;
    -f|--full)
      TEST_MODE="full"
      shift
      ;;
    -s|--only-slow)
      TEST_MODE="slow"
      shift
      ;;
    -h|--help)
      show_help
      exit 0
      ;;
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

# Configure test targets based on selected mode
case "$TEST_MODE" in
  quick)
    TEST_TARGETS=(
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
    TEST_TARGETS=(
      "tests/"
      "-m" "not slow"
    )
    ;;
  full)
    TEST_TARGETS=(
      "tests/"
    )
    ;;
  slow)
    TEST_TARGETS=(
      "tests/"
      "-m" "slow"
    )
    ;;
esac

# Configure parallel xdist flags with file-level grouping (--dist loadfile)
XDIST_ARGS=()
if [[ "$PARALLEL_JOBS" != "1" ]]; then
  XDIST_ARGS+=("-n" "$PARALLEL_JOBS" "--dist" "loadfile")
fi

# Execute pytest
"$PYTHON_EXEC" -m pytest \
  "${TEST_TARGETS[@]}" \
  "${XDIST_ARGS[@]}" \
  -q --tb=line \
  "${PYTEST_EXTRA_ARGS[@]}"
