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
- **Next (do):** §12 Harness-evolution substrate (§12):** P0 observability base landed
  (operator console: `core/operator_view.py`, shell heartbeats,
  `utils/live_console.py`, run-effectiveness views). §12.1 still needs
  the per-run harness fingerprint + infra-abort classifier before any
  harness-edit attribution is trustworthy.


---
## 1. All ./utils/*.sh should follow same .env python patterns as run_tests.sh
- needs investigation and todo expantion

## 12. Harness-evolution loop — deploy `HARNESS_EVOLUTION_DESIGN` (zero-dep path)

**Priority:** P2 (behind §11 gates; P0 substrate partially shipped).
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

Still open:

- [ ] **Per-run harness fingerprint:** persist `(harness git tag, resolved
      prompt hash, model)` per rollout (`hashlib` over the resolved
      `get_agent_prompts` dict). Prompts render at runtime (agents/base.py),
      so without the fingerprint §5 edit-verdict claims are unverifiable.
- [ ] **Infra-abort classifier:** label rollouts aborted by endpoint
      infra (`empty_body` / `no_alternate_endpoint` / `misconfigured`, from
      `model_health_events` + endpoint latches) so the Debugger's
      `component_hint` never blames the harness for a flaky endpoint (Soak18
      exact confound); report `failure_mode_mix` per iteration.

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
evidence, not a second mini-swe port.

- [ ] Real-model end-to-end validation + prompt/limit tuning (developer model that emits a second bash block).
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