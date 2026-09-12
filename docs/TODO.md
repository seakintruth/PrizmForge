# PrizmForge Roadmap / TODO

This file lists **only work that still needs to be accomplished**.

Completed work is **not repeated here**. Implementation, PR numbers, soak
post-mortems, and acceptance evidence live in **git history** (`git log`,
merged PRs #108–#124) and `docs/UNATTENDED_CLOSED_LOOP_CAPABILITIES.md`.
Do not paste shipped checklists back into this tracker.

**Last updated:** 2026-09-12

## How to use this file

- Tick a box when the change lands as a commit on the working branch
  (`soak/23`) and mark it `(branch)`; delete the item on the pass after
  that branch merges to `main` (no `[x]` museums there).
- Detailed *design* for an open item stays in this file until it ships.
- Do not merge `soak/doc-run-a-1`, `soak/4-tmp-reporting`,
  `self-edit/soak8`, or any trajectory/docs-only soak branch.

## Section priorities

| Section | Priority | Why |
|---|---|---|
| **§14 Terminal-class CLI benchmarks** | **next** | Route A approved in plan mode; own crafted set first, strict TB adapter later. Phases 1–4 ship on the bench harness with zero new deps |
| §13 Edit-process hardening | **P1** | Atomic apply, materialize crash recovery, bench trial isolation shipped on `soak/23`; §13.3–§13.5/§13.7/§13.8 remain (bench fidelity + verifier honesty) |
| §12 Harness-evolution loop | **P2** | P0/P1/P2 backbone shipped (§12.1–§12.3, §12.4 manifest, §12.5 Evolve gate); §12.4 rollback executor + §12.6 attribution wait on a live round-trip |
| §15 Soak24 findings | **fix on next branch** | First clean approve→materialize mutation since Soak8 (real, verifiable evidence); 4 confirmed code findings from the soak DB + 5 observability nits |
| §7 Closed-loop / mini-swe | **MEDIUM** | Unblocked by live endpoints/hooks, not code |
| Soak-era backlog (§1, §2.3, §3, §6) | **watch** | Lower priority; paid only if the next live soak shows them |
| §9 Annexes | **LOW / parked** | Do not start without new evidence |

---

## 0. Current state & next focus

- **Working branch `soak/23` (not on `main` yet):** §13.1 + §13.6
  (`43e8745`), §13.2 (`f8ef83b`), §12.4 decision observability
  (`760a895`/`3c75264`, includes `SCHEMA_VERSION = 4`),
  §12.5 Evolve gate (`f7fb5b6`/`4343119`). Ticked against `soak/23`;
  purged from this tracker after the merge.
- **Full test suite:** 1362 passed, 0 failed at the last `soak/23` commit;
  pre-commit clean.
- **§12.5 shipped in this cycle:** `harness/evolve_loop.py`
  (`run_evolve_iteration` / `run_evolve_session` / `EvolveBudget`),
  the `evolve.enabled` gate, harness mount loader
  (`harness/system_prompt/<role>.md` + `{{include}}`/`{{placeholder}}`),
  seed `evolve.md`, `[iter-<t>]` tagged materialize commits, and 23 new
  tests. Evolve needs a live model to be meaningful — it starts consuming
  verdicts at §14.6.
- **Next (do):** §14.1–§14.4 — manifest v2, command verifier, driver
  wiring to land before the §14.5 crafted terminal task set. All mock /
  deterministic first; live runs (§14.6) after the seeds are green.
- **Soak24 (2026-09-12):** first governed mutation **materialized via the
  approve→materialize path since Soak8** — proposal `b4041e15` on
  `docs/TODO.md`, reviewer-approved, written to disk (verified in the
  Soak24-target DB + git diff). Free-tier quota (`free-models-per-day`)
  exhausted ~17 min in; opencode fallback misconfigured → run sat on the
  120s no-alternative poll until ^C. Confirmed code findings + fixes in
  §15; degrade paths (§11.2 quota-park / empty-body fallback / resource
  throttle) all behaved as designed.
- **Gates reference:** the §10.7 acceptance criteria and Soak17/Soak22
  post-mortems shipped on the branch and are **not** re-pasted here (git
  history + §11.4 notes).
- **Company endpoints** still need a **manual unlock ~every 8 hours** and
  **must keep falling back** when one key locks.

---

## 14. Terminal-class CLI benchmarks (Route A)

Extend the boxed benchmark (§12.2) to **terminal / command-line-task**
style jobs: the agent works in a cloned repo under a real host bash shell
and is graded by a command that must exit 0. Shipped as **R-oute A on the
native harness** — no new deps, no Docker, deterministic/mock-first — with
a **strict Terminal-Bench (Harbor) translation seam** queued behind a gate
(§14.7). Source of truth: this section + `docs/benchmark_v1.md`.

### 14.1 Scope & locked decisions (2026-09-12, plan mode)

- **Target:** own crafted terminal set **first**, Terminal-Bench format
  later (§14.7).
- **Route:** native harness (Route A). **Live runs:** deterministic/mock
  first, live later.
- **Covenant intact:** `requirements.txt` stays `requests` + `pathspec`.
  Route A keeps the §12.7 out-of-scope list closed: no `terminal-bench`
  pip pkg, no HF `datasets`, no Docker / enclave OS-sandboxing. §14.7 is
  gated on an explicit override of that list.
- **Runtime:** host bash via `ShellWorktree.run_command` /
  `run_test_command` (`subprocess shell=True`; no tmux/PTY). The gap vs
  TB/Harbor (per-task Docker image + tmux) is accepted for the own-set
  phase.
- **Shell reachability:** a terminal task reaches a shell **only** when
  `developer.implementation="shell"` is set; `strict task_scope` skips the
  shell session when the seed names no target file — so **every crafted
  terminal seed must name a real target file**.
- **Dual grading:** terminal seeds may use the content contract
  (`empty_file`/`contains`/`absent`/`mode`) **or** the command verifier
  (exit 0 = pass). The FINISH-evidence gate stays first (§13.5).

- [ ] **Seeds authorship:** draft the 5 §14.5 tasks in-repo (self-authored,
      copy-mutable, no live installs) unless a user-supplied task set is
      provided before Phase 4.

### 14.2 Phase 1 — manifest v2 + repo fixtures

- [ ] `harness/benchmark/tasks.py`: `SUPPORTED_SCHEMA_VERSION = 2`; add
      optional per-task fields — `terminal` kind, `repo {url, commit}`
      (overrides `workdir` for the trial), `setup` (one-time bash list
      before turns), `verifier {command, timeout}` (command mode; content
      contract when absent). `rendered_json` / `rendered_contract` /
      **`contract_hash` fold every new field** so the rollout fingerprint
      stays truthful.
- [ ] `harness/benchmark/repo_fixture.py`: `git clone` snapshot at
      `commit` + `ingest_tree_to_governed` into the per-trial lib, bounded
      by `ShellWorktree.max_file_bytes` (512 KB) and a per-task file-count
      cap; clone cache shared across trials; never writes to the origin.
      (Wild remote repos stay out of the crafted set — copy-mutable
      fixtures only.)
- [ ] Tests: schema-v2 parse/reject, fixture clone + ingest bounds,
      `contract_hash` stability over the new fields.

### 14.3 Phase 2 — command verifier

- [ ] `harness/verify.py` command mode: run `verifier.command` via
      `ShellWorktree.run_test_command` in the trial workdir; exit 0 =
      `passed`, else `failed` (exit code + stderr in `verdict_note`).
      Runner injectable so unit tests never shell out.
- [ ] Evidence gate stays first: a command-passing trial with no
      `edit.materialized` + `file_write_log` evidence still fails (§13.5
      honesty).
- [ ] Tests: exit-0 pass, exit-1 fail + stderr capture, timeout bound,
      injectable runner.

### 14.4 Phase 3 — driver wiring

- [ ] `harness/benchmark/driver.py`: per-task clone/setup step before
      turns; per-task `max_turns` + wall-clock timeout honored; still
      sequential trials / single DB writer (no `--max-workers`).
- [ ] Bench config: terminal tasks run with
      `developer.implementation="shell"`; each seed names a target file so
      `strict task_scope` keeps the session on-task. CLI defaults stay
      tolerant (no new required flags).
- [ ] Integration test: one terminal task end-to-end with a mocked LLM —
      setup runs, agent edits, command verifier passes/fails.

### 14.5 Phase 4 — terminal task set + tests

- [ ] `harness/benchmark/tasks_terminal.json`: **5 crafted command-line
      tasks** (e.g. rename/refactor a script, fix a CLI flag default —
      each names a real target). Small copy-mutable repo fixture, no
      network / live installs.
- [ ] Task + verifier + per-task settings pass review before landing
      (mutability, determinism, shell reachability).
- [ ] Full suite green; commit on `soak/23`.

### 14.6 Phase 5 — live-run gate

- [ ] Mock/deterministic runs green on the terminal set; then `--live`
      endpoint runs (deterministic ordering, iteration-labeled results) —
      completes §13.7.
- [ ] §12.5 Evolve loop starts consuming **terminal** verdicts; §12.4's
      rollback executor (`git revert` / governed undo on
      `revert_candidates`) can land once an Evolve iteration round-trips
      (ties to §12.7 P2 gate).

### 14.7 Phase 6 — Terminal-Bench (Harbor) translation seam (gated)

- [ ] `harness/benchmark/tb_manifest.py`: translate a TB task
      (instruction → seed, `repo url + commit` → `repo`, `tests/test.sh`
      → `verifier.command`) into manifest-v2 tasks; TB format drift fails
      loudly, never silently.
- [ ] **Gate:** explicit Board approval to open §12.7 out-of-scope
      (Terminal-Bench pip / HF `datasets` / Docker OS-sandbox) is required
      before this phase. Not started until §14.5/§14.6 are green.
- [ ] Comparable pass@1 across own-set vs TB-task runs (single harness,
      not a duplicate).

### 14.8 Out of scope (until the §14.7 gate)

- `terminal-bench` pip package; HF `datasets`; Docker / enclave
  OS-sandboxing (tmux/PTY absent today); wild remote repos in seeds (no
  network installs); mutating / pushing to origin; benchmarking the
  sub-process sandbox itself.

### 14.9 Exit criteria

| Phase | Exit criterion |
|---|---|
| §14.2 manifest v2 | 5 terminal tasks parse; `contract_hash` folds `repo`/`setup`/`verifier` |
| §14.3 command verifier | Command mode passes/fails on exit code; honest with the evidence gate |
| §14.4 driver wiring | Terminal tasks run end-to-end on the mocked LLM; hermetic |
| §14.5 tasks + tests | `tasks_terminal.json` + tests green; full suite on `soak/23` |
| §14.6 live runs | Live endpoint runs give comparable pass@1; §12.5 consumes terminal verdicts |
| §14.7 TB seam | TB-format tasks translate cleanly or fail loudly; pass@1 comparable across sets |

---

## 12. Harness-evolution loop — remaining work

**Priority:** P2. Source: `docs/HARNESS_EVOLUTION_DESIGN.md`.

**Shipped on `soak/23` (not repeated):** §12.1 P0 substrate
(fingerprint + infra-abort classifier), §12.2 P1 boxed benchmark
(`harness/benchmark/` §14 builds on it), §12.3 P1 trajectory corpus
(`harness/cleaning.py`, `harness/debugger.py`/`corpus.py`), §12.4 manifest
+ verdicts + `task_outcomes` + `SCHEMA_VERSION = 4` standing up
`edit_verdicts` (the §5.2 prediction∩delta SQL), §12.5 the full Evolve
gate (`evolve_loop.py`, mount loader, `evolve.md`, `[iter-<t>]` tags).
Dependency posture: zero new runtime deps; see §14 for the terminal-class
extension.

### 12.4 (remaining) — rollback executor

- [ ] `git revert <edit.commit>` on the harness workspace (or
      `undo_proposal`) when confirms == 0 and flagged/extra regressions
      land; `revert_candidates(prior, cur)` SELECTs the offenders (§5.3).
      Executor runs in `run_evolve_session` before the next distillation
      so verdicts stay in the corpus. Lands after §14.6 (needs a defining
      live round-trip).

### 12.6 P3 attribution (after a working loop)

- [ ] Single-component swaps (`+ memory` / `+ tool` / `+ middleware` /
      `+ system_prompt`) to attribute pass@1 deltas (§7 component
      ablation).
- [ ] `H_best <- H_t` tracking; then cross-benchmark / cross-model
      transfer (deferred until the internal loop is stable).

### 12.7 Phase order & exit criteria

| Phase | Exit criterion |
|---|---|
| P0 (§12.1) | Rollouts carry fingerprints; infra aborts excluded and counted |
| P1 (§12.2–12.3) | One iteration produces cleaned/ + analysis/ + overview/ + index.json — **satisfied** |
| P2 (§12.4–12.5) | An iteration round-trips: harness edits → verdict → rollback (§14.6 unblocks the rollback leg) |
| P3 (§12.6) | A single-component swap changes measured pass@1 |

**Out of scope (do not start):** Terminal-Bench 2 / `terminal-bench` pip,
SWE-bench-verified (`datasets`), Docker / enclave OS-sandboxing, editing
`runs/` or endpoint config (even by the Evolve Agent), PostgreSQL /
SQLAlchemy mirror, and any dependency entry beyond `requests` / `pathspec`
for this loop. §14.7 is the only planned exception and stays gated.

---

## 13. Edit-process hardening — remaining work

**Priority:** P1; no new deps.
**Shipped on `soak/23` (not repeated):** §13.1 atomic apply (all-or-nothing
proposals, op-shape guard), §13.2 materialize crash consistency + multi-file
correctness (`recover_orphaned_applied`, per-file `file_statuses` /
`partial_materialized`, per-op file dispatch, post-commit symbol refresh),
§13.6 benchmark isolation + timeboxing (+ schema-version honor).

### 13.3 Diff / replace strictness (P1, bench fidelity)

- [ ] `_apply_unified_diff` (heuristic resync, soft-deletion matching) is
      either made strict (context must match exactly, ambiguity fails) or
      post-verified: reconstruct result == intended target, fail loudly on
      mismatch.
- [ ] Contract tests for `find_replace` `regex=True` / `count` application
      (currently only schema-level) and partially-matching diff hunks.

### 13.4 Efficiency — token cost per edit (P1)

- [ ] Chat-table mode: stop re-serializing the full step table each turn
      (`workflow/shell_developer.py`); send delta step + compact summaries
      (bounded) so a long session does not balloon the observation.
- [ ] Legacy fallback: reuse the primary attempt's file content across
      fallback re-queries (`workflow/developer_edit.py`), resending only
      instructions + prior failure reason.
- [ ] Reviewer prompt: cap re-pasted file content to the changed regions
      when the file is large (keep full content for small files).

### 13.5 Verifier honesty — disk + pre/post (P2)

- [ ] `harness/verify.py` reads governed DB only; check the on-disk file
      under the bench project dir (DB as fallback), recording which source
      satisfied.
- [ ] Add `mode: "new"` (absent in fixture, present after) so a `contains`
      fragment that was already true pre-task cannot pass.
- [ ] For the bench path, cross-check `status passed` against evidence
      (`edit.materialized` + `file_write_log` success) instead of trusting
      the runner's own label.

### 13.7 Live/control runs (P2)

- [ ] `bench_config` (`harness/benchmark/config.py`) hardcodes `endpoints:
      {}` / `mock-model`; add `--live` endpoint/model injection +
      deterministic ordering + iteration-labeled results so pass@1 is
      comparable across real control runs. `python -m harness.benchmark
      --dry-run` validates the manifest + isolated DB without LLM calls.
      (§14.6 exercises this.)

### 13.8 Test seams for the pipeline (P1)

- [ ] Split `apply_edit_proposal` / `materialize_proposal` (both C901) into
      small helpers — op-dispatch table, affected-path resolver,
      write-log status reducer — so atomicity/status logic is unit-testable
      without a DB.
- [ ] Cover the identified gaps: multi-op rollback, crash recovery, trial
      isolation, sort-order renumber stress (gap < `MIN_GAP_THRESHOLD`),
      regex/count find_replace, diff ambiguity.

---

## 15. Soak24 — first clean mutation + soak-DB code findings (2026-09-12)

Soak24 evidence: `/home/jeremy-gerdes/git/github/PrizmForge-Soak/Soak24-target/
PrizmForge/.PrizmForge/agents.db` (read `mode=ro`; sqlite3 absent — use
`.venv/bin/python` + stdlib sqlite3), `shell_trajectories/`, `reports/`, and
the target `git status`/`git diff`. Purge this section after the next branch
that carries its fixes merges.

### 15.1 Outcome (verifiable, keep as evidence until purge)

- [x] **One governed mutation completed the full approval chain on the
      default free model:** `edit_proposals` row `b4041e15-…` (target
      `docs/TODO.md`, mode `guid`) → `events`: `proposal.created` →
      `proposal.approved` (source=reviewer) → `edit.materialized`
      (success) → `file_write_log` status `success` → disk diff verified
      (12 insertions / 8 deletions, coherent §13-status updates). First
      materialized mutation since Soak8.
- [x] **Seed feedback addressed:** `agent_feedback` id 1 (seed) has
      `addressed_by=developer` at the materialize time.
- [x] **Background analysis delivered without mutation rights:**
      `agent_feedback` holds 10 `jr_reviewer` findings + 3
      `security_reviewer` passes (no actionable items); one project report
      written. Resource controller decisions logged (throttle 118→11 rpm
      on the 429 storm; feeder 30s→180s).
- [x] **Degradation paths behaved (§11.2/§11.3):** reasoning-only
      `content: null` response (`dots-3-note-preview:free`) flagged
      `empty_body` → fell back → opencode `MissingSessionID` → 240m
      misconfig park; `free-models-per-day` 429 → quota park
      `min(reset, 4h)`; then repeated `no_alternate_endpoint` (120s
      recheck) until operator ^C. Token math honest: `token_log` = 54
      calls / 261,982 tokens; resource `tokens_remaining` reconciles
      (20M-day budget).

### 15.2 Confirmed code findings from the soak DB (fix on next branch)

- [ ] **`cmd_export_db` task-scoped export leaks cross-task rows.** Tables
      without a `task_id` column fall through to `SELECT *` full-scope
      (`cli/commands.py:383-388`) and are only *labeled* `(all tasks)` —
      an export with `task_id=X` still ships every task's rows
      (e.g. `token_log`). Decide: reject scope+table, filter, or fail
      loudly instead of silently exporting full scope.
- [ ] **`cmd_export_db` CSV filename from `sqlite_master` table names**
      (`cli/commands.py:398`, `output_dir / f"{table_name}.csv"`). Low risk
      (fixed schema) but a hostile table name could write outside
      `output_dir`; sanitize/`Path`-resolve or reject.
- [ ] **`cmd_show_prompt` NULL-`prompt` TypeError.** `len(prompt)` at
      `cli/commands.py:329` is unguarded while `response` at `:333` is
      guarded — a NULL `prompt` row (failed/empty-body archive) raises
      `TypeError`. Mirror the `if response else 0` guard.
- [ ] **`cmd_init` hash-only fast path skips without verifying
      `file_summaries` + `file_lines` rows** (`cli/commands.py:85-89`):
      matching `content_hash` increments `indexed` and continues, so a
      partial/cleared index leaves rows silently missing. Verify both
      tables exist for the path before skipping, else re-sync.
- [ ] (**likely false positive — do not reopen without evidence**)
      `resource_controller.json` "UUID metadata brackets" finding: the file
      is valid JSON with documented `_note` keys; the reviewer conflated DB
      schema-line format with this JSON (§9.5 posture).

### 15.3 Observability / data-hygiene nits (design accepted, track)

- [ ] **`Work: 0.0s` header is a reset-then-print ordering bug**
      (`workflow/task_runner.py:771-778`): `_active_work_seconds = 0.0`
      is set immediately before the print, so the header always shows
      0.0 regardless of real model-call latency. The iteration timebox
      (line 1370) still consumes the true value — display-only, but the
      §6 "Work: 0.0s" backlog item now has a confirmed root cause.
      Fix: print the previous iteration's value, or move the reset
      after the print.
- [ ] **Duplicate startup line** — `✅ API keys configured for N
      endpoint(s)` printed twice (`main.py:154` + `:156`); remove one.
- [ ] **`endpoint_health.unavailable_until` is last-writer-loses
      persistence:** a 300s `empty_body` cooldown at 10:59:22 overwrote
      the 4h 429 park on the row (shows 11:04:22 while the in-memory
      latch counted 14399s). Persist `max(existing, new)` or have
      diagnostics read the runtime latch.
- [ ] **`edit_proposals.reviewed_at` / `reviewed_by_agent_id` stay NULL**
      even though `events.proposal.approved` (source=reviewer) exists —
      populate them in the approve/materialize path.
- [ ] **DB timestamp convention mixed per table** (`events`,
      `edit_proposals`, `errors` = UTC; `model_health_events`,
      `token_log`, `endpoint_health` = local EDT), which breaks
      cross-table joins and confused this review. Normalize to UTC.

### 15.4 Ops posture (matches backlog, confirmed again)

- [ ] **Free-only 8h unattended is not viable**: the `free-models-per-day`
      ceiling (~262K tokens ≈ 17 min here) plus the misconfigured opencode
      fallback leaves the remaining window as 120s no-alternative polling.
      Add a working second endpoint (paid/company) or shrink the window —
      otherwise the evolution-loop (§12.5) and §14 live runs will starve
      on free-tier alone.

---

## 7. Closed-loop and mini-swe residuals

Need live runtime / endpoints / machines (code on `main`).

### 7.1 Git closed loop

Source: `docs/UNATTENDED_CLOSED_LOOP_CAPABILITIES.md`.

- [ ] Live failing-hook smoke on a copy: CRITICAL feedback → developer
      fix-forward proposal → materialized and addressed, visible in
      events/errors/feedback. In-process proofs exist in
      `tests/unit/test_git_closed_loop.py`.
- [ ] Ignored-path in the git closed loop (e.g. gitignored `config.json`):
      skip git or fail with `path is gitignored`, never silent success.
      **Default parked (§9.3 decision 3).**
- [ ] Diagnostic dump shows a forced-hook-failure path (Workstream F dump
      sections). `git_fail` counter already exists in task summaries.

### 7.2 Mini-swe / shell port

Port itself is shipped (`docs/mini_swe_agent.md`); Soak4 proved the runner
executes real commands but the chat-refusal developer model will not drive
a second bash block — that e2e is the §14/soak workstream, not a re-port.

- [ ] Real-model end-to-end validation + prompt/limit tuning (a developer
      model that emits a second bash block).
- [ ] Manual cold-start smoke: seed consumed on turn 1, no `Unknown model`
      lines.
- [ ] Enclave sandboxing (container / approved-workstation). Shell runs
      are not confined to the worktree today.
- [ ] Post-materialize `test_command` re-run — **deferred** (session
      `test_command` + ruff pre-check already gate). Revisit only if a
      deploy-time validator becomes a requirement.
- [ ] EndpointManager / LiteLLM overlap — parked; no routing layer planned.

---

## Soak-era backlog (watch — pay only if the next live soak shows them)

### 1. Cold-soak SQLite ingest — NUC timing (operator)

Code shipped in #121 (single writer, MEMORY journal + `synchronous=OFF`
walk, restore DELETE + NORMAL, `executemany`, in-process hash skip).
Still unpaid:

- [ ] Time a wiped `cmd_init()` on the NUC (2-core / ≥8 GB) before vs after
      on the same tree; wall-clock drops to a short burst; no new
      `database is locked` storms.

Do not persist `.PrizmForge/` between soaks. Do not switch the live soak to
WAL unless this timing is still not enough.

### 2.3 Shell protocol nits (only if a soak shows them)

- [ ] `<finish>` alias — accept as alias for one release only if it recurs.
- [ ] `is_valid_bash_block` requires `` ```bash\n ``; strip `\r` in
      `normalize_shell_reply` if a soak emits `` ```bash\r\n ``.
- [ ] `classify_shell_reply` labels any text containing `` ```bash `` that
      is not a closed block `UNTERMINATED_BASH_BLOCK` (error text that
      *quotes* the format). Conservative; leave unless it poisons
      diagnostics.

### 3. Feedback / developer dispatch — soak watches

- [ ] **Seed-path regex** `[\w./-]+\.\w+`
      (`agents/parallel_workers.py` `_resolve_seed_target_path`) can bind
      `config.json`. Longest-wins + `project_files` lookup bounds it;
      tighten if a soak edits gitignored config.
- [ ] Scope-creep watch: a seed naming `workflow/__init__.py` must not
      enqueue siblings unless the task is repository-wide. Re-measure on
      the next soak with background agents on; if fan-out returns, the cap
      is not binding.

### 6. Latch / fallback — next-soak acceptance

Latch-only `is_available()`, skip-path fallback, dump-once, support
freeze, `seen` recurse all shipped. Still unpaid:

- [ ] One 429 parks an endpoint; stdout shows **one** dump; other agents
      skip in one line; orchestrator/developer reach a healthy fallback;
      `Work:` is not 0.0s only because support held the latch.

Non-goals (still): do not spoof OpenCode CLI headers; do not treat
`free-models-per-day` as a product bug; do not reopen short Retry-After
for non-quota 429/503.

---

## 9. Annexes (parked — do not start)

### 9.2 Structural tech-debt

- [ ] `project_files` metadata normalize — needs a design doc before
      touching the governed-edit path.
- [ ] Standardize file_editing error shape / status vocabulary.
- [ ] 120s unlock sleep in `agents/base.py` (401/KEY_LOCKED) and
      `interactive.py` (unattended recovery) → shared `unavailable_until`
      latch. Related to the 8-hour company unlock.

### 9.3 Defaults (do not reopen without evidence)

1. Hook failure: fix-forward unless `git.revert_on_hook_failure`.
2. Create-file: clean relative paths OK.
3. `config.json` stays human-only (gitignored).
4. Reviewer sees hook output optionally; developer is primary.
5. Network streaks: `NetworkBusyLoopGuard` (shipped).

### 9.4 Not this pass

- PostgreSQL / SQLAlchemy dual backend.
- Live-soak **WAL + single-writer queue** as the default runtime. Live soak
  stays DELETE + NORMAL after init. Revisit WAL only if NUC timing is not
  enough.
- Copy-forward of `.PrizmForge/` between soaks.

### 9.5 False positives — no change

- Init-window `synchronous=OFF` / MEMORY journal is intentional; restore
  before iteration 1 (#121).
- `core/db_helpers.py` feedback SQL is parameterized.
- `agent_schemas/*.json` stay example-shaped for `get_schema_example()`.
- `cli/__init__.py` empty / `datetime.now()` cosmetics.

---

## Implementation sequence (open work only)

| Order | Work item | Exit criterion |
|---:|---|---|
| 1 | §14.2 manifest v2 + repo fixture | 5 terminal tasks parse; `contract_hash` folds new fields |
| 2 | §14.3 command verifier | Exit-0/exit-1 graded; honest with evidence gate |
| 3 | §14.4 driver wiring | Terminal task end-to-end on mocked LLM; hermetic |
| 4 | §14.5 tasks_terminal.json + tests | Full suite green on `soak/23` |
| 5 | §14.6 live-run gate (mock → live) | Comparable pass@1; §12.5 consumes verdicts → unblocks §12.4 rollback |
| 6 | §13.3 / §13.4 / §13.5 / §13.8 | Strict diff, token-efficient prompts, honest verifier, test seams |
| 7 | §12.6 attribution ablations | A single-component swap changes measured pass@1 |
| 8 | §14.7 TB translation seam (gated) | Board gate opens §12.7 out-of-scope; TB tasks translate or fail loudly |