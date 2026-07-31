"""
Thin mutation-path event log (Phase D1).

stdlib + sqlite only. Not a full event bus — append-only domain events
for proposal / edit lifecycle observability.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.db_connection import get_db_connection


def publish_event(
    event_type: str,
    *,
    source: str = "system",
    task_id: Optional[str] = None,
    proposal_id: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> Optional[int]:
    """Append one event row. Returns event id or None on failure."""
    try:
        with get_db_connection() as conn:
            # Ensure table exists on older DBs
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT,
                    ts TEXT,
                    type TEXT NOT NULL,
                    source TEXT,
                    payload_json TEXT,
                    proposal_id TEXT
                )
                """
            )
            cur = conn.execute(
                """
                INSERT INTO events (task_id, ts, type, source, payload_json, proposal_id)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    datetime.now(timezone.utc).isoformat(),
                    event_type,
                    source,
                    json.dumps(payload or {}),
                    proposal_id,
                ),
            )
            return cur.lastrowid
    except Exception as e:
        print(f"   ⚠️  publish_event failed: {e}")
        return None


def list_events(
    task_id: Optional[str] = None,
    event_type: Optional[str] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    with get_db_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT,
                ts TEXT,
                type TEXT NOT NULL,
                source TEXT,
                payload_json TEXT,
                proposal_id TEXT
            )
            """
        )
        q = "SELECT id, task_id, ts, type, source, payload_json, proposal_id FROM events WHERE 1=1"
        params: list = []
        if task_id:
            q += " AND task_id = ?"
            params.append(task_id)
        if event_type:
            q += " AND type = ?"
            params.append(event_type)
        q += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(q, params).fetchall()
        out = []
        for r in rows:
            out.append({
                "id": r[0],
                "task_id": r[1],
                "ts": r[2],
                "type": r[3],
                "source": r[4],
                "payload": json.loads(r[5] or "{}"),
                "proposal_id": r[6],
            })
        return out
