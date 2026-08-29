# PrizmForge Roadmap / TODO

Single source of truth for open work items. Detailed design lives in the
linked documents; this file tracks status. Tick checkboxes as items land and
note the PR/commit.

Shipped sections were retired from this tracker on **2026-08-29** (their
design + acceptance evidence live in the linked docs — see `UNATTENDED_CLOSED_LOOP_PLAN.md`).

**Last updated:** 2026-08-29

---

## 0. Deployed state & PR map

- `main` @ `cf30bee` = merge of PR #96 (`fit/setup-accept-pip-path`).
- Previous `main` stamp: `954cc14` = merge of PR #95 (Workstream A Phase 1, git/pre-commit closed loop) — the merge base the §1 residuals sit on.
- Full normal gate: **848 passed** (`bash utils/run_tests.sh --normal -j 4`) before the §1 batch; that batch's proofs live in `tests/unit/` (referenced per item) and the re-run is logged on merge.

---

## 1. Merged residuals — PR #95 follow-ups (P-series) + soak recompute (W-series)

Both series were re-derived during the 2026-08-28/29 soak review of the PR #95
merge. **Root cause under test:** Soak9 emitted a single 1155-event developer
burst (all files × all agents) that shared the core loop's `RateLimiter` and
`TokenBudget` → the 429 flood that stalled the whole run.

Status: **implemented in working tree on top of `cf30bee`**; shippable as a follow-up PR.

### P-series (review residuals)

- [x] **P1 — Bare single-op payloads** — `EditPayload.model_validate` wraps a bare single op dict (no `operations` key); `developer_edit._normalize_payload` handles a bare `type` payload, mapping `create_file`/`full_replace` → `MODE_FULL_REPLACE` and `apply_diff` → `MODE_DIFF`; empty-ops payload raises `ValueError`. Tests: `test_developer_edit_helpers.py`, `TestBareSingleOpPayload` in `test_proposal_builder_regressions.py`.
- [x] **P2 — Delete-then-recreate row dedupe** — `proposal_builder._get_or_create_file_id` resurrects a soft-deleted (`is_deleted=1`) file row instead of creating a duplicate; no `is_deleted` filter in the lookup. Tests: `TestDeleteThenRecreate` in `test_proposal_builder_regressions.py`.
- [x] **P3 — Seed feedback excluded from backlog/backpressure** — seed rows (`category = 'seed_task'`) no longer count toward `backlog_metrics.unaddressed`, the task_runner COUNT/top/next-item queries, or RC `_check_feedback_backlog` tier escalation (190 real rows ≠ freeze even with 220 rows on disk). Tests: `test_backlog_growth.py`.
- [x] **P4 — Diagnostic data window watermark** — `_print_data_window` reports the newest record timestamp per table group with correct ordering columns (events `ts`, file_write_log `completed_at`, tasks `COALESCE(completed_at, started_at)`, errors `timestamp`, edit_proposals `created_at`) and `T`-normalized rendering. Tests: `test_query_developer_responses.py`.
- [x] **P5 — Write-log reflects the ruff gate** — the `file_write_log` row flips to `status='lint_failed'` when the in-process ruff pre-check fails (single real status, closed loop with the `edit.lint_failed` event + CRITICAL feedback). Tests: `test_lint_precheck.py`.
- [x] **P6 — Task finalize on hard stops** — `task_runner` finalizes the task (reason `"token budget exhausted"` / `"KeyboardInterrupt"`) on budget exhaustion and Ctrl-C instead of leaving an orphaned run.
- [x] **P7 — `log_error` argument-order + kwarg hygiene, severity-first** — every `log_error(severity, …)` call site fixed (writer, editing, proposal_builder, parallel_workers); the invalid `file_id=` keyword moved into `details={"file_id": …}`; `agents/base.py` was already kwargs-correct.
- [x] **P8 — Failed disk unlink never hides** — `_delete_file_from_disk` OSError (e.g. unlink on a directory, permissions) now returns an `error` result so materialize logs a write-log error row instead of leaving the governed store deleted with the disk file alive. Tests: `test_delete_file_op.py`.
- [x] **P9 — Shell turn success = EVERY gate landed** — a mixed approve/reject session returns `status="error"` (never `success`); all-rejected → `"rejected"`. Tests: `test_shell_developer.py`.
- [x] **P10 — Reviewer call accounting is honest** — `ReviewerVerdict.calls_used` (1 normal / 2 after same-prompt retry) surfaced on the verdict; both `developer_edit.py` and `shell_developer.py` increment `reviewer_calls` from the verdict. Tests: `test_reviewer_gate.py`.
- [x] **P11 — Non-hollow test fixes** — `test_query_developer_responses.py` tautology (`or True`) → real assertions; `test_network_busy_loop.py` exact stream-idle semantics (first record after the pause wins, later ones don't); `test_lint_precheck.py` dead `if False else` branch removed + failure marker made hermetic via a monkeypatched `subprocess.run`.

### W-series (soak recompute — burst/429 protection)

- [x] **W1 — Early-exit sessions still ship their WIP** — a shell session stopped by step-limit/user-signal/transport now materializes its worktree edits through the reviewer gate; the real exit status (`session_exit`) is preserved for the loop-guard. Tests: `test_shell_developer.py`.
- [x] **W2 — Archivist batches + honest retry** — archiving batches at `_ARCHIVE_BATCH_SIZE = 20`; one same-prompt retry only on non-empty unparseable output; an empty transport response is never retried; bus rows are deleted strictly per saved batch (a junk batch keeps its originals). Tests: `test_archivist_context.py`.
- [x] **W3 — Burn-rate escalation** — RC `optimize()` throttles to MODERATE when `current_burn_rate > rc.burn_rate_warning_per_minute` (default 40_000 tok/min; Soak9 burned 44,560) even at a healthy daily budget % — the burn is what trips the shared per-endpoint budget. Tests: `test_backlog_growth.py`.
- [x] **W4 — (folded into W5/W6)** — burst suppression is delivered by deferred pool start + lane isolation rather than a new throttle decision.
- [x] **W5 — Deferred background pool start** — the eager `agent_pool.start()` at cycle entry is gone; the pool starts only after the first successful materialize or after 2 turns (`_ensure_pool_started`), idempotent + FakePool-safe. Tests: `test_task_runner.py`.
- [x] **W6 — Developer lane isolation** — during a shell session the feedback agents are paused (`set_active_agents([])`) and the previous filter (None = all-active resume) is restored in `finally`; support workers are never touched. Tests: `test_parallel_workers.py`.
- [x] **W7 — Initial-review queue caps** — both initial-review and modified-file queues are `LIMIT`-capped by `background_agents.initial_review_max_files` (default 25) instead of enqueueing every project file per agent. Tests: `test_parallel_workers.py`.
- [x] **W8 — Intake-soft pool backoff** — `start()` bumps the feeder to 120s when `event_queue.qsize() > background_agents.intake_soft_batch` (default 100), a pool-level slack valve that cannot deadlock a queued batch (unlike a `ThrottleDecision([])`).

---

## 2. Unattended closed-loop hardening — open residuals only

All shipped workstreams (A–F) are recorded in `docs/UNATTENDED_CLOSED_LOOP_PLAN.md`; the tracker keeps only what is still open.

- [ ] **Live failing-hook smoke run on a copy** — run with a deliberately failing hook; confirm CRITICAL feedback → developer fix-forward proposal → materialized and addressed, all visible in events/errors/feedback. **Blocked: live runtime/endpoints** (in-process failure paths have deterministic unit proofs in `tests/unit/test_git_closed_loop.py`).
- [ ] **PR #94 body nit** (manual GitHub edit): body still cites `tests/unit/test_writer_git_closed_loop.py`; should cite `tests/unit/test_git_closed_loop.py`. **Blocked: GitHub/manual editor access** (cosmetic, merged-PR body).

---

## 3. Mini-swe agent — open items only

Implemented (beta), review-hardened, cold-start + soak process-eval rounds merged. Open items:

- [ ] **Real-model end-to-end validation + tuning** — live endpoints, prompt/limit tuning. **Blocked: live endpoints.**
- [ ] **Manual cold-start smoke** — seed task consumed on turn 1 (no `background` for two rounds), no `⚠️ Unknown model` lines. **Blocked: live endpoints.**
- [ ] **Enclave sandboxing** — shell runs are not confined to the worktree (container/approved-workstation controls for enclave deployment). **Blocked: operational/container controls.**
- [ ] **Optional hardening: post-materialize `test_command` re-run** — **Decision: intentionally deferred** (Phase-4 test-driven loop + the session's own pre-proposal `test_command` already gate every edit; a mid-session full re-run risks long/flaky hangs with no closed loop consuming it). The §7.2 in-process `ruff` pre-check ships the cheap fast-feedback gate instead. Revisit only if a deploy-time validator becomes a requirement.

---

## 4. Annexes (strategic / parked decisions)

### 4.1 Forge Federation strategy — `Federation/Plan.md`

Active northstar: Stage 0 (current single-Territory system) → Stage 1 (enhanced
single-Territory, next) → Stage 2 (multi-Territory, future). Operates via short,
YAGNI-focused sprints with bounded, measurable experiments.

### 4.2 `report/plan.md` file_editing structural refactors

Review-flagged structural items that "remain open": `project_files` refactor,
standardizing errors, 120s-sleep behavior, CLI command leakage, `__init__.py` cleanup.
Decision needed: fold into backlog as tech-debt or drop as stale.

### 4.3 UNATTENDED plan §15 open decisions (parked, with defaults)

1. Hook failure: fix-forward (leave disk dirty; CRITICAL fix) unless `git.revert_on_hook_failure` set — current behavior is fix-forward.
2. Create-file policy: clean relative paths OK; add prefix policy only if junk root files recur.
3. `config.json` as agent edit target: gitignored config stays human-only.
4. Reviewer sees hook output: developer primary; orchestrator summary; reviewer optional.
5. API/network failure streaks: pause + single CRITICAL summary after N consecutive failures (shipped — `NetworkBusyLoopGuard`, §6 retired).