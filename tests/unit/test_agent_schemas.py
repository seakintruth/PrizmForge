"""Unit coverage for core.agent_schemas pure schema + validation helpers."""

from __future__ import annotations

from core.agent_schemas import (
    AGENT_SCHEMAS,
    get_agents_by_table,
    get_schema,
    is_using_fallback,
    list_agents,
    validate_agent_response,
)

# ---------------------------------------------------------------------------
# AgentResponseSchema.validate
# ---------------------------------------------------------------------------


def test_validate_missing_required_fields():
    schema = AGENT_SCHEMAS["orchestrator"]
    ok, errors = schema.validate({"next_agent": "developer"})  # missing instructions, reasoning
    assert ok is False
    assert any("instructions" in e for e in errors)
    assert any("reasoning" in e for e in errors)


def test_validate_orchestrator_complete():
    schema = AGENT_SCHEMAS["orchestrator"]
    ok, errors = schema.validate(
        {
            "next_agent": "developer",
            "instructions": "implement the change",
            "reasoning": "backlog has a high-priority item",
        }
    )
    assert ok is True
    assert errors == []


def test_validate_array_not_list():
    schema = AGENT_SCHEMAS["jr_reviewer"]
    ok, errors = schema.validate(
        {
            "findings": "not-a-list",
            "summary": "review complete",
        }
    )
    assert ok is False
    assert any("must be an array" in e for e in errors)


def test_validate_array_item_missing_core_fields():
    schema = AGENT_SCHEMAS["jr_reviewer"]
    ok, errors = schema.validate(
        {
            "findings": [{"message": "only message present"}],
            "summary": "one finding",
        }
    )
    assert ok is False
    assert any("priority" in e for e in errors)
    assert any("category" in e for e in errors)


def test_validate_array_item_complete():
    schema = AGENT_SCHEMAS["jr_reviewer"]
    ok, errors = schema.validate(
        {
            "findings": [
                {
                    "priority": "HIGH",
                    "category": "bug",
                    "message": "null deref risk",
                    "suggestion": "add a guard",
                    "line_range": "10-12",
                }
            ],
            "summary": "one high finding",
        }
    )
    assert ok is True
    assert errors == []


def test_validate_array_item_not_object():
    schema = AGENT_SCHEMAS["jr_reviewer"]
    ok, errors = schema.validate(
        {
            "findings": ["string-item"],
            "summary": "bad item type",
        }
    )
    assert ok is False
    assert any("must be an object" in e for e in errors)


def test_text_agent_schema_always_valid():
    """reviewer has no required fields — any dict validates."""
    schema = AGENT_SCHEMAS["reviewer"]
    ok, errors = schema.validate({})
    assert ok is True
    assert errors == []


# ---------------------------------------------------------------------------
# get_schema / fallback
# ---------------------------------------------------------------------------


def test_get_schema_explicit():
    s = get_schema("orchestrator")
    assert s is not None
    assert s.agent_name == "orchestrator"
    assert s.is_fallback is False
    assert "next_agent" in s.required_fields


def test_get_schema_fallback_for_security_reviewer():
    s = get_schema("security_reviewer")
    assert s is not None
    assert s.is_fallback is True
    assert s.array_field == "security_findings"
    assert "summary" in s.required_fields


def test_get_schema_fallback_for_performance_analyzer():
    s = get_schema("performance_analyzer")
    assert s is not None
    assert s.is_fallback is True
    assert s.array_field == "performance_findings"


def test_get_schema_unknown_returns_none():
    assert get_schema("totally_unknown_agent_xyz") is None


def test_is_using_fallback():
    assert is_using_fallback("orchestrator") is False
    assert is_using_fallback("security_reviewer") is True
    assert is_using_fallback("totally_unknown_agent_xyz") is False


# ---------------------------------------------------------------------------
# list / table helpers
# ---------------------------------------------------------------------------


def test_list_agents_sorted():
    agents = list_agents()
    assert agents == sorted(agents)
    assert "orchestrator" in agents
    assert "jr_reviewer" in agents
    assert len(agents) == len(AGENT_SCHEMAS)


def test_get_agents_by_table():
    feedback_agents = get_agents_by_table("agent_feedback")
    assert "jr_reviewer" in feedback_agents
    assert "jr_researcher" in feedback_agents
    assert "orchestrator" not in feedback_agents  # db_table=None


# ---------------------------------------------------------------------------
# build_prompt_schema
# ---------------------------------------------------------------------------


def test_build_prompt_schema_includes_priority_and_category():
    schema = AGENT_SCHEMAS["jr_reviewer"]
    text = schema.build_prompt_schema(
        priority_values=["HIGH", "LOW"],
        category_values=["bug", "style"],
    )
    assert "HIGH" in text
    assert "LOW" in text
    assert "bug" in text
    assert "findings" in text
    assert "summary" in text


def test_build_prompt_schema_orchestrator_no_array():
    schema = AGENT_SCHEMAS["orchestrator"]
    text = schema.build_prompt_schema([], [])
    assert "next_agent" in text
    assert "instructions" in text
    assert "reasoning" in text


def test_build_prompt_schema_optional_fields_comment():
    schema = AGENT_SCHEMAS["jr_reviewer"]  # has optional overall_status
    text = schema.build_prompt_schema(["MEDIUM"], ["other"])
    assert "Optional fields" in text
    assert "overall_status" in text


# ---------------------------------------------------------------------------
# validate_agent_response convenience
# ---------------------------------------------------------------------------


def test_validate_agent_response_orchestrator():
    ok, errors = validate_agent_response(
        "orchestrator",
        {
            "next_agent": "developer",
            "instructions": "fix it",
            "reasoning": "needed",
        },
    )
    assert ok is True
    assert errors == []


def test_validate_agent_response_unknown_agent_passes():
    ok, errors = validate_agent_response("totally_unknown_agent_xyz", {"anything": True})
    assert ok is True
    assert errors == []


def test_validate_agent_response_missing_fields():
    ok, errors = validate_agent_response("orchestrator", {})
    assert ok is False
    assert len(errors) >= 3
