"""
Pytest fixtures for PrizmForge tests.

Isolation rules:
- Never write agents.db, reports, or exports into the real repo tree.
- Every test gets a private temp workspace (project + .PrizmForge).
- DB schema is initialized only when a test requests temp_db (or via
  fixtures that depend on it), so pure unit tests stay fast.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Repo-local paths that must never be used as test side-effect targets
_REPO_PRIZMFORGE = PROJECT_ROOT / ".PrizmForge"


@pytest.fixture(autouse=True)
def _isolate_prizmforge_workspace(tmp_path_factory, monkeypatch):
    """
    Force all tests into a per-test temp workspace.

    Sets:
      - PRIZMFORGE_DB_PATH → <tmp>/.PrizmForge/agents.db
      - core.config.get_config() project_directory → <tmp>/project

    Does NOT call init_db (keeps pure unit tests light). Tests that touch
    the DB should request the temp_db fixture (or one that depends on it).
    """
    base = tmp_path_factory.mktemp("prizmforge_ws")
    project = base / "project"
    project.mkdir(parents=True, exist_ok=True)
    prizm = base / ".PrizmForge"
    prizm.mkdir(parents=True, exist_ok=True)
    reports = prizm / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    db_path = prizm / "agents.db"

    monkeypatch.setenv("PRIZMFORGE_DB_PATH", str(db_path))
    monkeypatch.setenv("PRIZMFORGE_TEST_PROJECT_DIR", str(project))
    monkeypatch.setenv("PRIZMFORGE_TEST_WORKSPACE", str(base))

    from core import config as core_config

    _orig_get_config = core_config.get_config

    def _isolated_get_config():
        try:
            cfg = _orig_get_config()
        except Exception:
            cfg = {}
        if not isinstance(cfg, dict):
            cfg = {}
        out = dict(cfg)
        out["project_directory"] = str(project)
        out.setdefault("git", False)
        out.setdefault("git_auto_commit", False)
        out.setdefault("background_agents_enabled", False)
        return out

    monkeypatch.setattr(core_config, "get_config", _isolated_get_config)

    yield {
        "base": base,
        "project": project,
        "prizmforge": prizm,
        "db_path": db_path,
        "reports": reports,
    }

    if _REPO_PRIZMFORGE.exists():
        agents = _REPO_PRIZMFORGE / "agents.db"
        if agents.exists() and agents.stat().st_size == 0:
            try:
                agents.unlink()
            except OSError:
                pass


@pytest.fixture(scope="function")
def temp_db(monkeypatch, _isolate_prizmforge_workspace):
    """
    Fresh temp database with full schema for one test.

    Uses the autouse workspace's PRIZMFORGE_DB_PATH, then runs init_db().
    """
    db_path = str(_isolate_prizmforge_workspace["db_path"])
    monkeypatch.setenv("PRIZMFORGE_DB_PATH", db_path)

    p = Path(db_path)
    if p.exists():
        try:
            p.unlink()
        except OSError:
            pass
    p.parent.mkdir(parents=True, exist_ok=True)

    from core.db import init_db

    init_db()

    yield db_path

    try:
        if p.exists():
            p.unlink()
    except OSError:
        pass


@pytest.fixture
def mock_minimal_config(monkeypatch, _isolate_prizmforge_workspace):
    """
    Minimal valid configuration pointed at the isolated temp project.

    No shared /tmp/test_project — each test gets its own directory under
    the autouse workspace.
    """
    from core import config as core_config

    project_dir = str(_isolate_prizmforge_workspace["project"])
    Path(project_dir).mkdir(parents=True, exist_ok=True)

    minimal_config = {
        "project_directory": project_dir,
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
        "token_budget": {"max_tokens_per_4h": 1_000_000},
        "default_model": "mock-model",
    }

    monkeypatch.setattr(core_config, "get_config", lambda: minimal_config)
    return minimal_config


@pytest.fixture
def isolated_project(mock_minimal_config, temp_db, _isolate_prizmforge_workspace):
    """
    Full isolation pack: config + initialized DB + project path.

    Prefer this for worker/lifecycle/integration-style tests.
    """
    return {
        "config": mock_minimal_config,
        "db_path": temp_db,
        "project": _isolate_prizmforge_workspace["project"],
        "workspace": _isolate_prizmforge_workspace["base"],
        "reports": _isolate_prizmforge_workspace["reports"],
    }


@pytest.fixture
def capsys_and_temp_db(temp_db, capsys):
    """Convenience fixture that combines temp DB + output capture."""
    return {"db_path": temp_db, "capsys": capsys}


@pytest.fixture
def mock_openai_chat(monkeypatch):
    """
    Mock OpenAI-compatible chat completion at the HTTP layer (requests.post).

    Stdlib-only — does not require pytest-mock or responses.
    """
    from tests.mocks.openai import make_requests_response

    state = {"response_text": "Mocked response", "status_code": 200}

    def _fake_post(*args, **kwargs):
        return make_requests_response(
            state["response_text"],
            status_code=state["status_code"],
        )

    monkeypatch.setattr("agents.base.requests.post", _fake_post)
    try:
        import requests as _requests

        monkeypatch.setattr(_requests, "post", _fake_post)
    except Exception as e:
        print(f"    ⚠️  Exception handled in conftest.py: {e}")

    def _configure(response_text: str = "Mocked response", status_code: int = 200):
        state["response_text"] = response_text
        state["status_code"] = status_code
        return state

    return _configure


@pytest.fixture
def mock_llm():
    """
    High-level scriptable LLM mock (patches call_agent / call_endpoint).
    """
    from tests.mocks.openai import MockLLM

    return MockLLM()


@pytest.fixture
def mock_llm_patched(mock_llm):
    """
    Same as mock_llm, but already patches call_agent for the duration of the test.
    """
    with mock_llm.patch_call_agent():
        yield mock_llm
