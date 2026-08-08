import json

from core import llm_test_mode as ltm


def test_env_enables(monkeypatch):
    monkeypatch.setenv("PRIZMFORGE_TEST_MODE", "1")
    assert ltm.test_mode_enabled({}) is True


def test_config_enables():
    assert ltm.test_mode_enabled({"llm": {"test_mode": True}}) is True
    assert ltm.test_mode_enabled({"llm": {"test_mode": False}}) is False


def test_mock_orchestrator_json():
    raw = ltm.mock_call_agent("orchestrator", "hi", "t1", {"llm": {"test_mode": True}})
    data = json.loads(raw)
    assert data["next_agent"] == "complete"


def test_scripted_override():
    cfg = {"llm": {"test_mode": True, "mock_responses": {"developer": '{"operations":[]}'}}}
    assert "operations" in ltm.mock_call_agent("developer", "x", "t", cfg)


def test_mock_response_queue():
    from core import llm_test_mode as ltm

    ltm.reset_mock_queues()
    cfg = {
        "llm": {
            "test_mode": True,
            "mock_responses": {
                "developer": ["first", "second"],
            },
        }
    }
    assert ltm.mock_call_agent("developer", "p", "t", cfg) == "first"
    assert ltm.mock_call_agent("developer", "p", "t", cfg) == "second"
