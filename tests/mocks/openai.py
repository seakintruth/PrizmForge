"""
tests/mocks/openai.py

Reusable helpers for mocking OpenAI-compatible chat endpoints.

This module can be expanded later when you implement full endpoint support.
"""

from typing import Dict, Any, Optional
import responses


def mock_openai_chat_completion(
    response_text: str,
    model: str = "mock-gpt-4",
    status_code: int = 200,
    finish_reason: str = "stop",
    usage: Optional[Dict[str, int]] = None,
    base_url: str = "https://api.openai.com/v1/chat/completions"
) -> None:
    """
    Manually mock an OpenAI /chat/completions response.

    Useful when you need more control than the fixture provides.
    """
    if usage is None:
        usage = {"prompt_tokens": 15, "completion_tokens": 25, "total_tokens": 40}

    payload = {
        "id": "chatcmpl-test-mock",
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
                "finish_reason": finish_reason,
            }
        ],
        "usage": usage,
    }

    responses.add(
        responses.POST,
        base_url,
        json=payload,
        status=status_code,
        content_type="application/json"
    )
