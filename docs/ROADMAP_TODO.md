# PrizmForge Roadmap / TODO

Single source of truth for open work items. Detailed design lives in the
linked documents; this file tracks status. Tick checkboxes as items land and
note the PR/commit.

**Last updated:** 2026-08-28

---

## 0. Deployed state & PR map

- `main` @ `1ab2f08` = merge of PR #94 (Workstream A Phase 1, git/pre-commit closed loop).
- PR #93 (`feat/model-health-tracking`) merged into `main` (`f267b5a`) — Workstream F partial.
- PR #94 branch `feat/workstream-a-git-closed-loop` tip == merged tip (`c6a4a0e`); new work should branch from `main`.
- PR #83 (`backlog-proccessing-correction`) **CANCELLED** — superseded; see §5 for the only items from its review that never landed on `main`.
- Full normal gate: **834 passed** (`bash utils/run_tests.sh --normal -j 4`); pre-commit clean; suite passes with no `config.json` present. (Progression: 724 → 744 → 764 → 778 → 787 → 812 → 834.)

---

## 1. Gitignore-aware file filtering (from `todo-db_init` proposal)

**Design:** `docs/todo-db_init_should_ignore_gitignore_patterns.md` (full spec: new `core/gitignore.py`, integration patches, verification steps)

Goal: file indexing, truncation candidates, and consolidation must respect `.gitignore`
so caches (`__pycache__`, `.pytest_cache`, …), reports, and secrets (`api_key.json`)
are never treated as edit/truncation targets.

Related: `UNATTENDED_CLOSED_LOOP_PLAN.md` §7 Workstream E (repo policy awareness).

- [x] Add `core/gitignore.py` (`load_gitignore_spec`, `should_ignore_by_gitignore`, gitwildmatch via `pathspec`)
- [x] Integrate into `core/file_operations.py` — `should_ignore_file()` applies hardcoded ignores + `.gitignore`; `sync_file_to_database()` short-circuits on ignored paths
- [x] Integrate into `core/symbol_index.py` — `rebuild_project_symbols()` skips gitignored files
- [x] Integrate into `utils/consolidate.py` — `_is_ignored_path()` also consults `.gitignore`
- [x] Add `pathspec>=0.12.1` to `requirements.txt` and `requirements-dev.txt`
- [x] Tests: `tests/unit/test_gitignore.py` (19 passed)

Status: **DONE** (2026-08-22).

---

## 2. Test isolation: remove live `config.json` dependency

Fixed (2026-08-22): extended `tests/conftest.py` so `get_config` is patched at
every import site (core/*, agents/*, workflow, cli.commands, interactive),
added a safe `token_budget` default, and reset `interactive._shutdown_requested`
per test. Full suite now passes with no `config.json` present: **602 passed** at
the time; **724 passed** on the current gate.

- [x] Audit which tests call `core.config.get_config()` / `load_config()` against disk
- [x] Patch all local-binding sites in `_GET_CONFIG_PATCH_TARGETS`
- [x] Full `pytest tests` green with no `config.json` present

---

## 3. Unattended closed-loop hardening

**Plan:** `docs/UNATTENDED_CLOSED_LOOP_PLAN.md` (workstreams A–F with acceptance criteria).

Delivery order per §9:

- [x] **Phase 0 — Stabilize copy under test (operator)** — done during the 2026-08-25 soak (poison files reverted, DB + git log snapshotted).
- [x] **Phase 1 — Workstream A: git/pre-commit closed loop** — **SHIPPED & MERGED** in PR #94 (`1ab2f08` / `c6a4a0e`):
  - [x] Capture subprocess output in git path (`utils/git_operations.py::git_commit` → `{ok, attempted, code, stage, stdout, stderr, file_path, commit_hash}`; `stage` ∈ add|commit|rev-parse|timeout|disabled)
  - [x] Fail materialize on non-zero hook when git enabled (`materialize_proposal()` → `status="git_failed"`, never `success`+side field; keeps first failure on multi-file)
  - [x] CRITICAL feedback (`edit.git_failed` event) + `errors` row; deduped by `file_event_id=proposal_id`; `log_error` written after the write transaction commits
  - [x] Stop emitting unqualified `edit.materialized` success when git failed
  - [x] Tests: 12 tests in `tests/unit/test_git_closed_loop.py` (incl. backlog-drain + file-id rules proofs)
  - [x] Preserve on latest `main`: hook-failure feedback row must be picked up by fetch_top_feedback (CRITICAL ranks first) and drained to developer. — Proofs: `test_git_hook_critical_drains_before_high` (CRITICAL drains ahead of HIGH + `apply_backlog_overrides` redirects background→developer) and `test_multiple_critical_rows_pick_newest_unaddressed`.
  - [x] Confirm dump shows the failure — FULL DIAGNOSTIC DUMP now includes a git/hook-outcomes section (`show_git_failures`) fed by `edit.git_failed` events (Workstream F).
- Phase 1 residuals (carried forward):
  - [ ] **Live failing-hook smoke run on a copy** (next action): run with a deliberately failing hook, confirm CRITICAL feedback → developer fix-forward proposal → materialized and addressed, all visible in events/errors/feedback. **Blocked: live runtime/endpoints** (same class as the mini-swe cold-start smoke, §4; the in-process failure paths have deterministic unit proofs in `tests/unit/test_git_closed_loop.py`).
  - [x] **Failure visible in FULL DIAGNOSTIC DUMP** — shipped via `show_git_failures` in the FULL DIAGNOSTIC DUMP (Workstream F §8.2); confirmed by dump tests; the live-hook end-to-end confirmation is covered by the smoke residual above.
  - [ ] **PR #94 body nit** (manual GitHub edit): body still cites `tests/unit/test_writer_git_closed_loop.py`; should cite `tests/unit/test_git_closed_loop.py`. **Blocked: GitHub/manual editor access** (cosmetic, merged-PR body).
- [x] **Phase 2 — Workstream D: edit payload / developer-phase validation alignment** (§4): shared op-schema checks in validator (`validate_operation` in `file_editing/edit_payload.py`); reject `guid` as type; require find/replace fields; fuzz tables. SHIPPED. Gate: 744 → 764.
- [x] **Phase 3 — Workstream B: backlog backpressure & consolidation tiers** (§5): config tiers (`feedback.tiers`), dedupe on insert (`dup_key`/`dup_count` + `save_agent_feedback`), earlier agent pause (tier-based RC + BACKGROUND redirect at hard/freeze), stuck-id handling (`targeted_count`/`stuck`). SHIPPED. Gate: 764 → 778.
- [x] **Phase 4 — Workstream C: post-materialize targeted re-verify** (§6): bounded re-queue on success (one high-priority `FileChangeEvent` per touched path via `workflow/post_materialize.py`), parse hook paths → developer targets (`parse_hook_cited_files` + `HOOK CITED FILES` in git-failure feedback), auto-address on success (existing). SHIPPED. Gate: 778 → 787.
- [x] **Phase 5 — Workstream E + F: repo policy awareness & observability polish** (§7–§8). E gitignore shipped (§1); E secrets/caches excluded from agent file lists + truncation candidates + indexer; E env card (pre-commit presence → developer context) shipped; F `file_write_log` timestamps populated; F reporter run metrics (materialize ratio, fallback rate, git_fail, circuit opens); F dump git/hook outcomes section; F §8.4 circuit-breaker surface event; §7.2 optional in-process ruff pre-check (config `file_editing.in_process_ruff_check`, `lint_failed` closed loop). SHIPPED (E/F observability part). Gate: 787 → 812. No open residuals.
- Open decisions §15 (5 items) — parked; see §7 annex.

---

## 4. Mini-swe agent (developer.implementation = "shell")

**Design/status:** `docs/TODO_Incorperate_mini-swe-agent.md` — implemented (beta), review-hardened, cold-start + soak process-eval rounds merged (gates 616 → 623 → 693). Feature branch merged into `main`.

- [ ] **Real-model end-to-end validation + tuning** (highest): live endpoints, prompt/limit tuning. **Blocked: live endpoints.**
- [ ] **Manual cold-start smoke** (pending): seed task consumed on turn 1 (no `background` for two rounds), no `⚠️ Unknown model` lines. **Blocked: live endpoints.**
- [x] **Reviewer gate consolidation + legacy fail-closed**: shared `workflow/reviewer_gate.py` (`parse_reviewer_verdict` / `handle_reviewer_rejection` / `post_reviewer_suggestions`) used by both `shell_developer.py` and `developer_edit.py`; missing/unparseable verdict → REJECT (historical APPROVE default removed). Tests: `tests/unit/test_reviewer_gate.py`.
- [x] **Single same-prompt reviewer retry on infra rejects** (soak evidence 2026-08-28): a correct SQL-injection fix was shelved on one blank reviewer stream. `request_review_verdict` retries once (same prompt, cap 2 calls) only for empty/unparseable/unknown decision; a semantic REJECT or `None` transport failure never retries. R4 row of the soak table; tests: `tests/unit/test_reviewer_gate.py::TestRequestReviewRetry`.
- [x] **Governed file deletions**: governed `delete_file` operation added end-to-end — `DeleteFile` schema op (shared `validate_operation` gate), `apply_delete_file` (flips store `is_deleted`), materialize removes the disk file + `file_write_log` status `deleted` + deletion-aware `git add -A`, and shell `D`-status changes map to `delete_file` instead of being skipped. Tests: `tests/unit/test_delete_file_op.py`.
- [ ] **Enclave sandboxing**: shell runs are not confined to the worktree (container/approved-workstation controls for enclave deployment). **Blocked: operational/container controls.**
- [ ] **Optional hardening**: re-run `test_command` after materialize (overlaps Phase 4 / Workstream C). **Decision: intentionally deferred** — Phase 4's test-driven loop + the session's own pre-proposal `test_command` already gate every edit; a post-materialize full re-run risks long/flaky hangs mid-session with no closed loop consuming it. The §7.2 in-process `ruff` pre-check ships the cheap fast-feedback gate instead (see line 78). Revisit only if a deploy-time validator becomes a requirement.

---

## 5. PR 83 residuals → new work (PR 83 cancelled)

PR #83 (`backlog-proccessing-correction`) is **cancelled** — its commit history rewrote
`developer_edit.py` wholesale and shipped restore junk; almost everything else from its
review is already on `main` (full `developer_edit.py` incl. PR #94 `git_failed`, backlog →
developer + `addressing_feedback_ids`, RC `BACKLOG_PROCESSING` dispatch, seed feedback;
the 6-tuple `next_items` question is N/A — main's follow-up query is consistently 5 columns).
The three items below did **not** land and are the replacement scope.

- [x] **[P1 — Safety-critical] Legacy reviewer fails closed** — `workflow/developer_edit.py`: reviewer gate now uses shared `parse_reviewer_verdict` (via `core/json_parser`) and defaults **REJECT** on empty/non-JSON/missing `decision` (APPROVE default removed). Tests: `tests/unit/test_reviewer_gate.py`.
- [x] **[P2] Remove per-call runtime `ALTER TABLE`** — per-create `ADD COLUMN` loop removed from `workflow/proposal_builder.py`; column ensure moved to one-time `_migrate_schema` (`core/db.py` `_ensure_column`).
- [x] **[P3] Batch GUID hash capture** — `_capture_hashes_for_operations` now fetches all hashes in a single `WHERE line_guid IN (...)`.

---

## 6. API/network resilience (Workstream F remnants)

Largely **shipped** via PR #93 (`f267b5a`) and the mini-swe soak round:

- [x] Per-model down windows + round-robin rotation + probe mode + enforced ranking tiers (`core/model_health.py`)
- [x] Prioritizer circuit breaker (3 consecutive failed batches, exponential backoff, cycle cooldown)
- [x] Reviewer empty-response discipline (no stricter-prompt retries on endpoint outage)
- [x] Category normalization at the `save_agent_feedback` write choke point

- [x] Circuit-breaker metrics surfaced: prioritizer publishes `prioritizer.circuit_open` events; reporter prompt/stats include circuit-open count
- [x] Residual (§8.4): avoid busy-looping when sequential agents fail network repeatedly — `NetworkBusyLoopGuard` (workflow/task_runner.py) pauses scheduling for one iteration after 2 consecutive network-grade agent failures and surfaces ONE CRITICAL summary per outage episode (§15 decision 5). Tests: `tests/unit/test_network_busy_loop.py`.
- [x] Soak round #2 (2026-08-28) observability: dump lists all proposals + data watermark; `log_error` persists `agent_name`; archivist never archives unparseable output (keeps originals). Evidence + R1–R5 table in `docs/TODO_Incorperate_mini-swe-agent.md` §"Soak Process-Evaluation Round #2".

---

## 7. Documentation upkeep (continuous)

- [x] Keep `UNATTENDED_CLOSED_LOOP_PLAN` status header current as phases land (2026-08-28: header swept — Workstreams A–F all shipped, §15 decisions recorded, §16 current; Phase-1 sweep for §3.7/§9 done earlier)
- [x] Add short pointer from `docs/architecture.md` (Error/Observability or "Unattended verification") → `UNATTENDED_CLOSED_LOOP_PLAN.md` (§16) — already present: architecture §"Unattended Closed-Loop Hardening" links the plan; verified 2026-08-28
- [x] Retire `tests/doc_todo_architecture.md` and `tests/doc_todo_multi_platform_ci_cd.md` — link sweep clean, stubs deleted; content lives in `tests/README.md` + `tests/LLM_CONTEXT.md`.

---

## 8. Annexes (strategic / parked decisions)

### 8.1 Forge Federation strategy — `Federation/Plan.md`

Active northstar: Stage 0 (current single-Territory system) → Stage 1 (enhanced
single-Territory, next) → Stage 2 (multi-Territory, future). Operates via short,
YAGNI-focused sprints with bounded, measurable experiments. Not tracked as discrete
todos here beyond the single-Territory improvements already captured in §3–§6.

### 8.2 `report/plan.md` file_editing structural refactors

Review-flagged structural items that "remain open": `project_files` refactor,
standardizing errors, 120s-sleep behavior, CLI command leakage, `__init__.py` cleanup.
Decision needed: fold into backlog as tech-debt or drop as stale.

### 8.3 UNATTENDED plan §15 open decisions (parked, with defaults)

1. Hook failure: fix-forward (leave disk dirty; CRITICAL fix) unless `git.revert_on_hook_failure` set — current behavior is fix-forward.
2. Create-file policy: clean relative paths OK; add prefix policy only if junk root files recur.
3. `config.json` as agent edit target: gitignored config stays human-only.
4. Reviewer sees hook output: developer primary; orchestrator summary; reviewer optional.
5. API/network failure streaks: pause + single CRITICAL summary after N consecutive failures (see §6).