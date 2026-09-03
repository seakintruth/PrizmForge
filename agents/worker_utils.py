"""Shared helpers for background agent workers."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from contextlib import contextmanager


def interruptible_sleep(
    seconds: float,
    is_running: Callable[[], bool],
    *,
    slice_s: float = 0.25,
) -> None:
    """Sleep up to ``seconds`` while ``is_running()`` remains true.

    Breaks sleep into short slices so ``stop()`` can set ``running = False``
    and ``join(timeout=...)`` completes without waiting out a 30-300s sleep.
    """
    if seconds <= 0:
        return
    end = time.monotonic() + float(seconds)
    while is_running() and time.monotonic() < end:
        remaining = end - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(slice_s, remaining))


# ---------------------------------------------------------------------------
# c9 (soak recompute, 2026-08-29): foreground developer sessions starved on the
# rate-limited endpoint because support workers (prioritizer, archivist,
# reporter) kept running full LLM cycles mid-session (W6 lane isolation only
# paused feedback agents). These workers now hold off for the duration.
# ---------------------------------------------------------------------------

_foreground_counter = 0
_foreground_lock = threading.Lock()


def foreground_session_active() -> bool:
    """True while a foreground (developer) session is running."""
    with _foreground_lock:
        return _foreground_counter > 0


def begin_foreground_session() -> None:
    global _foreground_counter
    with _foreground_lock:
        _foreground_counter += 1


def end_foreground_session() -> None:
    global _foreground_counter
    with _foreground_lock:
        _foreground_counter = max(_foreground_counter - 1, 0)


@contextmanager
def foreground_session_guard():
    """Hold background-support LLM cycles while a foreground session runs.

    Nested sessions are tracked with a counter; ending only releases when the
    outermost session finishes.
    """
    begin_foreground_session()
    try:
        yield
    finally:
        end_foreground_session()


def hold_while_foreground_session_active(is_running: Callable[[], bool]) -> bool:
    """Wait out an active foreground session or a latched-all transport; return continuation.

    Probes every 5s so ``stop()`` is still responsive. No-ops immediately when
    neither a foreground session is active nor the shared transport is frozen
    (§6.3: all configured endpoints latched => support workers hold so they do
    not burn the last quota carries; orchestrator/developer keep working).
    """
    while is_running() and (foreground_session_active() or support_frozen()):
        interruptible_sleep(5, is_running)
    return is_running()


# ---------------------------------------------------------------------------
# §6.3 (soak-derived): when every configured endpoint is latched, freeze
# background support workers (prioritizer/archivist/reporter) so a frozen
# endpoint cannot burn the last remaining quota carries. The latch path
# flips this flag via set_support_frozen(); hold_while_foreground_session_active
# (used by the support-worker loops) then waits until any endpoint recovers.
# ---------------------------------------------------------------------------

_frozen_lock = threading.Lock()
_support_frozen = False


def support_frozen() -> bool:
    """True while the shared transport is frozen (all endpoints latched)."""
    with _frozen_lock:
        return _support_frozen


def set_support_frozen(frozen: bool) -> None:
    """Freeze (True) or resume (False) background support workers globally."""
    global _support_frozen
    with _frozen_lock:
        _support_frozen = bool(frozen)


# ---------------------------------------------------------------------------
# f9 (soak recompute, 2026-08-29): one rate-limited endpoint produced 275 HIGH
# "failed to return a response" rows (prioritizer alone 173) — one per call.
# Background pools (prioritizer/archivist/reviewers) hit the per-call logging
# path directly; the episode guard lives only in the sequential runner.
# ---------------------------------------------------------------------------


class TransportErrorCoalescer:
    """Collapse per-call transport failures into ONE HIGH per window-episode.

    Keyed by (agent, category); the first failure in a window logs HIGH and
    repeats inside the window log MEDIUM, so a throttled endpoint no longer
    floods the errors table at top severity while single glitches stay visible.
    """

    def __init__(self, window_seconds: float = 300.0):
        self.window_seconds = float(window_seconds)
        self._lock = threading.Lock()
        self._first_high: dict[tuple[str, str], float] = {}

    def classify(self, agent_name: str, category: str) -> str:
        key = (agent_name, category)
        now = time.time()
        with self._lock:
            first = self._first_high.get(key)
            if first is None or now - first >= self.window_seconds:
                self._first_high[key] = now
                return "HIGH"
            return "MEDIUM"

    def clear_for(self, agent_name: str) -> None:
        with self._lock:
            self._first_high = {k: v for k, v in self._first_high.items() if k[0] != agent_name}


_transport_error_coalescer = TransportErrorCoalescer()


def classify_transport_severity(agent_name: str, category: str) -> str:
    """Shared per-process coalescer for the background-worker transport path."""
    return _transport_error_coalescer.classify(agent_name, category)
