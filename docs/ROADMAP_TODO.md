# PrizmForge Roadmap / TODO

This file lists **only work that still needs to be accomplished**.

Completed work is **not repeated here**. Implementation, PR numbers, soak
post-mortems, and acceptance evidence live in **git history**
(`git log`, merged PRs #108–#116, and
`docs/UNATTENDED_CLOSED_LOOP_CAPABILITIES.md`). Do not paste shipped
checklists back into this tracker.

**Last updated:** 2026-09-05

## How to use this file

- Tick a box when the change lands on `main`; then delete that item on
  the next pass (do not leave `[x]` museums).
- Detailed *design* for an open item stays in this file until it ships.
- Do not merge `soak/doc-run-a-1` (trajectories + docs only).

## Section priorities

| Section | Priority | Why |
|---|---|---|
| §0 Current state | — | Index |
| **§8 Soak A-1** | **P0** | `RecursionError` can kill unattended; Gemini finishes with zero bash. |
| §6 Latch residuals | **P0** | §6.1 recurse-without-`seen` and §6.3 `is_available` re-entry are the A-1 crash path. |
| §2 Shell evidence / protocol holes | **P0** | Same as §8.2; kept here so Phase 2 design is not only in A-1 notes. |
| §1 Cold-soak SQLite ingest | **P1** | After the loop can stay up. |
| §3 Feedback / dispatch holes | **P1** | A-1 re-dispatched a seed that never ran a command. |
| §4 Task lifecycle | **P2** | Stalled/`in_progress` hygiene. |
| §5 Model-health / nits | **P2** | Demotion false positives; optional SQL. |
| §7 Closed-loop / mini-swe residuals | **MEDIUM** | Blocked on live hooks / endpoints / enclave. |
| §9 Annexes | **LOW** | WAL-as-default, Postgres, federation. |

---

## 0. Current state & next focus

- **`main` already has** soak-diag, `FINISH_EDIT_SESSION` + fence recovery,
  shell events/trajectories, skip-path fallback, dump-once, support freeze,
  `FreeUsageLimitError` quota class, praise filter (phrase + no error token),
  prioritizer `seed_task` first, `_recent_failure_kind` with a real connection,
  diagnose UTF-8. Do not re-implement those.
- **Next commit:** §8.1 (`seen` + latch re-entry) → §8.1a (per-endpoint
  token budget) → §8.2 / §2 (fail-closed evidence command).
- **A-1 (2026-09-05, Windows `Soak1-target`):** 11 tasks stalled, 0
  proposals, 0 writes, ~450k tokens, then `RecursionError` in
  `call_endpoint` ↔ `get_fallback_model` ↔ `is_available`.
  Company endpoints need a **manual unlock ~every 8 hours** and **must
  keep falling back** when one key locks.
- **Trajectories (do not merge):** `soak/doc-run-a-1` /
  `docs/soak-a-1-shell-trajectories/` — 12 sessions, all `Finished`,
  `api_calls=1`, `gemini/gemini-3.1-pro-preview`, **no bash block**.

---

## 8. Soak A-1 — recursive fallback, per-endpoint budget, finish-without-evidence

**Priority:** P0
**Evidence:** `soak/doc-run-a-1` / `docs/soak-a-1-shell-trajectories/`
**Live tree:** `PrizmForge-Soak/Soak1-target/` (Windows)

Two layers. Do not conflate them.

| Signal on endpoint A | Whose resource | Fallback to B? |
|---|---|---|
| Company key locked / 401 / unlock URL | A's key | **Yes.** B has a different key. |
| Provider 429 / quota | That provider | Yes if B is a different provider. |
| A's **endpoint token budget** exhausted | A's 4h bucket | **Yes.** B has its own bucket. Today this is a **process-wide singleton** — that is the bug. |
| Every endpoint bucket exhausted, or B already in `seen` | — | **No.** Stop the call. |

A-1 sequence:

1. Company endpoint 401 → latch + fallback (**correct**).
2. Shared singleton `TokenBudget` prints `0M / 0M` after ~450k tokens.
3. Budget miss still calls `get_fallback_model` → `call_endpoint`
   (`agents/base.py` ~188) with no visited set.
4. `gemini` ↔ `beta_beta_company_gemini` until `RecursionError`.
   `Failed to log fallback: maximum recursion depth exceeded` is the
   same stack.
5. Same storm re-enters
   `is_available()` → `_sync_support_freeze()` → `_all_endpoints_latched()`
   → `is_available()`.

`0M / 0M` may also mean soak-target `token_budget.max_tokens_per_4h` is
0. Check the **target** config. Either way, budget-fail must not recurse.

### 8.1 Stop recursive fallback (first commit)

Primary files: `agents/base.py`, `core/endpoint_manager.py`,
`core/fallback_stats.py`, `tests/unit/`.

- [ ] **`seen_endpoints` (or depth cap) on every `call_endpoint` recurse** —
      401, 429, latch-skip (§6.1), and budget miss. If the fallback name
      is already in `seen`, do not recurse. If nothing remains: bounded
      sleep + `record_model_outcome(..., kind="no_alternate_endpoint")`,
      return `None, 0`.
- [ ] **`EndpointHealth.is_available()` must not call
      `_sync_support_freeze()`.** Sync only from `mark_success` /
      `mark_failure` (optional periodic tick if expiry-without-mark must
      still unfreeze support).
- [ ] **`_all_endpoints_latched()` must not call `is_available()`.**
      Read `unavailable_until is None or now >= unavailable_until` only.
- [ ] **`log_fallback` fail-soft.** Telemetry must not take the process
      down if the stack is already deep.
- [ ] **Tests:**
      1. A key-locked, B healthy → one fallback, B invoked.
      2. Both locked → no infinite loop.
      3. A↔B budget/latch ping-pong cannot exceed depth.
      4. `_all_endpoints_latched` / `is_available` do not recurse even
         with the freeze flag forced off.

Company 8-hour unlock is unchanged: when `unavailable_until` expires or
the operator unlocks and the next success `mark_success`s, A is eligible
again.

### 8.1a Token budget is per endpoint

Today `get_token_budget()` is a process singleton
(`agents/base.py` + `core/token_budget.py`, one `max_tokens_per_4h`).
Company Gemini and public Gemini do **not** share a provider cap.

- [ ] **Key `TokenBudget` by `endpoint.name`.** Config:
      `endpoints.<name>.token_budget.max_tokens_per_4h`, falling back to
      top-level `token_budget.max_tokens_per_4h` only as the default for
      endpoints that omit it. Persist windows keyed `endpoint_name`.
- [ ] **Print** `Token budget exceeded: used / cap (endpoint=<name>)`.
      Never print a bare `0M / 0M`.
- [ ] **`can_spend(tokens, endpoint=...)`.** A exhausted still fallbacks
      to B if B's window has room and B ∉ `seen`.
- [ ] **Do not use KEY_LOCKED cooldown for a budget miss.** Optional
      `TOKEN_EXHAUSTED` latch on **A only** (existing ~15m) until the 4h
      window slides. B stays healthy.
- [ ] **Shell `_llm`:** `token_budget` is **endpoint-local**, not a
      session-permanent kind. Give up the session only when every
      reachable endpoint is budget-dead or latched.
      (Soak10 treated `token_budget` as immediately permanent — that was
      correct for the singleton, wrong after this change.)
- [ ] **Tests:** two endpoints, different caps; burn A only → next call
      spends B; burn both → one `token_budget` outcome, no recursive
      `call_endpoint`; `get_token_budget()` cannot ignore `endpoint.name`.

### 8.2 Finish-without-evidence

Not a materialize bug. Funnel: 0 proposals, 0 `file_write_log`, 12×
`shell_session_no_mutation`.

Every file in `docs/soak-a-1-shell-trajectories/`:

- `task_001-turn1-20260905T155651Z.json` — first reply
  `FINISH_EDIT_SESSION`, claims `workflow/__init__.py` and `workflow/`
  do not exist. **No bash.**
- `task_001-turn13-20260905T160122Z.json` — same for
  `workflow/task_runner.py`, “repository appears to be empty.”
- `task_002-turn1-20260905T160736Z.json` — finish + “I do not have
  access to your local file system” + ask the user to upload files.

Transport was fine (`successful_calls=1`, `last_llm_failure=null`).
Gemini treated the session as chat. The shipped “if the target file is
missing after inspect, do not invent a path — FINISH” rule then fired
on a **hallucinated** empty repo. The evidence command
(`pwd && git rev-parse --show-toplevel && ls -la`) is still prompt-only.

Design and checkboxes: **§2** (same work; do not implement twice).

### 8.3 Out of scope

- Do not disable company↔public Gemini fallback on **401 / key lock**.
- Do not treat two company keys as one provider quota.
- Do not copy `.PrizmForge` across soaks.
- Do not merge `soak/doc-run-a-1`.
- Do not enable WAL on the live soak writer for this item (§9).
- Do not pull optional PostgreSQL / SQLAlchemy forward.

### 8.4 Acceptance (same Windows box, same 8-hour unlock cadence)

1. Lock one company endpoint on purpose → fallback to the other **once**;
   process stays up; `seen` prevents A→B→A.
2. Exhaust **endpoint A’s** bucket → B is used and B’s counter moves.
   Exhaust **both** → stop, no `RecursionError`, no fallback ping-pong.
3. Shell first turn is a closed bash evidence command (or a forced retry),
   never an immediate `FINISH_EDIT_SESSION`.
4. Target-DB `--diagnostic` shows a proposal/write **or**
   `shell_workspace_validation_failed` with evidence stdout — not twelve
   `shell_session_no_mutation` chat refusals.

---

## 6. Latch / fallback residuals

Skip-path fallback, dump-once, support freeze, and
`FreeUsageLimitError` → quota **already shipped**. What is still open:

- [ ] **§6.1 recurse has no `seen` set** — latched / budget / 401 all
      use `return call_endpoint(...)`. Close under §8.1; then delete
      this row.
- [ ] **§6.3 `is_available()` re-probes `_sync_support_freeze` on every
      check** — freeze *policy* stays; the call graph must change under
      §8.1. Then delete this row.
- [ ] **Next-soak acceptance (still unpaid):** one 429 parks an
      endpoint; stdout shows **one** dump; other agents skip in one
      line; orchestrator/developer reach a healthy fallback; `Work:` is
      not 0.0s only because support held the latch.

Non-goals (still): do not spoof OpenCode CLI headers; do not treat
`free-models-per-day` as a product bug; do not reopen short Retry-After
for non-quota 429/503.

---

## 2. Shell developer — evidence fail-closed and remaining protocol holes

**Priority:** P0 (implements §8.2)
**Primary files:** `workflow/shell_developer.py`, `workflow/shell_protocol.py`,
`tests/unit/test_shell_developer_protocol_recovery.py`

Shipped and **not** repeated: `FINISH_EDIT_SESSION` only, conservative
unterminated-fence repair, structured protocol reasons, “do not mkdir a
missing task path after a real inspect.”

**Success criterion:** the first accepted assistant turn is a closed
bash evidence command that runs in the worktree and sees
`workflow/__init__.py`, *or* the session aborts with
`shell_workspace_validation_failed`. A model may not `FINISH` first.

### 2.1 Mandatory initial-workspace evidence (fail-closed)

Before the developer may edit **or finish**, require successful
execution of:

```bash
pwd && git rev-parse --show-toplevel && ls -la && test -f workflow/__init__.py
```

(The prompt may still show the shorter
`pwd && git rev-parse --show-toplevel && ls -la`; the loop must add
`test -f workflow/__init__.py` or equivalent marker.)

Persist:

- process working directory
- git worktree root
- command exit code
- stdout/stderr excerpts
- whether the requested task path exists

- [ ] **Reject `FINISH_EDIT_SESSION` until evidence has run and
      succeeded.** Inject a user turn: you have a real shell in a
      disposable worktree; emit the evidence command; do not ask anyone
      to upload files; command stdout **is** the repository.
- [ ] **If evidence stdout does not show `workflow/__init__.py` (or the
      configured marker):** emit
      `shell developer workspace validation failed: expected
      workflow/__init__.py under project root but it was not found`,
      publish `shell_workspace_validation_failed`, abort. Do not spend
      three format retries. Do not let the model declare “empty repo.”
- [ ] **A-1 fixture:** first assistant message is finish-without-bash
      claiming missing `workflow/__init__.py`. Session must not complete.
- [ ] **Windows worktree sanity (after evidence is forced):**
      `pf-shelldev-*` evidence stdout must list `workflow/`. If `ls` is
      truly empty, that is soak-setup / `project_directory` /
      `git worktree add` — file a separate item; do not blame Gemini.

### 2.2 Tests still missing

- [ ] Correct worktree exposes `workflow/__init__.py`.
- [ ] Empty temporary directory fails workspace validation.
- [ ] Worktree path is not inherited from a parent repository.
- [ ] Windows/Git Bash path handling still invokes commands in the
      correct directory.
- [ ] A valid bash response actually executes and produces captured
      output.
- [ ] Finish-before-evidence (A-1 turn 1) is rejected.

### 2.3 Remaining protocol nits (only if the next soak shows them)

- [ ] `<finish>` alias — watch A-1 follow-up; accept as alias for one
      release only if it recurs.
- [ ] `is_valid_bash_block` requires `` ```bash\n ``; strip `\r` in
      `normalize_shell_reply` if a soak emits `` ```bash\r\n ``.
- [ ] `classify_shell_reply` labels any text containing `` ```bash ``
      that is not a closed block `UNTERMINATED_BASH_BLOCK` (error text
      that *quotes* the format). Conservative; leave unless it poisons
      diagnostics.

Prompt block to keep (already on `main`; re-assert in the fail-closed
inject, do not regress):

```text
Do not ask the user to upload files or provide repository contents.
You have shell access to the project checkout.
Command stdout is the repository.
```

---

## 3. Feedback / developer dispatch holes

Shipped: praise filter (phrase AND no error token), prioritizer
`ORDER BY CASE WHEN category = 'seed_task' THEN 0 ELSE 1 END, timestamp DESC`,
caps (5 files / 3 items / 10 unaddressed / 10 to prioritizer).

Still open:

- [ ] **Do not re-dispatch the developer on the same seed** when the
      prior shell session finished before any command executed (A-1
      turns 1–13). Phase 4.4 of the old plan; not enforced.
- [ ] **Seed-path regex** `[\w./-]+\.\w+`
      (`agents/parallel_workers.py` `_resolve_seed_target_path`) can
      bind `config.json`. Longest-wins + `project_files` lookup bounds
      it; tighten if a soak edits gitignored config.
- [ ] Scope creep watch: a seed that names `workflow/__init__.py`
      must not enqueue `workflow/task_runner.py` /
      `proposal_builder.py` / `utils/pre_commit.sh` unless the task is
      repository-wide. Re-measure on the next soak with background
      agents on; if fan-out returns, the cap is not binding.

---

## 1. Cold-soak SQLite project ingest (NUC / 2-core / ≥8 GB)

**Status:** OPEN — after §8. No branch required to start.

**Constraint (intentional):** soaks do **not** copy `.PrizmForge/`.
Every soak start is a **cold full rebuild** of `.PrizmForge/agents.db`.
Do not plan cross-soak hash-skip, leftover `project_files.content_hash`,
or “second run is cheaper.” The only clock that matters is **one**
`cmd_init()` on a wiped DB.

**Symptom:** on a 2-core NUC, soak start spends a long time in
`🔄 Auto-indexing project files...` before iteration 1. Root is not
“SQLite is slow”; it is how init talks to SQLite.

**Hot path today**

- `main.py` → `init_db()` → `cmd_init()` (`cli/commands.py`) when
  `auto_init_on_start` is true (unattended default).
- `os.walk(project_directory)` then, **per text file**:
  1. `sync_file_to_database` — new connection, `INSERT OR REPLACE`
     full blob into `project_files`, `estimate_tokens`, **commit**.
  2. `generate_file_summary` + `save_file_summary` — **another**
     connection + commit.
  3. `initialize_file_lines` (`file_editing/writer.py`) — **another**
     connection, `DELETE FROM file_lines`, then **one `INSERT` per
     line** in a Python `for` loop (`uuid4` + md5 per line), **commit**.
- Then a fourth connection for the deleted-file pass.
- Then `refresh_target_indexes(..., force=True)`.

`initialize_file_lines` uses `file_editing.db.get_db_connection()`,
which does **not** apply `core.db_connection` pragmas. Those commits
often run at SQLite default `synchronous=FULL` (fsync per file).
Runtime connections already use `journal_mode=DELETE` +
`synchronous=NORMAL` (lock-safe for soak; terrible for bulk load).
~40k Python source lines ⇒ tens of thousands of single-row inserts
and three transactions per file.

**Non-goals**

- Do not persist `.PrizmForge/` between soaks to make init faster.
- Do not thread-pool ingest (one SQLite writer; two cores).
- Do not leave `synchronous=OFF` / `locking_mode=EXCLUSIVE` on after
  init.
- Do not switch the live soak DB to WAL for this item unless measured
  on the NUC; locking work assumed DELETE.
- Do not treat “daemon owns the DB” as the fix for *this* window.
  Init should be one exclusive bulk transaction, then hand the DB back.

### 1.1 Init connection + one transaction

- [ ] **`cmd_init` holds one writer** — open a single
      `core.db_connection.get_db_connection()` (or a dedicated
      `get_init_db_connection()`) for the whole walk. Pass `conn` into
      `sync_file_to_database`, `save_file_summary`, and
      `initialize_file_lines` (the last already accepts `conn=`).
      Commit **once** after all files + the deleted-file pass.
- [ ] **Never open `file_editing.db.get_db_connection()` during init** —
      that helper skips bulk pragmas and defaults to FULL sync. Route
      init through `core.db_connection`.
- [ ] **Deleted-file pass uses the same `conn`** — no extra context
      manager.

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

- `MEMORY` journal: box-crash mid-init already throws the DB away; an
  exception mid-walk can still roll back a half-built index. Prefer
  this over `journal_mode=OFF` first.
- `cache_size` 512 MiB + `mmap` 256 MiB is the intended 8 GB split.
  Do not grab multiple GB; agents + Python need the rest.
- Comment that these pragmas are **init-window only**.

### 1.3 `file_lines` bulk insert

- [ ] **`_initialize_lines_impl`: `executemany`** — build the row
      tuples in Python, one `executemany` per file (or chunks of
      5k–10k rows). Columns:
      `(line_guid, file_id, sort_order, content, content_hash, version, is_deleted)`.
      Keep `uuid4` + line md5.
- [ ] **Optional:** if secondary indexes on `file_lines` exist besides
      UNIQUE `line_guid`, create them **after** the bulk load
      (`ANALYZE` once). Do not drop UNIQUE `line_guid`.

### 1.4 Same-process only (not cross-soak)

- [ ] Hash short-circuit is **in-process only** (second `cmd_init()`
      in the same soak, or a mid-soak restart that did *not* wipe the
      live DB). Default soak still pays full rebuild. Do not advertise
      “next soak is faster.”

### 1.5 Work that is not required for iteration 1

- [ ] Throttle per-file `✅ {path}` prints (every 50 files + a final
      tally).
- [ ] `refresh_target_indexes(..., force=True)` runs **after** the DB
      commit (`force=False` only when an in-process index already
      exists — never assume a previous soak left one).
- [ ] `project_files.content` + `file_summaries` stay in the same
      transaction. Do not drop `file_lines`. Folding `project_files`
      into a later metadata-only table is tech-debt, not this item.

### 1.6 Files to touch

- `cli/commands.py` — `cmd_init` transaction + pragma window + print
  throttle.
- `file_editing/writer.py` — `_initialize_lines_impl` `executemany`.
- `core/file_operations.py` — optional `conn=` on
  `sync_file_to_database` / `save_file_summary`.
- `core/db_connection.py` — optional `get_init_db_connection()` so soak
  connections never inherit init pragmas.
- `tests/unit/` — no live endpoints:
  - init of N small files uses **one** commit path (spy `commit` /
    count connections);
  - `initialize_file_lines` writes expected line count + reconstructs
    content;
  - after init returns, `PRAGMA journal_mode` is `delete` and
    `synchronous` is not `OFF`;
  - `file_editing.db.get_db_connection` is not used on the init path.

### 1.7 Acceptance

- Cold soak (no `.PrizmForge/` copied) still produces a complete
  `files` + `file_lines` + `project_files` index; governed reconstruct
  matches disk.
- Wall-clock of `cmd_init` on the NUC drops from “noticeable stall” to
  a short burst; log walk+read, DB writes, deleted-file pass, symbol
  index.
- First orchestrator call still sees DELETE + NORMAL; no new
  `database is locked` storms vs current soak baseline.
- Existing file-line / proposal / git-closed-loop tests stay green;
  ruff clean on touched files.

**Verify on the NUC, not only CI.** Time a wiped `cmd_init()` before
and after on the same tree.

---

## 4. Task lifecycle

**Primary files:** `workflow/task_runner.py`, shutdown handling.

A-1 finalized tasks as `stalled` with
`error: maximum recursion depth exceeded` and left the unattended
summary at `Iterations: 0` / `Files modified: 0`. That is better than
`in_progress` forever, but the vocabulary and interrupt path are still
incomplete.

- [ ] Every task ends as one of:
      `completed` | `failed` | `deferred` | `cancelled` | `timed_out` |
      `no_change_required` | `stalled` (only after an unrecoverable
      runner exception). Do not leave `in_progress` after Ctrl+C,
      duration cap, or `RecursionError`.
- [ ] On `KeyboardInterrupt`, duration cap, shell protocol failure,
      workspace validation failure, or unrecoverable startup failure:

      ```python
      mark_task_status(
          task_id,
          "failed",
          reason="...",
      )
      ```

- [ ] Valid session, evidence ran, no justified change:

      ```python
      mark_task_status(
          task_id,
          "no_change_required",
          reason="review completed; no safe change justified",
      )
      ```

      A-1's twelve `Finished` + no-mutation sessions must **not** look
      like `completed` wins.
- [ ] Do not hand-edit historical Soak3 SQLite. Use the task-state
      helper or an admin command.

---

## 5. Model health and optional hygiene

- [ ] **`record_model_outcome(ok=False)` on latch-skip / budget / key
      lock must not demote model quality.** `core/model_health.py`
      `compute_stats` counts every `ok=False` in streak / failure_ratio.
      Exclude `no_alternate_endpoint`, `token_budget`, `key_locked`
      (operator/quota). Keep real 5xx / timeout / parse failures.
      Confirmed 2026-09-05; do before the next paid soak.
- [ ] Surface per-call advertised `Retry-After` on `rate_limited`
      events (Soak10 residual).
- [ ] OPTIONAL — quote SQL identifiers in `cli/commands.py` DB exports
      (`cmd_export_db`, `cmd_export_specific_tables`,
      `table_has_task_id`). `_quote_identifier()` = double-quote +
      escape embedded `"`. (`sqlite_master name=?` is already
      parameterized.)
- [ ] OPTIONAL — comment/string-aware DDL split in `core/db.py`
      `_apply_schema` (current `endswith(";")` per-line split breaks on
      `;` inside a comment or string). No `sqlparse`.

---

## 7. Closed-loop and mini-swe residuals

Blocked on live runtime / endpoints / machines. Do not start these
ahead of §8.

### 7.1 Git closed loop

Source: `docs/UNATTENDED_CLOSED_LOOP_CAPABILITIES.md`.

- [ ] Live failing-hook smoke on a copy: CRITICAL feedback → developer
      fix-forward proposal → materialized and addressed, visible in
      events/errors/feedback. In-process proofs already exist in
      `tests/unit/test_git_closed_loop.py`.
- [ ] Ignored-path in the git closed loop (e.g. gitignored
      `config.json`): skip git or fail with `path is gitignored`, never
      silent success. **Default parked (§9.3 decision 3).**
- [ ] Diagnostic dump shows a forced-hook-failure path (Workstream F
      dump sections). `git_fail` counter already exists in task
      summaries.

### 7.2 Mini-swe / shell port

Port itself is shipped (`docs/mini_swe_agent.md`). Open:

- [ ] Real-model end-to-end validation + prompt/limit tuning.
- [ ] Manual cold-start smoke: seed consumed on turn 1, no
      `Unknown model` lines.
- [ ] Enclave sandboxing (container / approved-workstation). Shell
      runs are not confined to the worktree today.
- [ ] Post-materialize `test_command` re-run — **deferred** (session
      `test_command` + ruff pre-check already gate). Revisit only if a
      deploy-time validator becomes a requirement.
- [ ] EndpointManager / LiteLLM overlap — parked; no routing layer
      planned.

---

## 9. Annexes (parked — do not start)

### 9.1 Federation

`Federation/Plan.md` — Stage 0 → Stage 1 → Stage 2. YAGNI sprints.

### 9.2 Structural tech-debt

- [ ] `project_files` metadata normalize — needs a design doc before
      touching the governed-edit path.
- [ ] Standardize file_editing error shape / status vocabulary.
- [ ] 120s unlock sleep in `agents/base.py` (401/KEY_LOCKED) and
      `interactive.py` (unattended recovery) → shared
      `unavailable_until` latch. Related to the 8-hour company unlock;
      do not block §8.1.

### 9.3 Defaults (do not reopen without evidence)

1. Hook failure: fix-forward unless `git.revert_on_hook_failure`.
2. Create-file: clean relative paths OK.
3. `config.json` stays human-only (gitignored).
4. Reviewer sees hook output optionally; developer is primary.
5. Network streaks: `NetworkBusyLoopGuard` (shipped).

### 9.4 Not this pass

- PostgreSQL / SQLAlchemy dual backend.
- Live-soak **WAL + single-writer queue** as the default runtime
  (old FIRST PASS Phase 5). Live soak stays DELETE + NORMAL after
  init (§1). Revisit WAL only if that is not enough on the NUC.
- Copy-forward of `.PrizmForge/` between soaks.

### 9.5 False positives — no change

- Init-window `synchronous=OFF` / MEMORY journal is intentional;
  restore before iteration 1 (§1).
- `core/db_helpers.py` feedback SQL is parameterized.
- `agent_schemas/*.json` stay example-shaped for
  `get_schema_example()`.
- `cli/__init__.py` empty / `datetime.now()` cosmetics.

---

## Implementation sequence (open work only)

| Order | Work item | Exit criterion |
|---:|---|---|
| 1 | §8.1 `seen` + latch re-entry | No A↔B `RecursionError`; tests 1–4 green |
| 2 | §8.1a per-endpoint `TokenBudget` | Burn A uses B; burn both stops clean |
| 3 | §2 / §8.2 fail-closed evidence | A-1 fixture rejected; first turn is bash |
| 4 | §3 no re-dispatch without a command | Seed does not loop 13 empty finishes |
| 5 | §5 demotion exclusions | Latch/budget/key_lock do not demote |
| 6 | §4 task status vocabulary | No leftover `in_progress` |
| 7 | §1 cold ingest | Timed wiped `cmd_init` on the NUC |
| 8 | §7 live-hook / mini-swe e2e | When endpoints and a hook-fail copy exist |

---

## Validation after §8 (replace the old Phases 1–4 smoke)

Two endpoints configured. Background agents off for the first pass.

```json
{
  "background_agents_enabled": false,
  "reporter": { "enabled": false, "interval_minutes": 10 },
  "resource_controller": { "enabled": false },
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

**Pass criteria**

1. Evidence command runs; `workflow/__init__.py` is in stdout.
2. Lock endpoint A → one fallback to B; no `RecursionError`.
3. Burn A's token window → B used; burn both → clean stop.
4. Task status is `completed`, `no_change_required`, or `failed` with a
   reason — never stuck `in_progress`.
5. `--diagnostic` on the **target** DB matches the trajectory files.
6. No twelve `shell_session_no_mutation` chat refusals.
