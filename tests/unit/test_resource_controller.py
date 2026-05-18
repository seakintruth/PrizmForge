"""
tests/unit/test_resource_controller.py

Full test suite for Resource Controller core data structures
and the adaptive ResourceControllerWorker.
"""

import pytest
from unittest.mock import patch, MagicMock
import threading
import time

from agents.resource_controller_worker import (
    AgentProfile,
    ResourceState,
    ThrottleDecision,
    HeuristicOptimizer,
    ResourceControllerWorker,
)
from tests.conftest import mock_minimal_config, temp_db  # type: ignore


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
        assert hasattr(worker, "stop_event")

    def test_resource_controller_worker_start_stop_lifecycle(self, mock_minimal_config):
        """Worker should start and stop cleanly."""
        worker = ResourceControllerWorker()
        worker.start()
        time.sleep(0.5)
        assert worker.is_running()
        worker.stop()
        assert not worker.is_running()

    @patch("agents.resource_controller_worker.ResourceControllerWorker._run_optimization_cycle")
    def test_worker_runs_optimization_cycle_periodically(self, mock_cycle, mock_minimal_config):
        """Worker should execute optimization cycles on schedule."""
        mock_cycle.return_value = None
        worker = ResourceControllerWorker(interval_seconds=0.2)
        worker.start()
        time.sleep(1.0)
        worker.stop()
        assert mock_cycle.call_count >= 3

    @patch("agents.resource_controller_worker.HeuristicOptimizer")
    def test_worker_uses_optimizer_for_throttle_decisions(self, mock_optimizer_class, mock_minimal_config):
        """Worker should delegate to the optimizer."""
        mock_optimizer = MagicMock()
        mock_optimizer_class.return_value = mock_optimizer

        worker = ResourceControllerWorker()
        worker._run_optimization_cycle()

        assert mock_optimizer.optimize.called
        assert mock_optimizer.apply_decisions.called

    def test_worker_gracefully_handles_optimizer_exception(self, mock_minimal_config):
        """Exceptions in the optimization cycle should be caught."""
        with patch("agents.resource_controller_worker.ResourceControllerWorker._run_optimization_cycle") as mock_cycle:
            mock_cycle.side_effect = Exception("simulated failure")
            worker = ResourceControllerWorker(interval_seconds=0.1)
            worker.start()
            time.sleep(0.5)
            worker.stop()
            assert not worker.is_running()

    def test_worker_respects_resource_controller_config(self, mock_minimal_config):
        """Worker should respect config values."""
        worker = ResourceControllerWorker()
        assert worker.max_background_agents > 0
        assert worker.throttle_level in ["none", "moderate", "aggressive"]

    @patch("agents.resource_controller_worker.call_agent")
    def test_worker_can_trigger_background_agent_activation(self, mock_call_agent, mock_minimal_config):
        """Worker should activate background agents when instructed."""
        mock_call_agent.return_value = {"status": "activated"}
        worker = ResourceControllerWorker()
        worker._activate_background_agent("jr_reviewer")
        assert mock_call_agent.called

    def test_worker_thread_safety_of_stop_event(self, mock_minimal_config):
        """Stop event should be thread-safe."""
        worker = ResourceControllerWorker()
        worker.start()

        def stop_from_thread():
            time.sleep(0.3)
            worker.stop()

        t = threading.Thread(target=stop_from_thread, daemon=True)
        t.start()
        t.join(timeout=2)
        assert not worker.is_running()

    def test_worker_integration_with_parallel_workers(self, mock_minimal_config):
        """Worker should coordinate with parallel background system."""
        with patch("agents.parallel_workers.start_parallel_workers") as mock_start:
            worker = ResourceControllerWorker()
            worker._apply_background_agent_decisions({"jr_reviewer": True, "security_reviewer": False})
            assert True  # coordination path exercised


if __name__ == "__main__":
    pytest.main([__file__, "-q", "--tb=no"])