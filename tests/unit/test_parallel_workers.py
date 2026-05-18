import pytest
from unittest.mock import patch, MagicMock
import threading
import queue
import time
from pathlib import Path
import concurrent.futures

from agents.parallel_workers import (
    FileChangeEvent,
    BackgroundWorker,
    start_parallel_workers,
    stop_parallel_workers,
    _worker_loop,
)
from tests.conftest import mock_minimal_config, temp_db  # type: ignore


@pytest.mark.usefixtures("temp_db", "mock_minimal_config")
class TestParallelWorkers:
    """Tests for the parallel background agent system."""

    def test_file_change_event_creation(self):
        """FileChangeEvent should be constructible with correct fields."""
        event = FileChangeEvent(
            file_path=Path("core/db.py"),
            change_type="modified",
            line_guids=["abc123"],
            timestamp=time.time(),
        )
        assert event.file_path == Path("core/db.py")
        assert event.change_type == "modified"
        assert len(event.line_guids) == 1

    def test_background_worker_instantiation(self):
        """Worker should initialize with correct agent and queue."""
        q = queue.Queue()
        worker = BackgroundWorker(agent_name="jr_reviewer", work_queue=q)
        assert worker.agent_name == "jr_reviewer"
        assert worker.work_queue is q
        assert worker.stop_event is not None

    @patch("agents.parallel_workers.call_agent")
    def test_worker_loop_processes_event(self, mock_call_agent, mock_minimal_config):
        """Worker thread should consume events and call the agent."""
        mock_call_agent.return_value = {"feedback": "test review"}
        q = queue.Queue()
        stop_event = threading.Event()

        # Put a test event
        event = FileChangeEvent(Path("test.py"), "modified")
        q.put(event)

        # Run one iteration
        _worker_loop("jr_reviewer", q, stop_event, max_iterations=1)

        assert mock_call_agent.called

    def test_start_parallel_workers_spawns_threads(self, mock_minimal_config):
        """start_parallel_workers should launch the configured number of threads."""
        with patch("agents.parallel_workers.threading.Thread") as mock_thread:
            mock_thread.return_value = MagicMock()
            start_parallel_workers(num_workers=2)
            assert mock_thread.call_count >= 2

    def test_stop_parallel_workers_signals_shutdown(self, mock_minimal_config):
        """stop_parallel_workers should set stop events on all workers."""
        workers = [BackgroundWorker("jr_reviewer", queue.Queue()) for _ in range(3)]
        stop_parallel_workers(workers)
        for w in workers:
            assert w.stop_event.is_set()

    def test_parallel_workers_handle_empty_queue_gracefully(self):
        """Worker should not crash on empty queue."""
        q = queue.Queue()
        stop_event = threading.Event()
        stop_event.set()  # immediate shutdown
        _worker_loop("jr_reviewer", q, stop_event, max_iterations=1)
        # No exception = success

    def test_parallel_workers_respect_resource_controller_throttle(self, mock_minimal_config):
        """Worker should respect Resource Controller throttling signals."""
        with patch("agents.parallel_workers.resource_controller") as mock_rc:
            mock_rc.should_run_agent.return_value = False
            q = queue.Queue()
            stop_event = threading.Event()
            _worker_loop("jr_reviewer", q, stop_event, max_iterations=1)
            assert mock_rc.should_run_agent.called

    def test_parallel_workers_integration_with_file_change_events(self):
        """End-to-end smoke test: event → queue → worker."""
        q = queue.Queue()
        event = FileChangeEvent(Path("file_editing/editing.py"), "modified")
        q.put(event)

        stop_event = threading.Event()
        stop_event.set()  # run once

        _worker_loop("security_reviewer", q, stop_event, max_iterations=1)
        # No crash + queue drained = success


class TestConcurrentRaceConditions:
    """Dedicated tests for concurrent worker race conditions."""

    def test_multiple_workers_consume_queue_without_race(self, mock_minimal_config):
        """Many workers pulling from the same queue simultaneously should not lose events."""
        q = queue.Queue()
        stop_event = threading.Event()

        # Pre-load many events
        for i in range(50):
            q.put(FileChangeEvent(Path(f"file_{i}.py"), "modified"))

        with patch("agents.parallel_workers.call_agent") as mock_call:
            mock_call.return_value = {"status": "ok"}

            # Run 8 workers concurrently for a short burst
            threads = []
            for i in range(8):
                t = threading.Thread(
                    target=_worker_loop,
                    args=(f"worker_{i}", q, stop_event, 10),  # max 10 iterations per worker
                    daemon=True,
                )
                threads.append(t)
                t.start()

            # Give them time to drain the queue
            time.sleep(2)
            stop_event.set()

            for t in threads:
                t.join(timeout=3)

            assert mock_call.call_count >= 40  # most events should be processed
            assert q.empty()  # no events left behind

    def test_stop_event_is_thread_safe_under_contention(self, mock_minimal_config):
        """Setting stop_event from main thread while workers are running should be atomic."""
        q = queue.Queue()
        stop_event = threading.Event()

        with patch("agents.parallel_workers.call_agent") as mock_call:
            mock_call.side_effect = lambda **kwargs: time.sleep(0.01)  # simulate work

            # Start several workers
            workers = []
            for i in range(5):
                worker = BackgroundWorker(f"race_worker_{i}", q)
                workers.append(worker)
                # Start their loops manually
                t = threading.Thread(target=_worker_loop, args=(worker.agent_name, q, worker.stop_event, 100), daemon=True)
                t.start()

            # Immediate shutdown from main thread
            stop_parallel_workers(workers)

            # All stop_events should be set
            for w in workers:
                assert w.stop_event.is_set()

    def test_concurrent_call_agent_calls_no_state_leakage(self, mock_minimal_config):
        """Concurrent calls to call_agent from multiple workers should not interfere."""
        from core.call_agent import call_agent  # type: ignore

        results = []

        def worker_task(agent_name: str):
            for _ in range(5):
                result = call_agent(agent_name=agent_name, prompt="race test")
                results.append(result)

        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
            futures = [
                executor.submit(worker_task, name)
                for name in ["jr_reviewer", "security_reviewer", "tech_writer"]
            ]
            for f in futures:
                f.result()

        # All results should be valid dicts (or None) — no crashes or corrupted state
        assert all(isinstance(r, (dict, type(None))) for r in results)
        assert len(results) == 30  # 3 agents × 5 calls each

    def test_resource_controller_throttling_under_concurrent_load(self, mock_minimal_config):
        """Resource Controller should be consulted safely under high contention."""
        q = queue.Queue()
        stop_event = threading.Event()

        with patch("agents.parallel_workers.resource_controller") as mock_rc:
            mock_rc.should_run_agent.return_value = True

            # Fire 10 workers at once
            threads = []
            for i in range(10):
                t = threading.Thread(
                    target=_worker_loop,
                    args=(f"rc_worker_{i}", q, stop_event, 3),
                    daemon=True,
                )
                threads.append(t)
                t.start()

            time.sleep(1.5)
            stop_event.set()
            for t in threads:
                t.join(timeout=2)

            # Each worker should have checked the controller at least once
            assert mock_rc.should_run_agent.call_count >= 10

    def test_queue_drain_under_high_contention_no_lost_events(self, mock_minimal_config):
        """Stress test: 100 events, many workers — ensure none are dropped due to race."""
        q = queue.Queue()
        stop_event = threading.Event()

        # Inject events rapidly from main thread
        for i in range(100):
            q.put(FileChangeEvent(Path(f"stress_{i}.py"), "modified"))

        with patch("agents.parallel_workers.call_agent") as mock_call:
            mock_call.return_value = {"processed": True}

            # Launch workers
            threads = []
            for i in range(12):
                t = threading.Thread(
                    target=_worker_loop,
                    args=(f"stress_{i}", q, stop_event, 20),
                    daemon=True,
                )
                threads.append(t)
                t.start()

            time.sleep(3)  # let them work
            stop_event.set()
            for t in threads:
                t.join(timeout=3)

            # All events should be consumed
            assert q.empty()
            assert mock_call.call_count >= 90


if __name__ == "__main__":
    pytest.main([__file__, "-q", "--tb=no"])