"""Parse provider 429 rate-limit headers to classify burst vs. quota exhaustion.

OpenRouter's `free-models-per-day` bucket reports `X-RateLimit-Limit/Remaining/
Reset` with a Reset epoch in milliseconds (midnight UTC). A 429 with
`Remaining: 0` and a Reset header is a *daily quota*, not a short burst — short
Retry-After hops just bounce off an empty bucket until the reset. This module
normalizes those headers so `call_endpoint` can park a quota-exhausted endpoint
instead of sleeping 3x60s on an empty window.
"""

from __future__ import annotations

import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast

# A Reset value above this is milliseconds (OpenRouter ms epochs, ~2001 in s).
_MS_THRESHOLD = 1_000_000_000_000
# An absolute seconds epoch is always >= 2001; smaller values are relative counts.
_EPOCH_FLOOR = 1_000_000_000

_REMAINING_KEYS = ("x-ratelimit-remaining", "ratelimit-remaining")
_RESET_KEYS = ("x-ratelimit-reset", "ratelimit-reset")

_QUOTA_BODY_TOKENS = ("free-models-per-day", "add 10 credits", "daily quota")


@dataclass
class RateLimitInfo:
    """Classification of a 429 response."""

    is_quota: bool
    remaining: int | None
    reset_epoch: float | None
    body_quota: bool


def parse_reset_to_epoch(value: object, *, now: float | None = None) -> float | None:
    """Convert an ``X-RateLimit-Reset`` value to a unix epoch (seconds).

    Handles OpenRouter ms epochs (> 1e12), absolute seconds epochs (>= 1e9),
    and small relative-seconds counts (reset in N seconds -> now + N). Returns
    None when the value is missing or cannot be parsed.
    """
    if value is None:
        return None
    try:
        n = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    now = time.time() if now is None else now
    if n > _MS_THRESHOLD:
        return n / 1000.0
    if n >= _EPOCH_FLOOR:
        return n
    return now + n


def classify_rate_limit(headers: object, body_text: str = "") -> RateLimitInfo:
    """Classify a 429 response into quota vs. burst.

    Quota when either:
      * the Remaining header is present and <= 0, or
      * the body mentions ``free-models-per-day`` / ``Add 10 credits`` / ``daily quota``.

    A Reset header alone is not quota (burst windows also send Reset).
    Everything else is a burst and keeps the short Retry-After backoff.
    """
    if headers is None:
        norm: dict[str, str] = {}
    else:
        norm = {str(k).lower(): str(v) for k, v in cast("Mapping[object, object]", headers).items()}

    remaining: int | None = None
    for key in _REMAINING_KEYS:
        raw = norm.get(key)
        if raw is None:
            continue
        try:
            remaining = int(float(raw))
        except (TypeError, ValueError):
            remaining = None
        break

    reset_epoch: float | None = None
    for key in _RESET_KEYS:
        reset_epoch = parse_reset_to_epoch(norm.get(key))
        if reset_epoch is not None:
            break

    body_lower = (body_text or "").lower()
    body_quota = any(token in body_lower for token in _QUOTA_BODY_TOKENS)

    is_quota = (remaining is not None and remaining <= 0) or body_quota
    return RateLimitInfo(
        is_quota=is_quota,
        remaining=remaining,
        reset_epoch=reset_epoch,
        body_quota=body_quota,
    )
