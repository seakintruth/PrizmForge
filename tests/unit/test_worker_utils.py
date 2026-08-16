"""interruptible_sleep must honor the running predicate."""

from __future__ import annotations

import time

from agents.worker_utils import interruptible_sleep


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
