"""
Integration tests for file editing pipeline.
NO EXTERNAL DEPENDENCIES - uses only pytest + stdlib.
"""

import pytest
import json
from pathlib import Path

from core.db_connection import get_db_connection
from file_editing import initialize_file_lines
from workflow.proposal_builder import create_proposal_from_developer_output
from file_editing.editing import apply_edit_proposal
from file_editing.writer import materialize_proposal
from core.config import get_config


class TestFileEditingPipeline:
    """End-to-end tests for governed file editing"""

    def test_01_initialize_simple_file(self, temp_db):
        """Test basic file initialization with GUIDs"""
        content = "def hello():\n    pass"
        result = initialize_file_lines("test_simple.py", content)
        
        assert result["status"] == "success"
        assert result["file_id"] > 0
        assert result["line_count"] == 2

    def test_02_initialize_multiline_file(self, temp_db):
        """Test file with multiple functions"""
        content = """def hello():
    print('world')
    return True

def goodbye():
    print('farewell')"""
        
        result = initialize_file_lines("test_multi.py", content)
        assert result["status"] == "success"
        assert result["line_count"] == 6

    def test_03_single_line_replacement(self, temp_db):
        """Test replacing a single line"""
        content = "line1\nline2\nline3"
        init_result = initialize_file_lines("test_single.py", content)
        file_id = init_result["file_id"]
        
        # Get GUIDs
        with get_db_connection() as conn:
            cursor = conn.execute("""
                SELECT line_guid FROM file_lines 
                WHERE file_id = ? AND is_deleted = 0 
                ORDER BY sort_order
            """, (file_id,))
            guids = [row[0] for row in cursor.fetchall()]
        
        assert len(guids) == 3
        
        # Replace middle line
        payload = {
            "target_file_path": "test_single.py",
            "summary": "Replace line 2",
            "rationale": "Testing single line replacement",
            "operations": [{
                "type": "replace_block",
                "start_line_guid": guids[1],
                "new_content": ["REPLACED LINE 2"],
                "rationale": "Replace single line"
            }]
        }
        
        proposal_result = create_proposal_from_developer_output(
            developer_output=payload,
            proposed_by_agent_id=1,
            target_file_path="test_single.py"
        )
        
        assert proposal_result["status"] == "success"

    def test_04_range_replacement(self, temp_db):
        """Test replacing multiple consecutive lines"""
        content = "line1\nline2\nline3\nline4\nline5"
        init_result = initialize_file_lines("test_range.py", content)
        file_id = init_result["file_id"]
        
        with get_db_connection() as conn:
            cursor = conn.execute("""
                SELECT line_guid FROM file_lines 
                WHERE file_id = ? ORDER BY sort_order
            """, (file_id,))
            guids = [row[0] for row in cursor.fetchall()]
        
        # Replace lines 2-4 (indices 1-3)
        payload = {
            "target_file_path": "test_range.py",
            "summary": "Replace middle lines",
            "rationale": "Testing range replacement",
            "operations": [{
                "type": "replace_block",
                "start_line_guid": guids[1],
                "end_line_guid": guids[3],
                "new_content": ["REPLACED 2", "REPLACED 3", "REPLACED 4"],
                "rationale": "Replace lines 2-4"
            }]
        }
        
        proposal_result = create_proposal_from_developer_output(
            developer_output=payload,
            proposed_by_agent_id=1,
            target_file_path="test_range.py"
        )
        
        assert proposal_result["status"] == "success"
        proposal_id = proposal_result["proposal_id"]
        
        # Approve and apply
        with get_db_connection() as conn:
            conn.execute("UPDATE edit_proposals SET status = 'approved' WHERE proposal_id = ?", (proposal_id,))
        
        apply_result = apply_edit_proposal(proposal_id)
        assert apply_result["status"] == "success"

    def test_05_insert_operations(self, temp_db):
        """Test insert_after operations"""
        content = "line1\nline2"
        init_result = initialize_file_lines("test_insert.py", content)
        file_id = init_result["file_id"]
        
        with get_db_connection() as conn:
            cursor = conn.execute("""
                SELECT line_guid FROM file_lines 
                WHERE file_id = ? ORDER BY sort_order
            """, (file_id,))
            guids = [row[0] for row in cursor.fetchall()]
        
        payload = {
            "target_file_path": "test_insert.py",
            "summary": "Insert new line",
            "rationale": "Testing insert",
            "operations": [{
                "type": "insert_after",
                "after_guid": guids[0],
                "new_content": ["INSERTED LINE"],
                "rationale": "Insert after first line"
            }]
        }
        
        proposal_result = create_proposal_from_developer_output(
            developer_output=payload,
            proposed_by_agent_id=1,
            target_file_path="test_insert.py"
        )
        
        assert proposal_result["status"] == "success"

    def test_06_delete_operations(self, temp_db):
        """Test delete_lines operations"""
        content = "line1\nline2\nline3"
        init_result = initialize_file_lines("test_delete.py", content)
        file_id = init_result["file_id"]
        
        with get_db_connection() as conn:
            cursor = conn.execute("""
                SELECT line_guid FROM file_lines 
                WHERE file_id = ? ORDER BY sort_order
            """, (file_id,))
            guids = [row[0] for row in cursor.fetchall()]
        
        payload = {
            "target_file_path": "test_delete.py",
            "summary": "Delete middle line",
            "rationale": "Testing deletion",
            "operations": [{
                "type": "delete_lines",
                "start_line_guid": guids[1],
                "rationale": "Remove line 2"
            }]
        }
        
        proposal_result = create_proposal_from_developer_output(
            developer_output=payload,
            proposed_by_agent_id=1,
            target_file_path="test_delete.py"
        )
        
        assert proposal_result["status"] == "success"

    def test_07_missing_rationale_autofix(self, temp_db):
        """Test that missing rationales are auto-fixed"""
        content = "line1"
        init_result = initialize_file_lines("test_autofix.py", content)
        
        # Payload without operation rationale (but WITH top-level rationale)
        payload_str = json.dumps({
            "target_file_path": "test_autofix.py",
            "summary": "Test rationale autofix",
            "rationale": "Testing auto-fix of missing operation rationales",
            "operations": [{
                "type": "insert_after",
                "after_guid": None,
                "new_content": ["new line"]
            }]
        })
        
        proposal_result = create_proposal_from_developer_output(
            developer_output=payload_str,
            proposed_by_agent_id=1,
            target_file_path="test_autofix.py"
        )
        
        # Should succeed due to auto-fix
        assert proposal_result["status"] == "success"