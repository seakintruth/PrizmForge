#!/bin/bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Setup report directory
REPORT_DIR="../report"
mkdir -p "$REPORT_DIR"
RUFF_LOG="$REPORT_DIR/ruff-check-$(date +%Y%m%d_%H%M%S).log"

# Default configuration
PYTHON_EXEC="python3"
SKIP_TESTS=false
SHOW_SUMMARY=true
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
        --skip-tests)
            SKIP_TESTS=true
            shift
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
echo -e "${BLUE}🚀 PrizmForge Pre-Push Checks${NC}"
echo -e "${BLUE}Executable: ${PYTHON_EXEC}${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════${NC}\n"

# Format checks (auto-fix, non-blocking)
echo -e "${BLUE}📝 Formatting & Auto-fixing...${NC}\n"

"$PYTHON_EXEC" -m black . > /dev/null 2>&1 && echo -e "${GREEN}✅ black${NC}" || echo -e "${YELLOW}⚠️  black${NC}"
"$PYTHON_EXEC" -m isort . > /dev/null 2>&1 && echo -e "${GREEN}✅ isort${NC}" || echo -e "${YELLOW}⚠️  isort${NC}"
"$PYTHON_EXEC" -m ruff check . --unsafe-fixes --fix > /dev/null 2>&1 && echo -e "${GREEN}✅ ruff (fixes)${NC}" || echo -e "${YELLOW}⚠️  ruff (fixes)${NC}"
"$PYTHON_EXEC" -m ruff format . > /dev/null 2>&1 && echo -e "${GREEN}✅ ruff format${NC}" || echo -e "${YELLOW}⚠️  ruff format${NC}"

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

if ! run_check "flake8 (errors)" "$PYTHON_EXEC -m flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics"; then
    exit 1
fi

run_check "flake8 (warnings)" "$PYTHON_EXEC -m flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics"

# Type checking (non-blocking)
echo -e "\n${BLUE}🏷️  Type Checking (informational)...${NC}\n"

run_check "mypy" "$PYTHON_EXEC -m mypy . --ignore-missing-imports" true

# Tests (optional)
if [ "$SKIP_TESTS" = true ]; then
    echo -e "\n${YELLOW}⏭️  Skipping tests (--skip-tests)${NC}"
else
    echo -e "\n${BLUE}🧪 Running Tests...${NC}\n"
    
    if ! run_check "pytest" "$PYTHON_EXEC -m pytest"; then
        exit 1
    fi
fi

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
