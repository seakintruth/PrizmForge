"""
tests/unit/test_base_agent.py

Unit tests for call_agent using the stdlib LLM mock framework.
No network calls; no pytest-mock / responses dependency.
"""

import json
import pytest


class TestBaseAgentWithMock:
    """Tests for the base agent calling mechanism using mocked LLM."""

    def test_call_agent_returns_scripted_response(self, mock_llm):
        mock_llm.set_response("developer", "def hello(): pass")
        with mock_llm.patch_call_agent():
            from agents.base import call_agent

            result = call_agent(
                agent_name="developer",
                prompt="Write hello",
                task_id="test_task_001",
            )
        assert result == "def hello(): pass"
        assert mock_llm.calls_for("developer")[0].prompt == "Write hello"

    def test_call_agent_json_payload(self, mock_llm):
        payload = {
            "target_file_path": "a.py",
            "summary": "rename",
            "rationale": "consistent naming across module",
            "operations": [
                {
                    "type": "find_replace",
                    "find": "old",
                    "replace": "new",
                    "rationale": "rename identifier",
                }
            ],
        }
        mock_llm.set_response("developer", json.dumps(payload))
        with mock_llm.patch_call_agent():
            from agents.base import call_agent

            result = call_agent("developer", "rename old to new", task_id="t2")
        parsed = json.loads(result)
        assert parsed["operations"][0]["type"] == "find_replace"

    def test_per_agent_responses(self, mock_llm):
        mock_llm.set_response("orchestrator", '{"next_agent": "developer"}')
        mock_llm.set_response(
            "reviewer", '{"decision": "APPROVE", "reason": "looks good"}'
        )
        with mock_llm.patch_call_agent():
            from agents.base import call_agent

            orch = call_agent("orchestrator", "what next?", task_id="t3")
            rev = call_agent("reviewer", "review please", task_id="t3")
        assert json.loads(orch)["next_agent"] == "developer"
        assert json.loads(rev)["decision"] == "APPROVE"
        assert len(mock_llm.calls) == 2

    def test_http_layer_mock(self, mock_openai_chat):
        """HTTP-level mock: requests.post returns a chat completion body."""
        mock_openai_chat(response_text="HTTP_LAYER_OK")
        import agents.base as base_mod

        resp = base_mod.requests.post("http://localhost/v1/chat/completions", json={})
        assert resp.status_code == 200
        assert resp.json()["choices"][0]["message"]["content"] == "HTTP_LAYER_OK"
