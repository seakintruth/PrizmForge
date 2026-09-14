# PrizmForge Roadmap / TODO

This file lists **only work that still needs to be accomplished**.

Completed work is **not repeated here**. Implementation, PR numbers, soak
post-mortems, and acceptance evidence live in **git history** (`git log`,
merged PRs #108–#128) and `docs/UNATTENDED_CLOSED_LOOP_CAPABILITIES.md`.
Do not paste shipped checklists back into this tracker.

**Last updated:** 2026-09-12

## How to use this file

- Tick a box when the change lands as a commit on the working branch
  (`fix/soak24-findings`, off `main`) and mark it `(branch)`; delete the
  item on the pass after that branch merges to `main` (no `[x]` museums
  there).
- Detailed *design* for an open item stays in this file until it ships.
- Do not merge `soak/doc-run-a-1`, `soak/4-tmp-reporting`,
  `self-edit/soak8`, or any trajectory/docs-only soak branch.

## Section priorities

| Section | Priority | Why |
|---|---|---|
| **§15 Soak24 findings** | **do now** | Ships first, before §14: 4 confirmed `cli/commands.py` bugs + all 5 §15.3 nits (incl. UTC normalization) on branch `fix/soak24-findings`; small, verified, keeps soak evidence clean |
| §16 Context protocol | **after §15** | Stops random reviewer file dumps; coverage ledger; OpenCode-style prune+rehydrate. Cheap, no live-endpoint gate. |
| **§14 Terminal-class CLI benchmarks** | **next** | Route A approved in plan mode; own crafted set first, strict TB adapter later. Phases 1–4 ship on the bench harness with zero new deps |
| §13 Edit-process hardening | **P1** | Atomic apply, materialize crash recovery, bench trial isolation shipped on `soak/23`; §13.5/§13.7 fold into §14.3/§14.6; §13.3/§13.4/§13.8 remain (bench fidelity + verifier honesty) |
| §12 Harness-evolution loop | **P2** | Backbone shipped **dark** on #128 (`evolve.enabled` default false). Do not enable until §12.8. Rollback *code* exists; rollback *safety* + live round-trip wait on §14.6 |
| §7 Closed-loop / mini-swe | **MEDIUM** | Unblocked by live endpoints/hooks, not code |
| Soak-era backlog (§1, §2.3, §3, §6) | **watch** | Lower priority; paid only if the next live soak shows them |
| §9 Annexes | **LOW / parked** | Do not start without new evidence |

---

## 0. Current state & next focus

- **#128 on `main`:** §13.1 / §13.2 / §13.6 and §12.4–§12.5 shipped.
  `SCHEMA_VERSION = 4` — first `init_db` after upgrade wipes a v3
  `agents.db`. Evolve stays **off**. Do not point `project_directory` at
  the main working clone if you flip `evolve.enabled`.
- **Next (do):** `fix/soak24-findings` — §15.2 + §15.3, then the four
  §12.8 enablement nits if you touch evolve files on that branch.
  Then **§16** reviewer context protocol (before any §14 live tokens for
  background agents). Then §14.1–§14.4 mock-first.
- **Soak24:** first approve→materialize since Soak8 (`b4041e15` on
  `docs/TODO.md`). Free-tier quota ~17m; degrade paths behaved.
- **Company endpoints** still need a manual unlock ~every 8 hours and
  must keep falling back when one key locks.

---

## 14. Terminal-class CLI benchmarks (Route A)

Extend the boxed benchmark (§12.2) to **terminal / command-line-task**
style jobs: the agent works in a cloned repo under a real host bash shell
and is graded by a command that must exit 0. Shipped as **Route A on the
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
- [ ] Full suite green; commit on `main`.

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
| §14.5 tasks + tests | `tasks_terminal.json` + tests green; full suite on `main` |
| §14.6 live runs | Live endpoint runs give comparable pass@1; §12.5 consumes terminal verdicts |
| §14.7 TB seam | TB-format tasks translate cleanly or fail loudly; pass@1 comparable across sets |

---

## 12. Harness-evolution loop — remaining work

**Priority:** P2. Source: `docs/HARNESS_EVOLUTION_DESIGN.md`.

**Shipped on #128 (not repeated):** §12.1 P0 substrate
(fingerprint + infra-abort classifier), §12.2 P1 boxed benchmark
(`harness/benchmark/` §14 builds on it), §12.3 P1 trajectory corpus
(`harness/cleaning.py`, `harness/debugger.py`/`corpus.py`), §12.4 manifest
+ verdicts + `task_outcomes` + `SCHEMA_VERSION = 4` standing up
`edit_verdicts` (the §5.2 prediction∩delta SQL), §12.5 the full Evolve
gate (`evolve_loop.py`, mount loader, `evolve.md`, `[iter-<t>]` tags).
`run_evolve_reverts` / `_git_revert` already run in `run_evolve_session`.
What is left is SHA binding + regression scoping (§12.4 remaining + §12.8),
not writing the executor from scratch.
Dependency posture: zero new runtime deps; see §14 for the terminal-class
extension.

### 12.4 (remaining) — rollback executor safety

Executor is in-tree and dark. Not safe to enable until:

- [x] Bind revert to the SHA `materialize_proposal` tagged (`[iter-<t>]`),
      not `git rev-parse HEAD`. Missing SHA → `undo_proposal`, never guess. —
      `harness/evolve_loop.py` `_materialize_commit_sha` (git log grep for the
      proposal marker `proposal <id>[0:8]`), `run_evolve_reverts` now routes a
      missing/untraceable SHA to `_try_undo_proposal`; `-1` commit only.
- [x] `revert_candidates`: revert only when `confirms == 0` AND
      `predicted_regressions ∩ landed`. Drop iteration-global
      `regressions_outnumber` (one unrelated flip reverts every zero-confirm
      edit). — `harness/evolve.py` + tests
      (`test_revert_candidates_ignores_unflagged_regressions`).
- [x] Delete the unused `json_each` `flagged_rows` query in `harness/evolve.py`.

### 12.8 Evolve enablement gate (before `evolve.enabled=true`)

- [x] `{{include:}}` resolves under `system_prompt/` (`Path.resolve` +
      `relative_to`); reject `../`. — `resolve_harness_prompt` + tests.
- [x] Count `applied` only on materialize `status == "success"` — not
      `lint_failed` / `git_failed`.
- [x] Validate **every op path** in the proposal, not only
      `target_file_path` on the propose dict. — `_proposal_touched_paths` +
      `validate_evolve_targets` + test.
- [x] Debugger/Evolve `--max-workers 1` on company keys until TokenPacer
      is locked. — `harness/debugger.py` `run_producer` defaults to
      `max_workers=1` (serial by default; parallelism an explicit opt-in).

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
| P2 (§12.4–12.5) | An iteration round-trips: harness edits → verdict → rollback (§14.6 unblocks the rollback leg) — §12.8 must be green before any live `evolve.enabled=true`. |
| P3 (§12.6) | A single-component swap changes measured pass@1 |

**Out of scope (do not start):** Terminal-Bench 2 / `terminal-bench` pip,
SWE-bench-verified (`datasets`), Docker / enclave OS-sandboxing, editing
`runs/` or endpoint config (even by the Evolve Agent), PostgreSQL /
SQLAlchemy mirror, and any dependency entry beyond `requests` / `pathspec`
for this loop. §14.7 is the only planned exception and stays gated.

---

## 13. Edit-process hardening — remaining work

**Priority:** P1; no new deps.
**Shipped on #128 (not repeated):** §13.1 atomic apply (all-or-nothing
proposals, op-shape guard), §13.2 materialize crash consistency + multi-file
correctness (`recover_orphaned_applied`, per-file `file_statuses` /
`partial_materialized`, per-op file dispatch, post-commit symbol refresh),
§13.6 benchmark isolation + timeboxing (+ schema-version honor).

### 13.3 Diff / replace strictness (P1, bench fidelity)

- [x] `_apply_unified_diff` (heuristic resync, soft-deletion matching) is
      either made strict (context must match exactly, ambiguity fails) or
      post-verified: reconstruct result == intended target, fail loudly on
      mismatch. — `file_editing/editing.py` strict rewrite (hunk count
      verification, pure-add hunks, no resync).
- [x] Contract tests for `find_replace` `regex=True` / `count` application
      (currently only schema-level) and partially-matching diff hunks. —
      `tests/unit/test_edit_contracts.py` (TestEditPayloadOperations).

### 13.4 Efficiency — token cost per edit (P1)

- [x] Chat-table mode: stop re-serializing the full step table each turn
      (`workflow/shell_developer.py`); send delta step + compact summaries
      (bounded) so a long session does not balloon the observation. — §16.3
      `core/session_projection.py` (when enabled; `_summarize_session` /
      compact bounded).
- [x] Legacy fallback: reuse the primary attempt's file content across
      fallback re-queries (`workflow/developer_edit.py`), resending only
      instructions + prior failure reason. — `workflow/developer_edit.py`
      dual mode views (`plain_views` / `guid_views`) read once, reused per
      attempt via `_view_for`.
- [x] Reviewer prompt: cap re-pasted file content to the changed regions
      when the file is large (keep full content for small files). —
      `workflow/reviewer_gate.py` `reviewer_original_view` (region view,
      bounded marker) wired into both developer + shell reviewer prompts.

### 13.5 Verifier honesty — disk + pre/post (P2)

The bench-path cross-check item below lands with **§14.3** (command
verifier); the disk + `mode: "new"` items stay independent.

- [x] `harness/verify.py` reads governed DB only; check the on-disk file
      under the bench project dir (DB as fallback), recording which source
      satisfied. — `_read_file(file_path, workdir)` returns `(content, source)`,
      `source == "disk"` recorded in the assertion note / `content_ok:disk`.
- [x] Add `mode: "new"` (absent in fixture, present after) so a `contains`
      fragment that was already true pre-task cannot pass. — `_check_assertion`
      mode `"new"` + `preexisting_in_fixture` guard in `verify_trial`.
      (Previously marked for independent landing; mode landed with verify.py upstream.)
- [x] For the bench path, cross-check `status passed` against evidence
      (`edit.materialized` + `file_write_log` success) instead of trusting
      the runner's own label. — `evidence_satisfied` (§14.3) gates command-mode
      passes; fail-closed on DB trouble.

### 13.7 Live/control runs (P2)

Lands via **§14.6** (`--live` runs consume this); exercised there.

- [ ] `bench_config` (`harness/benchmark/config.py`) hardcodes `endpoints:
      {}` / `mock-model`; add `--live` endpoint/model injection +
      deterministic ordering + iteration-labeled results so pass@1 is
      comparable across real control runs. `python -m harness.benchmark
      --dry-run` validates the manifest + isolated DB without LLM calls.
      (§14.6 exercises this.)

### 13.8 Test seams for the pipeline (P1)

- [x] Split `apply_edit_proposal` / `materialize_proposal` (both C901) into
      small helpers — op-dispatch table, affected-path resolver,
      write-log status reducer — so atomicity/status logic is unit-testable
      without a DB. — `file_editing/editing.py`: `_OP_APPLICATORS` +
      `_dispatch_operation` (name-based lookup so ops stay monkeypatchable),
      `_first_operation_error`; `file_editing/writer.py`: `_capture_before_state`,
      `_ensure_applied`, `_materialize_one_file`, `_combine_materialize_results`.
      C901 noqa removed from both.
- [x] Cover the identified gaps: multi-op rollback, crash recovery, trial
      isolation, sort-order renumber stress (gap < `MIN_GAP_THRESHOLD`),
      regex/count find_replace, diff ambiguity. — multi-op rollback
      (`test_edit_contracts` failure+exception variants), crash recovery
      (`test_git_closed_loop` orphaned-applied), trial isolation (driver
      per-trial clone + isolated DB wiring tests), renumber stress
      (`TestSortOrderRenumberStress`), regex/count + diff strictness
      (`TestEditPayloadOperations` §13.3 tests).

---

## 15. Soak24 — first clean mutation + soak-DB code findings (2026-09-12)

Soak24 evidence: `/home/jeremy-gerdes/git/github/PrizmForge-Soak/Soak24-target/
PrizmForge/.PrizmForge/agents.db` (read `mode=ro`; sqlite3 absent — use
`.venv/bin/python` + stdlib sqlite3), `shell_trajectories/`, `reports/`, and
the target `git status`/`git diff`. Fix branch (next, off `soak/23`):
`fix/soak24-findings`. Tick boxes `(branch)` as each lands; purge this
section after that branch merges.

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

### 15.2 Confirmed code findings from the soak DB (branch `fix/soak24-findings`)

- [x] **`cmd_export_db` task-scoped export leaks cross-task rows.** Tables
      without a `task_id` column fall through to `SELECT *` full-scope
      (`cli/commands.py:383-388`) and are only *labeled* `(all tasks)` —
      an export with `task_id=X` still ships every task's rows
      (e.g. `token_log`). Decide: reject scope+table, filter, or fail
      loudly instead of silently exporting full scope.
      **Fixed:** task-scoped exports now skip tables with no `task_id`
      column loudly (`⏭️ … not task-scoped`) in both `cmd_export_db` and
      `cmd_export_specific_tables`; full-scope (no `task_id`) still exports
      them with an `(all tasks)` tag. Tests:
      `tests/unit/test_cli_commands.py::TestExportTaskScopeNoLeak`.
- [x] **`cmd_export_db` CSV filename from `sqlite_master` table names**
      (`cli/commands.py:398`, `output_dir / f"{table_name}.csv"`). Low risk
      (fixed schema) but a hostile table name could write outside
      `output_dir`; sanitize/`Path`-resolve or reject.
      **Fixed:** `_is_safe_table_name` allowlist (`^[A-Za-z0-9_]+$`)
      rejects unsafe names before any file is created.
- [x] **`cmd_show_prompt` NULL-`prompt` TypeError.** `len(prompt)` at
      `cli/commands.py:329` is unguarded while `response` at `:333` is
      guarded — a NULL `prompt` row (failed/empty-body archive) raises
      `TypeError`. Mirror the `if response else 0` guard.
      **Fixed:** `len(prompt) if prompt else 0` + `"NO PROMPT"` rendering;
      test `test_cli_commands.py::test_cmd_show_prompt_null_prompt_does_not_crash`.
- [x] **`cmd_init` hash-only fast path skips without verifying
      `file_summaries` + `file_lines` rows** (`cli/commands.py:85-89`):
      matching `content_hash` increments `indexed` and continues, so a
      partial/cleared index leaves rows silently missing. Verify both
      tables exist for the path before skipping, else re-sync.
      **Fixed:** completeness check (file_summaries row + non-deleted
      `file_lines` via `files` join); re-syncs when incomplete. Tests:
      `tests/unit/test_cli_commands.py::TestCmdInitResyncPartialIndex`.
- (**likely false positive — do not reopen without evidence; not a fix
  item**) `resource_controller.json` "UUID metadata brackets" finding: the
  file is valid JSON with documented `_note` keys; the reviewer conflated DB
  schema-line format with this JSON (§9.5 posture).

### 15.3 Observability / data-hygiene nits (all five on the fix branch, incl. UTC normalization)

- [x] **`Work: 0.0s` header is a reset-then-print ordering bug**
      (`workflow/task_runner.py:771-778`): `_active_work_seconds = 0.0`
      is set immediately before the print, so the header always shows
      0.0 regardless of real model-call latency. The iteration timebox
      (line 1370) still consumes the true value — display-only, but the
      §6 "Work: 0.0s" backlog item now has a confirmed root cause.
      Fix: print the previous iteration's value, or move the reset
      after the print. **Fixed:** header prints the previous iteration's
      value before the reset; `global` declaration hoisted to the
      function top.
- [x] **Duplicate startup line** — `✅ API keys configured for N
      endpoint(s)` printed twice (`main.py:154` + `:156`); remove one.
      **Fixed:** the `else` duplicate removed; the line prints once.
- [x] **`endpoint_health.unavailable_until` is last-writer-loses
      persistence:** a 300s `empty_body` cooldown at 10:59:22 overwrote
      the 4h 429 park on the row (shows 11:04:22 while the in-memory
      latch counted 14399s). **Fixed:** `mark_failure` + `_save_to_db`
      now persist `max(existing, new)` (never-shrink latch), so a
      shorter cooldown can no longer clobber a longer active park and
      an expired one is freely replaced; `mark_success` still clears.
- [x] **`edit_proposals.reviewed_at` / `reviewed_by_agent_id` stay NULL**
      even though `events.proposal.approved` (source=reviewer) exists —
      populate them in the approve/materialize path.
      **Fixed:** approve/reject call sites in `workflow/developer_edit.py`,
      `workflow/shell_developer.py`, `harness/evolve_loop.py`, and
      `workflow/reviewer_gate.py` now pass `reviewed_by_agent_id=2`
      (developer=1, reviewer=2 convention). Tests:
      `tests/unit/test_proposal_builder.py::TestReviewedByAgentIdWiring`.
- [x] **DB timestamp convention mixed per table** (`events`,
      `edit_proposals`, `errors` = UTC; `model_health_events`,
      `token_log`, `endpoint_health` = local EDT), which breaks
      cross-table joins and confused this review. Normalize to UTC.
      **Fixed:** interop writer modules now use `utcnow()`/`utcnow_iso()`
      (naive UTC matching SQLite `CURRENT_TIMESTAMP`): `db_helpers`
      (messages/tasks/conversation_context/agent_feedback), `file_operations`
      (project_files), `archival` (agent_responses_archive),
      `fallback_stats` (endpoint_fallbacks), `writer` (proposal timestamps),
      `archivist_worker`, `reporter_worker`, `resource_controller_worker`,
      `prioritizer_worker`. `model_health` is internally consistent and left
      unchanged. Tests: `tests/unit/test_utc_timestamps.py`.

### 15.4 Ops posture (operator action — not on the fix branch; confirmed again)

- [ ] **Free-only 8h unattended is not viable**: the `free-models-per-day`
      ceiling (~262K tokens ≈ 17 min here) plus the misconfigured opencode
      fallback leaves the remaining window as 120s no-alternative polling.
      Add a working second endpoint (paid/company) or shrink the window —
      otherwise the evolution-loop (§12.5) and §14 live runs will starve
      on free-tier alone.

---

## 16. Context protocol — reviewer feed + session projection

**Priority:** after §15, before burning §14 live tokens on background agents.
**No new deps.** Uses `file_summaries`, `symbol_index`, `agent_review_tracking`,
`agent_responses_archive`, `shell_trajectories`.
**Does not change the Class-1 mutation path.** Analysis stays Class-4 sacrifice.

Random full-file fan-out to `jr_reviewer` / `security_reviewer` wastes tokens and
wall clock and still fails "every line eventually." TUI agents (OpenCode,
Claude Code) stay capable after long sessions by changing the *projection*
sent to the model, not by stuffing or inventing a pseudo-language.

JSON cannot hold `//` comments. Document enums with `_comment*` keys
(`example_config.json`); `docs/CONFIGURATION.md` is the schema SSOT.

### 16.0 Config honesty (small, same branch as §15 is fine)

- [x] `example_config.json` `cli_mode`: add
      `_comment_mode`: `Accepted: semi_attended | unattended. Anything else
      falls back to semi_attended.`
- [x] `docs/CONFIGURATION.md` `cli_mode.mode`: delete `interactive`.
      There is no `CLIMode.INTERACTIVE` (`core/cli_modes.py`). The typed CLI
      is `semi_attended`.
      Test: `tests/unit/test_config.py::TestCliModeDocumentHonesty`.

### 16.1 Stop random-file review

Replace `background_agents.*.random_review` / `random_files_per_cycle` as the
default feed.

- [x] Reviewer prompt assembly: send the **map**, not bodies —
      path + 1–2 line `file_summaries.summary` + top symbols from
      `symbol_index`. Cap the map (e.g. 80 rows); never paste source here.
      (`core/review_feed.build_reviewer_map`, ≤80 rows; `_process_file` is
      map-first via `_build_reviewer_prompt`.)
- [x] Reviewer JSON grows two fields (fail-closed parse, same as today):

      ```json
      {
        "findings": [],
        "need_files": [{"path": "...", "start": 1, "end": 80, "why": "..."}],
        "covered": [{"path": "...", "start": 1, "end": 80, "hash": "..."}]
      }
      ```

      (`extract_need_files` / `extract_covered`; malformed entries dropped.)

- [x] Honor `need_files`: at most 2–3 slices, ≤200 lines each, served from
      the governed DB (`file_lines` / `project_files`). Charge tokens to the
      analysis budget, never the developer budget.
      (`serve_need_files` — `file_lines` JOIN `files`, bounded; one confirm
      pass per cycle.)
- [x] On `file_events` / materialize: feed **blast-radius** from
      `symbol_index` (changed path + callers/callees/tests, depth ≤2),
      not a random sibling. Skip binaries, logos, lockfiles, `docs/TODO.md`
      unless the seed named them. (`blast_radius_paths`; `_queue_modified_files`
      feeds roots + radius; `should_skip_review_path` junk filter.)
- [x] Default `random_review` off in `example_config.json`; keep the key
      for one release as an explicit override.
      Tests: `tests/unit/test_review_feed.py`. Schema: SCHEMA_VERSION 4→5
      (adds `review_coverage`).

### 16.2 Coverage ledger (long-horizon "every line")

`agent_review_tracking(agent_name, file_path, content_hash_reviewed,
last_reviewed_at)` is the ledger. Use it.

- [x] Sweep (lowest priority, paused during a developer session): pick the
      next *uncovered* chunk — hash miss, then never-seen, then high fan-in.
      Not random. (`coverage_sweep_next` + `_sweep_loop`, paused while
      `foreground_session_active()`.)
- [x] Chunk ~80–120 source lines, one agent, one receipt. Mark covered only
      if `content_hash` still matches; a later write invalidates that chunk
      only. (`_covered_intervals` gates on current hash; receipts persist on
      `review_coverage`.)
- [x] Refuse "no findings" when `covered` is empty (Qwen-style receipt).
      Persist receipts on `agent_review_tracking` (add `lines_lo` / `lines_hi`
      only if a column is required; otherwise encode the range in an existing
      field or a small `review_coverage` table and bump `SCHEMA_VERSION`).
      (`_is_hollow_receipt` refused in `_process_file` and
      `_process_sweep_chunk`; `review_coverage` table, SCHEMA_VERSION 5.)
- [x] Operator diagnostic: `query_developer_responses.py` or
      `diagnose_soak.sh` section — `% lines covered` per agent, oldest
      uncovered path. No new CLI surface required for v1.
      (`coverage_diagnostic` / `format_coverage_diagnostic`; new QUERY 34 in
      `diagnose_soak.sh`.)
      Tests: `tests/unit/test_review_feed.py::TestCoverageSweepLedger`.

### 16.3 Session projection (OpenCode / Claude pattern)

Do **not** LLM-summarize a live developer session unless the model window
is actually near the reserve. Prefer prune + DB rehydrate.

- [x] **Prune payloads, keep structure** in shell-developer prompt assembly
      (`workflow/shell_developer.py`, folds §13.4): step table is
      id + one-line result; full stdout only for the last 1–2 commands
      (`max_output_chars` already caps a single result). Older `cat`/`grep`
      dumps become stubs (`[stdout omitted, hash=…]`).
      (`core/session_projection.project_step_table` — every row keeps
      `step`/`command`/`exit_code` + a `result` one-liner + a sha256 digest
      stub; `build_chat_prompt` and `_observation` project the table.)
- [x] **Hot tail:** last 2–3 turns verbatim. Everything earlier is eligible
      for stubbing. (`HOT_TAIL_TURNS=3`; `prune_messages` degrades only
      oversized old observations, never the system/launch prompts or the tail.)
- [x] **Rehydrate every call from disk/DB**, never from a compact blob:
      system prompt, tool/protocol instructions, task row, target path,
      workspace evidence listing. Tool schemas / bash protocol must not
      live only inside a summary.
      (System prompt + launch prompt are always re-sent verbatim; the compact
      checkpoint is re-read from `archived_context`, and the fallback brief is
      rebuilt from the task row.)
- [x] **If** a window emergency compact is required: tool-less one-shot
      summarizer (no `call_agent("developer")`), structured brief
      (goal, files, decisions, blockers, next command), store on
      `archived_context` / trajectory header; keep the hot tail; do not
      stack summaries — update one anchored checkpoint.
      (`_summarize_session` — raw `call_endpoint` single-user call, JSON brief
      or structural fallback; `upsert_context_checkpoint` anchors ONE row per
      task; `rebuild_messages_after_compact` = system + checkpoint + launch +
      hot tail.)
- [x] Reserve compact budget: trigger before 100% of
      `max_context_tokens` (mirror OpenCode `buffer` / Claude ~16% reserve)
      so the summarizer itself can run.
      (`maybe_compact_session` / `would_exceed_reserve`, `COMPACT_RESERVE_RATIO
      =0.16`, wired into the run loop before every `_llm()` call.)
- [x] Next orchestrator task starts from DB state (`tasks`, open feedback,
      last proposal), not from a compacted chat. That is `/clear` + plan,
      not `/compact`.
      (Already true at the harness: tasks/orchestrator context come from the
      governed DB. The trajectory/session transcript is an archive view, not
      the task source of truth.)
      Tests: `tests/unit/test_session_projection.py` (prune, hot tail,
      reserve/compact, one-row checkpoint, no-replay exit proxy on a real
      worktree chat session).

### 16.4 Out of scope

- Invented high-density "LLM-only" encodings or serialized ASTs as the
  security/correctness corpus. Skeleton/map is the first pass; raw lines
  are the second. `security_reviewer` always sees source slices.
- Compacting `agent_responses_archive` or deleting soak trajectories.
  Compact is a *view* for the next prompt; disk stays full.
- Promoting reviewers onto the mutation path, or letting `need_files`
  become unbounded tool spam.
- New runtime dependencies (`terminal-bench`, vector DBs, extra parsers).
  Tree-sitter is not required; `symbol_index` + `file_summaries` are enough
  for v1.

### 16.5 Exit criteria

| Slice | Done when |
|---|---|
| §16.0 | `example_config.json` + `CONFIGURATION.md` match `CLIMode` |
| §16.1 | A reviewer cycle with `random_review` off produces findings or `need_files` from the map; no random full-file attach in stdout |
| §16.2 | An 8h soak leaves a coverage % that increases monotonically while hashes are stable; mutation still not blocked |
| §16.3 | A 30-step shell session does not re-send turn-1 `ls` stdout on turn-30; protocol instructions still present after any compact |

### 16.5 Implementation sequence (insert into the table at the bottom)

After row 1 (§15), before §14.2:

| Order | Work item | Exit criterion |
|---:|---|---|
| 1b | §16.0 + §16.1 map/`need_files` | Random review off; map + bounded pulls |
| 1c | §16.2 coverage receipts | Ledger + diagnostic % |
| 8b | §16.3 prune/hot-tail (pairs with §13.4) | No payload-replay across 30 steps |

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

```markdown
## 18. Soak16 / w-10 — apply quality only (rest already shipped)

**Priority:** next on the working branch. §12–§17 are **done**; do not
re-implement stall-on-sed, empty-body latch, reviewer map, inspect
prompt-diet, CLI bench, or evolve/rollback here.
**This section implements only what Soak16 still showed after those
controls:** same-hunk re-apply, and truncated full_replace retried as
“send the whole file again.”
**Evidence branch (read-only, never merge):** `origin/soak/w-10`

```bash
git fetch origin soak/w-10
git rev-parse --abbrev-ref HEAD          # must NOT be soak/w-10
git show origin/soak/w-10:docs/soak-artifacts/01_funnel.txt
git show origin/soak/w-10:docs/soak-artifacts/02_proposals.txt
git show origin/soak/w-10:docs/soak-artifacts/03_reviewer_heads.txt
git show origin/soak/w-10:docs/soak-artifacts/04_developer_protocol.txt
git show origin/soak/w-10:docs/soak-artifacts/05_command_buckets.txt
git show origin/soak/w-10:docs/soak-artifacts/07_tasks.txt
git show origin/soak/w-10:docs/soak-artifacts/27_proposals.txt
git show origin/soak/w-10:docs/soak-artifacts/28_write_log.txt
```

Optional (wins vs stalls; do not copy JSON into this repo):

```bash
git ls-tree -r --name-only origin/soak/w-10 | grep -E 'trajectory|turn14|turn15|turn17'
```

Facts from those files (do not re-litigate):

- Funnel: 11 proposals, 8 applied, 8 writes, 3 REJECT (gate correct).
- Useful unique edit: `1bebd852` `workflow/task_runner.py` empty-backlog
  `_finalize_task` + return.
- Later applies on the same hunk: comments / feedback IDs 32 and 54.
- REJECT `4ccc4cd3`: find == replace (already on disk).
- REJECT `7d5751a3` / `0beabd1e`: truncated `core/model_health.py`;
  retry asked for the complete file and truncated again.
- Task closed `token budget exhausted: files_modified=8`.
- `04`: 155 valid bash; 27 rows avg prompt ~93k (legacy guid fallback).
- `05`: 2 evidence / 60 inspect / 93 other.
- Shorter-than-disk is a **valid purge**. Do not treat line-count drop
  as truncation.

### 18.1 Implement — same-hunk dedupe (missing)

§16/§17 do not stop a second governed proposal on an identical span.

- [ ] Dedupe key: `(target_path, hash of normalized find/old text)`.
      Second proposal in the same task with the same key → do not open
      a developer session; treat as `no_change_required` for that item.
- [ ] When an `applied` write matches the **seed path** and contains
      the required call (`_finalize_task` + `return progress`), mark
      that seed feedback addressed. Orchestrator must not dispatch
      developer again for IDs 32/54 on those lines.
- [ ] Comment-only or find==replace deltas do not increment
      `files_modified` for finish-gate / “seed still open.” Reviewer
      already rejects no-ops (`4ccc4cd3`); apply accounting must agree.

Files: proposal intake + `workflow/task_runner.py` dispatch. Unit test
with fixtures named after `1bebd852` then `9e48a67d` (second session
must not run).

### 18.2 Implement — recover truncated replace (missing)

§13 already forbids full_replace/guid on files ≥180 lines for the
*first* attempt. Prefer find_replace / structured `edit` (how
`1bebd852` landed). When a payload is still cut, **resume-and-stitch**.
Do not REJECT-and-reprompt “complete untruncated file.”

**Truncated** (size vs disk is not a signal):

```text
truncated := finish_reason == length
          or ast.parse failed
          or unterminated literal / block at EOF
          or last line is a mid-statement cut (e.g. `age_min =` with no RHS)
```

`finish_reason == stop` **and** `ast.parse` succeeds → payload is
complete. Fewer lines than disk is allowed (intentional purge). Send
to reviewer. Reviewer may still REJECT “deleted half the module with
no rationale” (`7d5751a3` style) — that is review, not stitch.

**Order:**

1. Persist the partial on the proposal. Do not send a half-file to
   reviewer.
2. Resume-and-stitch, same model, ≤2 continuations. Prompt feeds the
   last ~30 lines of the partial; model emits **only** the remainder
   (no recap, no second JSON wrapper). Stitch, strip suffix/prefix
   overlap if the model repeats the tail. Re-run the truncated check.
3. If still truncated: one `find_replace` of the broken span ±20 lines.
   Never a second whole-module full_replace/guid.
4. If that fails: mark that feedback stuck.

Optional warning only (not an apply block): top-level names that
vanished and are not named in the rationale → surface to reviewer.

Unit tests:

- [ ] Cut mid-function + valid remainder → continuation prompt contains
      the tail, not “send the complete file”; stitch + `ast.parse` OK.
- [ ] Remainder repeats the tail → overlap stripped.
- [ ] `stop` + parse OK + file shorter than disk (deleted a dead
      function) → **not** truncated, **not** continued, goes to reviewer.
- [ ] Stitch still truncated → hunk retry only; no whole-file replace.
- [ ] Second hunk failure → stuck.

### 18.3 Validate only — do not implement

Already owned by §13.4 (prompt assembly / inspect cap) and §17
(unique `sed` ≠ `NoProgress`). Check they hold.

- [ ] After evidence + `sed` of the seed path, a 10-step inspect-only
      chain must not be the product outcome (§13.4 cap or forced
      `edit`/`finish`). Distinct `sed` ranges must still not exit
      `NoProgress` (§17).
- [ ] `04_developer_protocol` 93k-char guid rows must not recur on a
      ≥180-line target during latch or truncation recovery (assert on
      the existing prompt builder).
- [ ] Feeder stays §16. Soak check only: unaddressed ≥ 10 remains paused.

If 18.3 fails, file a bug against §13.4 / §17 — do not add a third
inspect counter here.

### 18.4 Out of scope

- Merging `soak/w-10`. Copying trajectory JSON or
  `docs/soak-artifacts` onto the working branch.
- Re-porting mini-swe, reviewer maps, CLI bench, evolve/rollback,
  empty-body `NoneType`, 300s 503 sleeps, `beta_genai`.
- Counting 8 `file_write_log` rows as 8 product fixes.
- Treating fewer lines than disk as automatic truncation.

### 18.5 Acceptance

On the working branch, after 18.1–18.2 tests green:

1. Replay `git show origin/soak/w-10:docs/soak-artifacts/02_proposals.txt`
   as fixtures: first apply addresses seed; second identical span does
   not start a developer session.
2. Truncation fixture → resume-and-stitch (or hunk), never
   “complete untruncated file.”
3. Purge fixture → shorter file + `stop` + parse OK is eligible to
   apply/review.
4. Optional 2h soak (Gemini-only, new seed or empty if finalize is
   already on `main`): unique `(path, span)` applied ≥ 1; no ID 32/54
   comment churn; 18.3 checks pass or bugs filed on §13.4/§17.
```

## Implementation sequence (open work only)

| Order | Work item | Exit criterion |
|---:|---|---|
| 1 | §15 Soak24 findings (branch `fix/soak24-findings`) | A1–A4 `cli/commands.py` fixes + §15.3 all 5 (incl. UTC normalization) + tests; full suite green on `main` |
| 1b | §16.0 + §16.1 map/`need_files` | Random review off; map + bounded pulls |
| 1c | §16.2 coverage receipts | Ledger + diagnostic % |
| 3 | §14.2 manifest v2 + repo fixture | 5 terminal tasks parse; `contract_hash` folds new fields |
| 4 | §14.3 command verifier (folds §13.5 bench cross-check) | Exit-0/exit-1 graded; honest with the §13.5 evidence gate |
| 5 | §14.4 driver wiring | Terminal task end-to-end on mocked LLM; hermetic |
| 6 | §14.5 tasks_terminal.json + tests | Full suite green on `main` |
| 7 | §14.6 live-run gate (mock → live; folds §13.7 `--live`) | Comparable pass@1; §12.5 consumes verdicts → unblocks §12.4 |
| 8 | §12.4 safety + §12.8 enablement | Revert bound to tagged SHA; include-path contained; applied=success only; then (and only then) a live evolve round-trip |
| 8b | §16.3 prune/hot-tail (pairs with §13.4) | No payload-replay across 30 steps |
| 9 | §13.3 / §13.4 / §13.8 (independent P1 hardening) | Strict diff, token-efficient prompts, test seams — interleaved with §14 as capacity allows |
| 10 | §12.6 attribution ablations | A single-component swap changes measured pass@1 |
| 11 | §14.7 TB translation seam (gated) | Board gate opens §12.7 out-of-scope; TB tasks translate or fail loudly |