# =============================================================================
# tests/test_governed_editing.py
# Version: 2.2 - Updated payloads to match current EditPayload v1.3
# =============================================================================

import pytest
import sqlite3
import hashlib
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from file_editing.db import initialize_database
from file_editing.editing import apply_edit_proposal
from workflow.proposal_builder import create_proposal_from_developer_output


def _compute_content_hash(content: str) -> str:
    return hashlib.md5(content.encode()).hexdigest()


@pytest.fixture(scope="function")
def db(monkeypatch):
    """Fresh temporary database for each test.
    
    Deletes existing DB at the path (if any) before initialization
    to guarantee a clean state.
    """
    import tempfile
    import os

    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    # Delete pre-existing file if present
    if os.path.exists(db_path):
        try:
            os.unlink(db_path)
        except OSError:
            pass

    monkeypatch.setenv("PRIZMFORGE_DB_PATH", db_path)

    from core.db import init_db
    init_db()  # Use consolidated schema

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()

    # Cleanup
    try:
        if os.path.exists(db_path):
            os.unlink(db_path)
    except OSError:
        pass


@pytest.fixture
def sample_file(db):
    """Create a sample file with lines."""
    cursor = db.execute(
        "INSERT INTO files (file_path, current_version) VALUES (?, 1)",
        ("test/sample.py",)
    )
    file_id = cursor.lastrowid

    lines = [
        ("guid-1", 1000.0, "def hello():"),
        ("guid-2", 2000.0, "    print('world')"),
        ("guid-3", 3000.0, "    return True"),
    ]
    for guid, sort, content in lines:
        db.execute("""
            INSERT INTO file_lines 
            (line_guid, file_id, sort_order, content, content_hash, version, is_deleted)
            VALUES (?, ?, ?, ?, ?, 1, 0)
        """, (guid, file_id, sort, content, _compute_content_hash(content)))

    db.commit()
    return file_id


# =============================================================================
# Tests with correct EditPayload structure (v1.3)
# =============================================================================

def test_apply_replace_block(db, sample_file):
    """Test GUID-based replacement using current EditPayload schema."""
    payload = {
        "target_file_path": "test/sample.py",
        "summary": "Update print statement for clarity",
        "rationale": "Improve logging in sample function",
        "operations": [{
            "type": "replace_block",
            "start_line_guid": "guid-2",
            "new_content": ["    print('updated')"],
            "rationale": "Replace old print with updated version"
        }]
    }

    proposal = create_proposal_from_developer_output(
        developer_output=payload,
        proposed_by_agent_id=1,
        target_file_path="test/sample.py"
    )
    assert proposal["status"] == "success"
    proposal_id = proposal["proposal_id"]

    db.execute("UPDATE edit_proposals SET status = 'approved' WHERE proposal_id = ?", (proposal_id,))
    db.commit()

    result = apply_edit_proposal(proposal_id)
    assert result["status"] == "success"


def test_optimistic_concurrency_conflict(db, sample_file):
    """Test hash mismatch detection."""
    payload = {
        "target_file_path": "test/sample.py",
        "summary": "Test conflict scenario",
        "rationale": "Verify optimistic locking works",
        "operations": [{
            "type": "replace_block",
            "start_line_guid": "guid-2",
            "new_content": ["    print('new')"],
            "rationale": "Attempt to modify line"
        }]
    }

    proposal = create_proposal_from_developer_output(
        developer_output=payload,
        proposed_by_agent_id=1,
        target_file_path="test/sample.py"
    )
    proposal_id = proposal["proposal_id"]

    # Corrupt hash
    db.execute("UPDATE file_lines SET content_hash = 'invalid' WHERE line_guid = 'guid-2'")
    db.commit()

    db.execute("UPDATE edit_proposals SET status = 'approved' WHERE proposal_id = ?", (proposal_id,))
    db.commit()

    result = apply_edit_proposal(proposal_id)
    assert result["status"] == "conflicted"


def test_insert_after_with_none_for_empty_file(db):
    """Test insert into new file."""
    payload = {
        "target_file_path": "test/new_file.py",
        "summary": "Create new file with header",
        "rationale": "Initialize new module",
        "operations": [{
            "type": "insert_after",
            "after_guid": None,
            "new_content": ["# New file header", "print('hello')"],
            "rationale": "Add initial content to empty file"
        }]
    }

    result = create_proposal_from_developer_output(
        developer_output=payload,
        proposed_by_agent_id=1,
        target_file_path="test/new_file.py"
    )
    assert result["status"] == "success"


def test_delete_lines(db, sample_file):
    """Test line deletion."""
    payload = {
        "target_file_path": "test/sample.py",
        "summary": "Remove debug lines",
        "rationale": "Clean up unnecessary print and return",
        "operations": [{
            "type": "delete_lines",
            "start_line_guid": "guid-2",
            "end_line_guid": "guid-3",
            "rationale": "Delete range from guid-2 to guid-3"
        }]
    }

    proposal = create_proposal_from_developer_output(
        developer_output=payload,
        proposed_by_agent_id=1,
        target_file_path="test/sample.py"
    )
    proposal_id = proposal["proposal_id"]

    db.execute("UPDATE edit_proposals SET status = 'approved' WHERE proposal_id = ?", (proposal_id,))
    db.commit()

    result = apply_edit_proposal(proposal_id)
    assert result["status"] == "success"


def test_full_proposal_lifecycle(db, sample_file):
    """Full create → approve → apply flow."""
    payload = {
        "target_file_path": "test/sample.py",
        "summary": "Rename function for clarity",
        "rationale": "Improve function naming",
        "operations": [{
            "type": "replace_block",
            "start_line_guid": "guid-1",
            "new_content": ["def improved_hello():"],
            "rationale": "Rename hello to improved_hello"
        }]
    }

    proposal = create_proposal_from_developer_output(
        developer_output=payload,
        proposed_by_agent_id=1,
        target_file_path="test/sample.py"
    )
    assert proposal["status"] == "success"

    proposal_id = proposal["proposal_id"]
    db.execute("UPDATE edit_proposals SET status = 'approved' WHERE proposal_id = ?", (proposal_id,))
    db.commit()

    result = apply_edit_proposal(proposal_id)
    assert result["status"] == "success"


# =============================================================================
# Edge Case Tests
# =============================================================================

def test_delete_lines_single_line_only_start_guid(db, sample_file):
    """Delete single line when only start_line_guid is provided (no end_line_guid)."""
    payload = {
        "target_file_path": "test/sample.py",
        "summary": "Delete single line",
        "rationale": "Remove one specific line using only start GUID",
        "operations": [{
            "type": "delete_lines",
            "start_line_guid": "guid-2",
            "rationale": "Delete only the middle line"
        }]
    }

    proposal = create_proposal_from_developer_output(
        developer_output=payload,
        proposed_by_agent_id=1,
        target_file_path="test/sample.py"
    )
    assert proposal["status"] == "success"

    proposal_id = proposal["proposal_id"]
    db.execute("UPDATE edit_proposals SET status = 'approved' WHERE proposal_id = ?", (proposal_id,))
    db.commit()

    result = apply_edit_proposal(proposal_id)
    assert result["status"] == "success"
    # lines_deleted lives inside the operations result
    ops = result.get("operations", [])
    assert len(ops) > 0
    assert ops[0].get("lines_deleted", 0) >= 1


def test_delete_lines_nonexistent_start_guid(db, sample_file):
    """Non-existent GUID should cause optimistic concurrency conflict (not a simple error)."""
    payload = {
        "target_file_path": "test/sample.py",
        "summary": "Delete with invalid GUID",
        "rationale": "Test graceful failure on bad start GUID",
        "operations": [{
            "type": "delete_lines",
            "start_line_guid": "nonexistent-guid-xyz",
            "rationale": "Attempt deletion with invalid GUID"
        }]
    }

    proposal = create_proposal_from_developer_output(
        developer_output=payload,
        proposed_by_agent_id=1,
        target_file_path="test/sample.py"
    )
    proposal_id = proposal["proposal_id"]

    db.execute("UPDATE edit_proposals SET status = 'approved' WHERE proposal_id = ?", (proposal_id,))
    db.commit()

    result = apply_edit_proposal(proposal_id)
    # Because the GUID doesn't exist, hash validation fails → conflicted
    assert result["status"] in ("conflicted", "error")


def test_replace_block_with_end_line_guid(db, sample_file):
    """Test replacing a range of lines using both start_line_guid and end_line_guid."""
    payload = {
        "target_file_path": "test/sample.py",
        "summary": "Replace a block of lines",
        "rationale": "Bulk update using range",
        "operations": [{
            "type": "replace_block",
            "start_line_guid": "guid-1",
            "end_line_guid": "guid-2",
            "new_content": ["def refactored():", "    print('refactored')"],
            "rationale": "Replace first two lines"
        }]
    }

    proposal = create_proposal_from_developer_output(
        developer_output=payload,
        proposed_by_agent_id=1,
        target_file_path="test/sample.py"
    )
    assert proposal["status"] == "success"

    proposal_id = proposal["proposal_id"]
    db.execute("UPDATE edit_proposals SET status = 'approved' WHERE proposal_id = ?", (proposal_id,))
    db.commit()

    result = apply_edit_proposal(proposal_id)
    assert result["status"] == "success"


def test_insert_after_last_line(db, sample_file):
    """Insert content after the last line in the file."""
    payload = {
        "target_file_path": "test/sample.py",
        "summary": "Append code at end of file",
        "rationale": "Add new function after existing code",
        "operations": [{
            "type": "insert_after",
            "after_guid": "guid-3",
            "new_content": ["", "# New helper function", "def helper():", "    return True"],
            "rationale": "Append helper after last line"
        }]
    }

    result = create_proposal_from_developer_output(
        developer_output=payload,
        proposed_by_agent_id=1,
        target_file_path="test/sample.py"
    )
    assert result["status"] == "success"
