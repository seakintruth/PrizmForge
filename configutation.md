Reasoning:
The user wants me to create the companion documents:
1. CONFIGURATION.md
2. ARCHITECTURE.md
3. TROUBLESHOOTING.md
4. CONTRIBUTING.md

I'll create comprehensive but well-organized versions of each, pulling the relevant information from the original README.# CONFIGURATION.md

```markdown
# PrizmForge Configuration Guide

Complete configuration reference for PrizmForge Multi-Agent System.

## Table of Contents

- [Configuration Files](#configuration-files)
- [Project Settings](#project-settings)
- [Endpoint Configuration](#endpoint-configuration)
- [Model Configuration](#model-configuration)
- [Agent Assignments](#agent-assignments)
- [Rate Limiting & Token Budget](#rate-limiting--token-budget)
- [Fallback Settings](#fallback-settings)
- [Background Agents](#background-agents)
- [Git Integration](#git-integration)
- [File Operations](#file-operations)
- [Proxy Configuration](#proxy-configuration)

---

## Configuration Files

PrizmForge uses three JSON configuration files:

### config.json
Main system configuration (endpoints, models, settings)

### api_key.json
API keys and tokens (keep secure, never commit to git)

### agent_prompts.json
System prompts for each agent (usually don't need to edit)

**Location:** Same directory as `main.py`

---

## Project Settings

### Basic Configuration

```json
{
  "project_directory": "./project",
  "git": true,
  "git_auto_commit": true,
  "background_agents_enabled": true,
  "default_iteration_minutes": 5,
  "min_iterations_before_complete": 3
}
```

### Settings Explained

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `project_directory` | string | `"./project"` | Where your project files live |
| `git` | boolean | `true` | Enable git integration |
| `git_auto_commit` | boolean | `true` | Auto-commit file changes |
| `background_agents_enabled` | boolean | `true` | Enable continuous review |
| `default_iteration_minutes` | integer | `5` | Default task iteration time |
| `min_iterations_before_complete` | integer | `3` | Minimum iterations before completion |

### Project Directory Formats

**Relative path:**
```json
{
  "project_directory": "./project"
}
```

**Absolute Windows path:**
```json
{
  "project_directory": "C:/Users/username/my_project"
}
```
or
```json
{
  "project_directory": "C:\\Users\\username\\my_project"
}
```

**Absolute Linux/Mac path:**
```json
{
  "project_directory": "/home/username/my_project"
}
```

**Home directory:**
```json
{
  "project_directory": "~/Documents/my_project"
}
```

**All paths are automatically:**
- Normalized (handles forward/backslashes)
- Resolved to absolute paths
- User home expanded (`~` works)
- Verified writable on startup

---

## Endpoint Configuration

### Defining Endpoints

```json
{
  "endpoints": {
    "gemini": {
      "base_url": "https://api.our.example.domain/v1/chat/completions",
      "api_key_name": "gemini_api_key",
      "include_model_in_payload": true,
      "response_path": ["choices", 0, "message", "content"],
      "description": "Gemini endpoint",
      "priority": 20
    },
    "databricks": {
      "base_url": "https://our.databricks.example.domain/serving-endpoints/databricks-claude-sonnet-4-5/invocations",
      "api_key_name": "databricks_token",
      "include_model_in_payload": false,
      "response_path": ["choices", 0, "message", "content"],
      "description": "Databricks Claude endpoint",
      "priority": 10
    }
  },
  "default_endpoint": "databricks"
}
```

### Endpoint Properties

| Property | Required | Description |
|----------|----------|-------------|
| `base_url` | Yes | Full API endpoint URL |
| `api_key_name` | Yes | Key name in `api_key.json` |
| `include_model_in_payload` | Yes | Whether to send model name in request |
| `response_path` | Yes | JSON path to extract response text |
| `description` | No | Human-readable description |
| `priority` | No | Lower number = higher priority (default: 50) |

### API Key Configuration

Create `api_key.json` with keys matching `api_key_name`:

```json
{
  "gemini_api_key": "your-gemini-key-here",
  "databricks_token": "your-databricks-token-here",
  "custom_api_key": "your-custom-key-here"
}
```

### Response Path

The `response_path` array tells PrizmForge how to extract the text from API responses.

**Example response:**
```json
{
  "choices": [
    {
      "message": {
        "content": "Hello, World!"
      }
    }
  ]
}
```

**Response path:**
```json
["choices", 0, "message", "content"]
```

Translates to: `response["choices"][0]["message"]["content"]`

### Priority System

Endpoints with **lower priority numbers** are tried first:

```json
{
  "endpoints": {
    "primary": {
      "priority": 10    // Tried first
    },
    "secondary": {
      "priority": 20    // Tried second
    },
    "fallback": {
      "priority": 30    // Tried last
    }
  }
}
```

### Adding Custom Endpoints

```json
{
  "endpoints": {
    "openai": {
      "base_url": "https://api.openai.com/v1/chat/completions",
      "api_key_name": "openai_api_key",
      "include_model_in_payload": true,
      "response_path": ["choices", 0, "message", "content"],
      "description": "OpenAI endpoint",
      "priority": 15
    }
  }
}
```

Then add to `api_key.json`:
```json
{
  "openai_api_key": "sk-..."
}
```

---

## Model Configuration

### Defining Models

```json
{
  "models": {
    "gemini-3.1-pro-preview": {
      "endpoint": "gemini",
      "max_output_tokens": 16384,
      "temperature": 0.5,
      "description": "Most capable Gemini, best for complex reasoning"
    },
    "gemini-2.5-pro": {
      "endpoint": "gemini",
      "max_output_tokens": 16384,
      "temperature": 0.5,
      "description": "Strong reasoning, good balance"
    },
    "gemini-3-flash-preview": {
      "endpoint": "gemini",
      "max_output_tokens": 16384,
      "temperature": 0.7,
      "description": "Fast and cost-effective"
    },
    "databricks-claude-sonnet-4-5": {
      "endpoint": "databricks",
      "max_output_tokens": 16384,
      "temperature": 0.5,
      "description": "Claude Sonnet via Databricks"
    }
  }
}
```

### Model Properties

| Property | Required | Description |
|----------|----------|-------------|
| `endpoint` | Yes | Which endpoint to use |
| `max_output_tokens` | Yes | Maximum response length |
| `temperature` | Yes | Randomness (0.0-1.0) |
| `description` | No | Human-readable description |

### Temperature Guide

- **0.0-0.3**: Deterministic, focused (good for code)
- **0.4-0.6**: Balanced (good for most tasks)
- **0.7-1.0**: Creative, varied (good for brainstorming)

---

## Agent Assignments

### Agent Model Preferences

Assign specific models to each agent:

```json
{
  "agent_model_preferences": {
    "orchestrator": "databricks-claude-sonnet-4-5",
    "developer": "databricks-claude-sonnet-4-5",
    "reviewer": "databricks-claude-sonnet-4-5",
    "researcher": "gemini-3.1-pro-preview",
    "jr_reviewer": "gemini-3.1-pro-preview",
    "jr_researcher": "gemini-3.1-pro-preview",
    "tech_writer": "gemini-3-flash-preview",
    "file_manager": "gemini-3-flash-preview",
    "archivist": "gemini-3.1-pro-preview"
  }
}
```

### Agent Types

**Primary Agents:**
- `orchestrator` - Coordinates tasks
- `developer` - Writes code
- `reviewer` - Reviews code
- `researcher` - Finds better approaches
- `file_manager` - Applies file changes

**Background Agents:**
- `jr_reviewer` - Continuous code review
- `jr_researcher` - Continuous improvement suggestions
- `tech_writer` - Documentation checks
- `archivist` - Context management

### Optimizing Agent Assignments

**For cost efficiency:**
```json
{
  "agent_model_preferences": {
    "orchestrator": "gemini-3-flash-preview",
    "jr_reviewer": "gemini-3-flash-preview",
    "jr_researcher": "gemini-3-flash-preview",
    "tech_writer": "gemini-3-flash-preview"
  }
}
```

**For maximum quality:**
```json
{
  "agent_model_preferences": {
    "orchestrator": "gemini-3.1-pro-preview",
    "developer": "gemini-3.1-pro-preview",
    "reviewer": "gemini-3.1-pro-preview"
  }
}
```

**For load balancing:**
```json
{
  "agent_model_preferences": {
    "orchestrator": "databricks-claude-sonnet-4-5",
    "developer": "databricks-claude-sonnet-4-5",
    "reviewer": "databricks-claude-sonnet-4-5",
    "researcher": "gemini-3.1-pro-preview",
    "jr_reviewer": "gemini-3-flash-preview"
  }
}
```

---

## Rate Limiting & Token Budget

### Rate Limit Configuration

```json
{
  "rate_limit": {
    "max_calls_per_minute": 118
  }
}
```

The system automatically:
- Tracks API calls in a sliding 60-second window
- Sleeps when approaching limit
- Displays wait time when throttled

### Token Budget Configuration

```json
{
  "token_budget": {
    "max_tokens_per_4h": 30000000
  }
}
```

**What this does:**
- Tracks token usage over rolling 4-hour window
- Prevents exceeding quota
- Falls back to alternate endpoint when exceeded

**Monitor usage:**
```bash
👤 Human> status

📊 Tokens: 5M / 30M (16.7%) in last 4h
```

**Adjust limits:**
```json
{
  "rate_limit": {
    "max_calls_per_minute": 60  // Lower for shared keys
  },
  "token_budget": {
    "max_tokens_per_4h": 50000000  // Higher if you have quota
  }
}
```

---

## Fallback Settings

### Fallback Configuration

```json
{
  "fallback_settings": {
    "enabled": true,
    "max_fallback_attempts": 2,
    "cooldown_on_exhaustion_minutes": 15,
    "cooldown_on_lock_minutes": 30,
    "cooldown_on_rate_limit_minutes": 2,
    "cooldown_on_error_minutes": 5,
    "prefer_same_provider": false,
    "log_fallbacks": true
  }
}
```

### Fallback Settings Explained

| Setting | Default | Description |
|---------|---------|-------------|
| `enabled` | `true` | Enable automatic fallback |
| `max_fallback_attempts` | `2` | Max fallback tries before giving up |
| `cooldown_on_exhaustion_minutes` | `15` | Cooldown after token exhaustion (402) |
| `cooldown_on_lock_minutes` | `30` | Cooldown after API key locked (401) |
| `cooldown_on_rate_limit_minutes` | `2` | Cooldown after rate limit (429) |
| `cooldown_on_error_minutes` | `5` | Cooldown after server error (5xx) |
| `prefer_same_provider` | `false` | Try same provider's models first |
| `log_fallbacks` | `true` | Log fallback events to database |

### Cooldown Strategy

**Aggressive (faster recovery):**
```json
{
  "fallback_settings": {
    "cooldown_on_exhaustion_minutes": 5,
    "cooldown_on_lock_minutes": 10,
    "cooldown_on_rate_limit_minutes": 1,
    "cooldown_on_error_minutes": 2
  }
}
```

**Conservative (safer):**
```json
{
  "fallback_settings": {
    "cooldown_on_exhaustion_minutes": 30,
    "cooldown_on_lock_minutes": 60,
    "cooldown_on_rate_limit_minutes": 5,
    "cooldown_on_error_minutes": 10
  }
}
```

### Prefer Same Provider

When `prefer_same_provider: true`:
- If Gemini model fails, tries other Gemini models first
- Only falls back to different provider if all same-provider models fail

**Example:**
```json
{
  "fallback_settings": {
    "prefer_same_provider": true
  }
}
```

Fallback order:
1. `gemini-3.1-pro-preview` (fails)
2. `gemini-2.5-pro` (same provider)
3. `gemini-3-flash-preview` (same provider)
4. `databricks-claude-sonnet-4-5` (different provider)

---

## Background Agents

### Enable/Disable

```json
{
  "background_agents_enabled": true
}
```

### Background Agent Behavior

Background agents automatically:
1. Review files modified since last review (Priority 1)
2. Review random files every 30 seconds (Priority 7)
3. Post CRITICAL/HIGH feedback immediately
4. Track review history per file

### Tuning Background Agents

Edit `agents/parallel_workers.py`:

```python
class BackgroundAgentPool:
    def __init__(self):
        self.feeder_interval = 30  # Seconds between random file feeds
        # ...

def _feed_random_files(self):
    files_per_agent = 3  # Files fed per agent per cycle
```

**For less aggressive background review:**
```python
self.feeder_interval = 60  # Review every 60 seconds
files_per_agent = 1  # Feed 1 file per agent
```

**For more aggressive background review:**
```python
self.feeder_interval = 15  # Review every 15 seconds
files_per_agent = 5  # Feed 5 files per agent
```

---

## Git Integration

### Git Configuration

```json
{
  "git": true,
  "git_auto_commit": true
}
```

### Settings

| Setting | Description |
|---------|-------------|
| `git: true` | Enable git integration |
| `git_auto_commit: true` | Auto-commit file changes |

**When enabled:**
- Each file modification creates a git commit
- Commit message includes agent name and operation
- Git hash stored in database for tracking

**Disable for manual control:**
```json
{
  "git": false,
  "git_auto_commit": false
}
```

---

## File Operations

### File Operation Settings

```json
{
  "file_operations": {
    "max_file_size_kb": 500,
    "ignore_patterns": [
      "*.pyc",
      "__pycache__",
      ".git",
      "node_modules",
      ".env",
      "*.db",
      "venv",
      ".venv",
      ".PrizmFoundry"
    ]
  }
}
```

### Settings Explained

| Setting | Default | Description |
|---------|---------|-------------|
| `max_file_size_kb` | `500` | Maximum file size to process |
| `ignore_patterns` | See below | File patterns to ignore |

### Default Ignore Patterns

The system ignores:
- Compiled files (`*.pyc`)
- Cache directories (`__pycache__`, `node_modules`)
- Version control (`.git`)
- Environment files (`.env`, `venv`, `.venv`)
- Databases (`*.db`)
- PrizmForge data (`.PrizmFoundry`)

### Custom Ignore Patterns

```json
{
  "file_operations": {
    "ignore_patterns": [
      "*.log",
      "*.tmp",
      "build/",
      "dist/",
      ".pytest_cache",
      "*.egg-info"
    ]
  }
}
```

---

## Proxy Configuration

### For Restricted Networks

```json
{
  "proxy": {
    "http": "http://proxy.example.com:8080",
    "https": "http://proxy.example.com:8443"
  }
}
```

### Enterprise Network Example

```json
{
  "proxy": {
    "http": "http://OurProxy1:8080",
    "https": "http://OurProxy1Secure:8443"
  }
}
```

### No Proxy

```json
{
  "proxy": null
}
```

or omit the `proxy` key entirely.

---

## Complete Example Configuration

### Minimal config.json

```json
{
  "endpoints": {
    "gemini": {
      "base_url": "https://api.our.example.domain/v1/chat/completions",
      "api_key_name": "gemini_api_key",
      "include_model_in_payload": true,
      "response_path": ["choices", 0, "message", "content"],
      "priority": 10
    }
  },
  "default_endpoint": "gemini",
  "models": {
    "gemini-3.1-pro-preview": {
      "endpoint": "gemini",
      "max_output_tokens": 16384,
      "temperature": 0.5
    }
  },
  "agent_model_preferences": {
    "orchestrator": "gemini-3.1-pro-preview",
    "developer": "gemini-3.1-pro-preview",
    "reviewer": "gemini-3.1-pro-preview"
  },
  "project_directory": "./project"
}
```

### Production config.json

```json
{
  "endpoints": {
    "gemini": {
      "base_url": "https://api.our.example.domain/v1/chat/completions",
      "api_key_name": "gemini_api_key",
      "include_model_in_payload": true,
      "response_path": ["choices", 0, "message", "content"],
      "description": "Gemini endpoint",
      "priority": 20
    },
    "databricks": {
      "base_url": "https://our.databricks.example.domain/serving-endpoints/databricks-claude-sonnet-4-5/invocations",
      "api_key_name": "databricks_token",
      "include_model_in_payload": false,
      "response_path": ["choices", 0, "message", "content"],
      "description": "Databricks Claude endpoint",
      "priority": 10
    }
  },
  "default_endpoint": "databricks",
  "fallback_settings": {
    "enabled": true,
    "max_fallback_attempts": 2,
    "cooldown_on_exhaustion_minutes": 15,
    "cooldown_on_lock_minutes": 30,
    "cooldown_on_rate_limit_minutes": 2,
    "cooldown_on_error_minutes": 5,
    "prefer_same_provider": false,
    "log_fallbacks": true
  },
  "models": {
    "gemini-3.1-pro-preview": {
      "endpoint": "gemini",
      "max_output_tokens": 16384,
      "temperature": 0.5,
      "description": "Most capable Gemini"
    },
    "gemini-3-flash-preview": {
      "endpoint": "gemini",
      "max_output_tokens": 16384,
      "temperature": 0.7,
      "description": "Fast and efficient"
    },
    "databricks-claude-sonnet-4-5": {
      "endpoint": "databricks",
      "max_output_tokens": 16384,
      "temperature": 0.5,
      "description": "Claude Sonnet via Databricks"
    }
  },
  "agent_model_preferences": {
    "orchestrator": "databricks-claude-sonnet-4-5",
    "developer": "databricks-claude-sonnet-4-5",
    "reviewer": "databricks-claude-sonnet-4-5",
    "researcher": "gemini-3.1-pro-preview",
    "jr_reviewer": "gemini-3-flash-preview",
    "jr_researcher": "gemini-3-flash-preview",
    "tech_writer": "gemini-3-flash-preview",
    "file_manager": "gemini-3-flash-preview",
    "archivist": "gemini-3.1-pro-preview"
  },
  "project_directory": "/home/username/my_project",
  "git": true,
  "git_auto_commit": true,
  "background_agents_enabled": true,
  "default_iteration_minutes": 5,
  "min_iterations_before_complete": 3,
  "require_human_approval": true,
  "rate_limit": {
    "max_calls_per_minute": 118
  },
  "token_budget": {
    "max_tokens_per_4h": 30000000
  },
  "file_operations": {
    "max_file_size_kb": 500,
    "ignore_patterns": [
      "*.pyc",
      "__pycache__",
      ".git",
      "node_modules",
      ".env",
      "*.db",
      "venv",
      ".venv",
      ".PrizmFoundry"
    ]
  },
  "proxy": {
    "http": "http://proxy:8080",
    "https": "http://proxy:8443"
  }
}
```

---

## Validation

### Check Configuration

Start PrizmForge to validate:

```bash
python main.py

# You should see:
✅ Loaded 9 agent prompts
✅ Database initialized
✅ System initialized
```

### Test Endpoints

```bash
👤 Human> endpoints
# Shows all configured endpoints

👤 Human> health
# Shows endpoint availability
```

### Test a Model

```python
python -c "from utils.testing import test_agent; test_agent('orchestrator')"
```

---

## Environment Variables

You can also use environment variables for sensitive data:

```json
{
  "api_key": "${GEMINI_API_KEY}",
  "databricks_token": "${DATABRICKS_TOKEN}"
}
```

Then set in your shell:
```bash
export GEMINI_API_KEY="your-key"
export DATABRICKS_TOKEN="your-token"
```

**Note:** Current version doesn't support variable expansion. Use `api_key.json` for now.

---

## Configuration Best Practices

1. **Keep `api_key.json` secure** - Never commit to version control
2. **Use absolute paths** - Avoids confusion about project location
3. **Configure multiple endpoints** - Ensures high availability
4. **Balance model assignments** - Distribute load across providers
5. **Adjust rate limits** - Match your API quota
6. **Enable background agents** - Gets continuous feedback
7. **Use git integration** - Tracks all changes
8. **Set reasonable cooldowns** - Balance recovery speed vs. API respect

---

## Quick Reference

### Essential Settings

```json
{
  "project_directory": "/path/to/project",
  "default_endpoint": "your-primary-endpoint",
  "background_agents_enabled": true
}
```

### Performance Settings

```json
{
  "rate_limit": {
    "max_calls_per_minute": 118
  },
  "token_budget": {
    "max_tokens_per_4h": 30000000
  },
  "default_iteration_minutes": 5
}
```

### High Availability Settings

```json
{
  "fallback_settings": {
    "enabled": true,
    "max_fallback_attempts": 2
  }
}
```

---

Need help? See [TROUBLESHOOTING.md](TROUBLESHOOTING.md)