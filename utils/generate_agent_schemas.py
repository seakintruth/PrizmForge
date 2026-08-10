import json
from datetime import datetime
from pathlib import Path

# Schema output directory
SCHEMA_DIR = Path(__file__).parent.parent / "agent_schemas"

# =============================================================================
# Background Agent Schemas (Feedback with GUIDs)
# =============================================================================

BACKGROUND_AGENT_SCHEMAS = {
    "jr_reviewer": {
        "description": "Junior Code Reviewer - finds bugs, code smells, and issues",
        "array_field": "findings",
        "schema": {
            "findings": [
                {
                    "priority": "HIGH",
                    "category": "bug",
                    "message": "Specific issue description",
                    "suggestion": "How to fix it",
                    "start_line_guid": "guid-abc-123",
                    "end_line_guid": "guid-abc-125",
                }
            ],
            "summary": "Brief assessment of file quality",
        },
    },
    "jr_researcher": {
        "description": "Junior Researcher - identifies improvements and optimizations",
        "array_field": "suggestions",
        "schema": {
            "suggestions": [
                {
                    "priority": "MEDIUM",
                    "category": "performance",
                    "message": "Optimization opportunity identified",
                    "suggestion": "Use list comprehension instead of loop",
                    "start_line_guid": "guid-def-456",
                    "end_line_guid": "guid-def-458",
                }
            ],
            "summary": "Analysis complete with improvement suggestions",
        },
    },
    "tech_writer": {
        "description": "Technical Writer - reviews documentation quality",
        "array_field": "documentation_issues",
        "schema": {
            "documentation_issues": [
                {
                    "priority": "LOW",
                    "category": "documentation",
                    "message": "Missing or incomplete docstring",
                    "suggestion": "Add comprehensive docstring with parameters, return type, and examples",
                    "start_line_guid": "guid-xyz-789",
                }
            ],
            "summary": "Documentation review complete",
        },
    },
    "security_reviewer": {
        "description": "Security Specialist - identifies security vulnerabilities",
        "array_field": "security_findings",
        "schema": {
            "security_findings": [
                {
                    "priority": "CRITICAL",
                    "category": "security",
                    "message": "SQL injection vulnerability detected",
                    "suggestion": "Use parameterized queries instead of string concatenation",
                    "start_line_guid": "guid-sec-111",
                    "end_line_guid": "guid-sec-113",
                }
            ],
            "summary": "Security audit complete",
        },
    },
    "deployment_validator": {
        "description": "Deployment Validator - verifies changes match intent",
        "array_field": "issues",
        "schema": {
            "validation_status": "PASS",
            "issues": [
                {
                    "priority": "HIGH",
                    "category": "other",
                    "message": "Change does not match stated intent",
                    "suggestion": "Review implementation against requirements",
                    "start_line_guid": "guid-val-001",
                    "confidence": 0.85,
                }
            ],
            "summary": "Validation complete",
        },
    },
}

# =============================================================================
# Core Workflow Agent Schemas
# =============================================================================

CORE_AGENT_SCHEMAS = {
    "orchestrator": {
        "description": "Orchestrator - decides next agent and provides instructions",
        "schema": {
            "feedback_summary": "Brief summary of current state and prioritized items from message bus",
            "next_agent": "developer",
            "instructions": "Clear, specific instructions for the developer agent about what needs to be done",
            "reasoning": "Why this decision was made and what the current priorities are",
            "files_needed": ["path/to/file1.py", "path/to/file2.py"],
            "addressing_feedback_ids": [123, 456],
            "model": "gemini-3.1-pro-preview",
        },
    },
    "reviewer": {
        "description": "Reviewer - safety gate for edit proposals",
        "schema": {
            "decision": "APPROVE",
            "reason": "Changes are safe and properly implement the stated requirements",
            "suggestions": [
                "Consider adding unit tests for the new error handling logic",
                "The new function could benefit from more detailed docstring",
            ],
        },
    },
    "developer": {
        "description": "Developer - creates EditPayload for governed file editing",
        "schema": {
            "target_file_path": "path/to/file.py",
            "summary": "Brief description of all changes being made",
            "operations": [
                {
                    "type": "replace_block",
                    "start_line_guid": "guid-abc-123",
                    "end_line_guid": "guid-abc-125",
                    "new_content": [
                        "def improved_function(param1, param2):",
                        "    return param1 + param2",
                    ],
                    "rationale": "Refactored function for better readability",
                },
                {
                    "type": "insert_after",
                    "after_guid": "guid-xyz-789",
                    "new_content": [
                        "",
                        "def new_helper_function():",
                        "    return True",
                    ],
                    "rationale": "Added new helper function",
                },
                {
                    "type": "delete_lines",
                    "start_line_guid": "guid-old-111",
                    "end_line_guid": "guid-old-115",
                    "rationale": "Removed deprecated code block",
                },
            ],
            "rationale": "Overall explanation of why these changes are needed",
        },
    },
}

# =============================================================================
# Support Worker Schemas
# =============================================================================

SUPPORT_WORKER_SCHEMAS = {
    "archivist": {
        "description": "Archivist - compresses conversation history while preserving key decisions",
        "schema": {
            "summary": "Concise summary of the archived conversation period",
            "key_decisions": [
                "Decided to use SQLite for local storage instead of PostgreSQL",
                "Agreed to implement governed editing with line GUIDs",
                "Chose to use exponential backoff for API retries",
            ],
            "agent_interactions": "Developer and Reviewer collaborated on 3 proposals",
            "repetitive_patterns": "Multiple retries due to JSON parsing issues",
            "issues_resolved": [
                "Fixed database connection leak in core/db.py",
                "Resolved JSON parsing failures",
            ],
            "can_be_forgotten": ["Routine code review comments that were immediately addressed"],
        },
    },
    "prioritizer": {
        "description": "Prioritizer - ranks and filters feedback for orchestrator",
        "schema": {
            "top_suggestions": [
                {
                    "id": 123,
                    "final_score": 150,
                    "rank": 1,
                    "priority": "CRITICAL",
                    "category": "security",
                    "file_path": "core/db.py",
                    "summary": "SQL injection vulnerability in query builder",
                    "action_for_orchestrator": "Fix SQL injection in core/db.py using parameterized queries",
                }
            ],
            "summary": "Processed 45 feedback items. 2 CRITICAL, 5 HIGH, 18 MEDIUM, 20 LOW",
            "human_input_count": 0,
            "ignored_count": 8,
            "duplicate_count": 12,
        },
    },
    "project_reporter": {
        "description": "Project Reporter - generates human-readable markdown reports",
        "schema": {
            "_note": "This agent outputs MARKDOWN, not JSON",
            "output_format": "markdown",
            "structure": {
                "sections": [
                    "# PrizmForge Project Report",
                    "## Executive Summary",
                    "## Files Modified",
                    "## Git Commits",
                    "## Agent Activity",
                    "## Addressed Feedback",
                    "## Outstanding Issues",
                    "## Metrics",
                ]
            },
        },
    },
    "resource_controller": {
        "description": "Resource Controller - internal schemas for throttling decisions",
        "schema": {
            "_note": "Internal worker - does not output JSON to message bus",
            "throttle_decision": {
                "level": "MODERATE",
                "background_feeder_interval": 90,
                "active_agents": ["jr_reviewer", "jr_researcher", "prioritizer"],
                "rate_limit_per_minute": 60,
                "model_downgrades": {"tech_writer": "gemini-3-flash-preview"},
                "reasoning": "Budget at 40%, reducing activity to conserve tokens",
            },
        },
    },
}

# =============================================================================
# Generation Functions
# =============================================================================


def create_schema_directory():
    """Create the agent_schemas directory if it doesn't exist"""
    SCHEMA_DIR.mkdir(parents=True, exist_ok=True)
    print(f"📁 Created directory: {SCHEMA_DIR}")


def write_schema_file(agent_name: str, schema_data: dict, description: str):
    """Write a schema file with pretty formatting"""
    filepath = SCHEMA_DIR / f"{agent_name}.json"

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(schema_data, f, indent=2, ensure_ascii=False)

    print(f"✅ Generated: {filepath.name:<40} - {description}")


def generate_all_schemas():
    """Generate all agent schema files"""
    print("\n" + "=" * 70)
    print("🔧 PrizmForge Agent Schema Generator")
    print("=" * 70 + "\n")

    # Create directory
    create_schema_directory()
    print()

    # Generate background agent schemas
    print("📋 Background Agent Schemas (Feedback with GUIDs):")
    print("-" * 70)
    for agent_name, config in BACKGROUND_AGENT_SCHEMAS.items():
        write_schema_file(agent_name, config["schema"], config["description"])

    print()

    # Generate core workflow agent schemas
    print("🔨 Core Workflow Agent Schemas:")
    print("-" * 70)
    for agent_name, config in CORE_AGENT_SCHEMAS.items():
        write_schema_file(agent_name, config["schema"], config["description"])

    print()

    # Generate support worker schemas
    print("⚙️  Support Worker Schemas:")
    print("-" * 70)
    for agent_name, config in SUPPORT_WORKER_SCHEMAS.items():
        write_schema_file(agent_name, config["schema"], config["description"])

    print()
    print("=" * 70)
    print("✅ Schema generation complete!")
    print("=" * 70)

    # Count files
    background_count = len(BACKGROUND_AGENT_SCHEMAS)
    core_count = len(CORE_AGENT_SCHEMAS)
    support_count = len(SUPPORT_WORKER_SCHEMAS)
    total_count = background_count + core_count + support_count + 1  # +1 for metadata

    print(f"\nGenerated {total_count} schema files in: {SCHEMA_DIR}")
    print(f"  - Background agents: {background_count}")
    print(f"  - Core agents: {core_count}")
    print(f"  - Support workers: {support_count}")
    print("  - Metadata: 1")
    print("\nNext steps:")
    print("  1. Review generated schemas in agent_schemas/")
    print("  2. Update agents/base.py to load these schemas")
    print("  3. Update agent prompts to reference schema files")
    print()


def generate_readme():
    """Generate README.md for the agent_schemas directory"""
    readme_content = (
        """# Agent Schema Files

Generated schemas for PrizmForge multi-agent system.

## Categories

- **Background Agents**: jr_reviewer, jr_researcher, tech_writer, security_reviewer, deployment_validator
- **Core Agents**: orchestrator, developer, reviewer
- **Support Workers**: archivist, prioritizer, project_reporter, resource_controller

## GUID Format

All line references use format: `guid-xxx-123`

## Usage

```python
from core.agent_schemas import get_schema_example
schema = get_schema_example("jr_reviewer")
```

Last generated: """
        + datetime.now().strftime("%Y-%m-%d %H:%M")
        + "\n"
    )

    readme_path = SCHEMA_DIR / "README.md"
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(readme_content)

    print(f"📖 Generated: {readme_path.name:<40} - Documentation")


# =============================================================================
# Main Execution
# =============================================================================

if __name__ == "__main__":
    generate_all_schemas()
    generate_readme()

    # Print summary
    print("\n" + "=" * 70)
    print("📊 Generated Files Summary:")
    print("=" * 70)
