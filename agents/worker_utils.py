"""Shared helpers for background agent workers."""

from __future__ import annotations

import time
from collections.abc import Callable


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
