# =============================================================================
# tests/test_governed_editing.py
# Version: 2.6 - serial only (duration data showed all cases <0.03s)
# =============================================================================

import sys
from pathlib import Path

import pytest

# DB isolation required (own temp DB + process-local state). Duration report
# 2026-08-16 showed every case under 0.03s — not a duration gate.
pytestmark = [pytest.mark.serial]

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
