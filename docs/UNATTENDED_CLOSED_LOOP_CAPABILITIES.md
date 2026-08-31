# Unattended Closed-Loop Editing — Configuration & Operator Runbook

This document expands the README's [Unattended (config only, no stdin)](../README.md)
section into a complete runbook: how to configure, launch, observe, and safely
operate PrizmForge's **unattended closed-loop editing** of a target repository.

It describes **current product behavior** (the closed-loop workstreams A–F are
shipped), not a backlog. Open work items live in
[`docs/ROADMAP_TODO.md`](ROADMAP_TODO.md). For the full `config.json` schema see
[`docs/CONFIGURATION.md`](CONFIGURATION.md); for the mini-swe-style shell developer
see [`docs/mini_swe_agent.md`](mini_swe_agent.md).

---

## 1. What the capability is

PrizmForge edits a repository through a **sequential, governed mutation path**:

```
orchestrator decides → developer works in a disposable git worktree
  → proposal → reviewer gate → materialize (disk) → git add/commit
  → outcome routed back into feedback → next developer turn
```

Runs unattended for hours with **no stdin**. Every write is a structured
`EditPayload` proposal reviewed before it reaches disk; every materialize flows
through git (when enabled); every failure mode — hook failure, broken patch,
endpoint outage, stale backlog — is turned into **feedback the developer can
act on** instead of console noise.

Operator Principle #1 ([README](../README.md)) governs under load: the mutation
path is always the last thing that gets throttled; background analysis backs off
first.

### What the closed loop does for you

| Behavior | What it means on a target repo |
|----------|--------------------------------|
| Governed mutation only | Background agents can never write files; only the sequential loop mutates, via proposals through the Reviewer gate. |
| Reviewer gate fails closed | A missing/unparseable reviewer verdict REJECTs the proposal; nothing auto-approves. |
| Git closed loop | `git commit` outcome (and hook stdout/stderr) is captured. On failure the proposal is `git_failed`, an `edit.git_failed` event fires, and one deduped CRITICAL feedback row carries the hook excerpt to the developer. |
| Self-healing developer loop | A network/format/verification-failed session counts **neutral** for the no-progress guard; the latch re-arms, so mutation resumes when the endpoint recovers. |
| Backlog backpressure | As unaddressed feedback grows, lower-value reviewers pause and dedupe tightens; a large backlog enters `BACKLOG_PROCESSING` (single active work item). |
| Repo-policy awareness | `.gitignore` is honored, secrets/caches never reach agents, and an in-process `ruff` pre-check gives fast `edit.lint_failed` feedback (the hook stays authoritative). |
| Endpoint resilience | Per-model health, demotion, round-robin fallback, circuit breaker, and key-lock/quota cooldowns. |

---

## 2. Before you start

### 2.1 Target repo safety

- **Copy-first for self-edit.** For unattended runs that edit a copy of
  PrizmForge itself (or any valuable repo), work on a **copy**, never `main`.
  Production patterns assume the target tree is not clean.
- **Git is required** for the default shell developer (`developer.implementation = "shell"`):
  each session runs in a disposable `git worktree`. Point `project_directory` at a
  git repository.
- **Path containment** is enforced: resolved project paths must stay under the
  repository root (the directory containing `config.json`).
- `config.json` itself is **gitignored and human-only** — it is not a valid agent
  edit target.

### 2.2 Prerequisites

```bash
# Repo root of PrizmForge
./utils/setup.sh            # creates .venv, installs requirements + dev requirements
source .venv/bin/activate
```

- Python 3.11+, git (for worktrees), network access to your LLM endpoint(s).
- API keys in `api_key.json` (copy `example_api_key.json`; keyed by endpoint name).
- `llm.test_mode` (or `PRIZMFORGE_TEST_MODE=1`) runs everything against a mock
  LLM with scripted responses — useful for a first dry-run without keys.

---

## 3. Configure `config.json`

Start from `cp example_config.json config.json`. The keys below are the ones that
matter for an unattended run.

### 3.1 Project and mode

| Key | Example | Meaning |
|-----|---------|---------|
| `project_directory` | `"../ExampleProject"` | Target repo to edit. Resolved under repo root; created on init if absent. |
| `git` | `true` | Enable git helpers (recommended for the closed loop). |
| `git_auto_commit` | `true` | Auto-commit on successful materialize. Use with care; when **off**, the DB has the truth but disk+git diverge until a human commits. |
| `default_iteration_minutes` | `5` | Time box per orchestrator iteration. |
| `min_iterations_before_complete` | `3` | Minimum turns before the orchestrator may mark a task complete. |

### 3.2 `cli_mode.unattended`

Defaults shown are the code defaults (`core/cli_modes.py`).

```json
"cli_mode": {
  "mode": "unattended",
  "unattended": {
    "max_duration_hours": 2,
    "auto_continue": true,
    "checkpoint_interval_minutes": 15,
    "max_iterations_per_task": 30,
    "min_idle_minutes": 5.0,
    "auto_generate_tasks": true,
    "prioritize_critical_issues": true,
    "auto_init_on_start": true,
    "seed_task": "Add a docstring to app.py",
    "seed_tasks": [],
    "stop_when_backlog_empty": true,
    "exit_on_preflight_failure": true
  }
}
```

| Key | Default | Meaning |
|-----|---------|---------|
| `max_duration_hours` | `8.0` | Hard stop; the run exits after this wall-clock duration. |
| `auto_continue` | `true` | Continue tasks without confirmation prompts. |
| `checkpoint_interval_minutes` | `30` | Periodic snapshot for a later resume. |
| `max_iterations_per_task` | `20` | Cap on orchestrator turns per task. |
| `min_idle_minutes` | `5.0` | Idle time before auto actions / task transitions. |
| `auto_generate_tasks` | `true` | Derive follow-on work from feedback when the seed is done. |
| `prioritize_critical_issues` | `true` | Route CRITICAL feedback ahead of the queue. |
| `auto_init_on_start` | `true` | Index `project_directory` (file scan + symbol index) before the loop starts. |
| `seed_task` / `seed_tasks` | — | One or more seed descriptions. Injected as HIGH `seed_task` feedback on turn 1 (idempotent per task) so the loop has concrete work immediately instead of waiting for reviewer findings. |
| `stop_when_backlog_empty` | `false` | Exit when the feedback backlog drains. |
| `exit_on_preflight_failure` | `true` | Abort before running if preflight fails. |

If preflight fails (e.g. project dir not writable), the run prints the reasons and
exits — set `exit_on_preflight_failure: false` only when you know why and want the
run to continue anyway.

### 3.3 Developer implementation

```json
"developer": { "implementation": "shell" },
"shell_developer": {
  "step_limit": 30,
  "wall_time_limit_minutes": 20,
  "command_timeout_seconds": 120,
  "test_timeout_seconds": 600,
  "max_output_chars": 6000,
  "max_consecutive_format_errors": 3,
  "test_command": "python -m pytest tests/ -x -q",
  "on_test_failure": "discard",
  "model": null,
  "worktree_parent": ""
}
```

- `"shell"` (default): the agent edits inside a disposable worktree with real bash,
  then hands the collected change set through the Reviewer gate. Requires git.
  Change sets that are outside the worktree are not collected (shell escape is a
  known limitation — pair with container/sandbox controls for enclave use).
- `"edit_payload"`: the legacy structured EditPayload flow (no bash).
- `test_command` + `on_test_failure: discard` is a **fail-closed verification
  gate**: non-zero exit discards the session. Use `propose_anyway` only when you
  accept that risk.
- Session trajectories are written to `.PrizmForge/shell_trajectories/` as audit
  artifacts.

### 3.4 Closed-loop and load controls

| Key | Meaning |
|-----|---------|
| `feedback.max_unaddressed` / `max_age_days_low` | Cap on open feedback and aging of LOW items. |
| `finish_gate.high_grace_iterations` | CRITICAL always blocks completion; HIGH stops blocking after this many consecutive completion attempts. |
| `resource_controller.max_tokens_per_day` / `model_downgrades` | Daily spend cap and per-mode model downgrades; burn-rate throttling engages beyond the warning threshold. |
| `token_budget.max_tokens_per_4h` | Rolling token budget that halts the loop rather than overrunning. |
| `background_agents_enabled` + `background_agents.<name>` | Master switch + per-agent `enabled` / `on_modification` / `random_review`. |
| `reporter.interval_minutes` | How often the project reporter writes summaries. |
| `content_safety` | Binary/extension guards for governed writes (default safe). |
| `endpoints`, `default_endpoint`, `fallback_settings`*, `agent_model_preferences` | LLM backends, default routing, cross-endpoint fallback. |

\* Fallback behavior includes cooldowns (key lock, token exhaustion, rate limit)
and per-model health demotion built into the loop.

> Tip: keep `fallback_settings.enabled` on and give each endpoint a sibling model
> (`preferred_modes`/`fallback_order` under `file_editing` control editing style).
> When an endpoint is down, the loop rotates, marks the model down, and
> demotes it rather than idling.

---

## 4. Launching a run

```bash
# Optional: point the DB at the target (default is repo-root .PrizmForge/agents.db)
export PRIZMFORGE_DB_PATH=./ExampleProject/.PrizmForge/agents.db

# Real endpoints
python main.py

# Dry-run with a scripted mock LLM (no keys needed)
#   config.json: "llm": { "test_mode": true }   or:
PRIZMFORGE_TEST_MODE=1 python main.py
```

At boot you will see:

1. **Preflight** — validates unattended-run assumptions without prompting:
   `project_directory` exists/is writable and every configured endpoint has a real
   API key (key checks skipped in test mode).
2. **Auto-init** — `init` scans/indexes `project_directory` into the DB + symbol
   index (`.PrizmForge/indexes/`).
3. **Seed injection** — `🌱 Seed task registered as feedback item` on turn 1.
4. **The loop** — orchestrator decides, developer mutates, reviewer gates,
   materialize + git, feedback → prioritizer → next turn.

There is **no live console interaction** in unattended mode. The terminal is a
status feed; drive the run from config and monitor it with §6.

---

## 5. What the closed loop does at runtime

### 5.1 Mutation path

`orchestrator → developer → proposal → reviewer → materialize → git`

- Proposals capture content hashes + affected line GUIDs at creation (optimistic
  concurrency). Stale proposals fail as `conflicted`, not silently.
- The reviewer gate **fails closed** and retries once on infra-grade rejects
  (empty/unparseable); semantic REJECTs return comments to the developer directly.
- Materialize applies to the DB/file lines, writes to disk, then (with git on)
  stages and commits. Snapshot taken before materialize supports `undo`.

### 5.2 Git / hooks closed loop

With `git.enabled`:

```
materialize → git add/commit
   ├─ ok      → event edit.materialized
   └─ fail    → proposal status=git_failed
                event edit.git_failed
                errors row (CRITICAL or HIGH) with hook excerpt
                one CRITICAL feedback row, deduped by proposal_id
                → next developer turn gets the hook/pre-commit excerpt
```

- `git_auto_commit: false` + failures are captured identically; a missing commit
  is surfaced, not assumed.
- In-process `ruff` pre-check (config gate) fails the proposal to `lint_failed`
  before git, with the ruff output in feedback.
- `.gitignore` is honored (gitignored targets like `config.json` fail with a clear
  message rather than silent success); secret/cache paths never reach agents.

### 5.3 Feedback and prioritization

- Background reviewers post findings; the **prioritizer** ranks them; the
  orchestrator consumes the top item.
- Backlog backpressure: as unaddressed grows, lower-value agents pause and dedupe
  tightens; past the cap the loop runs in `BACKLOG_PROCESSING` with a single active
  work item (seed `seed_task` rows never count toward the backlog cap).
- Localized verify after success keeps the change radius to touched files; it does
  not spawn a full random review storm.

### 5.4 Self-healing under endpoint trouble

- No-progress guard: only a **finished zero-change** session builds the stall
  streak; transport/format failures are neutral, and the latch re-arms.
- Network-busy loop guard: two consecutive network-grade agent failures pause one
  iteration and write a single CRITICAL summary per outage episode.
- 429 handling: burst limits back off (AIMD); key locks and token exhaustion park
  the endpoint with a cooldown and fall over to a healthy sibling.

---

## 6. Observing a run

### 6.1 stdout signals

| You see | Meaning |
|---------|---------|
| `🌱 Seed task registered as feedback item` | Seed injected; turn-1 work exists. |
| `📋 Decision: developer` | Orchestrator chose the mutation path. |
| `⏳ Rate limited` / cooldown messages | Endpoint throttling; fallback engaged. |
| `🔒 ... KEY LOCKED` | Endpoint parked (30 min), fallback in use. |
| `git_failed` / CRITICAL feedback with hook excerpt | Pre-commit/hook violation routed to the developer. |
| `⚠️ Unknown model` | A model reference in config is unrecognized (typo); known-unlimited models use the silent 100k default. |

### 6.2 Runtime artifacts

```
<PrizmForge repo root>/.PrizmForge/        # PrizmForge's own runtime state
<project_directory>/.PrizmForge/
  agents.db                                # unified SQLite schema (tasks, events,
                                           #   edit_proposals, file_write_log, errors,
                                           #   agent_feedback, endpoint_health, ...)
  indexes/{INDEX,index_production,index_tests,index_docs}.md
  reports/                                 # reporter + git hook logs
  shell_trajectories/<task>-turn<N>-<UTC>.json   # shell developer audit trails
```

### 6.3 Diagnostic queries (read-only, live DB or a copy)

```bash
python utils/query_developer_responses.py --diagnostic            # full dump
python utils/query_developer_responses.py --diagnostic --task task_001
python utils/query_developer_responses.py --proposals             # edit proposals
python utils/query_developer_responses.py --events --limit 100    # lifecycle events
python utils/query_developer_responses.py --errors HIGH           # recent errors
python utils/query_developer_responses.py --errors --keyword materialize
python utils/query_developer_responses.py --write-log             # disk/git outcomes
python utils/query_developer_responses.py --model-health          # per-model flakiness
python utils/query_developer_responses.py --db <other>/.PrizmForge/agents.db --diagnostic
python utils/query_developer_responses.py --sql "SELECT category, COUNT(*) FROM agent_feedback GROUP BY category"
```

The dump prints a **data watermark** (`📆 data window: latest record seen ...`)
up front so a stale/copied DB snapshot can't silently skew what you read.

### 6.4 Semi-attended commands

With `cli_mode.mode = semi_attended`, `python main.py` supports typed commands:
`init`, `files`, `status`, `history`, `feedback <id>`, `health`, `reports`,
`resource_status`, `review_status`, plus free-text new tasks (`help` lists all).

---

## 7. Stopping, resuming, undo, rollback

| Question | Answer |
|----------|--------|
| When does a run stop? | `max_duration_hours` hard stop, `stop_when_backlog_empty`, token budget exhaustion, task completion, or Ctrl-C (finalizes the task instead of leaving an orphan). |
| Resume a checkpoint? | Checkpoints are saved at `checkpoint_interval_minutes` intervals so the persisted DB stays current; there is no separate resume command. Start a new run — `auto_init_on_start` re-scans and the loop continues from the existing DB state. |
| Undo a bad materialize? | `undo_proposal("<proposal_id>")` restores the pre-apply snapshot (snapshots taken automatically before materialize). |
| Roll back the developer? | `"developer": {"implementation": "edit_payload"}` (or remove the key) restores the legacy non-bash flow — no code change. |
| Revert a hook-failing edit? | Default is **fix-forward** (leave disk dirty, CRITICAL feedback) unless `git.revert_on_hook_failure` is set. |

---

## 8. Troubleshooting quick reference

| Symptom | Likely cause / next step |
|---------|--------------------------|
| Immediate exit before the loop | Preflight failure — read the printed errors; check project dir **writable** and under repo root. |
| `Unknown model` warnings every lookup | Config typo in `agent_model_preferences`/`default_model`; verify against `endpoints[].models`. |
| No seed work on turn 1 | `seed_task` missing or empty; check `cli_mode.unattended`. |
| Constant CRITICAL git failures | Pre-commit hook blocks every commit — the loop is reading the hook excerpt and fixing forward; fix the root blocker or run with `git: false` on a copy. |
| Endpoint down all night | The loop parks and falls back; see `health` / `--model-health`. OpenRouter `free-models-per-day` nights are a daily quota, not a burst — see roadmap §4 (product fix: top up the account). |
| Backlog keeps growing | Backpressure tiers are engaging by design; `BACKLOG OVERRIDE` means a single active item. Keep `seed_task` rows out of the cap (already excluded). |
| `test_command` discards edits | `on_test_failure: discard` (fail closed) is intended; use `propose_anyway` only if you accept breaking changes past a failed test gate. |

---

## 9. Related documents

- [README.md](../README.md) — quick start, core philosophy, governed editing.
- [CONFIGURATION.md](CONFIGURATION.md) — full `config.json` schema.
- [architecture.md](architecture.md) — system architecture and observability.
- [mini_swe_agent.md](mini_swe_agent.md) — shell developer implementation record.
- [ROADMAP_TODO.md](ROADMAP_TODO.md) — open work items only.