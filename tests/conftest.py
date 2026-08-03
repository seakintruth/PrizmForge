"""
Pytest fixtures for PrizmForge tests
Minimal version - no external dependencies beyond pytest
"""

import pytest
import tempfile
import os
import sys
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(scope="function")
def temp_db(monkeypatch):
    """
    Creates a fresh temporary database for each test.
    No external dependencies.
    """
    import tempfile
    import os

    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    # Delete if exists (defensive)
    if os.path.exists(db_path):
        try:
            os.unlink(db_path)
        except OSError:
            pass

    # Set environment variable so get_db_path() uses our temp DB
    monkeypatch.setenv("PRIZMFORGE_DB_PATH", db_path)

    # Initialize schema
    from core.db import init_db

    init_db()

    yield db_path

    # Cleanup
    try:
        if os.path.exists(db_path):
            os.unlink(db_path)
    except OSError:
        pass


@pytest.fixture
def tmp_path():
    """Provide a temporary directory (built-in alternative)"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_minimal_config(monkeypatch):
    """
    Provides a minimal valid configuration for tests.
    No external dependencies - uses unittest.mock.
    """
    from core import config as core_config

    minimal_config = {
        "project_directory": tempfile.gettempdir() + "/test_project",
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
                "priority": 10,
                "rate_limit_per_minute": 60,
            }
        },
        "models": {
            "mock-model": {
                "endpoint": "mock",
                "max_output_tokens": 1024,
                "max_context_tokens": 100000,
                "temperature": 0.5,
            }
        },
        "agent_model_preferences": {
            "developer": "mock-model",
            "reviewer": "mock-model",
            "orchestrator": "mock-model",
        },
    }

    monkeypatch.setattr(core_config, "get_config", lambda: minimal_config)
    return minimal_config


@pytest.fixture
def capsys_and_temp_db(temp_db, capsys):
    """Convenience fixture that combines temp DB + output capture."""
    return {"db_path": temp_db, "capsys": capsys}


@pytest.fixture
def mock_openai_chat(monkeypatch):
    """
    Mock OpenAI-compatible chat completion at the HTTP layer (requests.post).

    Stdlib-only — does not require pytest-mock or responses.

    Usage:
        mock_openai_chat(response_text='{"next_agent": "complete"}')
        # subsequent call_agent / call_endpoint traffic uses this response
    """
    from tests.mocks.openai import make_requests_response

    state = {"response_text": "Mocked response", "status_code": 200}

    def _fake_post(*args, **kwargs):
        return make_requests_response(
            state["response_text"],
            status_code=state["status_code"],
        )

    monkeypatch.setattr("agents.base.requests.post", _fake_post)
    # Also patch the top-level name in case other modules import requests
    try:
        import requests as _requests

        monkeypatch.setattr(_requests, "post", _fake_post)
    except Exception:
        pass

    def _configure(response_text: str = "Mocked response", status_code: int = 200):
        state["response_text"] = response_text
        state["status_code"] = status_code
        return state

    return _configure


@pytest.fixture
def mock_llm():
    """
    High-level scriptable LLM mock (patches call_agent / call_endpoint).

    Usage:
        def test_flow(mock_llm):
            mock_llm.set_response("orchestrator", '{"next_agent": "developer", ...}')
            mock_llm.set_responses("developer", [
                "FILES_NEEDED: a.py\\nPLAN: rename",
                '{"target_file_path": "a.py", "find": "old", "replace": "new"}',
            ])
            mock_llm.set_response("reviewer", '{"decision": "APPROVE", "reason": "ok"}')
            with mock_llm.patch_call_agent():
                ...
    """
    from tests.mocks.openai import MockLLM

    return MockLLM()


@pytest.fixture
def mock_llm_patched(mock_llm):
    """
    Same as mock_llm, but already patches call_agent for the duration of the test.
    Yields the MockLLM instance.
    """
    with mock_llm.patch_call_agent():
        yield mock_llm
