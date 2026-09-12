# PrizmForge Roadmap / TODO

This file lists **only work that still needs to be accomplished**.

Completed work is **not repeated here**. Implementation, PR numbers, soak
post-mortems, and acceptance evidence live in **git history**
(`git log`, merged PRs #108–#124, and
`docs/UNATTENDED_CLOSED_LOOP_CAPABILITIES.md`). Do not paste shipped
checklists back into this tracker.

**Last updated:** 2026-09-11

## How to use this file

- Tick a box when the change lands as a commit on the working branch
  (`feat/roadmap-soak17`) and mark it `(branch)`; delete the item on the
  pass after that branch merges to `main` (no `[x]` museums there).
- Detailed *design* for an open item stays in this file until it ships.
- Do not merge `soak/doc-run-a-1` or `soak/4-tmp-reporting`
  (trajectories + docs only).

## Section priorities

| Section | Priority | Why |
|---|---|---|
| §0 Current state | — | Index |
| §11 Soak17 root-cause fixes | **shipped (branch)** | §11.1–§11.3 landed (`a2cc0d2`/`6abe86e`/`7ed6a15`) + Soak22 notes (§11.4) on `feat/roadmap-soak17`; merge to `main`, then purge |
| **§12 Harness-evolution loop (`HARNESS_EVOLUTION_DESIGN`)** | **P2** | Zero-dep closed loop; P0+P1 (§12.1–§12.3) shipped on branch; §12.4/§12.5 next. External benchmarks out of scope |
| §13 Edit-process hardening | **P1** | Atomic apply, materialize crash recovery, and bench trial isolation are mutation-path + bench correctness; same tier as the remaining P1 work |
| §10 Mutation path | shipped #121–#124 | Proposal path + Soak16/Soak6 fixes soak-validated to materialization (Soak8); only §10.7 gate remains |
| §6 Next-soak 429 dump | **P0** | Partly paid by the Soak5 artifact; `Work: 0.0s` still open |
| §8 Operator soak A-1 | **ran** | Soak4 ran after #121; remaining gate is §10.7 / §11 |
| §5 Optional SQL hygiene | **P2** | Identifier quoting + comment-aware DDL split |
| §3 Seed-path / scope | **watch** | Next soak with background agents on |
| §2.3 Protocol nits | **watch** | Only if the next soak shows them |
| §1 NUC `cmd_init` timing | **P1 operator** | Code shipped in #121; still time on the box |
| §7 Closed-loop / mini-swe | **MEDIUM** | Unblocked by #121; needs live hooks / endpoints |
| §9 Annexes | **LOW** | WAL-as-default, Postgres, federation |

---

## 0. Current state & next focus

- **`main` already has (PRs #121–#124):** recursive `seen_endpoints`,
  latch-only `is_available()`, per-endpoint 4h + daily `TokenBudget`,
  fail-closed workspace evidence, zero-command seed latch, task status
  vocabulary, demotion exclusions, `Retry-After` on `rate_limited`
  events, cold `cmd_init` one-writer ingest (#121); chat-JSON-table
  protocol + Enterprise-chat developer driving, in-worktree edit
  primitive, command/change-state observations, stall tripwire,
  task-fiability pre-flight, `edit_payload` fallback gating (#122);
  `diagnose_soak.sh` automation + shell step-count bump (#123); Soak6
  mutation policy (#124) — bounded promo (`FULL_REPLACE_MAX_LINES`,
  `SHELL_PROMOTE_MAX_DIFF_LINES`), `LimitsExceeded` never promotes an
  unbounded diff, inspect/mutate step-budget split (`INSPECT_STEP_CAP`),
  banned base64/python write-exec (exit 78), utf-8 `errors="replace"`
  decode, `full_replace` fallback cap on oversized targets, retryable
  (truncation/syntax) REJECT → retry-the-same-file instead of stall.
  Do not re-implement those.
- **Soak artifacts (review only):** `docs/soak_artifacts/`
  (`stdout.txt`, `model_dashboard.txt`, `soak-target-.prizmforge/`).
  The Soak5 run validated the #122/#123 fixes in a live soak; Soak17
  aborted on a **phantom seed** with 0 model calls — that is §11.
  **Soak8** (`origin/self-edit/soak8`, `docs/soak-artifacts/`, do not
  merge): mutation path ran end-to-end to materialization — 6 proposals,
  3 applied, exit-78 banned-write fired, no `RepeatedFormatError`, no
  "produced no file changes"; both tasks ended on `token budget
  exhausted` (`files_modified=2` / `1`). See `02_proposals.txt`,
  `20_diagnostic.txt`, `05_command_buckets.txt`.
- **Working branch `feat/roadmap-soak17` (not on `main` yet):** §11.1–§11.3
  (`a2cc0d2`/`6abe86e`/`7ed6a15`), Soak22 console + rollout-finalize fixes
  (`593b69d`/`b20c814`, §11.4), §12.1 substrate (`4ca8338`), §12.2 benchmark
  (`8bcaf14`), and §12.3 corpus + §11.5 honest schema gate (`ca68d62`) are
  ticked here against the branch. They are purged from this tracker after
  the merge.
- **Next (do):** start §13.1/§13.2/§13.6 (edit-process hardening — atomic
  apply, materialize crash recovery, bench trial isolation), then §12.4
  (decision manifest) → §12.5 (Evolve gate) first iteration. Re-run the
  §10.7 acceptance gate on the §11-verified endpoints at the next live
  soak; the §11 closure is already committed.
- **Harness-evolution substrate (§12):** P0 observability base landed
  (operator console: `core/operator_view.py`, shell heartbeats,
  `utils/live_console.py`, run-effectiveness views). §12.1 fingerprint +
  infra-abort classifier, §12.2 boxed benchmark, and §12.3 trajectory
  corpus are shipped on `feat/roadmap-soak17`; §12.4/§12.5 remain.
- **Company endpoints** still need a **manual unlock ~every 8 hours**
  and **must keep falling back** when one key locks.
- **Trajectories (do not merge):** `soak/doc-run-a-1` /
  `docs/soak-a-1-shell-trajectories/`; `soak/4-tmp-reporting` /
  `docs/soak-a-4-example-tmp/`; `self-edit/soak8` /
  `docs/soak-artifacts/`.

---

## 10. Soak4 → Soak17 — mutation path (shipped; gate open)

**Priority:** shipped (PRs #121–#124). Only the §10.7 acceptance gate
is open, exercised by Soak17 (§11). Soak4–Soak16 post-mortem detail
(§10.0–§10.5) is in git history — do not re-paste it here.
**Soak8 update:** the mutation path reached **materialization** —
proposals created, approved, and applied (`workflow/__init__.py`),
banned base64 write rejected at exit 78 by the #124 policy, no
repeated-format / no-file-changes emissions. Tasks landed on
`token budget exhausted`, not a harness failure; Soak17 remains for
the targeted-seed gate (§11).

**Evidence:** `docs/soak_artifacts/stdout.txt` shows the proposal path
creating and gating **real proposals** in a soak — `e6a85797`
(`workflow/__init__.py`, approved + materialized first), then
`c5d6fb78` / `df6cd912` / `754abb94` / `f0872af5` / `1226b947` — with
the Soak16 fixes behaving as designed (edit primitive,
command/change-state observations, stall tripwire, task-fiability
pre-flight, `edit_payload` fallback gating; developer on
`gemini-3.1-pro-preview` @ api.genai.mil).

### 10.6 Out of scope

- Do not merge `soak/4-tmp-reporting` or `soak/doc-run-a-1`.
- Do not disable company↔public fallback on 401.
- Do not treat the RC 150M window as this soak’s spend.
- Do not “fix” mutation by widening fence repair or by asking the
  model harder that it has `/bin/sh`.
- Do not start §1 cold ingest or WAL ahead of this section.
- Mini-swe is not “folded in wrong.” The runner executed a real
  command in a real worktree. The developer **model** will not
  drive that runner past step 1.

### 10.7 Acceptance (short soak, two endpoints, developer ≠ Enterprise chat)

Soak8 (`self-edit/soak8`, review-only) already satisfied the
materialization spine — proposals created/approved/applied on repeated
target-run turns, exit-78 on the base64/python write attempt, no
repeated-format, no no-file-changes emit. Still tracked as a gate
because §11.2/§11.3 endpoints and the §11.1 targeted-seed run are not
fully green:

1. Trajectory `workspace_evidence` is filled **before** message[3]
   (no model-authored evidence fence required).
2. First model bash, if any, is inspect-of-target, not `pwd && ls`.
3. At least one session either writes a proposal or finishes
   `no_change_required` **after** printing the target file — never
   23 finishes that only deny having a shell.
4. `edit_proposals` ≥ 1 **or** an explicit
   `developer_model_not_shell_capable` / validation-failed status.
   `files_modified=0` with 30× evidence-only is a failed gate.
5. Zero-command latch does not freeze developer after a successful
   in-process evidence + `LlmUnavailable`.
6. `--model-health` is not empty after `kind=unknown`.
7. `Work:` is not 0.0s for the whole duration solely because the
   latch yielded to reviewers.

### 10.8 Soak16 remediation (shipped #122)

In-worktree edit primitive, command/change-state observations, stall
tripwire, task-fiability pre-flight, `edit_payload` fallback gating —
shipped in PR #122 and soak-validated. Details in git log.

### 10.9 Soak6 mutation policy (shipped #124)

Bounded promotion + inspect/mutate step split, banned base64/python
write-exec, utf-8 `errors="replace"` decode, `full_replace` fallback
cap, retryable-reject handling — shipped in PR #124. Details in git
log.

---

## 11. Soak17 — target-missing abort (shipped on branch; §11.4 notes)

**Priority:** shipped on branch (§11.1–§11.3 + §11.4 Soak22 notes).
**Soak17 symptom:** `workflow/shell_developer.py:1339` aborted the
session ("target missing after evidence") after **0 model calls**. The
driver: the orchestrator's own seed-hint list ("Look for TODO.md,
PLANS.md, IDEAS.md, ROADMAP.md, BACKLOG.md…") harvested `ROADMAP.md`
via `_seed_path_candidates`, but that file does not exist; three of the
five `files_needed` (`TODO.md`, `PLANS.md`, `IDEAS.md`) are **phantom**
(never in `project_files`; their "2 lines" came from
`get_file_content_from_db` stubs, not disk reads). Soak8 confirmed the
mutation path is healthy when the target exists on disk; the remaining
gap is §11.1 (phantom seeds must not abort) plus the §11.2/§11.3
endpoint gaps.

### 11.1 Existence-verified task targeting

- [x] `_task_is_targeted` must count a `files_needed` / addressed
      feedback file only when the file exists on disk. A target that
      never existed must not abort the session.
- [x] A seed that resolves to no existing file downgrades to an
      exploration session with a generic discovery hint — a
      case-insensitive glob of `todo|idea|plan|roadmap|backlog` over
      `*.md` / `*.markdown` — instead of a hard "target missing"
      abort (no hard-coded repo names), raising a `target_missing`
      event.

### 11.2 Config-failure vs transient classes + quota park

- [x] Treat `MissingSessionID`-class 400s as **permanent
      endpoint-config failures** (opencode/API session absent), not
      transient: surface the misconfiguration and demote without retry
      loops. `EndpointStatus` now has a `MISCONFIGURED` state.
- [x] Quota park = `min(seconds_to_reset, 4h)`, so a short
      `Retry-After` reopens on time instead of a fixed offline window.

### 11.3 Per-minute token-bucket headers + send pacing

- [x] Parse `x-ratelimit-limit-tokens-minute` /
      `x-ratelimit-remaining-tokens-minute` /
      `x-ratelimit-reset-tokens-minute` (and windowed `x-ratelimit-*`
      families) in `core/rate_limit_headers.py`; today only
      `X-RateLimit-Limit/Remaining/Reset` (daily free models) and
      `Retry-After` are read.
- [x] Persist the discovered per-minute budget to endpoint health; when
      `remaining-tokens-minute == 0`, park all consumers for the
      endpoint until `reset-tokens-minute`, and pace client token
      send-rate so parallel large prompts (one reviewer prompt was
      183k+ chars) cannot re-trigger the 429 storm.
      (Evidence: `docs/soak_artifacts/stdout.txt` 356-363 and 1007-1098 —
      `500000` tokens/min, `remaining 0`, `reset 59`; `Retry-After` is
      honored correctly, but consecutive windows keep re-tripping.)

### 11.4 Soak22 soak notes — hardening verified, two fixes shipped

Soak22 (2026-09-10, unattended run, `task_001` = discovery seed on
`docs/TODO.md`) stopped after ~1h with `files_modified=0` because both
endpoint families were unusable; the degradation paths handled it as
designed:

- openrouter free tier hit its daily 429 quota (`X-RateLimit-Reset:
  1789171200000` → 2026-09-12 00:00 UTC; `Retry-After=75812s`) → §11.2
  quota park `min(reset, 4h)` fired, then "No alternate endpoints
  available — recheck in 120s"; background workers auto-disabled;
  resource controller throttled 118→11 calls/min, feeder 30s→180s.
- The fallback target `opencode/big-pickle` is **misconfigured**
  (`MissingSessionID` 400 — "free tier can only be used in OpenCode"),
  so every fallback burned a request into a §11.2 misconfig park (240m)
  instead of retrying. Config hygiene item, not a code defect.
- Orchestrator 3/3 fail → task_001 finalized `timed_out`
  (`token budget exhausted: files_modified=0`). Note: the console's
  "Budget: 99.4% (19,889,292 tokens)" readout is **tokens remaining**,
  not a spent alarm.

Verified working in situ: TimeExceeded shell-session exit (10 model
calls), `no_progress` stall guard (13 calls vs limit 10), one-shot JSON
repair, the reviewer legitimately rejecting the §8/§10 heading deletion,
and background-agent lane isolation during developer sessions.

Fixes shipped:

- **Operator console (593b69d):** spend-window cutoff and latch
  countdown were off by the host offset (aware seeds vs naive-local
  writes) — `core/operator_view.py` `_normalize_ts` / `_local_naive`.
- **Rollout finalize (2026-09-11):** `classify_infra_abort` compared a
  naive-local `endpoint_health.unavailable_until` against an aware-UTC
  rollout `completed_at` raw → `TypeError: can't compare offset-naive
  and offset-aware datetimes` left the rollout stuck `in_progress`
  (mis-bucketed as plain failed, infra signal lost). Both sides now
  normalize to naive host wall-clock via `_wallclock_naive` (mirror of
  the console helper); regression tests cover aware↔naive mixes.

### 11.5 Honest schema gate (shipped ca68d62, branch)

`init_db()` (`core/db.py`) must never stamp a `PRAGMA user_version` it
cannot verify:

- Matching version + broken shape → **raise**, do not stamp. A `claimed
  user_version` is checked against `REQUIRED_TABLES` /
  `REQUIRED_COLUMNS` (`_schema_matches_canonical`), not trusted blind.
- Version mismatch (incl. `0`) → `_discard_db` deletes the DB +
  `-wal` + `-shm`, applies canonical DDL, **verifies before stamping**,
  then sets `user_version` once on a brand-new file.
- Any unlink failure → **raise** (`refusing to lie about schema: …`);
  the old "rebuild in place" `except OSError` branch (which stamped a
  new version over differing tables) is gone.
- Current + honest → open only; no unlink, no DDL, no version rewrite.

Tests: `tests/unit/test_db_schema.py` — fresh→v3+shape; second init →
same inode / same rows / version unchanged; v3 but `rollouts` dropped →
raises, version still 3; v2 → replaced, the rollouts `verdict` column
present, legacy rows gone; unlink fails on stale DB → `RuntimeError`,
version stays 2.
Docs: `docs/architecture.md` "Database initialization" paragraph updated.

- [x] Shipped in `ca68d62` on `feat/roadmap-soak17` (branch) — purge on
      merge to `main`.

---

## 12. Harness-evolution loop — deploy `HARNESS_EVOLUTION_DESIGN` (zero-dep path)

**Priority:** P2 — P0 rollout substrate shipped on branch (§12.1–§12.3).
**Source:** `docs/HARNESS_EVOLUTION_DESIGN.md` (implemented through §12.3 on branch).
**Dependency posture:** zero new runtime deps — `requirements.txt` stays
`requests` + `pathspec`. Uses stdlib sqlite3 JSON1 (verified here: 3.46.1,
`json_each` OK — the §5.2 verdict SQL runs natively), `importlib`, `base64`/`re`/
`json`, plus existing machinery: `call_agent`, `parallel_workers` (`threading`),
the governed pipeline (`apply_edit_proposal` → reviewer →
`materialize_proposal` / `undo_proposal`), `ShellWorktree`,
`model_health_events` / endpoint latches / `agent_responses_archive`.
The three new-dep triggers — Terminal-Bench 2 (`terminal-bench` pip pkg),
HuggingFace `datasets` (SWE-bench-verified), Docker OS-sandboxing — are
**out of scope** (§8-d1 internal soak-task set wins).

Phase order and exit criteria at the bottom (§12.7).

### 12.1 P0 substrate observability (shipped)

Shipped and **not** repeated: `core/operator_view.py`, shell heartbeats
(`shell_turn_start` / `shell_model_call_started` / `shell_command_executed` /
`shell_spinning`), `utils/live_console.py`, run-effectiveness diagnostics.

Shipped (2026-09-10, `harness/fingerprint.py` + `rollouts` table +
`schema v2`, later bumped to `SCHEMA_VERSION = 3` in §12.2):

- [x] **Per-run harness fingerprint:** persist `(harness git tag, resolved
      prompt hash, model)` per rollout (`sha256` over the sorted resolved
      `get_agent_prompts` dict at `core/config.py` `get_agent_prompts`). A
      `rollouts` row is created at `run_task_cycle` start (task_runner) and
      finalized (status, infra-abort label, token backfill from `token_log`)
      at loop end. Prompts render at runtime (agents/base.py), so the
      fingerprint makes §5 edit-verdict claims verifiable.
- [x] **Infra-abort classifier:** label rollouts aborted by endpoint infra
      (`empty_body` / `no_alternate_endpoint` / `misconfigured` /
      `rate_limited` / `key_locked` / `token_budget` / `token_exhausted`,
      from the `model_health_events` tail + endpoint `unavailable_until`
      latches) so the Debugger's `component_hint` never blames the harness
      for a flaky endpoint (Soak18 exact confound); `failure_mode_mix`
      reports pass@1 + infra vs non-infra failures per iteration.

### 12.2 P1 boxed benchmark (internal soak-task set)

Spec: `docs/benchmark_v1.md`. Verifier + tracer harness around existing soak
seeds using `ShellWorktree`; `k >= 2` rollouts/task; infra-aborted / timeout
trials count as failures (§7 pass@1). No Terminal-Bench-2 / SWE-bench-verified /
Docker sandbox (out of scope).

Decisions (2026-09-10): verifier = FINISH-evidence gate **+** content
assertions; 5 crafted canonical tasks in `harness/benchmark/tasks.json`;
sequential k trials sharing the single DB writer.

- [x] **Spec** (`docs/benchmark_v1.md`): task manifest format, verifier rules,
      driver/CLI, pass@1 accounting, out-of-scope list.
- [x] Implement `harness/benchmark/tasks.json` (5 canonical tasks) + loader.
- [x] Implement `harness/verify.py`: evidence gate → content assert → verdict
      (`passed | failed | infra_aborted`) + `component_hint`.
- [x] Implement `harness/benchmark/driver.py` + `python -m harness.benchmark`
      (sequential trials, contract_hash + verdict on `rollouts`,
      `runs/<iter>/results.json`, pass@1 via `failure_mode_mix`).
- [x] `SCHEMA_VERSION = 3`: `rollouts.contract_hash / verdict / verdict_note`.
- [x] Unit tests (verifier + driver) and slow integration (mocked LLM full run).

### 12.3 P1 trajectory corpus

Shipped (2026-09-11) — the §4.1 layered layout under `runs/<iter>/`; the §12.7
P1 exit criterion (one iteration produces `cleaned/` + `analysis/` +
`overview.md` + `index.json`) is now satisfied.

- [x] **Cleaning pass** (`harness/cleaning.py`): reusable base64-drop
      (`data:...;base64,...` blobs + long standalone base64 runs replaced by an
      elision marker) and consecutive-frame dedup (identical adjacent frames
      collapse with a `dup_count`) → `cleaned/<task_id>.jsonl`, one frame per
      line, every turn merged and chronologically ordered. Raw
      `shell_trajectories` stay untouched.
- [x] **Debugger producer** (`harness/debugger.py` + `harness/corpus.py`):
      parallel support-worker (ThreadPoolExecutor) consuming `cleaned/` →
      `analysis/<task_id>.md` + `overview.md` (failing tasks grouped by
      `component_hint`, passing by `success_patterns`) + `index.json`
      (entry → tasks → raw-traces drill-down, verdict cross-ref from
      `results.json`). Every root cause carries an evidence file + a
      `component_hint` from the fixed enum; LLM / parse / invalid-hint failures
      degrade to an explicit `inference_error`, never fabricated evidence.
      CLI: `python -m harness.corpus --iter N --raw <.PrizmForge/shell_trajectories>
      --runs <runs/iter_N> [--results results.json] [--max-workers 4]`.

### 12.4 P2 decision observability (manifest + verdict)

- [x] Manifest JSON per iteration (`harness/manifest/iteration-<t>.json`, written
      by `write_manifest_file`) with `predicted_fixes` / `predicted_regressions`
      per edit; mirrored into `harness_change_manifest(iteration, payload)`
      (`harness/evolve.py`, schema in `core/db.py`, `SCHEMA_VERSION=4`).
      `task_outcomes(iteration, task_id, passed, tokens)` recorded from a
      `run_benchmark` results dict (`record_iteration_outcomes`);
      `edit_verdicts(prior, cur)` runs the §5.2 prediction∩delta SQL via
      `json_each` (verified) and folds the verdict into per-edit precision —
      the §5.3 rollback rule now has real inputs.
- [ ] Rollback: `git revert <edit.commit>` on the harness workspace (or
      `undo_proposal`) when confirms == 0 and flagged/extra regressions land;
      `revert_candidates(prior, cur)` SELECTS the offenders (§5.3) — the
      executor (`git revert`/governed undo) runs in the §12.5 Evolve loop
      before the next distillation so verdicts stay in the corpus.

### 12.5 P2 Evolve gate

- [x] **Evolve Agent** edits only `harness/` via the governed pipeline with the
      reviewer gate mandatory + non-editable; one logical edit per commit,
      tagged `iter-<t>`; RC-style edit budget (`max_tokens_per_4h`-class) gates
      the loop. `harness/evolve_loop.py`: `run_evolve_iteration` (outcomes →
      evidence → propose → gate → snapshot+materialize → manifest →
      budget.spend), `run_evolve_session` (bench t → evolve → bench t+1 →
      `run_evolve_reverts` executing `revert_candidates` via `git revert` /
      injectable executor), `EvolveBudget` (edits + token caps, gated before
      any propose), and the `evolve.enabled` config gate. Harness-edit commits
      carry `[iter-<t>]` via the new `git_commit_tag` config in
      `materialize_proposal`.
- [x] Harness mount loader: `harness/system_prompt/<role>.md` + `{{include:file}}`
      + `{{placeholder}}` fill resolve at runtime (`resolve_harness_prompt` —
      the single prompt-assembly path, with a fallback to the legacy
      `agent_prompts.json` entry when no seed file exists so other agents keep
      one, truthful story). Evolve's personality lives in
      `harness/system_prompt/evolve.md`, which the harness git tag already
      fingerprints (follow-up: fold seeded prompt contents into `prompt_hash`).
- [x] `runs/`, tracer/verifier/sandbox config, and LLM endpoint / model config
      are read-only for the Evolve Agent; seed prompt files non-deletable.
      `validate_evolve_target` enforces `harness/`-only targets, blocks
      `runs/` + `config.json`/`agent_prompts.json`/`endpoints.json`, and
      denies deleting `system_prompt/` seeds (edits allowed).

### 12.6 P3 attribution (after a working loop)

- [ ] Single-component swaps (`+ memory` / `+ tool` / `+ middleware` /
      `+ system_prompt`) to attribute pass@1 deltas (§7 component ablation).
- [ ] `H_best <- H_t` tracking; then cross-benchmark / cross-model transfer
      (deferred until the internal loop is stable).

### 12.7 Phase order & exit criteria

| Phase | Exit criterion |
|---|---|
| P0 (§12.1) | Rollouts carry fingerprints; infra aborts excluded and counted |
| P1 (§12.2–12.3) | One iteration produces cleaned/ + analysis/ + overview/ + index.json for the internal set — **satisfied** (§12.3) |
| P2 (§12.4–12.5) | An iteration round-trips: harness edits → verdict → rollback |
| P3 (§12.6) | A single-component swap changes measured pass@1 |

**Out of scope (do not start):** Terminal-Bench 2, SWE-bench-verified
(`datasets`), Docker / enclave OS-sandboxing, editing `runs/` or endpoint
config (even by the Evolve Agent), PostgreSQL / SQLAlchemy mirror, and any
dependency entry beyond `requests` / `pathspec` for this loop.

---

## 13. Edit-process hardening (resiliency / efficiency / testability / bench-worthiness)

**Priority:** P1 — same tier as remaining P1 work; no new deps.
**Source of truth:** `file_editing/`, `workflow/developer_edit.py`,
`workflow/shell_developer.py`, `harness/verify.py`,
`harness/benchmark/driver.py`.

### 13.1 Atomic apply — all-or-nothing proposals (P1)

- [x] `apply_edit_proposal` must apply a proposal's operations in ONE
      transaction: any per-op failure rolls back the whole proposal (status
      `error`, governed store untouched) instead of committing partial state.
      Today `file_editing/editing.py:807-821` returns a dict for a failed op,
      and `file_editing/db.py` commits on clean exit of the context — op1
      lands, op2 does not. Wrap ops in an explicit transaction helper
      (e.g. a SAVEPOINT the dispatcher rolls back on first failure).
- [x] **Op-shape guard (no mixed re-init):** content-level ops
      (`find_replace` / `full_replace` / `apply_diff` / `create_file` /
      `delete_file`) recreate the whole line store (`initialize_file_lines`
      DELETEs all rows); a proposal mixing them with line-level ops
      silently drops prior ops' lines/GUIDs. Reject the mix in the apply
      path (and at `EditPayload` / proposal-creation time), same benign-gate
      pattern as `validate_operation`.
- [x] Tests: multi-op proposal with failing op #2 → governed store unchanged,
      status `error`; mixed line+content proposal → rejected before apply.

### 13.2 Materialize crash consistency + multi-file correctness (P1)

- [x] Recovery scanner for `status='applied'` orphans: get `find_orphaned_applied`
      (applied proposals whose `file_write_log` lacks a row per touched path) +
      `recover_orphaned_applied()` (idempotent re-materialize); `run_benchmark`
      runs it at iteration start (`file_editing/writer.py`, `harness/benchmark/
      driver.py`). Global `init_db` hook deferred to the §13.7 live bootstrap —
      a blanket hook would fire git/disk writes on every app/test wake. Note:
      `git_failed`/`lint_failed` count as healed (disk written) since write-log
      rows exist.
- [x] Multi-file `undo_proposal` must snapshot/restore EVERY affected path,
      not only `target_file_path` (`file_editing/undo.py`): snapshots are
      keyed `(proposal_id, file_path)`; paths that did not exist pre-apply
      (`content_before` NULL) are soft-deleted + unlinked, not recreated
      empty. Multi-file + created-secondary-file tests added.
- [x] Surface materialize results per file: `write_log` already records
      per-file status; `materialize_proposal` now returns `file_statuses`
      (path → success/error/lint_failed) + a `partial_materialized` flag
      instead of collapsing to a single bin (`file_editing/writer.py`).
- [x] **Multi-file apply dispatch:** `apply_edit_proposal` ran EVERY op against
      the proposal's primary `file_id`, so a content op with its own
      `target_file_path` silently edited the wrong file (find_replace
      reported "No matches; file unchanged"). Ops now resolve their own file
      id via `_resolve_op_file_id` (GUID check + SAVEPOINT dispatch).
- [x] Symbol refresh moved out of the materialize write transaction: a DB
      writer inside the open txn (multi-file materialize) busy-waited 30s on
      its own RESERVED lock then silently dropped. Refreshes now run
      post-commit (`file_editing/writer.py`).

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

### 13.6 Benchmark isolation + timeboxing (P1)

- [x] Per-trial fresh project dir and per-iteration DB reset (or explicit
      cleanup deleting non-fixture files/rows) — the driver reuses one
      `bench_dir` + the global DB (cross-trial leakage today).
- [x] Per-trial wall-clock timeout + hard per-iteration cap (`max_turns`
      alone lets a hung shell command stall the bench).
- [x] Honor `tasks.json` `schema_version` in `harness/benchmark/tasks.py`
      (currently ignored).
- [x] Isolation tests: trial-1-created file absent from trial-2 fixture dir /
      DB; `absent` assertions robust across trials.

### 13.7 Live/control runs (P2)

- [ ] `bench_config` (`harness/benchmark/config.py`) hardcodes `endpoints:
      {}` / `mock-model`; add `--live` endpoint/model injection +
      deterministic ordering + iteration-labeled results so pass@1 is
      comparable across real control runs. `python -m harness.benchmark
      --dry-run` validates the manifest + isolated DB without LLM calls.

### 13.8 Test seams for the pipeline (P1)

- [ ] Split `apply_edit_proposal` / `materialize_proposal` (both C901) into
      small helpers — op-dispatch table, affected-path resolver,
      write-log status reducer — so atomicity/status logic is unit-testable
      without a DB.
- [ ] Cover the identified gaps: multi-op rollback, crash recovery, trial
      isolation, sort-order renumber stress (gap < `MIN_GAP_THRESHOLD`),
      regex/count find_replace, diff ambiguity.

---

## 8. Operator soak A-1 — ran (Soak4)

---

**Priority:** ran. Recursive fallback, per-endpoint budget, fail-closed
evidence shipped in #121; Soak4 confirmed worktree + evidence. The
remaining gate is §10.7 / §11, not a re-soak of this checklist.

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

**Soak4 result (do not re-run this as P0):** evidence + worktree
passed; the chat-refusal gate failed (0 proposals). Remaining gate is
§10.7, with developer ≠ Enterprise chat.

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
      (Soak5 artifact evidence: one dump per 429, one-line skip, and a
      fallback attempt to `beta_genai` — but a token-budget gate and
      `Work: 0.0s` remain; see `docs/soak_artifacts/stdout.txt` 1015-1098.)

Non-goals (still): do not spoof OpenCode CLI headers; do not treat
`free-models-per-day` as a product bug; do not reopen short Retry-After
for non-quota 429/503.

---

## 2. Shell developer — remaining protocol holes

Shipped in #121 and **not** repeated: fail-closed evidence,
`FINISH_EDIT_SESSION` rejected until `test -f workflow/__init__.py`,
A-1 finish-without-bash fixture, worktree-not-parent tests.

Soak4: that evidence loop is not enough. Do **not** keep the
“you have a real shell / do not ask the user to upload files”
sermon in the first user turn — it triggers Gemini Enterprise
refusal. Mutation-path work is §10 (in-process evidence, inspect
target first, developer ≠ Enterprise chat).

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

- [x] Quote SQL identifiers in `cli/commands.py` DB exports
      (`cmd_export_db`, `cmd_export_specific_tables`,
      `table_has_task_id`). `_quote_identifier()` = double-quote +
      escape embedded `"`. (`sqlite_master name=?` is already
      parameterized.)
- [x] Comment/string-aware DDL split in `core/db.py`
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

Port itself is shipped (`docs/mini_swe_agent.md`). Soak4 showed the
runner executes real commands; Gemini Enterprise will not drive past
evidence — that e2e is **§10**, not a second mini-swe port.

- [ ] Real-model end-to-end validation + prompt/limit tuning **after
      §10** (developer model that emits a second bash block).
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
| 0 | Commit §12.3 corpus modules + §11.5 honest gate (branch) | Pre-commit + full suite green on `feat/roadmap-soak17` |
| 1 | §1 NUC wiped `cmd_init` timing | Short burst; DELETE+NORMAL after return |
| 2 | §6 next-soak 429 dump | One dump; `Work:` not 0.0s from support latch |
| 3 | §7 live-hook / mini-swe e2e | When endpoints and a hook-fail copy exist |
| 4 | §12.4 decision manifest | `harness/manifest/iteration-<t>.json` + `task_outcomes` feed the §5.2 verdict SQL |
| 5 | §12.5 Evolve gate first iteration | An iteration round-trips edits → verdict → rollback on the internal set |
| 6 | §12.6 attribution ablations | A single-component swap changes measured pass@1 |
| 7 | §13.1/§13.2/§13.6 — atomic apply, crash recovery, bench isolation | Proposals apply all-or-nothing; no orphan `applied` rows; trials hermetic |