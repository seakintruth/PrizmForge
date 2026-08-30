"""Per-model health tracking with recency-weighted flakiness scoring.

Why this exists
===============
EndpointHealth tracks per-ENDPOINT outages (error_count, consecutive_failures,
unavailable_until), but free-tier instability is usually per-MODEL: one model on
an endpoint hammers rate limits while siblings stay fine. This module keeps a
lightweight, SQLite-backed event log of per-model outcomes and derives:

- a recency-weighted failure ratio (exponential decay, configurable half-life),
- the current consecutive-failure streak,
- an automatic demotion verdict with a growing-but-capped cooldown,
- a short "down" window: after ``down_streak`` consecutive failures a model is
  treated as unavailable for ~``down_base_seconds`` (doubling per extra
  failure, capped) so rotation skips it instead of re-dialing the same dead
  model. Unlike endpoint cooldowns this is per-model, and unlike demotion it
  is enforced: down models are only attempted when no healthy candidate exists.

Demotion is advisory ordering, not exclusion: ``rank_candidates`` sorts
candidates so healthy models are tried first, demoted ones next, and currently
-down ones last. A demoted model is still usable (explicit requests always go
through) and automatically recovers once its recent window looks healthy again
— the verdict is recomputed from events on demand, so there is no sticky state
to reset.

All DB access is best-effort: any failure degrades to "no history" and never
breaks an LLM call.

Config (all optional, under ``model_health``)::

    {
      "enabled": true,
      "half_life_minutes": 45,
      "failure_ratio_threshold": 0.6,
      "min_samples_for_demotion": 5,
      "consecutive_failure_threshold": 4,
      "base_cooldown_minutes": 15,
      "max_cooldown_minutes": 240,
      "down_streak": 2,
      "down_base_seconds": 300,
      "down_max_seconds": 1800,
      "event_retention_hours": 72
    }
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)

try:
    from core.config import get_config
except ImportError:  # pragma: no cover - standalone usage

    def get_config() -> dict[str, Any]:
        return {}


try:
    from core.db import get_db_path

    def _db_file() -> str:
        return str(get_db_path())

except ImportError:  # pragma: no cover - standalone usage

    def _db_file() -> str:
        from pathlib import Path

        return str(Path.cwd() / ".PrizmForge" / "agents.db")


# Defaults mirror the documented config block above.
DEFAULTS = {
    "enabled": True,
    "half_life_minutes": 45,
    "failure_ratio_threshold": 0.6,
    "min_samples_for_demotion": 5,
    "consecutive_failure_threshold": 4,
    "base_cooldown_minutes": 15,
    "max_cooldown_minutes": 240,
    "down_streak": 2,
    "down_base_seconds": 300,
    "down_max_seconds": 1800,
    "event_retention_hours": 72,
}

_LOCK = threading.Lock()
_PRUNE_EVERY = 64  # records between lazy prune passes
# NOTE: only ever mutated under _LOCK inside record_model_outcome(), so the
# read-modify-write counter is safe (SQLite writes themselves are serialized).
_records_since_prune = 0


def _setting(key: str) -> Any:
    try:
        cfg = get_config().get("model_health", {}) or {}
        val = cfg.get(key, DEFAULTS[key])
    except Exception:
        val = DEFAULTS[key]
    return DEFAULTS[key] if val is None else val


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_file(), timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS model_health_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            model_ref TEXT NOT NULL,
            endpoint TEXT,
            ok INTEGER NOT NULL,
            latency_ms INTEGER DEFAULT 0,
            kind TEXT DEFAULT ''
        )
        """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_model_health_events_ref_ts ON model_health_events(model_ref, ts)")
    return conn


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def _parse(ts: str) -> datetime | None:
    try:
        return datetime.fromisoformat(str(ts))
    except (ValueError, TypeError):
        return None


def _decay_weight(ts: datetime, now: datetime) -> float:
    """Exponential recency weight: 1.0 now, 0.5 one half-life ago."""
    half_life = max(float(_setting("half_life_minutes")), 1.0)
    age_min = max((now - ts).total_seconds() / 60.0, 0.0)
    return 0.5 ** (age_min / half_life)


def record_model_outcome(
    model_ref: str | None,
    endpoint: str | None = None,
    ok: bool = True,
    latency_ms: int = 0,
    kind: str = "",
) -> None:
    """Record one request outcome. Never raises; silently skips when disabled."""
    if not model_ref or not _setting("enabled"):
        return
    global _records_since_prune
    try:
        with _LOCK:
            conn = _connect()
            try:
                conn.execute(
                    "INSERT INTO model_health_events (ts, model_ref, endpoint, ok, latency_ms, kind) VALUES (?, ?, ?, ?, ?, ?)",
                    (_iso(datetime.now()), str(model_ref), endpoint, 1 if ok else 0, int(latency_ms), kind[:60]),
                )
                conn.commit()
            finally:
                conn.close()
            _records_since_prune += 1
            if _records_since_prune >= _PRUNE_EVERY:
                _records_since_prune = 0
                prune_old_events()
    except Exception as e:  # tracker must never break request flow
        logger.debug(f"model_health record skipped: {e}")


def prune_old_events(retention_hours: float | None = None) -> int:
    """Delete events older than the retention window. Returns rows removed."""
    hours = float(retention_hours if retention_hours is not None else _setting("event_retention_hours"))
    cutoff = _iso(datetime.now() - timedelta(hours=max(hours, 1.0)))
    try:
        conn = _connect()
        try:
            cur = conn.execute("DELETE FROM model_health_events WHERE ts < ?", (cutoff,))
            conn.commit()
            return cur.rowcount or 0
        finally:
            conn.close()
    except Exception:
        return 0


def load_events(model_ref: str | None = None, since_hours: float | None = None) -> list[dict]:
    """Return events (oldest first) optionally scoped to a model and window."""
    hours = float(since_hours if since_hours is not None else max(float(_setting("event_retention_hours")), 1.0))
    cutoff = _iso(datetime.now() - timedelta(hours=hours))
    sql = "SELECT ts, model_ref, endpoint, ok, latency_ms, kind FROM model_health_events WHERE ts >= ?"
    params: list[Any] = [cutoff]
    if model_ref:
        sql += " AND model_ref = ?"
        params.append(model_ref)
    sql += " ORDER BY ts ASC"
    try:
        conn = _connect()
        try:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()
    except Exception:
        return []


def load_events_for_models(
    model_refs: Sequence[str],
    since_hours: float | None = None,
) -> dict[str, list[dict]]:
    """Load events for several models in a single query.

    Returns ``{model_ref: events_oldest_first}`` scoped to the retention
    window, so callers scoring many candidates avoid N+1 round-trips. Unknown
    refs map to empty lists; DB failure degrades to {}.
    """
    refs = list(dict.fromkeys(r for r in model_refs if r))
    if not refs:
        return {}
    hours = float(since_hours if since_hours is not None else max(float(_setting("event_retention_hours")), 1.0))
    cutoff = _iso(datetime.now() - timedelta(hours=hours))
    placeholders = ",".join("?" for _ in refs)
    # placeholders holds only fixed "?" marks (a count, never user text), so the
    # IN (...) clause is injection-safe-by-construction despite the static scan.
    sql = (
        "SELECT ts, model_ref, endpoint, ok, latency_ms, kind FROM model_health_events "  # noqa: S608
        "WHERE ts >= ? AND model_ref IN (" + placeholders + ") ORDER BY ts ASC"
    )
    out: dict[str, list[dict]] = {r: [] for r in refs}
    try:
        conn = _connect()
        try:
            for row in conn.execute(sql, [cutoff, *refs]).fetchall():
                d = dict(row)
                key = str(d.get("model_ref"))
                if key in out:
                    out[key].append(d)
        finally:
            conn.close()
    except Exception:
        return {}
    return out


def compute_stats(events: list[dict], now: datetime | None = None) -> dict:
    """Derive recency-weighted stats from an event list (see record_model_outcome)."""
    now = now or datetime.now()
    wf = ws = 0.0
    latencies: list[int] = []
    last_error_ts: str | None = None
    streak = 0  # trailing run of failures (events are oldest-first)
    skipped = 0  # events with an unparseable ts, excluded from all stats
    for ev in events:
        raw_ts = ev.get("ts") or ""
        ts = _parse(raw_ts)
        if ts is None:
            skipped += 1
            continue
        w = _decay_weight(ts, now)
        if ev.get("ok"):
            ws += w
            streak = 0
        else:
            wf += w
            streak += 1
            last_error_ts = ev.get("ts")
        if ev.get("latency_ms"):
            latencies.append(int(ev["latency_ms"]))
    attempts = len(events) - skipped
    denom = wf + ws
    return {
        "attempts": attempts,
        "skipped_events": skipped,
        "weighted_failures": round(wf, 3),
        "weighted_successes": round(ws, 3),
        "weighted_samples": round(denom, 3),
        "failure_ratio": round(wf / denom, 3) if denom > 0 else 0.0,
        "consecutive_failures": streak,
        "last_error_ts": last_error_ts,
        "avg_latency_ms": int(sum(latencies) / len(latencies)) if latencies else 0,
    }


def evaluate_demotion(stats: dict, now: datetime | None = None) -> dict | None:
    """Turn stats into a demotion verdict (dict with until/reason) or None."""
    now = now or datetime.now()
    ratio_thr = float(_setting("failure_ratio_threshold"))
    min_samples = float(_setting("min_samples_for_demotion"))
    streak_thr = int(_setting("consecutive_failure_threshold"))
    base_cd = float(_setting("base_cooldown_minutes"))
    max_cd = float(_setting("max_cooldown_minutes"))

    ratio = float(stats.get("failure_ratio", 0.0))
    samples = float(stats.get("weighted_samples", 0.0))
    streak = int(stats.get("consecutive_failures", 0))

    if streak >= streak_thr:
        # Streak rule trips early; cooldown doubles with each extra failure, capped.
        extra = streak - streak_thr
        minutes = min(base_cd * (2**extra), max_cd)
        return {"until": now + timedelta(minutes=minutes), "reason": f"{streak} consecutive failures"}
    if samples >= min_samples and ratio >= ratio_thr:
        return {"until": now + timedelta(minutes=base_cd), "reason": f"failure_ratio {ratio:.2f} >= {ratio_thr}"}
    return None


def model_verdict(model_ref: str, now: datetime | None = None) -> dict:
    """Convenience: stats + demotion verdict + effective rank penalty for one model."""
    now = now or datetime.now()
    stats = compute_stats(load_events(model_ref), now=now)
    demotion = evaluate_demotion(stats, now=now)
    return {"model_ref": model_ref, **stats, "demotion": demotion}


def _compute_down_until(stats: dict, now: datetime | None = None) -> datetime | None:
    """Enforced down-window derived from already-computed stats."""
    now = now or datetime.now()
    streak_thr = int(_setting("down_streak"))
    base_s = float(_setting("down_base_seconds"))
    max_s = float(_setting("down_max_seconds"))

    streak = int(stats.get("consecutive_failures", 0))
    if streak < streak_thr or not stats.get("last_error_ts"):
        return None

    last_fail = _parse(str(stats["last_error_ts"]))
    if last_fail is None:
        return None
    extra = streak - streak_thr
    seconds = min(base_s * (2**extra), max_s)
    until = last_fail + timedelta(seconds=seconds)
    return until if until > now else None


def model_down_until(model_ref: str, now: datetime | None = None) -> datetime | None:
    """Short enforced down-window after repeated consecutive failures.

    After ``down_streak`` trailing failures a model is considered down until
    ``last_failure + down_base_seconds``, doubling per extra failure and
    capped at ``down_max_seconds``. Any success clears it (streak resets).
    Returns None while the model is up.
    """
    now = now or datetime.now()
    stats = compute_stats(load_events(model_ref), now=now)
    return _compute_down_until(stats, now=now)


def rank_candidates(candidates: list[tuple[str, int]], now: datetime | None = None) -> list[tuple[str, int]]:
    """Order ``(model_ref, priority)`` pairs: healthy → demoted → down.

    Healthy candidates sort by weighted failure_ratio ascending, then by the
    caller's priority ascending. Demoted candidates keep their relative order
    behind all healthy ones. Currently-down models (recent failure streak)
    sink behind even those — they are only reached when nothing healthier
    exists, which doubles as the automatic recovery probe during full outages.
    """
    now = now or datetime.now()
    events_by_ref = load_events_for_models([ref for ref, _pri in candidates])
    scored: list[tuple[int, float, int, str]] = []
    for model_ref, priority in candidates:
        stats = compute_stats(events_by_ref.get(model_ref, []), now=now)
        tier = 0
        if evaluate_demotion(stats, now=now):
            tier = 1
        if _compute_down_until(stats, now=now):
            tier = 2
        scored.append((tier, float(stats["failure_ratio"]), int(priority or 0), model_ref))
    scored.sort(key=lambda t: (t[0], t[1], t[2], t[3]))
    return [(m, p) for (_t, _r, p, m) in scored]


def health_report(limit: int = 30, now: datetime | None = None) -> list[dict]:
    """Per-model report rows (worst first) for CLI/dashboards."""
    now = now or datetime.now()
    events = load_events()
    by_model: dict[str, list[dict]] = {}
    for ev in events:
        by_model.setdefault(str(ev.get("model_ref")), []).append(ev)
    rows = []
    for model_ref, evs in by_model.items():
        stats = compute_stats(evs, now=now)
        demotion = evaluate_demotion(stats, now=now)
        rows.append(
            {
                "model_ref": model_ref,
                "attempts": stats["attempts"],
                "fail_ratio": stats["failure_ratio"],
                "streak": stats["consecutive_failures"],
                "avg_ms": stats["avg_latency_ms"],
                "demoted": "YES" if demotion else "",
                "until": _iso(demotion["until"]) if demotion else "",
                "reason": demotion["reason"] if demotion else "",
            }
        )
    rows.sort(key=lambda r: (-r["fail_ratio"], -r["streak"], r["model_ref"]))
    return rows[:limit]
