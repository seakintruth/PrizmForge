# PrizmForge Roadmap / TODO

Single source of truth for open work items. Detailed design lives in the
linked documents; this file tracks status. Tick checkboxes as items land and
note the PR/commit.

Shipped sections were retired from this tracker on **2026-08-29** (their
design + acceptance evidence live in the linked docs — see `UNATTENDED_CLOSED_LOOP_CAPABILITIES.md`).

**Last updated:** 2026-08-31

## 0.0 Handle short retry after 429 or 503 errors

This can stay on standard HTTP. The change is policy in PrizmForge: honor a **short advertised wait**, retry **once on the same endpoint**, then fallback. No new error type.

### 0.1 Goal

When a completion returns `429` or `503` with an advertised wait **≤ 600 seconds**, treat that attempt as a brief outage (including GPU warm-up):

1. Parse the wait.  
2. Latch the endpoint for that many seconds.  
3. Sleep.  
4. Retry the **same** endpoint and model **once**.  
5. If that retry fails, take the existing fallback path (`get_fallback_model` / OpenRouter in your dump).

Waits **above 600 seconds** stay on today’s path: `Rate limit cooldown too long` → fallback immediately. That is what `Retry-After: 42534` plus `FreeUsageLimitError` must continue to do.

### 0.2 Decision table

| Response | Advertised wait | Action |
|---|---|---|
| `200` with usable `choices[0].message.content` | — | Success; `mark_success()` |
| `503` or `429` | 1–600 s | Wait that long, **retry same once** |
| `503` or `429` | missing / unparseable | Use current fixed cooldown (503 → 5 min, 429 → 2 min), then retry same once |
| `503` or `429` | **> 600 s** | Do **not** wait; fallback now |
| `401` / `402` | — | Unchanged (`KEY_LOCKED` / `TOKEN_EXHAUSTED`) |
| Retry after wait still `4xx`/`5xx` or empty | — | Fallback; do not wait a second time |

Optional hint `X-Retry-Same: 1` may be logged; it must not be required. Classification is status + bounded `Retry-After` only.

### 0.3 Where the wait comes from

Prefer, in order:

1. Header `Retry-After` (delta-seconds or HTTP-date)  
2. JSON `error.retry_after_seconds` if present  
3. Status default: `429` → 120 s, `503` → 300 s  

Clamp a parsed value into `[1, 600]`. Values above 600 are **not** clamped into a 10-minute sleep; they trip the “too long → fallback” branch.

Put the parser next to the existing header work in `core/rate_limit_headers.py` (or a small helper beside it). `core/http_diag.py` already prints `Retry-After`; reuse that extraction so the dump and the latch see the same number.

## 0.4 Where to implement it

The raw client (`core/http_client.py`) should stay a single POST. The loop belongs in the caller that already does health + fallback — `core/endpoint_manager.py` and whatever wraps `call_endpoint()` in `workflow/`.

Suggested shape:

```text
attempt 1
  POST
  if success → record success, return
  wait = advertised_wait(status, headers, body)
  if wait is None or wait > 600:
      mark_failure(...)
      fallback
  mark_failure(SERVER_ERROR or RATE_LIMITED, cooldown_seconds=wait)
  log "⏳ Retry-After Ns — retry same endpoint once"
  sleep(wait)

attempt 2  (same endpoint, same payload)
  POST
  if success → mark_success, return
  mark_failure(...)
  fallback
```

`EndpointHealth.mark_failure` today takes **minutes** and ignores the header (`RATE_LIMITED` 2 min, `SERVER_ERROR` 5 min). Extend it to accept `cooldown_seconds` derived from `Retry-After`. Keep the old minute table only when no header is present.

Do **not** record a warm-up `503` as a model-quality failure in `core/model_health.py` until the **retry** also fails. Otherwise one GPU swap will demote a healthy Qwen after `down_streak: 2`.

### 0.5 Config

Add under global fallback / endpoint settings (defaults shown):

```json
"retry_after": {
  "honor": true,
  "max_wait_seconds": 600,
  "same_endpoint_retries": 1,
  "fallback_if_wait_exceeds_max": true
}
```

`same_endpoint_retries: 1` is the whole policy. Do not add a `warmup` flag or a new `EndpointStatus`.

### 0.6 Logging (match the dump you already have)

First failure:

```text
HTTP 503
endpoint: clore_qwen
Retry-After: 120
⏳ Advertised wait 120s (≤ 600s) — retry same endpoint once
```

Wait too long:

```text
HTTP 429
Retry-After: 42534
⏳ Rate limit cooldown too long (42534s)
→ Falling back to openrouter/openrouter/free
```

Retry still failing:

```text
HTTP 503
same-endpoint retry exhausted
→ Falling back to ...
```

While the latch is active, other agents should see the existing skip line (`Not calling the API — cooldown remaining Ns`) and wait on the **same** latch rather than each starting their own 600 s sleep. One shared `unavailable_until` on `EndpointHealth` already does that if the first caller sets it before sleeping.

### 0.7 Tests

Put them next to existing endpoint/health tests:

1. `503` + `Retry-After: 90` → one sleep of 90 s (mock), second POST succeeds, **no** fallback.  
2. `429` + `Retry-After: 42534` → no long sleep, fallback immediately.  
3. `503` + `Retry-After: 600` → wait 600 s, retry once.  
4. `503` + `Retry-After: 601` → fallback, no wait.  
5. `503` with no header → default 300 s, retry once.  
6. First `503` + wait, second `503` → fallback.  
7. HTTP-date `Retry-After` within 600 s → honored.  
8. Concurrent agents: only one wait; others observe the latch.  
9. Successful retry does **not** increment `model_health` failure streak.

Sleep must be injected so tests do not actually wait 600 s.

### 0.8 Out of scope for this change

- New error types (`ModelWarmingError`, `gpu_warming`).  
- Raising `model_health` `down_max_seconds` to absorb warm-up; the endpoint latch is the right layer.

### 0.9 Suggested sequence

1. Parser + unit tests for `Retry-After` and the 600 s cap.  
2. `mark_failure(..., cooldown_seconds=)`.  
3. Same-endpoint retry loop around the existing POST.  
4. Skip `record_model_outcome(ok=False)` until the retry fails.  
5. Log lines that distinguish “wait and retry same” from “cooldown too long → fallback.”  
6. Manual check with a stub server that returns 503 + `Retry-After: 2`, then 200.

That is the full engine-side plan: standard `503`/`429` + advertised wait, honor up to 600 seconds as a one-shot same-endpoint retry, then fallback — including the 32B warm-up case without a custom response type.


---

## 1. Deployed state & PR map

- `main` @ `8be697f` = **roadmap stamp for Soak9 recompute pass 2 (a9–f9)**; functional tip `6d79e5d` — see §1 (2026-08-29).
- **Soak2 recompute pass 3 — mutation-path priority (d9/index hardening)**: Soak2 (2026-08-29 16:13–~20:30) exposed that d9 counted transport-failed sessions as stall → the developer froze for whole tasks while Resource Controller reasoned *"freeze: prioritizer + developer only"*. Fixed at root (see `## 1` pass-3 entry): failed/uncompleted sessions are **neutral**, genuine finished-zero-change sessions alone build the streak, and the latch **self-heals** every `rearm_after` iterations. README now documents **Operator Principle #1 — the mutation path is the most unblocked path**. Gate → **901 passed**.
- Previous stamps: `26566f3` = PR-95 residual batch (P1–P11 + W1–W8, §1); `198f6d8` = roadmap stamp (848 → 877); `cf30bee` = PR #96 (`fit/setup-accept-pip-path`) = current `origin/main`; `954cc14` = PR #95 merge base (Workstream A Phase 1).
- Full normal gate: **877 passed** at `26566f3`; recompute pass 2 re-verified after `bc11cef`, `4821f4d`, `ae822ed`, `70d1b95`, `1646e91`, `6d79e5d` → **897 passed** (`bash utils/run_tests.sh --normal -j 4`, +20 tests, 2026-08-29), ruff clean. Pre-commit hooks (black/isort/ruff/flake8/mypy) green on every commit.
- `main` is **10 commits ahead of `origin/main`** (`cf30bee`), all pending the next PR.

### Next PR — PR-95 residuals + Soak9 recompute pass 2 (P1–P11, W1–W8, a9–f9)

Opening from `main` (`8be697f`) against `base: cf30bee` (`origin/main`).

- **Title (suggested):** `fix: PR-95 residual batch (P1–P11, W1–W8) + Soak9 recompute pass 2 (a9–f9)`
- **Head:** `8be697f` · **Base:** `origin/main` (`cf30bee`) · 10 commits.
- **Part 1 — PR-95 residuals (`26566f3` + `198f6d8`):** P1–P11 review residuals (bare single-op payloads, delete-then-recreate dedupe, seed-feedback exclusion, data-window watermark, write-log ruff gate, task finalize on hard stops, `log_error` argument hygiene, failed-unlink visibility, shell turn success semantics, honest reviewer-call accounting, non-hollow test fixes) and W1–W8 soak hardening (WIP-shipping on early exit, archivist batches + honest retry, burn-rate escalation, deferred pool start, developer lane isolation, review-queue caps, intake-soft pool backoff). Gate 848 → 877.
- **Part 2 — Soak9 recompute pass 2 (`bc11cef` … `8be697f`):** a9 archive-row prune, b9 strict JSON archive contract, c9 foreground-session backoff for support workers, d9 no-progress developer guard, e9 prioritizer post dedup, f9 background transport-error coalescing — full detail per item in §1. Gate 877 → 897 (+20 tests).
- **Merge notes:** only code-churn pan is the shared `agents/base.py` `call_agent` failure block (f9) — low collision risk; test files are additive (`test_worker_utils.py`, `test_task_runner.py`, `test_prioritizer_phases.py`, `test_archivist_context.py`).
- **Verification:** full normal gate `bash utils/run_tests.sh --normal -j 4` = **897 passed**; `ruff check .` clean; pre-commit hooks green on every commit. No live-endpoint dependencies (all in-process, hermetic).

---


## 2. Unattended closed-loop hardening — open residuals only

All shipped workstreams (A–F) are recorded in `docs/UNATTENDED_CLOSED_LOOP_CAPABILITIES.md`; the tracker keeps only what is still open.

- [ ] **Live failing-hook smoke run on a copy** — run with a deliberately failing hook; confirm CRITICAL feedback → developer fix-forward proposal → materialized and addressed, all visible in events/errors/feedback. **Blocked: live runtime/endpoints** (in-process failure paths have deterministic unit proofs in `tests/unit/test_git_closed_loop.py`).
- [ ] **PR #94 body nit** (manual GitHub edit): body still cites `tests/unit/test_writer_git_closed_loop.py`; should cite `tests/unit/test_git_closed_loop.py`. **Blocked: GitHub/manual editor access** (cosmetic, merged-PR body).
- [ ] **Ignored-path handling in the git closed loop** — a git-governed target that is gitignored (e.g. `config.json`) needs an explicit branch: skip git or fail with a clear "path is gitignored" message, never silent success. **Default parked (§5.3 decision 3: gitignored config stays human-only).** Source: `docs/UNATTENDED_CLOSED_LOOP_CAPABILITIES.md` §3.7.
- [ ] **Diagnostic dump shows a forced-hook-failure path** — at least one non-success path visible under events/errors after an intentional hook failure; the `git_fail` counter is already present in task summaries. **Blocked: Workstream F dump sections (`docs/UNATTENDED_CLOSED_LOOP_CAPABILITIES.md` §8.2).**

---

## 3. Mini-swe agent (shell developer) — shipped + open items

### Shipped (2026-08-23 → 2026-08-28; gates 616 → 623 → 693 → 724, plus 2026-08-29 closed-loop residuals)

**SHIPPED & MERGED**: native mini-swe-agent port as the shell developer
(`workflow/shell_developer.py`, MIT attribution + material differences in
`THIRD_PARTY_NOTICES.md`). Original 5-item plan landed in full:

1. Native port of the mini-swe-agent core loop (worktree + bash).
2. Disposable `git worktree` isolation per session; real bash edits + post-session `test_command` verification.
3. Session output converted to governed EditPayload proposals → Reviewer → materialize.
4. Wired into the task loop behind `developer.implementation` (`"shell"` default, `"edit_payload"` legacy fallback).
5. Packaging/tooling (`setup.sh` git prereq; `export_project_zip.py` excludes runtime artifacts).

Capability/operator runbook: `docs/mini_swe_agent.md`. Rollback: `developer.implementation: "edit_payload"` (no code change).

### Open items

- [ ] **Real-model end-to-end validation + tuning** — live endpoints, prompt/limit tuning. **Blocked: live endpoints.**
- [ ] **Manual cold-start smoke** — seed task consumed on turn 1 (no `background` for two rounds), no `⚠️ Unknown model` lines. **Blocked: live endpoints.**
- [ ] **Enclave sandboxing** — shell runs are not confined to the worktree (container/approved-workstation controls for enclave deployment). **Blocked: operational/container controls.**
- [ ] **Optional hardening: post-materialize `test_command` re-run** — **Decision: intentionally deferred** (Phase-4 test-driven loop + the session's own pre-proposal `test_command` already gate every edit; a mid-session full re-run risks long/flaky hangs with no closed loop consuming it). The §7.2 in-process `ruff` pre-check ships the cheap fast-feedback gate instead. Revisit only if a deploy-time validator becomes a requirement.
- [ ] **EndpointManager / LiteLLM-overlap revisit (parked)** — if verification/model routing ever moves toward a LiteLLM-style layer, revisit `EndpointManager` overlap (mini-swe follow-up #7; see `docs/mini_swe_agent.md`). **Blocked: no such routing layer planned.**

## 4. Annexes (strategic / parked decisions)

### N.1 Forge Federation strategy — `Federation/Plan.md`

Active northstar: Stage 0 (current single-Territory system) → Stage 1 (enhanced
single-Territory, next) → Stage 2 (multi-Territory, future). Operates via short,
YAGNI-focused sprints with bounded, measurable experiments.

### N.2 `report/plan.md` file_editing structural refactors

Review-flagged structural items. **Decision (2026-08-29): FOLDED INTO BACKLOG AS TECH-DEBT** — each is small, bounded, and independently scoped; a future sprint can pick them up without a dedicated design doc.

- [ ] **`project_files` refactor** — normalize file metadata/index rows and their update paths.
- [ ] **Standardize errors** across file_editing — single error shape/status vocabulary instead of per-module strings.
- [ ] **120s-sleep behavior** — the legacy fixed sleep in the editing loop: replace with event-driven wait or configurable strategy.
- [ ] **CLI command leakage** — audit `cli.commands` for shelled-out / ungoverned commands that bypass the governed edit path.
- [ ] **`__init__.py` cleanup** — remove obsolete re-exports in `file_editing/__init__.py`.

### N.3 UNATTENDED plan §15 open decisions (parked, with defaults)

1. Hook failure: fix-forward (leave disk dirty; CRITICAL fix) unless `git.revert_on_hook_failure` set — current behavior is fix-forward.
2. Create-file policy: clean relative paths OK; add prefix policy only if junk root files recur.
3. `config.json` as agent edit target: gitignored config stays human-only.
4. Reviewer sees hook output: developer primary; orchestrator summary; reviewer optional.
5. API/network failure streaks: pause + single CRITICAL summary after N consecutive failures (shipped — `NetworkBusyLoopGuard`).

## 5. Cold-soak SQLite project ingest (NUC / 2-core / ≥8 GB)

**Status:** OPEN — design only (2026-08-31). No branch yet.

**Constraint (intentional):** soaks do **not** copy `.PrizmForge/`. Every soak
start is a **cold full rebuild** of `prizmforge.db`. Do not plan cross-soak
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

### N.1 Init connection + one transaction

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

### N.2 Init-only pragmas (restore before iteration 1)

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

### N.3 `file_lines` bulk insert

- [ ] **`_initialize_lines_impl`: `executemany`** — build the row tuples in
      Python, one `executemany` per file (or chunks of 5k–10k rows if a file
      is huge). Same columns:
      `(line_guid, file_id, sort_order, content, content_hash, version, is_deleted)`.
      Keep `uuid4` + line md5; they are cheap next to per-row `execute`.
- [ ] **Optional:** if secondary indexes on `file_lines` exist besides UNIQUE
      `line_guid`, create them **after** the bulk load (`ANALYZE` once). Do
      not drop UNIQUE `line_guid`.

### N.4 Same-process only (not cross-soak)

- [ ] Hash short-circuit is **in-process only** (second `cmd_init()` in the
      same soak, or a mid-soak restart that did *not* wipe the live DB).
      Default soak still pays full rebuild. Do not advertise “next soak is
      faster.”

### N.5 Work that is not required for iteration 1

- [ ] Throttle per-file `✅ {path}` prints (every 50 files + a final tally).
- [ ] `refresh_target_indexes(..., force=True)` runs **after** the DB commit
      (keep it on the cold-soak bill, or `force=False` only when an in-process
      index already exists — never assume a previous soak left one).
- [ ] `project_files.content` + `file_summaries` may stay in the same
      transaction; do not add extra commits. Do not drop `file_lines` (governed
      editor). Folding `project_files` into a later metadata-only table is
      §5.2 tech-debt, not this item.

### N.6 Files to touch

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

### N.7 Acceptance

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


## 7. Optional PostgreSQL via SQLAlchemy (SQLite remains default)

**Status:** OPEN — design only (2026-08-31). No branch yet. Depends on §6
(cold-soak ingest) only in the sense that **init bulk-load must stay a
first-class path** on both backends; do not block §6 on this.

**Why:** SQLite is correct for NUC soaks, hermetic tests, and wiped
`.PrizmForge/` isolation. A shared or multi-writer deploy (later federation
§5.1, long-lived operator DB, concurrent soaks against one store) needs a
server engine. The product switch is **configuration**, not a fork.

**Default stays SQLite.** Postgres is opt-in. CI and `utils/run_tests.sh`
stay on SQLite unless an explicit extra job is added.

### N.1 Decision: SQLAlchemy Core first, not ORM-everywhere

The schema lives as a large raw-SQL string in `core/db.py` (`init_db`,
`_apply_schema`, `_migrate_schema`) plus two connection helpers
(`core/db_connection.py`, `file_editing/db.py`) and dozens of
`conn.execute("""...""")` call sites. An overnight ORM rewrite of
`file_lines` / proposals / workers will stall the mutation path.

- **Phase A:** SQLAlchemy **engine + connection** facade. Call sites keep
  textual SQL (`sqlalchemy.text`) until each module is touched for another
  reason.
- **Phase B:** SQLAlchemy `MetaData` / `Table` models for schema create +
  migrations (replace the string blob + `PRAGMA table_info` ALTER loop).
- **Phase C (optional, later):** ORM mapped classes only where it removes
  duplication (e.g. `edit_proposals`, `agent_feedback`). Line store and
  archives can stay Core/`executemany` forever.

Do not introduce Django, Tortoise, or a second query layer.

**Dependencies (pin in extras, not required for default install):**

```text
sqlalchemy>=2.0,<3
psycopg[binary]>=3.1    # Postgres driver only when backend=postgresql
```

Suggested extra: `pip install -e ".[postgres]"`. SQLite uses SQLAlchemy’s
bundled `sqlite3` dialect — no extra package.

### N.2 Configuration (files, not env-only)

Add a top-level `database` object to `config.json` / `example_config.json`.
Document in `docs/CONFIGURATION.md`. Secrets stay in `api_key.json` (or a
sibling gitignored file), never in `config.json`.

```json
"database": {
  "backend": "sqlite",
  "sqlite": {
    "path": null
  },
  "postgresql": {
    "host": "127.0.0.1",
    "port": 5432,
    "name": "prizmforge",
    "user": "prizmforge",
    "sslmode": "prefer",
    "connect_timeout_s": 10
  }
}
```

- `backend`: `sqlite` (default) | `postgresql`. Unknown value → `ValueError`
  at `validate_config`.
- `sqlite.path`: `null` keeps today’s rule (`PRIZMFORGE_DB_PATH` else
  `<project>/.PrizmForge/agents.db`).
- Postgres password: `api_key.json` → `keys.database.password` (or
  `keys.postgresql.password`). Mirror endpoint-key style. Empty password +
  `backend=postgresql` → fail closed at startup.
- Optional override URL (operator/CI only): env `PRIZMFORGE_DATABASE_URL`
  wins over `backend`+fields. Allowed schemes: `sqlite`, `sqlite+pysqlite`,
  `postgresql`, `postgresql+psycopg`. Reject `postgres://` ambiguity or
  normalize it once in code.

`validate_config` checks types only. Reachability is `init_db()` /
preflight, not config parse (so unit tests can load configs without a
server).

Unattended preflight (`core/preflight.py`): if `backend=postgresql`,
require the extra installed and a successful `SELECT 1` before soak start.

### N.3 Single engine facade

Replace the split `sqlite3.connect` world with one module, e.g.
`core/db_engine.py`:

- `get_engine()` — process singleton, built from config.
- `session_scope()` / `connection_scope()` — context manager that yields a
  connection with `commit`/`rollback` matching `get_db_connection`.
- `get_db_path()` remains for SQLite file location and diagnostics; Postgres
  returns the sanitized URL (`password` redacted).

**SQLite engine kwargs (preserve soak locking story after §6 init window):**

- `connect_args={"timeout": 30}` (or current values).
- `poolclass=NullPool` (or `StaticPool` + `check_same_thread=False` only if
  a measured single-connection soak needs it). Default: **NullPool** so we
  do not invent a second writer pool on the file DB.
- On connect: `PRAGMA journal_mode=DELETE`, `synchronous=NORMAL`,
  `temp_store=MEMORY`, `foreign_keys=ON` — same as `core/db_connection.py`
  today. §6 init pragmas stay a **separate** connect event or
  `execution_options` used only by `cmd_init`.

**Postgres engine kwargs:**

- `poolclass=QueuePool`, small pool (`pool_size=5`, `max_overflow=5`) on an
  8 GB NUC; configurable later.
- `pool_pre_ping=True`.
- `isolation_level` default (READ COMMITTED). Do not copy SQLite’s
  `EXCLUSIVE` / `journal_mode` onto Postgres.
- `statement_timeout` via `SET` on connect if we see runaway queries.

**Deprecate, then delete:**

- `file_editing.db.get_db_connection` — must call the facade (it currently
  skips pragmas; that is already a soak footgun).
- Raw `sqlite3.connect` in `core/db.py` `init_db`, `core/model_health.py`,
  workers, `utils/query_developer_responses.py`.
- Keep `sqlite3` only inside the SQLite dialect connect hook and tests that
  assert PRAGMA.

`DatabaseRetryError` + wall-clock commit budget stay for SQLite lock/busy.
On Postgres map deadlocks / `lock_not_available` to the same exception so
callers do not grow a second retry vocabulary.

### N.4 Dialect-safe SQL (inventory before rewrite)

Textual SQL that is **SQLite-only** today and must be parameterized or
branched:

| Pattern | SQLite today | Postgres |
|---|---|---|
| Surrogate keys | `INTEGER PRIMARY KEY AUTOINCREMENT` | `INTEGER GENERATED BY DEFAULT AS IDENTITY` (or `SERIAL`) |
| Upsert | `INSERT OR REPLACE` (`project_files`, `file_summaries`) | `INSERT … ON CONFLICT (file_path) DO UPDATE SET …` |
| Instant | `datetime('now')`, `CURRENT_TIMESTAMP` | `NOW()`, `CURRENT_TIMESTAMP` |
| Booleans | `INTEGER 0/1` | keep `SMALLINT`/`INTEGER` in v1 (do not flip to native `BOOLEAN` mid-migration) |
| Singleton rows | `CHECK (id = 1)` (`cli_checkpoints`, `reporter_state`) | same CHECK, or `INSERT … ON CONFLICT (id)` |
| Introspection | `PRAGMA table_info`, `sqlite_master` | `information_schema.columns` / Alembic |
| Bulk init | §6 `executemany` + MEMORY journal | `psycopg` `executemany` or `COPY` for `file_lines` only if measured |
| FKs | `PRAGMA foreign_keys=ON` | always on |

Rules:

- No `SELECT *` new code; column lists survive dialect type drift.
- Placeholders: SQLAlchemy `text("… WHERE file_path = :path")` bound
  params. Ban `f"SELECT … {table}"` except for the existing export helper
  after an allowlist.
- `lastrowid` after `INSERT INTO files` must use
  `inserted_primary_key` / `RETURNING file_id` on Postgres.
- `Row` access: keep both index and key (`row["file_id"]`) via
  `mappings()`.

Phase A may wrap the worst call sites (`INSERT OR REPLACE`, `lastrowid`,
`datetime('now')`) in `core/db_sql.py` helpers keyed by dialect name.

### N.5 Schema create + migrations

Today: one SQL blob + additive `_ensure_column` for old files.

Target:

- [ ] **SQLAlchemy `MetaData` in `core/schema.py`** — one `Table()` per
      existing table (start with the critical set: `files`, `file_lines`,
      `edit_proposals`, `messages`, `tasks`, `errors`, `agent_feedback`,
      `project_files`, `events`). Remaining tables can stay in the blob for
      one PR if listed explicitly.
- [ ] **`init_db()`** becomes `metadata.create_all(engine)` + dialect
      connect pragmas (SQLite only).
- [ ] **Alembic** (`alembic/`) for additive migrations from that point.
      First revision = “schema as of this PR” (empty upgrade on a fresh
      `create_all`). Stop hand-written `_ensure_column` for new columns.
- [ ] SQLite file DBs from older soaks: still support `_migrate_schema`
      **or** one-shot “wipe and recreate” because soaks already throw
      `.PrizmForge/` away. Do not invent a production SQLite upgrade story
      beyond current additive columns unless an operator keeps a durable
      file DB.

Postgres: never run `PRAGMA`. Never run §6 `journal_mode=MEMORY`. Init
performance work for Postgres is a different checklist (`COPY` / unlogged
`file_lines` during load, then `ALTER TABLE … SET LOGGED`) — park unless a
soak actually uses Postgres.

### N.6 Product behavior that must not change

- Default `backend=sqlite`, path under `.PrizmForge/`, wiped per soak.
- Governed reconstruct (`file_lines` + `sort_order` + `is_deleted`) identical.
- Tests use tmp SQLite; no Docker required for `run_tests.sh --normal`.
- `log_error` stays non-blocking (short timeout / best-effort) on both
  backends.
- Dual-writer rule on SQLite is unchanged: one writer during materialize;
  do not open a second engine against the same file.

### N.7 Phased delivery

- [ ] **7.A — Config + engine + SQLite parity**  
      `database` block, `get_engine()`, migrate `init_db` +
      `get_db_connection` + `file_editing.db` to the facade. Behavior on
      SQLite indistinguishable. Gate green. No Postgres CI yet.
- [ ] **7.B — Dialect helpers + lastrowid/upsert**  
      Fix the inventory in §7.4 at the highest-traffic writers
      (`file_operations`, `writer.initialize_file_lines`,
      `proposal_builder`, `db_helpers`). Unit tests run the same SQL
      helpers against a SQLite engine.
- [ ] **7.C — Postgres smoke (optional extra)**  
      `tests/integration/test_postgres_smoke.py` marked `@pytest.mark.postgres`,
      skipped without `PRIZMFORGE_DATABASE_URL`. Creates schema, indexes one
      file, reconstructs lines, writes one proposal row. Document compose
      snippet in `docs/soak_runbook.md` (do not make compose the default
      soak).
- [ ] **7.D — Alembic + MetaData**  
      Move off the schema string. One documented `alembic upgrade head` for
      durable Postgres; SQLite soaks still `create_all` on empty file.

### N.8 Files to touch (7.A minimum)

- `core/config.py` + `docs/CONFIGURATION.md` + `example_config.json`
- `example_api_key.json` — `keys.database.password` placeholder
- `core/db_engine.py` (new), `core/db.py`, `core/db_connection.py`,
  `file_editing/db.py`
- `core/preflight.py` — Postgres reachability
- `pyproject.toml` / install extras
- `tests/unit/test_db_engine.py` — backend selection, URL redaction,
  SQLite PRAGMA on connect, reject unknown backend
- `tests/unit/test_db_retry_patience.py` — still valid on SQLite engine

### N.9 Acceptance

- `backend` omitted or `"sqlite"` → bit-identical operator story to
  current `main` (path, pragmas after init, tests).
- `backend: "postgresql"` without password / extra / server → **fail
  closed** with an actionable message, no silent SQLite fallback.
- No password in logs, events, or `get_db_path()` print.
- Ruff clean; normal gate does not require Postgres.
- §6 init pragmas still compile and apply **only** when dialect is SQLite.

### N.10 scope

- Multi-tenant Postgres, read replicas, federation Stage 2.
- Moving agent JSON blobs into JSONB in the first Postgres PR (TEXT is
  fine; JSONB is a later migration).
- Replacing the message bus with Redis/NATS.
- SQLAlchemy 1.4 APIs (`Query`, `sessionmaker` legacy binds).

---
