"""Tests for wall-clock DB retry budget and ResponseParser strategies."""

from __future__ import annotations

import sqlite3
import time
from unittest.mock import MagicMock

import pytest

from core.db_connection import (
    DatabaseRetryError,
    _backoff_sleep,
    _commit_with_retry,
    execute_with_retry,
)
from core.json_parser import ParseStatus
from core.response_parser import ResponseParser


class TestBackoffCountdown:
    def test_backoff_stops_when_deadline_passed(self):
        deadline = time.monotonic() - 0.01
        assert _backoff_sleep(0, deadline) is False

    def test_backoff_sleeps_within_budget(self):
        deadline = time.monotonic() + 2.0
        start = time.monotonic()
        ok = _backoff_sleep(0, deadline, cap=0.05)
        elapsed = time.monotonic() - start
        assert ok is True
        assert elapsed < 0.5


class TestCommitRetryTerminal:
    def test_commit_raises_after_budget(self):
        conn = MagicMock()
        conn.commit.side_effect = sqlite3.OperationalError("database is locked")

        with pytest.raises(DatabaseRetryError, match="budget|attempts"):
            _commit_with_retry(conn, retries=4, max_retry_seconds=0.15)

        # Must not loop unbounded — a few attempts only within the short budget
        assert 1 <= conn.commit.call_count <= 4

    def test_non_lock_error_not_retried(self):
        conn = MagicMock()
        conn.commit.side_effect = sqlite3.OperationalError("no such table: missing")

        with pytest.raises(sqlite3.OperationalError, match="no such table"):
            _commit_with_retry(conn, retries=5, max_retry_seconds=2.0)

        assert conn.commit.call_count == 1

    def test_database_retry_error_not_caught_by_execute_with_retry(self, monkeypatch, tmp_path):
        """Inner DatabaseRetryError must propagate — never nested into infinite loop."""
        db = tmp_path / "t.db"
        sqlite3.connect(db).close()

        def boom(*_a, **_k):
            raise DatabaseRetryError("commit failed after budget")

        monkeypatch.setattr("core.db_connection.get_db_connection", boom)

        with pytest.raises(DatabaseRetryError, match="commit failed"):
            execute_with_retry("SELECT 1", retries=5, max_retry_seconds=5.0)


class TestResponseParser:
    def test_parses_markdown_json(self):
        parser = ResponseParser()
        raw = 'Here you go:\n```json\n{"next_agent": "developer"}\n```\n'
        result = parser.parse(raw)
        assert result.success
        assert result.data["next_agent"] == "developer"

    def test_parses_raw_object(self):
        parser = ResponseParser()
        result = parser.parse('prefix {"a": 1, "b": 2} suffix')
        assert result.success
        assert result.data["a"] == 1

    def test_empty_response(self):
        parser = ResponseParser()
        result = parser.parse("   \n")
        assert result.status == ParseStatus.EMPTY

    def test_malformed(self):
        parser = ResponseParser()
        result = parser.parse("not json at all")
        assert not result.success
        assert result.status in (ParseStatus.MALFORMED, ParseStatus.EMPTY)
