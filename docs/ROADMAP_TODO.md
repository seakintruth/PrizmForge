# PrizmForge Roadmap / TODO

Single source of truth for open work items. Detailed design lives in the
linked documents; this file tracks status. Tick checkboxes as items land and
note the PR/commit.

Shipped sections were retired from this tracker on **2026-08-29** (their
design + acceptance evidence live in the linked docs — see `UNATTENDED_CLOSED_LOOP_PLAN.md`).

**Last updated:** 2026-08-29

---

## 0. Deployed state & PR map

- `main` @ `8be697f` = **roadmap stamp for Soak9 recompute pass 2 (a9–f9)**; functional tip `6d79e5d` — see §1 (2026-08-29).
- **Soak2 recompute pass 3 — mutation-path priority (d9/index hardening)**: Soak2 (2026-08-29 16:13–~20:30) exposed that d9 counted transport-failed sessions as stall → the developer froze for whole tasks while Resource Controller reasoned *"freeze: prioritizer + developer only"*. Fixed at root (see `## 1` pass-3 entry): failed/uncompleted sessions are **neutral**, genuine finished-zero-change sessions alone build the streak, and the latch **self-heals** every `rearm_after` iterations. README now documents **Operator Principle #1 — the mutation path is the most unblocked path**. Gate → **901 passed**.
- Previous stamps: `26566f3` = PR-95 residual batch (P1–P11 + W1–W8, §1); `198f6d8` = roadmap stamp (848 → 877); `cf30bee` = PR #96 (`fit/setup-accept-pip-path`) = current `origin/main`; `954cc14` = PR #95 merge base (Workstream A Phase 1).
- Full normal gate: **877 passed** at `26566f3`; recompute pass 2 re-verified after `bc11cef`, `4821f4d`, `ae822ed`, `70d1b95`, `1646e91`, `6d79e5d` → **897 passed** (`bash utils/run_tests.sh --normal -j 4`, +20 tests, 2026-08-29), ruff clean. Pre-commit hooks (black/isort/ruff/flake8/mypy) green on every commit.
- `main` is **10 commits ahead of `origin/main`** (`cf30bee`), all pending the next PR.

### Next PR — PR-95 residuals + Soak9 recompute pass 2 (P1–P11, W1–W8, a9–f9)

Opening from `main` (`8be697f`) against `base: cf30bee` (`origin/main`).

- **Title (suggested):** `fix: PR-95 residual batch (P1–P11, W1–W8) + Soak9 recompute pass 2 (a9–f9)`
- **Head:** `8be697f` · **Base:** `origin/main` (`cf30bee`) · 10 commits.
- **Part 1 — PR-95 residuals (`26566f3` + `198f6d8`):** P1–P11 review residuals (bare single-op payloads, delete-then-recreate dedupe, seed-feedback exclusion, data-window watermark, write-log ruff gate, task finalize on hard stops, `log_error` argument hygiene, failed-unlink visibility, shell turn success semantics, honest reviewer-call accounting, non-hollow test fixes) and W1–W8 soak hardening (WIP-shipping on early exit, archivist batches + honest retry, burn-rate escalation, deferred pool start, developer lane isolation, review-queue caps, intake-soft pool backoff). Gate 848 → 877.
- **Part 2 — Soak9 recompute pass 2 (`bc11cef` … `8be697f`):** a9 archive-row prune, b9 strict JSON archive contract, c9 foreground-session backoff for support workers, d9 no-progress developer guard, e9 prioritizer post dedup, f9 background transport-error coalescing — full detail per item in §1. Gate 877 → 897 (+20 tests).
- **Merge notes:** only code-churn pan is the shared `agents/base.py` `call_agent` failure block (f9) — low collision risk; test files are additive (`test_worker_utils.py`, `test_task_runner.py`, `test_prioritizer_phases.py`, `test_archivist_context.py`).
- **Verification:** full normal gate `bash utils/run_tests.sh --normal -j 4` = **897 passed**; `ruff check .` clean; pre-commit hooks green on every commit. No live-endpoint dependencies (all in-process, hermetic).

---

## 1. Merged residuals — PR #95 follow-ups (P-series) + soak recompute (W-series)

Both series were re-derived during the 2026-08-28/29 soak review of the PR #95
merge. **Root cause under test:** Soak9 emitted a single 1155-event developer
burst (all files × all agents) that shared the core loop's `RateLimiter` and
`TokenBudget` → the 429 flood that stalled the whole run.

Status: **SHIPPED & MERGED** in `26566f3` (2026-08-29, gate 848 → 877).

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

### Soak9 recompute pass 2 (a9–f9) — non-overlapping corrections

Derived from the Soak9 branch inspection (the run executed pre-`26566f3`
code); each fix was vetted to NOT overlap the P/W series above. **Root cause
under test:** the run's shared rate-limited endpoint starved the foreground
developer session while the support pool (prioritizer/archivist/reporter)
kept streaming LLM cycles into it, and the archivist's conversation-history
pipeline re-archived the same rows forever with prompts that had no JSON
contract.

Status: **SHIPPED & MERGED** `bc11cef` … `6d79e5d` (2026-08-29).

- [x] **a9 — Prune `conversation_history` on archive save** — saved conversation batches are deleted in the same transaction (mirroring the message-bus path `DELETE FROM messages`); unsaved (junk) batches keep their rows for re-archive. Soak evidence: 6 `archived_context` snapshots with repeated identical `turn_range` starts and ~110k-char prompts. Tests: `test_archivist_context.py`.
- [x] **b9 — Strict JSON output contract in archive prompts** — both prompt builders end with `Respond with ONLY this JSON … {"summary": …, "key_decisions": […]}`; keys match `_parse_archive_response`. Soak evidence: 12.6k–28.4k-token prose replies that the tolerant parser could not recover ("Expecting value: line 1 column 1" kept 201/206/209 msg + 597/614 conv batches unarchived). Tests: `test_archivist_context.py`.
- [x] **c9 — Support workers yield to an active foreground session** — a counter-based `foreground_session_guard()` wraps `session.run` in the shell developer; prioritizer/archivist/reporter loops hold off via `hold_while_foreground_session_active()` (5s probe, still responsive to `stop()`), so the foreground session gets the shared endpoint. Complements W6 lane isolation (feedback agents only). Tests: `test_worker_utils.py`.
- [x] **d9 — No-progress developer loop guard** — `NoProgressLoopGuard` counts consecutive zero-change developer turns (same signal `_finalize_task` uses for "stalled"); past `NO_PROGRESS_TURNS_THRESHOLD` (3) it posts one HIGH stall summary and redirects developer decisions to background discovery (FAILSAFE-style), including the backlog-mode redirect. Any materialized file resets the streak. Soak evidence: task_002/003/005 `files_modified=0` with "📋 Decision: developer" and "Work: 0.0s" every turn. Tests: `test_task_runner.py`.
- [x] **e9 — Dedup unchanged prioritizer posts** — `_post_results` keeps a ranked-set signature and skips reposting when unchanged (items still marked processed). Soak evidence: identical HIGH "🎯 PRIORITIZED FEEDBACK" posts every ~60–90s (13:07:57→13:14:57). Tests: `test_prioritizer_phases.py`.
- [x] **f9 — Coalesce background-worker transport-error telemetry** — `TransportErrorCoalescer` logs ONE HIGH per (agent, category) per 5-min window with repeats at MEDIUM, applied only to background-pool agents via `call_agent`. Soak evidence: 275 HIGH "failed to return a response" rows (prioritizer 173). Tests: `test_worker_utils.py`.

### Soak2 recompute pass 3 (2026-08-29) — mutation-path priority (d9 hardening)

Soak2 ran the fixed build (`89b684c`) and surfaced a regression in **d9**: under
endpoint degradation (opencode `key_locked` ~1h, openrouter unavailable/
rate-limited), 10 of 11 tasks stalled `files_modified=0` because the no-progress
guard counted **transport-failed shell sessions** (`LlmUnavailable`,
`RepeatedFormatError` — see trajectory files `task_011-turn1..3`) as zero-change
turns. 3 dead sessions latched the guard, which then held the developer for the
remainder of each task — directly contradicting Resource Controller's own freeze
reasoning ("prioritizer + developer only"). The mutation path — the point of the
loop — was the LEAST unblocked path.

Status: **FIXED** at root (this PR, gate 897 → 901).

- [x] **d9/MU — The mutation path is the most unblocked path** — `_is_uncompleted_session` classifies a developer turn as NEUTRAL when the session never completed (any status other than `success`/`rejected`, except the genuine "session finished but produced no file changes" which still counts); `_record_developer_progress` is fed the structured `mut` result at all three dispatch sites (`task_runner.py` shell, edit_payload, backlog redirect). The `NoProgressLoopGuard` latch now **self-heals**: `record_cycle()` re-arms it every `rearm_after` (default = threshold) iterations, so a recovered endpoint always gets a developer retry. Backlog-redirect branch no longer pauses the developer on failure-derived latches. README documents **Operator Principle #1 — the mutation path is the most unblocked path** under Core Philosophy. Tests: `TestNoProgressGuard` in `test_task_runner.py` (4 new: failed-session-neutral, genuine-finished-still-latches, success-clears, latch-rearms). Gate → **901 passed**, ruff clean.

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

Review-flagged structural items. **Decision (2026-08-29): FOLDED INTO BACKLOG AS TECH-DEBT** — each is small, bounded, and independently scoped; a future sprint can pick them up without a dedicated design doc.

- [ ] **`project_files` refactor** — normalize file metadata/index rows and their update paths.
- [ ] **Standardize errors** across file_editing — single error shape/status vocabulary instead of per-module strings.
- [ ] **120s-sleep behavior** — the legacy fixed sleep in the editing loop: replace with event-driven wait or configurable strategy.
- [ ] **CLI command leakage** — audit `cli.commands` for shelled-out / ungoverned commands that bypass the governed edit path.
- [ ] **`__init__.py` cleanup** — remove obsolete re-exports in `file_editing/__init__.py`.

### 4.3 UNATTENDED plan §15 open decisions (parked, with defaults)

1. Hook failure: fix-forward (leave disk dirty; CRITICAL fix) unless `git.revert_on_hook_failure` set — current behavior is fix-forward.
2. Create-file policy: clean relative paths OK; add prefix policy only if junk root files recur.
3. `config.json` as agent edit target: gitignored config stays human-only.
4. Reviewer sees hook output: developer primary; orchestrator summary; reviewer optional.
5. API/network failure streaks: pause + single CRITICAL summary after N consecutive failures (shipped — `NetworkBusyLoopGuard`, §6 retired).