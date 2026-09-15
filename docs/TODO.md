# PrizmForge Roadmap / TODO

This file lists **only work that still needs to be accomplished**.

Completed work is **not repeated here**. Implementation, PR numbers, soak
post-mortems, and acceptance evidence live in **git history** (`git log`,
merged PRs #108–#128) and `docs/UNATTENDED_CLOSED_LOOP_CAPABILITIES.md`.
Do not paste shipped checklists back into this tracker.

**Last updated:** 2026-09-14

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
| **§14.6 live-run gate** | **next** | §14.1–§14.5 + §13.7 shipped on `main`; the last open §14 item is a real `--live` endpoint run on the crafted terminal set (needs working endpoints) |
| **§12.6 attribution** | **after §14.6** | `harness/attribution.py` scaffolded (branch); exercise a live single-component swap once the loop round-trips |
| §15.4 ops posture | **operator** | Code half (latch-aware no-alternate sleep) shipped; operator must add a paid/company endpoint or shorten the unattended window |
| §13 Edit-process hardening | **P1** | Atomic apply, crash recovery, bench isolation, verifier honesty, diff strictness, and token-efficiency shipped; §13.7 seam shipped, exercise = §14.6 |
| §12 Harness-evolution loop | **P2** | Backbone shipped **dark** (#128, `evolve.enabled` false); rollback *code* exists; rollback *safety* + live round-trip wait on §14.6 |
| §7 Closed-loop / mini-swe | **MEDIUM** | Unblocked by live endpoints/hooks, not code |
| Soak-era backlog (§1, §2.3, §3, §6) | **watch** | Lower priority; paid only if the next live soak shows them |
| §9 Annexes | **LOW / parked** | Do not start without new evidence |

---

## 0. Current state & next focus

- **Merged on `main` (#128, #131, #133, #134):** §13.1 / §13.2 / §13.6,
  §12.4–§12.5 (Evolve stays **off**; `SCHEMA_VERSION = 4`), §15.2 + §15.3,
  §16.0–§16.3, and **§14.1–§14.5 + §13.7** (terminal-class bench:
  manifest v2 + repo fixtures, command verifier, driver wiring, the 5
  crafted terminal tasks, and `--live` endpoint/model injection).
  Do not point `project_directory` at the main working clone if you flip
  `evolve.enabled`.
- **Next (do):** **§14.6 live-run gate** — mock/deterministic runs are
  green on the terminal set; run real `--live` trials (deterministic
  ordering, iteration-labeled results) to complete §13.7 and let §12.5
  consume terminal verdicts. Then §12.6 attribution (`harness/attribution.py`
  scaffolded; exercise it on a live swap). §14.7 stays gated on Board
  approval.
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

**Shipped on soak/25 → `main` (#133/#134, not repeated):** §14.1–§14.5.
`harness/benchmark/tasks.py` schema v2 (`kind`, `repo {url, commit}`,
`setup`, `verifier {command, timeout}` all folded into `contract_hash`),
`harness/benchmark/repo_fixture.py` (mirror clone at a pinned commit +
`ingest_tree_to_governed` under the 512 KB / 200-file caps), `harness/verify.py`
command mode (exit 0 = pass, evidence-gate first, injectable runner),
`harness/benchmark/driver.py` wiring (per-task clone/setup, `max_turns` /
`timeout_s`, `developer.implementation="shell"` + `strict task_scope` for
terminal tasks), the 5 crafted tasks in `tasks_terminal.json` (copy-mutable
fixtures, each naming a real target, deterministic verifiers), and §13.7
`--live` injection (`--endpoints-json` / `--model`). Tests:
`test_benchmark_tasks_v2.py`, `test_harness_verify.py::TestCommandVerifier`,
`test_benchmark_terminal_driver.py::TestTerminalDriverE2E`,
`test_benchmark_driver.py::TestLiveAndDryRun`.

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

### 14.2 Phase 1 — manifest v2 + repo fixtures

### 14.3 Phase 2 — command verifier

### 14.4 Phase 3 — driver wiring

### 14.5 Phase 4 — terminal task set + tests

### 14.6 Phase 5 — live-run gate

- [ ] Mock/deterministic runs are green on the terminal set (terminal E2E +
      verifier tests). Run `--live` endpoint runs on the crafted tasks
      (deterministic ordering, iteration-labeled results) for a comparable
      pass@1 — completes §13.7.
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
| §14.2 manifest v2 | 5 terminal tasks parse; `contract_hash` folds `repo`/`setup`/`verifier` — **satisfied** |
| §14.3 command verifier | Command mode passes/fails on exit code; honest with the evidence gate — **satisfied** |
| §14.4 driver wiring | Terminal tasks run end-to-end on the mocked LLM; hermetic — **satisfied** |
| §14.5 tasks + tests | `tasks_terminal.json` + tests green; full suite on `main` — **satisfied** |
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

### 12.8 Evolve enablement gate (before `evolve.enabled=true`)

### 12.6 P3 attribution (after a working loop)

- [x] Single-component swap harness (`+ memory` / `+ tool` / `+ middleware` /
      `+ system_prompt`) measuring pass@1 deltas against a baseline
      (branch). — `harness/attribution.py` `run_attribution`: baseline at
      `iteration`, each swap at `iteration + rank` with its labelled config
      overlay threaded via `run_benchmark(config_overrides=...)`;
      per-variant `pass@1` / `delta` / task passes + harness fingerprint
      (tag + prompt hash) written to `harness/attribution/attribution-<n>.json`.
      Tests: `tests/unit/test_attribution.py`. Exercise on a live swap once
      the loop round-trips.
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

### 13.4 Efficiency — token cost per edit (P1)

### 13.5 Verifier honesty — disk + pre/post (P2)

The bench-path cross-check item below lands with **§14.3** (command
verifier); the disk + `mode: "new"` items stay independent.

### 13.7 Live/control runs (P2)

Lands via **§14.6** (`--live` runs consume this); exercised there.

The `--live` injection itself shipped on soak/25 → `main` (not repeated):
`use_bench_config(endpoints=, model=)`, `__main__.py --endpoints-json` /
`--model`, results carry `endpoint` / `model` / iteration-labeled rows, and
`python -m harness.benchmark --dry-run` validates the manifest + isolated DB
without LLM calls. What remains open is the **live exercise** (§14.6), not
the seam.

### 13.8 Test seams for the pipeline (P1)

---

## 15. Soak24 — first clean mutation + soak-DB code findings (2026-09-12)

Soak24 evidence: `/home/jeremy-gerdes/git/github/PrizmForge-Soak/Soak24-target/
PrizmForge/.PrizmForge/agents.db` (read `mode=ro`; sqlite3 absent — use
`.venv/bin/python` + stdlib sqlite3), `shell_trajectories/`, `reports/`, and
the target `git status`/`git diff`. Fix branch (next, off `soak/23`):
`fix/soak24-findings`. Tick boxes `(branch)` as each lands; purge this
section after that branch merges.

### 15.1 Outcome (verifiable, keep as evidence until purge)

### 15.2 Confirmed code findings from the soak DB (branch `fix/soak24-findings`)

- (**likely false positive — do not reopen without evidence; not a fix
  item**) `resource_controller.json` "UUID metadata brackets" finding: the
  file is valid JSON with documented `_note` keys; the reviewer conflated DB
  schema-line format with this JSON (§9.5 posture).

### 15.3 Observability / data-hygiene nits (all five on the fix branch, incl. UTC normalization)

### 15.4 Ops posture (operator action — confirmed again)

- [ ] **Free-only 8h unattended is not viable**: the `free-models-per-day`
      ceiling (~262K tokens ≈ 17 min here) plus the misconfigured opencode
      fallback leaves the remaining window as idle no-alternative polling.
      **Code half shipped (branch):** the no-alternate sleep is now
      latch-aware — it sleeps across the real `unavailable_until` remaining
      time instead of re-polling every 120s, capped by the new
      `fallback_settings.no_alternate_max_sleep_seconds` (default 600, floor
      30) so a long quota park no longer burns the whole window as polls
      (`agents/base.py` `_bounded_no_alternate_sleep`; tests in
      `test_recursive_fallback.py`; documented in `docs/CONFIGURATION.md` /
      `example_config.json`). **Operator half still open:** add a working
      second endpoint (paid/company) or shorten the unattended
      `max_duration_hours` — otherwise the evolution-loop (§12.5) and §14
      live runs will starve on free-tier alone.

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

### 16.1 Stop random-file review

Replace `background_agents.*.random_review` / `random_files_per_cycle` as the
default feed.

### 16.2 Coverage ledger (long-horizon "every line")

`agent_review_tracking(agent_name, file_path, content_hash_reviewed,
last_reviewed_at)` is the ledger. Use it.

### 16.3 Session projection (OpenCode / Claude pattern)

Do **not** LLM-summarize a live developer session unless the model window
is actually near the reserve. Prefer prune + DB rehydrate.

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

### 16.5 Implementation sequence

Sections §16.0–§16.3 shipped on soak/25 → `main` (rows 1b/1c/8b of the old
sequence table); no open sequence rows remain for §16.

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
| 1 | §14.6 live-run gate (mock → live; folds §13.7 `--live`) | Comparable pass@1 on the crafted terminal set; §12.5 consumes verdicts → unblocks §12.4 |
| 2 | §12.6 attribution exercise (harness/attribution.py scaffolded) | A single-component swap changes measured pass@1; `H_best <- H_t` tracked |
| 3 | §15.4 operator half — add a paid/company endpoint or shorten `cli_mode.unattended.max_duration_hours` | Unattended window does real work; no long idle no-alternate polling |
| 4 | §14.7 TB translation seam (gated) | Board gate opens §12.7 out-of-scope; TB tasks translate or fail loudly |