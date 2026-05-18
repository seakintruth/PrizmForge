# Contributing to PrizmForge

Guide for extending and customizing PrizmForge.

## Table of Contents

- [Adding New Endpoints](#adding-new-endpoints)
- [Adding New Models](#adding-new-models)
- [Adding New Agents](#adding-new-agents)
- [Adding New Commands](#adding-new-commands)
- [Adding Background Agents](#adding-background-agents)
- [Modifying Database Schema](#modifying-database-schema)
- [Creating Custom Workflows](#creating-custom-workflows)
- [Testing Extensions](#testing-extensions)

---

## Adding New Endpoints

### Step 1: Add Endpoint Configuration

Edit `config.json`:

```json
{
  "endpoints": {
    "openai": {
      "base_url": "https://api.openai.com/v1/chat/completions",
      "api_key_name": "openai_api_key",
      "include_model_in_payload": true,
      "response_path": ["choices", 0, "message", "content"],
      "description": "OpenAI GPT endpoint",
      "priority": 25
    }
  }
}
```

**Configuration fields:**
- `base_url` - Full API endpoint URL
- `api_key_name` - Key name in api_key.json
- `include_model_in_payload` - Whether to send model in request body
- `response_path` - JSON path to extract response text
- `description` - Human-readable description
- `priority` - Lower number = higher priority (optional, default: 50)

### Step 2: Add API Key

Edit `api_key.json`:

```json
{
  "openai_api_key": "sk-..."
}
```

### Step 3: Test Endpoint

```bash
python main.py

👤 Human> endpoints
# Should show your new endpoint

👤 Human> health
# Should show as available
```

### Step 4: Add Models for Endpoint

Add models that use this endpoint:

```json
{
  "models": {
    "gpt-4": {
      "endpoint": "openai",
      "max_output_tokens": 8192,
      "temperature": 0.7,
      "description": "GPT-4"
    },
    "gpt-3.5-turbo": {
      "endpoint": "openai",
      "max_output_tokens": 4096,
      "temperature": 0.7,
      "description": "GPT-3.5 Turbo"
    }
  }
}
```

### Example: Custom Endpoint with Different Response Format

If your endpoint returns a different JSON structure:

```json
{
  "result": {
    "data": {
      "text": "Response here"
    }
  }
}
```

Set `response_path` accordingly:

```json
{
  "endpoints": {
    "custom": {
      "response_path": ["result", "data", "text"]
    }
  }
}
```

---

## Adding New Models

### Step 1: Define Model

Edit `config.json`:

```json
{
  "models": {
    "claude-3-opus": {
      "endpoint": "databricks",
      "max_output_tokens": 4096,
      "temperature": 0.5,
      "description": "Claude 3 Opus via Databricks"
    }
  }
}
```

**Model fields:**
- `endpoint` - Which endpoint to use (must exist in endpoints)
- `max_output_tokens` - Maximum response length
- `temperature` - Randomness (0.0-1.0)
- `description` - Human-readable description (optional)

### Step 2: Assign to Agents (Optional)

```json
{
  "agent_model_preferences": {
    "developer": "claude-3-opus"
  }
}
```

### Step 3: Test Model

```bash
👤 Human> endpoints
# Should show new model

# Test with specific agent
python -c "from utils.testing import test_agent; test_agent('developer')"
```

---

## Adding New Agents

### Step 1: Create System Prompt

Edit `agent_prompts.json`:

```json
{
  "security_auditor": {
    "role": "Security Auditor",
    "system_prompt": "You are a security auditor. Your job is to:\n1. Review code for security vulnerabilities\n2. Check for common attack vectors (SQL injection, XSS, CSRF)\n3. Verify authentication and authorization\n4. Check for sensitive data exposure\n\nResponse format (JSON only):\n{\n  \"vulnerabilities\": [\n    {\n      \"severity\": \"CRITICAL|HIGH|MEDIUM|LOW\",\n      \"type\": \"sql_injection|xss|csrf|etc\",\n      \"location\": \"file.py:line\",\n      \"description\": \"What's vulnerable\",\n      \"fix\": \"How to fix\"\n    }\n  ],\n  \"summary\": \"Overall security assessment\"\n}"
  }
}
```

### Step 2: Assign Model

Edit `config.json`:

```json
{
  "agent_model_preferences": {
    "security_auditor": "gemini-3.1-pro-preview"
  }
}
```

### Step 3: Create Agent Logic (Optional)

If you need custom logic beyond the base agent, create a new file:

`agents/security_auditor.py`:

```python
"""Security auditor agent logic"""
from agents.base import call_agent
import json

def call_security_auditor(file_path: str, content: str, task_id: str) -> dict:
    """Call security auditor with file content"""
    
    prompt = f"""Review this file for security vulnerabilities:

```python {file_path}
{content}
```

Analyze for:
- SQL injection
- XSS vulnerabilities
- CSRF issues
- Authentication bypasses
- Sensitive data exposure
"""
    
    response = call_agent("security_auditor", prompt, task_id)
    
    if not response:
        return None
    
    # Parse JSON response
    try:
        if "```json" in response:
            json_str = response.split("```json")[1].split("```")[0].strip()
        else:
            json_str = response
        
        return json.loads(json_str)
    except json.JSONDecodeError:
        print("⚠️  Could not parse security auditor JSON")
        return None
```

### Step 4: Integrate into Workflow

Edit `workflow/task_runner.py` or `agents/orchestrator.py`:

```python
# In task_runner.py
if next_agent == "security_auditor":
    from agents.security_auditor import call_security_auditor
    
    # Get files to audit
    files = get_files_for_audit(task_id)
    
    for file_path in files:
        content = get_file_content_from_db(file_path)
        result = call_security_auditor(file_path, content, task_id)
        
        # Process results
        if result and result["vulnerabilities"]:
            for vuln in result["vulnerabilities"]:
                save_agent_feedback(
                    "security_auditor", file_path,
                    vuln["severity"], vuln["type"],
                    vuln["description"], vuln["fix"],
                    task_id, None
                )
```

### Step 5: Update Orchestrator

Edit `agent_prompts.json` to let orchestrator know about new agent:

```json
{
  "orchestrator": {
    "system_prompt": "...\n\nAvailable agents:\n- developer\n- reviewer\n- researcher\n- security_auditor  <-- Add this\n- file_manager\n- complete"
  }
}
```

### Step 6: Test Agent

```python
python -c "from utils.testing import test_agent; test_agent('security_auditor')"
```

---

## Adding New Commands

### Step 1: Create Command Function

Edit `cli/commands.py`:

```python
def cmd_security_report(task_id: str = None):
    """Generate security report"""
    from core.db import get_db_path
    import sqlite3
    
    print(f"\n🔒 Security Report")
    print("=" * 60)
    
    from core.db_connection import get_db_connection
    with get_db_connection() as conn:
        cursor = conn.cursor()        
        # Query security feedback
        query = """
            SELECT file_path, priority, message, suggestion
            FROM agent_feedback
            WHERE agent_name = 'security_auditor'
            AND category IN ('sql_injection', 'xss', 'csrf', 'auth')
        """
        
        if task_id:
            query += " AND task_id = ?"
            cursor.execute(query, (task_id,))
        else:
            cursor.execute(query)
        
        vulnerabilities = cursor.fetchall()
        # Don't conn.close()
    
    if not vulnerabilities:
        print("✅ No security issues found\n")
        return
    
    # Group by severity
    critical = [v for v in vulnerabilities if v[1] == 'CRITICAL']
    high = [v for v in vulnerabilities if v[1] == 'HIGH']
    medium = [v for v in vulnerabilities if v[1] == 'MEDIUM']
    
    print(f"\n🚨 CRITICAL: {len(critical)}")
    for file_path, _, message, suggestion in critical:
        print(f"   {file_path}")
        print(f"   • {message}")
        print(f"   💡 {suggestion}\n")
    
    print(f"⚠️  HIGH: {len(high)}")
    for file_path, _, message, suggestion in high:
        print(f"   {file_path}: {message}\n")
    
    print(f"⚡ MEDIUM: {len(medium)}\n")
    print("=" * 60 + "\n")
```

### Step 2: Add Command Handler

Edit `interactive.py`:

```python
# In interactive_loop(), add before task execution fallthrough:

if cmd.lower() == "security" or cmd.lower().startswith("security "):
    parts = cmd.split()
    task_id = parts[1] if len(parts) > 1 else None
    cmd_security_report(task_id)
    continue  # ← IMPORTANT
```

### Step 3: Update Help

Edit `cli/commands.py`, in `cmd_help()`:

```python
def cmd_help():
    """Show help"""
    print("""
...
📊 ANALYSIS COMMANDS:
  security [task_id]  - Generate security report
  ...
""")
```

### Step 4: Test Command

```bash
python main.py

👤 Human> help
# Should show new command

👤 Human> security
# Should run without errors

👤 Human> security task_001
# Should show task-specific report
```

---

## Adding Background Agents

### Step 1: Create Agent Prompt

Edit `agent_prompts.json`:

```python
{
  "performance_analyzer": {
    "role": "Performance Analyzer (Background)",
    "system_prompt": "You are a performance analyzer running in parallel. Analyze code for:\n- Performance bottlenecks\n- Inefficient algorithms\n- Memory leaks\n- Database query optimization\n\nResponse (JSON):\n{\n  \"issues\": [\n    {\n      \"priority\": \"HIGH|MEDIUM|LOW\",\n      \"type\": \"bottleneck|memory|query|algorithm\",\n      \"location\": \"function_name or line range\",\n      \"issue\": \"Description\",\n      \"suggestion\": \"How to optimize\",\n      \"estimated_improvement\": \"2x faster, 50% less memory, etc\"\n    }\n  ],\n  \"summary\": \"Overall performance assessment\"\n}"
  }
}
```

### Step 2: Add to Worker Pool

Edit `agents/parallel_workers.py`:

```python
def start(self, task_id: str):
    """Start background workers"""
    if self.running:
        return
    
    self.running = True
    self.task_id = task_id
    self.recently_queued = {
        'jr_reviewer': set(),
        'jr_researcher': set(),
        'tech_writer': set(),
        'performance_analyzer': set()  # ← Add this
    }
    
    # Start workers
    for agent_name in ['jr_reviewer', 'jr_researcher', 'tech_writer', 'performance_analyzer']:
        worker = threading.Thread(
            target=self._worker_loop,
            args=(agent_name,),
            daemon=True,
            name=f"{agent_name}-worker"
        )
        worker.start()
        self.workers.append(worker)
        print(f"    🤖 Started {agent_name} worker")
```

### Step 3: Add Feedback Parsing

Edit `agents/parallel_workers.py`, in `_parse_and_save_feedback()`:

```python
def _parse_and_save_feedback(self, agent_name: str, event: FileChangeEvent, response: str):
    """Parse response and save feedback"""
    try:
        if "```json" in response:
            json_str = response.split("```json")[1].split("```")[0].strip()
        else:
            json_str = response
        
        data = json.loads(json_str)
        
        # Extract findings based on agent type
        items = []
        if agent_name == "jr_reviewer":
            items = data.get("findings", [])
        elif agent_name == "jr_researcher":
            items = data.get("suggestions", [])
        elif agent_name == "tech_writer":
            items = data.get("documentation_issues", [])
        elif agent_name == "performance_analyzer":  # ← Add this
            items = data.get("issues", [])
        
        # Save each item...
```

### Step 4: Assign Model

Edit `config.json`:

```json
{
  "agent_model_preferences": {
    "performance_analyzer": "gemini-3-flash-preview"
  }
}
```

### Step 5: Test

```bash
python main.py

👤 Human> init
👤 Human> build a simple app

# Watch for output:
# 🤖 Started performance_analyzer worker
# ✅ performance_analyzer posted 2 feedback item(s)

👤 Human> review_status
# Should show performance_analyzer stats
```

---

## Modifying Database Schema

### Step 1: Add Table Definition

Edit `core/db.py`, in `init_db()`:

```python
conn.executescript("""
    -- Existing tables...
    
    -- New table
    CREATE TABLE IF NOT EXISTS security_scans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id TEXT,
        file_path TEXT,
        scan_type TEXT,
        vulnerabilities_found INTEGER,
        critical_count INTEGER,
        high_count INTEGER,
        scanned_at TEXT,
        scanned_by TEXT
    );
    
    -- Index for performance
    CREATE INDEX IF NOT EXISTS idx_security_scans_task 
    ON security_scans(task_id);
    
    CREATE INDEX IF NOT EXISTS idx_security_scans_file 
    ON security_scans(file_path);
""")
```

### Step 2: Create Helper Functions

Create `core/security_helpers.py`:

```python
"""Security scan database helpers"""
import sqlite3
from datetime import datetime
from core.db import get_db_path

def save_security_scan(task_id: str, file_path: str, scan_type: str,
                       vulnerabilities: list, scanned_by: str):
    """Save security scan results"""
    critical = len([v for v in vulnerabilities if v['severity'] == 'CRITICAL'])
    high = len([v for v in vulnerabilities if v['severity'] == 'HIGH'])
    with get_db_connection() as conn:
        cursor = conn.cursor() 
        conn.execute("""
            INSERT INTO security_scans
            (task_id, file_path, scan_type, vulnerabilities_found,
            critical_count, high_count, scanned_at, scanned_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (task_id, file_path, scan_type, len(vulnerabilities),
            critical, high, datetime.now().isoformat(), scanned_by))
        # don't conn.commit()
        # don't conn.close()

def get_security_scans(task_id: str) -> list:
    """Get security scans for task"""

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT file_path, scan_type, vulnerabilities_found,
                critical_count, high_count, scanned_at
            FROM security_scans
            WHERE task_id = ?
            ORDER BY scanned_at DESC
        """, (task_id,))
        results = cursor.fetchall()
    return results
```

### Step 3: Use in Code

```python
from core.security_helpers import save_security_scan

# After security audit
if vulnerabilities:
    save_security_scan(
        task_id, file_path, "static_analysis",
        vulnerabilities, "security_auditor"
    )
```

### Step 4: Test Migration

```bash
# Backup database first
cp .PrizmFoundry/agents.db .PrizmFoundry/agents.db.backup

# Run PrizmForge (will create new tables)
python main.py

# Verify tables created
sqlite3 .PrizmFoundry/agents.db ".tables"
# Should show: security_scans
```

---

## Creating Custom Workflows

### Example: Security Audit Workflow

Create `workflow/security_audit.py`:

```python
"""Security audit workflow"""
from agents.base import call_agent
from core.db_helpers import get_unaddressed_feedback
from core.file_operations import get_file_content_from_db
from core.security_helpers import save_security_scan
import sqlite3
from core.db import get_db_path

def run_security_audit(task_id: str):
    """Run comprehensive security audit"""
    print(f"\n🔒 Starting Security Audit")
    print("=" * 60)
    
    # Get all Python files
    with get_db_connection() as conn:
        cursor = conn.cursor()    cursor = conn.cursor()
        cursor.execute("""
            SELECT file_path
            FROM project_files
            WHERE file_type = '.py' AND is_binary = 0
        """)
        files = [row[0] for row in cursor.fetchall()]
    
    print(f"📁 Scanning {len(files)} Python files...\n")
    
    total_vulns = 0
    critical_files = []
    
    # Scan each file
    for i, file_path in enumerate(files, 1):
        print(f"[{i}/{len(files)}] Scanning {file_path}...")
        
        content = get_file_content_from_db(file_path)
        if not content:
            continue
        
        # Call security auditor
        prompt = f"""Perform security audit on:

```python {file_path}
{content}
```
"""
        response = call_agent("security_auditor", prompt, task_id)
        
        if response:
            # Parse vulnerabilities
            import json
            try:
                if "```json" in response:
                    json_str = response.split("```json")[1].split("```")[0]
                else:
                    json_str = response
                
                data = json.loads(json_str)
                vulns = data.get("vulnerabilities", [])
                
                if vulns:
                    total_vulns += len(vulns)
                    print(f"  ⚠️  Found {len(vulns)} issue(s)")
                    
                    # Check for critical
                    critical = [v for v in vulns if v['severity'] == 'CRITICAL']
                    if critical:
                        critical_files.append(file_path)
                    
                    # Save to database
                    save_security_scan(task_id, file_path, "audit", vulns, "security_auditor")
                else:
                    print(f"  ✅ No issues")
                    
            except json.JSONDecodeError:
                print(f"  ⚠️  Could not parse response")
    
    # Summary
    print(f"\n{'='*60}")
    print(f"📊 Security Audit Complete")
    print(f"   Files scanned: {len(files)}")
    print(f"   Issues found: {total_vulns}")
    print(f"   Critical files: {len(critical_files)}")
    if critical_files:
        print(f"\n🚨 Files with CRITICAL issues:")
        for file_path in critical_files:
            print(f"   • {file_path}")
    print(f"{'='*60}\n")
    
    return total_vulns
```

### Integrate into CLI

Edit `cli/commands.py`:

```python
def cmd_security_audit(task_id: str = None):
    """Run security audit"""
    from workflow.security_audit import run_security_audit
    
    if not task_id:
        task_id = f"security_audit_{int(time.time())}"
    
    from core.db_helpers import create_task
    create_task(task_id, "Security audit")
    
    total_vulns = run_security_audit(task_id)
    
    if total_vulns > 0:
        print(f"\n📋 View detailed feedback:")
        print(f"   feedback {task_id}")
        print(f"\n📊 Generate report:")
        print(f"   security {task_id}\n")
```

Edit `interactive.py`:

```python
if cmd.lower() == "audit" or cmd.lower().startswith("audit "):
    parts = cmd.split()
    task_id = parts[1] if len(parts) > 1 else None
    cmd_security_audit(task_id)
    continue
```

### Test Workflow

```bash
python main.py

👤 Human> init
👤 Human> audit

🔒 Starting Security Audit
============================================================
📁 Scanning 15 Python files...

[1/15] Scanning app.py...
  ⚠️  Found 3 issue(s)
[2/15] Scanning auth.py...
  🚨 Found 2 CRITICAL issue(s)
...

============================================================
📊 Security Audit Complete
   Files scanned: 15
   Issues found: 12
   Critical files: 2

🚨 Files with CRITICAL issues:
   • auth.py
   • database.py
============================================================
```

---

## Testing Extensions

### Unit Testing Custom Agents

Create `tests/test_security_auditor.py`:

```python
"""Test security auditor agent"""
import unittest
from agents.base import call_agent

class TestSecurityAuditor(unittest.TestCase):
    def test_sql_injection_detection(self):
        """Test SQL injection detection"""
        vulnerable_code = '''
def get_user(username):
    query = f"SELECT * FROM users WHERE username = '{username}'"
    return db.execute(query)
'''
        
        prompt = f"Analyze for SQL injection:\n{vulnerable_code}"
        response = call_agent("security_auditor", prompt, "test_task")
        
        self.assertIsNotNone(response)
        self.assertIn("sql_injection", response.lower())
    
    def test_safe_code(self):
        """Test safe code returns no issues"""
        safe_code = '''
def get_user(username):
    query = "SELECT * FROM users WHERE username = ?"
    return db.execute(query, (username,))
'''
        
        prompt = f"Analyze for SQL injection:\n{safe_code}"
        response = call_agent("security_auditor", prompt, "test_task")
        
        self.assertIsNotNone(response)
        # Should indicate no issues or low severity

if __name__ == '__main__':
    unittest.main()
```

Run tests:

```bash
python -m unittest tests/test_security_auditor.py
```

### Integration Testing Workflows

Create `tests/test_security_workflow.py`:

```python
"""Test security audit workflow"""
import unittest
import os
from workflow.security_audit import run_security_audit
from core.db import init_db
from core.file_operations import sync_file_to_database

class TestSecurityWorkflow(unittest.TestCase):
    def setUp(self):
        """Set up test database"""
        os.environ['TESTING'] = '1'
        init_db()
        
        # Add test file
        vulnerable_code = '''
def login(username, password):
    query = f"SELECT * FROM users WHERE username='{username}'"
    user = db.execute(query).fetchone()
    return user
'''
        sync_file_to_database("test_auth.py", vulnerable_code)
    
    def test_security_audit_finds_vulnerabilities(self):
        """Test that audit finds vulnerabilities"""
        vulns = run_security_audit("test_task")
        
        self.assertGreater(vulns, 0, "Should find vulnerabilities")
    
    def tearDown(self):
        """Clean up"""
        os.environ.pop('TESTING', None)

if __name__ == '__main__':
    unittest.main()
```

### Manual Testing Checklist

- [ ] Agent responds to test prompt
- [ ] Agent output is valid JSON
- [ ] Agent stores data in database correctly
- [ ] Command appears in help
- [ ] Command executes without errors
- [ ] Command with arguments works
- [ ] Export includes new data
- [ ] Endpoint fallback works
- [ ] Background agent queues files
- [ ] Background agent posts feedback

---

## Best Practices

### Code Style

**Follow existing patterns:**

```python
# Good: Matches existing style
def cmd_my_command():
    """Command description"""
    print(f"\n📋 My Command")
    print("=" * 60)
    # Implementation
    print()

# Bad: Different style
def myCommand():
    print("My Command")
    # Implementation
```

**Use type hints:**

```python
def process_file(file_path: str, content: str) -> dict:
    """Process file and return results"""
    return {"success": True}
```

**Document functions:**

```python
def complex_operation(param1: str, param2: int) -> bool:
    """
    Perform complex operation.
    
    Args:
        param1: Description of param1
        param2: Description of param2
    
    Returns:
        True if successful, False otherwise
    
    Example:
        result = complex_operation("test", 42)
    """
    pass
```

### Database Operations

**Always use parameterized queries:**

```python
# Good: Prevents SQL injection
cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))

# Bad: Vulnerable to SQL injection
cursor.execute(f"SELECT * FROM tasks WHERE id = '{task_id}'")
```

**Close connections and Commit changes:**

```python

# Use our custom context manager, close and commit happen automatically
with get_db_connection() as conn:
    cursor = conn.cursor()
    cursor.execute(...)
    results = cursor.fetchall()

```



### Error Handling

**Handle expected errors:**

```python
def call_external_api():
    try:
        response = requests.post(...)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        print("⏱️  Request timeout")
        return None
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
        return None
    except json.JSONDecodeError:
        print("⚠️  Invalid JSON response")
        return None
```

**Don't swallow all errors:**

```python
# Bad: Hides problems
try:
    something()
except:
    pass

# Good: Handle specifically or re-raise
try:
    something()
except SpecificException as e:
    print(f"⚠️  Known issue: {e}")
except Exception as e:
    print(f"❌ Unexpected error: {e}")
    raise  # Re-raise for debugging
```

### Agent Prompts

**Be specific:**

```python
# Good: Clear instructions
system_prompt = """You are a security auditor. Analyze code for:
1. SQL injection vulnerabilities
2. XSS vulnerabilities
3. CSRF issues

Response format (JSON only):
{
  "vulnerabilities": [...],
  "summary": "..."
}
"""

# Bad: Vague
system_prompt = "Review code for security issues"
```

**Specify output format:**

```python
system_prompt = """...

IMPORTANT: Respond with ONLY valid JSON. No markdown, no explanations.

Example:
{
  "field1": "value1",
  "field2": ["item1", "item2"]
}
"""
```

**Handle parsing failures:**

```python
response = call_agent(...)

try:
    # Try multiple parsing strategies
    if "```json" in response:
        json_str = response.split("```json")[1].split("```")[0].strip()
    elif "{" in response:
        start = response.find("{")
        end = response.rfind("}") + 1
        json_str = response[start:end]
    else:
        json_str = response
    
    data = json.loads(json_str)
except json.JSONDecodeError:
    print(f"⚠️  Could not parse JSON from {agent_name}")
    return None
```

---

## Debugging Extensions

### Enable Verbose Logging

Add debug prints:

```python
def my_function(param):
    print(f"DEBUG: my_function called with {param}")
    
    result = do_something(param)
    print(f"DEBUG: result = {result}")
    
    return result
```

### Check Database State

```bash
sqlite3 .PrizmFoundry/agents.db

-- Check if data was saved
SELECT * FROM my_table LIMIT 5;

-- Check recent entries
SELECT * FROM my_table 
ORDER BY timestamp DESC 
LIMIT 10;
```

### Test Agent Responses

```python
from agents.base import call_agent

response = call_agent("my_agent", "test prompt", "test_task")
print("="*60)
print("RESPONSE:")
print(response)
print("="*60)
```

### Export for Analysis

```bash
👤 Human> export_tables my_table,agent_responses_archive test_task

# Open CSV in Excel/LibreOffice
# Check for patterns, errors, etc.
```

---

## Submitting Changes

### Before Submitting

1. **Test your changes:**
   - Run manual tests
   - Run unit tests if applicable
   - Test with multiple endpoints

2. **Check for breaking changes:**
   - Does it affect existing workflows?
   - Does it require config changes?
   - Does it require database migration?

3. **Update documentation:**
   - Add to appropriate .md file
   - Update help text
   - Add examples

4. **Clean up:**
   - Remove debug prints
   - Remove commented code
   - Check for hardcoded values

### Documentation Updates

**If adding command:**
- Update main README.md "Commands" section
- Update `cmd_help()` in cli/commands.py
- Add to TROUBLESHOOTING.md if complex

**If adding agent:**
- Update main README.md "Agents" section
- Update ARCHITECTURE.md "Agent Types"
- Add to CONFIGURATION.md "Agent Assignments"

**If adding endpoint:**
- Update CONFIGURATION.md "Endpoint Configuration"
- Add example to main README.md

**If adding database table:**
- Update ARCHITECTURE.md "Database Schema"
- Add helper functions documentation

---

## Examples Repository

Check out example extensions:

- **Custom agents**: See `examples/agents/`
- **Custom workflows**: See `examples/workflows/`
- **Custom commands**: See `examples/commands/`
- **Endpoint adapters**: See `examples/endpoints/`

*(Note: Create these directories with examples as the project grows)*

---

## Getting Help

### Resources

- **Architecture details**: See [ARCHITECTURE.md](ARCHITECTURE.md)
- **Configuration help**: See [CONFIGURATION.md](CONFIGURATION.md)
- **Debugging help**: See [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

### Community

- Share your extensions
- Report issues
- Suggest improvements

---

## Future Enhancements

Ideas for contributors:

- **Web UI** - Browser-based interface
- **Plugin system** - Dynamic agent loading
- **Agent marketplace** - Share custom agents
- **Workflow templates** - Reusable workflows
- **Real-time collaboration** - Multi-user support
- **Visual workflow editor** - Drag-and-drop workflows
- **Performance monitoring** - Track agent effectiveness
- **A/B testing** - Compare different prompts/models

---

**Happy building! 🚀**

Need help? See [TROUBLESHOOTING.md](TROUBLESHOOTING.md)