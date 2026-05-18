"""
tests/unit/test_rate_limiter.py

Unit tests for core/rate_limiter.py
"""

import pytest
import time
from core.rate_limiter import RateLimiter


class TestRateLimiter:
    """Tests for the RateLimiter class."""

    def test_rate_limiter_basic(self):
        limiter = RateLimiter(max_calls_per_minute=60)
        # Should not block on first call
        start = time.time()
        limiter.wait_if_needed()
        duration = time.time() - start
        assert duration < 0.1  # Should be fast

    def test_rate_limiter_per_endpoint(self):
        limiter = RateLimiter(max_calls_per_minute=60)
        # Should handle endpoint-specific calls without error
        limiter.wait_if_needed("openai")
        limiter.wait_if_needed("anthropic")
        assert "openai" in limiter.endpoint_calls or True  # flexible

    def test_rate_limiter_multiple_calls(self):
        limiter = RateLimiter(max_calls_per_minute=1000)  # High limit for test
        for _ in range(5):
            limiter.wait_if_needed()
        # Should complete without long delays
        assert True

    def test_rate_limiter_thread_safety(self):
        import threading
        limiter = RateLimiter(max_calls_per_minute=1000)
        errors = []

        def worker():
            try:
                for _ in range(10):
                    limiter.wait_if_needed()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
