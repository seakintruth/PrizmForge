"""
tests/mocks/openai.py

Stdlib-only helpers for mocking LLM / OpenAI-compatible chat endpoints.
No dependency on `responses` or `pytest-mock`.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock, patch

# Modules that do `from agents.base import call_agent` must be listed here.
# Integration tests should only patch via MockLLM.patch_call_agent() / this list.
CALL_AGENT_PATCH_TARGETS: tuple[str, ...] = (
    "agents.base.call_agent",
    "agents.orchestrator.call_agent",
    "agents.prioritizer_worker.call_agent",
    "agents.reporter_worker.call_agent",
    "agents.parallel_workers.call_agent",
    "workflow.task_runner.call_agent",
    "workflow.developer_edit.call_agent",
    "agents.archivist_worker.call_agent",
)


def register_call_agent_patch_target(dotted_path: str) -> None:
    """Register a new import site that binds call_agent locally."""
    global CALL_AGENT_PATCH_TARGETS
    if dotted_path not in CALL_AGENT_PATCH_TARGETS:
        CALL_AGENT_PATCH_TARGETS = tuple([*list(CALL_AGENT_PATCH_TARGETS), dotted_path])


# ---------------------------------------------------------------------------
# HTTP-level mock (patches requests.post)
# ---------------------------------------------------------------------------


def make_chat_completion_payload(
    response_text: str,
    model: str = "mock-model",
    finish_reason: str = "stop",
    usage: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Build an OpenAI-compatible chat.completion JSON body."""
    if usage is None:
        usage = {
            "prompt_tokens": 15,
            "completion_tokens": max(1, len(response_text) // 4),
            "total_tokens": 15 + max(1, len(response_text) // 4),
        }
    return {
        "id": "chatcmpl-test-mock",
        "object": "chat.completion",
        "created": 1712345678,
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": response_text},
                "finish_reason": finish_reason,
            }
        ],
        "usage": usage,
    }


def make_requests_response(
    response_text: str,
    status_code: int = 200,
    model: str = "mock-model",
) -> MagicMock:
    """Return a MagicMock that looks like a successful requests.Response."""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = make_chat_completion_payload(response_text, model=model)
    mock_resp.text = json.dumps(mock_resp.json.return_value)
    mock_resp.raise_for_status = MagicMock()
    if status_code >= 400:

        def _raise():
            import requests

            raise requests.exceptions.HTTPError(f"HTTP {status_code}")

        mock_resp.raise_for_status.side_effect = _raise
    return mock_resp


def mock_openai_chat_completion(
    response_text: str,
    model: str = "mock-model",
    status_code: int = 200,
) -> Any:
    """
    Patch `requests.post` (as used by agents.base) to return a fixed completion.

    Returns the mock response object. Use as a context manager via the
    returned patch, or prefer the `mock_llm_http` fixture.
    """
    mock_resp = make_requests_response(response_text, status_code=status_code, model=model)
    return patch("agents.base.requests.post", return_value=mock_resp)


# ---------------------------------------------------------------------------
# High-level scripted mock for call_agent / call_endpoint
# ---------------------------------------------------------------------------


@dataclass
class LLMCallRecord:
    agent_name: str
    prompt: str
    task_id: str | None = None
    model: str | None = None
    response: str | None = None


@dataclass
class MockLLM:
    """
    Scriptable LLM stand-in for tests.

    Usage:
        llm = MockLLM()
        llm.set_response("developer", '{"operations": []}')
        llm.set_responses("orchestrator", [
            '{"next_agent": "developer", ...}',
            '{"next_agent": "complete", ...}',
        ])
        with llm.patch_call_agent():
            ...
    """

    default_response: str = '{"status": "ok"}'
    _queues: dict[str, list[str]] = field(default_factory=dict)
    _defaults: dict[str, str] = field(default_factory=dict)
    calls: list[LLMCallRecord] = field(default_factory=list)

    def set_response(self, agent_name: str, text: str) -> MockLLM:
        """Set a single (or next) response for an agent."""
        self._queues[agent_name] = [text]
        self._defaults[agent_name] = text
        return self

    def set_responses(self, agent_name: str, texts: Sequence[str]) -> MockLLM:
        """Queue sequential responses for an agent (popped FIFO)."""
        self._queues[agent_name] = list(texts)
        if texts:
            self._defaults[agent_name] = texts[-1]
        return self

    def set_default(self, text: str) -> MockLLM:
        self.default_response = text
        return self

    def _next(self, agent_name: str) -> str:
        queue = self._queues.get(agent_name)
        if queue:
            # Keep last response for subsequent calls if queue empties
            if len(queue) == 1:
                return queue[0]
            return queue.pop(0)
        if agent_name in self._defaults:
            return self._defaults[agent_name]
        return self.default_response

    def handler(
        self,
        agent_name: str,
        prompt: str,
        task_id: str | None = None,
        context: Any = None,
        model_override: str | None = None,
        **kwargs,
    ) -> str:
        """Drop-in replacement for agents.base.call_agent."""
        response = self._next(agent_name)
        self.calls.append(
            LLMCallRecord(
                agent_name=agent_name,
                prompt=prompt or "",
                task_id=task_id,
                model=model_override,
                response=response,
            )
        )
        return response

    def endpoint_handler(
        self,
        messages: list[dict],
        max_tokens: int | None = None,
        temperature: float | None = None,
        model: str | None = None,
        **kwargs,
    ):
        """
        Drop-in replacement for agents.base.call_endpoint.
        Returns (response_text, token_count) to match the real signature
        when it returns a tuple; falls back to text-only if needed.
        """
        # Infer agent from message roles if possible; else use default queue
        agent_name = kwargs.get("agent_name") or "endpoint"
        response = self._next(agent_name)
        self.calls.append(
            LLMCallRecord(
                agent_name=agent_name,
                prompt=json.dumps(messages)[:500] if messages else "",
                model=model,
                response=response,
            )
        )
        # call_endpoint typically returns (text, tokens) or text
        tokens = max(1, len(response) // 4)
        return response, tokens

    def patch_call_agent(self):
        """
        Context manager: patch call_agent at definition and common import sites.

        `from agents.base import call_agent` binds a local name, so we must
        patch each consumer module as well as agents.base.
        """
        from contextlib import ExitStack, contextmanager

        targets = CALL_AGENT_PATCH_TARGETS

        @contextmanager
        def _cm():
            with ExitStack() as stack:
                for t in targets:
                    try:
                        stack.enter_context(patch(t, side_effect=self.handler))
                    except Exception:
                        # Module may not be imported yet in some tests
                        pass
                yield self

        return _cm()

    def patch_call_endpoint(self):
        """Context manager: patch agents.base.call_endpoint."""
        return patch("agents.base.call_endpoint", side_effect=self.endpoint_handler)

    def patch_all(self):
        """Patch both call_agent and call_endpoint."""
        from contextlib import ExitStack, contextmanager

        @contextmanager
        def _cm():
            with ExitStack() as stack:
                stack.enter_context(self.patch_call_agent())
                stack.enter_context(self.patch_call_endpoint())
                yield self

        return _cm()

    def calls_for(self, agent_name: str) -> list[LLMCallRecord]:
        return [c for c in self.calls if c.agent_name == agent_name]

    def reset(self) -> None:
        self.calls.clear()
        self._queues.clear()
        self._defaults.clear()
