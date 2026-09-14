"""§15.3 B5: DB timestamp writers produce naive UTC, not local wall time."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from core.db_helpers import utcnow, utcnow_iso

PROJECT_ROOT = Path(__file__).parent.parent.parent

# Writer modules normalized to the naive-UTC helpers. These must not emit local
# ``datetime.now()`` timestamps into DB columns that interop with SQLite
# ``datetime('now')`` / ``CURRENT_TIMESTAMP``.
_UTC_NORMALIZED_MODULES = (
    "core/db_helpers.py",
    "core/file_operations.py",
    "core/archival.py",
    "core/fallback_stats.py",
    "file_editing/writer.py",
    "agents/archivist_worker.py",
    "agents/reporter_worker.py",
    "agents/resource_controller_worker.py",
    "agents/prioritizer_worker.py",
)


def test_utcnow_is_naive_utc():
    n = utcnow()
    assert n.tzinfo is None
    # Within a few seconds of true UTC wall time.
    drift = abs((datetime.now(timezone.utc).replace(tzinfo=None) - n).total_seconds())
    assert drift < 5


def test_utcnow_iso_round_trips_utc():
    iso = utcnow_iso()
    parsed = datetime.fromisoformat(iso)
    assert parsed.tzinfo is None
    drift = abs((datetime.now(timezone.utc).replace(tzinfo=None) - parsed).total_seconds())
    assert drift < 5


def test_utcnow_monotonic():
    a = utcnow_iso()
    b = utcnow_iso()
    assert datetime.fromisoformat(b) >= datetime.fromisoformat(a) - timedelta(seconds=1)


def test_normalized_writers_emit_no_local_datetime_now():
    """No stray local-time writers remain in DB-interop modules."""
    for rel in _UTC_NORMALIZED_MODULES:
        src = (PROJECT_ROOT / rel).read_text(encoding="utf-8")
        assert "datetime.now()" not in src, f"{rel} still calls datetime.now()"
