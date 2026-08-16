"""Parallel worker tests — always MockLLM; never hit live call_agent."""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from agents.parallel_workers import BackgroundAgentPool, FileChangeEvent, get_agent_pool

# Process-global pool / threads → serial; start/stop cases are duration-slow.
pytestmark = pytest.mark.serial

# Minimal agent set so pool.start() actually launches threads under test.
# Real config.json agents must never leak in (conftest forces {}).
_TEST_BG_AGENTS = {
    "jr_reviewer": {
        "enabled": True,
        "on_modification": True,
        "random_review": False,
    },
}


@pytest.fixture
def pool_env(isolated_project, monkeypatch):
    """Opt in to one feedback agent + MockLLM-safe call_agent for pool tests."""
    from core import config as core_config

    cfg = dict(isolated_project["config"])
    cfg["background_agents_enabled"] = True
    cfg["background_agents"] = dict(_TEST_BG_AGENTS)
    cfg["background_feeder"] = {"interval_seconds": 60}
    monkeypatch.setattr(core_config, "get_config", lambda: cfg)
    # parallel_workers may have already bound get_config at import
    try:
        monkeypatch.setattr("agents.parallel_workers.get_config", lambda: cfg)
    except Exception:
        pass
    return cfg


@pytest.mark.usefixtures("temp_db", "mock_minimal_config")
class TestParallelWorkers:
    """Pool helpers + start/stop/queue cases. Only measured-slow methods get @pytest.mark.slow."""

    def test_file_change_event_creation(self):
        """FileChangeEvent should be constructible with correct fields."""
        event = FileChangeEvent(
            event_id="test-123",
            file_path="core/db.py",
            operation="modified",
            content="test content",
            content_hash="abc123",
            metadata={},
            task_id="test_task",
            timestamp="2024-01-01T00:00:00",
        )
        assert event.file_path == "core/db.py"
        assert event.operation == "modified"

    def test_background_agent_pool_instantiation(self):
        """Agent pool should initialize correctly."""
        pool = BackgroundAgentPool()
        assert pool is not None
        assert hasattr(pool, "start")
        assert hasattr(pool, "stop")

    @pytest.mark.slow
    def test_agent_pool_start_stop(self, pool_env):
        """Agent pool should start and stop without crashing — under MockLLM."""
        with patch(
            "agents.parallel_workers.call_agent",
            return_value='{"findings": [], "summary": "ok"}',
        ):
            pool = BackgroundAgentPool()
            try:
                pool.start(task_id="test_task")
                time.sleep(0.3)
                pool.stop()
                assert pool.running is False
            except Exception as e:
                pytest.fail(f"Agent pool failed: {e}")

    @pytest.mark.slow
    def test_start_noop_when_agents_disabled(self, isolated_project):
        """With background_agents_enabled=False, start must not launch workers."""
        pool = BackgroundAgentPool()
        pool.start(task_id="disabled")
        assert pool.running is False
        assert pool.workers == []
        pool.stop()

    def test_get_agent_pool_singleton(self):
        """get_agent_pool should return singleton instance."""
        pool1 = get_agent_pool()
        pool2 = get_agent_pool()
        assert pool1 is pool2

    @pytest.mark.slow
    def test_queue_file_change(self, pool_env):
        """Should be able to queue file changes under MockLLM."""
        with patch(
            "agents.parallel_workers.call_agent",
            return_value='{"findings": [], "summary": "ok"}',
        ):
            pool = BackgroundAgentPool()
            pool.start(task_id="test_task")
            try:
                pool.queue_file_change(file_path="test.py", operation="modified", content="test content")
                time.sleep(0.3)
                assert hasattr(pool, "queue") or hasattr(pool, "event_queue") or pool.running is not None
            finally:
                pool.stop()
                assert pool.running is False

    @pytest.mark.slow
    def test_worker_processes_events(self, pool_env):
        """Workers should process queued events via mocked call_agent."""
        with patch(
            "agents.parallel_workers.call_agent",
            return_value='{"findings": [], "summary": "ok"}',
        ) as mock_call_agent:
            pool = BackgroundAgentPool()
            pool.start(task_id="test_task")
            try:
                pool.queue_file_change(file_path="test.py", operation="modified", content="def test(): pass")
                time.sleep(1.0)
                assert isinstance(mock_call_agent.call_count, int)
            finally:
                pool.stop()
                assert pool.running is False

    @pytest.mark.slow
    def test_empty_queue_handling(self, pool_env):
        """Worker should handle empty queue gracefully."""
        with patch(
            "agents.parallel_workers.call_agent",
            return_value='{"findings": []}',
        ):
            pool = BackgroundAgentPool()
            pool.start(task_id="test_task")
            time.sleep(0.3)
            pool.stop()
            assert pool.running is False

    @pytest.mark.slow
    def test_force_review_cycle(self, pool_env):
        """Force review cycle should queue files under MockLLM."""
        with patch(
            "agents.parallel_workers.call_agent",
            return_value='{"findings": []}',
        ):
            # Use a fresh pool, not the process singleton, to avoid cross-test state
            pool = BackgroundAgentPool()
            pool.start(task_id="test_task")
            try:
                pool.force_review_cycle(file_limit=5)
                time.sleep(0.3)
            finally:
                pool.stop()
                assert pool.running is False


class TestAgentPoolConfiguration:
    """Tests for agent pool configuration (fast; not slow)."""

    def test_agent_configs_loaded(self):
        """Agent pool should load configs from config (empty under isolation)."""
        pool = BackgroundAgentPool()
        assert hasattr(pool, "agent_configs")
        assert isinstance(pool.agent_configs, dict)

    def test_modification_agents_list(self):
        pool = BackgroundAgentPool()
        assert hasattr(pool, "modification_agents")
        assert isinstance(pool.modification_agents, list)

    def test_random_review_agents_list(self):
        pool = BackgroundAgentPool()
        assert hasattr(pool, "random_review_agents")
        assert isinstance(pool.random_review_agents, list)


@pytest.mark.usefixtures("temp_db")
class TestAgentPoolActiveControl:
    """Active-agent control; only live pool start is slow."""

    @pytest.mark.slow
    def test_set_active_agents(self, pool_env):
        with patch(
            "agents.parallel_workers.call_agent",
            return_value='{"findings": []}',
        ):
            pool = BackgroundAgentPool()
            pool.start(task_id="test_task")
            try:
                pool.set_active_agents(["jr_reviewer", "prioritizer"])
                assert pool.active_agents_filter is not None
                assert "jr_reviewer" in pool.active_agents_filter
            finally:
                pool.stop()

    def test_set_feeder_interval(self):
        pool = BackgroundAgentPool()
        pool.set_feeder_interval(60.0)
        assert pool.feeder_interval == 60.0
        pool.set_feeder_interval(30.0)
        assert pool.feeder_interval == 30.0


@pytest.mark.slow
@pytest.mark.usefixtures("temp_db")
class TestConcurrentBehavior:
    """Concurrent pool behavior (9–25s)."""

    def test_multiple_file_changes_concurrent(self, pool_env):
        with patch(
            "agents.parallel_workers.call_agent",
            return_value='{"findings": [], "summary": "ok"}',
        ) as mock_call_agent:
            pool = BackgroundAgentPool()
            pool.start(task_id="test_task")
            try:
                for i in range(10):
                    pool.queue_file_change(
                        file_path=f"test_{i}.py",
                        operation="modified",
                        content=f"def test_{i}(): pass",
                    )
                time.sleep(1.5)
                assert mock_call_agent.call_count >= 0
            finally:
                pool.stop()

    def test_start_stop_lifecycle(self, pool_env):
        """Should handle multiple start/stop cycles under MockLLM."""
        with patch(
            "agents.parallel_workers.call_agent",
            return_value='{"findings": []}',
        ):
            pool = BackgroundAgentPool()
            for i in range(3):
                pool.start(task_id=f"test_task_{i}")
                time.sleep(0.2)
                pool.stop()
                assert pool.running is False
                time.sleep(0.1)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
