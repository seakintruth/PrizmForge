#!/usr/bin/env bash
# =============================================================================
# utils/setup.sh
# Create / reuse project-root .venv and install runtime + dev dependencies.
# Supports corporate environments by adding public PyPI as extra index.
#
# Distro support:
#   Debian/Ubuntu/Mint  apt-get   python<X.Y>-venv
#   Fedora/RHEL/CentOS  dnf/yum   (venv included; python3-devel if missing)
#   openSUSE            zypper    python3-venv / python3-devel
#   Arch/CachyOS        pacman    (included in the python package)
#   Alpine              apk       py3-venv / py3-pip
#   Void                xbps      (usually included)
#   NixOS/Gentoo/macOS/WSL — venv is part of the interpreter; no pkg needed
# =============================================================================

set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.."
REPO_ROOT="$(pwd)"
VENV_DIR="${REPO_ROOT}/.venv"

PYTHON_EXEC="${PYTHON_EXEC:-python3}"
FORCE_RECREATE=0
NO_SUDO=0

# -----------------------------------------------------------------------------
# Platform detection (Linux distros, Git Bash / MSYS2, macOS)
# -----------------------------------------------------------------------------
PLATFORM="linux"
case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*) PLATFORM="windows-msys" ;;
  Darwin)               PLATFORM="macos" ;;
esac

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
  -n, --no-sudo       Never invoke package managers; report missing pieces only
  -h, --help          Show this help

Supported distros: Debian/Ubuntu, Fedora/RHEL, openSUSE, Arch, Alpine, Void,
plus any system where the interpreter already ships venv + ensurepip.
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
    -n|--no-sudo)
      NO_SUDO=1
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
NO_SUDO="${NO_SUDO:-0}"

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
# Privilege helper — works with sudo, doas, or root; never required when the
# interpreter already has venv+ensurepip (macOS, most rolling releases, pyenv).
# =============================================================================

PKGMGR=""          # set by detect_pkgmgr
SUDO_CMD=""

detect_privilege_cmd() {
  if [[ "$(id -u)" -eq 0 ]]; then
    SUDO_CMD=""
  elif command -v sudo >/dev/null 2>&1; then
    if sudo -n true >/dev/null 2>&1; then
      SUDO_CMD="sudo -n"
    else
      SUDO_CMD="sudo"
    fi
  elif command -v doas >/dev/null 2>&1; then
    SUDO_CMD="doas"
  else
    SUDO_CMD=""
  fi
}

# detect_pkgmgr <var-out> — prints the system package manager, or nothing
detect_pkgmgr() {
  if command -v apt-get >/dev/null 2>&1; then echo "apt"
  elif command -v dnf >/dev/null 2>&1; then echo "dnf"
  elif command -v yum >/dev/null 2>&1; then echo "yum"
  elif command -v zypper >/dev/null 2>&1; then echo "zypper"
  elif command -v pacman >/dev/null 2>&1; then echo "pacman"
  elif command -v apk >/dev/null 2>&1; then echo "apk"
  elif command -v xbps-install >/dev/null 2>&1; then echo "xbps"
  fi
}

pkg_install() {
  # pkg_install <package...> — returns 0 on success. Refresh lists once on
  # failure for distros that cache an index (apt/dnf/zypper).
  local mgr="$1"; shift
  local -a cmd
  case "$mgr" in
    apt)    cmd=(apt-get install -y);;
    dnf)    cmd=(dnf install -y);;
    yum)    cmd=(yum install -y);;
    zypper) cmd=(zypper --non-interactive install);;
    pacman) cmd=(pacman -S --needed --noconfirm);;
    apk)    cmd=(apk add);;
    xbps)   cmd=(xbps-install -Sy);;
    *) return 1;;
  esac

  if $SUDO_CMD "${cmd[@]}" "$@"; then
    return 0
  fi
  case "$mgr" in
    apt)
      echo "Retrying after 'apt-get update'..."
      $SUDO_CMD apt-get update && $SUDO_CMD apt-get install -y "$@" && return 0 ;;
    dnf|yum)
      echo "Retrying after 'makecache'..."
      $SUDO_CMD "${mgr}" makecache && $SUDO_CMD "${cmd[@]}" "$@" && return 0 ;;
    zypper)
      echo "Retrying after 'zypper refresh'..."
      $SUDO_CMD zypper --non-interactive refresh && $SUDO_CMD "${cmd[@]}" "$@" && return 0 ;;
    pacman)
      echo "Retrying after '-Sy' refresh..."
      $SUDO_CMD pacman -Sy --needed --noconfirm "$@" && return 0 ;;
    apk)
      echo "Retrying after 'apk update'..."
      $SUDO_CMD apk update && $SUDO_CMD apk add "$@" && return 0 ;;
  esac
  return 1
}

# -----------------------------------------------------------------------------
# Map (distro, python X.Y) → the package that provides venv + ensurepip
# -----------------------------------------------------------------------------
venv_package_for() {
  local mgr="$1" pymajor="$2" pyminor="$3" pyver="${2}.${3}"
  case "$mgr" in
    apt)    echo "python${pyver}-venv";;                 # falls back to python3-venv via try-list
    dnf|yum)
      # Fedora/RHEL: venv is in python3 itself; ensurepip too (>= F28).
      # Only very old EL needs devel; offer it as last resort.
      echo "python3"
      ;;
    zypper) echo "python3-venv";;
    pacman) echo "python";;                              # single `python` pkg includes venv
    apk)    echo "py3-venv";;
    xbps)   echo "python3-venv" ;;                       # best-effort name; often preinstalled
    *) return 1;;
  esac
}

# =============================================================================
# Ensure venv + ensurepip support for THIS interpreter, using the native
# package manager of whatever platform we're on.
# =============================================================================

if [[ "$PLATFORM" == "windows-msys" ]]; then
  # Git Bash / MSYS2: official Python for Windows ships complete venv +
  # ensurepip; there is no system package manager (and no sudo). Skip all
  # package logic — if venv is still missing, the interpreter itself is a
  # stripped install (e.g. Windows Store stub) and only a real Python fixes it.
  if ! "$PYTHON_EXEC" -c "import venv, ensurepip" >/dev/null 2>&1; then
    echo "Error: '${PYTHON_EXEC}' lacks venv/ensurepip and this is Git Bash/Windows," >&2
    echo "where no package manager applies." >&2
    echo "" >&2
    echo "Fixes:" >&2
    echo "  1. Install the full Python from https://www.python.org/downloads/" >&2
    echo "     (check 'Install pip' / 'py launcher' options during setup)." >&2
    echo "  2. If 'python3' resolves to the Windows Store alias, disable it:" >&2
    echo "     Settings > Apps > Advanced app settings > App execution aliases" >&2
    echo "     then re-run with: ./utils/setup.sh --python py" >&2
    exit 1
  fi

elif [[ "$PLATFORM" == "macos" ]]; then
  # macOS: framework CPython from python.org/Homebrew includes venv+ensurepip.
  if ! "$PYTHON_EXEC" -c "import venv, ensurepip" >/dev/null 2>&1; then
    echo "Error: '${PYTHON_EXEC}' lacks venv/ensurepip on macOS." >&2
    echo "Install full Python via https://www.python.org/downloads/ or:" >&2
    echo "  brew install python" >&2
    exit 1
  fi

else
  # Linux: use the native package manager when pieces are missing.

  VENV_OK=1
  "$PYTHON_EXEC" -c "import venv" >/dev/null 2>&1 || VENV_OK=0
  "$PYTHON_EXEC" -c "import ensurepip" >/dev/null 2>&1 || VENV_OK=0

  if [[ "$VENV_OK" -ne 1 ]]; then
    PKGMGR="$(detect_pkgmgr)"

    if [[ -z "$PKGMGR" ]]; then
      echo "Error: this Python lacks venv/ensurepip and no supported package manager was found." >&2
      echo "Install venv support manually, e.g.:" >&2
      echo "  Debian/Ubuntu: sudo apt install python3-venv" >&2
      echo "  Fedora/RHEL:   sudo dnf install python3" >&2
      echo "  openSUSE:      sudo zypper install python3-venv" >&2
      echo "  Arch:          sudo pacman -S python" >&2
      echo "  Alpine:        sudo apk add py3-venv py3-pip" >&2
      echo "Or build/install a full Python (pyenv, official installer)." >&2
      exit 1
    fi

    if [[ "$NO_SUDO" -eq 1 ]]; then
      echo "Error: Python '${PYTHON_EXEC}' lacks venv/ensurepip and --no-sudo was given." >&2
      echo "Install your distro's venv package manually, then re-run." >&2
      exit 1
    fi

    detect_privilege_cmd
    if [[ -z "$SUDO_CMD" && "$(id -u)" -ne 0 ]]; then
      echo "Error: need root (sudo/doas) to install packages, but neither sudo nor doas is available." >&2
      exit 1
    fi

    PY_MAJOR="$("$PYTHON_EXEC" -c 'import sys; print(sys.version_info.major)')"
    PY_MINOR="$("$PYTHON_EXEC" -c 'import sys; print(sys.version_info.minor)')"

    echo "Python '${PYTHON_EXEC}' lacks venv/ensurepip support."
    echo "Detected package manager: ${PKGMGR}. Installing venv support (may prompt for your password)..."

    INSTALLED=0
    case "$PKGMGR" in
      apt)
        # Try exact version first, then generic python3-venv.
        for PKG in "python${PY_MAJOR}.${PY_MINOR}-venv" "python3-venv"; do
          echo "Attempting: ${PKG}"
          if pkg_install apt "$PKG"; then INSTALLED=1; break; fi
        done
        ;;
    dnf|yum)
      # Modern Fedora/RHEL ship venv inside python3 itself; reinstall to fix a
      # stripped-down install, then fall back to devel headers for old EL.
      for PKG in "python3" "python3-devel" "python${PY_MAJOR}.${PY_MINOR}-devel"; do
        echo "Attempting: ${PKG}"
        if pkg_install "$PKGMGR" "$PKG"; then INSTALLED=1; break; fi
      done
      ;;
    zypper)
      for PKG in "python3-venv" "python3"; do
        echo "Attempting: ${PKG}"
        if pkg_install zypper "$PKG"; then INSTALLED=1; break; fi
      done
      ;;
    pacman)
      echo "Attempting: python"
      if pkg_install pacman "python"; then INSTALLED=1; fi
      ;;
    apk)
      for PKG in "py3-venv" "py3-pip"; do
        echo "Attempting: ${PKG}"
        if pkg_install apk "$PKG"; then INSTALLED=1; break; fi
      done
      ;;
    xbps)
      echo "Attempting: python3"
      if pkg_install xbps "python3"; then INSTALLED=1; fi
      ;;
    esac

    if [[ "$INSTALLED" -eq 1 ]] \
       && "$PYTHON_EXEC" -c "import venv" >/dev/null 2>&1 \
       && "$PYTHON_EXEC" -c "import ensurepip" >/dev/null 2>&1; then
      echo "venv/ensurepip support installed."
      VENV_OK=1
    else
      echo "" >&2
      echo "Error: could not make venv available automatically." >&2
      echo "Run manually (distro-specific):" >&2
      case "$PKGMGR" in
        apt)    echo "  sudo apt update && sudo apt install python3-venv" >&2;;
        dnf|yum) echo "  sudo ${PKGMGR} install python3 python3-devel" >&2;;
        zypper) echo "  sudo zypper install python3-venv" >&2;;
        pacman) echo "  sudo pacman -S python" >&2;;
        apk)    echo "  sudo apk add py3-venv py3-pip" >&2;;
        xbps)   echo "  sudo xbps-install -Sy python3" >&2;;
      esac
      echo "Then re-run: ./utils/setup.sh --force" >&2
      exit 1
    fi
  fi
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

# Resolve venv Python binary (Windows venvs use Scripts/, POSIX use bin/)
# NOTE: on Git Bash/MSYS, a Windows-layout venv has BOTH Scripts/python.exe
# and a bin/ dir created by MSYS shims — prefer Scripts/python.exe there.
if [[ "$PLATFORM" == "windows-msys" && -x "${VENV_DIR}/Scripts/python.exe" ]]; then
  VENV_PYTHON="${VENV_DIR}/Scripts/python.exe"
elif [[ -x "${VENV_DIR}/bin/python" ]]; then
  VENV_PYTHON="${VENV_DIR}/bin/python"
elif [[ -x "${VENV_DIR}/Scripts/python.exe" ]]; then
  VENV_PYTHON="${VENV_DIR}/Scripts/python.exe"
else
  echo "Error: could not locate python inside ${VENV_DIR}" >&2
  echo "The venv creation may have failed partway — try: ./utils/setup.sh --force" >&2
  exit 1
fi

# MSYS path conversion mangles URLs passed to native Windows python/pip
# (https://pypi.org/simple → //pypi.org/...). Disable it for child processes.
if [[ "$PLATFORM" == "windows-msys" ]]; then
  export MSYS_NO_PATHCONV=1
  export MSYS2_ARG_CONV_EXCL="*"
fi

echo "Using venv Python: ${VENV_PYTHON}"

"${VENV_PYTHON}" -c '
import sys
ver = sys.version.split()[0]
print(f"  Python {ver} at {sys.executable}")
'

# ---------------------------------------------------------------------------
# Ensure the venv actually has pip (venvs created without ensurepip lack it)
# ---------------------------------------------------------------------------
if ! "${VENV_PYTHON}" -m pip --version >/dev/null 2>&1; then
  echo "venv has no pip — attempting to bootstrap via ensurepip..."
  if "${VENV_PYTHON}" -m ensurepip --upgrade >/dev/null 2>&1 \
     && "${VENV_PYTHON}" -m pip --version >/dev/null 2>&1; then
    echo "pip bootstrapped successfully."
  else
    echo "Error: this virtual environment has no pip and ensurepip failed." >&2
    echo "" >&2
    echo "Most likely the host interpreter's venv/ensurepip support is incomplete" >&2
    echo "(Debian/Ubuntu keep it in python<X.Y>-venv; Alpine in py3-venv)." >&2
    echo "" >&2
    echo "Fix — remove the broken venv, install support, recreate:" >&2
    echo "  ./utils/setup.sh --force   # will attempt the right package automatically" >&2
    echo "or manually:" >&2
    echo "  rm -rf ${VENV_DIR} && <install distro venv package> && ./utils/setup.sh" >&2
    exit 1
  fi
fi

# ---------------------------------------------------------------------------
# Install dependencies
# ---------------------------------------------------------------------------
echo "Upgrading pip..."
pip_install --upgrade pip

echo "Installing runtime dependencies..."
pip_install -r "${REPO_ROOT}/requirements.txt"
echo "Installing development dependencies..."
pip_install -r "${REPO_ROOT}/requirements-dev.txt"

# =============================================================================
# Configuration files: config.json + api_key.json
# Built from example_config.json / example_api_key.json with prompts.
# Skipped in non-interactive shells (no TTY) — files are left as plain copies.
# =============================================================================

CONFIG_FILE="${REPO_ROOT}/config.json"
API_KEY_FILE="${REPO_ROOT}/api_key.json"

# Only prompt when stdin+stdout are a terminal and not explicitly disabled.
if [[ -t 0 && -t 1 && "${SETUP_SKIP_CONFIG:-0}" != "1" ]]; then
  DO_CONFIG=1
else
  DO_CONFIG=0
fi

# --- api_key.json ------------------------------------------------------------
if [[ ! -f "$API_KEY_FILE" ]]; then
  if [[ "$DO_CONFIG" -eq 1 ]]; then
    echo ""
    echo "=============================================================="
    echo "API keys"
    echo "--------------------------------------------------------------"
    echo "api_key.json holds your LLM provider secrets. It is gitignored."
    echo "Keys are organized per ENDPOINT (matching config.json:endpoints)."
    echo "Press Enter to keep the placeholder; paste a real key to set it."
    echo ""

    # Start structured skeleton from example (keeps any comments/extra fields)
    python3 - <<'PYEOF'
import json
data = {"_comment": "API keys per endpoint. See example_api_key.json.", "keys": {}}
json.dump(data, open("api_key.json", "w"), indent=2)
PYEOF

    # Enumerate endpoints from the freshly copied config.json
    mapfile -t ENDPOINTS < <(python3 -c "
import json
cfg = json.load(open('$CONFIG_FILE'))
for name in (cfg.get('endpoints') or {}):
    print(name)
")

    if [[ ${#ENDPOINTS[@]} -eq 0 ]]; then
      ENDPOINTS=("gemini")
    fi

    for EP in "${ENDPOINTS[@]}"; do
      read -r -p "API key for endpoint '${EP}' [placeholder]: " KEYVAL || KEYVAL=""
      if [[ -z "$KEYVAL" ]]; then KEYVAL="YOUR_${EP^^}_KEY"; fi
      python3 - "$API_KEY_FILE" "$EP" "$KEYVAL" <<'PYEOF'
import json, sys
path, ep, val = sys.argv[1], sys.argv[2], sys.argv[3]
data = json.load(open(path))
data.setdefault("keys", {})[ep] = {"api_key": val}
json.dump(data, open(path, "w"), indent=2)
PYEOF
      echo "  ✅ keys.${EP} set"
    done

    chmod 600 "$API_KEY_FILE" 2>/dev/null || true
    echo "✅ Created ${API_KEY_FILE}"
  else
    cp example_api_key.json "$API_KEY_FILE"
    echo "Created ${API_KEY_FILE} from template (non-interactive mode — add your keys manually)."
  fi
else
  echo "✅ ${API_KEY_FILE} already exists — keeping it."
fi

# --- config.json --------------------------------------------------------------
if [[ ! -f "$CONFIG_FILE" ]]; then
  cp example_config.json "$CONFIG_FILE"
  echo "✅ Created ${CONFIG_FILE} from template."

  if [[ "$DO_CONFIG" -eq 1 ]]; then
    echo ""
    echo "=============================================================="
    echo "config.json walkthrough"
    echo "--------------------------------------------------------------"
    echo "The full template is already valid. The questions below only"
    echo "customize the essentials; Enter accepts the default."
    echo ""

    ask() {
      # ask <prompt> <default> <outvar>
      local reply
      read -r -p "$1 [$2]: " reply || reply=""
      printf -v "$3" '%s' "${reply:-$2}"
    }

    # 1. Project directory (the tree agents will work on)
    DEF_PROJ="$(python3 -c "import json;print(json.load(open('$CONFIG_FILE'))['project_directory'])")"
    ask "Project directory for agent file operations" "$DEF_PROJ" PROJ_DIR
    python3 - "$CONFIG_FILE" "$PROJ_DIR" <<'PYEOF'
import json, sys
path, val = sys.argv[1], sys.argv[2]
cfg = json.load(open(path))
cfg["project_directory"] = val
json.dump(cfg, open(path, "w"), indent=2)
PYEOF

    # 2. Test mode (no real API spend)
    ask "Enable llm.test_mode now (no real API calls; recommended first run)? y/N" "N" TESTMODE
    if [[ "$TESTMODE" =~ ^[Yy] ]]; then
      python3 - "$CONFIG_FILE" <<'PYEOF'
import json, sys
path = sys.argv[1]
cfg = json.load(open(path))
cfg.setdefault("llm", {})["test_mode"] = True
json.dump(cfg, open(path, "w"), indent=2)
PYEOF
      echo "  test_mode=ON — safe to explore without spending tokens."
    fi

    # 3. CLI mode
    ask "CLI mode: interactive / semi_attended / unattended" "interactive" CLIMODE
    python3 - "$CONFIG_FILE" "$CLIMODE" <<'PYEOF'
import json, sys
path, val = sys.argv[1], sys.argv[2]
cfg = json.load(open(path))
cfg.setdefault("cli_mode", {})["mode"] = val
json.dump(cfg, open(path, "w"), indent=2)
PYEOF

    echo ""
    echo "Everything else (endpoints, models, budgets, background agents)"
    echo "is set to the documented defaults from example_config.json."
    echo "See CONFIGURATION.md for the complete schema."
  fi
else
  echo "✅ ${CONFIG_FILE} already exists — keeping it."
fi

# -----------------------------------------------------------------------------
# Activate the venv in this shell
# -----------------------------------------------------------------------------
# NOTE: a script cannot modify its parent shell's environment — sourcing this
# file (`. ./utils/setup.sh` or `source ./utils/setup.sh`) makes the
# activation persist after the script ends. When executed normally the
# activation applies only inside the script, so we also print the command.
if [[ -f "${VENV_DIR}/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "${VENV_DIR}/bin/activate"
elif [[ -f "${VENV_DIR}/Scripts/activate" ]]; then
  # shellcheck disable=SC1091
  source "${VENV_DIR}/Scripts/activate"
fi

if [[ -n "${VIRTUAL_ENV:-}" ]]; then
  echo ""
  echo "✅ Virtual environment activated: ${VIRTUAL_ENV}"
fi

echo ""
echo "=============================================================="
echo "Setup complete."
echo "  venv:   ${VENV_DIR}"
echo "  python: ${VENV_PYTHON}"
echo ""
if [[ -n "${VIRTUAL_ENV:-}" && "${BASH_SOURCE[0]}" != "$0" ]]; then
  echo "The venv is ACTIVE in your current shell (script was sourced)."
else
  echo "Activate with:"
  if [[ "$PLATFORM" == "windows-msys" && -f "${VENV_DIR}/Scripts/activate" ]]; then
    echo "  source ${VENV_DIR}/Scripts/activate     # Git Bash"
  elif [[ -f "${VENV_DIR}/bin/activate" ]]; then
    echo "  source ${VENV_DIR}/bin/activate"
  else
    echo "  ${VENV_DIR}\\Scripts\\activate"
  fi
  echo "(or run this script via 'source ./utils/setup.sh' to auto-activate)"
fi
echo ""
echo "Launch PrizmForge with:"
if [[ -n "${VIRTUAL_ENV:-}" && "${BASH_SOURCE[0]}" != "$0" ]]; then
  echo "  python main.py"
else
  echo "  source ${VENV_DIR}/bin/activate   # if not already active"
  echo "  python main.py"
fi
echo ""
echo "To install the project in editable mode later, run:"
echo "  pip install -e ."
echo "=============================================================="

# Hint for sourced execution
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  :
else
  # Being sourced: skip the trailing exit so we don't close the user's shell.
  return 0 2>/dev/null || true
fi
