#!/usr/bin/env bash
# =============================================================================
# utils/setup.sh
# Create / reuse project-root .venv and install runtime + dev dependencies.
# Supports corporate environments by adding public PyPI as extra index.
# =============================================================================

set -euo pipefail

cd "$(dirname "$0")/.."
REPO_ROOT="$(pwd)"
VENV_DIR="${REPO_ROOT}/.venv"

PYTHON_EXEC="${PYTHON_EXEC:-python3}"
FORCE_RECREATE=0

# =============================================================================
# PyPI Configuration (for corporate mirrors)
# =============================================================================

# Always include the public PyPI as an extra index.
# This allows installation of packages that may not exist in internal mirrors.
PYPI_EXTRA_INDEX="--extra-index-url https://pypi.org/simple --trusted-host pypi.org --trusted-host files.pythonhosted.org"

# Helper to ensure all pip installs use the extra index
pip_install() {
    "${VENV_PYTHON}" -m pip install $PYPI_EXTRA_INDEX "$@"
}

# =============================================================================
# Help
# =============================================================================

show_help() {
  cat << EOF
Usage: $(basename "$0") [OPTIONS]

Bootstrap a local Python virtual environment for PrizmForge and install
dependencies from requirements.txt and requirements-dev.txt.

Options:
  -p, --python PATH   Python interpreter used to create the venv (default: python3)
  -f, --force         Remove existing .venv and recreate it
  -h, --help          Show this help
EOF
}

# =============================================================================
# Argument Parsing
# =============================================================================

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

# =============================================================================
# Preconditions
# =============================================================================

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

# =============================================================================
# Create or Recreate Virtual Environment
# =============================================================================

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

# Resolve venv Python binary (POSIX vs Windows)
if [[ -x "${VENV_DIR}/bin/python" ]]; then
  VENV_PYTHON="${VENV_DIR}/bin/python"
elif [[ -x "${VENV_DIR}/Scripts/python.exe" ]]; then
  VENV_PYTHON="${VENV_DIR}/Scripts/python.exe"
else
  echo "Error: could not locate python inside ${VENV_DIR}" >&2
  exit 1
fi

echo "Using venv Python: ${VENV_PYTHON}"

"${VENV_PYTHON}" -c '
import sys
ver = sys.version.split()[0]
print(f"  Python {ver} at {sys.executable}")
'

# ---------------------------------------------------------------------------
# Install dependencies
# ---------------------------------------------------------------------------
echo "Upgrading pip..."
pip_install --upgrade pip

echo "Installing runtime dependencies..."
pip_install -r "${REPO_ROOT}/requirements.txt"
echo "Installing development dependencies..."
pip_install -r "${REPO_ROOT}/requirements-dev.txt"

echo ""
echo "=============================================================="
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
echo ""
echo "To install the project in editable mode later, run:"
echo "  pip install -e ."
echo "=============================================================="