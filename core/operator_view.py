"""
Read-only operator view over the runtime agents.db (Part 1: operator console).

The primary architecture stays single-writer / single-process. Every read here
opens one short ``mode=ro`` transaction and closes it immediately: no PRAGMAs
are mutated, no WAL is required, and a long-running console can never block a
worker holding the write side. Mirrors the read-only discipline of
``utils/query_developer_responses.py`` for live observability.

Nothing in this module writes to the database.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any

from core.db import get_db_path


def _ro_conn(db_path: str | None = None) -> sqlite3.Connection:
    path = db_path or get_db_path()
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5.0)
    conn.row_factory = sqlite3.Row
    return conn


def _normalize_ts(value: str | None) -> datetime | None:
    """Parse an ISO timestamp (with or without tz suffix) as timezone-aware UTC."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _age_seconds(value: str | None, now: datetime) -> int | None:
    dt = _normalize_ts(value)
    if dt is None:
        return None
    return max(int((now - dt).total_seconds()), 0)


def _row_fields(row: sqlite3.Row, fields: list[str]) -> dict[str, Any]:
    return {f: (row[f] if f in row.keys() else None) for f in fields}


def snapshot(db_path: str | None = None, now: datetime | None = None) -> dict[str, Any]:
    """High-level status for the console header panes.

    Returns tasks (recent 20), endpoint latches, open-feedback backlog summary,
    token spend (window + total), and the recent model-outcome health window.
    """
    now = now or datetime.now(timezone.utc)
    out: dict[str, Any] = {
        "tasks": [],
        "endpoints": [],
        "backlog": {"open": 0, "high": 0, "stuck": 0},
        "spend": {"window_seconds": 14400, "window_tokens": 0, "total_tokens": 0},
        "health_window_seconds": 300,
        "health": {"calls": 0, "ok": 0, "avg_latency_ms": None},
    }
    with _ro_conn(db_path) as conn:
        rows = conn.execute("""
            SELECT id, description, status, started_at, completed_at
            FROM tasks
            ORDER BY started_at DESC
            LIMIT 20
            """).fetchall()
        for row in rows:
            item = dict(row)
            item["age_s"] = _age_seconds(row["started_at"], now)
            out["tasks"].append(item)

        for row in conn.execute("SELECT * FROM endpoint_health"):
            item = _row_fields(
                row,
                [
                    "endpoint_name",
                    "status",
                    "consecutive_failures",
                    "last_success",
                    "unavailable_until",
                    "tokens_per_minute",
                    "tokens_remaining_minute",
                    "tokens_reset_epoch",
                ],
            )
            item["unavailable_in_s"] = _age_seconds(item["unavailable_until"], now) if item.get("unavailable_until") else None
            out["endpoints"].append(item)

        row = conn.execute("""
            SELECT COUNT(*) AS open, SUM(priority = 'HIGH') AS high, SUM(stuck = 1) AS stuck
            FROM agent_feedback
            WHERE addressed = 0
            """).fetchone()
        out["backlog"] = {
            "open": row["open"] or 0,
            "high": row["high"] or 0,
            "stuck": row["stuck"] or 0,
        }

        # token_log.timestamp is an ISO string; compare lexically for the window.
        iso_window = now.isoformat(timespec="seconds")
        row = conn.execute(
            "SELECT COALESCE(SUM(tokens_used), 0) AS w FROM token_log WHERE timestamp >= ?",
            (iso_window,),
        ).fetchone()
        out["spend"]["window_tokens"] = row["w"]
        row = conn.execute("SELECT COALESCE(SUM(tokens_used), 0) AS t FROM token_log").fetchone()
        out["spend"]["total_tokens"] = row["t"]

        # model_health_events.ts is an ISO timestamp string; filter by a
        # threshold computed from a max ts of the same format.
        row = conn.execute("""
            SELECT COUNT(*) AS n, COALESCE(SUM(ok), 0) AS ok, AVG(latency_ms) AS avg_ms
            FROM model_health_events
            """).fetchone()
        out["health"] = {"calls": row["n"] or 0, "ok": row["ok"] or 0, "avg_latency_ms": row["avg_ms"]}
    return out


def task_trace(task_id: str, db_path: str | None = None) -> dict[str, Any]:
    """Full trace for one task: archived developer steps + lifecycle events."""
    out: dict[str, Any] = {"task_id": task_id, "steps": [], "events": []}
    with _ro_conn(db_path) as conn:
        for row in conn.execute(
            """
            SELECT id, step_number, model, response_format_status, parse_success,
                   command, command_exit_code, timestamp
            FROM agent_responses_archive
            WHERE task_id = ?
            ORDER BY id
            """,
            (task_id,),
        ):
            out["steps"].append(dict(row))
        for row in conn.execute(
            """
            SELECT id, ts, type, source, payload_json
            FROM events
            WHERE task_id = ?
            ORDER BY id
            """,
            (task_id,),
        ):
            item = dict(row)
            try:
                import json

                item["payload"] = json.loads(item.pop("payload_json") or "{}")
            except (ValueError, TypeError):
                item["payload"] = {}
            out["events"].append(item)
        for row in conn.execute(
            "SELECT description, status, started_at, completed_at FROM tasks WHERE id = ?",
            (task_id,),
        ):
            out["task"] = dict(row)
    return out


def developer_session_live(task_id: str, db_path: str | None = None, now: datetime | None = None) -> dict[str, Any]:
    """Live view of one shell-developer session for the console.

    ``in_flight`` reports seconds since the last ``shell_model_call_started``
    heartbeat when no later ``shell_command_executed`` / ``shell_turn_start``
    event supersedes it — i.e. the operator sees a model call actually waiting
    on the endpoint, not the last logged result.
    """
    now = now or datetime.now(timezone.utc)
    out: dict[str, Any] = {
        "task_id": task_id,
        "steps": 0,
        "last_step_number": None,
        "last_command": None,
        "last_exit_code": None,
        "last_step_ts": None,
        "in_flight": False,
        "in_flight_s": None,
        "last_event": None,
        "last_event_ts": None,
    }
    with _ro_conn(db_path) as conn:
        row = conn.execute(
            """
            SELECT step_number, command, command_exit_code, timestamp
            FROM agent_responses_archive
            WHERE task_id = ? AND command IS NOT NULL AND command_exit_code IS NOT NULL
            ORDER BY id DESC
            LIMIT 1
            """,
            (task_id,),
        ).fetchone()
        if row:
            out["steps"] = conn.execute(
                "SELECT COUNT(*) AS n FROM agent_responses_archive WHERE task_id = ?",
                (task_id,),
            ).fetchone()["n"]
            out["last_step_number"] = row["step_number"]
            out["last_command"] = row["command"]
            out["last_exit_code"] = row["command_exit_code"]
            out["last_step_ts"] = row["timestamp"]

        rows = conn.execute(
            """
            SELECT ts, type, payload_json
            FROM events
            WHERE task_id = ? AND type IN ('shell_turn_start', 'shell_model_call_started', 'shell_command_executed')
            ORDER BY id
            """,
            (task_id,),
        ).fetchall()
        if rows:
            out["last_event"], out["last_event_ts"] = rows[-1]["type"], rows[-1]["ts"]
            started_ts = None
            for r in reversed(rows):
                if r["type"] == "shell_model_call_started":
                    started_ts = r["ts"]
                    break
                if r["type"] in ("shell_turn_start", "shell_command_executed"):
                    break
            if started_ts is not None:
                started_dt = _normalize_ts(started_ts)
                last_step_dt = _normalize_ts(out["last_step_ts"]) if out["last_step_ts"] else None
                # A call heartbeat is only "in flight" if nothing completed
                # after it (a later command/finish supersedes the marker).
                if started_dt is not None and (last_step_dt is None or started_dt > last_step_dt):
                    out["in_flight"] = True
                    out["in_flight_s"] = _age_seconds(started_ts, now)
    return out


def feedback_backlog(task_id: str | None = None, db_path: str | None = None) -> list[dict[str, Any]]:
    """Open feedback items with their duplication/targeting/stuck indicators."""
    q = """
        SELECT id, agent_name, file_path, priority, category, message, suggestion,
               task_id, timestamp, dup_key, dup_count, targeted_count, stuck
        FROM agent_feedback
        WHERE addressed = 0
    """
    params: tuple = ()
    if task_id:
        q += " AND task_id = ?"
        params = (task_id,)
    q += " ORDER BY CASE priority WHEN 'HIGH' THEN 0 WHEN 'MEDIUM' THEN 1 ELSE 2 END, id"
    with _ro_conn(db_path) as conn:
        return [dict(r) for r in conn.execute(q, params).fetchall()]


def health_summary(db_path: str | None = None, limit: int = 20) -> dict[str, Any]:
    """Recent per-model endpoint outcome events (recency window for the console)."""
    out: dict[str, Any] = {"recent": []}
    with _ro_conn(db_path) as conn:
        for row in conn.execute(
            """
            SELECT ts, model_ref, endpoint, ok, latency_ms, kind, retry_after_s, detail
            FROM model_health_events
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ):
            out["recent"].append(dict(row))
    out["recent"].reverse()
    return out
