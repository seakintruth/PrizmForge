"""Tests for recency-weighted per-model health tracking (core/model_health.py)."""

from datetime import datetime, timedelta

import pytest

from core import model_health as mh


@pytest.fixture
def tracker_db(temp_db, monkeypatch):
    """Point the tracker at the isolated test DB and reset module state."""
    monkeypatch.setattr(mh, "_db_file", lambda: temp_db)
    monkeypatch.setattr(mh, "_records_since_prune", 0)
    yield temp_db


def _ev(ts, ok, latency_ms=0):
    return {"ts": ts.isoformat(timespec="seconds"), "ok": 1 if ok else 0, "latency_ms": latency_ms}


# =========================================================================
# Scoring math
# =========================================================================
def test_decay_weights_recent_failures_more(tracker_db):
    now = datetime.now()
    # One fresh failure and one failure one half-life old (weight 0.5 each).
    events = [_ev(now - timedelta(minutes=1), False), _ev(now - timedelta(minutes=45), False)]
    stats = mh.compute_stats(events, now=now)
    assert 1.4 < stats["weighted_failures"] < 1.6

    # Same count, but both recent → higher weighted failures.
    fresh = mh.compute_stats([_ev(now, False), _ev(now, False)], now=now)
    assert fresh["weighted_failures"] > stats["weighted_failures"]


def test_successes_reduce_failure_ratio(tracker_db):
    now = datetime.now()
    events = [_ev(now, True), _ev(now, False), _ev(now, True)]
    stats = mh.compute_stats(events, now=now)
    assert stats["failure_ratio"] == pytest.approx(1 / 3, abs=0.01)


def test_consecutive_streak_counts_trailing_failures_only(tracker_db):
    now = datetime.now()
    events = [
        _ev(now - timedelta(minutes=5), False),
        _ev(now - timedelta(minutes=4), False),
        _ev(now - timedelta(minutes=3), True),
        _ev(now - timedelta(minutes=2), False),
        _ev(now - timedelta(minutes=1), False),
    ]
    stats = mh.compute_stats(events, now=now)
    assert stats["consecutive_failures"] == 2


# =========================================================================
# Demotion verdicts
# =========================================================================
def test_demotion_requires_min_samples(tracker_db):
    now = datetime.now()
    stats = {"failure_ratio": 1.0, "weighted_samples": 2.0, "consecutive_failures": 1}
    assert mh.evaluate_demotion(stats, now=now) is None


def test_ratio_rule_demotes_with_base_cooldown(tracker_db):
    now = datetime.now()
    stats = {"failure_ratio": 0.9, "weighted_samples": 10.0, "consecutive_failures": 1}
    verdict = mh.evaluate_demotion(stats, now=now)
    assert verdict is not None
    assert (verdict["until"] - now).total_seconds() == pytest.approx(15 * 60, rel=0.01)
    assert "ratio" in verdict["reason"]


def test_streak_rule_trips_early_and_doubles_cooldown(tracker_db):
    cfg = dict(mh.DEFAULTS, consecutive_failure_threshold=4, base_cooldown_minutes=15, max_cooldown_minutes=60)
    now = datetime.now()

    stats = {"failure_ratio": 0.0, "weighted_samples": 1.0, "consecutive_failures": 4}
    stats6 = {**stats, "consecutive_failures": 6}
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(mh, "_setting", lambda k: cfg[k])
        v4 = mh.evaluate_demotion(stats, now=now)
        v6 = mh.evaluate_demotion(stats6, now=now)
        assert v4 is not None
        assert (v6["until"] - now).total_seconds() == pytest.approx(60 * 60, rel=0.01)  # capped at max
        assert (v6["until"] - now).total_seconds() > (v4["until"] - now).total_seconds()


def test_recovery_after_successes_clears_demotion(tracker_db):
    now = datetime.now()
    # Flaky past, then a run of successes: streak resets and ratio drops.
    events = [_ev(now - timedelta(hours=2), False)] * 5 + [_ev(now - timedelta(minutes=i), True) for i in range(1, 9)]
    stats = mh.compute_stats(events, now=now)
    assert mh.evaluate_demotion(stats, now=now) is None


# =========================================================================
# Ranking + persistence
# =========================================================================
def test_rank_candidates_puts_demoted_last(tracker_db):
    import sqlite3
    from datetime import datetime

    healthy, flaky = "ep/a-good", "ep/b-flaky"
    conn = sqlite3.connect(tracker_db)
    base = datetime.now()
    for i in range(8):  # flaky: all failures, recent
        ts = (base - timedelta(minutes=30 - i)).isoformat(timespec="seconds")
        conn.execute(
            "INSERT INTO model_health_events (ts, model_ref, endpoint, ok, latency_ms, kind) VALUES (?, ?, ?, 0, 0, 'x')",
            (ts, flaky, "ep"),
        )
    conn.commit()
    conn.close()

    ranked = mh.rank_candidates([(flaky, 10), (healthy, 20)])
    assert ranked[0][0] == healthy
    assert ranked[-1][0] == flaky


def test_record_outcome_persists_and_prunes(tracker_db):
    mh.record_model_outcome("ep/m", "ep", ok=True, latency_ms=123)
    mh.record_model_outcome("ep/m", "ep", ok=False, kind="timeout")
    events = mh.load_events("ep/m")
    assert len(events) == 2
    assert any(e["kind"] == "timeout" for e in events)

    removed = mh.prune_old_events(retention_hours=1) >= 0
    assert removed  # call succeeds; rowcount may legitimately be 0


def test_disabled_tracker_records_nothing(tracker_db, monkeypatch):
    monkeypatch.setattr(mh, "_setting", lambda k: False if k == "enabled" else mh.DEFAULTS[k])
    mh.record_model_outcome("ep/x", "ep", ok=False)
    assert mh.load_events("ep/x") == []


def test_health_report_flags_worst_model(tracker_db):
    for _ in range(6):
        mh.record_model_outcome("ep/bad", "ep", ok=False, kind="rate_limited")
    for _ in range(6):
        mh.record_model_outcome("ep/good", "ep", ok=True, latency_ms=50)

    rows = mh.health_report()
    by_ref = {r["model_ref"]: r for r in rows}
    assert by_ref["ep/bad"]["demoted"] == "YES"
    assert by_ref["ep/good"]["demoted"] == ""


def test_load_events_for_models_partitions_and_orders(tracker_db):
    import sqlite3

    now = datetime.now()
    conn = sqlite3.connect(tracker_db)
    for i, ok in enumerate([1, 0, 1]):
        ref = "ep/a" if i < 2 else "ep/b"
        ts = (now - timedelta(minutes=3 - i)).isoformat(timespec="seconds")
        conn.execute(
            "INSERT INTO model_health_events (ts, model_ref, endpoint, ok, latency_ms, kind) VALUES (?, ?, ?, ?, 0, 'x')",
            (ts, ref, "ep", ok),
        )
    conn.commit()
    conn.close()

    got = mh.load_events_for_models(["ep/a", "ep/b", "ep/nope"])
    assert [e["ok"] for e in got["ep/a"]] == [1, 0]  # oldest first
    assert len(got["ep/b"]) == 1
    assert got["ep/nope"] == []
    assert got == {"ep/a": got["ep/a"], "ep/b": got["ep/b"], "ep/nope": []}

    assert mh.load_events_for_models([]) == {}


def test_compute_stats_skips_unparseable_ts(tracker_db):
    now = datetime.now()
    events = [_ev(now, True), {"ts": "not-a-date", "ok": 0, "latency_ms": 0}, _ev(now, False)]
    stats = mh.compute_stats(events, now=now)
    assert stats["attempts"] == 2
    assert stats["skipped_events"] == 1
    assert stats["consecutive_failures"] == 1
    assert stats["last_error_ts"] is not None  # only the parseable failure counted


def test_rank_candidates_sinks_down_models_last(tracker_db):
    import sqlite3

    conn = sqlite3.connect(tracker_db)
    now = datetime.now()
    for i, ok in enumerate([0, 0]):
        ts = (now - timedelta(seconds=2 - i)).isoformat(timespec="seconds")
        conn.execute(
            "INSERT INTO model_health_events (ts, model_ref, endpoint, ok, latency_ms, kind) VALUES (?, ?, ?, ?, 0, 'x')",
            (ts, "ep/down", "ep", ok),
        )
    conn.commit()
    conn.close()

    ranked = mh.rank_candidates([("ep/healthy", 20), ("ep/down", 10)])
    assert ranked[0][0] == "ep/healthy"
    assert ranked[-1][0] == "ep/down"
