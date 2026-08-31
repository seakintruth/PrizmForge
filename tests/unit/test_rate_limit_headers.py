"""
Rate-limit header classifier: burst vs. daily-quota (OpenRouter).

Covers parse_reset_to_epoch (ms epochs, seconds epochs, relative seconds) and
classify_rate_limit (Remaining == 0, Reset present, body keywords).
"""

from __future__ import annotations

import time

import pytest

from core.rate_limit_headers import classify_rate_limit, parse_reset_to_epoch


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
