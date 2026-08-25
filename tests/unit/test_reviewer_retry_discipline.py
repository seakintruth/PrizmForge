"""Tests for jr_reviewer retry discipline (soak P3 fix).

Soak evidence: 147 'failed JSON validation after 3 attempts' events (~441
calls). Empty responses — an endpoint problem, not a format problem — burned
all 3 attempts with progressively stricter prompts that could not help.
"""

import agents.parallel_workers as pw
from agents.parallel_workers import BackgroundAgentPool as ParallelWorkerPool


class FakeEvent:
    def __init__(self):
        self.file_path = "src/app.py"
        self.task_id = "task_001"
        self.operation = "initial_review"
        self.event_id = "evt_1"
        self.metadata = None


def _make_pool(monkeypatch, responses):
    """Pool whose call_agent pops scripted responses; counts invocations."""
    pool = ParallelWorkerPool.__new__(ParallelWorkerPool)  # skip __init__ threads
    pool.agent_configs = {}
    calls = {"n": 0}

    def fake_call_agent(agent_name, prompt, task_id, model_override=None, auto_resume=False):
        calls["n"] += 1
        return responses.pop(0) if responses else None

    monkeypatch.setattr(pw, "call_agent", fake_call_agent)
    monkeypatch.setattr("time.sleep", lambda s: None)

    def noop_parse(agent_name, event, response):
        raise AssertionError("should not parse after empty response")

    monkeypatch.setattr(pool, "_parse_and_save_feedback", noop_parse)
    return pool, calls


def test_empty_response_stops_retry_ladder(temp_db, monkeypatch):
    """An empty response must not trigger stricter-prompt retries."""
    pool, calls = _make_pool(monkeypatch, [None])
    pool._process_file("jr_reviewer", FakeEvent())
    assert calls["n"] == 1


def test_malformed_json_retries_with_stricter_prompt(temp_db, monkeypatch):
    """Malformed JSON keeps the existing retry ladder (now with backoff)."""
    pool, calls = _make_pool(
        monkeypatch,
        ["not json at all {{{", "still not json", None],
    )
    pool._process_file("jr_reviewer", FakeEvent())
    assert calls["n"] == 3


def test_valid_json_parses_first_attempt(temp_db, monkeypatch):
    pool, calls = _make_pool(
        monkeypatch,
        ['{"findings": [], "summary": "clean"}'],
    )
    parsed = {}

    def fake_parse(agent_name, event, response):
        parsed["called"] = True

    monkeypatch.setattr(pool, "_parse_and_save_feedback", fake_parse)
    pool._process_file("jr_reviewer", FakeEvent())
    assert calls["n"] == 1
    assert parsed.get("called")
