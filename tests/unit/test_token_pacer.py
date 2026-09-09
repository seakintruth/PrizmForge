"""TokenPacer: per-endpoint token send-rate pacing (Soak17 §11.3).

Covers budget-coverage vs. deficit behavior, refill over elapsed time, the
sleep cap for pathological budgets, and state refresh.
"""

from __future__ import annotations

import pytest

from core.token_pacer import PACER_MAX_SLEEP, TokenPacer


def test_no_budget_returns_zero_and_does_not_consume():
    p = TokenPacer("generic")
    assert p.acquire(1000) == 0.0


def test_budget_coverage_consumes_without_sleep():
    p = TokenPacer("coverage", limit=100000, remaining=5000, measured_at=100.0)
    assert p.acquire(1000, now=100.0) == 0.0
    assert p.remaining == pytest.approx(4000.0)


def test_deficit_sleeps_refill_time():
    # 60 tokens at 600/min (10/s) need 6s of refill.
    p = TokenPacer("deficit", limit=600, remaining=0, measured_at=100.0)
    assert p.acquire(60, now=100.0) == pytest.approx(6.0)


def test_refill_over_elapsed_time_avoids_sleep():
    # 60s elapsed refills the whole 600-token bucket: no sleep needed.
    p = TokenPacer("refill", limit=600, remaining=0, measured_at=100.0)
    assert p.acquire(600, now=160.0) == 0.0
    assert p.remaining == pytest.approx(0.0)


def test_cap_limits_huge_sleeps():
    p = TokenPacer("cap", limit=1000, remaining=0, measured_at=100.0)
    assert p.acquire(1_000_000, now=100.0) == pytest.approx(PACER_MAX_SLEEP)


def test_update_refreshes_budget():
    p = TokenPacer("update")
    p.update(500000, 1234, measured_at=200.0)
    assert p.limit == 500000
    assert p.remaining == pytest.approx(1234.0)
    assert p.acquire(100, now=200.0) == 0.0


def test_reset_drops_state():
    p = TokenPacer("reset", limit=100, remaining=0, measured_at=1.0)
    assert p.acquire(1, now=1.0) > 0.0
    p.reset()
    assert p.acquire(1, now=1.0) == 0.0
