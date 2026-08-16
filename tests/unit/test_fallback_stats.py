"""Endpoint fallback logging and aggregate stats."""

from __future__ import annotations


def test_log_and_get_fallback_stats(temp_db):
    from core.fallback_stats import get_fallback_stats, log_fallback

    log_fallback(
        original_endpoint="gemini",
        fallback_endpoint="openai",
        reason="rate_limit",
        task_id="t_fb",
        agent_name="developer",
    )
    log_fallback(
        original_endpoint="gemini",
        fallback_endpoint="openai",
        reason="timeout",
        task_id="t_fb",
        agent_name="reviewer",
    )

    stats = get_fallback_stats()
    assert stats["total"] >= 2
    assert "rate_limit" in stats["by_reason"] or stats["by_reason"]
    assert "gemini" in stats["by_endpoint"]
    assert len(stats["recent"]) >= 1
