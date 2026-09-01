"""
Rate-limit header classifier: burst vs. daily-quota (OpenRouter).

Covers parse_reset_to_epoch (ms epochs, seconds epochs, relative seconds) and
classify_rate_limit (Remaining == 0, Reset present, body keywords).
"""

from __future__ import annotations

import time

import pytest

from core.rate_limit_headers import (
    advertised_wait_seconds,
    classify_rate_limit,
    parse_reset_to_epoch,
)


def test_parse_ms_epoch_reset():
    assert parse_reset_to_epoch("1788134400000", now=1788133000.0) == pytest.approx(1788134400.0)


def test_parse_seconds_epoch_reset():
    assert parse_reset_to_epoch("1788134400", now=0.0) == 1788134400.0


def test_parse_relative_seconds_reset():
    assert parse_reset_to_epoch("30", now=1000.0) == 1030.0


def test_parse_invalid_reset_returns_none():
    assert parse_reset_to_epoch("abc", now=0.0) is None
    assert parse_reset_to_epoch("", now=0.0) is None
    assert parse_reset_to_epoch(None, now=0.0) is None


def test_burst_when_remaining_positive_no_reset():
    info = classify_rate_limit({"X-RateLimit-Limit": "50", "X-RateLimit-Remaining": "30"})
    assert info.is_quota is False
    assert info.remaining == 30
    assert info.reset_epoch is None
    assert info.body_quota is False


def test_quota_when_remaining_zero():
    info = classify_rate_limit({"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1788134400000"})
    assert info.is_quota is True


def test_reset_header_alone_is_not_quota():
    info = classify_rate_limit({"X-RateLimit-Reset": "30"})
    assert info.is_quota is False
    assert info.reset_epoch == pytest.approx(time.time() + 30, abs=5)


def test_quota_via_body_tokens_without_headers():
    body = '{"error": {"code": 429, "message": "free-models-per-day. Add 10 credits to unlock."}}'
    info = classify_rate_limit({"Content-Type": "application/json"}, body_text=body)
    assert info.is_quota is True
    assert info.body_quota is True
    assert info.remaining is None
    assert info.reset_epoch is None


def test_headers_case_insensitive():
    info = classify_rate_limit({"X-RATELIMIT-REMAINING": "0", "X-RATELIMIT-RESET": "45"})
    assert info.is_quota is True
    assert info.remaining == 0


def test_non_dict_like_headers_safe():
    info = classify_rate_limit(None)
    assert info.is_quota is False
    assert info.remaining is None


def test_advertised_wait_from_retry_after_header():
    assert advertised_wait_seconds(503, {"Retry-After": "90"}) == 90


def test_advertised_wait_from_retry_after_http_date():
    # HTTP-date Retry-After within the window is honored.
    later = time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime(time.time() + 45))
    wait = advertised_wait_seconds(503, {"Retry-After": later}, now=time.time())
    assert 40 <= wait <= 45


def test_advertised_wait_from_body_retry_after_seconds():
    body = '{"error": {"retry_after_seconds": 30}}'
    assert advertised_wait_seconds(503, {}, body_text=body) == 30


def test_advertised_wait_status_defaults():
    # 429 -> 120s, 503 -> 300s when nothing is advertised.
    assert advertised_wait_seconds(429, {}) == 120
    assert advertised_wait_seconds(503, {}) == 300


def test_advertised_wait_unparseable_uses_status_default():
    assert advertised_wait_seconds(429, {"Retry-After": "abc"}) == 120


def test_advertised_wait_above_max_returned_uncapped():
    # Values above the cap are returned un-clamped so the caller can branch to
    # "cooldown too long -> fallback now".
    assert advertised_wait_seconds(429, {"Retry-After": "42534"}) == 42534
    assert advertised_wait_seconds(503, {"Retry-After": "601"}) == 601


def test_advertised_wait_unknown_status_returns_none():
    assert advertised_wait_seconds(500, {}) is None
    assert advertised_wait_seconds(200, {}) is None


def test_advertised_wait_clamps_min_to_one():
    assert advertised_wait_seconds(429, {"Retry-After": "0"}) == 1
    assert advertised_wait_seconds(503, {"Retry-After": "-5"}) == 1
