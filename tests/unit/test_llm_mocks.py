"""
Verify the LLM mocking framework works end-to-end without real network calls.
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestMockLLMScripting:
    def test_set_response_and_handler(self):
        from tests.mocks.openai import MockLLM

        llm = MockLLM()
        llm.set_response("developer", '{"ok": true}')
        out = llm.handler("developer", "do something", task_id="t1")
        assert out == '{"ok": true}'
        assert len(llm.calls) == 1
        assert llm.calls[0].agent_name == "developer"
        assert llm.calls[0].task_id == "t1"

    def test_sequential_responses(self):
        from tests.mocks.openai import MockLLM

        llm = MockLLM()
        llm.set_responses("orchestrator", ["first", "second", "third"])
        assert llm.handler("orchestrator", "p1") == "first"
        assert llm.handler("orchestrator", "p2") == "second"
        assert llm.handler("orchestrator", "p3") == "third"
        # After queue drains, last response is sticky
        assert llm.handler("orchestrator", "p4") == "third"

    def test_default_fallback(self):
        from tests.mocks.openai import MockLLM

        llm = MockLLM().set_default("DEFAULT")
        assert llm.handler("unknown_agent", "x") == "DEFAULT"

    def test_patch_call_agent_context_manager(self):
        from tests.mocks.openai import MockLLM

        llm = MockLLM()
        llm.set_response("developer", "PATCHED_OK")

        with llm.patch_call_agent():
            from agents.base import call_agent

            # May still fail on prompts/config — but if it gets through, response is ours
            # Force direct use of the patched symbol
            import agents.base as base_mod

            result = base_mod.call_agent("developer", "hello", task_id="t")
            assert result == "PATCHED_OK"

        assert llm.calls_for("developer")
        assert llm.calls_for("developer")[0].response == "PATCHED_OK"


class TestMockHttpLayer:
    def test_make_requests_response_shape(self):
        from tests.mocks.openai import make_requests_response

        resp = make_requests_response("hello world")
        assert resp.status_code == 200
        body = resp.json()
        assert body["choices"][0]["message"]["content"] == "hello world"
        assert "usage" in body

    def test_mock_openai_chat_fixture(self, mock_openai_chat):
        mock_openai_chat(response_text="FIXTURE_RESPONSE")
        import agents.base as base_mod

        # Direct call to the patched requests.post
        r = base_mod.requests.post("http://example.com", json={})
        assert r.status_code == 200
        assert r.json()["choices"][0]["message"]["content"] == "FIXTURE_RESPONSE"

    def test_mock_llm_fixture(self, mock_llm):
        mock_llm.set_response("reviewer", '{"decision": "APPROVE"}')
        with mock_llm.patch_call_agent():
            import agents.base as base_mod

            result = base_mod.call_agent("reviewer", "review this", task_id="t2")
            assert json.loads(result)["decision"] == "APPROVE"

    def test_mock_llm_patched_fixture(self, mock_llm_patched):
        mock_llm_patched.set_response("orchestrator", '{"next_agent": "complete"}')
        import agents.base as base_mod

        result = base_mod.call_agent("orchestrator", "done?", task_id="t3")
        assert "complete" in result
        assert mock_llm_patched.calls_for("orchestrator")


class TestNoNetworkLeak:
    """Ensure mocked call_agent never hits the network."""

    def test_call_agent_mock_blocks_requests(self, mock_llm):
        mock_llm.set_response("developer", "no-network")

        def boom(*args, **kwargs):
            raise AssertionError(
                "requests.post must not be called when call_agent is mocked"
            )

        with patch("agents.base.requests.post", side_effect=boom):
            with mock_llm.patch_call_agent():
                import agents.base as base_mod

                result = base_mod.call_agent("developer", "x", task_id="t4")
                assert result == "no-network"
