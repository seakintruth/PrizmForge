# =============================================================================
# PrizmForge/file_editing/db.py
# Version: 1.2 - Sprint 6 Complete
# Purpose: Database connection, error logging, and reconstruction helpers
# =============================================================================

import sqlite3
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, Dict, Any, List
import json
import hashlib
from datetime import datetime

def get_db_path() -> str:
    """Get database path, respecting PRIZMFORGE_DB_PATH env var (useful for testing)."""
    return os.environ.get(
        "PRIZMFORGE_DB_PATH",
        str(Path(__file__).parent.parent / "agents.db")
    )

@contextmanager
def get_db_connection():
    """Context manager for SQLite connection with proper commit/rollback."""
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def log_error(component: str, category: str, severity: str, message: str, 
              details: str = None, task_id: str = None, proposal_id: str = None,
              file_path: str = None, line_guid: str = None, stack_trace: str = None):
    """Centralized error logging to stdout + errors table."""
    print(f"[{severity}] {component}.{category}: {message}")
    try:
        with get_db_connection() as conn:
            conn.execute("""
                INSERT INTO errors 
                (component, error_category, severity, message, details, task_id, proposal_id, file_path, line_guid, stack_trace)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (component, category, severity, message, details, task_id, proposal_id, file_path, line_guid, stack_trace))
    except Exception as e:
        print(f"CRITICAL: Failed to log error to DB: {e}")

def initialize_database(db_path: str = None):
    """
    Deprecated. Schema initialization is now handled by core.db.init_db().
    This function is kept for backward compatibility only.
    """
    print("⚠️  file_editing.initialize_database() is deprecated. "
          "Call core.db.init_db() instead.")

def reconstruct_file_content(conn: sqlite3.Connection, file_id: int) -> str:
    """Rebuild file content from DB lines (sorted by sort_order)."""
    cursor = conn.execute("""
        SELECT content 
        FROM file_lines 
        WHERE file_id = ? AND is_deleted = 0
        ORDER BY sort_order
    """, (file_id,))
    lines = [row["content"] for row in cursor.fetchall()]
    return "\n".join(lines)

def capture_current_hashes(conn: sqlite3.Connection, file_id: int, line_guids: List[str]) -> Dict[str, str]:
    """Return {line_guid: content_hash} for the given guids."""
    if not line_guids:
        return {}
    placeholders = ",".join("?" * len(line_guids))
    rows = conn.execute(
        f"SELECT line_guid, content_hash FROM file_lines WHERE line_guid IN ({placeholders})",
        line_guids
    ).fetchall()
    return {row["line_guid"]: row["content_hash"] for row in rows}