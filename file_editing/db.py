# =============================================================================
# PrizmForge/file_editing/db.py
# Version: 1.3 - Consolidated database path with core.db
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
    """
    Get database path using centralized core.db configuration.
    Falls back to legacy path if core.db is unavailable.
    """
    try:
        from core.db import get_db_path as core_get_db_path

        return core_get_db_path()
    except ImportError:
        # Fallback for standalone usage
        return os.environ.get(
            "PRIZMFORGE_DB_PATH",
            str(Path(__file__).parent.parent / ".PrizmForge" / "agents.db"),
        )


@contextmanager
def get_db_connection():
    """Context manager for SQLite connection with proper commit/rollback."""
    conn = sqlite3.connect(get_db_path(), timeout=60.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=OFF")
        conn.execute("PRAGMA synchronous=OFF")
    except Exception:
        pass
    try:
        yield conn
        try:
            conn.commit()
        except sqlite3.OperationalError as e:
            # Best-effort commit on flaky mounts
            print(f"[WARN] file_editing.db commit: {e}")
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        try:
            conn.close()
        except Exception:
            pass


def log_error(
    component: str,
    category: str,
    severity: str,
    message: str,
    details: str = None,
    task_id: str = None,
    proposal_id: str = None,
    file_path: str = None,
    line_guid: str = None,
    stack_trace: str = None,
):
    """Centralized error logging to stdout + errors table."""
    print(f"[{severity}] {component}.{category}: {message}")
    try:
        with get_db_connection() as conn:
            # Updated to match core/db.py errors table schema
            conn.execute(
                """
                INSERT INTO errors 
                (level, message, context, file_path, function_name, task_id, stack_trace)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    severity,  # level
                    message,  # message
                    json.dumps(
                        {
                            "component": component,
                            "category": category,
                            "details": details,
                            "proposal_id": proposal_id,
                            "line_guid": line_guid,
                        }
                    ),  # context (JSON)
                    file_path,
                    f"{component}.{category}",  # function_name
                    task_id,
                    stack_trace,
                ),
            )
    except Exception as e:
        print(f"CRITICAL: Failed to log error to DB: {e}")


def initialize_database(db_path: str = None):
    """
    Deprecated. Schema initialization is now handled by core.db.init_db().
    This function is kept for backward compatibility only.
    """
    print(
        "⚠️  file_editing.initialize_database() is deprecated. "
        "Call core.db.init_db() instead."
    )


def reconstruct_file_content(conn: sqlite3.Connection, file_id: int) -> str:
    """Rebuild file content from DB lines (sorted by sort_order)."""
    cursor = conn.execute(
        """
        SELECT content 
        FROM file_lines 
        WHERE file_id = ? AND is_deleted = 0
        ORDER BY sort_order
    """,
        (file_id,),
    )
    lines = []
    for row in cursor.fetchall():
        if isinstance(row, sqlite3.Row) or (
            hasattr(row, "keys") and not isinstance(row, tuple)
        ):
            lines.append(row["content"])
        else:
            lines.append(row[0])
    return "\n".join(lines)


def capture_current_hashes(
    conn: sqlite3.Connection, file_id: int, line_guids: List[str]
) -> Dict[str, str]:
    """Return {line_guid: content_hash} for the given guids."""
    if not line_guids:
        return {}
    placeholders = ",".join("?" * len(line_guids))
    rows = conn.execute(
        f"SELECT line_guid, content_hash FROM file_lines WHERE line_guid IN ({placeholders})",
        line_guids,
    ).fetchall()
    return {row["line_guid"]: row["content_hash"] for row in rows}
