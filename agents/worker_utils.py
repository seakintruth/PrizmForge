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
    """Wait out an active foreground session; return whether the caller should continue.

    Probes every 5s so ``stop()`` is still responsive. No-ops immediately when
    no foreground session is active.
    """
    while is_running() and foreground_session_active():
        interruptible_sleep(5, is_running)
    return is_running()
