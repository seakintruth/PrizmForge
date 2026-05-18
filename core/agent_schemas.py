"""
Agent Response Schemas - Dynamically Built from Database
The database is the single source of truth.

FALLBACK MECHANISM:
- Any agent not explicitly defined will use jr_reviewer schema as template
- This allows adding new background agents (security_reviewer, performance_reviewer, etc.)
  without touching this code
"""

from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, replace
from pathlib import Path
import json


@dataclass
class AgentResponseSchema:
    """Defines expected response structure for an agent"""
    agent_name: str
    db_table: Optional[str]
    required_fields: List[str]
    optional_fields: List[str]
    array_field: Optional[str]
    item_fields: Optional[List[str]]  # Field names in array items
    output_format: str = 'json'
    is_fallback: bool = False  # True if using fallback schema
    
    def validate(self, response: Dict[str, Any]) -> tuple[bool, List[str]]:
        """Validate response against schema"""
        errors = []
        
        # Check required fields
        for field in self.required_fields:
            if field not in response:
                errors.append(f"Missing required field: {field}")
        
        # Validate array items if applicable
        if self.array_field and self.array_field in response:
            items = response[self.array_field]
            if not isinstance(items, list):
                errors.append(f"{self.array_field} must be an array")
            elif self.item_fields and items:
                for i, item in enumerate(items):
                    if not isinstance(item, dict):
                        errors.append(f"Item {i}: must be an object")
                        continue
                    # Check for required item fields (priority, category, message are core)
                    for field in ["priority", "category", "message"]:
                        if field in self.item_fields and field not in item:
                            errors.append(f"Item {i}: missing field '{field}'")
        
        return len(errors) == 0, errors
    
    def build_prompt_schema(
        self, 
        priority_values: List[str],
        category_values: List[str],
        db_columns: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Generate JSON schema dynamically from current database state
        
        Args:
            priority_values: Actual priority values from database
            category_values: Actual category values from database
            db_columns: Optional column metadata from database
        """
        if self.array_field and self.item_fields:
            # Build item example with live database values
            item_example = {}
            
            for field in self.item_fields:
                if field == "priority":
                    item_example[field] = " | ".join(priority_values)
                elif field == "category":
                    item_example[field] = " | ".join(category_values)
                elif field == "message":
                    item_example[field] = "<description of issue>"
                elif field == "suggestion":
                    item_example[field] = "<how to fix>"
                elif field == "line_range":
                    item_example[field] = "10-15"
                elif field in ["confidence", "score"]:
                    item_example[field] = 0.8
                elif field == "type":
                    item_example[field] = "create | modify | delete"
                elif field == "path":
                    item_example[field] = "<file path>"
                elif field == "is_diff":
                    item_example[field] = True
                else:
                    item_example[field] = f"<{field}>"
            
            # Build full schema
            schema = {self.array_field: [item_example]}
        else:
            schema = {}
        
        # Add required fields
        for field in self.required_fields:
            if field not in schema:
                if field == "summary":
                    schema[field] = "<one line summary>"
                elif field == "validation_status":
                    schema[field] = "PASS | FAIL"
                else:
                    schema[field] = f"<{field}>"
        
        result = json.dumps(schema, indent=2)
        
        # Add optional fields as comment
        if self.optional_fields:
            result += f"\n\n// Optional fields: {', '.join(self.optional_fields)}"
        
        return result


# ============= STATIC SCHEMA DEFINITIONS =============
# These define structure, but values are populated from database

AGENT_SCHEMAS = {
    "jr_reviewer": AgentResponseSchema(
        agent_name="jr_reviewer",
        db_table="agent_feedback",
        required_fields=["findings", "summary"],
        optional_fields=["overall_status"],
        array_field="findings",
        item_fields=["priority", "category", "message", "suggestion", "line_range"],
        output_format="json"
    ),
    
    "jr_researcher": AgentResponseSchema(
        agent_name="jr_researcher",
        db_table="agent_feedback",
        required_fields=["suggestions", "summary"],
        optional_fields=[],
        array_field="suggestions",
        item_fields=["priority", "category", "message", "suggestion"],
        output_format="json"
    ),
    
    "tech_writer": AgentResponseSchema(
        agent_name="tech_writer",
        db_table="agent_feedback",
        required_fields=["documentation_issues", "summary"],
        optional_fields=["documentation_score"],
        array_field="documentation_issues",
        item_fields=["priority", "category", "message", "suggestion"],
        output_format="json"
    ),
    
    "deployment_validator": AgentResponseSchema(
        agent_name="deployment_validator",
        db_table="agent_feedback",
        required_fields=["validation_status", "issues", "summary"],
        optional_fields=["confidence"],
        array_field="issues",
        item_fields=["priority", "category", "message", "suggestion", "confidence"],
        output_format="json"
    ),
    
    "prioritizer": AgentResponseSchema(
        agent_name="prioritizer",
        db_table="messages",
        required_fields=["top_suggestions"],
        optional_fields=["summary", "human_input_count", "ignored_count", "duplicate_count"],
        array_field="top_suggestions",
        item_fields=["id", "score", "priority", "category", "summary", "action_for_orchestrator"],
        output_format="json"
    ),
    
    "orchestrator": AgentResponseSchema(
        agent_name="orchestrator",
        db_table=None,
        required_fields=["next_agent", "instructions", "reasoning"],
        optional_fields=["files_needed", "model", "estimated_minutes", "feedback_summary"],
        array_field=None,
        item_fields=None,
        output_format="json"
    ),
    
    "file_manager": AgentResponseSchema(
        agent_name="file_manager",
        db_table="file_modifications",
        required_fields=["operations", "summary"],
        optional_fields=[],
        array_field="operations",
        item_fields=["type", "path", "content", "is_diff", "reasoning"],
        output_format="json"
    ),
    
    "archivist": AgentResponseSchema(
        agent_name="archivist",
        db_table="archived_context",
        required_fields=["summary", "key_decisions"],
        optional_fields=["agent_interactions", "repetitive_patterns", "issues_resolved", "can_be_forgotten"],
        array_field=None,
        item_fields=None,
        output_format="json"
    ),
    
    "reviewer": AgentResponseSchema(
        agent_name="reviewer",
        db_table=None,
        required_fields=[],
        optional_fields=[],
        array_field=None,
        item_fields=None,
        output_format="text"
    ),
    
    "researcher": AgentResponseSchema(
        agent_name="researcher",
        db_table=None,
        required_fields=[],
        optional_fields=[],
        array_field=None,
        item_fields=None,
        output_format="text"
    ),
    
    "project_reporter": AgentResponseSchema(
        agent_name="project_reporter",
        db_table="project_reports",
        required_fields=[],
        optional_fields=[],
        array_field=None,
        item_fields=None,
        output_format="text"
    ),
}


# ============= FALLBACK SCHEMA TEMPLATE =============

# Any undefined agent uses this as template
FALLBACK_SCHEMA_TEMPLATE = "jr_reviewer"


def _create_fallback_schema(agent_name: str) -> AgentResponseSchema:
    """
    Create a schema for an undefined agent using jr_reviewer as template
    
    Convention: Replaces "findings" with agent-specific array name
    - security_reviewer → "security_findings"
    - performance_reviewer → "performance_findings"
    - custom_analyzer → "custom_findings"
    """
    template = AGENT_SCHEMAS[FALLBACK_SCHEMA_TEMPLATE]
    
    # Infer array field name from agent name
    # Strip common suffixes and add "_findings"
    base_name = agent_name.replace("_reviewer", "").replace("_analyzer", "").replace("_auditor", "")
    array_field = f"{base_name}_findings"
    
    # Create new schema with agent-specific name
    return replace(
        template,
        agent_name=agent_name,
        array_field=array_field,
        is_fallback=True
    )


# ============= DYNAMIC VALUE DISCOVERY =============

def get_distinct_values(table: str, column: str) -> List[str]:
    """
    Query database for distinct values in a column
    Returns actual values currently in use
    """
    from core.db import get_db_path
    from core.db_connection import get_db_connection
    
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Check if table and column exist
            cursor.execute(f"PRAGMA table_info({table})")
            columns = [row[1] for row in cursor.fetchall()]
            
            if column not in columns:
                return []
            
            # Get distinct non-null values
            cursor.execute(f"""
                SELECT DISTINCT {column} 
                FROM {table} 
                WHERE {column} IS NOT NULL 
                  AND {column} != ''
                ORDER BY {column}
            """)
            
            values = [row[0] for row in cursor.fetchall()]
        
        return values
    except Exception as e:
        print(f"⚠️  Could not query {table}.{column}: {e}")
        return []


def get_priority_values() -> List[str]:
    """Get actual priority values from database"""
    values = get_distinct_values("agent_feedback", "priority")
    
    # If empty (new database), return defaults
    if not values:
        return ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    
    return values


def get_category_values() -> List[str]:
    """Get actual category values from database"""
    values = get_distinct_values("agent_feedback", "category")
    
    # If empty (new database), return defaults
    if not values:
        return ["security", "bug", "performance", "maintainability", 
                "documentation", "architecture", "style", "other"]
    
    return values


def get_operation_types() -> List[str]:
    """Get actual file operation types from database"""
    values = get_distinct_values("file_modifications", "operation")
    
    if not values:
        return ["create", "modify", "delete"]
    
    return values


# ============= HELPER FUNCTIONS =============

def get_schema(agent_name: str) -> Optional[AgentResponseSchema]:
    """
    Get schema for an agent
    
    If agent not defined, creates fallback schema using jr_reviewer template
    This allows infinite extensibility without code changes
    """
    # Check if explicitly defined
    if agent_name in AGENT_SCHEMAS:
        return AGENT_SCHEMAS[agent_name]
    
    # Check if it looks like a background agent that should use fallback
    # Convention: ends with _reviewer, _analyzer, _auditor, or starts with jr_
    fallback_patterns = ["_reviewer", "_analyzer", "_auditor", "_checker", "_validator"]
    
    if any(agent_name.endswith(pattern) for pattern in fallback_patterns) or agent_name.startswith("jr_"):
        print(f"    ℹ️  {agent_name}: Using fallback schema (jr_reviewer template)")
        return _create_fallback_schema(agent_name)
    
    # Unknown agent type, no schema
    return None


def get_prompt_schema_text(agent_name: str) -> str:
    """
    Get JSON schema text for agent prompt with LIVE database values
    This is called every time we prompt an agent, so values are always current
    """
    schema = get_schema(agent_name)
    if not schema:
        return "{}"
    
    # Get live values from database
    priority_values = get_priority_values()
    category_values = get_category_values()
    
    return schema.build_prompt_schema(priority_values, category_values)


def validate_agent_response(agent_name: str, response: Dict[str, Any]) -> tuple[bool, List[str]]:
    """Validate agent response against schema"""
    schema = get_schema(agent_name)
    if not schema:
        return True, []
    return schema.validate(response)


def list_agents() -> List[str]:
    """Get list of all explicitly defined agents"""
    return sorted(AGENT_SCHEMAS.keys())


def get_agents_by_table(table_name: str) -> List[str]:
    """Get agents that write to a specific table"""
    return [
        agent_name
        for agent_name, schema in AGENT_SCHEMAS.items()
        if schema.db_table == table_name
    ]


def is_using_fallback(agent_name: str) -> bool:
    """Check if agent is using fallback schema"""
    schema = get_schema(agent_name)
    return schema.is_fallback if schema else False


def get_schema_statistics() -> Dict[str, Any]:
    """Get statistics about current schema state"""
    return {
        "total_agents": len(AGENT_SCHEMAS),
        "priority_values": get_priority_values(),
        "category_values": get_category_values(),
        "operation_types": get_operation_types(),
        "agents_by_output": {
            "json": [a for a, s in AGENT_SCHEMAS.items() if s.output_format == "json"],
            "text": [a for a, s in AGENT_SCHEMAS.items() if s.output_format == "text"],
        },
        "fallback_template": FALLBACK_SCHEMA_TEMPLATE
    }


def add_value_if_missing(table: str, column: str, value: str) -> bool:
    """
    Add a new enum value by inserting a record (if it doesn't exist)
    This allows the system to organically grow its vocabulary
    
    Returns True if value was added or already exists
    """
    current_values = get_distinct_values(table, column)
    
    if value in current_values:
        return True  # Already exists
    
    # Could log this as a schema evolution event
    print(f"📝 New {column} value discovered: {value}")
    return True  # Value will exist after agent saves feedback