# PrizmForge Configuration Schema

Authoritative reference for `config.json` and related files.  
**Template:** copy `example_config.json` → `config.json`.  
**Secrets:** copy `example_api_key.json` → `api_key.json` (gitignored).

Keys beginning with `_` in examples are documentation only and ignored at runtime.

Validation runs at load (`core.config.validate_config`). Invalid types raise `ValueError`.

---

## Files

| File | Role |
|------|------|
| `config.json` | Runtime settings (this schema) |
| `example_config.json` | Checked-in template with sample values |
| `api_key.json` | Secrets keyed by **endpoint name** (`keys.<endpoint>.api_key`) |
| `example_api_key.json` | Placeholder template in the same shape |
| `agent_prompts.json` | Agent system prompts (not covered here) |

---

## Top-level keys

| Key | Type | Default / required | Description |
|-----|------|--------------------|-------------|
| `project_directory` | string | **required** | Working tree for agent file ops. May be created on init; resolved path must stay under **repo root** (directory containing `config.json`). |
| `git` | bool | `false` | Enable git helpers |
| `git_auto_commit` | bool | `false` | Auto-commit after successful materialize (use with care) |
| `default_iteration_minutes` | number | `5` | Time box per orchestrator iteration |
| `min_iterations_before_complete` | int | `3` | Orchestrator should not complete before this many turns |
| `background_agents_enabled` | bool | `true` | Product default: background analysis pool on |
| `default_model` | string | optional | Fallback model reference (bare model id or `endpoint/model`) when no agent preference applies |
| `default_endpoint` | string | optional | Name of default entry in `endpoints` |
| `cli_mode` | object | optional | Interactive / unattended mode (see below) |
| `endpoints` | object | optional | Named HTTP LLM backends |
| `fallback_settings` | object | optional | Cross-endpoint fallback policy |
| `models` | object | optional | Model id → endpoint + generation params |
| `agent_model_preferences` | object | optional | Agent name → model reference (bare id or `endpoint/model`; resolved via `normalize_model_reference`) |
| `proxy` | object | optional | HTTP(S) proxy URLs |
| `token_budget` | object | optional | Spend limits |
| `reporter` | object | optional | Project reporter worker |
| `resource_controller` | object | optional | Throttle / budget controller |
| `background_agents` | object | optional | Per-agent background flags |
| `background_feeder` | object | optional | Feeder interval / batch size |
| `file_operations` | object | optional | Index/ignore rules |
| `file_editing` | object | optional | Multi-mode edit policy |
| `feedback` | object | optional | Backlog aging |
| `content_safety` | object | optional | Binary / extension guards |

---

## `cli_mode`

| Key | Type | Description |
|-----|------|-------------|
| `mode` | string | `interactive` \| `semi_attended` \| `unattended` |
| `unattended` | object | Used when mode is unattended |

### `cli_mode.unattended`

| Key | Type | Description |
|-----|------|-------------|
| `max_duration_hours` | number | Hard stop duration |
| `auto_continue` | bool | Continue tasks without prompt |
| `checkpoint_interval_minutes` | number | Checkpoint cadence |
| `max_iterations_per_task` | int | Cap turns per task |
| `min_idle_minutes` | number | Idle before auto actions |
| `auto_generate_tasks` | bool | Generate follow-on work |
| `prioritize_critical_issues` | bool | Prefer CRITICAL feedback |

---

## `endpoints` (map of name → endpoint)

| Key | Type | Description |
|-----|------|-------------|
| `base_url` | string | Chat-completions URL |
| `api_key_name` | string | Optional field name inside this endpoint's entry in `api_key.json:keys` (default `api_key`) |
| `key_management_url` | string | Human unlock / key UI (optional) |
| `include_model_in_payload` | bool | Send `model` field in body |
| `response_path` | array | Path to assistant text (e.g. `["choices",0,"message","content"]`) |
| `description` | string | Label |
| `priority` | int | Lower = preferred on ties (convention) |
| `rate_limit_per_minute` | number | Soft client-side limit |

---

## `fallback_settings`

| Key | Type | Description |
|-----|------|-------------|
| `enabled` | bool | Enable endpoint failover |
| `max_fallback_attempts` | int | Attempts across endpoints |
| `cooldown_on_exhaustion_minutes` | number | |
| `cooldown_on_lock_minutes` | number | API key lock |
| `cooldown_on_rate_limit_minutes` | number | |
| `cooldown_on_error_minutes` | number | |
| `prefer_same_provider` | bool | |
| `log_fallbacks` | bool | |

---

## `models` (map of model id → spec)

| Key | Type | Description |
|-----|------|-------------|
| `endpoint` | string | Key into `endpoints` |
| `max_output_tokens` | int | |
| `temperature` | number | |
| `max_context_tokens` | int | Optional context window hint |
| `description` | string | |

---

## `agent_model_preferences`

Map of agent name → model id string. Typical agents:

`orchestrator`, `developer`, `reviewer`, `researcher`, `prioritizer`,  
`jr_reviewer`, `jr_researcher`, `tech_writer`, `file_manager`, `archivist`,  
`project_reporter`, `resource_controller`, `deployment_validator`, `security_reviewer`

---

## `proxy`

| Key | Type | Description |
|-----|------|-------------|
| `http` | string | Proxy URL or empty to disable |
| `https` | string | Proxy URL or empty to disable |

---

## `token_budget`

| Key | Type | Description |
|-----|------|-------------|
| `max_tokens_per_4h` | int | Rolling window budget used by `TokenBudget` |

---

## `reporter`

| Key | Type | Description |
|-----|------|-------------|
| `enabled` | bool | |
| `interval_minutes` | number | |
| `change_threshold_percent` | number | |
| `change_threshold_lines` | int | |
| `include_git_commits` | bool | |
| `include_agent_activity` | bool | |
| `max_reports_to_keep` | int | |
| `report_trigger_cooldown_minutes` | number | |

---

## `resource_controller`

| Key | Type | Description |
|-----|------|-------------|
| `enabled` | bool | |
| `check_interval_seconds` | number | |
| `max_tokens_per_day` | int | |
| `aggressive_throttling_threshold` | number | 0-1 budget fraction |
| `project_goals` | object | Human-owned goals (treat as immutable for agents) |

### `resource_controller.project_goals`

| Key | Type | Description |
|-----|------|-------------|
| `max_daily_cost_usd` | number | |
| `priority_focus` | string[] | e.g. `["security","performance"]` |
| `human_only_adjust` | bool | |
| `notes` | string | |

---

## `background_agents` (map of agent → flags)

| Key | Type | Description |
|-----|------|-------------|
| `enabled` | bool | |
| `on_modification` | bool | Queue on file change |
| `random_review` | bool | Random sample reviews |
| `random_files_per_cycle` | int | |
| `confidence_threshold` | number | Optional (e.g. deployment_validator) |

---

## `background_feeder`

| Key | Type | Description |
|-----|------|-------------|
| `interval_seconds` | number | Feeder wake interval |
| `files_per_agent_default` | int | Batch size |

---

## `file_operations`

| Key | Type | Description |
|-----|------|-------------|
| `max_file_size_kb` | int | Skip larger files on index |
| `ignore_patterns` | string[] | Glob-like ignore list |

---

## `file_editing`

Multi-mode edit policy (t-shirt size + fallback).

| Key | Type | Description |
|-----|------|-------------|
| `method` | string | Soft legacy preference: `guid` \| `find_replace` \| `full_replace` \| `diff` (also accepts legacy `guid_sloc`, `planned_diff`) |
| `preferred_modes` | string[] | Ordered soft preferences |
| `fallback_order` | string[] | Fallback chain on invalid LLM JSON |
| `small_file_threshold_lines` | int | Prefer full_replace below this size |

Validated mode names: `guid`, `guid_sloc`, `find_replace`, `full_replace`, `diff`, `planned_diff`.

---

## `feedback`

Backlog aging for unattended runs.

| Key | Type | Description |
|-----|------|-------------|
| `max_age_days_low` | int | Dismiss old LOW items |
| `max_unaddressed` | int | Cap total open feedback |

---

## `content_safety`

Binary / installer protection for governed writes (`full_replace`, `create_file`, disk materialize).

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `disallow_binary_content` | bool | `true` | Reject PE/MSI/OLE magic, NULs, high non-text byte ratio |
| `blocked_extensions` | string[] | built-in catalog | Path suffixes to refuse. **`[]`** = no extension blocking. Omit key = use built-in default list |

Built-in default extensions (when key omitted):

`.msi` `.msp` `.msm` `.msu` `.exe` `.dll` `.sys` `.com` `.scr` `.cpl` `.ocx` `.drv` `.bin` `.iso` `.img` `.dmg` `.appx` `.appxbundle` `.msix` `.cab`

Text scripts (`.ps1`, `.bat`, `.cmd`, `.js`, ...) are **not** in that catalog.

To allow an MSI **path**, remove `.msi` from `blocked_extensions`. Real MSI **bytes** are still blocked while `disallow_binary_content` is true.

---

## `api_key.json` schema

Structured form, keyed by **endpoint name** (must match an entry in `config.json:endpoints`).
Supports any number of endpoints; no per-provider variable names.

```json
{
  "_comment": "Secrets per endpoint. This file is gitignored.",
  "keys": {
    "gemini":     { "api_key": "..." },
    "beta_genai": { "api_key": "...", "custom_field": "..." }
  }
}
```

Resolution (`EndpointManager.get_api_key`):
1. `keys.<endpoint_name>.<endpoint.api_key_name>` when the endpoint sets a custom `api_key_name`
2. otherwise `keys.<endpoint_name>.api_key`

Legacy flat form (`{"gemini_api_key": "..."}`) is **rejected at load** with a
pointer to `example_api_key.json`.

---

## Minimal valid config

```json
{
  "project_directory": "./project"
}
```

All other sections are optional; code uses safe defaults where possible. `project_directory` is required for path containment.

---

## Related code

| Concern | Module |
|---------|--------|
| Load / validate | `core/config.py` |
| Content safety | `core/content_safety.py` |
| Repo-root project dir | `core/config.ensure_project_directory` |
| Edit mode selection | `workflow/edit_mode_selector.py` |


## Target repository indexes

After CLI `init` (and after each successful materialize), structural indexes are written to:

```text
<project_directory>/.PrizmForge/indexes/
  INDEX.md
  index_production.md
  index_tests.md
  index_docs.md
```

- **Indexes only** (default on init / post-write): no full source dump.
- **Full consolidation** (PrizmForge self or optional): `python utils/consolidate.py` or `--full`.
- **Target indexes only:** `python utils/consolidate.py --target --indexes-only`

Agents (orchestrator, prioritizer, developer) load truncated slices via `core.index_context`.
