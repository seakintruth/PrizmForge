"""Per-endpoint token send-rate pacing driven by x-ratelimit-*-tokens-* headers.

Soak17 §11.3: a parallel large prompt (one reviewer prompt was 183k+ chars) can
re-trigger a per-minute token-bucket 429 storm even when ``Retry-After`` is
honored on each reply. The pacer throttles the client send-rate against the last
discovered per-minute budget: each ``acquire()`` sleeps only the deficit needed
to refill at ``limit`` tokens/minute, bounded so a single huge prompt never
stalls the process forever.
"""

from __future__ import annotations

import time

# Never let one prompt stall the caller more than this many seconds waiting for
# tokens. A 183k-char prompt (~46k tokens) against a 500k/min bucket is a ~6s
# refill; the cap only matters for pathological budgets.
PACER_MAX_SLEEP = 60.0

_REFILL_PER_SECOND_FACTOR = 1.0 / 60.0


class TokenPacer:
    """One per-endpoint token bucket, refilling at ``limit`` tokens/minute.

    State is process-local (mirrors the RateLimiter); the discovered budget is
    also persisted to endpoint health so it survives restarts and is visible to
    the whole process.
    """

    def __init__(
        self,
        endpoint_name: str,
        limit: int | None = None,
        remaining: int | None = None,
        measured_at: float | None = None,
    ):
        self.endpoint_name = endpoint_name
        self.limit = limit
        self.remaining: float | None = float(remaining) if remaining is not None else None
        self.measured_at = measured_at

    def update(self, limit: int | None, remaining: int | None, measured_at: float | None = None) -> None:
        """Record the budget the server just advertised on any response."""
        if limit is not None:
            self.limit = limit
        if remaining is not None:
            self.remaining = float(remaining)
        self.measured_at = time.time() if measured_at is None else measured_at

    def reset(self) -> None:
        """Drop all budget state (e.g. after a latch expires)."""
        self.limit = None
        self.remaining = None
        self.measured_at = None

    def _available_tokens(self, now: float) -> float | None:
        if not self.limit or self.remaining is None or self.measured_at is None:
            return None
        elapsed = max(0.0, now - self.measured_at)
        refilled = self.remaining + elapsed * float(self.limit) * _REFILL_PER_SECOND_FACTOR
        return min(float(self.limit), refilled)

    def acquire(self, tokens: int, *, now: float | None = None) -> float:
        """Sleep the deficit so ``tokens`` fit the per-minute bucket.

        Returns the seconds actually slept (0 when no budget is known yet, the
        bucket already covers the request, or the deficit is capped). Consumes
        tokens from the bucket on success.
        """
        if tokens <= 0 or not self.limit:
            return 0.0
        now = time.time() if now is None else now
        available = self._available_tokens(now)
        if available is None:
            return 0.0

        if available >= tokens:
            self.measured_at = now
            self.remaining = min(float(self.limit), max(0.0, available - tokens))
            return 0.0

        deficit = tokens - available
        refill_s = deficit * 60.0 / float(self.limit)
        sleep_s = min(refill_s, PACER_MAX_SLEEP)
        if sleep_s <= 0:
            return 0.0
        self.measured_at = now + sleep_s
        self.remaining = min(float(self.limit), max(0.0, available + sleep_s * float(self.limit) * _REFILL_PER_SECOND_FACTOR - tokens))
        return sleep_s
