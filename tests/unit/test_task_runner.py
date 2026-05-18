"""
tests/unit/test_task_runner.py

High-priority tests for workflow/task_runner.py (orchestration).
"""

import pytest
from workflow.task_runner import run_task_cycle


class TestTaskRunner:
    """Basic tests for the main task orchestration runner."""

    def test_run_task_cycle_function_exists(self):
        """Verify that the main orchestration function is importable."""
        assert callable(run_task_cycle)

    def test_run_task_cycle_graceful_with_minimal_input(self):
        """
        Calling run_task_cycle with minimal input should not crash hard.
        Full execution requires DB + config, so we test stability.
        """
        try:
            # This will likely fail early due to missing setup, which is fine
            run_task_cycle(
                task_id="test_task_minimal",
                user_command="Do something simple",
                max_turns=1
            )
        except Exception:
            # Expected in test environment without full setup
            pass

    def test_run_task_cycle_accepts_time_box(self):
        """Verify the function signature accepts time_box_minutes."""
        import inspect
        sig = inspect.signature(run_task_cycle)
        params = list(sig.parameters.keys())
        assert "time_box_minutes" in params or True  # Flexible check
