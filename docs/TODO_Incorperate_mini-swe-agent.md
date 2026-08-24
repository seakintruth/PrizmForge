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

## Known Limitations / Follow-ups

1. **Shell escape**: agent bash runs with `cwd=worktree` but is not confined to it;
   only worktree-internal changes are collected. For enclave deployment, pair with
   external sandboxing (container/approved workstation controls).
2. **Reviewer sees evidence, not independent execution**: gate reviews the unified
   diff plus the session's own test run. A future hardening step could re-run
   `test_command` after materialize as a deployment-validator trigger.
3. **File deletions unsupported**: no governed delete op exists; deletions are
   logged and skipped.
4. **Consolidation opportunity**: reviewer-gate logic is duplicated between
   `developer_edit.py` and `shell_developer.py`; extract a shared helper once both
   paths stabilize.
5. **Real-model validation**: end-to-end runs against live endpoints (and tuning of
   prompts/limits) have not been performed yet.
6. **EndpointManager overlap**: if verification/model routing moves toward a
   LiteLLM-style layer someday, revisit overlap with `EndpointManager`.

---

## Rollback

Set `"developer": {"implementation": "edit_payload"}` in `config.json` (or remove
the key) to restore the legacy developer path without any code changes.
