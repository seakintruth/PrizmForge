# PrizmForge Roadmap / TODO
# FIRST PASS

## Plan: Stabilize PrizmForge Soak Execution and Observability

### Objective

Enable unattended soak runs to reliably:

1. Execute shell-developer commands in the intended worktree.
2. Produce governed proposals and file mutations when justified.
3. Avoid feedback backlog overload and SQLite contention.
4. Persist enough telemetry to diagnose failures without reading raw trajectory files.
5. Close task lifecycle records cleanly.

---

## Phase 0 — Preserve Evidence and Establish a Baseline

**Priority:** Immediate  
**Owner:** Developer  
**Success criterion:** Current Soak3 artifacts remain available for regression tests.

1. Preserve the current trajectory files:

```text
PrizmForge-Soak/Soak3-target/PrizmForge/.PrizmForge/shell_trajectories/
```

2. Preserve the target database:

```text
PrizmForge-Soak/Soak3-target/PrizmForge/.PrizmForge/agents.db
```

3. Add regression fixtures from representative failures:
   - prose-only response;
   - unterminated Bash fence;
   - valid closed Bash fence;
   - finish token inside a Bash block;
   - valid finish token plus summary;
   - model claiming the repository/file does not exist before issuing a command.

4. Add a regression test named similarly to:

```text
tests/unit/test_shell_developer_protocol_recovery.py
```

---

## Phase 1 — Fix Shell Developer Protocol Handling

**Priority:** Highest  
**Primary files:** `workflow/shell_developer.py`, mini-SWE prompt construction, shell-response parser  
**Success criterion:** A shell developer can inspect `workflow/__init__.py`, run a command, and either make a valid change or cleanly finish.

### 1.1 Standardize the protocol

Use one canonical completion token:

```text
FINISH_EDIT_SESSION
```

Do not support competing conventions such as:

```text
<finish>
```

The accepted forms should be exactly:

````text
```bash
pwd && ls -la
```
````

or:

```text
FINISH_EDIT_SESSION
Summary: No justified change was required after review.
```

### 1.2 Make the prompt example-driven

End the shell developer system prompt with this content:

````text
RESPONSE FORMAT — REQUIRED

Return exactly one of these forms.

To execute one command:

```bash
pwd && ls -la
```

To finish:

FINISH_EDIT_SESSION
Summary: <short summary>

Rules:
- A command reply must include both the opening ```bash line and closing ``` line.
- Emit exactly one command block per reply.
- Do not add prose outside a command block.
- Do not put FINISH_EDIT_SESSION in a code block.
- Do not ask the user to upload files or provide repository contents.
- You have shell access to the project checkout.
- Begin every task with:

```bash
pwd && ls -la && find . -maxdepth 2 -type f | head -100
```
````

### 1.3 Add narrow malformed-fence recovery

The current model frequently returns:

````text
```bash
ls -la
````

without the closing fence.

Implement a conservative normalizer before rejecting a response:

```python
def normalize_shell_reply(reply: str) -> str:
    reply = reply.strip()

    if reply.startswith("```bash\n") and not reply.endswith("\n```"):
        command = reply[len("```bash\n") :].strip()

        if command and "```" not in command:
            return f"```bash\n{command}\n```"

    return reply
```

Do **not** auto-repair:
- prose mixed with commands;
- multiple fences;
- an empty command;
- XML/JSON tool calls;
- finish tokens inside command blocks.

### 1.4 Prevent unsafe “missing file” replacement behavior

Add a developer prompt rule:

```text
Never create a task-named path merely because it cannot be found. Before
creating any missing file or directory, inspect the checkout with pwd, ls, and
find. If the requested file is absent after inspection, end the session using
FINISH_EDIT_SESSION and explain that no safe change was made.
```

This prevents unsafe output such as:

```bash
mkdir -p workflow
touch workflow/__init__.py
```

when the developer is simply confused about its workspace.

### 1.5 Improve parser diagnostics

Return structured invalid-format reasons:

```python
{
    "reason": "unterminated_bash_fence",
    "response_excerpt": "```bash\nls -la",
    "expected": "closed_bash_block_or_finish_token",
}
```

This will make failures actionable without manually reading trajectory JSON.

---

## Phase 2 — Verify the Developer Worktree and Command Execution Path

**Priority:** Highest  
**Primary files:** `workflow/shell_developer.py`, worktree/session-launch code  
**Success criterion:** The first valid command runs from the expected project root and sees `workflow/__init__.py`.

### 2.1 Add mandatory initial-workspace evidence

Before the developer may edit any file, require successful execution of:

```bash
pwd && git rev-parse --show-toplevel && ls -la && test -f workflow/__init__.py
```

Capture and persist:

- process working directory;
- Git worktree root;
- command exit code;
- stdout/stderr excerpts;
- whether the requested task path exists.

### 2.2 Fail explicitly if the session is in the wrong directory

If the command result does not identify the intended worktree, terminate with a specific error:

```text
shell developer workspace validation failed:
expected workflow/__init__.py under project root but it was not found
```

Do not continue through three model-format retries if the real issue is an invalid worktree/cwd.

### 2.3 Add tests

Test cases:

1. Correct worktree exposes `workflow/__init__.py`.
2. Empty temporary directory fails workspace validation.
3. Worktree path is not inherited from the parent repository.
4. Windows/Git Bash path handling still invokes commands in the correct directory.
5. A valid Bash response actually executes and produces captured output.

---

## Phase 3 — Add Shell Session Observability

**Priority:** High  
**Primary files:** `workflow/shell_developer.py`, `core/db.py`, `core/events.py`, model-health integration  
**Success criterion:** `query_developer_responses.py --diagnostic` explains every shell session without needing trajectory-file inspection.

### 3.1 Persist developer model responses

Store shell developer exchanges in the same response/conversation table used by ordinary agents.

Required fields:

```text
task_id
agent_name = developer
model
session_id
step_number
prompt
response
response_format_status
command
command_exit_code
timestamp
```

### 3.2 Persist shell failure events

Record these as structured errors/events:

| Condition | Suggested category |
|---|---|
| Prose response | `shell_protocol_prose_response` |
| Unterminated Bash fence | `shell_protocol_unterminated_fence` |
| Invalid finish response | `shell_protocol_invalid_finish` |
| Three invalid replies | `shell_protocol_repeated_format_error` |
| Correct finish but no mutation | `shell_session_no_mutation` |
| Wrong working directory | `shell_workspace_validation_failed` |
| Command returned non-zero | `shell_command_failed` |

### 3.3 Record model-health outcomes

Each call should produce a model-health record:

```text
transport_success
provider_response_success
protocol_valid
command_executed
command_success
session_outcome
```

A response can be transport-successful but protocol-invalid. Do not label that condition as an API failure.

### 3.4 Fix diagnostic classifier terminology

Update the trajectory inspector:

| Current label | Replacement |
|---|---|
| `HAS_BASH_BLOCK` | `VALID_BASH_BLOCK` |
| N/A | `UNTERMINATED_BASH_BLOCK` |
| `HAS_FINISH_TOKEN` | `VALID_FINISH_SESSION` |
| `NO_PROTOCOL_MARKER` | `PROSE_OR_UNSUPPORTED_FORMAT` |

Only classify a valid Bash command block when:

```python
text.strip().startswith("```bash\n") and text.strip().endswith("\n```")
```

Do not classify a parser error message containing the literal text ```` ```bash ```` as a valid Bash response.

---

## Phase 4 — Constrain Background Review and Feedback Growth

**Priority:** High  
**Primary files:** background worker dispatch, feedback ingestion, `workflow/backlog.py`, prioritizer  
**Success criterion:** A single-file seed task does not generate a repository-wide 33-item feedback backlog.

### 4.1 Scope initial review to the task target

For a seed task naming:

```text
workflow/__init__.py
```

initial background review should begin with:

```text
workflow/__init__.py
```

Optionally include direct dependencies only if explicitly configured.

Do not automatically enqueue broad files such as:

```text
workflow/task_runner.py
workflow/proposal_builder.py
utils/pre_commit.sh
utils/models_cli.py
```

unless the task is explicitly repository-wide.

### 4.2 Filter non-actionable observations

Do not create feedback items for praise or confirmation statements such as:

```text
The function correctly handles...
SQL queries properly use parameterized queries...
Robust fallback logic...
```

Require each submitted feedback item to include:

```text
problem statement
specific file path
severity
evidence
concrete suggested action
```

### 4.3 Cap initial worker fan-out

Recommended initial limits:

```text
initial peer-review files: 5
feedback items per reviewer cycle: 3
maximum unaddressed feedback before pause: 10
maximum feedback items sent to prioritizer: 10
```

### 4.4 Prioritize mutation-capable work

When a seed task exists, prioritize it ahead of broad reviewer feedback. Do not repeatedly dispatch the developer against the same vague seed task if prior shell sessions failed before executing commands.

---

## Phase 5 — Stabilize SQLite Persistence

**Priority:** High  
**Primary files:** `core/db_connection.py`, `core/db.py`, `core/token_budget.py`, archival and endpoint-health writers  
**Success criterion:** Background activity does not produce `database is locked` during normal operation.

### 5.1 Standardize database connection settings

Every SQLite connection should use:

```python
sqlite3.connect(
    db_path,
    timeout=30,
)
```

and run:

```sql
PRAGMA journal_mode=WAL;
PRAGMA busy_timeout=30000;
PRAGMA synchronous=NORMAL;
PRAGMA foreign_keys=ON;
```

### 5.2 Keep write transactions short

Do not hold database transactions open during:

- API calls;
- shell commands;
- parsing;
- LLM response handling;
- file indexing;
- test execution.

Only open the write transaction after the work result exists.

### 5.3 Retry short write operations

Use bounded retry with jitter for lock/busy errors only. Do not retry the entire agent operation due to a failed telemetry write.

### 5.4 Move toward one database writer

Use an internal event/write queue:

```text
workers -> persistence queue -> single DB writer -> SQLite
```

Prioritize this for:

- endpoint health;
- token budget;
- conversation archival;
- feedback ingestion;
- lifecycle events;
- model-health outcomes.

---

## Phase 6 — Repair Task Lifecycle Handling

**Priority:** Medium  
**Primary files:** `workflow/task_runner.py`, shutdown handling, task state helpers  
**Success criterion:** No abandoned tasks remain `in_progress` after a run stops.

### 6.1 Close every task state

Task outcomes should be one of:

```text
completed
failed
deferred
cancelled
timed_out
no_change_required
```

### 6.2 Handle interruption safely

On `KeyboardInterrupt`, timeout, shell protocol failure, or unrecoverable startup failure:

```python
mark_task_status(
    task_id,
    "failed",
    reason="shell developer protocol failure after retry limit",
)
```

For a valid session with no justified change:

```python
mark_task_status(
    task_id,
    "no_change_required",
    reason="review completed; no safe change justified",
)
```

### 6.3 Avoid direct database edits for historical Soak3

Use the existing task-state helper or administrative command to resolve the stale task. Do not manually alter SQLite unless no supported maintenance path exists.

---

## Phase 7 — Windows/Git Bash Output Reliability

**Priority:** Medium  
**Primary files:** `utils/diagnose_soak.sh`, utility launch scripts  
**Success criterion:** Reports can be redirected to files without `UnicodeEncodeError`.

Keep these exports in `diagnose_soak.sh` before Python calls:

```bash
export PYTHONUTF8=1
export PYTHONIOENCODING="utf-8"
```

Use report capture as:

```bash
./utils/diagnose_soak.sh \
  --python /c/git/programs/Python31209/python.exe \
  > ../reports/soak.txt 2>&1
```

Add a regression test that invokes the report tool with redirected output under Windows-compatible Python.

---

## Recommended Implementation Sequence

| Order | Work item | Exit criterion |
|---:|---|---|
| 1 | Shell protocol fixtures and parser tests | Valid/invalid/unterminated response cases covered |
| 2 | Prompt contract and required initial command | First response is a valid closed Bash block |
| 3 | Narrow unterminated-fence normalizer | ` ```bash\nls -la ` executes only when safe |
| 4 | Worktree/cwd validation | Developer sees `workflow/__init__.py` |
| 5 | Shell session DB events and response persistence | Diagnostics show shell replies and failures |
| 6 | Reduce initial background review fan-out | Single-file task stays single-file initially |
| 7 | Feedback quality filter | Praise is not stored as remediation feedback |
| 8 | SQLite WAL/busy timeout/retry hardening | No normal-operation lock failures |
| 9 | Single DB writer queue | High-concurrency soak remains stable |
| 10 | Task finalization paths | No stale `in_progress` tasks |

---

## Validation Run

Use a short, isolated run after Phases 1–4:

```json
{
  "background_agents_enabled": false,
  "reporter": {
    "enabled": false,
    "interval_minutes": 10
  },
  "resource_controller": {
    "enabled": false
  },
  "cli_mode": {
    "mode": "unattended",
    "unattended": {
      "max_duration_hours": 0.25,
      "max_iterations_per_task": 3,
      "auto_generate_tasks": false,
      "stop_when_backlog_empty": true,
      "seed_tasks": [
        "Inspect workflow/__init__.py. Make one small, justified improvement if needed. Do not create missing files. If no change is justified, finish with FINISH_EDIT_SESSION and a summary."
      ]
    }
  }
}
```

**Pass criteria:**

1. First shell command reports the expected worktree root.
2. `workflow/__init__.py` is visible to the developer.
3. At least one valid shell command executes.
4. Trajectory data and database response records agree.
5. Task does not remain `in_progress`.
6. No broad reviewer backlog is created.
7. The final status is either:
   - a valid proposal/write, or
   - `no_change_required` with a persisted rationale.

# FOLLOWING PASS

Single source of truth for **open** work items. Detailed design lives in the
linked documents; this file tracks status. Tick checkboxes as items land and
note the PR/commit.

Completed / shipped items are **pruned from this tracker** — completion notes
and acceptance evidence live in git history and `docs/UNATTENDED_CLOSED_LOOP_CAPABILITIES.md`.
Do not re-add shipped items or their PR maps.

**Last updated:** 2026-09-05

## Section priorities

| Section | Priority | Why |
|---|---|---|
| §0 Current state & next focus | — | Intro / index only |
| §1 Cold-soak SQLite ingest | **HIGH** | Actionable now (no live-endpoint dependency); biggest recurring soak-start win. |
| §2 Closed-loop hardening residuals | **MEDIUM** | Real UAT gaps, but blocked on live endpoints / GitHub access. |
| §3 Mini-swe agent open items | **MEDIUM** | Core validation is high-value but blocked on live endpoints; rest deferred/parked. |
| §4 Annexes / parked decisions | **LOW** | Intentional tech-debt; no urgency. |
| §5 New work this pass | **HIGH** | Soak-derived actionable fixes live here; tick as they land. |
| §6 Soak-derived endpoint latch / fallback| **HIGH** | Update endpoint latches |

**Legend:** HIGH = do next (actionable, unblocked) · MEDIUM = trackable, blocked on external deps (live endpoints / GitHub / containers) · LOW = deferred or parked by design.

## 0. Current state & next focus

- **Branch** `feat/soak-improvements` is **PR #115, in review (2026-09-05)**. It
  is built directly on `main` (PR #113 soak-diag tip) so it contains everything
  from the now-removed stale branches (`feat/roadmap`, `feat/roadmap-open-items`,
  `feat/http-error-diag`, `soak/14` — all merged via PRs #108–#113) plus Pass 1
  Phases 0–4 and the Soak10 fix. Completion notes are in git — see `git log` on
  `main`.
- **PR #115 review gate**: two merge-blocking reviewer findings (seed task must
  survive the prioritizer intake cap; praise filter must not be "no suggestion ⇒
  drop") are fixed in the branch head. Details + non-blocking nits: §5.
- **Next-up**: §1 cold-soak SQLite ingest (OPEN — design only, no branch yet).
  Then §5 soak-derived items. Note: Soak7 produced **0 materialized edits** because
  its shell session exhausted the free-model quota (HTTP 403 / goal limit), not a
  code defect — so there is no verified mutation-path finding to act on yet.
- **Soak10 recompute (2026-09-05, on `feat/soak-improvements`)**:
  - ROOT CAUSES: (1) the shell developer treated a single `None` LLM return as
    terminal (`LlmUnavailable`) instead of backing off/retrying; (2) two
    `call_endpoint` None-return paths (all-latched "no alternate endpoints" and
    token-budget carve-out) recorded **no** model-health failure, so the
    trajectory could not say whether the fatal call was rate-limiting, a health
    latch, or budget; (3) `cfg.model` was `None`, so Phase 3.3
    `record_model_outcome(None, ...)` silently dropped every session record and
    the archive `model` column stayed NULL; (4) Phase 4.2's praise filter
    dismissed the `[SEED TASK]` directive and status messages, leaving 0 valid
    prioritizer items.
  - FIXED (commits f08bd17..HEAD on `feat/soak-improvements`, in PR #115 review): record the two
    silent failure kinds (`no_alternate_endpoint`, `token_budget`); shell
    `_llm` re-resolves the model like `call_agent` each attempt (explicit
    override > RC throttle > agent prefs) and retries transient kinds
    (`rate_limited` / 5xx / timeout / latch) with linear backoff up to
    `shell_developer.llm_failure_max_retries` (default 3, 15s base), while
    permanent kinds (key_locked / token_budget / ...) give up immediately;
    Phase 3.1 archive + Phase 3.3 health records now use the resolved model;
    trajectory `model_stats`/`last_llm_failure` capture resolved model, attempt
    counts, and failure kinds; prioritizer praise filter exempts
    `seed_task`/message items.
  - RESIDUAL (track for next soak): after retries exhaust the session still
    exits `LlmUnavailable` truthfully (by design); consider surfacing the
    per-call advertised Retry-After on `rate_limited` events.

## 1. Cold-soak SQLite project ingest (NUC / 2-core / ≥8 GB)

**Status:** OPEN — design only (2026-08-31). No branch yet.

**Constraint (intentional):** soaks do **not** copy `.PrizmForge/`. Every soak
start is a **cold full rebuild** of `.PrizmForge/agents.db`. Do not plan cross-soak
hash-skip, leftover `project_files.content_hash`, or “second run is cheaper.”
The only clock that matters is **one** `cmd_init()` on a wiped DB.

**Symptom:** on a 2-core NUC, soak start spends a long time in
`🔄 Auto-indexing project files...` before iteration 1. Root is not “SQLite
is slow”; it is how init talks to SQLite.

**Hot path today**

- `main.py` → `init_db()` → `cmd_init()` (`cli/commands.py`) when
  `auto_init_on_start` is true (unattended default).
- `os.walk(project_directory)` then, **per text file**:
  1. `sync_file_to_database` — new connection, `INSERT OR REPLACE` full blob
     into `project_files`, `estimate_tokens`, **commit**.
  2. `generate_file_summary` + `save_file_summary` — **another** connection +
     commit.
  3. `initialize_file_lines` (`file_editing/writer.py`) — **another**
     connection, `DELETE FROM file_lines`, then **one `INSERT` per line** in a
     Python `for` loop (`uuid4` + md5 per line), **commit**.
- Then a fourth connection for the deleted-file pass.
- Then `refresh_target_indexes(..., force=True)`.

`initialize_file_lines` uses `file_editing.db.get_db_connection()`, which does
**not** apply `core.db_connection` pragmas. Those commits often run at SQLite
default `synchronous=FULL` (fsync per file). Runtime connections already use
`journal_mode=DELETE` + `synchronous=NORMAL` (lock-safe for soak; terrible for
bulk load). ~40k Python source lines ⇒ tens of thousands of single-row inserts
and three transactions per file.

**Non-goals**

- Do not persist `.PrizmForge/` between soaks to make init faster.
- Do not thread-pool ingest (one SQLite writer; two cores).
- Do not leave `synchronous=OFF` / `locking_mode=EXCLUSIVE` on after init.
- Do not switch the live soak DB to WAL for this item unless measured on the
  NUC; locking work assumed DELETE.
- Do not treat “daemon owns the DB” as the fix for *this* window. Init should
  be one exclusive bulk transaction, then hand the DB back.

### 1.1 Init connection + one transaction

- [ ] **`cmd_init` holds one writer** — open a single
      `core.db_connection.get_db_connection()` (or a dedicated
      `get_init_db_connection()`) for the whole walk. Pass `conn` into
      `sync_file_to_database`, `save_file_summary`, and `initialize_file_lines`
      (the last already accepts `conn=`). Commit **once** after all files + the
      deleted-file pass.
- [ ] **Never open `file_editing.db.get_db_connection()` during init** — that
      helper skips bulk pragmas and defaults to FULL sync. Either route init
      through `core.db_connection` or apply the same pragmas there (prefer the
      former so there is one writer policy).
- [ ] **Deleted-file pass uses the same `conn`** — no extra context manager.

### 1.2 Init-only pragmas (restore before iteration 1)

On the init connection, **before** the walk (8 GB floor; 2-core NUC):

```sql
PRAGMA journal_mode = MEMORY;
PRAGMA synchronous = OFF;
PRAGMA temp_store = MEMORY;
PRAGMA cache_size = -524288;     -- 512 MiB page cache
PRAGMA mmap_size = 268435456;    -- 256 MiB mmap
PRAGMA locking_mode = EXCLUSIVE;
PRAGMA busy_timeout = 5000;
```

After the single commit, **before** `cmd_init` returns:

```sql
PRAGMA locking_mode = NORMAL;
PRAGMA synchronous = NORMAL;
PRAGMA journal_mode = DELETE;
```

- `MEMORY` journal: box-crash mid-init already throws the DB away; an exception
  mid-walk can still roll back a half-built index. Prefer this over
  `journal_mode=OFF` first.
- `cache_size` 512 MiB + `mmap` 256 MiB is the intended 8 GB split. Do not
  grab multiple GB; agents + Python need the rest.
- Document in a comment that these pragmas are **init-window only**.

### 1.3 `file_lines` bulk insert

- [ ] **`_initialize_lines_impl`: `executemany`** — build the row tuples in
      Python, one `executemany` per file (or chunks of 5k–10k rows if a file
      is huge). Same columns:
      `(line_guid, file_id, sort_order, content, content_hash, version, is_deleted)`.
      Keep `uuid4` + line md5; they are cheap next to per-row `execute`.
- [ ] **Optional:** if secondary indexes on `file_lines` exist besides UNIQUE
      `line_guid`, create them **after** the bulk load (`ANALYZE` once). Do
      not drop UNIQUE `line_guid`.

### 1.4 Same-process only (not cross-soak)

- [ ] Hash short-circuit is **in-process only** (second `cmd_init()` in the
      same soak, or a mid-soak restart that did *not* wipe the live DB).
      Default soak still pays full rebuild. Do not advertise “next soak is
      faster.”

### 1.5 Work that is not required for iteration 1

- [ ] Throttle per-file `✅ {path}` prints (every 50 files + a final tally).
- [ ] `refresh_target_indexes(..., force=True)` runs **after** the DB commit
      (keep it on the cold-soak bill, or `force=False` only when an in-process
      index already exists — never assume a previous soak left one).
- [ ] `project_files.content` + `file_summaries` may stay in the same
      transaction; do not add extra commits. Do not drop `file_lines` (governed
      editor). Folding `project_files` into a later metadata-only table is
      tech-debt, not this item.

### 1.6 Files to touch

- `cli/commands.py` — `cmd_init` transaction + pragma window + print throttle.
- `file_editing/writer.py` — `_initialize_lines_impl` `executemany`.
- `core/file_operations.py` — accept optional `conn=` on
  `sync_file_to_database` / `save_file_summary`.
- `core/db_connection.py` — optional `get_init_db_connection()` so soak
  connections never inherit init pragmas.
- `tests/unit/` — new tests (no live endpoints):
  - init of N small files uses **one** commit path (spy `commit` / count
    connections).
  - `initialize_file_lines` writes expected line count + reconstructs content.
  - after init helper returns, `PRAGMA journal_mode` is `delete` and
    `synchronous` is not `OFF`.
  - `file_editing.db.get_db_connection` is not used on the init path.

### 1.7 Acceptance

- Cold soak (no `.PrizmForge/` copied) still produces a complete `files` +
  `file_lines` + `project_files` index; governed reconstruct matches disk.
- Wall-clock of `cmd_init` on the NUC drops from “noticeable stall” to a short
  burst; log the four buckets: walk+read, DB writes, deleted-file pass,
  symbol index.
- First orchestrator call still sees DELETE + NORMAL; no new dual-writer /
  `database is locked` storms vs current soak baseline.
- Gate: existing file-line / proposal / git-closed-loop tests stay green;
  ruff clean on touched files.

**Verify on the NUC, not only CI:** CI disks hide fsync cost. Time a wiped
`cmd_init()` before and after on the same tree.


## 2. Unattended closed-loop hardening — open residuals only

All shipped workstreams (A–F) are recorded in `docs/UNATTENDED_CLOSED_LOOP_CAPABILITIES.md`; the tracker keeps only what is still open.

- [ ] **Live failing-hook smoke run on a copy** — run with a deliberately failing hook; confirm CRITICAL feedback → developer fix-forward proposal → materialized and addressed, all visible in events/errors/feedback. **Blocked: live runtime/endpoints** (in-process failure paths have deterministic unit proofs in `tests/unit/test_git_closed_loop.py`).
- [ ] **PR #94 body nit** (manual GitHub edit): body still cites `tests/unit/test_writer_git_closed_loop.py`; should cite `tests/unit/test_git_closed_loop.py`. **Blocked: GitHub/manual editor access** (cosmetic, merged-PR body).
- [ ] **Ignored-path handling in the git closed loop** — a git-governed target that is gitignored (e.g. `config.json`) needs an explicit
  branch: skip git or fail with a clear "path is gitignored" message, never silent
  success. **Default parked (§4 decision 3: gitignored config stays human-only).** Source: `docs/UNATTENDED_CLOSED_LOOP_CAPABILITIES.md` §3.7.
- [ ] **Diagnostic dump shows a forced-hook-failure path** — at least one non-success path visible under events/errors after an intentional hook failure; the `git_fail` counter is already present in task summaries. **Blocked: Workstream F dump sections (`docs/UNATTENDED_CLOSED_LOOP_CAPABILITIES.md` §8.2).**

---

## 3. Mini-swe agent (shell developer) — open items only

The native port itself (core loop, disposable worktree, governed proposal
conversion, `developer.implementation: "shell"` wiring, packaging) is
**shipped and merged** — full detail in `docs/mini_swe_agent.md`. Only still-open
items are tracked here.

- [ ] **Real-model end-to-end validation + tuning** — live endpoints, prompt/limit tuning. **Blocked: live endpoints.**
- [ ] **Manual cold-start smoke** — seed task consumed on turn 1 (no `background` for two rounds), no `⚠️ Unknown model` lines. **Blocked: live endpoints.**
- [ ] **Enclave sandboxing** — shell runs are not confined to the worktree (container/approved-workstation controls for enclave deployment). **Blocked: operational/container controls.**
- [ ] **Optional hardening: post-materialize `test_command` re-run** — **Decision: intentionally deferred** (Phase-4 test-driven loop + the session's own pre-proposal `test_command` already gate every edit; a mid-session full re-run risks long/flaky hangs with no closed loop consuming it). The in-process `ruff` pre-check ships the cheap fast-feedback gate instead. Revisit only if a deploy-time validator becomes a requirement.
- [ ] **EndpointManager / LiteLLM-overlap revisit (parked)** — if verification/model routing ever moves toward a LiteLLM-style layer, revisit `EndpointManager` overlap (mini-swe follow-up #7; see `docs/mini_swe_agent.md`). **Blocked: no such routing layer planned.**

---

## 4. Annexes (strategic / parked decisions)

### 4.1 Forge Federation strategy — `Federation/Plan.md`

Active northstar: Stage 0 (current single-Territory system) → Stage 1 (enhanced
single-Territory, next) → Stage 2 (multi-Territory, future). Operates via short,
YAGNI-focused sprints with bounded, measurable experiments.

### 4.2 `report/plan.md` structural refactors (backlog / tech-debt)

Review-flagged structural items, each small, bounded, and independently scoped.
**NOTE:** The prior low-risk pair (CLI-leakage audit, `__init__.py` cleanup) is
**shipped** and pruned — its acceptance is in git. These are the still-open
mutation-path refactors and the re-scoped sleep item.

Mutation-path refactors — **parked; need a design doc before touching the governed-edit path** (higher regression risk):

- [ ] **`project_files` refactor** — normalize file metadata/index rows and their update paths.
- [ ] **Standardize errors** across file_editing — single error shape/status vocabulary instead of per-module strings.

Re-scoped (the fixed 120 s sleep is **not** in the editing loop):

- [ ] **120s-sleep behavior** — the roadmap's "editing-loop" 120 s sleeps actually live in `agents/base.py` (401/KEY_LOCKED unlock wait, proxy/auth pause) and `interactive.py` (unattended recovery). Replace with the shared `EndpointHealth.unavailable_until` latch / configurable cooldown from the shipped retry-after policy (see `core/rate_limit_headers.py`).

### 4.3 UNATTENDED plan open decisions (parked, with defaults)

1. Hook failure: fix-forward (leave disk dirty; CRITICAL fix) unless `git.revert_on_hook_failure` set — current behavior is fix-forward.
2. Create-file policy: clean relative paths OK; add prefix policy only if junk root files recur.
3. `config.json` as agent edit target: gitignored config stays human-only.
4. Reviewer sees hook output: developer primary; orchestrator summary; reviewer optional.
5. API/network failure streaks: pause + single CRITICAL summary after N consecutive failures (shipped — `NetworkBusyLoopGuard`).

---

## 5. New work this pass (from soak-review)

Placeholder for actionable items that surface from the Soak7 review and
future soak analyses. When a soak reveals a concrete, verified defect or
regression, add a dated, file-referenced entry here and tick it once fixed.
Do not add speculative or endpoint-dependent items.

Soak7 (2026-09-02) produced 54 `jr_reviewer` feedback items but **0
materialized edits**. Root cause of the 0 materializes: the task_001 shell
session exhausted the **free-model quota** (HTTP 403 / goal limit) before it
could propose — a resource constraint, **not** a code defect. Remaining noise
was API/Network + quota. Triaged below; the two SQL nits are cheap, unblocked
hardening but are **not** the soak failure and are optional:

- [ ] **OPTIONAL — Quote SQL identifiers in `cli/commands.py` DB exports** — `cmd_export_db`,
      `cmd_export_specific_tables`, `table_has_task_id` interpolate raw
      `{table_name}` into SQL/`PRAGMA` (`cli/commands.py:356,359,399,490,493`).
      Add a `_quote_identifier()` helper (double-quote + escape embedded `"`).
      (The `sqlite_master name=?` existence check is already parameterized.)
- [ ] **OPTIONAL — Robust DDL splitting in `core/db.py` `_apply_schema`** — current
      `endswith(";")` per-line split breaks if a `;` appears inside a comment
      or string literal. Replace with a comment/string-aware scanner; no new
      dependency (`sqlparse` not required).

### Soak10 → PR #115 review gate (2026-09-05)

PR #115 (`feat/soak-improvements`) is under review. Two reviewer findings are
**merge-blocking**; both are fixed in the branch head (ticked below). The nits
do not block the merge and are tracked for the next soak.

- [x] **Seed task must survive the prioritizer intake cap** — `agents/prioritizer_worker.py` `_get_all_feedback()` ordered `ORDER BY timestamp DESC LIMIT 10`. Seed rows are written at task start (oldest); ten newer reviewer items fill the cap and the seed never enters, so the Phase 4.4 8.0 boost is never applied. Fixed: `ORDER BY CASE WHEN category = 'seed_task' THEN 0 ELSE 1 END, timestamp DESC`. Regression: `test_prio_intake_seed_survives_newer_reviewer_cap`.
- [x] **Praise filter must not be "no suggestion ⇒ drop"** — `core/db_helpers.py` `is_praise_only_feedback()` returned `True` whenever the item had no suggestion, discarding real findings whose action lives in the message. Now it requires a praise phrase AND no problem/error token (a missing suggestion is irrelevant; the `suggestion` parameter is kept for the callers). Tests in `tests/unit/test_pass1_feedback_constraints.py`.

Nits (do not block — tracked):

- [ ] `<finish>` token is intentionally dead (`workflow/shell_protocol.py`). Models that still emit it burn format retries. Watch the next soak; if it recurs, accept it as an alias for one release.
- [ ] `classify_shell_reply` labels any reply containing ` ```bash ` that is not a closed block `UNTERMINATED_BASH_BLOCK` — error text that *quotes* the format gets mislabeled. Conservative (never calls invalid text valid); acceptable.
- [ ] `is_valid_bash_block` requires ` ```bash\n `; a model emitting ` ```bash\r\n ` fails. Cheap fix: strip `\r` during normalize; do if the next soak shows it.
- [ ] **CONFIRMED (2026-09-05): `record_model_outcome(ok=False)` on latch-skip / budget DOES increment model-quality demotion** — `core/model_health.py` `compute_stats` counts every `ok=False` event's `streak` / `failure_ratio` regardless of `kind`, so `no_alternate_endpoint` / `token_budget` (quota/latch, not model-quality failures) can trip `evaluate_demotion` / `_compute_down_until` and demote a healthy model on paid soaks. Exclude non-model-quality kinds from streak / failure-ratio accumulation before the next paid soak.
- [ ] Phase 2 workspace check is prompt-only (`workflow/shell_developer.py` asks the first command to be `pwd && git rev-parse --show-toplevel && ls -la`). A wrong cwd still spends format retries. Fine for PR #115; do NOT tick "fail closed if `workflow/__init__.py` missing".
- [ ] Seed-path regex `[\w./-]+\.\w+` (`agents/parallel_workers.py` `_resolve_seed_target_path`) can bind `config.json` when a seed mentions it. Longest-wins ordering + `project_files` existence lookup bounds the damage; acceptable.

## 6. Soak-derived endpoint latch / fallback

**Status:** §6.1/§6.2/§6.3/§6.4 implemented (all four; checkboxes ticked; 980 unit tests pass,
ruff clean) — pending next-soak acceptance. From Soak7 iteration 22 log (63.6m
elapsed, Work: 0.0s). Independent of free-tier quota. These four fire on paid
endpoints the first time a primary 429/503 parks and another endpoint is
still healthy.

**Symptom:** OpenRouter already latched (`LOCAL health latch: rate_limited`,
`Remaining: 0`). Support agents (prioritizer, jr_reviewer, archivist,
reporter) reprint the full last HTTP dump and print `No alternate endpoints
available — recheck in 120s`. Orchestrator retry *does* fall back to
`opencode/big-pickle`. Developer work stays `0.0s`.

**Non-goals**
- Do not spoof OpenCode CLI `User-Agent` / `x-opencode-*` headers.
- Do not treat OpenRouter `free-models-per-day` as a product bug (paid
  credits / a non-free default are the operator fix).
- Do not reopen the shipped short Retry-After 429/503 policy (§0.0).

### 6.1 Skip-path must use the same fallback as a live POST

Latch skip (`endpoint.health.is_available() is False`) must call
`get_fallback_model()` before declaring “no alternate.” Today only some
POST-failure branches fall back; the skip branch sleeps 30–120s and
returns `None`.

- [x] In `agents/base.py` `call_endpoint`, the unavailable-skip path:
      try fallback endpoint/model; if one exists, recurse/`call_endpoint`
      on it (same signature as the 429/503 fallback).
- [x] If every candidate is latched, *then* print `No alternate endpoints
      available` and use the existing bounded sleep (`min(max(wait, 30), 120)`).
- [x] Test: primary latched, fallback healthy → one POST to fallback, no
      “no alternate” line (`test_latched_primary_falls_back_to_healthy_endpoint`
      in `tests/unit/test_call_endpoint_rate_limit.py`).
- [x] Test: both latched → bounded sleep, no live POST.
      (`test_skip_path_all_parked_sleeps_bounded_backoff`)

### 6.2 Print the HTTP dump once per latch, not per agent call

`print_http_error_dump` on every skip turned one 429 into megabytes of
identical stdout. Paid bursts will do the same.

- [x] Dump (status, redacted headers, parsed error, body truncate) only
      when `mark_failure` *sets* a new `unavailable_until` (or when the
      stored dump changes).
- [x] Later skips: one line
      `⚠️  {endpoint} skipped (LOCAL health latch: {status}) — {Ns}s left`.
      Do not reprint `Last HTTP dump from when this latch was set:`.
- [x] Optional: keep the dump on `EndpointHealth.last_http_dump` for
      debug / a verbose flag; default soak stdout stays quiet.
- [x] Test: two skip-path calls under the same latch → dump appears once
      (`capfd`) (`test_local_latch_skip_prints_dump_without_calling_api`).

### 6.3 Freeze support agents while the shared latch is active

jr_reviewer format-retries and archivist batches burned the only remaining
OpenCode attempts while orchestrator/developer did no work.

- [x] When every configured endpoint is latched **or** the active
      endpoint for the foreground model is latched and no fallback is
      healthy: freeze background agents to orchestrator + developer only.
      Implemented via a shared freeze flag (`_sync_support_freeze` from
      `core/endpoint_manager.py`) honored by the support-worker hold loop
      (`agents/worker_utils.py`, prioritizer/archivist/reporter) and by the
      feedback-agent loop (`agents/parallel_workers.py` `_worker_loop`,
      jr_reviewer etc.).
- [x] Resume the previous filter when any endpoint `mark_success`s or
      `unavailable_until` expires (`is_available()` re-probes every check,
      so expiry without a mark_success still unfreezes).
- [x] Do not enqueue jr_reviewer JSON retries on an empty transport
      caused by a latch skip (`Empty response (endpoint issue) — skipping
      format retries` should be the last line, not attempt 2 and 3).
- [x] Test: latch both endpoints → prioritizer/archivist/jr_reviewer not
      called; after `mark_success` they run again.

### 6.4 `FreeUsageLimitError` is quota, not a 120s warm-up

OpenCode 429 body:

```json
{"type":"error","error":{"type":"FreeUsageLimitError","message":"Error from provider (Console): Rate limit exceeded. Please try again later."}}
```

No `Retry-After`. Current code uses the 429 status default (120s),
`Advertised wait 120s — retry same endpoint once`. That is the burst /
GPU-warm path. Console/IP daily caps need the quota path.

- [x] In `classify_rate_limit` (or a sibling on the parsed body):
      `is_quota = True` when `error.type == "FreeUsageLimitError"` or
      top-level `"type": "FreeUsageLimitError"`, even with no Reset /
      Remaining headers.
- [x] Quota branch unchanged: park (`RATE_LIMITED`, existing ~15 min cap
      or sleep-to-reset if a Reset exists), fallback immediately, **no**
      same-endpoint 120s honor.
- [x] Advertised-wait 120/300s remains only for 429/503 that are *not*
      quota.
- [x] Test: OpenCode-shaped body, no `Retry-After` → no 120s sleep, fallback
      or park (`test_call_endpoint_rate_limit.py` +
      `test_rate_limit_headers.py`).

### 6.5 Files / acceptance

- `agents/base.py` — skip-path fallback; dump-once; quota vs wait.
- `core/rate_limit_headers.py` — `FreeUsageLimitError` → `is_quota`.
- `core/http_diag.py` / `core/endpoint_manager.py` — dump stored on latch
  set, not on every skip.
- `agents/worker_utils.py` + `core/endpoint_manager.py` — support
  freeze while all endpoints latched (held via
  `hold_while_foreground_session_active`; latch path sets the flag).
- `agents/parallel_workers.py` — empty-transport jr_reviewer format-retry
  skip (already present).
- Tests as listed; ruff clean; no live endpoints.

**Acceptance (next soak, paid or free):** one 429 parks an endpoint;
stdout shows **one** dump; other agents skip in one line; orchestrator
or developer still reaches a healthy fallback; `Work:` is not 0.0s for
the rest of the run solely because support workers held the latch.

## Persistent Notes:
**Deliberate / false-positive — no change:**
- `core/db.py` `journal_mode=OFF` + `synchronous=OFF` + FK-disabled-during-apply:
  intentional init-window & mount tradeoffs — already covered by §1 here.
- `core/db_helpers.py` "SQL injection" (ids 39–43): parameterized — f-strings only
  assemble `?` placeholders or a constant `task_filter`; not injectable.
- `agent_schemas/*.json` items (ids 17–38): sample-output → formal-JSON-Schema
  would regress `get_schema_example()` (`core/agent_schemas.py:312`); excluded.
- `cli/__init__.py` empty / `datetime.now()`×3 / cosmetic nits: harmless.

---


