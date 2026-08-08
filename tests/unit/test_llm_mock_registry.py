"""P0.2 — call_agent patch target registry."""

from tests.mocks.openai import CALL_AGENT_PATCH_TARGETS, MockLLM, register_call_agent_patch_target


def test_registry_includes_core_sites():
    joined = " ".join(CALL_AGENT_PATCH_TARGETS)
    assert "agents.base.call_agent" in joined
    assert "workflow.task_runner.call_agent" in joined
    assert "workflow.developer_edit.call_agent" in joined


def test_register_extends_targets():
    register_call_agent_patch_target("tests.fake_module.call_agent")
    from tests.mocks import openai as m

    assert "tests.fake_module.call_agent" in m.CALL_AGENT_PATCH_TARGETS
    # idempotent
    register_call_agent_patch_target("tests.fake_module.call_agent")
    assert list(m.CALL_AGENT_PATCH_TARGETS).count("tests.fake_module.call_agent") == 1


def test_mock_llm_uses_registry():
    llm = MockLLM()
    cm = llm.patch_call_agent()
    assert cm is not None
