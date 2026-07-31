Manually fixing:
----------------------
We currently have 3 tables that list all project files in this repo, we should have one, we have also switched to using line guid and line for all coms, so we need to stop storing content in the project_files tabl :
1) interactive.py, parallel_workers, reporter_worker, commands.py, context_manager.py, task_runner.py all contain "FROM project_files"
2) commands.py contain "FROM file_summaries"
3) commands.py, writer.py, proposal_builder.py contain "FROM files"



----------------------
currently my driver agent the Orchestrator I instruct it to :

Respond **ONLY** with valid JSON in this exact format:
{{
  "feedback_summary": "Brief summary of current state and prioritized items",
  "next_agent": "developer|background|complete",
  "instructions": "Clear instructions (only used when calling developer)",
  "reasoning": "Why you made this decision",
  "files_needed": ["optional list of files"],
  "addressing_feedback_ids": [123, 456],
  "model": "optional-model-override"
}}"""


A couple of issues I see is that there's no prompting the prioritizer to focus on building proposals, and  the build_orchestrator_context isn't focusing on the agent_feedback table, but is reading directly from the messy 'messages' table in _get_prioritized_suggestions.

So we always pile up 100 to 200 feedback items that never get addressed. we need to change _get_prioritized_suggestions to focus on 'proposals' and 'agent_feedback' and lean heavily on sending anything we can to the developer, only send to background if there are no feedback_items not addressed or proposals not addressed, complete only ever happens after there are no feedback items left to address, or our run iterations or time limit is up (these should only apply when in semi-attended mode, in unattended mode it should never respond with complete).


Prompt to fix self:
----------------------
Please verify that these critical fixes from the audit are still present, if so fix them. First, update file_editing/writer.py to prevent path traversal by resolving paths and ensuring they are strictly within the configured project_directory. Second, update file_editing/edit_payload.py to remove the default empty string (="") for the rationale field in BaseOperation and all inherited classes so it is strictly required. Third, refactor the roughly 10 Python files that still reference the project_files table. We need to stop storing the entire file content as a single text block in project_files. Instead, update the system to rely on the file_summaries table for metadata/summaries and the file_lines table for actual content. Since this has never been deployed, do not worry about migrations—just update the schema in core/db.py directly (e.g., dropping project_files or its content column, and linking file_summaries to the governed files table) and update all SQL queries to match. Update Documentation on file change. Fifth, in agents/base.py, fix the proxy/connection exception handling in call_endpoint so that if a proxy, auth, or connection error occurs, it pauses for 2 minutes and actually retries the request rather than burning through attempts and returning None. Sixth, in call_agent within agents/base.py, prevent spamming the agent_responses_archive table by skipping the archive_raw_response call entirely if response is None (network failure). Finally, after bug fixing, (A) investigate making the cli more usefull and viability of running in unattended mode. (B) standardize the use of __ini__.py accross the project using best practices.


Databricks from advana review:
Reasoning:
The user is asking me to review how `agent_schemas` is being incorporated in the project, noting that it seems "half baked".

Let me analyze how agent schemas are currently being used:

1. **File: `core\agent_schemas.py`** - This is a comprehensive implementation with:
   - Static schema definitions for different agents
   - Fallback schema templates
   - Dynamic value discovery from database
   - Schema validation functions
   - Factory functions

2. **File: `agents\base.py`** - The `call_agent` function imports and uses schemas:
   ```python
   from core.agent_schemas import get_schema_example
   
   schema_example = get_schema_example(agent_name)
   
   system_prompt += f"""
   **MANDATORY OUTPUT FORMAT:**
   Your ENTIRE response must be valid JSON matching this structure EXACTLY:
   {schema_example}
   """
   ```

3. **Schema JSON files in `agent_schemas\` directory** - Many example schemas are defined, but they're just static files.

The issues I see:

1. **Inconsistent usage**: The `call_agent` function adds schema examples to prompts, but this is done for ALL agents regardless of whether they need it. Not all agents output JSON.

2. **Redundancy**: The `core/agent_schemas.py` has Python dataclasses defining schemas, AND there are JSON files in `agent_schemas/` directory with examples. These aren't fully integrated.

3. **Half-baked validation**: The validation logic exists but isn't consistently enforced throughout the codebase.

4. **Missing connection**: The schema system isn't fully integrated with the response parsing and validation workflow.

Let me provide specific feedback on what needs improvement.# Review: `agent_schemas` Implementation

## Current State Assessment

You're right - the `agent_schemas` system is **half-baked**. Here's what I found:

### ✅ What's Working

1. **`core/agent_schemas.py`** - Well-structured with:
   - Static schema definitions
   - Dynamic value discovery from DB
   - Fallback schema template for undefined agents
   - Validation functions

2. **`agent_schemas/*.json`** - Comprehensive example schemas exist

3. **Basic injection in `agents/base.py`** - Schemas are being added to prompts

---

## ❌ Major Issues

### 1. **Blanket Schema Injection**

**Problem**: In `agents/base.py`, schemas are injected into **EVERY agent's prompt**, regardless of output type:

```python
schema_example = get_schema_example(agent_name)

system_prompt += f"""
**MANDATORY OUTPUT FORMAT:**
Your ENTIRE response must be valid JSON matching this structure EXACTLY:
{schema_example}
"""
```

**Why it's broken**:
- `project_reporter` outputs **Markdown**, not JSON
- `reviewer` outputs **text** in many cases
- `archivist` has flexible output

**Impact**: Confuses agents that shouldn't be outputting JSON

---

### 2. **Disconnected Schema Files**

**Problem**: The JSON files in `agent_schemas/` are **not loaded or used** by the Python code.

**Evidence**:
- `core/agent_schemas.py` has hardcoded `AGENT_SCHEMAS` dict
- `get_schema_example()` loads from `agent_schemas/*.json` files
- But validation and enforcement uses the hardcoded Python schemas

**Result**: Two sources of truth that can drift out of sync

---

### 3. **Validation Not Enforced**

**Problem**: `validate_agent_response()` exists but is **never called** in the workflow.

**Where it should be**:
- After `call_agent()` returns
- Before proposal creation
- In background agent processing

**Current flow**:
```python
response = call_agent("jr_reviewer", prompt, task_id)
# ❌ No validation here
data = parse_json_response(response)  # Generic parsing
```

**Should be**:
```python
response = call_agent("jr_reviewer", prompt, task_id)
# ✅ Validate against schema
valid, errors = validate_agent_response("jr_reviewer", response)
if not valid:
    # Handle schema violation
```

---

### 4. **Inconsistent Priority/Category Values**

**Problem**: Priority and category enums are defined in multiple places:

- `core/agent_schemas.py`: `["CRITICAL", "HIGH", "MEDIUM", "LOW"]`
- Database queries: Hardcoded strings scattered throughout
- Agent prompts: Different agents use different conventions

**Result**: No single source of truth for valid values

---

### 5. **No Runtime Schema Evolution**

**Problem**: The "dynamic value discovery" is theoretical:

```python
def get_distinct_values(table: str, column: str) -> List[str]:
    """Query database for distinct values in a column"""
```

This function exists but **priorities and categories are still hardcoded** in:
- `get_priority_values()` - Returns hardcoded list
- `get_category_values()` - Returns hardcoded list

**Actual behavior**: Falls back to hardcoded defaults instead of learning from DB

---

## 🔧 Recommended Fixes

### Fix 1: **Conditional Schema Injection**

Update `agents/base.py` to only inject schemas for JSON-outputting agents:

```python
from core.agent_schemas import get_schema, get_prompt_schema_text

def call_agent(agent_name: str, prompt: str, task_id: str, ...):
    # ... existing code ...
    
    schema = get_schema(agent_name)
    
    # ✅ Only inject schema if agent outputs JSON
    if schema and schema.output_format == 'json':
        schema_text = get_prompt_schema_text(agent_name)
        system_prompt += f"""

**MANDATORY OUTPUT FORMAT:**
Your ENTIRE response must be valid JSON matching this structure EXACTLY:
{schema_text}

**CRITICAL RULES:**
- First character of your response: {{
- Last character of your response: }}
- No text before the {{
- No text after the }}
- No markdown fences (```json)
"""
    elif schema and schema.output_format == 'text':
        # Text-based agents like project_reporter
        system_prompt += "\n\nRespond in clear, well-formatted text."
```

---

### Fix 2: **Consolidate Schema Sources**

**Option A - Load from JSON files** (recommended):

```python
# core/agent_schemas.py
def _load_schemas_from_files() -> Dict[str, AgentResponseSchema]:
    """Load all schemas from agent_schemas/*.json directory"""
    schema_dir = Path(__file__).parent.parent / "agent_schemas"
    schemas = {}
    
    for schema_file in schema_dir.glob("*.json"):
        if schema_file.stem.startswith("_"):
            continue  # Skip metadata files
        
        with open(schema_file) as f:
            schema_data = json.load(f)
        
        # Convert JSON schema to AgentResponseSchema object
        schemas[schema_file.stem] = _parse_schema_json(schema_data)
    
    return schemas
```

**Option B - Remove JSON files, use Python only**:
- Delete `agent_schemas/*.json`
- Keep only `core/agent_schemas.py`
- Generate examples dynamically

---

### Fix 3: **Enforce Validation**

Add validation checkpoints:

```python
# agents/parallel_workers.py - Background agents
def _process_file(self, agent_name: str, event: FileChangeEvent):
    response = call_agent(agent_name, prompt, event.task_id)
    
    if response:
        # ✅ VALIDATE AGAINST SCHEMA
        valid, errors = validate_agent_response(agent_name, response)
        
        if not valid:
            log_error("parallel_workers", "schema_validation", "HIGH",
                     f"{agent_name} violated schema: {errors}",
                     task_id=event.task_id)
            return  # Reject invalid response
        
        self._parse_and_save_feedback(agent_name, event, response)
```

```python
# workflow/proposal_builder.py - Developer agent
def create_proposal_from_developer_output(developer_output, ...):
    # ✅ VALIDATE EditPayload schema
    try:
        payload = EditPayload.model_validate_json(developer_output)
    except ValidationError as e:
        return {
            "status": "error",
            "message": f"Developer output violated EditPayload schema: {e}"
        }
```

---

### Fix 4: **Single Source for Enums**

Create a central enum module:

```python
# core/enums.py
from enum import Enum

class Priority(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

class Category(str, Enum):
    SECURITY = "security"
    BUG = "bug"
    PERFORMANCE = "performance"
    MAINTAINABILITY = "maintainability"
    DOCUMENTATION = "documentation"
    ARCHITECTURE = "architecture"
    STYLE = "style"
    OTHER = "other"
```

Then import and use everywhere:
```python
from core.enums import Priority, Category

# In agent prompts:
f"Priority must be one of: {[p.value for p in Priority]}"

# In database queries:
priority_values = [p.value for p in Priority]
```

---

### Fix 5: **Actually Use Dynamic Discovery**

Make the "learn from DB" feature actually work:

```python
def get_priority_values() -> List[str]:
    """Get actual priority values from database (with fallback)"""
    values = get_distinct_values("agent_feedback", "priority")
    
    # ✅ Use DB values if available, otherwise fall back
    if values and len(values) > 0:
        return sorted(values, key=lambda p: PRIORITY_ORDER.get(p, 99))
    
    # Fallback to defaults
    return ["CRITICAL", "HIGH", "MEDIUM", "LOW"]

# Similar for categories
def get_category_values() -> List[str]:
    values = get_distinct_values("agent_feedback", "category")
    return values if values else ["security", "bug", "performance", ...]
```

---

## 🎯 Priority Ranking

**High Priority** (Do First):
1. ✅ **Fix #1**: Conditional schema injection (prevents confusing text-output agents)
2. ✅ **Fix #3**: Enforce validation at key points (prevents bad data from entering system)

**Medium Priority**:
3. ✅ **Fix #4**: Centralize enums (reduces duplication, prevents drift)

**Low Priority** (Nice to have):
4. **Fix #2**: Consolidate schema sources (cleanup, but system works either way)
5. **Fix #5**: Dynamic enum discovery (theoretical benefit, not critical)

---

## 📝 Summary

The `agent_schemas` system has good bones but needs:
- **Selective application** (not all agents need JSON schemas)
- **Actual validation enforcement** (schemas defined but not checked)
- **Single source of truth** (enums scattered across codebase)
- **Integration with parsing** (validation disconnected from usage)

The core issue: **Schemas are being injected into prompts, but never validated on the way back out**. It's like having a type system that never throws errors.


## Critical System Challenges
1 {DONE}

2. **Data Consistency Concerns**
   - Potential column naming inconsistencies requiring thorough query auditing
   - Risk of subtle integration errors due to naming discrepancies

3. **Error Management Complexity**
   - Inconsistent error response patterns across functions
   - Unpredictable error handling mechanisms complicate upstream error management

4. **Concurrency Potential Vulnerabilities**
   - Parallel worker operations need enhanced thread-safety verification
   - Potential race conditions in shared state management

### High-Priority Design Issues

5. **Validation Logic Weaknesses**
   - Rationale field validation shows significant implementation gaps
   - Default empty string conflicts with stated requirements

6. **Temporal Validation Challenges**
   - Current GUID validation occurs at application time
   - Potential integrity risks due to file state changes between proposal and approval

7. **Documentation Misalignment**
   - Developer guidance lacks comprehensive editing requirement details
   - Agent prompts insufficiently specify critical structural expectations

8. **Resource Control Reliability**
   - Throttling disable mechanism lacks robust recovery strategy
   - Potential system vulnerability during unexpected interruptions

### Performance and Efficiency Concerns

9. **Token Estimation Limitations**
   - Simplistic token calculation method
   - Risks of budget miscalculations with current heuristic approach

10. **Database Connectivity Optimization**
   - Context management present but connection pooling absent
   - Potential performance and resource allocation improvements needed

Writes in WAL mode, yet parallel processing might introduce database contention challenges. JSON parsing introduces complex merge strategies with potential resumption risks. Background agent coordination suffers from potential race conditions, and simultaneous file reviews lack robust deduplication mechanisms.

Git integration remains fragile, permitting file writes despite commit failures. This could generate untracked changes. Configuration validation is minimal, potentially enabling cryptic error scenarios. CLI unattended mode checkpoint functionality exists but requires extensive edge case testing.

Legacy code cleanup demands immediate attention. The deprecated `file_manager` agent persists in prompts, necessitating complete removal or explicit unused status marking. Recommendations focus on schema consolidation, standardizing error handling, and implementing robust validation mechanisms.

Critical steps include removing deprecated file editing schemas, updating imports, and creating a migration guide. A new `OperationResult` class will standardize error handling with clear return types, ensuring consistent operation outcomes.

Validation improvements target the `BaseOperation` dataclass, enforcing strict rationale requirements. A post-initialization validation ensures rationale meets minimum length and content standards, preventing incomplete or meaningless operation descriptions.

Developer agent prompts require enhancement, specifically addressing GUID references and edit payload expectations. The proposed changes will clarify file context representation and improve overall system communication clarity.

Resource controller safety introduces a mechanism for temporarily disabling throttling with a guaranteed re-enable callback, preventing potential long-term system resource lockouts.

Token estimation strategies will incorporate tiktoken as an optional dependency, maintaining existing heuristic fallback mechanisms while improving estimation accuracy tracking.

Proposal validation will strengthen pre-review checks, ensuring GUID integrity and providing precise error messaging for common submission failures.

Observability enhancements focus on comprehensive metrics tracking proposal lifecycle events, monitoring reviewer interactions, and evaluating background agent performance over extended periods.

Conflict resolution strategies now include advanced auto-rebase techniques, implementing three-way merge approaches for handling proposal conflicts with intelligent guidance mechanisms.

Security considerations reveal robust protections: flexible API key management, reviewer-gated code execution safeguards, parameterized database queries, and securely escaped Git integration commands.

The system demonstrates an innovative governed editing approach, scoring 8.5/10 for its sophisticated design and safety properties, with primary remaining concerns around migration completeness.

Migration challenges include potential deprecated code persistence, error handling refinements needed, and possible race conditions in background worker processes. While test coverage is adequate, expanding scenarios for governed editing and concurrent interactions would further strengthen the system's reliability and readiness for production deployment.# PrizmForge Multi-Agent System - Comprehensive Review

## Executive Summary

**Overall Assessment: 8.5/10** - Production-Ready with Minor Fixes Needed

PrizmForge is a sophisticated autonomous software development system with a well-architected **governed self-modification** approach. The core innovation—line-level editing with stable GUIDs and a reviewer safety gate—is significantly more robust than traditional diff-based patching.

### Strengths
- ✅ Excellent safety-first design with proposal → review → materialize workflow
- ✅ Clean separation between mutation (sequential) and analysis (parallel)
- ✅ Comprehensive error logging and auditability
- ✅ Multi-endpoint resilience with automatic fallback
- ✅ Adaptive resource management with learned agent profiles
- ✅ Good test framework with proper fixtures and mocks

### Critical Issues Requiring Immediate Attention
- ❌ Schema consolidation incomplete (deprecated code still present)
- ❌ Inconsistent error handling patterns across components
- ⚠️ EditPayload validation has default value contradicting requirements
- ⚠️ Potential race conditions in background worker coordination

---

## Detailed Analysis

### 1. Architecture & Design (9/10)

**Strengths:**
- The **governed editing path** is the star feature - this is the right way to do autonomous modification
- Clear agent categorization (Sequential/Governed, Parallel Background, Support)
- Well-documented with comprehensive architecture.md and mermaid diagrams
- GUID-based line addressing solves the "stale line numbers" problem elegantly

**Issues:**
```python
# ISSUE: Legacy code still present despite being marked deprecated
# file_editing/schema.py should be completely removed
# Currently: Marked deprecated but still contains full schema definition

# RECOMMENDATION:
# 1. Delete file_editing/schema.py entirely
# 2. Update all imports to use core.db
# 3. Add migration documentation
```

### 2. Governed File Editing (9/10)

**Strengths:**
- Optimistic concurrency via content hashes is correct approach
- Post-write invalidation prevents conflicting proposals
- Detailed operation results with lines affected
- Clear proposal lifecycle tracking

**Critical Issue:**
```python
# file_editing/edit_payload.py
@dataclass
class BaseOperation:
    type: str
    rationale: str = ""  # ❌ DEFAULT VALUE CONTRADICTS VALIDATION
    
    def __post_init__(self):
        # This will fail for default empty string!
        if not (10 <= len(self.rationale) <= 500):
            raise ValueError("rationale must be between 10 and 500 characters")

# FIX:
@dataclass
class BaseOperation:
    type: str
    rationale: str  # ✅ No default - truly required
    
    def __post_init__(self):
        if not isinstance(self.rationale, str):
            raise ValueError("rationale must be a string")
        if not (10 <= len(self.rationale) <= 500):
            raise ValueError("rationale must be between 10 and 500 characters")
```

**Medium Priority:**
```python
# GUID validation happens too late
# In workflow/proposal_builder.py - validation is at proposal creation
# But in file_editing/editing.py - GUIDs are checked again at apply time

# RECOMMENDATION: Add GUID pre-validation at review time
def validate_proposal_guids(proposal_id: str) -> bool:
    """Validate GUIDs exist BEFORE reviewer sees it"""
    # Check all referenced GUIDs actually exist
    # Provide clear error messages if not
    # This catches problems earlier in the workflow
```

### 3. Agent Orchestration (8.5/10)

**Strengths:**
- Clean decision routing (developer | background | complete)
- Progress forcing prevents infinite loops
- Good integration with background agent pool

**Issues:**

```python
# workflow/task_runner.py line ~247
# Orchestrator retry logic is good, but fallback decision is questionable
if not decision:
    print(f"❌ Orchestrator failed after {MAX_ORCHESTRATOR_RETRIES} attempts")
    decision = {
        "next_agent": "reviewer",  # ❌ Why reviewer if orchestrator failed?
        "reasoning": "Orchestrator failed - defaulting to review",
        "instructions": "Review the current state",
        "files_needed": []
    }

# RECOMMENDATION: Better fallback strategy
if not decision:
    # Check what we've tried so far
    if progress["developer_calls"] == 0:
        decision = {"next_agent": "developer", ...}  # Haven't tried making changes
    elif progress["reviewer_calls"] == 0:
        decision = {"next_agent": "reviewer", ...}   # Haven't reviewed yet
    else:
        decision = {"next_agent": "complete", ...}    # Stuck - complete with error
```

### 4. Database & Schema (8/10)

**Strengths:**
- Comprehensive schema with proper indexes
- Good use of foreign keys
- Centralized error logging table
- Context manager for connection safety

**Issues:**

```python
# core/db_connection.py
# The checkpoint happens on EVERY close, even for read-only operations
@contextmanager
def get_db_connection(..., checkpoint_on_close: bool = True):
    # ...
    finally:
        if checkpoint_on_close:
            _checkpoint_with_retry(conn, retries)  # ❌ Expensive for reads

# RECOMMENDATION:
# 1. Set checkpoint_on_close=False for read-only operations
# 2. Or detect if any writes occurred before checkpointing
```

**Column Naming:**
The code has many comments about "correct column names" suggesting past inconsistency:
```python
# file_editing/writer.py line 122
# "Update file metadata (correct column: file_id)"
# This suggests there was confusion between file_id vs id

# RECOMMENDATION: Run a comprehensive audit
# grep -r "file_id\|file_path" --include="*.py" | review all queries
```

### 5. Background Agents & Parallel Processing (7.5/10)

**Strengths:**
- Clean worker pool design
- Priority-based event queue
- Review tracking prevents redundant work
- Resource-aware throttling

**Critical Issue - Race Conditions:**

```python
# agents/parallel_workers.py
class BackgroundAgentPool:
    def __init__(self):
        self.recently_queued = {}  # ❌ Dictionary modified by multiple threads
        
    def queue_file_change(self, file_path: str, ...):
        # Multiple threads call this simultaneously
        for agent_name in self.modification_agents:
            if agent_name in self.recently_queued:
                self.recently_queued[agent_name].add(file_path)  # ❌ Not thread-safe

# FIX:
import threading

class BackgroundAgentPool:
    def __init__(self):
        self.recently_queued = {}
        self._queue_lock = threading.Lock()
        
    def queue_file_change(self, file_path: str, ...):
        with self._queue_lock:
            for agent_name in self.modification_agents:
                if agent_name in self.recently_queued:
                    self.recently_queued[agent_name].add(file_path)
```

**Medium Priority:**
```python
# agents/parallel_workers.py - feeder interval adjustment
def _adjust_feeder_interval(self, queue_size: int):
    if queue_size < 10:
        self.feeder_interval = self.base_feeder_interval
    elif queue_size < 50:
        self.feeder_interval = self.base_feeder_interval * 1.5
    # ... etc

# ISSUE: No hysteresis - interval thrashes if queue size oscillates around threshold
# RECOMMENDATION: Add hysteresis or exponential smoothing
```

### 6. Resource Controller (8.5/10)

**Strengths:**
- Adaptive learning from agent performance
- Progressive throttling levels
- Model downgrades during budget pressure
- Good separation of concerns

**Issue:**

```python
# agents/resource_controller_worker.py
def temporarily_disable_throttling(self, duration_seconds: int = 30):
    self.throttling_disabled_until = datetime.now() + timedelta(seconds=duration_seconds)
    print(f"🔓 Throttling temporarily disabled for {duration_seconds} seconds")
    
# ❌ PROBLEM: If process crashes during disabled window, no cleanup
# ❌ PROBLEM: If exception occurs, throttling stays disabled

# FIX: Add guaranteed re-enable
def temporarily_disable_throttling(self, duration_seconds: int = 30):
    self.throttling_disabled_until = datetime.now() + timedelta(seconds=duration_seconds)
    
    # Guaranteed re-enable even if something goes wrong
    def _ensure_enabled():
        time.sleep(duration_seconds + 5)
        if self.throttling_disabled_until and datetime.now() > self.throttling_disabled_until:
            self.throttling_disabled_until = None
            print("🔒 Throttling automatically re-enabled (safety)")
    
    threading.Thread(target=_ensure_enabled, daemon=True).start()
```

### 7. Error Handling & Observability (8/10)

**Strengths:**
- Centralized error logging with `log_error()`
- Comprehensive `errors` table with context
- Detailed operation results
- Good use of structured logging

**Issue - Inconsistent Return Types:**

```python
# Different functions use different error patterns:

# Pattern 1: Dict with status
def apply_edit_proposal(proposal_id: str) -> Dict[str, Any]:
    return {"status": "error", "message": "..."}

# Pattern 2: None on error
def call_agent(...) -> Optional[str]:
    return None  # On error

# Pattern 3: Raise exception
def validate_guid_exists(...):
    if not valid:
        raise ValueError("GUID not found")

# RECOMMENDATION: Standardize on one pattern (prefer Dict with status)
@dataclass
class OperationResult:
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    details: Optional[Dict] = None
```

### 8. Testing (7.5/10)

**Strengths:**
- Good fixture design (`temp_db`, `mock_openai_chat`)
- Separation of unit vs integration tests
- Race condition tests for parallel workers

**Gaps:**

```bash
# Missing test coverage for:
- Optimistic concurrency conflict resolution flow
- Proposal invalidation cascade
- Resource controller throttling transitions
- Background agent coordination edge cases
- Full orchestrator → developer → reviewer → materialize flow

# RECOMMENDATION: Add integration test
def test_full_governed_editing_flow(temp_db, mock_openai_chat):
    """End-to-end: create proposal → review → materialize"""
    # Initialize file
    # Mock developer output with EditPayload
    # Mock reviewer approval
    # Verify file written to disk
    # Verify overlapping proposals invalidated
```

### 9. Configuration & Deployment (8/10)

**Strengths:**
- Multi-endpoint support
- Environment variable overrides
- Path normalization

**Issues:**

```python
# core/config.py
# No schema validation for config.json
def load_config(config_path: str = None) -> Dict[str, Any]:
    with open(config_file, 'r', encoding='utf-8') as f:
        config = json.load(f)  # ❌ No validation
    # ...

# RECOMMENDATION: Add Pydantic model
from pydantic import BaseModel, Field, validator
from typing import Dict, List, Optional

class EndpointConfig(BaseModel):
    base_url: str
    api_key_name: str
    include_model_in_payload: bool
    response_path: List[str | int]
    priority: int = Field(default=50, ge=1, le=100)
    rate_limit_per_minute: int = Field(default=60, ge=1)

class ConfigSchema(BaseModel):
    project_directory: str
    git: bool = True
    endpoints: Dict[str, EndpointConfig]
    default_endpoint: str
    models: Dict[str, dict]
    
    @validator('default_endpoint')
    def default_endpoint_must_exist(cls, v, values):
        if 'endpoints' in values and v not in values['endpoints']:
            raise ValueError(f"default_endpoint '{v}' not found in endpoints")
        return v

def load_config(config_path: str = None) -> Dict[str, Any]:
    with open(config_file, 'r', encoding='utf-8') as f:
        raw_config = json.load(f)
    
    # Validate with Pydantic
    try:
        validated = ConfigSchema(**raw_config)
        return validated.dict()
    except ValidationError as e:
        print(f"❌ Configuration validation failed:")
        for error in e.errors():
            print(f"   {error['loc']}: {error['msg']}")
        raise
```

**Missing Documentation:**
```markdown
# No documented upgrade path for configuration changes
# Example: If you add a new required config field, how do existing users migrate?

# RECOMMENDATION: Add config/CHANGELOG.md
## v1.4 → v1.5
- Added: `resource_controller.project_goals` (optional)
- Changed: `background_agents` now supports per-agent `model` override
- Migration: Existing configs work without changes
```

---

### 10. JSON Parsing & LLM Resilience (9/10)

**Strengths:**
- Excellent multi-strategy parsing (markdown, braces, etc.)
- Truncation detection with auto-resume
- Format-specific merge strategies
- Confidence scoring

**Minor Issue:**

```python
# core/json_parser.py
def _extract_json_content(self, text: str) -> Optional[str]:
    """Extract JSON content, stripping markdown fences and surrounding text"""
    # Strategy 1: Extract from ```json block
    if "```json" in text:
        match = re.search(r'```json\s*\n(.*?)(?:```|$)', text, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
    
    # Strategy 3: Find first { to last }
    if '{' in text:
        start = text.find('{')
        end = text.rfind('}') + 1
        
        if start < end:
            return text[start:end]  # ✅ Good
        else:
            # Truncated JSON (no closing brace found)
            json_part = text[start:]
            if '```' in json_part:
                json_part = json_part.split('```')[0]
            return json_part  # ⚠️ Returns incomplete JSON without marking it

# RECOMMENDATION: Return tuple (content, is_complete)
def _extract_json_content(self, text: str) -> Tuple[Optional[str], bool]:
    # ... strategies ...
    if start < end:
        return text[start:end], True  # Complete
    else:
        return text[start:], False    # Incomplete
```

---

### 11. CLI & User Experience (7/10)

**Strengths:**
- Good command organization
- Export functionality for debugging
- Status and health monitoring
- Semi-attended and unattended modes

**Issues:**

```python
# interactive.py - User feedback during long operations
def run_task_cycle(task_id: str, user_command: str, ...):
    # ...
    while current_turn < max_turns:
        # ... lots of processing ...
        # ❌ No progress indicator during long LLM calls
        response = call_agent("developer", enhanced_instructions, ...)

# RECOMMENDATION: Add progress feedback
import sys

def call_agent_with_progress(agent_name: str, prompt: str, ...):
    print(f"  ⏳ Calling {agent_name}...", end='', flush=True)
    
    # Show dots during wait
    def show_progress():
        while not done_event.is_set():
            print('.', end='', flush=True)
            time.sleep(1)
    
    progress_thread = threading.Thread(target=show_progress, daemon=True)
    progress_thread.start()
    
    response = call_agent(agent_name, prompt, ...)
    done_event.set()
    print(" ✅")
    return response
```

**Error Messages Need Improvement:**

```python
# Current:
"❌ Developer failed after 3 attempts"

# Better:
"""
❌ Developer Agent Failed
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Attempts: 3/3
Last Error: Invalid JSON response
Context: Trying to modify core/db.py

Possible causes:
  • Model context limit exceeded
  • Network timeout
  • Malformed prompt

Next steps:
  1. Check endpoint health: `health`
  2. View last attempt: `show_prompt task_001 developer`
  3. Export logs: `export task_001`
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
```

---

### 12. Security Considerations (8.5/10)

**Strengths:**
- API keys separate from config
- Reviewer gate prevents unauthorized changes
- Full audit trail in database
- Git integration for rollback

**Issues:**

```python
# 1. No protection against path traversal
# file_editing/writer.py
def write_file_to_disk(file_path: str, content: str, ...):
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)  # ❌ No validation

# ATTACK: Developer could propose:
{
    "target_file_path": "../../etc/passwd",
    "operations": [...]
}

# FIX: Add path validation
def write_file_to_disk(file_path: str, content: str, ...):
    path = Path(file_path).resolve()
    project_root = Path(get_config()["project_directory"]).resolve()
    
    # Ensure path is within project
    if not str(path).startswith(str(project_root)):
        raise SecurityError(f"Path {file_path} is outside project directory")
    
    # Prevent dangerous locations
    dangerous_paths = [".git", ".ssh", ".env"]
    if any(part in path.parts for part in dangerous_paths):
        raise SecurityError(f"Cannot modify {file_path} (protected path)")
```

```python
# 2. Database injection risk (minor)
# Several places use string interpolation instead of parameters

# BAD (from agents/parallel_workers.py):
placeholders = ','.join('?' * len(feedback_ids))
conn.execute(f"UPDATE agent_feedback ... WHERE id IN ({placeholders})", feedback_ids)

# GOOD (parameterized):
conn.execute(
    "UPDATE agent_feedback ... WHERE id IN ({})".format(','.join(['?']*len(feedback_ids))),
    feedback_ids
)

# BEST: Use executemany for bulk updates
```

```python
# 3. Sensitive data in error logs
# core/archival.py
def archive_raw_response(task_id: str, agent_name: str, prompt: str, 
                        response: str, ...):
    # ❌ Full prompt and response stored forever
    # Could contain API keys, secrets, PII

# RECOMMENDATION: Add scrubbing
import re

SENSITIVE_PATTERNS = [
    (r'(api[_-]?key["\s:=]+)["\']?([a-zA-Z0-9_-]+)', r'\1***REDACTED***'),
    (r'(password["\s:=]+)["\']?([^\s"\']+)', r'\1***REDACTED***'),
    (r'(token["\s:=]+)["\']?([a-zA-Z0-9_-]+)', r'\1***REDACTED***'),
]

def scrub_sensitive_data(text: str) -> str:
    for pattern, replacement in SENSITIVE_PATTERNS:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text
```

---

### 13. Performance & Scalability (7.5/10)

**Strengths:**
- Token estimation at write time (not repeated)
- Smart context manager with prioritization
- Indexes on hot query paths
- Connection pooling via context manager

**Issues:**

```python
# 1. N+1 Query Problem
# workflow/proposal_builder.py
def _capture_hashes_for_operations(conn, file_id, payload):
    affected_guids = []
    expected_hashes = {}
    
    for op in payload.operations:
        guids = _get_affected_guids_from_operation(op)
        if guids:
            affected_guids.extend(guids)
            for guid in guids:  # ❌ Query per GUID
                row = conn.execute(
                    "SELECT content_hash FROM file_lines WHERE line_guid = ? ...",
                    (guid,)
                ).fetchone()

# FIX: Batch query
def _capture_hashes_for_operations(conn, file_id, payload):
    all_guids = []
    for op in payload.operations:
        all_guids.extend(_get_affected_guids_from_operation(op))
    
    if not all_guids:
        return [], {}
    
    # Single query for all GUIDs
    placeholders = ','.join('?' * len(all_guids))
    rows = conn.execute(
        f"SELECT line_guid, content_hash FROM file_lines WHERE line_guid IN ({placeholders})",
        all_guids
    ).fetchall()
    
    expected_hashes = {row[0]: row[1] for row in rows}
    return list(set(all_guids)), expected_hashes
```

```python
# 2. Memory leak risk in long-running tasks
# agents/parallel_workers.py
class BackgroundAgentPool:
    def __init__(self):
        self.recently_queued = {agent: set() for agent in all_agents}
        # ❌ These sets grow unbounded
        
    def queue_file_change(self, file_path: str, ...):
        self.recently_queued[agent_name].add(file_path)  # Never cleared

# FIX: Use LRU cache with size limit
from collections import OrderedDict

class BoundedSet:
    def __init__(self, max_size=1000):
        self._data = OrderedDict()
        self.max_size = max_size
    
    def add(self, item):
        if item in self._data:
            self._data.move_to_end(item)
        else:
            self._data[item] = True
            if len(self._data) > self.max_size:
                self._data.popitem(last=False)
```

```python
# 3. Inefficient file reconstruction
# file_editing/db.py
def reconstruct_file_content(conn: sqlite3.Connection, file_id: int) -> str:
    cursor = conn.execute("""
        SELECT content 
        FROM file_lines 
        WHERE file_id = ? AND is_deleted = 0
        ORDER BY sort_order
    """, (file_id,))
    lines = [row["content"] for row in cursor.fetchall()]
    return "\n".join(lines)  # ❌ For large files, this builds giant string in memory

# BETTER: Stream to file
def reconstruct_file_to_stream(conn: sqlite3.Connection, file_id: int, output_stream):
    cursor = conn.execute("""...""")
    for row in cursor:
        output_stream.write(row["content"])
        output_stream.write("\n")
```

---

### 14. Code Quality & Maintainability (8/10)

**Strengths:**
- Good separation of concerns
- Clear module organization
- Comprehensive docstrings in key areas
- Type hints in many places

**Issues:**

```python
# 1. Inconsistent type hint coverage
# Some files have excellent hints:
def apply_edit_proposal(proposal_id: str) -> Dict[str, Any]: ...

# Others have none:
def some_function(data, options):  # ❌ No hints
    ...

# RECOMMENDATION: Add to CI
# mypy --strict core/ file_editing/ workflow/
```

```python
# 2. Magic numbers throughout codebase
# file_editing/editing.py
INITIAL_GAP = 1024.0  # ✅ Good - named constant
MIN_GAP_THRESHOLD = 0.001
RENUMBER_GAP = 1024.0

# But elsewhere:
if elapsed > 0.3:  # ❌ What is 0.3?
    time.sleep(0.1 * (2 ** attempt))  # ❌ Magic formula

# Better:
RESPONSE_TIMEOUT_THRESHOLD_SECONDS = 0.3
BASE_BACKOFF_INTERVAL = 0.1
```

```python
# 3. Duplicate logic
# Multiple places implement "get recent items from table"

# agents/archivist_worker.py
cutoff_time = (datetime.now() - timedelta(minutes=10)).isoformat()
cursor.execute("SELECT ... WHERE timestamp < ?", (cutoff_time,))

# agents/resource_controller_worker.py
ten_min_ago = (datetime.now() - timedelta(minutes=10)).isoformat()
cursor.execute("SELECT ... FROM token_log WHERE timestamp > ?", ...)

# RECOMMENDATION: Extract to utility
# core/db_utils.py
def get_recent_records(conn, table: str, minutes: int, order: str = "DESC"):
    cutoff = (datetime.now() - timedelta(minutes=minutes)).isoformat()
    return conn.execute(f"""
        SELECT * FROM {table} 
        WHERE timestamp {'>' if order == 'DESC' else '<'} ?
        ORDER BY timestamp {order}
    """, (cutoff,)).fetchall()
```

---

### 15. Documentation Quality (8.5/10)

**Strengths:**
- Excellent `architecture.md` with mermaid diagrams
- Clear README with quick start
- Comprehensive troubleshooting guide
- Good inline comments for complex logic

**Gaps:**

```markdown
# 1. Missing: API reference for custom agents
# If I want to add a new agent, I need to piece together info from multiple files

# RECOMMENDATION: Add docs/CUSTOM_AGENTS.md
## Adding a Custom Agent

### 1. Define System Prompt
```json
// agent_prompts.json
{
  "my_custom_agent": {
    "role": "Custom Agent Role",
    "system_prompt": "You are..."
  }
}
```

### 2. Register with Configuration
### 3. Implement Handler (if needed)
### 4. Test

---

# 2. Missing: Database schema evolution guide
# Current schema is v1.3 but no documented migration path

# RECOMMENDATION: Add migrations/
migrations/
  001_initial_schema.sql
  002_add_reviewed_at.sql
  003_consolidate_schema.sql
  README.md  # How to apply migrations
```

---

## Priority Fix List

### 🔴 Critical (Fix Before Production)

1. **Race condition in `BackgroundAgentPool.recently_queued`**
   - File: `agents/parallel_workers.py`
   - Impact: Data corruption in multi-threaded environment
   - Fix: Add `threading.Lock()` around all dictionary mutations

2. **Path traversal vulnerability in file writer**
   - File: `file_editing/writer.py`
   - Impact: Could write files outside project directory
   - Fix: Add path validation with `Path.resolve()` checks

3. **`EditPayload.rationale` default value contradiction**
   - File: `file_editing/edit_payload.py`
   - Impact: Invalid payloads pass initial validation, fail later
   - Fix: Remove default value, make truly required

4. **Remove deprecated `file_editing/schema.py`**
   - Impact: Confusion about source of truth for schema
   - Fix: Delete file, update imports

### 🟡 High (Fix Soon)

5. **Add GUID validation at review time**
   - File: `workflow/proposal_builder.py`
   - Impact: Better error messages, fail-fast behavior
   - Fix: Validate GUIDs exist before sending to reviewer

6. **Improve orchestrator fallback decision**
   - File: `workflow/task_runner.py`
   - Impact: Better recovery from orchestrator failure
   - Fix: Smarter fallback based on progress state

7. **Add config validation with Pydantic**
   - File: `core/config.py`
   - Impact: Catch config errors at startup vs runtime
   - Fix: Create `ConfigSchema` model

8. **Fix N+1 query in hash capture**
   - File: `workflow/proposal_builder.py`
   - Impact: Performance on large proposals
   - Fix: Batch GUID lookups

### 🟢 Medium (Improve Quality)

9. **Add resource controller re-enable safety**
   - File: `agents/resource_controller_worker.py`
   - Impact: Throttling could stay disabled after crash
   - Fix: Guaranteed re-enable thread

10. **Standardize error return patterns**
    - Files: Multiple
    - Impact: Easier error handling
    - Fix: Use consistent `OperationResult` pattern

11. **Add sensitive data scrubbing**
    - File: `core/archival.py`
    - Impact: API keys in database
    - Fix: Regex-based scrubbing before storage

12. **Fix memory leak in `recently_queued`**
    - File: `agents/parallel_workers.py`
    - Impact: Unbounded growth in long-running processes
    - Fix: Use `BoundedSet` with LRU eviction

---

## Testing Recommendations

### Critical Test Gaps

```python
# 1. Integration test for full governed flow
def test_end_to_end_governed_editing(temp_db):
    """Complete flow: init file → create proposal → review → materialize"""
    # Initialize file with GUIDs
    init_result = initialize_file_lines("test.py", "def hello():\n    pass")
    
    # Create proposal
    payload = {...}
    proposal = create_proposal_from_developer_output(payload, ...)
    
    # Review and approve
    update_proposal_status(proposal["proposal_id"], "approved")
    
    # Materialize
    result = materialize_proposal(proposal["proposal_id"])
    
    # Verify file on disk
    assert Path("test.py").read_text() == expected_content
    
    # Verify overlapping proposals invalidated
    assert get_proposal_status(other_proposal_id) == "needs_revalidation"
```

```python
# 2. Optimistic concurrency conflict test
def test_optimistic_concurrency_prevents_conflicting_edits(temp_db, sample_file):
    """Two proposals modify same line - second should fail validation"""
    # Create two proposals targeting same line
    proposal_1 = create_proposal_from_developer_output({
        "target_file_path": "test.py",
        "operations": [{
            "type": "replace_block",
            "start_line_guid": "guid-1",
            "new_content": ["def updated_v1():"]
        }]
    }) 
    proposal_2 = create_proposal_from_developer_output({
        "target_file_path": "test.py",
        "operations": [{
            "type": "replace_block",
            "start_line_guid": "guid-1",  # Same GUID!
            "new_content": ["def updated_v2():"]
        }]
    })
    
    # Approve and apply first
    update_proposal_status(proposal_1["proposal_id"], "approved")
    result_1 = apply_edit_proposal(proposal_1["proposal_id"])
    assert result_1["status"] == "success"
    
    # Second should fail validation (hash changed)
    update_proposal_status(proposal_2["proposal_id"], "approved")
    result_2 = apply_edit_proposal(proposal_2["proposal_id"])
    assert result_2["status"] == "conflicted"
    assert "hash mismatch" in result_2.get("message", "").lower()
```

```python
# 3. Background agent coordination test
def test_background_agents_coordinate_safely(temp_db, mock_minimal_config):
    """Multiple background agents processing same file should not corrupt data"""
    from agents.parallel_workers import BackgroundAgentPool
    import threading
    
    pool = BackgroundAgentPool()
    pool.start(task_id="test_coordination")
    
    # Queue same file for multiple agents simultaneously
    def queue_work(agent_name):
        for _ in range(10):
            pool.queue_file_change(
                file_path="test.py",
                operation="modified",
                content="def test(): pass"
            )
    
    threads = [
        threading.Thread(target=queue_work, args=(name,))
        for name in ["jr_reviewer", "security_reviewer", "tech_writer"]
    ]
    
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    # Verify no exceptions raised and queue is consistent
    time.sleep(2)
    pool.stop()
    
    # Check database integrity
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA integrity_check")
        assert cursor.fetchone()[0] == "ok"
```

```python
# 4. Resource controller throttling transition test
def test_resource_controller_throttles_progressively(temp_db, mock_minimal_config):
    """As budget depletes, throttling should progressively increase"""
    from agents.resource_controller_worker import HeuristicOptimizer, ResourceState
    
    optimizer = HeuristicOptimizer()
    
    # Test each throttling level
    test_states = [
        (0.95, "NORMAL"),
        (0.45, "MODERATE"),
        (0.15, "AGGRESSIVE"),
        (0.03, "CRITICAL")
    ]
    
    for budget_pct, expected_level in test_states:
        state = ResourceState(
            tokens_used_in_window=int(1_000_000 * (1 - budget_pct)),
            tokens_remaining=int(1_000_000 * budget_pct),
            max_tokens=1_000_000,
            current_burn_rate=1000.0,
            api_calls_last_minute=10,
            api_rate_limit=60,
            budget_percentage=budget_pct,
            time_remaining_in_window=60.0
        )
        
        decision = optimizer.optimize(state)
        assert decision.level == expected_level
        
        # Verify agents are progressively restricted
        if expected_level == "CRITICAL":
            assert len(decision.active_agents) <= 1
        elif expected_level == "AGGRESSIVE":
            assert len(decision.active_agents) <= 2
```

```python
# 5. JSON parsing edge cases test
def test_json_parser_handles_all_truncation_types():
    """Verify parser correctly detects and handles truncation in all formats"""
    from core.json_parser import get_json_parser
    
    parser = get_json_parser()
    
    test_cases = [
        # (response, expected_truncated, expected_type)
        ('{"key": "value"}', False, "NONE"),  # Complete
        ('{"key": "val', True, "JSON"),  # Truncated string
        ('{"key": "value",', True, "JSON"),  # Trailing comma
        ('{"a": 1, "b": {"c":', True, "JSON"),  # Incomplete nested
        ('```python\ndef test():\n    pass', True, "CODE_BLOCK"),  # No closing fence
        ('Here is code:\n```\ndef test():', True, "CODE_BLOCK"),  # Truncated code
    ]
    
    for response, should_truncate, expected_type in test_cases:
        result = parser.detect(response)
        assert result.is_truncated == should_truncate, f"Failed for: {response[:30]}"
        if should_truncate:
            assert expected_type in str(result.truncation_type)
```

### Load & Stress Tests

```python
# 6. Large file editing test
def test_editing_large_files_performs_acceptably(temp_db):
    """System should handle files with 1000+ lines efficiently"""
    # Create file with 1000 lines
    content = "\n".join([f"line_{i} = {i}" for i in range(1000)])
    result = initialize_file_lines("large_file.py", content)
    
    assert result["status"] == "success"
    
    # Time a replace operation
    import time
    start = time.time()
    
    proposal = create_proposal_from_developer_output({
        "target_file_path": "large_file.py",
        "operations": [{
            "type": "replace_block",
            "start_line_guid": result["line_guids"][500],  # Middle of file
            "new_content": ["# Modified line"]
        }]
    })
    
    elapsed = time.time() - start
    
    # Should complete in under 1 second
    assert elapsed < 1.0, f"Proposal creation took {elapsed}s (too slow)"
```

```python
# 7. Concurrent proposal stress test
def test_many_concurrent_proposals(temp_db):
    """System should handle many proposals being created simultaneously"""
    import concurrent.futures
    
    def create_proposal_worker(i):
        return create_proposal_from_developer_output({
            "target_file_path": f"file_{i % 10}.py",
            "operations": [{
                "type": "insert_after",
                "after_guid": None,
                "new_content": [f"# Proposal {i}"]
            }]
        })
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(create_proposal_worker, i) for i in range(50)]
        results = [f.result() for f in futures]
    
    # All should succeed
    assert all(r["status"] == "success" for r in results)
    
    # All proposal IDs should be unique
    proposal_ids = [r["proposal_id"] for r in results]
    assert len(proposal_ids) == len(set(proposal_ids))
```

---

## Architecture Evolution Recommendations

### 1. Plugin System for Custom Agents

**Current State:** Adding a new agent requires modifying core files.

**Recommendation:**
```python
# agents/plugin_loader.py
from typing import Protocol, Dict, Any

class AgentPlugin(Protocol):
    """Interface for custom agents"""
    
    @property
    def name(self) -> str:
        """Agent identifier"""
        ...
    
    @property
    def system_prompt(self) -> str:
        """Agent instructions"""
        ...
    
    def process(self, input: Dict[str, Any]) -> Dict[str, Any]:
        """Main processing logic"""
        ...
    
    def validate_output(self, output: str) -> bool:
        """Output validation"""
        ...

class AgentRegistry:
    def __init__(self):
        self.plugins: Dict[str, AgentPlugin] = {}
    
    def register(self, plugin: AgentPlugin):
        self.plugins[plugin.name] = plugin
    
    def load_from_directory(self, path: str):
        """Auto-discover plugins in directory"""
        for module in Path(path).glob("*.py"):
            # Dynamic import and registration
            ...

# Example custom agent
# plugins/my_agent.py
class MyCustomAgent:
    @property
    def name(self) -> str:
        return "my_custom_agent"
    
    @property
    def system_prompt(self) -> str:
        return "You are a custom agent that..."
    
    def process(self, input: Dict[str, Any]) -> Dict[str, Any]:
        # Custom logic
        return {"status": "success", "data": ...}
```

### 2. Event-Driven Architecture for Better Observability

**Current State:** Coordination via database polling and direct calls.

**Recommendation:**
```python
# core/events.py
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, List

class EventType(Enum):
    PROPOSAL_CREATED = "proposal.created"
    PROPOSAL_APPROVED = "proposal.approved"
    PROPOSAL_REJECTED = "proposal.rejected"
    FILE_MATERIALIZED = "file.materialized"
    AGENT_COMPLETED = "agent.completed"
    FEEDBACK_POSTED = "feedback.posted"

@dataclass
class Event:
    type: EventType
    payload: Dict[str, Any]
    timestamp: str
    source: str

class EventBus:
    def __init__(self):
        self._subscribers: Dict[EventType, List[Callable]] = {}
    
    def subscribe(self, event_type: EventType, handler: Callable):
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)
    
    def publish(self, event: Event):
        # Notify all subscribers
        for handler in self._subscribers.get(event.type, []):
            try:
                handler(event)
            except Exception as e:
                log_error("event_bus", "publish", "MEDIUM", str(e))

# Usage:
event_bus = EventBus()

# Subscribe to proposal approvals
event_bus.subscribe(
    EventType.PROPOSAL_APPROVED,
    lambda e: queue_file_for_background_review(e.payload["file_path"])
)

# Publish after approval
event_bus.publish(Event(
    type=EventType.PROPOSAL_APPROVED,
    payload={"proposal_id": proposal_id, "file_path": file_path},
    timestamp=datetime.now().isoformat(),
    source="reviewer"
))
```

### 3. Query Builder for Complex Database Operations

**Current State:** SQL strings scattered throughout codebase.

**Recommendation:**
```python
# core/query_builder.py
from dataclasses import dataclass
from typing import List, Optional, Tuple

@dataclass
class Query:
    table: str
    columns: List[str] = None
    where: List[Tuple[str, str, Any]] = None
    order_by: Optional[str] = None
    limit: Optional[int] = None
    
    def to_sql(self) -> Tuple[str, List[Any]]:
        cols = ", ".join(self.columns) if self.columns else "*"
        sql = f"SELECT {cols} FROM {self.table}"
        params = []
        
        if self.where:
            conditions = []
            for column, op, value in self.where:
                conditions.append(f"{column} {op} ?")
                params.append(value)
            sql += " WHERE " + " AND ".join(conditions)
        
        if self.order_by:
            sql += f" ORDER BY {self.order_by}"
        
        if self.limit:
            sql += f" LIMIT {self.limit}"
        
        return sql, params

# Usage:
query = Query(
    table="agent_feedback",
    columns=["file_path", "priority", "message"],
    where=[
        ("task_id", "=", task_id),
        ("addressed", "=", 0),
        ("priority", "IN", ["CRITICAL", "HIGH"])
    ],
    order_by="timestamp DESC",
    limit=10
)

sql, params = query.to_sql()
cursor.execute(sql, params)
```

### 4. Proposal Versioning & Rollback

**Current State:** Once materialized, proposals can't be easily reverted.

**Recommendation:**
```python
# file_editing/versioning.py
def create_checkpoint(file_id: int, description: str) -> str:
    """Create a named checkpoint of current file state"""
    checkpoint_id = str(uuid4())
    
    with get_db_connection() as conn:
        # Snapshot current file_lines
        conn.execute("""
            INSERT INTO file_checkpoints (checkpoint_id, file_id, description, created_at)
            VALUES (?, ?, ?, datetime('now'))
        """, (checkpoint_id, file_id, description))
        
        # Copy current lines to checkpoint_lines
        conn.execute("""
            INSERT INTO checkpoint_lines (checkpoint_id, line_guid, sort_order, content)
            SELECT ?, line_guid, sort_order, content
            FROM file_lines
            WHERE file_id = ? AND is_deleted = 0
        """, (checkpoint_id, file_id))
    
    return checkpoint_id

def rollback_to_checkpoint(checkpoint_id: str):
    """Restore file to a previous checkpoint"""
    with get_db_connection() as conn:
        # Get file_id
        row = conn.execute(
            "SELECT file_id FROM file_checkpoints WHERE checkpoint_id = ?",
            (checkpoint_id,)
        ).fetchone()
        
        if not row:
            raise ValueError("Checkpoint not found")
        
        file_id = row[0]
        
        # Soft delete current lines
        conn.execute("UPDATE file_lines SET is_deleted = 1 WHERE file_id = ?", (file_id,))
        
        # Restore from checkpoint
        conn.execute("""
            INSERT INTO file_lines (line_guid, file_id, sort_order, content, version)
            SELECT line_guid, ?, sort_order, content, version + 1
            FROM checkpoint_lines
            WHERE checkpoint_id = ?
        """, (file_id, checkpoint_id))

# Usage:
checkpoint = create_checkpoint(file_id, "Before risky refactor")
# ... make changes ...
if something_went_wrong:
    rollback_to_checkpoint(checkpoint)
```

---

## Performance Optimization Roadmap

### Phase 1: Low-Hanging Fruit (1-2 days)

1. ✅ **Batch GUID lookups** in proposal builder
2. ✅ **Add indexes** on frequently queried columns
3. ✅ **Cache file summaries** in memory (TTL-based)
4. ✅ **Pre-compile regex patterns** in JSON parser

### Phase 2: Structural Improvements (1 week)

5. ✅ **Connection pooling** instead of per-operation connections
6. ✅ **Async I/O** for background agents (use `asyncio`)
7. ✅ **Lazy loading** for file content (don't load unless needed)
8. ✅ **Streaming file reconstruction** for large files

### Phase 3: Advanced Optimizations (2-3 weeks)

9. ✅ **Query result caching** with invalidation on writes
10. ✅ **Parallel proposal validation** (validate multiple proposals concurrently)
11. ✅ **Incremental context building** (reuse context across iterations)
12. ✅ **Database write batching** (batch INSERT/UPDATE operations)

---

## Deployment Checklist

### Pre-Production

- [ ] Fix all 🔴 Critical issues
- [ ] Add path traversal protection
- [ ] Add config schema validation
- [ ] Fix race condition in BackgroundAgentPool
- [ ] Remove deprecated schema.py
- [ ] Add comprehensive integration tests
- [ ] Add sensitive data scrubbing
- [ ] Document migration path from previous versions
- [ ] Set up monitoring/alerting for error table
- [ ] Create rollback plan

### Production Readiness

- [ ] Load testing with realistic workloads
- [ ] Backup and restore procedures documented
- [ ] API key rotation procedure documented
- [ ] Database migration scripts tested
- [ ] Disaster recovery plan created
- [ ] Performance baseline established
- [ ] Security audit completed
- [ ] Documentation review by external party

### Operations

- [ ] Monitoring dashboard for key metrics
- [ ] Alerting on error rate thresholds
- [ ] Log aggregation and analysis
- [ ] Automated health checks
- [ ] Resource usage trending
- [ ] Proposal approval/rejection rates tracking

---

## Final Recommendations

### What to Prioritize

**If you're deploying for internal use (low risk):**
1. Fix race condition (#1)
2. Add path validation (#2)
3. Fix EditPayload default (#3)
4. Deploy with monitoring

**If you're deploying for production (external users):**
1. Fix all 🔴 Critical issues
2. Fix all 🟡 High priority issues
3. Complete integration test suite
4. Security audit
5. Load testing
6. Staged rollout with rollback plan

### Long-Term Vision

This is already a sophisticated system. To take it to the next level:

1. **Visual Workflow Builder** - Let non-technical users create custom agent workflows
2. **Agent Marketplace** - Share custom agents with community
3. **Real-Time Collaboration** - Multiple users working with same agent system
4. **Advanced Observability** - Grafana dashboards, distributed tracing
5. **Multi-Repository Support** - Manage changes across multiple codebases
6. **Formal Verification** - Prove correctness of critical editing operations

---

## Conclusion

**PrizmForge is production-ready with fixes to the critical issues identified above.**

The governed editing system is the standout feature—it's a fundamentally better approach to autonomous code modification than traditional diff-based patching. The combination of:

- **GUID-based line addressing** (stable references)
- **Optimistic concurrency** (prevents conflicts)
- **Reviewer safety gate** (human-in-the-loop)
- **Full audit trail** (every change tracked)

...creates a system that's both powerful and safe.

The architecture is well thought out, the code is generally high quality, and the documentation is comprehensive. The test framework provides a solid foundation for expansion.

**Grade: 8.5/10** - With the critical fixes applied, this becomes a **9/10** system.

The path to 10/10 is refinement: complete the plugin system, add event-driven observability, finish the integration test suite, and continue learning from production usage.

**Recommended next steps:**
1. Apply critical fixes (2-3 days)
2. Add missing integration tests (1 week)
3. Deploy to staging with monitoring
