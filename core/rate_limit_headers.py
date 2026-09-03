"""Parse provider 429 rate-limit headers to classify burst vs. quota exhaustion.

OpenRouter's `free-models-per-day` bucket reports `X-RateLimit-Limit/Remaining/
Reset` with a Reset epoch in milliseconds (midnight UTC). A 429 with
`Remaining: 0` and a Reset header is a *daily quota*, not a short burst — short
Retry-After hops just bounce off an empty bucket until the reset. This module
normalizes those headers so `call_endpoint` can park a quota-exhausted endpoint
instead of sleeping 3x60s on an empty window.
"""

from __future__ import annotations

import email.utils
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

# The 600 s ceiling (10 minutes). Advertised waits above this trip the
# "cooldown too long -> fallback now" branch instead of a long in-process sleep.
MAX_ADVERTISED_WAIT = 600

# Default wait when the header/body is missing or unparseable (ROADMAP §0.0
# decision table): 429 -> 120 s, 503 -> 300 s.
DEFAULT_STATUS_WAIT = {429: 120, 503: 300}

_QUOTA_BODY_TOKENS = (
    "free-models-per-day",
    "add 10 credits",
    "daily quota",
    # Provider error types that are quota exhaustion, not a transient burst.
    "freeusagelimiterror",
)


def advertised_wait_seconds(
    status: int,
    headers: object,
    body_text: str = "",
    *,
    now: float | None = None,
    max_wait: int = MAX_ADVERTISED_WAIT,
) -> int | None:
    """Return the advertised retry wait in seconds for a 429/503 response.

    Resolution order (ROADMAP §0.3):
      1. ``Retry-After`` header (delta-seconds or HTTP-date).
      2. JSON ``error.retry_after_seconds`` in the body.
      3. Status default (429 -> 120 s, 503 -> 300 s).

    Returns the raw advertised value clamped into ``[1, max_wait]``, or ``None``
    when the wait is missing/unparseable and there is no status default. Values
    strictly above ``max_wait`` are returned un-clamped so the caller can
    distinguish "honor this wait" from "too long -> fallback now".
    """
    delta = _parse_retry_after_header(headers, now=now)
    if delta is not None:
        return delta if delta > max_wait else max(1, delta)

    body_delta = _parse_body_retry_after(body_text)
    if body_delta is not None:
        return body_delta if body_delta > max_wait else max(1, body_delta)

    default = DEFAULT_STATUS_WAIT.get(status)
    if default is not None:
        return max(1, default)
    return None


def _parse_retry_after_header(headers: object, *, now: float | None = None) -> int | None:
    if headers is None:
        return None
    raw = None
    for key, value in cast("Mapping[object, object]", headers).items():
        if str(key).lower() == "retry-after":
            raw = str(value)
            break
    if raw is None:
        return None
    raw = raw.strip()
    if not raw:
        return None
    now = time.time() if now is None else now
    try:
        return max(1, int(float(raw)))
    except (TypeError, ValueError):
        pass
    try:
        parsed = email.utils.parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        return None
    if parsed is None:
        return None
    return max(1, int(parsed.timestamp() - now))


def _parse_body_retry_after(body_text: str) -> int | None:
    if not body_text:
        return None
    try:
        body = cast(dict, __import__("json").loads(body_text))
    except Exception:
        return None
    error = body.get("error")
    if not isinstance(error, dict):
        return None
    value = error.get("retry_after_seconds")
    if value is None:
        return None
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return None


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
      * the body mentions ``free-models-per-day`` / ``Add 10 credits`` / ``daily quota``,
        or an ``error.type`` of ``FreeUsageLimitError`` (provider daily cap).

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
