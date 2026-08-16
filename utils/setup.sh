#!/usr/bin/env bash
# =============================================================================
# utils/setup.sh
# Create / reuse project-root .venv and install runtime + dev dependencies.
# =============================================================================

set -euo pipefail

cd "$(dirname "$0")/.."
REPO_ROOT="$(pwd)"
VENV_DIR="${REPO_ROOT}/.venv"

PYTHON_EXEC="${PYTHON_EXEC:-python3}"
FORCE_RECREATE=0

show_help() {
  cat << EOF
Usage: $(basename "$0") [OPTIONS]

Bootstrap a local Python virtual environment for PrizmForge and install
dependencies from requirements.txt and requirements-dev.txt.

Options:
  -p, --python PATH   Python interpreter used to create the venv (default: python3)
  -f, --force         Remove existing .venv and recreate it
  -h, --help          Show this help

Environment:
  PYTHON_EXEC         Same as --python (overridden by the flag when present)

After a successful run:
  source .venv/bin/activate          # Linux / macOS
  # or
  .venv\\Scripts\\activate           # Windows

Then use the suite as usual, e.g.:
  ./utils/run_tests.sh --normal
  python main.py
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -p|--python)
      [[ -n "${2:-}" && ! "$2" =~ ^- ]] || { echo "Error: $1 needs a path" >&2; exit 1; }
      PYTHON_EXEC="$2"
      shift 2
      ;;
    -f|--force)
      FORCE_RECREATE=1
      shift
      ;;
    -h|--help)
      show_help
      exit 0
      ;;
    *)
      echo "Error: unknown option: $1" >&2
      show_help >&2
      exit 1
      ;;
  esac
done

# ---------------------------------------------------------------------------
# Preconditions
# ---------------------------------------------------------------------------
if ! command -v "$PYTHON_EXEC" >/dev/null 2>&1; then
  echo "Error: Python interpreter not found: ${PYTHON_EXEC}" >&2
  exit 1
fi

if [[ ! -f "${REPO_ROOT}/requirements.txt" ]]; then
  echo "Error: requirements.txt not found at ${REPO_ROOT}/requirements.txt" >&2
  exit 1
fi

if [[ ! -f "${REPO_ROOT}/requirements-dev.txt" ]]; then
  echo "Error: requirements-dev.txt not found at ${REPO_ROOT}/requirements-dev.txt" >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# Create or recreate venv
# ---------------------------------------------------------------------------
if [[ "$FORCE_RECREATE" -eq 1 && -d "$VENV_DIR" ]]; then
  echo "Removing existing virtual environment: ${VENV_DIR}"
  rm -rf "$VENV_DIR"
fi

if [[ ! -d "$VENV_DIR" ]]; then
  echo "Creating virtual environment: ${VENV_DIR}"
  "$PYTHON_EXEC" -m venv "$VENV_DIR"
else
  echo "Reusing existing virtual environment: ${VENV_DIR}"
fi

# Resolve venv Python / pip (POSIX first, then Windows layout)
if [[ -x "${VENV_DIR}/bin/python" ]]; then
  VENV_PYTHON="${VENV_DIR}/bin/python"
elif [[ -x "${VENV_DIR}/Scripts/python.exe" ]]; then
  VENV_PYTHON="${VENV_DIR}/Scripts/python.exe"
else
  echo "Error: could not locate python inside ${VENV_DIR}" >&2
  exit 1
fi

echo "Using venv Python: ${VENV_PYTHON}"
"${VENV_PYTHON}" -c "import sys; print(f'  {sys.version.split()[0]} ({sys.executable})')"

# ---------------------------------------------------------------------------
# Install dependencies
# ---------------------------------------------------------------------------
echo "Upgrading pip..."
"${VENV_PYTHON}" -m pip install --upgrade pip

echo "Installing runtime dependencies (requirements.txt)..."
"${VENV_PYTHON}" -m pip install -r "${REPO_ROOT}/requirements.txt"

echo "Installing development / test dependencies (requirements-dev.txt)..."
"${VENV_PYTHON}" -m pip install -r "${REPO_ROOT}/requirements-dev.txt"

echo ""
echo "============================================================"
echo "Setup complete."
echo "  venv:   ${VENV_DIR}"
echo "  python: ${VENV_PYTHON}"
echo ""
echo "Activate with:"
if [[ -f "${VENV_DIR}/bin/activate" ]]; then
  echo "  source ${VENV_DIR}/bin/activate"
else
  echo "  ${VENV_DIR}\\Scripts\\activate"
fi
echo "============================================================"
