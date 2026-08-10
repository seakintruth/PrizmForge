"""
Config / env-driven mock LLM for unattended and local runs without API keys.

Enable with either:
  - env ``PRIZMFORGE_TEST_MODE=1``
  - config ``"llm": { "test_mode": true }``

Optional scripted responses (string or list queue per agent):
  ``"llm": { "test_mode": true, "mock_responses": {
       "orchestrator": [ "{...developer...}", "{...complete...}" ],
       "developer": [ "FILES_NEEDED: ...", "{...operations...}" ],
       "reviewer": "{...APPROVE...}"
  }}``
"""

from __future__ import annotations

import json
import os
from typing import Any

# Per-process queues copied from config lists (pop from front)
_queues: dict[str, list[str]] = {}


def test_mode_enabled(config: dict[str, Any] | None = None) -> bool:
    env = os.environ.get("PRIZMFORGE_TEST_MODE", "").strip().lower()
    if env in ("1", "true", "yes", "on"):
        return True
    if config is None:
        try:
            from core.config import get_config

            config = get_config()
        except Exception:
            return False
    llm = (config or {}).get("llm") or {}
    return bool(llm.get("test_mode"))


def reset_mock_queues() -> None:
    """Clear scripted queues (tests)."""
    _queues.clear()


def _coerce_response(val: Any) -> str:
    if isinstance(val, str):
        return val
    return json.dumps(val)


def _default_response(agent_name: str) -> str:
    name = (agent_name or "").lower()
    if name == "orchestrator":
        return json.dumps(
            {
                "feedback_summary": "test_mode: no backlog action",
                "next_agent": "complete",
                "instructions": "test_mode idle complete",
                "reasoning": "PRIZMFORGE test_mode default",
                "files_needed": [],
                "addressing_feedback_ids": [],
            }
        )
    if name == "developer":
        return json.dumps(
            {
                "target_file_path": "app.py",
                "summary": "test_mode no-op",
                "rationale": "Mock LLM does not edit by default",
                "operations": [],
            }
        )
    if name == "reviewer":
        return json.dumps(
            {
                "decision": "APPROVE",
                "reason": "test_mode auto-approve",
                "suggestions": [],
            }
        )
    if name == "prioritizer":
        return json.dumps({"categorized": []})
    return json.dumps({"findings": [], "notes": f"test_mode default for {agent_name}"})


def mock_call_agent(
    agent_name: str,
    prompt: str,
    task_id: str,
    config: dict[str, Any] | None = None,
) -> str:
    if config is None:
        try:
            from core.config import get_config

            config = get_config()
        except Exception:
            config = {}
    llm = (config or {}).get("llm") or {}
    scripted = llm.get("mock_responses") or {}
    if not isinstance(scripted, dict) or agent_name not in scripted:
        return _default_response(agent_name)

    val = scripted[agent_name]
    # list => queue (initialize once per agent name from config snapshot)
    if isinstance(val, list):
        if agent_name not in _queues:
            _queues[agent_name] = [_coerce_response(x) for x in val]
        if _queues[agent_name]:
            return _queues[agent_name].pop(0)
        # exhausted: last response or default
        if val:
            return _coerce_response(val[-1])
        return _default_response(agent_name)

    return _coerce_response(val)
