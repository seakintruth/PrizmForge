# PrizmForge Roadmap / TODO

Single source of truth for **open** work items. Detailed design lives in the
linked documents; this file tracks status. Tick checkboxes as items land and
note the PR/commit.

Completed / shipped items are **pruned from this tracker** — completion notes
and acceptance evidence live in git history and `docs/UNATTENDED_CLOSED_LOOP_CAPABILITIES.md`.
Do not re-add shipped items or their PR maps.

**Last updated:** 2026-09-02

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

- **Branch** `feat/roadmap` is merged into `main` / `origin/main` (2026-09-02).
  The most recent shipped work on that branch: short Retry-After 429/503 policy
  (last updated 2026-09-01), CLI-leakage audit + `__init__.py` cleanup, doc
  edits verified by soak, and the shell-developer reviewer diff-truncation fix.
  All completion notes are in git — see `git log` on `feat/roadmap` / `main`.
- **Next-up**: §1 cold-soak SQLite ingest (OPEN — design only, no branch yet).
  Then §5 soak-derived items. Note: Soak7 produced **0 materialized edits** because
  its shell session exhausted the free-model quota (HTTP 403 / goal limit), not a
  code defect — so there is no verified mutation-path finding to act on yet.

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


