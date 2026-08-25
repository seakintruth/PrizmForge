# TODO: Incorporate mini-swe-agent as the Developer Agent

Status: **Implemented (beta) — pending real-model validation**
Date: 2026-08-23

---

## Background / Motivation

Review of the 2026 open-source agent landscape (opencode, OpenClaw, Hermes Agent)
showed that PrizmForge's differentiated value is its **governed mutation pipeline**
(proposal → Reviewer gate → materialize), not its execution engine. The structured
EditPayload developer produced unverified edits: nothing ever ran tests or shell
commands before the Reviewer judged a proposal.

[mini-swe-agent](https://github.com/SWE-agent/mini-swe-agent) (MIT, ~hundreds of LOC)
demonstrates that a minimal query/execute loop with real bash access outperforms
constrained JSON-emitting developers. Rather than vendoring an external dependency
(ATO/supply-chain cost for government packaging), the working concepts were rebuilt
natively inside PrizmForge.

### Plan

1. Port the mini-swe-agent core loop natively (MIT attribution preserved).
2. Isolate each session in a disposable `git worktree`; let the model edit and verify
   there with real bash.
3. Convert session output into governed proposals so the existing
   Reviewer → materialize pipeline stays the only mutation path.
4. Wire into the task runner behind a config switch, keeping the legacy developer.
5. Update packaging (`setup.sh`, `export_project_zip.py`) for distribution to work.

---

## What Was Accomplished

### New module: `workflow/shell_developer.py`

- **Control loop** adapted from mini-swe-agent: system/instance prompt → model reply →
  last ```bash fenced block executed in the worktree → observation fed back → repeat.
  Session ends on `FINISH_EDIT_SESSION` sentinel, step limit, wall-clock limit, or
  repeated format errors.
- **All LLM calls route through `agents.base.call_endpoint()`** — per-endpoint rate
  limiting, token budget, endpoint health, and fallback governance apply unchanged.
- **Worktree isolation** (`ShellWorktree`): one disposable worktree per session,
  subdirectory-aware (project_directory may sit inside the repo root); changes
  collected via `git diff --cached --name-status -z`; renames mapped to destination;
  deletions skipped with a warning (no governed delete operation exists yet);
  guaranteed cleanup in `finally`.
- **Governed handoff**: changed files become EditPayload proposals
  (`create_file` / `full_replace`) via the existing
  `create_proposal_from_developer_output()`, then pass through the unchanged
  Reviewer gate and `materialize_proposal()`.
- **Verification**: optional `test_command` runs post-session against the edited
  worktree; non-zero exit **fails closed** (`on_test_failure: discard`, default) or
  proceeds on explicit opt-in (`propose_anyway`). Test exit code + output tail are
  embedded in proposal rationale and shown to the Reviewer as evidence.
- **Audit artifacts**: full session trajectories serialized to
  `.PrizmForge/shell_trajectories/<task>-turn<N>-<UTC>.json` (RMF evidence).

### Wiring & configuration

- `workflow/task_runner.py`: developer branch now dispatches on
  `developer.implementation`:
  - `"shell"` — new agent (set as default in `example_config.json`)
  - `"edit_payload"` — legacy structured flow, fully intact; also the code-level
    fallback when the key is absent (keeps older configs and tests stable)
- New config sections documented in CONFIGURATION.md:
  - `developer.implementation`
  - `shell_developer.{step_limit, wall_time_limit_minutes, command_timeout_seconds,
    test_timeout_seconds, max_output_chars, max_consecutive_format_errors,
    test_command, on_test_failure, model, worktree_parent}`

### Packaging

- `utils/setup.sh`: git prerequisite check (worktrees require git); warning counter
  surfaced in the setup summary.
- `utils/export_project_zip.py`: excludes `.PrizmForge/` runtime state,
  `shell_trajectories/`, and `*.db` / `.sqlite*` files from packaged archives —
  verified zero runtime artifacts leak into a test export.
- `THIRD_PARTY_NOTICES.md`: MIT license text and attribution for mini-swe-agent,
  with a description of material differences from upstream.

### Tests

`tests/unit/test_shell_developer.py` (9 tests, all passing):

- Response parsing: bash-block extraction, finish sentinel + summary
- Change→operation mapping: A→`create_file`, M→`full_replace`, D/S→skipped
- Worktree lifecycle against a real git repo: create / collect / cleanup;
  non-repo rejection
- End-to-end turn with mocked LLM + reviewer: approved session materializes exactly
  one proposal with correct progress counters; rejected session reports `rejected`
  and mutates nothing

### Verification results

| Gate | Result |
|------|--------|
| Targeted tests (shell dev, task_runner, proposal_builder, developer_edit helpers) | 30 passed |
| Full normal gate (`bash utils/run_tests.sh --normal -j 4`) | **606 passed** |
| ruff (new/modified files) | clean |
| mypy | zero new errors (baseline debt untouched) |
| Export zip leak check | no `.PrizmForge`/DB/trajectory entries |

---

## Review Round (external review of this implementation)

An external review confirmed all 5 plan items were covered but identified gaps
between the plan's safety claims and the code. All items below are now addressed
in `workflow/shell_developer.py` unless noted:

### High — fixed

1. **Reviewer gate failed open twice** (None response or non-JSON → APPROVE).
   Now **fails closed**: missing/empty/unparseable verdicts, and any `decision`
   value other than APPROVE/REJECT, REJECT the proposal. Shell-session diffs
   originate from arbitrary bash execution, so gate authority must not depend on
   endpoint health.
2. **Worktree base could be stale vs governed state** (branch from HEAD while
   materialized proposals may be uncommitted). `ShellWorktree.create()` now runs
   `sync_governed_state()`: every tracked non-deleted governed file is rewritten
   from the DB and DB-deleted files removed, so the agent edits governed content
   and the Reviewer's diff base matches what would actually be replaced.

### Medium — fixed

3. **Feedback marked addressed too broadly**: only feedback whose `file_path`
   maps to a change that actually materialized (gate == success) is marked
   addressed; skipped/rejected changes keep their feedback open.
4. **`max_file_bytes` was dead config**: wired through to the oversize check in
   `collect_changes()` and added to the CONFIGURATION.md table.
5. **Silent drop of out-of-scope changes**: `_strip_sub()` misses now log a
   warning naming the skipped path; oversize skips also log file sizes.
6. **Finish-token precedence swallowed a final command**: a reply containing both
   a bash block and `FINISH_EDIT_SESSION` now executes the command first, asks
   for confirmation, and force-finishes after 3 deferrals.

### Low — fixed / documented

7. `selected_mode="shell_session"` shows as an unknown mode in
   run-effectiveness grouping. Accepted: attribution beats grouping; no change.
8. Limits were only checked before each LLM call: each bash command's timeout is
   now capped by the remaining wall-clock budget, and CONFIGURATION.md documents
   the residual behavior.
9. `on_test_failure` values are validated in `from_config()`; typos fall back to
   `discard` (fail closed) with a warning.

### Verification after the review round

| Gate | Result |
|------|--------|
| Shell developer tests (incl. 9 new regression tests) | 18 passed |
| Full normal gate (`bash utils/run_tests.sh --normal -j 4`) | **615 passed** |
| ruff / mypy | clean / zero new errors |

---

## Post-Validation Round

A follow-up validation confirmed all review-round fixes but caught one gap the
base-sync fix itself introduced, plus two nits. All addressed:

1. **Sync drift polluted the change set**: `sync_governed_state()` writes DB
   content that may differ from HEAD (uncommitted materializations — the exact
   scenario the sync exists for), but `collect_changes()` diffed against HEAD,
   so drifted files were re-proposed as agent work. Fix: `create()` now stages
   the post-sync worktree and records its tree
   (`git add -A` + `git write-tree`, stored as `_baseline_tree`);
   `collect_changes()` diffs against that baseline instead of HEAD. Only
   agent-authored work is collected; drifted files keep their governed content.
   Regression test: `test_collect_changes_exclude_sync_drift`.
2. **Nit — prefix stripping**: `lstrip("./")` (character-set strip) replaced with
   precise `removeprefix("./")`.
3. **Nit — non-numeric feedback IDs**: `int()` conversion failures from
   orchestrator hallucination are skipped with a warning instead of raising;
   covered by extending the feedback-mapping test.

Verification after this round: 19/19 shell-developer tests,
**616 passed** full normal gate, ruff clean, mypy baseline unchanged.

---

## Unattended Cold-Start Round

Implemented from the Hermes cold-start plan
(`.hermes/plans/2026-08-24_021500-unattended-coldstart-context-fixes.md`):

1. **Seed-as-feedback** (`workflow/task_runner.py`): new `_inject_seed_feedback()`
   inserts the task's seed description as a HIGH `category='seed_task'`
   `agent_feedback` row right after `create_task()` — idempotent per task, empty
   commands ignored. The prioritizer/orchestrator backlog counts and the
   BACKLOG_PROCESSING redirect now have concrete work from iteration 1 instead of
   waiting ~5 min for reviewer findings.
2. **Backlog redirect implemented**: the `"Would process via developer agent
   (implementation needed)"` stub is gone. Both the orchestrator `developer`
   path and the BACKLOG_PROCESSING redirect now route through a shared
   `_dispatch_developer()` helper that honors `developer.implementation`
   (`shell` or legacy `edit_payload`) — design decision flagged by the plan,
   resolved per its recommendation (consistency over predictability). Redirects
   pass `addressing_feedback_ids=[fb_id]` so materialized work marks the item
   addressed (shell path maps it to files that actually landed).
   Mode-preference derivation extracted to `_edit_mode_settings()`, shared by
   both call sites.
3. **Context-limit resolution** (`core/context_manager.py`): root cause was
   setup-created model entries being `{}` — `get_model_config()` resolved the ID
   but returned no limits, falling to the unknown-model branch every iteration.
   Known-but-unlimited models now take the 100k default **silently**; only
   genuinely unknown references warn. `utils/setup.sh` prompts for max context
   tokens when adding a model and writes real entries
   (`max_context_tokens`, capped `max_output_tokens`) instead of `{}`;
   `example_config.json` verified to carry limits on every shipped model;
   CONFIGURATION.md documents the behavior.

Tests added: `test_seed_feedback.py` (3), `test_backlog_redirect_dispatch.py` (1),
`test_context_limit_resolution.py` (3, incl. regression that unknown models still
warn). Full normal gate: **623 passed**, ruff clean.

Manual smoke validation still pending (requires live endpoints): point
`project_directory` at a scratch git repo, set
`cli_mode.unattended.seed_tasks = ["Add a docstring to app.py"]`,
`duration_hours: 0.2`, run `python main.py`; expect
`🌱 Seed task registered as feedback item` on turn 1, a developer dispatch (or
immediate REDIRECT) on iteration 1 — not two rounds of `background` — and no
`⚠️ Unknown model` lines.

---

## Known Limitations / Follow-ups

1. **Shell escape**: agent bash runs with `cwd=worktree` but is not confined to it;
   only worktree-internal changes are collected. For enclave deployment, pair with
   external sandboxing (container/approved workstation controls).
2. **Reviewer sees evidence, not independent execution**: gate reviews the unified
   diff plus the session's own test run. A future hardening step could re-run
   `test_command` after materialize as a deployment-validator trigger.
3. **Legacy developer path still fails open**: `developer_edit.py` defaults to
   APPROVE on missing/unparseable reviewer verdicts (pre-existing behavior,
   unchanged in this round). Fold into the gate-consolidation item below.
4. **File deletions unsupported**: no governed delete op exists; deletions are
   logged and skipped.
5. **Consolidation opportunity**: reviewer-gate logic is duplicated between
   `developer_edit.py` and `shell_developer.py`; extract a shared helper once both
   paths stabilize — and make the legacy path fail closed at the same time.
6. **Real-model validation**: end-to-end runs against live endpoints (and tuning of
   prompts/limits) have not been performed yet.
7. **EndpointManager overlap**: if verification/model routing moves toward a
   LiteLLM-style layer someday, revisit overlap with `EndpointManager`.

---

## Rollback

Set `"developer": {"implementation": "edit_payload"}` in `config.json` (or remove
the key) to restore the legacy developer path without any code changes.

---

## Soak Process-Evaluation Round (2026-08-25)

Evidence source: HumanHaunt soak DB (`.PrizmForge/agents.db`), 12h unattended run.
Model/API flakiness was already addressed by the model-health round; this round
targets the *process* failures the same data exposed.

### Findings → Fixes

| # | Finding (evidence) | Fix |
|---|--------------------|-----|
| P1 | **Tasks never close**: 5/5 tasks `in_progress` after 12h. FINISH gate requires `critical_count == 0` but background reviewers keep posting HIGH items, so the gate never clears; when `max_turns` exhausts, no terminal status is written at all. | Grace-based finish gate (`finish_gate.high_grace_iterations`, default 3): CRITICAL always blocks; HIGH stops blocking after N consecutive FINISH attempts with pending HIGHs. Loop exhaustion / shutdown / exception now finalize the task: `completed` if files modified, else `stalled`, with a result string. |
| P2 | **Prioritizer error storm**: 1,071 API errors in bursts of up to 31/s — `_categorize_batch` swallows failures and the batch loop advances instantly, so an endpoint outage turns one cycle into ~17 rapid failing batches, every cycle. | Circuit breaker: per-cycle consecutive-failure counter; abort after 3 consecutive failed batches with exponential inter-batch backoff; cycle-level cooldown (5 min) before retrying categorization. Success resets the counter. |
| P3 | **jr_reviewer burn**: 147 "failed JSON validation after 3 attempts" events (~441 wasted calls). Empty responses (endpoint down) trigger identical retries with a stricter prompt that cannot help. | Empty/None response → no stricter-prompt retries (endpoint problem); single short backoff then break. Malformed JSON → keep stricter-prompt ladder but add 2 s between attempts. |
| P4 | **Category fragmentation**: 36 distinct `agent_feedback.category` values vs the prioritizer's canonical ~8 ("code_smell"/"code-smell", "test_coverage"/"test-coverage"/"coverage-gap"…), fragmenting grouping, dedup, and task-generation counts. | `normalize_category()` applied at the single write choke point (`save_agent_feedback`): spelling/separator canonicalization + alias map → {security, bug, performance, maintainability, documentation, architecture, style, test, other}; process categories (`seed_task`, `review_rejection`, `uncategorized`) pass through. |

Seed-task duplication seen in soak is already fixed by the cold-start round
(injection is idempotent per task).

### Verification
- New unit tests: category normalization, finish-gate decision, task
  finalization, prioritizer circuit breaker, reviewer empty-response discipline.
- Full gate green; ruff clean; mypy: zero new errors.


### Rotation follow-up (same round)

P2 originally parked the prioritizer for 5 minutes when the circuit opened.
Per review, idle parking was replaced with active resilience:

- **Per-model down windows**: after `down_streak` (2) consecutive failures a
  model is marked down for `down_base_seconds` (300 s), doubling per extra
  failure up to `down_max_seconds` (1800 s); any success clears it
  (`model_down_until`, `core/model_health.py`).
- **Enforced ranking tiers**: fallback/rotation ordering is now
  healthy → demoted → down; down models are skipped entirely while any
  healthy candidate exists and become the automatic recovery probe when all
  candidates are down.
- **Round-robin rotation**: on batch failure the categorizer advances to the
  next healthy `endpoint/model` (`_rr_next_model`) instead of re-dialing the
  same one — wrapping back to the original endpoint lands on its sibling
  model because the failed one is marked down.
- **Probe mode**: an open circuit no longer idles; each cycle runs exactly one
  batch through the rotation. A successful probe reopens the circuit; a
  failed one leaves it armed.

Verified: 9 new/updated unit tests; full gate 693 passed; ruff clean; mypy
zero new errors.
