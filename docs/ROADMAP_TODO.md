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
| §2 Optional PostgreSQL | **LOW** | Deferred by design; only needed for multi-writer/federation deploys not planned yet. |
| §3 Closed-loop hardening residuals | **MEDIUM** | Real UAT gaps, but blocked on live endpoints / GitHub access. |
| §4 Mini-swe agent open items | **MEDIUM** | Core validation is high-value but blocked on live endpoints; rest deferred/parked. |
| §5 Annexes / parked decisions | **LOW** | Intentional tech-debt; no urgency. |
| §6 New work this pass | **HIGH** | Soak-derived actionable fixes live here; tick as they land. |

**Legend:** HIGH = do next (actionable, unblocked) · MEDIUM = trackable, blocked on external deps (live endpoints / GitHub / containers) · LOW = deferred or parked by design.

## 0. Current state & next focus

- **Branch** `feat/roadmap` is merged into `main` / `origin/main` (2026-09-02).
  The most recent shipped work on that branch: short Retry-After 429/503 policy
  (last updated 2026-09-01), CLI-leakage audit + `__init__.py` cleanup, doc
  edits verified by soak, and the shell-developer reviewer diff-truncation fix.
  All completion notes are in git — see `git log` on `feat/roadmap` / `main`.
- **Next-up candidates** (below): §1 cold-soak SQLite ingest and §2 optional
  PostgreSQL are both **OPEN — design only, no branch yet**. They are the two
  largest open items and do not depend on live endpoints.

## 1. Cold-soak SQLite project ingest (NUC / 2-core / ≥8 GB)

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


## 2. Optional PostgreSQL via SQLAlchemy (SQLite remains default)

**Status:** OPEN — design only (2026-08-31). No branch yet. Depends on §1
(cold-soak ingest) only in the sense that **init bulk-load must stay a
first-class path** on both backends; do not block §1 on this.

**Why:** SQLite is correct for NUC soaks, hermetic tests, and wiped
`.PrizmForge/` isolation. A shared or multi-writer deploy (later federation,
long-lived operator DB, concurrent soaks against one store) needs a server
engine. The product switch is **configuration**, not a fork.

**Default stays SQLite.** Postgres is opt-in. CI and `utils/run_tests.sh`
stay on SQLite unless an explicit extra job is added.

### 2.1 Decision: SQLAlchemy Core first, not ORM-everywhere

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

### 2.2 Configuration (files, not env-only)

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

### 2.3 Single engine facade

Replace the split `sqlite3.connect` world with one module, e.g.
`core/db_engine.py`:

- `get_engine()` — process singleton, built from config.
- `session_scope()` / `connection_scope()` — context manager that yields a
  connection with `commit`/`rollback` matching `get_db_connection`.
- `get_db_path()` remains for SQLite file location and diagnostics; Postgres
  returns the sanitized URL (`password` redacted).

**SQLite engine kwargs (preserve soak locking story after §1 init window):**

- `connect_args={"timeout": 30}` (or current values).
- `poolclass=NullPool` (or `StaticPool` + `check_same_thread=False` only if
  a measured single-connection soak needs it). Default: **NullPool** so we
  do not invent a second writer pool on the file DB.
- On connect: `PRAGMA journal_mode=DELETE`, `synchronous=NORMAL`,
  `temp_store=MEMORY`, `foreign_keys=ON` — same as `core/db_connection.py`
  today. §1 init pragmas stay a **separate** connect event or
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

### 2.4 Dialect-safe SQL (inventory before rewrite)

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
| Bulk init | §1 `executemany` + MEMORY journal | `psycopg` `executemany` or `COPY` for `file_lines` only if measured |
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

### 2.5 Schema create + migrations

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

Postgres: never run `PRAGMA`. Never run §1 `journal_mode=MEMORY`. Init
performance work for Postgres is a different checklist (`COPY` / unlogged
`file_lines` during load, then `ALTER TABLE … SET LOGGED`) — park unless a
soak actually uses Postgres.

### 2.6 Product behavior that must not change

- Default `backend=sqlite`, path under `.PrizmForge/`, wiped per soak.
- Governed reconstruct (`file_lines` + `sort_order` + `is_deleted`) identical.
- Tests use tmp SQLite; no Docker required for `run_tests.sh --normal`.
- `log_error` stays non-blocking (short timeout / best-effort) on both
  backends.
- Dual-writer rule on SQLite is unchanged: one writer during materialize;
  do not open a second engine against the same file.

### 2.7 Phased delivery

- [ ] **2.A — Config + engine + SQLite parity**  
      `database` block, `get_engine()`, migrate `init_db` +
      `get_db_connection` + `file_editing.db` to the facade. Behavior on
      SQLite indistinguishable. Gate green. No Postgres CI yet.
- [ ] **2.B — Dialect helpers + lastrowid/upsert**  
      Fix the inventory in §2.4 at the highest-traffic writers
      (`file_operations`, `writer.initialize_file_lines`,
      `proposal_builder`, `db_helpers`). Unit tests run the same SQL
      helpers against a SQLite engine.
- [ ] **2.C — Postgres smoke (optional extra)**  
      `tests/integration/test_postgres_smoke.py` marked `@pytest.mark.postgres`,
      skipped without `PRIZMFORGE_DATABASE_URL`. Creates schema, indexes one
      file, reconstructs lines, writes one proposal row. Document compose
      snippet in `docs/soak_runbook.md` (do not make compose the default
      soak).
- [ ] **2.D — Alembic + MetaData**  
      Move off the schema string. One documented `alembic upgrade head` for
      durable Postgres; SQLite soaks still `create_all` on empty file.

### 2.8 Files to touch (2.A minimum)

- `core/config.py` + `docs/CONFIGURATION.md` + `example_config.json`
- `example_api_key.json` — `keys.database.password` placeholder
- `core/db_engine.py` (new), `core/db.py`, `core/db_connection.py`,
  `file_editing/db.py`
- `core/preflight.py` — Postgres reachability
- `pyproject.toml` / install extras
- `tests/unit/test_db_engine.py` — backend selection, URL redaction,
  SQLite PRAGMA on connect, reject unknown backend
- `tests/unit/test_db_retry_patience.py` — still valid on SQLite engine

### 2.9 Acceptance

- `backend` omitted or `"sqlite"` → bit-identical operator story to
  current `main` (path, pragmas after init, tests).
- `backend: "postgresql"` without password / extra / server → **fail
  closed** with an actionable message, no silent SQLite fallback.
- No password in logs, events, or `get_db_path()` print.
- Ruff clean; normal gate does not require Postgres.
- §1 init pragmas still compile and apply **only** when dialect is SQLite.

### 2.10 Out of scope

- Multi-tenant Postgres, read replicas, federation Stage 2.
- Moving agent JSON blobs into JSONB in the first Postgres PR (TEXT is
  fine; JSONB is a later migration).
- Replacing the message bus with Redis/NATS.
- SQLAlchemy 1.4 APIs (`Query`, `sessionmaker` legacy binds).

---

## 3. Unattended closed-loop hardening — open residuals only

All shipped workstreams (A–F) are recorded in `docs/UNATTENDED_CLOSED_LOOP_CAPABILITIES.md`; the tracker keeps only what is still open.

- [ ] **Live failing-hook smoke run on a copy** — run with a deliberately failing hook; confirm CRITICAL feedback → developer fix-forward proposal → materialized and addressed, all visible in events/errors/feedback. **Blocked: live runtime/endpoints** (in-process failure paths have deterministic unit proofs in `tests/unit/test_git_closed_loop.py`).
- [ ] **PR #94 body nit** (manual GitHub edit): body still cites `tests/unit/test_writer_git_closed_loop.py`; should cite `tests/unit/test_git_closed_loop.py`. **Blocked: GitHub/manual editor access** (cosmetic, merged-PR body).
- [ ] **Ignored-path handling in the git closed loop** — a git-governed target that is gitignored (e.g. `config.json`) needs an explicit
  branch: skip git or fail with a clear "path is gitignored" message, never silent
  success. **Default parked (§5 decision 3: gitignored config stays human-only).** Source: `docs/UNATTENDED_CLOSED_LOOP_CAPABILITIES.md` §3.7.
- [ ] **Diagnostic dump shows a forced-hook-failure path** — at least one non-success path visible under events/errors after an intentional hook failure; the `git_fail` counter is already present in task summaries. **Blocked: Workstream F dump sections (`docs/UNATTENDED_CLOSED_LOOP_CAPABILITIES.md` §8.2).**

---

## 4. Mini-swe agent (shell developer) — open items only

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

## 5. Annexes (strategic / parked decisions)

### 5.1 Forge Federation strategy — `Federation/Plan.md`

Active northstar: Stage 0 (current single-Territory system) → Stage 1 (enhanced
single-Territory, next) → Stage 2 (multi-Territory, future). Operates via short,
YAGNI-focused sprints with bounded, measurable experiments.

### 5.2 `report/plan.md` structural refactors (backlog / tech-debt)

Review-flagged structural items, each small, bounded, and independently scoped.
**NOTE:** The prior low-risk pair (CLI-leakage audit, `__init__.py` cleanup) is
**shipped** and pruned — its acceptance is in git. These are the still-open
mutation-path refactors and the re-scoped sleep item.

Mutation-path refactors — **parked; need a design doc before touching the governed-edit path** (higher regression risk):

- [ ] **`project_files` refactor** — normalize file metadata/index rows and their update paths.
- [ ] **Standardize errors** across file_editing — single error shape/status vocabulary instead of per-module strings.

Re-scoped (the fixed 120 s sleep is **not** in the editing loop):

- [ ] **120s-sleep behavior** — the roadmap's "editing-loop" 120 s sleeps actually live in `agents/base.py` (401/KEY_LOCKED unlock wait, proxy/auth pause) and `interactive.py` (unattended recovery). Replace with the shared `EndpointHealth.unavailable_until` latch / configurable cooldown from the shipped retry-after policy (see `core/rate_limit_headers.py`).

### 5.3 UNATTENDED plan open decisions (parked, with defaults)

1. Hook failure: fix-forward (leave disk dirty; CRITICAL fix) unless `git.revert_on_hook_failure` set — current behavior is fix-forward.
2. Create-file policy: clean relative paths OK; add prefix policy only if junk root files recur.
3. `config.json` as agent edit target: gitignored config stays human-only.
4. Reviewer sees hook output: developer primary; orchestrator summary; reviewer optional.
5. API/network failure streaks: pause + single CRITICAL summary after N consecutive failures (shipped — `NetworkBusyLoopGuard`).

---

## 6. New work this pass (from soak-review)

Placeholder for actionable items that surface from the Soak7 review and
future soak analyses. When a soak reveals a concrete, verified defect or
regression, add a dated, file-referenced entry here and tick it once fixed.
Do not add speculative or endpoint-dependent items.

Soak7 (2026-09-02) so far produced 54 `jr_reviewer` feedback items but **0
materialized edits** (task_001 shell session hit its `step_limit=30` mid-review;
remaining errors were API/Network + quota noise). Triage: most items are
false-positive or working-as-designed (see below). Two are genuinely actionable:

- [ ] **Quote SQL identifiers in `cli/commands.py` DB exports** — `cmd_export_db`,
      `cmd_export_specific_tables`, `table_has_task_id` interpolate raw
      `{table_name}` into SQL/`PRAGMA` (`cli/commands.py:356,359,399,490,493`).
      Add a `_quote_identifier()` helper (double-quote + escape embedded `"`).
      (But : `sqlite_master name=?` check already parameterized.)
- [ ] **Robust DDL splitting in `core/db.py` `_apply_schema`** — current
      `endswith(";")` per-line split breaks if a `;` appears inside a comment
      or string literal. Replace with a comment/string-aware scanner; no new
      dependency (`sqlparse` not required).

**Deliberate / false-positive — no change:**
- `core/db.py` `journal_mode=OFF` + `synchronous=OFF` + FK-disabled-during-apply:
  intentional init-window & mount tradeoffs — already covered by §1 and §2 here.
- `core/db_helpers.py` "SQL injection" (ids 39–43): parameterized — f-strings only
  assemble `?` placeholders or a constant `task_filter`; not injectable.
- `agent_schemas/*.json` items (ids 17–38): sample-output → formal-JSON-Schema
  would regress `get_schema_example()` (`core/agent_schemas.py:312`); excluded.
- `cli/__init__.py` empty / `datetime.now()`×3 / cosmetic nits: harmless.

---
