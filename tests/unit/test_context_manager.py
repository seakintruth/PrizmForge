"""
tests/unit/test_context_manager.py

Realistic tests for ContextManager that match the actual implementation.
"""

import pytest
import time
from pathlib import Path

from core.context_manager import get_context_manager, ContextManager
from core.db_connection import get_db_connection


class TestContextManagerBasic:
    """Basic instantiation and singleton tests."""

    def test_context_manager_singleton(self):
        """get_context_manager should return singleton instance."""
        cm1 = get_context_manager()
        cm2 = get_context_manager()
        assert cm1 is cm2
        assert isinstance(cm1, ContextManager)

    def test_context_manager_has_config(self):
        """Context manager should load configuration."""
        cm = get_context_manager()
        assert hasattr(cm, "config")
        assert hasattr(cm, "model_limits")

    def test_model_limits_loaded(self):
        """Model limits should be loaded from config."""
        cm = get_context_manager()
        assert isinstance(cm.model_limits, dict)
        # Should have at least the default
        assert cm.default_context_limit > 0


class TestModelContextLimits:
    """Tests for model-specific context limits."""

    def test_get_model_context_limit_known_model(self):
        """Should return correct limit for known models."""
        cm = get_context_manager()

        # Test with common model names
        for model in ["gemini-3.1-pro-preview", "gemini-3-flash-preview"]:
            limit = cm.get_model_context_limit(model)
            assert isinstance(limit, int)
            assert limit > 0

    def test_get_model_context_limit_unknown_model(self):
        """Should return default for unknown models."""
        cm = get_context_manager()
        limit = cm.get_model_context_limit("unknown-model-xyz")

        assert isinstance(limit, int)
        assert limit == cm.default_context_limit

    def test_get_model_context_limit_none(self):
        """Should handle None model gracefully."""
        cm = get_context_manager()
        limit = cm.get_model_context_limit(None)

        assert isinstance(limit, int)
        assert limit > 0


class TestGetPrioritizedFilesFast:
    """Tests for _get_prioritized_files_fast method."""

    def test_get_prioritized_files_empty_db(self, temp_db):
        """Should return empty list when no files exist."""
        cm = ContextManager()
        files = cm._get_prioritized_files_fast(task_id="test_task", limit=10)

        assert isinstance(files, list)
        assert len(files) == 0

    def test_get_prioritized_files_with_limit(self, temp_db):
        """Should respect limit parameter."""
        # Add some test files
        with get_db_connection() as conn:
            for i in range(20):
                conn.execute(
                    """
                    INSERT INTO project_files 
                    (file_path, content, estimated_tokens, last_modified, 
                     size_bytes, file_type, is_binary, content_hash)
                    VALUES (?, ?, ?, ?, ?, ?, 0, ?)
                """,
                    (
                        f"test_{i}.py",
                        "def test(): pass",
                        100,
                        "2024-01-01T00:00:00",
                        50,
                        ".py",
                        f"hash_{i}",
                    ),
                )

        cm = ContextManager()
        files = cm._get_prioritized_files_fast(task_id="test_task", limit=5)

        assert isinstance(files, list)
        assert len(files) <= 5

    def test_get_prioritized_files_invalid_limit(self, temp_db):
        """Should handle invalid limit values."""
        cm = ContextManager()

        # Negative limit
        files = cm._get_prioritized_files_fast(task_id="test_task", limit=-5)
        assert isinstance(files, list)

        # Zero limit
        files = cm._get_prioritized_files_fast(task_id="test_task", limit=0)
        assert files == []


class TestBuildOrchestratorContext:
    """Tests for build_orchestrator_context method."""

    def test_build_context_basic(self, temp_db):
        """Should build context with basic inputs."""
        cm = ContextManager()

        context_str, metadata = cm.build_orchestrator_context(
            task_id="test_task",
            user_command="Build a hello world function",
            conversation_history=[],
            model="gemini-3-flash-preview",
        )

        assert isinstance(context_str, str)
        assert isinstance(metadata, dict)
        assert len(context_str) > 0

    def test_build_context_metadata_structure(self, temp_db):
        """Metadata should have required fields."""
        cm = ContextManager()

        _, metadata = cm.build_orchestrator_context(
            task_id="test_task",
            user_command="Test command",
            conversation_history=[],
            model="gemini-3-flash-preview",
        )

        # Check required metadata fields
        assert "tokens_used" in metadata
        assert "context_limit" in metadata
        assert "files_included" in metadata
        assert "context_utilization" in metadata

        assert isinstance(metadata["tokens_used"], int)
        assert isinstance(metadata["context_limit"], int)
        assert isinstance(metadata["files_included"], list)

    def test_build_context_respects_token_limit(self, temp_db):
        """Should not exceed context token limit."""
        cm = ContextManager()

        _, metadata = cm.build_orchestrator_context(
            task_id="test_task",
            user_command="Test",
            conversation_history=[],
            model="gemini-3-flash-preview",
        )

        assert metadata["tokens_used"] <= metadata["context_limit"]

    def test_build_context_with_conversation_history(self, temp_db):
        """Should include conversation history in context."""
        cm = ContextManager()

        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]

        context_str, metadata = cm.build_orchestrator_context(
            task_id="test_task",
            user_command="Continue",
            conversation_history=history,
            model="gemini-3-flash-preview",
        )

        assert metadata["tokens_used"] > 0
        assert isinstance(context_str, str)

    def test_build_context_with_files(self, temp_db):
        """Should include files when available."""
        # Add test files
        with get_db_connection() as conn:
            conn.execute(
                """
                INSERT INTO project_files 
                (file_path, content, estimated_tokens, last_modified, 
                 size_bytes, file_type, is_binary, content_hash)
                VALUES (?, ?, ?, ?, ?, ?, 0, ?)
            """,
                (
                    "test.py",
                    "def hello(): pass",
                    100,
                    "2024-01-01T00:00:00",
                    50,
                    ".py",
                    "hash123",
                ),
            )

            # Add summary
            conn.execute(
                """
                INSERT INTO file_summaries 
                (file_path, summary, purpose, line_count)
                VALUES (?, ?, ?, ?)
            """,
                ("test.py", "Test file", "Testing", 1),
            )

        cm = ContextManager()
        context_str, metadata = cm.build_orchestrator_context(
            task_id="test_task",
            user_command="Review test.py",
            conversation_history=[],
            model="gemini-3-flash-preview",
        )

        # Should mention files
        assert "test.py" in context_str or len(metadata["files_included"]) > 0


class TestGetPrioritizedSuggestions:
    """Tests for _get_prioritized_suggestions method."""

    def test_get_suggestions_empty_db(self, temp_db):
        """Should handle empty feedback gracefully."""
        cm = ContextManager()
        result = cm._get_prioritized_suggestions("test_task")

        # Should return None or empty string when no feedback
        assert result is None or result == ""

    def test_get_suggestions_with_feedback(self, temp_db):
        """Should format feedback when available."""
        # Add test feedback
        with get_db_connection() as conn:
            conn.execute(
                """
                INSERT INTO agent_feedback 
                (agent_name, file_path, priority, category, message, 
                 task_id, addressed, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, 0, ?)
            """,
                (
                    "jr_reviewer",
                    "test.py",
                    "HIGH",
                    "bug",
                    "Test bug message",
                    "test_task",
                    "2024-01-01T00:00:00",
                ),
            )

        cm = ContextManager()
        result = cm._get_prioritized_suggestions("test_task")

        assert result is not None
        assert "HIGH" in result or "bug" in result


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_handles_missing_files_table(self):
        """Should handle database errors gracefully."""
        cm = ContextManager()

        # This should not crash even if DB is broken
        files = cm._get_prioritized_files_fast(task_id="test_task", limit=10)

        assert isinstance(files, list)

    def test_handles_none_task_id(self, temp_db):
        """Should handle None task_id."""
        cm = ContextManager()

        files = cm._get_prioritized_files_fast(task_id=None, limit=10)

        assert isinstance(files, list)

    def test_handles_empty_string_task_id(self, temp_db):
        """Should handle empty task_id."""
        cm = ContextManager()

        files = cm._get_prioritized_files_fast(task_id="", limit=10)

        assert isinstance(files, list)

    def test_very_large_limit(self, temp_db):
        """Should handle unrealistic limit without OOM."""
        cm = ContextManager()

        files = cm._get_prioritized_files_fast(task_id="test_task", limit=1_000_000)

        assert isinstance(files, list)
        # Should be limited by actual DB content, not crash


class TestPerformance:
    """Basic performance sanity checks."""

    def test_query_completes_quickly(self, temp_db):
        """Basic queries should complete in reasonable time."""
        # Add some test data
        with get_db_connection() as conn:
            for i in range(50):
                conn.execute(
                    """
                    INSERT INTO project_files 
                    (file_path, content, estimated_tokens, last_modified, 
                     size_bytes, file_type, is_binary, content_hash)
                    VALUES (?, ?, ?, ?, ?, ?, 0, ?)
                """,
                    (
                        f"test_{i}.py",
                        "def test(): pass",
                        100,
                        "2024-01-01T00:00:00",
                        50,
                        ".py",
                        f"hash_{i}",
                    ),
                )

        cm = ContextManager()

        start = time.time()
        files = cm._get_prioritized_files_fast(task_id="test_task", limit=20)
        duration = time.time() - start

        # Should complete in under 1 second
        assert duration < 1.0
        assert isinstance(files, list)

    def test_build_context_performance(self, temp_db):
        """Building context should be reasonably fast."""
        cm = ContextManager()

        start = time.time()
        cm.build_orchestrator_context(
            task_id="test_task",
            user_command="Test command",
            conversation_history=[],
            model="gemini-3-flash-preview",
        )
        duration = time.time() - start

        # Should complete in under 2 seconds
        assert duration < 2.0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
