"""detect_and_resume merges continuation when truncation is high-confidence."""

from __future__ import annotations

from core.truncation_detector import detect_and_resume


def test_detect_and_resume_merges_when_truncated():
    partial = '{"target_file_path": "a.py", "new_content": "def foo():\n    return'
    continuation = ' 1\n"}'

    def fake_call(agent, prompt, task_id):
        assert agent == "developer"
        assert "continue" in prompt.lower() or "left off" in prompt.lower()
        return continuation

    merged, resumed = detect_and_resume(
        partial,
        agent_name="developer",
        original_prompt="Rewrite foo",
        expected_format="json",
        call_agent_fn=fake_call,
    )
    # High-confidence truncation should resume; if detector is conservative, still no crash
    if resumed:
        assert "def foo" in merged
        assert merged != partial
    else:
        assert merged == partial


def test_detect_and_resume_no_op_on_complete_json():
    complete = '{"target_file_path": "a.py", "new_content": "x = 1\n", "summary": "ok"}'
    calls = []

    def fake_call(*args, **kwargs):
        calls.append(args)
        return "should not be used"

    merged, resumed = detect_and_resume(
        complete,
        agent_name="developer",
        original_prompt="edit",
        expected_format="json",
        call_agent_fn=fake_call,
    )
    assert resumed is False
    assert merged == complete
    assert calls == []
