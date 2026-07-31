#!/usr/bin/env bash
# Fast gate: mutation + cycle + events (inner loop / pre-commit)
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m pytest \
  tests/unit/test_edit_contracts.py \
  tests/integration/test_golden_path.py \
  tests/integration/test_run_task_cycle.py \
  tests/unit/test_events_undo.py \
  tests/unit/test_hardening.py \
  tests/unit/test_developer_edit_helpers.py \
  tests/unit/test_llm_mocks.py \
  -q --tb=line "$@"
