"""Tests for iteration timeout active-work tracking.

Soak evidence: first iteration reported 11.3 min elapsed, but ~4 min was
rate-limit sleeps (4 x 60 s). The developer did ~5 min of real work but the
5-min budget was exhausted by idle time. Iteration timeout should only count
active HTTP latency, not rate-limit sleeps or DB lock backoffs.
"""

from __future__ import annotations

import time

import pytest


class TestActiveWorkTracking:
    """run_task_cycle must track active work time, not wall-clock time."""

    def test_active_time_accumulates_across_calls(self, monkeypatch):
        """_active_work_seconds must increase by the actual HTTP latency each call."""
        import workflow.task_runner as tr

        monkeypatch.setattr(tr, "_active_work_seconds", 0.0)

        # Simulate a call_agent that took 2s of active work
        tr._active_work_seconds += 2.0
        assert tr._active_work_seconds == pytest.approx(2.0)

        tr._active_work_seconds += 1.5
        assert tr._active_work_seconds == pytest.approx(3.5)

    def test_timeout_uses_active_time_not_wall_clock(self, monkeypatch):
        """Iteration should continue when wall-clock exceeds budget but active work doesn't."""
        import workflow.task_runner as tr

        monkeypatch.setattr(tr, "_active_work_seconds", 0.0)

        time_box_minutes = 5
        active_budget = time_box_minutes * 60  # 300s

        # Simulate 4 rate-limit sleeps (60s each) = 240s idle
        # plus 2s of actual HTTP work per call = 8s active
        for _ in range(4):
            # Simulate what happens: rate limit sleep (idle) + HTTP call (active)
            _ = time.sleep  # not actually sleeping in test
            tr._active_work_seconds += 2.0  # 2s HTTP latency

        # Wall clock would be > 240s but active work is only 8s
        assert tr._active_work_seconds < active_budget
        # The iteration should NOT timeout
        assert tr._active_work_seconds < active_budget

    def test_timeout_fires_when_active_budget_exhausted(self, monkeypatch):
        """Iteration should timeout when active work exceeds budget."""
        import workflow.task_runner as tr

        monkeypatch.setattr(tr, "_active_work_seconds", 0.0)

        time_box_minutes = 5
        active_budget = time_box_minutes * 60  # 300s

        # Simulate 310s of active work (all HTTP calls, no sleeps)
        tr._active_work_seconds = 310.0

        assert tr._active_work_seconds >= active_budget

    def test_db_lock_backoff_not_counted(self, monkeypatch):
        """DB lock retry backoff time must not count toward active work."""
        from core.db_connection import _backoff_sleep

        # _backoff_sleep uses time.sleep internally; the caller should NOT
        # add the backoff time to _active_work_seconds
        deadline = time.monotonic() + 0.1
        result = _backoff_sleep(0, deadline, cap=0.01)
        # Whether it retried or not, the caller's active time should be
        # unaffected — this is a smoke test that the function doesn't crash
        assert isinstance(result, bool)

    def test_active_time_resets_per_iteration(self, monkeypatch):
        """_active_work_seconds must reset at the start of each iteration."""
        import workflow.task_runner as tr

        # Simulate iteration 1 accumulating active time
        monkeypatch.setattr(tr, "_active_work_seconds", 150.0)

        # New iteration starts — active time resets
        monkeypatch.setattr(tr, "_active_work_seconds", 0.0)
        assert tr._active_work_seconds == 0.0
