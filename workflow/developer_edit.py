"""
Developer mutation pipeline extracted from task_runner.

Flow (after files are known):
  mode select → load files → generate/validate with fallback →
  normalize payload → create proposal → reviewer → materialize

Primary entry: run_developer_mutation(...)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from agents.base import call_agent
from core.db_connection import get_db_connection
from core.db_helpers import post_message
from core.edit_response_validator import validate_developer_edit_response
from core.events import publish_event
from core.file_operations import format_file_with_guids, get_file_content_from_db
from core.index_context import load_symbol_json_context
from core.json_parser import parse_json_response
from file_editing.undo import snapshot_before_apply
from file_editing.writer import materialize_proposal
from workflow.edit_mode_selector import DEFAULT_FALLBACK_ORDER, MODE_DIFF, MODE_FULL_REPLACE, MODE_GUID, next_fallback_mode, select_edit_mode
from workflow.proposal_builder import create_proposal_from_developer_output, update_proposal_status


# =========================================================================
# 🎯 PHASE 3: CLOSED-LOOP REVIEWER FEEDBACK EXTRACTION
# =========================================================================
def fetch_latest_reviewer_feedback(task_id: str, target_file: str) -> dict | None:
    """
    Fetches the most recent unaddressed Reviewer rejection reason and suggestions
    for a given task and target file.

    Schema (core/db.py agent_feedback):
      message, suggestion, timestamp — NOT feedback_text / created_at
    Schema (edit_proposals):
      proposal_id PK, task_id (when present)
    """
    try:
        with get_db_connection() as conn:
            row = conn.execute(
                """
                SELECT message, suggestion, timestamp
                FROM agent_feedback
                WHERE task_id = ? AND file_path = ? AND agent_name = 'reviewer'
                  AND addressed = 0
                ORDER BY timestamp DESC
                LIMIT 1
                """,
                (task_id, target_file),
            ).fetchone()
            if not row:
                return None
            return {
                "message": row[0],
                "suggestion": row[1],
                "timestamp": row[2],
            }
    except Exception as e:
        print(f"   ⚠️  fetch_latest_reviewer_feedback failed: {e}")
        return None
