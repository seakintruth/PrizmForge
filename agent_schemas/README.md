# Agent Schema Files

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

Last generated: 2026-05-19 03:17
