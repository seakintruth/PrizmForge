"""
tests/unit/test_json_repair.py

Unit tests for the controlled one-shot JSON repair path in agents.base.call_agent.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest


VALID_ORCH_JSON = json.dumps(
    {
        "feedback_summary": "ok",
        "next_agent": "developer",
        "instructions": "do the thing",
        "reasoning": "backlog has items",
        "files_needed": [],
        "addressing_feedback_ids": [],
    }
)

MARKDOWN_ANALYSIS = """### Peer Review: Governed Editing Path
Based on a comprehensive review of the governed editing flow,
I recommend calling the developer next.
"""


@pytest.fixture
def stub_agent_deps(monkeypatch):
    """Minimal stubs so call_agent can run without network or real config."""
    prompts = {
        "orchestrator": {"system_prompt": "You are the orchestrator. Respond with JSON only."},
        "developer": {"system_prompt": "You are the developer. Respond with JSON only."},
        "reviewer": {"system_prompt": "You are the reviewer. Free-form text is fine."},
        "prioritizer": {"system_prompt": "You are the prioritizer. Respond with JSON only."},
    }
    monkeypatch.setattr("agents.base.get_agent_prompts", lambda: prompts)

    # Avoid real endpoint / schema / archive / conversation side effects
    monkeypatch.setattr(
        "agents.base.get_endpoint_manager",
        lambda: MagicMock(
            validate_model=lambda m: m or "mock-model",
            get_endpoint_for_model=lambda m: MagicMock(name="mock"),
        ),
    )
    monkeypatch.setattr(
        "core.agent_schemas.get_schema_example",
        lambda name: '{"example": true}',
    )
    monkeypatch.setattr("core.archival.archive_raw_response", lambda *a, **k: None)
    monkeypatch.setattr("agents.base.save_conversation", lambda *a, **k: None)

    # Disable test_mode short-circuit
    monkeypatch.setattr(
        "core.llm_test_mode.test_mode_enabled",
        lambda cfg: False,
        raising=False,
    )

    # Minimal config
    from core import config as config_mod

    cfg = {
        "project_directory": "/tmp/test_project",
        "default_model": "mock-model",
        "agent_model_preferences": {
            "orchestrator": "mock-model",
            "developer": "mock-model",
            "reviewer": "mock-model",
            "prioritizer": "mock-model",
        },
        "token_budget": {"max_tokens_per_4h": 50_000_000},
    }
    monkeypatch.setattr(config_mod, "get_config", lambda: cfg)
    monkeypatch.setattr("agents.base.get_config", lambda: cfg)

    # Suppress resource controller noise
    monkeypatch.setattr(
        "agents.resource_controller_worker.get_resource_controller",
        lambda: MagicMock(
            get_model_override=lambda n: None,
            update_agent_performance=lambda *a, **k: None,
        ),
        raising=False,
    )


class TestJsonRepair:
    def test_valid_json_skips_repair(self, stub_agent_deps, monkeypatch):
        """Already-valid JSON must not trigger a repair call."""
        calls = []

        def fake_endpoint(messages, **kwargs):
            calls.append("endpoint")
            return VALID_ORCH_JSON, 50

        monkeypatch.setattr("agents.base.call_endpoint", fake_endpoint)

        from agents.base import call_agent

        result = call_agent("orchestrator", "what next?", task_id="t1", auto_resume=False)
        assert result == VALID_ORCH_JSON
        assert len(calls) == 1  # no repair call

    def test_malformed_triggers_one_repair(self, stub_agent_deps, monkeypatch):
        """Markdown / non-JSON response should trigger exactly one repair attempt."""
        responses = [MARKDOWN_ANALYSIS, VALID_ORCH_JSON]
        calls = {"n": 0}

        def fake_endpoint(messages, **kwargs):
            idx = min(calls["n"], len(responses) - 1)
            calls["n"] += 1
            return responses[idx], 80

        monkeypatch.setattr("agents.base.call_endpoint", fake_endpoint)

        from agents.base import call_agent

        result = call_agent("orchestrator", "what next?", task_id="t2", auto_resume=False)
        assert calls["n"] == 2  # original + one repair
        parsed = json.loads(result)
        assert parsed["next_agent"] == "developer"

    def test_repair_failure_keeps_original(self, stub_agent_deps, monkeypatch):
        """If the repair also fails to parse, the original response is kept."""
        responses = [MARKDOWN_ANALYSIS, "still not json at all"]
        calls = {"n": 0}

        def fake_endpoint(messages, **kwargs):
            idx = min(calls["n"], len(responses) - 1)
            calls["n"] += 1
            return responses[idx], 40

        monkeypatch.setattr("agents.base.call_endpoint", fake_endpoint)

        from agents.base import call_agent

        result = call_agent("orchestrator", "what next?", task_id="t3", auto_resume=False)
        assert calls["n"] == 2
        assert result == MARKDOWN_ANALYSIS  # original preserved

    def test_text_output_agent_skips_repair(self, stub_agent_deps, monkeypatch):
        """reviewer / project_reporter / archivist must never trigger JSON repair."""
        calls = {"n": 0}

        def fake_endpoint(messages, **kwargs):
            calls["n"] += 1
            return "This is a free-form review. Looks fine overall.", 30

        monkeypatch.setattr("agents.base.call_endpoint", fake_endpoint)

        from agents.base import call_agent

        result = call_agent("reviewer", "please review", task_id="t4", auto_resume=False)
        assert calls["n"] == 1  # no repair
        assert "free-form review" in result

    def test_is_repair_attempt_prevents_recursion(self, stub_agent_deps, monkeypatch):
        """_is_repair_attempt=True must not attempt another repair."""
        calls = {"n": 0}

        def fake_endpoint(messages, **kwargs):
            calls["n"] += 1
            return MARKDOWN_ANALYSIS, 20

        monkeypatch.setattr("agents.base.call_endpoint", fake_endpoint)

        from agents.base import call_agent

        result = call_agent(
            "orchestrator",
            "repair me",
            task_id="t5",
            auto_resume=False,
            _is_repair_attempt=True,
        )
        assert calls["n"] == 1  # no second repair
        assert result == MARKDOWN_ANALYSIS

    def test_empty_response_skips_repair(self, stub_agent_deps, monkeypatch):
        """Empty / whitespace-only responses should not trigger repair."""
        calls = {"n": 0}

        def fake_endpoint(messages, **kwargs):
            calls["n"] += 1
            return "   \n  ", 5

        monkeypatch.setattr("agents.base.call_endpoint", fake_endpoint)

        from agents.base import call_agent

        result = call_agent("orchestrator", "what next?", task_id="t6", auto_resume=False)
        assert calls["n"] == 1
        assert result.strip() == ""
