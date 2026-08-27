"""Tests for ProjectReporterWorker._save_state double-close bug.

Soak evidence: reporter logged 'Cannot operate on a closed database' because
_save_state called conn.commit() and conn.close() explicitly inside a
get_db_connection() context manager, which also commits and closes on exit.
The explicit close fires first, causing the context manager exit to fail.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch


class TestReporterSaveState:
    def test_save_state_does_not_double_close(self):
        """_save_state must not call conn.close() or conn.commit() explicitly."""
        from agents.reporter_worker import ProjectReporterWorker

        worker = ProjectReporterWorker()
        worker.last_report_time = None
        worker.last_file_count = 0
        worker.last_line_delta = 0

        mock_conn = MagicMock()

        with patch("agents.reporter_worker.get_db_connection") as mock_ctx:
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_conn)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

            worker._save_state()

        # The context manager handles commit/close; _save_state must NOT
        # call them explicitly.
        mock_conn.commit.assert_not_called()
        mock_conn.close.assert_not_called()
        # The context manager's __exit__ was called (which triggers commit+close)
        mock_ctx.return_value.__exit__.assert_called_once()

    def test_save_state_executes_insert(self):
        """_save_state must execute the INSERT OR REPLACE statement."""
        from agents.reporter_worker import ProjectReporterWorker

        worker = ProjectReporterWorker()
        worker.last_report_time = None
        worker.last_file_count = 5
        worker.last_line_delta = 10

        mock_conn = MagicMock()

        with patch("agents.reporter_worker.get_db_connection") as mock_ctx:
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_conn)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

            worker._save_state()

        mock_conn.execute.assert_called_once()
        call_args = mock_conn.execute.call_args[0]
        assert "INSERT OR REPLACE" in call_args[0]
