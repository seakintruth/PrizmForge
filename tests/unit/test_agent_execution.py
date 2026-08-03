"""
tests/unit/test_agent_execution.py

Stability and routing tests for call_agent under mocked LLM responses.
"""


class TestAgentExecutionBasic:
    """Basic stability tests for call_agent with mocks."""

    def test_call_agent_developer_does_not_crash(self, mock_llm):
        mock_llm.set_response("developer", "print('hello')")
        with mock_llm.patch_call_agent():
            from agents.base import call_agent

            result = call_agent(
                agent_name="developer",
                prompt="Write a hello world function",
                task_id="test_task_basic_1",
            )
        assert result == "print('hello')"

    def test_call_agent_unknown_agent_via_mock(self, mock_llm):
        """Even unknown agent names return the default scripted response when mocked."""
        mock_llm.set_default('{"error": "unknown"}')
        with mock_llm.patch_call_agent():
            from agents.base import call_agent

            result = call_agent(
                agent_name="this_agent_does_not_exist",
                prompt="Test prompt",
                task_id="test_task_basic_2",
            )
        assert result is not None
        assert "unknown" in result or result == mock_llm.default_response

    def test_sequential_orchestrator_turns(self, mock_llm):
        mock_llm.set_responses(
            "orchestrator",
            [
                '{"next_agent": "developer", "instructions": "fix it"}',
                '{"next_agent": "complete", "instructions": "done"}',
            ],
        )
        with mock_llm.patch_call_agent():
            from agents.base import call_agent

            r1 = call_agent("orchestrator", "start", task_id="seq1")
            r2 = call_agent("orchestrator", "continue", task_id="seq1")
        assert "developer" in r1
        assert "complete" in r2
        assert len(mock_llm.calls_for("orchestrator")) == 2
