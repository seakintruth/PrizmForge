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
| **§16 Reviewer context protocol** | **download now → next (after §15)** | Stop feeding background reviewers random file dumps; split navigate / cover / edit. Must land before §14.6 spends live tokens on background agents. MVP + blast-radius + coverage sweep |
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

- [ ] Bind revert to the SHA `materialize_proposal` tagged (`[iter-<t>]`),
      not `git rev-parse HEAD`. Missing SHA → `undo_proposal`, never guess.
- [ ] `revert_candidates`: revert only when `confirms == 0` AND
      `predicted_regressions ∩ landed`. Drop iteration-global
      `regressions_outnumber` (one unrelated flip reverts every zero-confirm
      edit).
- [ ] Delete the unused `json_each` `flagged_rows` query in `harness/evolve.py`.

### 12.8 Evolve enablement gate (before `evolve.enabled=true`)

- [ ] `{{include:}}` resolves under `system_prompt/` (`Path.resolve` +
      `relative_to`); reject `../`.
- [ ] Count `applied` only on materialize `status == "success"` — not
      `lint_failed` / `git_failed`.
- [ ] Validate **every op path** in the proposal, not only
      `target_file_path` on the propose dict.
- [ ] Debugger/Evolve `--max-workers 1` on company keys until TokenPacer
      is locked.

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

The bench-path cross-check item below lands with **§14.3** (command
verifier); the disk + `mode: "new"` items stay independent.

- [ ] `harness/verify.py` reads governed DB only; check the on-disk file
      under the bench project dir (DB as fallback), recording which source
      satisfied.
- [ ] Add `mode: "new"` (absent in fixture, present after) so a `contains`
      fragment that was already true pre-task cannot pass.
- [ ] For the bench path, cross-check `status passed` against evidence
      (`edit.materialized` + `file_write_log` success) instead of trusting
      the runner's own label.

### 13.7 Live/control runs (P2)

Lands via **§14.6** (`--live` runs consume this); exercised there.

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
- (**likely false positive — do not reopen without evidence; not a fix
  item**) `resource_controller.json` "UUID metadata brackets" finding: the
  file is valid JSON with documented `_note` keys; the reviewer conflated DB
  schema-line format with this JSON (§9.5 posture).

### 15.3 Observability / data-hygiene nits (all five on the fix branch, incl. UTC normalization)

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

### 15.4 Ops posture (operator action — not on the fix branch; confirmed again)

- [ ] **Free-only 8h unattended is not viable**: the `free-models-per-day`
      ceiling (~262K tokens ≈ 17 min here) plus the misconfigured opencode
      fallback leaves the remaining window as 120s no-alternative polling.
      Add a working second endpoint (paid/company) or shrink the window —
      otherwise the evolution-loop (§12.5) and §14 live runs will starve
      on free-tier alone.

---

## 16. Reviewer context protocol — navigate / cover / edit (2026-09-12)

Diagnosis: "pick N random files and dump them at `jr_reviewer`" collapses
three separate jobs — **navigate**, **cover**, **edit** — into a passive
random sampler. Best-of-breed long-horizon systems split them. After
Soak24 we already hold the ledger: `agent_review_tracking(agent, path,
content_hash, last_reviewed_at)` — use it, don't reinvent it. Class-1
mutation stays untouched; this changes only how Class-3 is *fed*.

### 16.1 Design principles

1. **Context is a tool, not a buffet.** Window = RAM, repo/DB = disk.
   Stable task card + condensed map first, then *pull* slices. "Here are 8
   random files" burns tokens and trains the model to hallucinate files it
   never saw.
2. **Two review modes, never one random sampler.**
   - **Delta / blast-radius** (materialize / file event): changed file +
     callers/callees/tests from the symbol graph — cheap, high-signal,
     every mutation.
   - **Coverage sweep** (long unattended clock): next *uncovered* chunk
     from the ledger — every line eventually.
3. **Skeleton first, source on request.** Tree-sitter / CST skeletons
   (signatures, imports, class layout, no bodies) cut 80–90% of tokens and
   still let the model ask for the right file. We already store
   `file_summaries` + `core/symbol_index.py`: emit 1–2 line summaries +
   symbol names; never paste bodies until the reviewer returns
   `need_files: [...]`.
4. **Graph beats grep** for "what else must I read." Blast-radius from the
   symbol index, not "also send `cli/__init__.py`." No new package — walk
   what we already index.
5. **Coverage is a receipt, not a vibe.** Chunk the *source* (not the
   diff): one accountable reader per chunk, and refuse "no findings"
   unless every chunk returned a `Covered:` receipt — that is how an 8h
   soak gets "every line eventually" without stuffing the repo into one
   prompt.
6. **No LLM-native gibberish for jr/security.** Compressed encodings /
   serialized ASTs are fine for navigation and summarization only; they
   drop literals, magic numbers, auth strings, off-by-ones — exactly what
   `security_reviewer` exists to catch. First pass = skeleton, second pass
   = raw lines, no third invented dialect.
7. **Persistent notes beat transcript stuffing.** Findings to
   `agent_feedback` (already) + a per-soak `coverage.jsonl`; never re-paste
   the previous hour's reviewer prose into the next call.

### 16.2 Concrete shape (Class-3 feeding only)

```text
init / file event
  → symbol index + 1–2 line file_summaries (already exist)
  → coverage ledger: (agent, path, hash, lines_lo, lines_hi, status)

delta path (on materialize / file_events)
  → blast-radius(path, depth=2) from symbol_index
  → reviewer gets: map row + changed hunk + neighbor signatures
  → optional tool: request_file(path, start, end)  # bounded

sweep path (background, lowest priority)
  → pick next uncovered chunk: oldest hash miss, then never-seen,
    then files with fan-in (not random)
  → chunk size ~80–120 lines, one agent, one receipt
  → mark covered only if hash still matches
  → if file changed under them, invalidate that chunk only
```

- [ ] Reviewer JSON grows two fields: `need_files` (capped 2–3 slices,
      ≤200 lines each) + `covered` (path/start/end/hash receipts).
- [ ] `need_files` is served from the governed DB, not a second LLM call
      with the whole file; charged to the analysis budget, **never** the
      developer budget.
- [ ] **Do not:** send `docs/TODO.md` / logos to `jr_reviewer`; invent a
      repo-wide pseudo-language as the security corpus; "review the whole
      tree" in one orchestrator prompt; let `need_files` grow into
      unbounded tool spam.

### 16.3 Order of work

- [ ] **MVP (first commit, post-§15):** stop the random file pick → emit
      the existing summary index into the reviewer prompt → honor
      `need_files` + `covered` receipts against `agent_review_tracking`.
- [ ] **Second commit:** delta / blast-radius (depth=2) + chunk coverage
      sweep with receipts and per-chunk hash invalidation.
- [ ] **Before §14.6 live tokens:** must be green before background agents
      ($12.5 Evolve consumes verdicts) spend live tokens — 250 source
      files × ~4 chunks ≈ 1k receipts is a scheduling problem, not a
      context problem; random sampling is the only mode without a receipt.

### 16.4 Token / wall-clock note

Random full files = O(files × reviewers × turns), and you pay again every
turn the text stays in history ("context tax"). Map + request = one cheap
map prompt + sparse pulls; background reviewers stay Class-4 and yield the
instant a developer session starts (backlog pause already exists).

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
| 1 | §15 Soak24 findings (branch `fix/soak24-findings`) | A1–A4 `cli/commands.py` fixes + §15.3 all 5 (incl. UTC normalization) + tests; full suite green on `main` |
| 2 | §16 Reviewer context protocol | Random file dump removed; map-first prompts; `need_files` + `covered` honored against `agent_review_tracking`; §14.6 live tokens only after green |
| 3 | §14.2 manifest v2 + repo fixture | 5 terminal tasks parse; `contract_hash` folds new fields |
| 4 | §14.3 command verifier (folds §13.5 bench cross-check) | Exit-0/exit-1 graded; honest with the §13.5 evidence gate |
| 5 | §14.4 driver wiring | Terminal task end-to-end on mocked LLM; hermetic |
| 6 | §14.5 tasks_terminal.json + tests | Full suite green on `main` |
| 7 | §14.6 live-run gate (mock → live; folds §13.7 `--live`) | Comparable pass@1; §12.5 consumes verdicts → unblocks §12.4 |
| 8 | §12.4 safety + §12.8 enablement | Revert bound to tagged SHA; include-path contained; applied=success only; then (and only then) a live evolve round-trip |
| 9 | §13.3 / §13.4 / §13.8 (independent P1 hardening) | Strict diff, token-efficient prompts, test seams — interleaved with §14 as capacity allows |
| 10 | §12.6 attribution ablations | A single-component swap changes measured pass@1 |
| 11 | §14.7 TB translation seam (gated) | Board gate opens §12.7 out-of-scope; TB tasks translate or fail loudly |