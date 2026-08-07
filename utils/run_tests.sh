#!/usr/bin/env bash

# Test suite runner for PrizmForge

set -euo pipefail

cd "$(dirname "$0")/.."

# Default configuration
PYTHON_EXEC="python3"
TEST_MODE="quick"  # Modes: quick (default), normal, full

# Help documentation
show_help() {
  cat << EOF
Usage: $(basename "$0") [OPTIONS] [-- [PYTEST_ARGS]]

Test suite runner for PrizmForge.

Options:
  -p, --python PATH    Path to Python executable (default: python3)
  -q, --quick          Run the fast-gate test subset (default).
  -n, --normal         Run the standard test suite under tests/, excluding slow tests (-m "not slow").
  -f, --full           Run the complete test suite under tests/, including all slow tests.
  -h, --help           Display this help message and exit.

Test Modes:
  --quick (default)   Runs fast-gate core unit and integration test files:
                      - tests/unit/test_edit_contracts.py
                      - tests/integration/test_golden_path.py
                      - tests/integration/test_run_task_cycle.py
                      - tests/unit/test_events_undo.py
                      - tests/unit/test_hardening.py
                      - tests/unit/test_developer_edit_helpers.py
                      - tests/unit/test_llm_mocks.py
  --normal            Runs all tests in tests/, skipping @pytest.mark.slow (-m "not slow").
  --full              Runs all tests in tests/ without skipping any tests (includes slow tests).

Examples:
  # Run default quick test gate using default python3
  $0

  # Run quick gate with a specific Python executable
  $0 -p C:\\git\\programs\\Python31209\\python.exe

  # Run normal test suite (skipping slow tests)
  $0 -p C:\\git\\programs\\Python31209\\python.exe --normal

  # Run full test suite (including slow tests)
  $0 -p C:\\git\\programs\\Python31209\\python.exe --full

  # Pass extra arguments to pytest
  $0 --normal -- -k "test_golden_path"
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
esac

# Execute pytest
"$PYTHON_EXEC" -m pytest \
  "${TEST_TARGETS[@]}" \
  -q --tb=line \
  "${PYTEST_EXTRA_ARGS[@]}"
