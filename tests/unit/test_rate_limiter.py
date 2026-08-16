"""Unit coverage for core.rate_limiter — including mocked-time cooldown path."""

from __future__ import annotations

import threading
import time
from unittest.mock import patch

from core.rate_limiter import RateLimiter


def test_rate_limiter_basic_no_wait():
    limiter = RateLimiter(max_calls_per_minute=60)
    start = time.time()
    limiter.wait_if_needed()
    assert time.time() - start < 0.1
    assert len(limiter.calls) == 1


def test_rate_limiter_per_endpoint_isolation():
    limiter = RateLimiter(max_calls_per_minute=60)
    limiter.wait_if_needed("openai")
    limiter.wait_if_needed("anthropic")
    assert "openai" in limiter.endpoint_calls
    assert "anthropic" in limiter.endpoint_calls
    assert len(limiter.endpoint_calls["openai"]) == 1
    assert len(limiter.endpoint_calls["anthropic"]) == 1
    # Global deque is separate from per-endpoint
    assert len(limiter.calls) == 0


def test_rate_limiter_multiple_calls():
    limiter = RateLimiter(max_calls_per_minute=1000)
    for _ in range(5):
        limiter.wait_if_needed()
    assert len(limiter.calls) == 5


def test_rate_limiter_thread_safety():
    limiter = RateLimiter(max_calls_per_minute=1000)
    errors: list[Exception] = []

    def worker():
        try:
            for _ in range(10):
                limiter.wait_if_needed()
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    assert len(limiter.calls) == 30


def test_set_max_calls():
    limiter = RateLimiter(max_calls_per_minute=60)
    limiter.set_max_calls(30)
    assert limiter.max_calls == 30


def test_global_limit_triggers_sleep_with_mocked_time():
    """When the window is full, wait_if_needed must sleep then record the call."""
    limiter = RateLimiter(max_calls_per_minute=2)
    # Seed two calls at t=1000
    limiter.calls.append(1000.0)
    limiter.calls.append(1000.5)

    sleeps: list[float] = []

    def fake_sleep(seconds: float):
        sleeps.append(seconds)

    # Now is only 10s later → both calls still in the 60s window
    with patch("core.rate_limiter.time.time", return_value=1010.0):
        with patch("core.rate_limiter.time.sleep", side_effect=fake_sleep):
            # After sleep, advance time so the next loop iteration succeeds
            call_count = {"n": 0}

            def advancing_time():
                call_count["n"] += 1
                # First few reads while deciding to sleep stay at 1010;
                # after sleep, jump past the window so the append succeeds.
                if sleeps:
                    return 1061.0
                return 1010.0

            with patch("core.rate_limiter.time.time", side_effect=advancing_time):
                limiter.wait_if_needed()

    assert len(sleeps) >= 1
    assert sleeps[0] > 0
    # Call was recorded after the wait
    assert len(limiter.calls) == 3


def test_old_calls_evicted_from_window():
    """Calls older than 60s must be dropped before counting."""
    limiter = RateLimiter(max_calls_per_minute=2)
    limiter.calls.append(1000.0)  # will be >60s old
    limiter.calls.append(1000.5)

    with patch("core.rate_limiter.time.time", return_value=1070.0):  # +70s
        with patch("core.rate_limiter.time.sleep") as slept:
            limiter.wait_if_needed()
            slept.assert_not_called()

    # Old entries popped; only the new call remains (or new + any still in window)
    assert len(limiter.calls) >= 1
    assert all(t >= 1010.0 for t in limiter.calls)


def test_per_endpoint_uses_config_limit(monkeypatch):
    """Per-endpoint path reads rate_limit_per_minute from config."""
    from core import config as config_mod

    monkeypatch.setattr(
        config_mod,
        "get_config",
        lambda: {
            "endpoints": {
                "slow": {"rate_limit_per_minute": 1},
            }
        },
    )

    limiter = RateLimiter(max_calls_per_minute=1000)
    limiter.endpoint_calls["slow"] = __import__("collections").deque([1000.0])

    sleeps: list[float] = []

    def fake_sleep(s: float):
        sleeps.append(s)

    call_n = {"n": 0}

    def advancing_time():
        call_n["n"] += 1
        if sleeps:
            return 1061.0
        return 1010.0

    with patch("core.rate_limiter.time.time", side_effect=advancing_time):
        with patch("core.rate_limiter.time.sleep", side_effect=fake_sleep):
            limiter.wait_if_needed("slow")

    assert len(sleeps) >= 1
    assert len(limiter.endpoint_calls["slow"]) >= 1
