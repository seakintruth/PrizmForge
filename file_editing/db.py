# =============================================================================
# PrizmForge/file_editing/db.py
# Version: 1.6 - reconstruct_file_content matches core.db file_lines schema
# Purpose: Database connection, error logging, and reconstruction helpers
# =============================================================================

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

# log_error must not wait on locks — proposal/apply paths call it on the hot path.
_LOG_ERROR_CONNECT_TIMEOUT_S = 0.5
_LOG_ERROR_BUSY_TIMEOUT_MS = 500


def get_db_path() -> str:
    """
    Get database path using centralized core.db configuration.
    Falls back to .PrizmForge/prizmforge.db relative to CWD.
    """
    try:
        from core.db import get_db_path as _core_get_db_path

        return _core_get_db_path()
    except Exception:
        return str(Path(".PrizmForge") / "prizmforge.db")


@contextmanager
def get_db_connection():
    """Context manager for a SQLite connection with row_factory."""
    path = get_db_path()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def log_error(
    severity: str,
    component: str,
    category: str,
    message: str,
    *,
    details: dict | None = None,
    file_path: str | None = None,
    task_id: str | None = None,
    proposal_id: str | None = None,
    line_guid: str | None = None,
    stack_trace: str | None = None,
    agent_name: str | None = None,
) -> None:
    """
    Best-effort error logging that never blocks the caller.

    Always prints to stdout first (the reliable channel); the INSERT is
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
            (level, message, context, file_path, function_name, task_id, stack_trace, agent_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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
                        "agent_name": agent_name,
                    }
                ),
                file_path,
                f"{component}.{category}",
                task_id,
                stack_trace,
                agent_name,
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


def reconstruct_file_content(conn: sqlite3.Connection, file_id: int) -> str:
    """Reconstruct current file content from line table ordered by sort_order.

    Schema (core.db): file_lines uses is_deleted + sort_order — not is_current
    or line_number. Matches initialize_file_lines / writer inserts.
    """
    cursor = conn.execute(
        """
        SELECT content FROM file_lines
        WHERE file_id = ? AND COALESCE(is_deleted, 0) = 0
        ORDER BY sort_order
        """,
        (file_id,),
    )
    lines = []
    for row in cursor.fetchall():
        if isinstance(row, sqlite3.Row) or (hasattr(row, "keys") and not isinstance(row, tuple)):
            lines.append(row["content"])
        else:
            lines.append(row[0])
    return "\n".join(lines)


def capture_current_hashes(conn: sqlite3.Connection, file_id: int, line_guids: list[str]) -> dict[str, str]:
    """Return {line_guid: content_hash} for the given guids."""
    if not line_guids:
        return {}
    placeholders = ",".join("?" * len(line_guids))
    rows = conn.execute(
        f"SELECT line_guid, content_hash FROM file_lines WHERE line_guid IN ({placeholders})",
        line_guids,
    ).fetchall()
    return {row["line_guid"]: row["content_hash"] for row in rows}
