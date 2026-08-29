"""interruptible_sleep must honor the running predicate, and the c9 foreground gate."""

from __future__ import annotations

import time

from agents.worker_utils import (
    TransportErrorCoalescer,
    begin_foreground_session,
    end_foreground_session,
    foreground_session_active,
    foreground_session_guard,
    hold_while_foreground_session_active,
    interruptible_sleep,
)


def test_interruptible_sleep_exits_early_when_stopped():
    flags = {"running": True}

    def stop_soon():
        time.sleep(0.15)
        flags["running"] = False

    import threading

    t = threading.Thread(target=stop_soon, daemon=True)
    t.start()
    start = time.monotonic()
    interruptible_sleep(5.0, lambda: flags["running"], slice_s=0.05)
    elapsed = time.monotonic() - start
    t.join(timeout=1.0)
    # Should not wait the full 5s
    assert elapsed < 2.0


def test_interruptible_sleep_zero_is_noop():
    start = time.monotonic()
    interruptible_sleep(0, lambda: True)
    assert time.monotonic() - start < 0.5


# ---------------------------------------------------------------------------
# c9 (soak recompute): a counter-based foreground session gate holds the
# support workers off the rate-limited endpoint during a developer session.
# ---------------------------------------------------------------------------


def test_foreground_gate_counter_semantics():
    try:
        assert not foreground_session_active()
        begin_foreground_session()
        assert foreground_session_active()
        begin_foreground_session()  # nested
        assert foreground_session_active()
        end_foreground_session()  # still one active
        assert foreground_session_active()
        end_foreground_session()
        assert not foreground_session_active()
    finally:
        while foreground_session_active():
            end_foreground_session()


def test_foreground_session_guard_cleans_up_on_return():
    try:
        assert not foreground_session_active()
        with foreground_session_guard():
            assert foreground_session_active()
        assert not foreground_session_active()
    finally:
        while foreground_session_active():
            end_foreground_session()


def test_foreground_session_guard_cleans_up_on_exception():
    try:
        assert not foreground_session_active()
        try:
            with foreground_session_guard():
                raise RuntimeError("boom")
        except RuntimeError:
            pass
        assert not foreground_session_active()
    finally:
        while foreground_session_active():
            end_foreground_session()


def test_hold_returns_immediately_when_no_foreground_session(monkeypatch):
    def explode(*_args, **_kwargs):
        raise AssertionError("should not sleep when gate is inactive")

    monkeypatch.setattr("agents.worker_utils.interruptible_sleep", explode)
    try:
        assert hold_while_foreground_session_active(lambda: True) is True
    finally:
        while foreground_session_active():
            end_foreground_session()


def test_hold_waits_while_foreground_active(monkeypatch):
    try:
        begin_foreground_session()
        monkeypatch.setattr(
            "agents.worker_utils.interruptible_sleep",
            lambda _seconds, is_running: end_foreground_session(),
        )
        assert hold_while_foreground_session_active(lambda: True) is True
    finally:
        while foreground_session_active():
            end_foreground_session()


def test_hold_breaks_when_stopped_during_hold(monkeypatch):
    flags = {"running": True}
    try:
        begin_foreground_session()

        def stop_simulating_sleep(_seconds, is_running):
            flags["running"] = False

        monkeypatch.setattr("agents.worker_utils.interruptible_sleep", stop_simulating_sleep)
        assert hold_while_foreground_session_active(lambda: flags["running"]) is False
    finally:
        while foreground_session_active():
            end_foreground_session()


# ---------------------------------------------------------------------------
# f9 (soak recompute): one HIGH per transport-failure window-episode for
# background agents (soak gave 275 HIGH rows from a single rate-limited
# endpoint, prioritizer alone 173).
# ---------------------------------------------------------------------------


def test_coalescer_first_high_then_medium_within_window():
    coalescer = TransportErrorCoalescer(window_seconds=300.0)
    assert coalescer.classify("prioritizer", "call_agent") == "HIGH"
    assert coalescer.classify("prioritizer", "call_agent") == "MEDIUM"
    assert coalescer.classify("prioritizer", "call_agent") == "MEDIUM"


def test_coalescer_agents_are_independent():
    coalescer = TransportErrorCoalescer(window_seconds=300.0)
    assert coalescer.classify("prioritizer", "call_agent") == "HIGH"
    assert coalescer.classify("archivist", "call_agent") == "HIGH"  # own episode
    assert coalescer.classify("prioritizer", "call_agent") == "MEDIUM"


def test_coalescer_new_episode_after_window_elapses():
    coalescer = TransportErrorCoalescer(window_seconds=0.01)
    assert coalescer.classify("prioritizer", "call_agent") == "HIGH"
    time.sleep(0.03)
    assert coalescer.classify("prioritizer", "call_agent") == "HIGH"  # new episode
    assert coalescer.classify("prioritizer", "call_agent") == "MEDIUM"


def test_coalescer_clear_for_resets_episode():
    coalescer = TransportErrorCoalescer(window_seconds=300.0)
    assert coalescer.classify("prioritizer", "call_agent") == "HIGH"
    coalescer.clear_for("prioritizer")
    assert coalescer.classify("prioritizer", "call_agent") == "HIGH"
