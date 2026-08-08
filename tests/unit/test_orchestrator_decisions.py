"""
Unit tests for Orchestrator decision logic.
"""

import json
from unittest.mock import patch

from agents.orchestrator import call_orchestrator


def _decision(next_agent="developer", instructions="do work", files_needed=None):
    return json.dumps(
        {
            "feedback_summary": "test",
            "next_agent": next_agent,
            "instructions": instructions,
            "reasoning": "because",
            "files_needed": files_needed or [],
            "addressing_feedback_ids": [],
            "model": None,
        }
    )


def test_orchestrator_routes_developer(mock_llm, mock_minimal_config, temp_db):
    mock_llm.set_response("orchestrator", _decision(next_agent="developer", files_needed=["x.py"]))
    with mock_llm.patch_call_agent():
        with patch("agents.orchestrator.get_context_manager") as gcm:
            gcm.return_value.build_orchestrator_context.return_value = (
                "ctx",
                {
                    "tokens_used": 10,
                    "context_limit": 100000,
                    "context_utilization": 0.01,
                    "total_project_files": 1,
                    "files_included": ["x.py"],
                    "files_excluded": [],
                    "truncation_reason": None,
                },
            )
            decision = call_orchestrator("t1", "cmd", [], 1, 10, 5.0)

    assert decision is not None
    assert decision.get("next_agent") == "developer"
    assert "x.py" in (decision.get("files_needed") or [])


def test_orchestrator_routes_complete(mock_llm, mock_minimal_config, temp_db):
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
                    "total_project_files": 1,
                    "files_included": ["app.py"],
                    "files_excluded": [],
                    "truncation_reason": None,
                },
            )
            decision = call_orchestrator("t2", "cmd", [], 5, 10, 5.0)

    assert decision is not None
    assert decision.get("next_agent") == "complete"


def test_orchestrator_routes_background(mock_llm, mock_minimal_config, temp_db):
    bg_config = dict(mock_minimal_config)
    bg_config["background_agents_enabled"] = True

    mock_llm.set_response(
        "orchestrator",
        _decision(next_agent="background", instructions="scan", files_needed=[]),
    )
    with mock_llm.patch_call_agent():
        with patch("agents.orchestrator.get_config", return_value=bg_config):
            with patch("agents.orchestrator.get_context_manager") as gcm:
                gcm.return_value.build_orchestrator_context.return_value = (
                    "ctx",
                    {
                        "tokens_used": 10,
                        "context_limit": 100000,
                        "context_utilization": 0.01,
                        "total_project_files": 5,
                        "files_included": ["app.py"],
                        "files_excluded": [],
                        "truncation_reason": None,
                    },
                )
                decision = call_orchestrator("t3", "cmd", [], 2, 10, 5.0)

    assert decision is not None
    assert decision.get("next_agent") == "background"


def test_orchestrator_invalid_json_returns_none_or_empty(mock_llm, mock_minimal_config, temp_db):
    mock_llm.set_response("orchestrator", "NOT JSON AT ALL {{{")
    with mock_llm.patch_call_agent():
        with patch("agents.orchestrator.get_context_manager") as gcm:
            gcm.return_value.build_orchestrator_context.return_value = (
                "ctx",
                {
                    "tokens_used": 10,
                    "context_limit": 100000,
                    "context_utilization": 0.01,
                    "total_project_files": 1,
                    "files_included": ["app.py"],
                    "files_excluded": [],
                    "truncation_reason": None,
                },
            )
            decision = call_orchestrator("t4", "cmd", [], 1, 10, 5.0)

    assert decision is None or decision.get("next_agent") is None


def test_orchestrator_empty_agent_response(mock_llm, mock_minimal_config, temp_db):
    mock_llm.set_response("orchestrator", "")
    mock_llm._queues["orchestrator"] = [""]
    with mock_llm.patch_call_agent():
        with patch("agents.orchestrator.get_context_manager") as gcm:
            gcm.return_value.build_orchestrator_context.return_value = (
                "ctx",
                {
                    "tokens_used": 1,
                    "context_limit": 100000,
                    "context_utilization": 0.0,
                    "total_project_files": 1,
                    "files_included": ["app.py"],
                    "files_excluded": [],
                    "truncation_reason": None,
                },
            )
            decision = call_orchestrator("t5", "cmd", [], 1, 10, 5.0)

    assert decision is None


def test_orchestrator_cold_start_short_circuit(temp_db, mock_minimal_config):
    """When project directory has 0 files and 0 backlog, route to developer without LLM call."""
    with patch("agents.orchestrator.get_context_manager") as gcm:
        gcm.return_value.build_orchestrator_context.return_value = (
            "ctx",
            {
                "tokens_used": 10,
                "context_limit": 100000,
                "context_utilization": 0.01,
                "total_project_files": 0,  # Cold start (0 files)
                "files_included": [],
                "files_excluded": [],
            },
        )
        decision = call_orchestrator("t_cold", "Build Shiny app", [], 1, 5, 5.0)

    assert decision is not None
    assert decision.get("next_agent") == "developer"
    assert "Cold start" in decision.get("feedback_summary", "")


def test_orchestrator_background_disabled_override(mock_llm, mock_minimal_config, temp_db):
    bg_config = dict(mock_minimal_config)
    bg_config["background_agents_enabled"] = False

    mock_llm.set_response(
        "orchestrator",
        _decision(next_agent="background", instructions="scan", files_needed=[]),
    )
    with mock_llm.patch_call_agent():
        with patch("agents.orchestrator.get_config", return_value=bg_config):
            with patch("agents.orchestrator.get_context_manager") as gcm:
                gcm.return_value.build_orchestrator_context.return_value = (
                    "ctx",
                    {
                        "tokens_used": 10,
                        "context_limit": 100000,
                        "context_utilization": 0.01,
                        "total_project_files": 5,
                        "files_included": ["app.py"],
                        "files_excluded": [],
                        "truncation_reason": None,
                    },
                )
                decision = call_orchestrator("t6", "cmd", [], 2, 10, 5.0)

    assert decision is not None
    assert decision.get("next_agent") == "developer"
    assert "Overridden" in decision.get("reasoning", "")
