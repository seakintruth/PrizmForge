"""
tests/unit/test_token_modules.py

Tests for token estimation and budgeting logic.
"""

import pytest
import tempfile
import os
from core.token_estimator import estimate_tokens, estimate_messages
from core.token_budget import TokenBudget


class TestTokenEstimator:
    """Tests for token estimation utilities."""

    def test_estimate_tokens_basic(self):
        text = "Hello world"
        tokens = estimate_tokens(text)
        assert isinstance(tokens, int)
        assert tokens > 0

    def test_estimate_tokens_longer_text(self):
        text = "This is a much longer piece of text that should consume more tokens."
        tokens = estimate_tokens(text)
        assert tokens > 5

    def test_estimate_messages(self):
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"}
        ]
        total = estimate_messages(messages)
        assert isinstance(total, int)
        assert total > 0


class TestTokenBudget:
    """Tests for TokenBudget (rolling 4-hour window with DB persistence)."""

    def test_token_budget_initialization(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            budget = TokenBudget(db_path=db_path, max_tokens_per_4h=1000000)
            assert budget.max_tokens == 1000000
            assert budget.get_used() == 0

    def test_token_budget_add_usage(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            budget = TokenBudget(db_path=db_path, max_tokens_per_4h=1000000)
            budget.add_usage(1500)
            assert budget.get_used() >= 1500

    def test_token_budget_can_spend(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            budget = TokenBudget(db_path=db_path, max_tokens_per_4h=10000)
            assert budget.can_spend(500) is True
            budget.add_usage(9000)
            assert budget.can_spend(2000) is False

    def test_token_budget_remaining(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            budget = TokenBudget(db_path=db_path, max_tokens_per_4h=5000)
            budget.add_usage(1200)
            remaining = budget.remaining()
            assert remaining > 0
            assert remaining <= 5000
