# =============================================================================
# PrizmForge/file_editing/db.py
# Version: 1.5 - Non-blocking error logging under DB contention
# Purpose: Database connection, error logging, and reconstruction helpers
# =============================================================================

from __future__ import annotations

import json
import sqlite3
from typing import Any

from core.db import get_db_path

# Short timeouts so log_error never blocks proposal create/apply under lock contention.
_LOG_ERROR_CONNECT_TIMEOUT_S = 0.25
_LOG_ERROR_BUSY_TIMEOUT_MS = 250


def log_error(
    severity: str,
    component: str,
    category: str,
    message: str,
    *,
    details: dict[str, Any] | None = None,
    file_path: str | None = None,
    task_id: str | None = None,
    proposal_id: str | None = None,
    line_guid: str | None = None,
    stack_trace: str | None = None,
) -> None:
    """
    Best-effort error logging that never blocks the caller.

    Always prints to stdout first (the reliable channel). The INSERT is
    best-effort and may be skipped under contention so hot paths
    (proposal create/apply) cannot stall.
    """
    print(f"[{severity}] {component}.{category}: {message}")

    conn: sqlite3.Connection | None = None
    try:
        conn = sqlite3.connect(
            get_db_path(),
            timeout=_LOG_ERROR_CONNECT_TIMEOUT_S,
            isolation_level=None,  # autocommit — no long-held write transaction
        )
        try:
            conn.execute(f"PRAGMA busy_timeout={_LOG_ERROR_BUSY_TIMEOUT_MS}")
        except Exception:  # noqa: S110
            pass

        conn.execute(
            """
            INSERT INTO errors
            (level, message, context, file_path, function_name, task_id, stack_trace)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                severity,
                message,
                json.dumps(
                    {
                        "component": component,
                        "category": category,
                        "details": details,
                        "proposal_id": proposal_id,
                        "line_guid": line_guid,
                    }
                ),
                file_path,
                f"{component}.{category}",
                task_id,
                stack_trace,
            ),
        )
    except sqlite3.OperationalError as e:
        # Locked / busy / IO — drop DB write, never block caller
        print(f"[WARN] log_error DB skip (non-blocking): {e}")
    except Exception as e:
        print(f"CRITICAL: Failed to log error to DB: {e}")
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:  # noqa: S110
                pass


def initialize_database(db_path: str | None = None):
    """
    Deprecated. Schema initialization is now handled by core.db.init_db().
    This function is kept for backward compatibility only.
    """
    print("⚠️  file_editing.initialize_database() is deprecated. Call core.db.init_db() instead.")
