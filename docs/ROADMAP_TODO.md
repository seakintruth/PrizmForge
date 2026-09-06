# PrizmForge Roadmap / TODO

This file lists **only work that still needs to be accomplished**.

Completed work is **not repeated here**. Implementation, PR numbers, soak
post-mortems, and acceptance evidence live in **git history**
(`git log`, merged PRs #108–#121, and
`docs/UNATTENDED_CLOSED_LOOP_CAPABILITIES.md`). Do not paste shipped
checklists back into this tracker.

**Last updated:** 2026-09-06

## How to use this file

- Tick a box when the change lands on `main`; then delete that item on
  the next pass (do not leave `[x]` museums).
- Detailed *design* for an open item stays in this file until it ships.
- Do not merge `soak/doc-run-a-1` (trajectories + docs only).

## Section priorities

| Section | Priority | Why |
|---|---|---|
| §0 Current state | — | Index |
| **§8 Operator soak A-1** | **P0** | Unpaid Windows 15-minute two-endpoint acceptance |
| §6 Next-soak 429 dump | **P0** | Unpaid soak check |
| §5 Optional SQL hygiene | **P2** | Identifier quoting + comment-aware DDL split |
| §3 Seed-path / scope | **watch** | Next soak with background agents on |
| §2.3 Protocol nits | **watch** | Only if the next soak shows them |
| §1 NUC `cmd_init` timing | **P1 operator** | Code shipped in #121; still time on the box |
| §7 Closed-loop / mini-swe | **MEDIUM** | Unblocked by #121; needs live hooks / endpoints |
| §9 Annexes | **LOW** | WAL-as-default, Postgres, federation |

---

## 0. Current state & next focus

- **`main` already has (PR #121):** `seen_endpoints` recurse, latch-only
  `is_available()`, per-endpoint 4h + daily `TokenBudget`, fail-closed
  workspace evidence, zero-command seed latch, task status vocabulary
  (`failed` / `timed_out` / `no_change_required` / `stalled`), demotion
  exclusions (`key_locked`, `unauthorized`, `token_budget`,
  `token_exhausted`, `no_alternate_endpoint`), `Retry-After` on
  `rate_limited` events, cold `cmd_init` one-writer ingest. Do not
  re-implement those.
- **Next:** operator 15-minute two-endpoint soak on the Windows box
  (same 8-hour unlock cadence). In code, remaining unblocked hygiene
  is §5 optional SQL.
- **Company endpoints** still need a **manual unlock ~every 8 hours**
  and **must keep falling back** when one key locks.
- **Trajectories (do not merge):** `soak/doc-run-a-1` /
  `docs/soak-a-1-shell-trajectories/`.

---

## 8. Operator soak A-1 — unpaid acceptance

**Priority:** P0
**Live tree:** `PrizmForge-Soak/Soak1-target/` (Windows)

Code for recursive fallback, per-endpoint budget, and fail-closed
evidence **shipped in #121**. This section is the live check only.

### 8.1 Soak-watches (do not implement unless the soak shows them)

- [ ] Finish-before-evidence injects and continues up to `step_limit`.
      Correct vs an immediate `FINISH_EDIT_SESSION`, but a chatty model
      can still burn a full session of LLM calls. If that reappears,
      cap rejected FINISH turns and fail closed.
- [ ] Evidence uses POSIX `test -f` via `shell=True`. Confirm Git Bash
      / PATH so `pf-shelldev-*` evidence stdout lists `workflow/`. If
      `ls` is truly empty, that is soak-setup / `project_directory` /
      `git worktree add` — file a separate item; do not blame Gemini.

### 8.2 Out of scope (unchanged)

- Do not disable company↔public Gemini fallback on **401 / key lock**.
- Do not treat two company keys as one provider quota.
- Do not copy `.PrizmForge` across soaks.
- Do not merge `soak/doc-run-a-1`.
- Do not enable WAL on the live soak writer unless NUC DELETE+NORMAL
  is not enough (§9).
- Do not pull optional PostgreSQL / SQLAlchemy forward.
- Resource controller `max_tokens_per_day` stays process-wide. Do not
  treat it as an endpoint bucket.

### 8.3 Acceptance (same Windows box, same 8-hour unlock cadence)

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

Copy `endpoints.<name>.token_budget` 4h/daily keys from
`example_config.json` into the live soak `config.json` (gitignored).

---

## 6. Latch / fallback — next-soak acceptance

Skip-path fallback, dump-once, support freeze, `seen` recurse, and
`is_available()` latch-only **already shipped**.

- [ ] **Next-soak acceptance (still unpaid):** one 429 parks an
      endpoint; stdout shows **one** dump; other agents skip in one
      line; orchestrator/developer reach a healthy fallback; `Work:` is
      not 0.0s only because support held the latch.

Non-goals (still): do not spoof OpenCode CLI headers; do not treat
`free-models-per-day` as a product bug; do not reopen short Retry-After
for non-quota 429/503.

---

## 2. Shell developer — remaining protocol holes

Shipped in #121 and **not** repeated: fail-closed evidence,
`FINISH_EDIT_SESSION` rejected until `test -f workflow/__init__.py`,
A-1 finish-without-bash fixture, worktree-not-parent tests.

Prompt block to keep (already on `main`; do not regress):

```text
Do not ask the user to upload files or provide repository contents.
You have shell access to the project checkout.
Command stdout is the repository.
```

### 2.3 Remaining protocol nits (only if the next soak shows them)

- [ ] `<finish>` alias — watch A-1 follow-up; accept as alias for one
      release only if it recurs.
- [ ] `is_valid_bash_block` requires `` ```bash\n ``; strip `\r` in
      `normalize_shell_reply` if a soak emits `` ```bash\r\n ``.
- [ ] `classify_shell_reply` labels any text containing `` ```bash ``
      that is not a closed block `UNTERMINATED_BASH_BLOCK` (error text
      that *quotes* the format). Conservative; leave unless it poisons
      diagnostics.

---

## 3. Feedback / developer dispatch — soak watches

Shipped: praise filter, prioritizer `seed_task` first, caps, **no
re-dispatch** when the prior shell session ran no command (#121).

Still open:

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

## 1. Cold-soak SQLite ingest — NUC timing (operator)

**Code shipped in #121.** One `get_init_db_connection()` writer, MEMORY
journal + `synchronous=OFF` for the walk, restore DELETE + NORMAL,
`executemany` for `file_lines`, in-process hash skip only.

Still unpaid:

- [ ] Time a wiped `cmd_init()` on the NUC (2-core / ≥8 GB) before vs
      after on the same tree. Wall-clock should drop from “noticeable
      stall” to a short burst; first orchestrator call still sees
      DELETE + NORMAL; no new `database is locked` storms vs current
      soak baseline.

Do not persist `.PrizmForge/` between soaks. Do not switch live soak
to WAL unless this timing is still not enough.

---

## 5. Optional SQL hygiene

Demotion exclusions and `Retry-After` **shipped in #121**. Remaining:

- [ ] Quote SQL identifiers in `cli/commands.py` DB exports
      (`cmd_export_db`, `cmd_export_specific_tables`,
      `table_has_task_id`). `_quote_identifier()` = double-quote +
      escape embedded `"`. (`sqlite_master name=?` is already
      parameterized.)
- [ ] Comment/string-aware DDL split in `core/db.py`
      `_apply_schema` (current `endswith(";")` per-line split breaks on
      `;` inside a comment or string). No `sqlparse`.

---

## 7. Closed-loop and mini-swe residuals

§8 code is on `main`. These still need live runtime / endpoints /
machines.

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
      `unavailable_until` latch. Related to the 8-hour company unlock.

### 9.3 Defaults (do not reopen without evidence)

1. Hook failure: fix-forward unless `git.revert_on_hook_failure`.
2. Create-file: clean relative paths OK.
3. `config.json` stays human-only (gitignored).
4. Reviewer sees hook output optionally; developer is primary.
5. Network streaks: `NetworkBusyLoopGuard` (shipped).

### 9.4 Not this pass

- PostgreSQL / SQLAlchemy dual backend.
- Live-soak **WAL + single-writer queue** as the default runtime.
  Live soak stays DELETE + NORMAL after init. Revisit WAL only if
  NUC timing is not enough.
- Copy-forward of `.PrizmForge/` between soaks.

### 9.5 False positives — no change

- Init-window `synchronous=OFF` / MEMORY journal is intentional;
  restore before iteration 1 (#121).
- `core/db_helpers.py` feedback SQL is parameterized.
- `agent_schemas/*.json` stay example-shaped for
  `get_schema_example()`.
- `cli/__init__.py` empty / `datetime.now()` cosmetics.

---

## Implementation sequence (open work only)

| Order | Work item | Exit criterion |
|---:|---|---|
| 1 | §8.3 Windows 15-minute two-endpoint soak | Pass criteria 1–6 |
| 2 | §5 optional SQL quoting + DDL split | Export uses quoted ids; `;` in comments/strings does not split DDL |
| 3 | §1 NUC wiped `cmd_init` timing | Short burst; DELETE+NORMAL after return |
| 4 | §6 next-soak 429 dump | One dump; `Work:` not 0.0s from support latch |
| 5 | §7 live-hook / mini-swe e2e | When endpoints and a hook-fail copy exist |
