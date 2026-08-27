"""Tests for configurable DB commit retry patience.

Soak evidence: background workers hit DatabaseRetryError after 8 s, losing
data. The default budget should be longer, and callers should be able to
request more patience via get_db_connection(commit_max_seconds=...).
"""

from __future__ import annotations

import sqlite3
from unittest.mock import MagicMock, patch

import pytest

from core.db_connection import (
    DEFAULT_COMMIT_MAX_SECONDS,
    DEFAULT_COMMIT_RETRIES,
    DatabaseRetryError,
    _commit_with_retry,
    get_db_connection,
)


class TestDbRetryDefaults:
    def test_default_commit_max_seconds_increased(self):
        """Default commit budget should be >= 15 s (up from 8 s)."""
        assert DEFAULT_COMMIT_MAX_SECONDS >= 15.0

    def test_default_commit_retries_unchanged(self):
        """Retry count stays at 5 — only the time budget grows."""
        assert DEFAULT_COMMIT_RETRIES == 5


class TestCommitWithRetryBudget:
    def test_commit_raises_after_new_budget(self):
        """Commit still raises after the (longer) budget is exhausted."""
        conn = MagicMock()
        conn.commit.side_effect = sqlite3.OperationalError("database is locked")

        with pytest.raises(DatabaseRetryError, match=r"budget|attempts"):
            _commit_with_retry(conn, retries=4, max_retry_seconds=0.2)

        assert 1 <= conn.commit.call_count <= 4

    def test_commit_succeeds_within_budget(self):
        """Commit succeeds on second attempt within budget."""
        conn = MagicMock()
        call_n = {"n": 0}

        def side_effect():
            call_n["n"] += 1
            if call_n["n"] == 1:
                raise sqlite3.OperationalError("database is locked")

        conn.commit.side_effect = side_effect
        _commit_with_retry(conn, retries=3, max_retry_seconds=5.0)
        assert conn.commit.call_count == 2


class TestGetDbConnectionPatience:
    def test_max_retry_seconds_passed_through(self):
        """get_db_connection passes max_retry_seconds to _commit_with_retry."""
        with patch("core.db_connection._commit_with_retry") as mock_commit:
            mock_commit.return_value = None
            with get_db_connection(max_retry_seconds=25.0, checkpoint_on_close=False):
                pass
            mock_commit.assert_called_once()
            _, kwargs = mock_commit.call_args
            assert kwargs.get("max_retry_seconds") == 25.0

    def test_default_patience_when_not_specified(self):
        """When max_retry_seconds is not passed, the module default is used."""
        with patch("core.db_connection._commit_with_retry") as mock_commit:
            mock_commit.return_value = None
            with get_db_connection(checkpoint_on_close=False):
                pass
            _, kwargs = mock_commit.call_args
            assert kwargs.get("max_retry_seconds") == DEFAULT_COMMIT_MAX_SECONDS
