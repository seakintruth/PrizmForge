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
            cursor = conn.cursor()

            # agent_feedback: message + optional suggestion; order by timestamp then id
            cursor.execute(
                """
                SELECT id, message, suggestion
                FROM agent_feedback
                WHERE task_id = ?
                  AND file_path = ?
                  AND agent_name = 'reviewer'
                  AND addressed = 0
                ORDER BY COALESCE(timestamp, '') DESC, id DESC
                LIMIT 1
                """,
                (task_id, target_file),
            )

            fb_row = cursor.fetchone()
            if fb_row:
                msg = (fb_row[1] or "").strip()
                sug = (fb_row[2] or "").strip()
                reason = msg
                if sug:
                    reason = f"{msg}\nSuggestion: {sug}" if msg else sug
                return {"feedback_id": fb_row[0], "reason": reason or "Reviewer rejection (no detail)"}

            # Prefer rejected proposals for this task+file; fall back to file-only
            cursor.execute(
                """
                SELECT proposal_id, rationale
                FROM edit_proposals
                WHERE target_file_path = ?
                  AND status = 'rejected'
                  AND (task_id = ? OR task_id IS NULL)
                ORDER BY
                    CASE WHEN task_id = ? THEN 0 ELSE 1 END,
                    COALESCE(created_at, '') DESC
                LIMIT 1
                """,
                (target_file, task_id, task_id),
            )

            prop_row = cursor.fetchone()
            if prop_row:
                return {
                    "proposal_id": prop_row[0],
                    "reason": prop_row[1] or "Proposal rejected by Reviewer",
                }

    except Exception as e:
        print(f"   ⚠️ Could not fetch reviewer feedback: {e}")

    return None
