"""Tests for per-model down windows + prioritizer round-robin rotation.

Follow-up to the soak P2 fix: instead of parking the worker idle, failed
models are marked down (~5 min, doubling, capped) and the categorization
loop rotates to the next healthy candidate — landing on a sibling model
when rotation wraps back to the original endpoint.
"""

import typing
from datetime import datetime, timedelta

import pytest

from core import model_health as mh


@pytest.fixture
def tracker_db(temp_db, monkeypatch):
    monkeypatch.setattr(mh, "_db_file", lambda: temp_db)
    monkeypatch.setattr(mh, "_records_since_prune", 0)
    yield temp_db


# =========================================================================
# model_down_until
# =========================================================================
def test_two_consecutive_failures_mark_model_down_5_minutes(tracker_db):
    now = datetime.now()
    for _ in range(2):  # streak threshold default = 2
        mh.record_model_outcome("ep/a/m1", "ep", ok=False, kind="rate_limited")
    until = mh.model_down_until("ep/a/m1", now=now + timedelta(seconds=10))
    assert until is not None
    # last failure was ~now → window ends ~5 min out
    assert 200 < (until - now).total_seconds() < 310


def test_single_failure_does_not_mark_down(tracker_db):
    mh.record_model_outcome("ep/a/m1", "ep", ok=False)
    assert mh.model_down_until("ep/a/m1") is None


def test_down_window_doubles_and_caps(tracker_db):
    now = datetime.now()
    for _ in range(4):  # streak 4 → base * 2^(4-2) = 1200s, cap 1800s not hit
        mh.record_model_outcome("ep/a/m1", "ep", ok=False)
    stats = mh.compute_stats(mh.load_events("ep/a/m1"), now=now)
    assert stats["consecutive_failures"] == 4
    until = mh.model_down_until("ep/a/m1", now=now)
    assert until is not None
    delta = (until - now).total_seconds()
    assert 1100 < delta <= 1210


def test_success_clears_down_window(tracker_db):
    mh.record_model_outcome("ep/a/m1", "ep", ok=False)
    mh.record_model_outcome("ep/a/m1", "ep", ok=False)
    mh.record_model_outcome("ep/a/m1", "ep", ok=True)  # streak reset
    assert mh.model_down_until("ep/a/m1") is None


def test_expired_window_reports_up(tracker_db):
    now = datetime.now()
    for _ in range(2):
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(mh, "datetime", __import__("datetime").datetime)
        mh.record_model_outcome("ep/a/m1", "ep", ok=False)
    # Simulate old failures by rewriting timestamps directly.
    import sqlite3

    conn = sqlite3.connect(tracker_db)
    old = (now - timedelta(hours=2)).isoformat(timespec="seconds")
    conn.execute("UPDATE model_health_events SET ts=?", (old,))
    conn.commit()
    conn.close()
    assert mh.model_down_until("ep/a/m1", now=now) is None


# =========================================================================
# ranking tiers: healthy → demoted → down
# =========================================================================
def test_rank_puts_down_model_behind_everything(tracker_db):
    now = datetime.now()
    healthy, demotedish, dead = "ep/h", "ep/d", "ep/x"

    # dead: fresh consecutive failures → down tier
    for _ in range(3):
        mh.record_model_outcome(dead, "ep", ok=False)

    # demoted-ish: mixed history, ratio high but no recent streak
    for i in range(6):
        ok = 0 if i < 5 else 1
        ts = (now - timedelta(minutes=40 - i)).isoformat(timespec="seconds")
        import sqlite3

        conn = sqlite3.connect(tracker_db)
        conn.execute(
            "INSERT INTO model_health_events (ts, model_ref, endpoint, ok, latency_ms, kind) VALUES (?, ?, 'ep', ?, 0, 'x')",
            (ts, demotedish, ok),
        )
        conn.commit()
        conn.close()

    ranked = mh.rank_candidates([(dead, 1), (demotedish, 2), (healthy, 3)])
    order = [m for m, _p in ranked]
    assert order[0] == healthy
    assert order[-1] == dead


# =========================================================================
# prioritizer round-robin
# =========================================================================
def test_rr_rotates_to_next_candidate_on_failure(temp_db, monkeypatch):
    """After a failing batch, the next batch uses a DIFFERENT endpoint/model."""
    from agents.prioritizer_worker import PrioritizerWorker

    w = PrioritizerWorker()
    used = []

    def fake_batch(batch):
        used.append(w._rr_override or "default")
        return False  # always fail → forces rotation each time

    monkeypatch.setattr(w, "_categorize_batch", fake_batch)

    refs = iter(["primary/m-a", "secondary/m-b", "primary/m-c"])

    def fake_next():
        w._rr_override = next(refs)
        return w._rr_override

    monkeypatch.setattr(w, "_rr_next_model", fake_next)
    monkeypatch.setattr(w, "_get_all_feedback", lambda: [])
    items = [type("F", (), {"category": "uncategorized"})() for _ in range(90)]

    # Patch cycle pieces we don't care about here.
    monkeypatch.setattr(w, "_filter_low_quality_feedback", lambda it: (it, 0))
    monkeypatch.setattr(w, "_score_within_categories", lambda it: {})
    monkeypatch.setattr(w, "_cross_category_ranking", lambda sc: [])
    monkeypatch.setattr(w, "_post_results", lambda r: None)
    monkeypatch.setattr("agents.prioritizer_worker.time.sleep", lambda s: None)

    w._categorize_feedback(items)
    assert len(used) == 3  # breaker stops after 3 consecutive failures
    assert len(set(used)) >= 2  # ...but on different models, not the same one


def test_rr_skips_down_models_via_ranking(tracker_db, monkeypatch):
    """Rotation lands on the healthy sibling when wrapping to same endpoint."""
    from agents.prioritizer_worker import PrioritizerWorker

    # ep/a has two models; m1 just failed twice → down. m2 untouched.
    for _ in range(2):
        mh.record_model_outcome("ep/a/m-down", "ep/a", ok=False)

    class FakeEP:
        def __init__(self, name, priority):
            self.name = name
            self.priority = priority

    class FakeMgr:
        endpoints: typing.ClassVar[dict] = {"ep/a": FakeEP("ep/a", 10), "ep/b": FakeEP("ep/b", 20)}
        models: typing.ClassVar[dict] = {"ep/a/m-down": {}, "ep/a/m-sib": {}, "ep/b/m-other": {}}

        def get_available_endpoints(self):
            return list(self.endpoints.values())

    class FakeCfg:
        def get(self, _k, d=None):
            return d

    import agents.prioritizer_worker as pw
    import core.endpoint_manager as cem

    monkeypatch.setattr(cem, "get_endpoint_manager", lambda: FakeMgr())
    monkeypatch.setattr(pw, "get_config", lambda: FakeCfg())

    w = PrioritizerWorker()
    picks = {w._rr_next_model() for _ in range(3)}
    assert "ep/a/m-down" not in picks  # down model never surfaces while up alternatives exist
    assert picks <= {"ep/a/m-sib", "ep/b/m-other"}
