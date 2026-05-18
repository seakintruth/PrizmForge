"""
tests/conftest.py

Shared pytest fixtures for PrizmForge.

Includes:
- A reusable mock for OpenAI-compatible /chat/completions endpoint
- Database fixtures (when needed)
"""

import pytest
import responses
from typing import Callable, Dict, Any, Optional


# =============================================================================
# OpenAI-compatible Chat Mock
# =============================================================================

@pytest.fixture
def mock_openai_chat():
    """
    Pytest fixture that mocks an OpenAI-style chat completions endpoint.

    Usage:
        def test_something(mock_openai_chat):
            mock_openai_chat(response_text="Hello from mock!")
            # Now any call to the OpenAI endpoint will return the mocked response
    """
    @responses.activate
    def _mock(response_text: str = "This is a mocked response.", 
              model: str = "mock-model",
              finish_reason: str = "stop",
              usage: Optional[Dict[str, int]] = None) -> None:
        """
        Activate the mock and set the response.

        Args:
            response_text: The content the model should "return"
            model: Model name to echo back
            finish_reason: Usually "stop"
            usage: Optional token usage dict
        """
        if usage is None:
            usage = {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}

        mock_response = {
            "id": "chatcmpl-mock123",
            "object": "chat.completion",
            "created": 1712345678,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": response_text
                    },
                    "finish_reason": finish_reason
                }
            ],
            "usage": usage
        }

        responses.add(
            responses.POST,
            "https://api.openai.com/v1/chat/completions",  # Common base - adjust per endpoint config
            json=mock_response,
            status=200,
            content_type="application/json"
        )

        # Also support common alternative base URLs used in the project
        responses.add(
            responses.POST,
            "https://api.example.com/v1/chat/completions",
            json=mock_response,
            status=200,
            content_type="application/json"
        )

    return _mock


# =============================================================================
# Future fixtures (examples)
# =============================================================================

@pytest.fixture
def sample_task_id() -> str:
    """Provide a consistent task ID for tests."""
    return "test_task_001"


# =============================================================================
# CLI / Database Testing Fixtures
# =============================================================================

@pytest.fixture(scope="function")
def temp_db(monkeypatch):
    """
    Creates a fresh temporary database and sets PRIZMFORGE_DB_PATH
    so that get_db_connection() uses it.
    
    Deletes any existing database at the target path before initialization
    to ensure a clean state between test runs.
    """
    import tempfile
    import os
    from core.db import init_db   # Use consolidated initializer

    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    # Delete if it somehow already exists (defensive)
    if os.path.exists(db_path):
        try:
            os.unlink(db_path)
        except OSError:
            pass

    monkeypatch.setenv("PRIZMFORGE_DB_PATH", db_path)

    # Initialize full consolidated schema
    init_db()

    yield db_path

    # Cleanup after test
    try:
        if os.path.exists(db_path):
            os.unlink(db_path)
    except OSError:
        pass


@pytest.fixture
def mock_minimal_config(monkeypatch):
    """
    Provides a minimal valid configuration for tests.
    """
    from core import config as core_config

    minimal_config = {
        "project_directory": "/tmp/test_project",
        "git": False,
        "git_auto_commit": False,
        "background_agents_enabled": False,
        "default_endpoint": "mock",
        "endpoints": {
            "mock": {
                "base_url": "http://localhost:9999/v1/chat/completions",
                "api_key_name": "mock_key",
                "include_model_in_payload": True,
                "response_path": ["choices", 0, "message", "content"],
                "priority": 10
            }
        },
        "models": {
            "mock-model": {
                "endpoint": "mock",
                "max_output_tokens": 1024,
                "temperature": 0.5
            }
        }
    }

    monkeypatch.setattr(core_config, "get_config", lambda: minimal_config)
    return minimal_config


@pytest.fixture
def capsys_and_temp_db(temp_db, capsys):
    """Convenience fixture that combines temp DB + output capture."""
    return {"db_path": temp_db, "capsys": capsys}