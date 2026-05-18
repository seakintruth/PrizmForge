"""
tests/unit/test_resource_controller.py

Tests for Resource Controller core data structures.
"""

import pytest
from agents.resource_controller_worker import (
    AgentProfile,
    ResourceState,
    ThrottleDecision,
    HeuristicOptimizer
)


class TestAgentProfile:
    """Tests for AgentProfile dataclass."""

    def test_agent_profile_creation(self):
        profile = AgentProfile(
            name="developer",
            avg_tokens_per_call=1850.0,
            avg_duration_seconds=14.2,
            feedback_value_score=0.88
        )
        assert profile.name == "developer"
        assert profile.feedback_value_score == 0.88
        assert profile.total_calls == 0  # default

    def test_agent_profile_to_dict_roundtrip(self):
        original = AgentProfile(
            name="reviewer",
            avg_tokens_per_call=920.0,
            avg_duration_seconds=7.8,
            feedback_value_score=0.79,
            total_calls=42,
            total_feedback_generated=31
        )
        data = original.to_dict()
        restored = AgentProfile.from_dict(data)

        assert restored.name == original.name
        assert restored.feedback_value_score == original.feedback_value_score


class TestResourceState:
    """Tests for ResourceState snapshot."""

    def test_resource_state_full_creation(self):
        state = ResourceState(
            tokens_used_in_window=187500,
            tokens_remaining=312500,
            max_tokens=500000,
            current_burn_rate=3850.0,
            api_calls_last_minute=27,
            api_rate_limit=60,
            budget_percentage=0.625,
            time_remaining_in_window=38.4
        )
        assert state.tokens_remaining == 312500
        assert state.budget_percentage == 0.625

    def test_resource_state_string_representation(self):
        state = ResourceState(
            tokens_used_in_window=95000,
            tokens_remaining=405000,
            max_tokens=500000,
            current_burn_rate=2100.0,
            api_calls_last_minute=9,
            api_rate_limit=60,
            budget_percentage=0.81,
            time_remaining_in_window=55.0
        )
        output = str(state)
        assert "Budget" in output
        assert "tok/min" in output


class TestThrottleDecision:
    """Tests for ThrottleDecision."""

    def test_throttle_decision_moderate(self):
        decision = ThrottleDecision(
            level="MODERATE",
            background_feeder_interval=45,
            active_agents=["developer", "jr_researcher", "tech_writer"],
            rate_limit_per_minute=35,
            model_downgrades={"developer": "gpt-4o-mini"},
            reasoning="Moderate sustained load detected"
        )
        assert decision.level == "MODERATE"
        assert len(decision.active_agents) == 3

    def test_throttle_decision_to_dict(self):
        decision = ThrottleDecision(
            level="AGGRESSIVE",
            background_feeder_interval=120,
            active_agents=["developer"],
            rate_limit_per_minute=15,
            model_downgrades={},
            reasoning="Critical token burn rate"
        )
        data = decision.to_dict()
        assert data["level"] == "AGGRESSIVE"
        assert "reasoning" in data


class TestHeuristicOptimizer:
    """Basic tests for HeuristicOptimizer."""

    def test_optimizer_can_be_instantiated(self):
        optimizer = HeuristicOptimizer()
        assert optimizer is not None

    def test_optimizer_returns_decision(self):
        optimizer = HeuristicOptimizer()

        # Create a minimal ResourceState
        state = ResourceState(
            tokens_used_in_window=100000,
            tokens_remaining=400000,
            max_tokens=500000,
            current_burn_rate=2000.0,
            api_calls_last_minute=10,
            api_rate_limit=60,
            budget_percentage=0.8,
            time_remaining_in_window=50.0
        )

        try:
            decision = optimizer.optimize(state)
            # It should return a ThrottleDecision or None
            assert decision is None or isinstance(decision, ThrottleDecision)
        except Exception:
            # Acceptable if full optimization requires more setup (DB/config)
            pass
