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
