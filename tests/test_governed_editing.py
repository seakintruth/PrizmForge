# =============================================================================
# tests/test_governed_editing.py
# Version: 2.4 - Mark module slow (proposal→apply lifecycle)
# =============================================================================

import hashlib
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest

from core.db import init_db
from file_editing.editing import apply_edit_proposal
from workflow.proposal_builder import create_proposal_from_developer_output

# Full proposal→apply lifecycle is DB-heavy; exclude from --normal
pytestmark = pytest.mark.slow

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _compute_content_hash(content: str) -> str:
    return hashlib.md5(content.encode(), usedforsecurity=False).hexdigest()


@pytest.fixture(scope="function")
def db(monkeypatch):
    """Fresh temporary database for each test.

    Deletes existing DB at the path (if any) before initialization
    to guarantee a clean state.
    """

    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
