"""
P1.1 — Orchestrator decision matrix under MockLLM.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def orch_env(temp_db, monkeypatch, mock_minimal_config):
    from core import config as config_mod

    base = {
        "project_directory": "./project",
        "background_agents_enabled": False,
        "min_iterations_before_complete": 3,
        "token_budget": {"max_tokens_per_4h": 1_000_000},
        "default_model": "mock-model",
        "agent_model_preferences": {},
        "endpoints": {},
        "cli_mode": {"mode": "semi_attended"},
    }

    def fake():
        return dict(base)

    monkeypatch.setattr(config_mod, "get_config", fake)
    return base


def _decision(**kwargs):
    d = {
        "feedback_summary": "test",
        "next_agent": "developer",
        "instructions": "do work",
        "reasoning": "because",
        "files_needed": ["a.py"],
        "addressing_feedback_ids": [],
        "model": None,
    }
    d.update(kwargs)
    return json.dumps(d)


def test_orchestrator_routes_developer(mock_llm, orch_env, temp_db):
    from agents.orchestrator import call_orchestrator

    mock_llm.set_response("orchestrator", _decision(next_agent="developer", files_needed=["x.py"]))
    with mock_llm.patch_call_agent():
        with patch("agents.orchestrator.get_context_manager") as gcm:
            gcm.return_value.build_orchestrator_context.return_value = (
                "ctx",
                {
                    "tokens_used": 10,
                    "context_limit": 100000,
                    "context_utilization": 0.01,
                    "files_included": [],
                    "files_excluded": [],
                    "truncation_reason": None,
                },
            )
            # db_connection import may be missing in orchestrator - patch if needed
            decision = call_orchestrator("t1", "cmd", [], 1, 10, 5.0)
    assert decision is not None
    assert decision.get("next_agent") == "developer"
    assert "x.py" in (decision.get("files_needed") or [])


def test_orchestrator_routes_complete(mock_llm, orch_env, temp_db):
    from agents.orchestrator import call_orchestrator

    mock_llm.set_response(
        "orchestrator",
        _decision(next_agent="complete", instructions="done", files_needed=[]),
    )
    with mock_llm.patch_call_agent():
        with patch("agents.orchestrator.get_context_manager") as gcm:
            gcm.return_value.build_orchestrator_context.return_value = (
                "ctx",
                {
                    "tokens_used": 10,
                    "context_limit": 100000,
                    "context_utilization": 0.01,
                    "files_included": [],
                    "files_excluded": [],
                    "truncation_reason": None,
                },
            )
            decision = call_orchestrator("t2", "cmd", [], 5, 10, 5.0)
    assert decision is not None
    assert decision.get("next_agent") == "complete"


def test_orchestrator_routes_background(mock_llm, orch_env, temp_db):
    from agents.orchestrator import call_orchestrator

    mock_llm.set_response(
        "orchestrator",
        _decision(next_agent="background", instructions="scan", files_needed=[]),
    )
    with mock_llm.patch_call_agent():
        with patch("agents.orchestrator.get_context_manager") as gcm:
            gcm.return_value.build_orchestrator_context.return_value = (
                "ctx",
                {
                    "tokens_used": 10,
                    "context_limit": 100000,
                    "context_utilization": 0.01,
                    "files_included": [],
                    "files_excluded": [],
                    "truncation_reason": None,
                },
            )
            decision = call_orchestrator("t3", "cmd", [], 2, 10, 5.0)
    assert decision is not None
    assert decision.get("next_agent") == "background"


def test_orchestrator_invalid_json_returns_none_or_empty(mock_llm, orch_env, temp_db):
    from agents.orchestrator import call_orchestrator

    mock_llm.set_response("orchestrator", "NOT JSON AT ALL {{{")
    with mock_llm.patch_call_agent():
        with patch("agents.orchestrator.get_context_manager") as gcm:
            gcm.return_value.build_orchestrator_context.return_value = (
                "ctx",
                {
                    "tokens_used": 10,
                    "context_limit": 100000,
                    "context_utilization": 0.01,
                    "files_included": [],
                    "files_excluded": [],
                    "truncation_reason": None,
                },
            )
            decision = call_orchestrator("t4", "cmd", [], 1, 10, 5.0)
    # parse_json_response returns None on hard failure
    assert decision is None or decision.get("next_agent") is None


def test_orchestrator_empty_agent_response(mock_llm, orch_env, temp_db):
    from agents.orchestrator import call_orchestrator

    mock_llm.set_response("orchestrator", "")
    # empty string may still be returned by handler - set queue to empty response
    mock_llm._queues["orchestrator"] = [""]
    with mock_llm.patch_call_agent():
        with patch("agents.orchestrator.get_context_manager") as gcm:
            gcm.return_value.build_orchestrator_context.return_value = (
                "ctx",
                {
                    "tokens_used": 1,
                    "context_limit": 100000,
                    "context_utilization": 0.0,
                    "files_included": [],
                    "files_excluded": [],
                    "truncation_reason": None,
                },
            )
            decision = call_orchestrator("t5", "cmd", [], 1, 10, 5.0)
    assert decision is None

def test_orchestrator_cold_start_short_circuit(temp_db, orch_env):
  """When project directory has 0 files and 0 backlog, route to developer without LLM call."""
  from agents.orchestrator import call_orchestrator

  with patch("agents.orchestrator.get_context_manager") as gcm:
    gcm.return_value.build_orchestrator_context.return_value = (
        "ctx",
        {
            "tokens_used": 10,
            "context_limit": 100000,
            "context_utilization": 0.01,
            "total_project_files": 0,  # Cold start
            "files_included": [],
            "files_excluded": [],
        },
    )
    decision = call_orchestrator("t_cold", "Build Shiny app", [], 1, 5, 5.0)

  assert decision is not None
  assert decision["next_agent"] == "developer"
  assert "Programmatic short-circuit" in decision["reasoning"]


def test_orchestrator_background_disabled_override(
    mock_llm, temp_db, orch_env, monkeypatch
):
  """When background_agents_enabled=False, override LLM decision from background to developer."""
  from agents.orchestrator import call_orchestrator
  from core import config as config_mod

  # Force background_agents_enabled = False
  original_get_config = config_mod.get_config

  def fake_config():

    c = dict(original_get_config())
    c["background_agents_enabled"] = False
    return c

  monkeypatch.setattr(config_mod, "get_config", fake_config)

  # Mock LLM returning 'background'
  mock_llm.set_response("orchestrator", '{"next_agent": "background"}')

  with mock_llm.patch_call_agent():
    with patch("agents.orchestrator.get_context_manager") as gcm:
      gcm.return_value.build_orchestrator_context.return_value = (
          "ctx",
          {
              "tokens_used": 10,
              "context_limit": 100000,
              "context_utilization": 0.01,
              "total_project_files": 1,
              "files_included": [{"path": "app.py"}],
              "files_excluded": [],
          },
      )
      decision = call_orchestrator("t_override", "Build app", [], 1, 5, 5.0)

  assert decision["next_agent"] == "developer"
  assert "Overridden: background_agents_enabled is False" in decision["reasoning"]
