#!/bin/bash

set -e

# Automatically navigate to the Git root directory
GIT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$GIT_ROOT"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Setup report directory inside project root
REPORT_DIR=".PrizmForge/reports"
mkdir -p "$REPORT_DIR"
RUFF_LOG="$REPORT_DIR/ruff-check-$(date +%Y%m%d_%H%M%S).log"

# Default configuration (overridable via ENV vars or CLI arguments)
PYTHON_EXEC="${PYTHON_EXEC:-python3}"
SHOW_SUMMARY="${SHOW_SUMMARY:-true}"
STAGE_FIXED_FILES="${STAGE_FIXED_FILES:-true}" # Auto-stage fixes during git commit
FAILED_CHECKS=()
PASSED_CHECKS=()

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -p|--python)
            if [[ -n "${2:-}" && ! "$2" =~ ^- ]]; then
                PYTHON_EXEC="$2"
                shift 2
            else
                echo -e "${RED}Error: Option $1 requires a non-empty Python path.${NC}"
                exit 1
            fi
            ;;
        --no-summary)
            SHOW_SUMMARY=false
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [-p|--python PATH] [--skip-tests] [--no-summary]"
            exit 1
            ;;
    esac
done

# =========================================================================
# 🛠️ AUTO-INSTALL / RE-SYNC PRE-COMMIT HOOK
# =========================================================================
HOOK_FILE=".git/hooks/pre-commit"

install_or_update_hook() {
    if [ -d ".git/hooks" ]; then
        echo -e "${BLUE}⚙️  Syncing .git/hooks/pre-commit with PYTHON_EXEC=${PYTHON_EXEC}...${NC}"
        cat << EOF > "$HOOK_FILE"
#!/bin/bash
# Auto-generated pre-commit hook by utils/pre_push.sh

# Resolve Python Executable in priority order
if [ -n "\$PYTHON_EXEC" ]; then
    PY_BIN="\$PYTHON_EXEC"
elif [ -n "\$VIRTUAL_ENV" ]; then
    PY_BIN="\$VIRTUAL_ENV/Scripts/python.exe"
    [ ! -f "\$PY_BIN" ] && PY_BIN="\$VIRTUAL_ENV/bin/python"
else
    PY_BIN="${PYTHON_EXEC}"
fi

export PYTHON_EXEC="\$PY_BIN"

# Execute repository pre-push script
./utils/pre_push.sh
EOF
        chmod +x "$HOOK_FILE"
        echo -e "${GREEN}✅ Pre-commit hook synced at $HOOK_FILE${NC}\n"
    fi
}

# Re-sync hook whenever pre_push.sh is run
install_or_update_hook

run_check() {
    local check_name=$1
    local command=$2
    local allow_failure=${3:-false}
    
    echo -e "${BLUE}🔄 Running: ${check_name}...${NC}"
    
    if eval "$command" > /dev/null 2>&1; then
        PASSED_CHECKS+=("$check_name")
        echo -e "${GREEN}✅ ${check_name}${NC}"
        return 0
    else
        if [ "$allow_failure" = true ]; then
            PASSED_CHECKS+=("$check_name (warnings only)")
            echo -e "${YELLOW}⚠️  ${check_name} (warnings only)${NC}"
            return 0
        else
            FAILED_CHECKS+=("$check_name")
            echo -e "${RED}❌ ${check_name}${NC}"
            return 1
        fi
    fi
}

# Run checks
echo -e "\n${BLUE}═══════════════════════════════════════════════════${NC}"
echo -e "${BLUE}🚀 PrizmForge Pre-Commit / Pre-Push Checks${NC}"
echo -e "${BLUE}Executable: ${PYTHON_EXEC}${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════${NC}\n"

# Format checks (auto-fix, non-blocking)
echo -e "${BLUE}📝 Formatting & Auto-fixing...${NC}\n"

"$PYTHON_EXEC" -m black . > /dev/null 2>&1 && echo -e "${GREEN}✅ black${NC}" || echo -e "${YELLOW}⚠️  black${NC}"
"$PYTHON_EXEC" -m isort . > /dev/null 2>&1 && echo -e "${GREEN}✅ isort${NC}" || echo -e "${YELLOW}⚠️  isort${NC}"
"$PYTHON_EXEC" -m ruff check . --unsafe-fixes --fix > /dev/null 2>&1 && echo -e "${GREEN}✅ ruff (fixes)${NC}" || echo -e "${YELLOW}⚠️  ruff (fixes)${NC}"
"$PYTHON_EXEC" -m ruff format . > /dev/null 2>&1 && echo -e "${GREEN}✅ ruff format${NC}" || echo -e "${YELLOW}⚠️  ruff format${NC}"

# If running during git commit, auto-stage formatted files
if [ "$STAGE_FIXED_FILES" = true ] && [ -d ".git" ]; then
    git update-index --again > /dev/null 2>&1 || true
fi

# Linting checks (blocking)
echo -e "\n${BLUE}🔍 Linting Checks (blocking)...${NC}\n"

# Ruff check with logging on failure
echo -e "${BLUE}🔄 Running: ruff check...${NC}"
if "$PYTHON_EXEC" -m ruff check . > "$RUFF_LOG" 2>&1; then
    PASSED_CHECKS+=("ruff check")
    echo -e "${GREEN}✅ ruff check${NC}"
else
    FAILED_CHECKS+=("ruff check")
    echo -e "${RED}❌ ruff check${NC}"
    echo -e "${YELLOW}📋 Full report: $RUFF_LOG${NC}"
    echo -e "${YELLOW}Preview:${NC}"
    head -50 "$RUFF_LOG"
    exit 1
fi


# Flake8 errors (blocking) — excludes virtual environments & build artifacts
FLAKE8_EXCLUDES="--exclude=.venv,venv,build,dist,.git,.github,.PrizmForge,.pytest_cache,.ruff_cache,.vscode,ExampleProject,report"
FLAKE8_LOG="$REPORT_DIR/flake8-errors.log"

echo -e "${BLUE}🔄 Running: flake8 (errors)...${NC}"

if ! "$PYTHON_EXEC" -m flake8 . --count $FLAKE8_EXCLUDES --select=E9,F63,F7,F82 --show-source --statistics 2>&1 | tee "$FLAKE8_LOG"; then
    FAILED_CHECKS+=("flake8 (errors)")
    echo -e "${RED}❌ flake8 (errors)${NC}"
    echo -e "${YELLOW}📋 Full error report saved to: $FLAKE8_LOG${NC}"
    exit 1
else
    PASSED_CHECKS+=("flake8 (errors)")
    echo -e "${GREEN}✅ flake8 (errors)${NC}"
fi

# Flake8 warnings (informational)
run_check "flake8 (warnings)" "$PYTHON_EXEC -m flake8 . --count $FLAKE8_EXCLUDES --exit-zero --max-complexity=15 --max-line-length=127 --statistics"

# Type checking (non-blocking)
echo -e "\n${BLUE}🏷️  Type Checking (informational)...${NC}\n"

run_check "mypy" "$PYTHON_EXEC -m mypy . --ignore-missing-imports" true

# Summary
if [ "$SHOW_SUMMARY" = true ]; then
    echo -e "\n${BLUE}═══════════════════════════════════════════════════${NC}"
    
    if [ ${#FAILED_CHECKS[@]} -eq 0 ]; then
        echo -e "${GREEN}✅ All checks passed!${NC}"
        echo -e "\nPassed checks (${#PASSED_CHECKS[@]}):"
        for check in "${PASSED_CHECKS[@]}"; do
            echo -e "  ${GREEN}✓${NC} $check"
        done
    else
        echo -e "${RED}❌ Some checks failed!${NC}"
        echo -e "\nFailed checks (${#FAILED_CHECKS[@]}):"
        for check in "${FAILED_CHECKS[@]}"; do
            echo -e "  ${RED}✗${NC} $check"
        done
        echo -e "\n${YELLOW}📋 Report logs in: $REPORT_DIR/${NC}"
        exit 1
    fi
    
    echo -e "${BLUE}═══════════════════════════════════════════════════${NC}\n"
fi
