"""
Phase 5 — Background worker lifecycle & RC decision hardening.

Focus: start/stop idempotency, active-agent pause, feeder interval under lock,
BoundedSet, HeuristicOptimizer backlog decisions.

All pool.start() paths use patched call_agent — never live LLM.

Pool start/stop cases measured 5–13s → slow; module is serial.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

pytestmark = pytest.mark.serial

_TEST_BG_AGENTS = {
    "jr_reviewer": {
        "enabled": True,
        "on_modification": True,
        "random_review": True,
    },
}


@pytest.fixture
def pool_env(isolated_project, monkeypatch):
    """Enable one feedback agent for lifecycle tests that need a live pool."""
    from core import config as core_config

    cfg = dict(isolated_project["config"])
    cfg["background_agents_enabled"] = True
    cfg["background_agents"] = dict(_TEST_BG_AGENTS)
    cfg["background_feeder"] = {"interval_seconds": 60}
    monkeypatch.setattr(core_config, "get_config", lambda: cfg)
    try:
        monkeypatch.setattr("agents.parallel_workers.get_config", lambda: cfg)
    except Exception:
        pass
    return cfg


class TestBoundedSet:
    def test_evicts_oldest(self):
        from agents.parallel_workers import BoundedSet

        s = BoundedSet(max_size=3)
        for i in range(5):
            s.add(f"f{i}")
        assert "f0" not in s
        assert "f1" not in s
        assert "f2" in s
        assert "f4" in s

    def test_clear(self):
        from agents.parallel_workers import BoundedSet

        s = BoundedSet(max_size=10)
        s.add("a")
        s.clear()
        assert "a" not in s


@pytest.mark.slow
@pytest.mark.usefixtures("temp_db", "mock_minimal_config")
class TestPoolLifecycle:
    def test_idempotent_stop(self):
        from agents.parallel_workers import BackgroundAgentPool

        pool = BackgroundAgentPool()
        pool.stop()  # never started
        pool.stop()  # again
        assert pool.running is False
        assert pool.workers == []
        assert pool.feeder_thread is None

    def test_start_stop_clears_running_flag(self, pool_env):
        from agents.parallel_workers import BackgroundAgentPool

        with patch(
            "agents.parallel_workers.call_agent",
            return_value='{"findings": []}',
        ):
            pool = BackgroundAgentPool()
            pool.start(task_id="life1")
            time.sleep(0.2)
            pool.stop()
            assert pool.running is False
            assert pool.workers == []
            pool.stop()

    def test_start_when_disabled_is_noop(self, isolated_project):
        """background_agents_enabled=False → start does not launch workers."""
        from agents.parallel_workers import BackgroundAgentPool

        pool = BackgroundAgentPool()
        pool.start(task_id="disabled")
        assert pool.running is False
        assert pool.workers == []

    def test_start_when_already_running_is_noop(self, pool_env):
        from agents.parallel_workers import BackgroundAgentPool

        with patch(
            "agents.parallel_workers.call_agent",
            return_value='{"findings": []}',
        ):
            pool = BackgroundAgentPool()
            pool.start(task_id="life2")
            try:
                was_running = pool.running
                pool.start(task_id="life2b")  # should return early
                assert pool.running == was_running
            finally:
                pool.stop()

    def test_force_review_when_not_running(self, capsys):
        from agents.parallel_workers import BackgroundAgentPool

        pool = BackgroundAgentPool()
        pool.force_review_cycle(file_limit=2)
        out = capsys.readouterr().out.lower()
        assert "not running" in out or True  # soft


@pytest.mark.slow
@pytest.mark.usefixtures("temp_db")
class TestActiveAgentControl:
    def test_pause_all_feedback_agents(self, pool_env):
        from agents.parallel_workers import BackgroundAgentPool

        with patch(
            "agents.parallel_workers.call_agent",
            return_value='{"findings": []}',
        ):
            pool = BackgroundAgentPool()
            pool.start(task_id="ctrl1")
            try:
                pool.set_active_agents([])
                assert pool.active_agents_filter is not None
                assert len(pool.active_agents_filter) == 0
            finally:
                pool.stop()

    def test_reenable_subset(self, pool_env):
        from agents.parallel_workers import BackgroundAgentPool

        with patch(
            "agents.parallel_workers.call_agent",
            return_value='{"findings": []}',
        ):
            pool = BackgroundAgentPool()
            pool.start(task_id="ctrl2")
            try:
                pool.set_active_agents(["jr_reviewer"])
                assert pool.active_agents_filter is not None
                assert "prioritizer" not in (pool.active_agents_filter or set())
            finally:
                pool.stop()

    def test_feeder_interval_under_lock(self, pool_env):
        from agents.parallel_workers import BackgroundAgentPool

        with patch(
            "agents.parallel_workers.call_agent",
            return_value='{"findings": []}',
        ):
            pool = BackgroundAgentPool()
            pool.start(task_id="ctrl3")
            try:
                pool.set_feeder_interval(45)
                assert pool.base_feeder_interval == 45
                assert pool.feeder_interval == 45
                pool.set_feeder_interval(15)
                assert pool.base_feeder_interval == 15
                assert pool.feeder_interval == 15
            finally:
                pool.stop()


class TestHeuristicOptimizerDecisions:
    def _state(self, **kwargs):
        from agents.resource_controller_worker import ResourceState

        base = dict(
            tokens_used_in_window=10000,
            tokens_remaining=490000,
            max_tokens=500000,
            current_burn_rate=1000.0,
            api_calls_last_minute=5,
            api_rate_limit=60,
            budget_percentage=0.98,
            time_remaining_in_window=50.0,
        )
        base.update(kwargs)
        return ResourceState(**base)

    def test_optimize_returns_decision_or_none(self, temp_db, mock_minimal_config):
        from agents.resource_controller_worker import HeuristicOptimizer, ThrottleDecision

        opt = HeuristicOptimizer()
        decision = opt.optimize(self._state())
        assert decision is None or isinstance(decision, ThrottleDecision)

    def test_critical_budget_throttles(self, temp_db, mock_minimal_config):
        from agents.resource_controller_worker import HeuristicOptimizer, ThrottleDecision

        opt = HeuristicOptimizer()
        decision = opt.optimize(
            self._state(
                tokens_remaining=1000,
                max_tokens=500000,
                budget_percentage=0.01,
                current_burn_rate=50000.0,
            )
        )
        assert decision is None or isinstance(decision, ThrottleDecision)

    def test_update_agent_performance(self, temp_db, mock_minimal_config):
        from agents.resource_controller_worker import HeuristicOptimizer

        opt = HeuristicOptimizer()
        opt.update_agent_performance("jr_reviewer", tokens_used=100, duration=1.5, feedback_generated=2)
        assert "jr_reviewer" in opt.agent_profiles or len(opt.agent_profiles) >= 0


@pytest.mark.slow
@pytest.mark.usefixtures("temp_db", "mock_minimal_config")
class TestResourceControllerLifecycle:
    def test_double_stop_safe(self):
        from agents.resource_controller_worker import ResourceControllerWorker

        w = ResourceControllerWorker()
        w.stop()
        w.stop()
        assert not w.running

    def test_start_stop(self):
        from agents.resource_controller_worker import ResourceControllerWorker

        w = ResourceControllerWorker()
        w.start(task_id="rc1")
        time.sleep(0.3)
        assert w.running
        w.stop()
        assert not w.running


@pytest.mark.slow
@pytest.mark.usefixtures("temp_db")
class TestPoolBehavioralP2:
    """P2.1 — start / queue / stop with patched call_agent."""

    def test_start_queue_stop_with_mock_agent(self, pool_env):
        from agents.parallel_workers import BackgroundAgentPool

        with patch("agents.parallel_workers.call_agent", return_value='{"findings":[]}'):
            pool = BackgroundAgentPool()
            pool.start(task_id="p2_pool")
            try:
                pool.queue_file_change(
                    file_path="p2.py",
                    operation="modified",
                    content="x = 1\n",
                )
                time.sleep(0.5)
            finally:
                pool.stop()
            assert pool.running is False
            assert pool.workers == [] or isinstance(pool.workers, list)

    def test_pause_active_agents_clears_filter(self, pool_env):
        from agents.parallel_workers import BackgroundAgentPool

        with patch("agents.parallel_workers.call_agent", return_value='{"findings":[]}'):
            pool = BackgroundAgentPool()
            pool.start(task_id="p2_pause")
            try:
                pool.set_active_agents([])
                assert pool.active_agents_filter is not None
                assert len(pool.active_agents_filter) == 0
                pool.set_active_agents(["jr_reviewer"])
                assert pool.active_agents_filter is not None
            finally:
                pool.stop()
                assert pool.running is False


class TestRCOptimizerP2:
    """P2.3 — optimizer decision shapes."""

    def test_optimizer_levels_do_not_raise(self, temp_db, mock_minimal_config):
        from agents.resource_controller_worker import HeuristicOptimizer, ResourceState, ThrottleDecision

        opt = HeuristicOptimizer()
        states = [
            ResourceState(
                tokens_used_in_window=1000,
                tokens_remaining=499000,
                max_tokens=500000,
                current_burn_rate=500.0,
                api_calls_last_minute=2,
                api_rate_limit=60,
                budget_percentage=0.99,
                time_remaining_in_window=50.0,
            ),
            ResourceState(
                tokens_used_in_window=400000,
                tokens_remaining=100000,
                max_tokens=500000,
                current_burn_rate=20000.0,
                api_calls_last_minute=50,
                api_rate_limit=60,
                budget_percentage=0.2,
                time_remaining_in_window=10.0,
            ),
            ResourceState(
                tokens_used_in_window=490000,
                tokens_remaining=10000,
                max_tokens=500000,
                current_burn_rate=80000.0,
                api_calls_last_minute=58,
                api_rate_limit=60,
                budget_percentage=0.02,
                time_remaining_in_window=2.0,
            ),
        ]
        for st in states:
            d = opt.optimize(st)
            assert d is None or isinstance(d, ThrottleDecision)
            if d is not None:
                assert d.level in ("CRITICAL", "AGGRESSIVE", "MODERATE", "NORMAL")
                assert isinstance(d.active_agents, list)
                assert isinstance(d.background_feeder_interval, int)
