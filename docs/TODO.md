# PrizmForge Roadmap / TODO

This file lists **only work that still needs to be accomplished**.

Completed work is **not repeated here**. Implementation, PR numbers, soak
post-mortems, and acceptance evidence live in **git history**
(`git log`, merged PRs #108–#124, and
`docs/UNATTENDED_CLOSED_LOOP_CAPABILITIES.md`). Do not paste shipped
checklists back into this tracker.

**Last updated:** 2026-09-09

## How to use this file

- Tick a box when the change lands on `main`; then delete that item on
  the next pass (do not leave `[x]` museums).
- Detailed *design* for an open item stays in this file until it ships.
- Do not merge `soak/doc-run-a-1` or `soak/4-tmp-reporting`
  (trajectories + docs only).

## Section priorities

| Section | Priority | Why |
|---|---|---|
| §0 Current state | — | Index |
| **§11 Soak17 root-cause fixes (targeting / 400 class / headers)** | **P0** | Phantom-seed abort burned Soak17 at 0 model calls. Fix §11.1 existence-verified targeting first, then §11.2 config-failure class + quota park, then §11.3 per-minute token headers. |
| **§12 Harness-evolution loop (`HARNESS_EVOLUTION_DESIGN`)** | **P2** | Zero-dep closed loop; P0 substrate partially shipped (operator console). External benchmarks out of scope |
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
- **Next (do):** §11 — make targeting existence-verified, close the
  endpoint config/header gaps, then re-run the §10.7 acceptance gate on
  a targeted task that names an existing file. (Soak8 already shows a
  real targeted run reaching materialization; §11 closes the phantom-seed
  abort and the §11.2/§11.3 endpoint gaps.)
- **Harness-evolution substrate (§12):** P0 observability base landed
  (operator console: `core/operator_view.py`, shell heartbeats,
  `utils/live_console.py`, run-effectiveness views). §12.1 still needs
  the per-run harness fingerprint + infra-abort classifier before any
  harness-edit attribution is trustworthy.
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

## 11. Soak17 — target-missing abort (open, P0)

**Priority:** P0 — next work.
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

---

## 12. Harness-evolution loop — deploy `HARNESS_EVOLUTION_DESIGN` (zero-dep path)

**Priority:** P2 (behind §11 gates; P0 rollout substrate shipped).
**Source:** `docs/HARNESS_EVOLUTION_DESIGN.md` (draft, not implemented).
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

### 12.1 P0 substrate observability (partially shipped)

Shipped and **not** repeated: `core/operator_view.py`, shell heartbeats
(`shell_turn_start` / `shell_model_call_started` / `shell_command_executed` /
`shell_spinning`), `utils/live_console.py`, run-effectiveness diagnostics.

Shipped (2026-09-10, `harness/fingerprint.py` + `rollouts` table +
`SCHEMA_VERSION = 2`):

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

- [ ] Verifier + tracer harness around existing soak seeds using
      `ShellWorktree`; `k >= 2` rollouts/task; infra-aborted / timeout trials
      count as failures (§7 pass@1). No Terminal-Bench-2 / SWE-bench-verified /
      Docker sandbox (out of scope).

### 12.3 P1 trajectory corpus

- [ ] Extract base64-drop + consecutive-frame-dedup cleaning into a reusable
      function → `runs/<iter>/cleaned/<task_id>.jsonl`; raw `shell_trajectories`
      stay untouched.
- [ ] **Debugger producer** (parallel_workers pattern) consuming `cleaned/` →
      `runs/<iter>/analysis/<task_id>.md` + `overview.md` + `index.json`
      (entry → tasks → traces drill-down); every claim carries a file path and
      a `component_hint` from the fixed enum.

### 12.4 P2 decision observability (manifest + verdict)

- [ ] Manifest JSON per iteration (`harness/manifest/iteration-<t>.json`) with
      `predicted_fixes` / `predicted_regressions` per edit; mirror into
      `harness_change_manifest(iteration, payload)` +
      `task_outcomes(iteration, task_id, passed, tokens)` for the §5.2 verdict
      SQL (json_each verified). Fold `predicted_regressions` into the verdict so
      the §5.3 rollback rule has real inputs.
- [ ] Rollback: `git revert <edit.commit>` on the harness workspace (or
      `undo_proposal`) when confirms == 0 and flagged/extra regressions land;
      reverts happen before the next distillation so verdicts stay in the
      corpus.

### 12.5 P2 Evolve gate

- [ ] **Evolve Agent** edits only `harness/` via the governed pipeline with the
      reviewer gate mandatory + non-editable; one logical edit per commit,
      tagged `iter-<t>`; RC-style edit budget (`max_tokens_per_4h`-class) gates
      the loop.
- [ ] Harness mount loader: `harness/system_prompt/<role>.md` + tools /
      middleware / skills / memory resolve at runtime (single prompt-assembly
      path replacing direct `agent_prompts.json` reads) so the fingerprint stays
      truthful.
- [ ] `runs/`, tracer/verifier/sandbox config, and LLM endpoint / model config
      are read-only for the Evolve Agent; seed prompt files non-deletable.

### 12.6 P3 attribution (after a working loop)

- [ ] Single-component swaps (`+ memory` / `+ tool` / `+ middleware` /
      `+ system_prompt`) to attribute pass@1 deltas (§7 component ablation).
- [ ] `H_best <- H_t` tracking; then cross-benchmark / cross-model transfer
      (deferred until the internal loop is stable).

### 12.7 Phase order & exit criteria

| Phase | Exit criterion |
|---|---|
| P0 (§12.1) | Rollouts carry fingerprints; infra aborts excluded and counted |
| P1 (§12.2–12.3) | One iteration produces cleaned/ + analysis/ + overview/ + index.json for the internal set |
| P2 (§12.4–12.5) | An iteration round-trips: harness edits → verdict → rollback |
| P3 (§12.6) | A single-component swap changes measured pass@1 |

**Out of scope (do not start):** Terminal-Bench 2, SWE-bench-verified
(`datasets`), Docker / enclave OS-sandboxing, editing `runs/` or endpoint
config (even by the Evolve Agent), PostgreSQL / SQLAlchemy mirror, and any
dependency entry beyond `requests` / `pathspec` for this loop.

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
| 1 | §1 NUC wiped `cmd_init` timing | Short burst; DELETE+NORMAL after return |
| 2 | §6 next-soak 429 dump | One dump; `Work:` not 0.0s from support latch |
| 3 | §7 live-hook / mini-swe e2e | When endpoints and a hook-fail copy exist |
| 4 | §12.1 fingerprint + infra-abort classifier | Rollouts carry a harness fingerprint; infra aborts excluded from root-cause |
| 5 | §12.2–12.5 internal benchmark → corpus → manifest/Evolve first iteration | An iteration round-trips edits → verdict → rollback on the internal set |
| 6 | §12.6 attribution ablations | A single-component swap changes measured pass@1 |