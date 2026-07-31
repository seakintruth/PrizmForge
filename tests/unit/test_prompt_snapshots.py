"""
Phase 6 — Prompt snapshot / regression guards (stdlib only).

Ensures critical agent prompts still contain required mode and format
instructions after refactors. No snapshot library required.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

PROMPTS_PATH = PROJECT_ROOT / "agent_prompts.json"


@pytest.fixture(scope="module")
def prompts():
    assert PROMPTS_PATH.exists(), "agent_prompts.json missing"
    data = json.loads(PROMPTS_PATH.read_text(encoding="utf-8"))
    return data


def _system(prompts, agent: str) -> str:
    entry = prompts.get(agent)
    assert entry is not None, f"missing agent prompt: {agent}"
    text = entry.get("system_prompt") or entry.get("prompt") or ""
    assert isinstance(text, str) and len(text) > 50, f"{agent} system_prompt too short"
    return text


class TestDeveloperPrompt:
    def test_requires_json_and_operations(self, prompts):
        text = _system(prompts, "developer").lower()
        assert "json" in text
        assert "operation" in text

    def test_mentions_edit_modes(self, prompts):
        text = _system(prompts, "developer")
        # At least one multi-mode signal should remain after prompt edits
        signals = ("find_replace", "GUID", "guid", "full_replace", "diff", "replace")
        assert any(s in text for s in signals)


class TestReviewerPrompt:
    def test_approve_gate(self, prompts):
        text = _system(prompts, "reviewer")
        assert "APPROVE" in text or "approve" in text.lower()
        assert "proposal" in text.lower() or "json" in text.lower()


class TestOrchestratorPrompt:
    def test_routing_next_agent(self, prompts):
        text = _system(prompts, "orchestrator").lower()
        assert "next_agent" in text or "next agent" in text
        assert "json" in text


class TestSchemaFilesPresent:
    def test_core_schemas_exist(self):
        schema_dir = PROJECT_ROOT / "agent_schemas"
        for name in ("developer.json", "reviewer.json", "orchestrator.json"):
            path = schema_dir / name
            assert path.exists(), f"missing {name}"
            json.loads(path.read_text(encoding="utf-8"))
