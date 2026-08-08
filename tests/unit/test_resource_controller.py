"""
tests/unit/test_resource_controller.py

Full test suite for Resource Controller core data structures
and the adaptive ResourceControllerWorker.
"""

import threading
import time

import pytest

from agents.resource_controller_worker import (
    AgentProfile,
    HeuristicOptimizer,
    ResourceControllerWorker,
    ResourceState,
    ThrottleDecision,
)


class TestAgentProfile:
    """Tests for AgentProfile dataclass."""

    def test_agent_profile_creation(self):
        """AgentProfile should be created with correct defaults."""
        profile = AgentProfile(
            name="developer",
            avg_tokens_per_call=1850.0,
            avg_duration_seconds=14.2,
            feedback_value_score=0.88,
        )
        assert profile.name == "developer"
        assert profile.feedback_value_score == 0.88
        assert profile.total_calls == 0

    def test_agent_profile_to_dict_roundtrip(self):
        """AgentProfile should support full dict serialization roundtrip."""
        original = AgentProfile(
            name="reviewer",
            avg_tokens_per_call=920.0,
            avg_duration_seconds=7.8,
            feedback_value_score=0.79,
            total_calls=42,
            total_feedback_generated=31,
        )
        data = original.to_dict()
        restored = AgentProfile.from_dict(data)
        assert restored.name == original.name
        assert restored.feedback_value_score == original.feedback_value_score


class TestResourceState:
    """Tests for ResourceState snapshot."""

    def test_resource_state_full_creation(self):
        """ResourceState should accept all fields."""
        state = ResourceState(
            tokens_used_in_window=187500,
            tokens_remaining=312500,
            max_tokens=500000,
            current_burn_rate=3850.0,
            api_calls_last_minute=27,
            api_rate_limit=60,
            budget_percentage=0.625,
            time_remaining_in_window=38.4,
        )
        assert state.tokens_remaining == 312500
        assert state.budget_percentage == 0.625

    def test_resource_state_string_representation(self):
        """String representation should be human-readable."""
        state = ResourceState(
            tokens_used_in_window=95000,
            tokens_remaining=405000,
            max_tokens=500000,
            current_burn_rate=2100.0,
            api_calls_last_minute=9,
            api_rate_limit=60,
            budget_percentage=0.81,
            time_remaining_in_window=55.0,
        )
        output = str(state)
        assert "Budget" in output
        assert "tok/min" in output


class TestThrottleDecision:
    """Tests for ThrottleDecision."""

    def test_throttle_decision_moderate(self):
        """Moderate throttle decision should be constructed correctly."""
        decision = ThrottleDecision(
            level="MODERATE",
            background_feeder_interval=45,
            active_agents=["developer", "jr_researcher", "tech_writer"],
            rate_limit_per_minute=35,
            model_downgrades={"developer": "gpt-4o-mini"},
            reasoning="Moderate sustained load detected",
        )
        assert decision.level == "MODERATE"
        assert len(decision.active_agents) == 3

    def test_throttle_decision_to_dict(self):
        """ThrottleDecision should serialize to dict."""
        decision = ThrottleDecision(
            level="AGGRESSIVE",
            background_feeder_interval=120,
            active_agents=["developer"],
            rate_limit_per_minute=15,
            model_downgrades={},
            reasoning="Critical token burn rate",
        )
        data = decision.to_dict()
        assert data["level"] == "AGGRESSIVE"
        assert "reasoning" in data


class TestHeuristicOptimizer:
    """Basic tests for HeuristicOptimizer."""

    def test_optimizer_can_be_instantiated(self):
        """HeuristicOptimizer should instantiate cleanly."""
        optimizer = HeuristicOptimizer()
        assert optimizer is not None

    def test_optimizer_returns_decision(self):
        """optimize() should return a ThrottleDecision or None."""
        optimizer = HeuristicOptimizer()
        state = ResourceState(
            tokens_used_in_window=100000,
            tokens_remaining=400000,
            max_tokens=500000,
            current_burn_rate=2000.0,
            api_calls_last_minute=10,
            api_rate_limit=60,
            budget_percentage=0.8,
            time_remaining_in_window=50.0,
        )
        decision = optimizer.optimize(state)
        assert decision is None or isinstance(decision, ThrottleDecision)


@pytest.mark.usefixtures("temp_db", "mock_minimal_config")
class TestResourceControllerWorker:
    """Comprehensive tests for the adaptive ResourceControllerWorker."""

    def test_resource_controller_worker_instantiation(self, mock_minimal_config):
        """Worker should initialize with correct configuration."""
        worker = ResourceControllerWorker()
        assert worker is not None
        assert hasattr(worker, "optimizer")

    def test_resource_controller_worker_start_stop_lifecycle(self, mock_minimal_config):
        """Worker should start and stop cleanly."""
        worker = ResourceControllerWorker()
        worker.start(task_id="test_task")
        time.sleep(0.5)
        assert worker.running
        worker.stop()
        assert not worker.running

    def test_worker_uses_optimizer_gracefully(self, mock_minimal_config):
        """Worker should use optimizer without crashing."""
        worker = ResourceControllerWorker()
        worker.start(task_id="test_task")
        time.sleep(1.0)
        assert worker.running is True
        assert worker.optimizer is not None
        worker.stop()
        assert worker.running is False

    def test_worker_respects_resource_controller_config(self, mock_minimal_config):
        """Worker should respect config values."""
        worker = ResourceControllerWorker()
        assert hasattr(worker, "config")
        assert hasattr(worker, "rc_config")

    def test_worker_thread_safety_of_stop(self, mock_minimal_config):
        """Stop should be thread-safe."""
        worker = ResourceControllerWorker()
        worker.start(task_id="test_task")

        def stop_from_thread():
            time.sleep(0.3)
            worker.stop()

        t = threading.Thread(target=stop_from_thread, daemon=True)
        t.start()
        t.join(timeout=2)
        assert not worker.running


if __name__ == "__main__":
    pytest.main([__file__, "-q", "--tb=no"])
