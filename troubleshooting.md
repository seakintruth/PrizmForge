# PrizmForge Troubleshooting Guide

Detailed debugging and problem-solving guide.

## Table of Contents

- [Startup Issues](#startup-issues)
- [API and Endpoint Issues](#api-and-endpoint-issues)
- [File Operation Issues](#file-operation-issues)
- [Background Agent Issues](#background-agent-issues)
- [Database Issues](#database-issues)
- [Performance Issues](#performance-issues)
- [Configuration Issues](#configuration-issues)
- [Debugging Workflows](#debugging-workflows)
- [Common Error Messages](#common-error-messages)

---

## Startup Issues

### "config.json not found"

**Symptoms:**
```
❌ ERROR: Missing configuration files:
  • config.json
```

**Causes:**
- Running from wrong directory
- Config file not created

**Solutions:**

1. **Check current directory:**
```bash
ls -la
# Should see: config.json, api_key.json, agent_prompts.json
```

2. **Run from correct directory:**
```bash
cd /path/to/PrizmForge
python main.py
```

3. **Create config.json if missing:**
```bash
cp config.json.example config.json
# Edit with your settings
```

---

### "API key not configured"

**Symptoms:**
```
❌ ERROR: API key not configured
Please edit api_key.json with your API key
```

**Causes:**
- Missing `api_key.json`
- Placeholder values still present

**Solutions:**

1. **Create api_key.json:**
```json
{
  "gemini_api_key": "your-actual-key-here",
  "databricks_token": "your-actual-token-here"
}
```

2. **Verify key format:**
- Gemini keys typically start with specific prefixes
- Databricks tokens are long alphanumeric strings

3. **Test key:**
```bash
👤 Human> health
# Should show endpoint status
```

---

### "Project directory not writable"

**Symptoms:**
```
⚠️  Warning: Project directory may not be writable
```

**Causes:**
- Insufficient permissions
- Directory doesn't exist
- Path incorrect

**Solutions:**

1. **Check permissions:**
```bash
ls -ld /path/to/project
# Should show write permissions (drwxr-xr-x or similar)
```

2. **Create directory:**
```bash
mkdir -p /path/to/project
```

3. **Fix permissions:**
```bash
chmod u+w /path/to/project
```

4. **Use different directory:**
```json
{
  "project_directory": "~/my_project"
}
```

---

## API and Endpoint Issues

### "API KEY LOCKED OR INVALID"

**Symptoms:**
```
============================================================
🔒 API KEY LOCKED OR INVALID (databricks)
============================================================
Unlock at: https://our.example.domain/AI-PORTAL/user-ui/keys
```

**Causes:**
- API key locked by provider
- Too many failed requests
- Incorrect key format

**Solutions:**

1. **Unlock key:**
- Visit the URL shown
- Follow provider's unlock process
- Wait for cooldown period (30 minutes default)

2. **Check fallback:**
```bash
👤 Human> health
# Should show fallback endpoint available
```

3. **Reset endpoint:**
```bash
👤 Human> reset databricks
# After fixing the key
```

4. **Use alternate endpoint temporarily:**
```json
{
  "default_endpoint": "gemini"
}
```

---

### "No endpoints currently available"

**Symptoms:**
```
❌ NO ENDPOINTS CURRENTLY AVAILABLE
   All endpoints are experiencing issues or in cooldown
```

**Causes:**
- All endpoints in cooldown
- All API keys invalid
- Network connectivity issues

**Solutions:**

1. **Check endpoint health:**
```bash
👤 Human> health

⏳ DATABRICKS: UNAVAILABLE (available in 25m)
⏳ GEMINI: UNAVAILABLE (available in 15m)
```

2. **Wait for cooldown:**
- Check "Available in" time
- Wait or reduce cooldown in config

3. **Reset all endpoints:**
```bash
👤 Human> reset
✅ Reset all endpoints to healthy status
```

4. **Check network connectivity:**
```bash
curl -I https://api.our.example.domain/
# Should return HTTP 200 or similar
```

5. **Check proxy settings:**
```json
{
  "proxy": {
    "http": "http://proxy:8080",
    "https": "http://proxy:8443"
  }
}
```

---

### "Model 'X' not found"

**Symptoms:**
```
⚠️  Model 'gemini-2.0-flash' not found. Using 'gemini-3.1-pro-preview'
   Available: gemini-3.1-pro-preview, gemini-2.5-pro, gemini-2.5-flash
```

**Causes:**
- Model name typo in config
- Model not defined in `models` section

**Solutions:**

1. **Check available models:**
```bash
👤 Human> endpoints
# Shows all configured models
```

2. **Fix model name in config:**
```json
{
  "agent_model_preferences": {
    "orchestrator": "gemini-3.1-pro-preview"  // Use exact name
  }
}
```

3. **Add missing model:**
```json
{
  "models": {
    "your-model-name": {
      "endpoint": "gemini",
      "max_output_tokens": 16384,
      "temperature": 0.5
    }
  }
}
```

---

### Rate Limiting (429 errors)

**Symptoms:**
```
⏳ Rate limited (gemini)...
   Sleeping 60s...
```

**Causes:**
- Exceeded API rate limit
- Too many requests in short time

**Solutions:**

1. **Wait for retry:**
- System automatically waits and retries
- Falls back to alternate endpoint if wait > 1 minute

2. **Reduce rate limit:**
```json
{
  "rate_limit": {
    "max_calls_per_minute": 60  // Lower than current
  }
}
```

3. **Check fallback stats:**
```bash
👤 Human> fallbacks
# See how often rate limiting occurs
```

4. **Disable background agents temporarily:**
```json
{
  "background_agents_enabled": false
}
```

---

### Token Budget Exceeded

**Symptoms:**
```
⚠️  Token budget exceeded: 31M / 30M
```

**Causes:**
- Used all tokens in 4-hour window
- Too many large requests

**Solutions:**

1. **Check current usage:**
```bash
👤 Human> status

📊 Tokens: 31M / 30M (103.3%) in last 4h
```

2. **Wait for budget reset:**
- Tokens older than 4 hours are removed automatically
- Check usage every 30 minutes

3. **Increase budget:**
```json
{
  "token_budget": {
    "max_tokens_per_4h": 50000000
  }
}
```

4. **Optimize token usage:**
- Use Flash models for background agents
- Reduce context size
- Disable background agents

---

## File Operation Issues

### "File not found"

**Symptoms:**
```
❌ Could not read: myfile.py
```

**Causes:**
- File not indexed in database
- File path incorrect
- File deleted after indexing

**Solutions:**

1. **Re-index project:**
```bash
👤 Human> init
```

2. **Check indexed files:**
```bash
👤 Human> files
# Lists all indexed files
```

3. **Verify file exists:**
```bash
ls -la myfile.py
```

4. **Check ignore patterns:**
```json
{
  "file_operations": {
    "ignore_patterns": [
      // Make sure your file isn't ignored
    ]
  }
}
```

---

### "Patch failed"

**Symptoms:**
```
❌ Patch failed: patch: **** malformed patch at line 5
```

**Causes:**
- Invalid diff format
- File changed since diff created
- Line numbers incorrect

**Solutions:**

1. **Check agent response:**
```bash
Human> show_prompt task_001 developer
# Look at the diff that was generated
```

2. **Re-index file:**
```bash
👤 Human> init
# Ensures database has latest file content
```

3. **Check file modifications:**
```bash
👤 Human> changes
# See recent modifications
```

4. **Export and inspect:**
```bash
👤 Human> export task_001
# Open file_modifications.csv to see what changed
```

5. **Manual recovery:**
```bash
# Restore from backup if exists
ls -la myfile.py.backup.*
cp myfile.py.backup.12345 myfile.py
```

---

### "File manager not parsing"

**Symptoms:**
```
⚠️  Could not parse file manager JSON
No file operations detected
```

**Causes:**
- File manager returned invalid JSON
- No operations in response
- Model hallucinated

**Solutions:**

1. **Check file manager response:**
```bash
👤 Human> show_prompt task_001 file_manager

RESPONSE:
Here are the operations...  # ← Not JSON!
```

2. **Verify file manager prompt:**
```json
// agent_prompts.json
{
  "file_manager": {
    "system_prompt": "You MUST respond with ONLY valid JSON..."
  }
}
```

3. **Try different model:**
```json
{
  "agent_model_preferences": {
    "file_manager": "gemini-3.1-pro-preview"  // More reliable
  }
}
```

4. **Export for analysis:**
```bash
👤 Human> export_tables agent_responses_archive task_001
# Open in Excel, search for file_manager responses
```

---

## Background Agent Issues

### "Background agents not working"

**Symptoms:**
- No console output like "✅ jr_reviewer posted feedback"
- `review_status` shows 0 reviews

**Causes:**
- Background agents disabled
- No files to review
- Agents crashing silently

**Solutions:**

1. **Check if enabled:**
```json
{
  "background_agents_enabled": true
}
```

2. **Check review status:**
```bash
👤 Human> review_status

🤖 jr_reviewer:
   Files reviewed: 0  # ← Problem!
   Total reviews: 0
```

3. **Check console for errors:**
Look for:
```
⚠️  jr_reviewer error: ...
```

4. **Check if files indexed:**
```bash
👤 Human> files
# Should show files
```

5. **Test agent manually:**
```python
python -c "from utils.testing import test_agent; test_agent('jr_reviewer')"
```

6. **Check database:**
```bash
sqlite3 .PrizmFoundry/agents.db
SELECT COUNT(*) FROM project_files WHERE is_binary = 0;
# Should be > 0
```

---

### "Too many API calls from background agents"

**Symptoms:**
```
⏳ Rate limited...
⏳ Rate limited...
⏳ Rate limited...
```

**Causes:**
- Background agents too aggressive
- Too many files
- Feeder interval too short

**Solutions:**

1. **Reduce feeder interval:**
Edit `agents/parallel_workers.py`:
```python
self.feeder_interval = 60  # Instead of 30
```

2. **Reduce files per cycle:**
Edit `agents/parallel_workers.py`:
```python
files_per_agent = 1  # Instead of 3
```

3. **Use faster models:**
```json
{
  "agent_model_preferences": {
    "jr_reviewer": "gemini-3-flash-preview",
    "jr_researcher": "gemini-3-flash-preview",
    "tech_writer": "gemini-3-flash-preview"
  }
}
```

4. **Disable temporarily:**
```json
{
  "background_agents_enabled": false
}
```

---

### "Background agents reviewing same files repeatedly"

**Symptoms:**
```bash
👤 Human> review_status

🤖 jr_reviewer:
   Recent reviews:
     • app.py (reviewed 10x)
     • app.py (reviewed 10x)
     • app.py (reviewed 10x)
```

**Causes:**
- File being modified frequently
- Review tracking not working
- Intended behavior (periodic review)

**Solutions:**

1. **Check if intentional:**
- Background agents review modified files (high priority)
- Plus random files every 30s (normal priority)
- Multiple reviews are expected

2. **Check review tracking:**
```bash
sqlite3 .PrizmFoundry/agents.db

SELECT * FROM agent_review_tracking 
WHERE file_path = 'app.py';
```

3. **Reduce random review frequency:**
Edit `agents/parallel_workers.py`:
```python
self.feeder_interval = 120  # 2 minutes instead of 30 seconds
```

4. **Check file modifications:**
```bash
👤 Human> changes
# See if file is being modified repeatedly
```

---

## Database Issues

### "Database locked"

**Symptoms:**
```
sqlite3.OperationalError: database is locked
```

**Causes:**
- Multiple processes accessing database
- Long-running transaction
- Corrupted database

**Solutions:**

1. **Close other connections:**
```bash
# Find processes using database
lsof .PrizmFoundry/agents.db

# Kill if necessary
kill <PID>
```

2. **Restart PrizmForge:**
```bash
# Exit cleanly
👤 Human> quit

# Restart
python main.py
```

3. **Check for corruption:**
```bash
sqlite3 .PrizmFoundry/agents.db "PRAGMA integrity_check;"
# Should return: ok
```

4. **Rebuild database:**
```bash
# Backup first!
cp .PrizmFoundry/agents.db .PrizmFoundry/agents.db.backup

# Delete and re-initialize
rm .PrizmFoundry/agents.db
python main.py
👤 Human> init
```

---

### "Database too large"

**Symptoms:**
- Slow queries
- High disk usage
- `.PrizmFoundry/agents.db` > 1GB

**Causes:**
- Many tasks executed
- Large file contents stored
- Archival not working

**Solutions:**

1. **Check database size:**
```bash
du -h .PrizmFoundry/agents.db
```

2. **Export important data:**
```bash
👤 Human> export task_001
👤 Human> export task_002
```

3. **Delete old tasks:**
```bash
sqlite3 .PrizmFoundry/agents.db

DELETE FROM conversation_history WHERE task_id = 'old_task';
DELETE FROM agent_feedback WHERE task_id = 'old_task';
DELETE FROM agent_responses_archive WHERE task_id = 'old_task';
DELETE FROM archived_context WHERE task_id = 'old_task';
DELETE FROM messages WHERE task_id = 'old_task';

VACUUM;  -- Reclaim space
```

4. **Start fresh:**
```bash
# Backup first
cp .PrizmFoundry/agents.db .PrizmFoundry/agents.db.backup

# Delete
rm .PrizmFoundry/agents.db

# Re-initialize
python main.py
👤 Human> init
```

---

### "Can't find .PrizmFoundry directory"

**Symptoms:**
- Can't see `.PrizmFoundry` in file browser
- Database not found errors

**Causes:**
- Hidden directory (starts with `.`)
- Looking in wrong location

**Solutions:**

1. **Show hidden files:**

**Windows:**
- File Explorer → View → Show hidden files

**Mac:**
- Finder → Cmd+Shift+. (dot)

**Linux:**
```bash
ls -la
# Shows hidden directories
```

2. **Check location:**
```bash
# Database is in project directory
cd <project_directory>
ls -la .PrizmFoundry/
```

3. **Verify in config:**
```json
{
  "project_directory": "/path/to/project"
}
```

4. **Access directly:**
```bash
cd /path/to/project/.PrizmFoundry
ls -la
# Should see: agents.db, agents_exports/
```

---

## Performance Issues

### "System very slow"

**Symptoms:**
- Long delays between agent calls
- High CPU usage
- Unresponsive

**Causes:**
- Background agents too active
- Large files being processed
- Network latency
- Database queries slow

**Solutions:**

1. **Disable background agents:**
```json
{
  "background_agents_enabled": false
}
```

2. **Use faster models:**
```json
{
  "agent_model_preferences": {
    "orchestrator": "gemini-3-flash-preview",
    "jr_reviewer": "gemini-3-flash-preview"
  }
}
```

3. **Reduce file size limits:**
```json
{
  "file_operations": {
    "max_file_size_kb": 100
  }
}
```

4. **Add more ignore patterns:**
```json
{
  "file_operations": {
    "ignore_patterns": [
      "*.log",
      "*.json",  // Ignore large data files
      "data/",
      "logs/"
    ]
  }
}
```

5. **Optimize database:**
```bash
sqlite3 .PrizmFoundry/agents.db "VACUUM; ANALYZE;"
```

---

### "High memory usage"

**Symptoms:**
- System using multiple GB of RAM
- Out of memory errors

**Causes:**
- Large file contents in memory
- Too many background agents
- Memory leak

**Solutions:**

1. **Reduce context size:**
Edit `agents/orchestrator.py`:
```python
# Limit files in context
LIMIT 3  # Instead of LIMIT 10
```

2. **Disable background agents:**
```json
{
  "background_agents_enabled": false
}
```

3. **Restart periodically:**
```bash
# After each major task
👤 Human> quit
python main.py
```

4. **Reduce max file size:**
```json
{
  "file_operations": {
    "max_file_size_kb": 50
  }
}
```

---

## Configuration Issues

### "Changes to config.json not taking effect"

**Symptoms:**
- Modified config.json
- System still using old values

**Causes:**
- Config cached in memory
- Need to restart

**Solutions:**

1. **Restart PrizmForge:**
```bash
👤 Human> quit
python main.py
```

2. **Verify config location:**
```bash
ls -la config.json
# Make sure editing correct file
```

3. **Check for JSON syntax errors:**
```bash
python -m json.tool config.json
# Should output formatted JSON
# If error, shows line number
```

---

### "Invalid JSON in config"

**Symptoms:**
```
json.decoder.JSONDecodeError: Expecting ',' delimiter: line 15 column 5
```

**Causes:**
- Missing comma
- Missing quote
- Trailing comma
- Invalid syntax

**Solutions:**

1. **Validate JSON:**
```bash
python -m json.tool config.json
# Shows exact error location
```

2. **Common issues:**
```json
{
  "setting1": "value1"  // ← Missing comma
  "setting2": "value2",  // ← Trailing comma before }
}

{
  "setting1": value1,  // ← Missing quotes around value
}
```

3. **Use JSON validator:**
- https://jsonlint.com/
- Paste your config and check

4. **Restore from backup:**
```bash
cp config.json.backup config.json
```

---

## Debugging Workflows

### Debugging Task Failures

**Step 1: Check what happened**
```bash
👤 Human> show_prompt task_001
# Shows all prompts and responses
```

**Step 2: View conversation**
```bash
👤 Human> conversation task_001
# Shows conversation flow
```

**Step 3: Check feedback**
```bash
👤 Human> feedback task_001
# Shows unaddressed issues
```

**Step 4: Check endpoint health**
```bash
👤 Human> health
# Shows if endpoints available
```

**Step 5: Check fallback history**
```bash
👤 Human> fallbacks
# Shows endpoint switching
```

**Step 6: Export everything**
```bash
👤 Human> export task_001
# Get CSV files for analysis
```

**Step 7: Analyze in spreadsheet**
- Open `agent_responses_archive.csv`
- Filter by `parse_success = 0` to find failures
- Check `parse_error` column for error messages
- Look at `prompt` and `response` columns

---

### Debugging Agent Not Responding

**Step 1: Test agent manually**
```python
python -c "from utils.testing import test_agent; test_agent('developer')"
```

**Step 2: Check agent configuration**
```json
{
  "agent_model_preferences": {
    "developer": "gemini-3.1-pro-preview"
  }
}
```

**Step 3: Check model exists**
```bash
👤 Human> endpoints
# Should show the model
```

**Step 4: Check endpoint health**
```bash
👤 Human> health
# Check if endpoint available
```

**Step 5: Check database for responses**
```bash
sqlite3 .PrizmFoundry/agents.db

SELECT agent_name, parse_success, parse_error
FROM agent_responses_archive
WHERE agent_name = 'developer'
ORDER BY timestamp DESC
LIMIT 5;
```

---

### Debugging File Operations

**Step 1: Check if file indexed**
```bash
👤 Human> files
# Should list the file
```

**Step 2: Check file content in database**
```bash
sqlite3 .PrizmFoundry/agents.db

SELECT file_path, length(content), content_hash
FROM project_files
WHERE file_path = 'myfile.py';
```

**Step 3: Check modification history**
```bash
sqlite3 .PrizmFoundry/agents.db

SELECT operation, changed_by, timestamp
FROM file_modifications
WHERE file_path = 'myfile.py'
ORDER BY timestamp DESC;
```

**Step 4: Check what file manager received**
```bash
👤 Human> show_prompt task_001 file_manager
# Look at the input
```

**Step 5: Export for analysis**
```bash
👤 Human> export_tables file_modifications,project_files task_001
```

---

### Debugging Endpoint Issues

**Step 1: Check configuration**
```bash
👤 Human> endpoints
# Lists all endpoints and models
```

**Step 2: Check health**
```bash
👤 Human> health
# Shows availability
```

**Step 3: Check fallback history**
```bash
👤 Human> fallbacks
# Shows switching patterns
```

**Step 4: Test manually**
```bash
curl -X POST https://api.our.example.domain/v1/chat/completions \
  -H "Authorization: Bearer YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"gemini-3-flash-preview","messages":[{"role":"user","content":"test"}]}'
```

**Step 5: Check database**
```bash
sqlite3 .PrizmFoundry/agents.db

SELECT * FROM endpoint_health;

SELECT original_endpoint, reason, COUNT(*) 
FROM endpoint_fallbacks 
GROUP BY original_endpoint, reason;
```

**Step 6: Reset if needed**
```bash
👤 Human> reset
# Clears all cooldowns
```

---

## Common Error Messages

### "NoneType object has no attribute..."

**Causes:**
- Agent returned None (API call failed)
- Parsing failed
- Missing required field

**Solutions:**
1. Check endpoint health
2. Check agent responses archive for failures
3. Enable fallback if disabled
4. Check API key validity

---

### "list index out of range"

**Causes:**
- Empty response from API
- Unexpected response format
- Response path incorrect

**Solutions:**
1. Check `response_path` in endpoint config
2. Test endpoint manually
3. Check agent response in database
4. Verify model compatibility with endpoint

---

### "Connection timeout"

**Causes:**
- Network issues
- Proxy misconfiguration
- Endpoint down

**Solutions:**
1. Check network connectivity
2. Verify proxy settings
3. Check endpoint URL
4. Try alternate endpoint

---

### "Permission denied"

**Causes:**
- Insufficient file permissions
- Directory not writable
- Database locked

**Solutions:**
1. Check file/directory permissions
2. Run with appropriate user
3. Close other database connections
4. Check disk space

---

## Getting More Help

### Export Diagnostic Data

```bash
# Export everything
👤 Human> export task_001

# Export specific tables
👤 Human> export_tables agent_responses_archive,endpoint_health,endpoint_fallbacks
```

### Check System Status

```bash
# Token usage
👤 Human> status

# Endpoint health
👤 Human> health

# Fallback statistics
👤 Human> fallbacks

# Review status
👤 Human> review_status
```

### Database Inspection

```bash
sqlite3 .PrizmFoundry/agents.db

-- View all tables
.tables

-- Check recent errors
SELECT agent_name, timestamp, parse_error
FROM agent_responses_archive
WHERE parse_success = 0
ORDER BY timestamp DESC
LIMIT 10;

-- Check endpoint health
SELECT * FROM endpoint_health;

-- Check recent fallbacks
SELECT * FROM endpoint_fallbacks
ORDER BY timestamp DESC
LIMIT 10;
```

---

## Prevention Best Practices

1. **Configure multiple endpoints** - Ensures availability
2. **Monitor endpoint health** - Use `health` command regularly
3. **Check fallback stats** - Identify problematic endpoints
4. **Export regularly** - Keep backups of important tasks
5. **Test after configuration changes** - Use `endpoints` and `health`
6. **Index before tasks** - Always run `init` first
7. **Monitor token usage** - Use `status` command
8. **Review feedback** - Check `feedback` and `review_status`
9. **Keep database clean** - Delete old tasks periodically
10. **Restart periodically** - Fresh state prevents memory issues

---

Need architectural details? See [ARCHITECTURE.md](ARCHITECTURE.md)

Need configuration help? See [CONFIGURATION.md](CONFIGURATION.md)