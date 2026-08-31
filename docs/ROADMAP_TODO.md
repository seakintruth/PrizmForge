# PrizmForge Roadmap / TODO

Single source of truth for open work items. Detailed design lives in the
linked documents; this file tracks status. Tick checkboxes as items land and
note the PR/commit.

Shipped sections were retired from this tracker on **2026-08-29** (their
design + acceptance evidence live in the linked docs — see `UNATTENDED_CLOSED_LOOP_CAPABILITIES.md`).

**Last updated:** 2026-08-31

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

All shipped workstreams (A–F) are recorded in `docs/UNATTENDED_CLOSED_LOOP_CAPABILITIES.md`; the tracker keeps only what is still open.

- [ ] **Live failing-hook smoke run on a copy** — run with a deliberately failing hook; confirm CRITICAL feedback → developer fix-forward proposal → materialized and addressed, all visible in events/errors/feedback. **Blocked: live runtime/endpoints** (in-process failure paths have deterministic unit proofs in `tests/unit/test_git_closed_loop.py`).
- [ ] **PR #94 body nit** (manual GitHub edit): body still cites `tests/unit/test_writer_git_closed_loop.py`; should cite `tests/unit/test_git_closed_loop.py`. **Blocked: GitHub/manual editor access** (cosmetic, merged-PR body).
- [ ] **Ignored-path handling in the git closed loop** — a git-governed target that is gitignored (e.g. `config.json`) needs an explicit branch: skip git or fail with a clear "path is gitignored" message, never silent success. **Default parked (§5.3 decision 3: gitignored config stays human-only).** Source: `docs/UNATTENDED_CLOSED_LOOP_CAPABILITIES.md` §3.7.
- [ ] **Diagnostic dump shows a forced-hook-failure path** — at least one non-success path visible under events/errors after an intentional hook failure; the `git_fail` counter is already present in task summaries. **Blocked: Workstream F dump sections (`docs/UNATTENDED_CLOSED_LOOP_CAPABILITIES.md` §8.2).**

---

## 3. Mini-swe agent (shell developer) — shipped + open items

### Shipped (2026-08-23 → 2026-08-28; gates 616 → 623 → 693 → 724, plus 2026-08-29 closed-loop residuals)

**SHIPPED & MERGED**: native mini-swe-agent port as the shell developer
(`workflow/shell_developer.py`, MIT attribution + material differences in
`THIRD_PARTY_NOTICES.md`). Original 5-item plan landed in full:

1. Native port of the mini-swe-agent core loop (worktree + bash).
2. Disposable `git worktree` isolation per session; real bash edits + post-session `test_command` verification.
3. Session output converted to governed EditPayload proposals → Reviewer → materialize.
4. Wired into the task loop behind `developer.implementation` (`"shell"` default, `"edit_payload"` legacy fallback).
5. Packaging/tooling (`setup.sh` git prereq; `export_project_zip.py` excludes runtime artifacts).

Capability/operator runbook: `docs/mini_swe_agent.md`. Rollback: `developer.implementation: "edit_payload"` (no code change).

### Open items

- [ ] **Real-model end-to-end validation + tuning** — live endpoints, prompt/limit tuning. **Blocked: live endpoints.**
- [ ] **Manual cold-start smoke** — seed task consumed on turn 1 (no `background` for two rounds), no `⚠️ Unknown model` lines. **Blocked: live endpoints.**
- [ ] **Enclave sandboxing** — shell runs are not confined to the worktree (container/approved-workstation controls for enclave deployment). **Blocked: operational/container controls.**
- [ ] **Optional hardening: post-materialize `test_command` re-run** — **Decision: intentionally deferred** (Phase-4 test-driven loop + the session's own pre-proposal `test_command` already gate every edit; a mid-session full re-run risks long/flaky hangs with no closed loop consuming it). The §7.2 in-process `ruff` pre-check ships the cheap fast-feedback gate instead. Revisit only if a deploy-time validator becomes a requirement.
- [ ] **EndpointManager / LiteLLM-overlap revisit (parked)** — if verification/model routing ever moves toward a LiteLLM-style layer, revisit `EndpointManager` overlap (mini-swe follow-up #7; see `docs/mini_swe_agent.md`). **Blocked: no such routing layer planned.**

---

## 4. Post-merge feat/ramp-up residuals (2026-08-30) — open items

`feat/ramp-up` merged `main` (`11bfc02`, includes PR #100 soak/setup, #103
models-cli, #105). This landed a real failing test
(`test_parse_model_ids_openai_shape`) and surfaced repo-wide mypy debt (64
errors → 43 after this pass). Fixed here: `parse_model_ids` now object-rows-only
in the OpenAI `{"data": ...}` shape; feature-owned + trivial mypy classes; RC
`_apply_decision` resolves a real endpoint via `EndpointManager(get_config())`
(was `get_rate_limiter(None)`, silently failing); `run_configure` C901
suppressed with `# noqa: C901`. Gate: **905 passed** (batched, `overall_exit=0`),
`ruff check` + `ruff format --check` clean. Open:

- [x] **Full-repo mypy cleanup (43 errors)** — non-gating (CI has no mypy; `pre_commit.sh` runs it warnings-only). Remaining by file: `tests/integration/test_golden_path.py` (12), `core/agent_schemas.py` (5), `core/endpoint_manager.py` (4), `workflow/task_runner.py` (3), `utils/run_codemodes.py` (3, libcst API drift), `utils/list_endpoint_models.py` (3), `file_editing/edit_payload.py` (3), `workflow/proposal_builder.py` (2), `tests/mocks/openai.py` (2), `agents/prioritizer_worker.py` (2), `agents/orchestrator.py` (2), `workflow/post_materialize.py` (1), `utils/query_developer_responses.py` (1). See `mypy .` for line-level detail. **Landed: `mypy .` → `Success: no issues found in 181 source files`.** Type-only fixes (annotations, `isinstance` narrowing, honest `str | None` / `dict | None` / `Any` signatures); the libcst drift in `run_codemodes.py` was fixed against the installed libcst API (`BaseExpression.code` → `with_changes`; `AnnAssign(simple=…)` dropped; assign-target isinstance narrowing) and still round-trips correctly; `_get_or_create_file_id` now raises instead of returning `None` on a failed insert; `proxy`/`models`/SQL param plumbing typed.
- [x] **`run_configure` (core/models_wizard.py) C901 → real refactor** — complexity 25 > 15; previously suppressed with `# noqa: C901` (repo precedent `call_endpoint`). **Landed:** extracted `run_configure` into `_print_config_header`, `_fetch_catalog_if_requested`, `_pick_tiers`, `_apply_tiers`, `_edit_agent_overrides`, `_edit_prompts`, `_validate_and_write`; `run_configure` complexity 25 → 1; `# noqa: C901` dropped. Prompt sequence unchanged (`test_configure_wizard_assigns_tiers_from_answers` green).
- [x] **RC rate-limiter-adjust unit coverage** — `_apply_decision` applies `set_max_calls` against the endpoint resolved via `EndpointManager(get_config())`; `test_apply_decision_adjusts_resolved_endpoint_rate_limiter` proves the shared `get_rate_limiter(endpoint)` limiter's `max_calls` actually changes (25 → 40) across two applications (previously the `get_rate_limiter(None)` path silently no-opped).
- [x] **OpenRouter `free-models-per-day` is a daily quota, not a burst 429** — `call_endpoint`'s 429 branch (`agents/base.py`) prints the `X-RateLimit-*` headers then sleeps a hard 60s (`Retry-After` default) against a bucket that resets at midnight UTC. Headers are the real signal and are parsed nowhere: `X-RateLimit-Limit: 50`, `Remaining: 0`, `Reset: 1788134400000` (ms → 2026-08-31 00:00 UTC; value > 1e12 = ms, else seconds). Soak symptom: opencode 429 ×3 → 5m `UNAVAILABLE` → OpenRouter daily `Remaining: 0` → 3×60s hops, the two dead endpoints ping-ponging all night while the mutation path idles in `time.sleep(60)`. **Fix:** parse the Reset header and classify quota vs burst — quota when `Remaining == 0`, a Reset header exists, or the body mentions `free-models-per-day`/`Add 10 credits`; then `wait = reset − now`. `wait > 60s` → park the endpoint (`RATE_LIMITED`, cooldown capped ~15 min like `TOKEN_EXHAUSTED`, log the real reset), fall back immediately, no 3×60s hop; `wait ≤ 60s` → sleep-to-reset and retry once; burst (`Remaining > 0` / no Reset) keeps the current short retry. Desired stdout: `⏳ openrouter daily quota exhausted (free-models-per-day) … parking openrouter until <reset>`. Tests: extend `tests/unit/test_call_endpoint_rate_limit.py` (ms-reset long wait, body-quota-without-headers, short-wait sleep-to-retry, burst path unchanged). **Operational note:** adding $10 on OpenRouter unlocks 1000 free-model req/day; until then `openrouter/free` hits this nightly after ~50 calls. **Landed:** new `core/rate_limit_headers.py` (`parse_reset_to_epoch` — ms > 1e12, epoch ≥ 1e9, else now + value; `classify_rate_limit` → dataclass) + 429 branch classify/park/sleep-to-reset in `agents/base.py`; tests: `tests/unit/test_rate_limit_headers.py` (10) + 4 call-path tests (`test_429_quota_ms_reset_parks_and_does_not_hop`, `test_429_quota_body_token_sleeps_and_retries`, `test_429_quota_short_reset_sleeps_to_reset_then_retries`, `test_429_burst_with_ratelimit_headers_not_quota`). 49 targeted tests green.
- [x] **Both-endpoints-parked: stop the 60s hop** — when every candidate sits `UNAVAILABLE`/`RATE_LIMITED` (e.g. opencode key_locked + OpenRouter daily quota empty), the fallback chain + loop retries short (60s) instead of one longer backoff or a cycle pause; a minutes-level backoff matches Operator Principle #1 better than hammering two empty buckets. Depends on the quota item above. **Landed:** the no-fallback skip branch in `agents/base.py` now sleeps `min(max(wait, 30), 120)` (minutes-level) and reports it (`test_skip_path_all_parked_sleeps_bounded_backoff`).
- [x] **`setup.sh` venv-persistence convenience wrapper** — running `utils/setup.sh` plainly now `exec`s into an interactive bash that sources `~/.bashrc` then activates the repo's `.venv` (via a mktemp `--rcfile`), so the terminal lands inside the activated venv. Skipped when the script was sourced, when stdin/stdout are not a TTY (CI / pipes / cron unaffected), or when `VIRTUAL_ENV` already equals the repo venv. `bash -n` clean.

---

## 5. Annexes (strategic / parked decisions)

### 5.1 Forge Federation strategy — `Federation/Plan.md`

Active northstar: Stage 0 (current single-Territory system) → Stage 1 (enhanced
single-Territory, next) → Stage 2 (multi-Territory, future). Operates via short,
YAGNI-focused sprints with bounded, measurable experiments.

### 5.2 `report/plan.md` file_editing structural refactors

Review-flagged structural items. **Decision (2026-08-29): FOLDED INTO BACKLOG AS TECH-DEBT** — each is small, bounded, and independently scoped; a future sprint can pick them up without a dedicated design doc.

- [ ] **`project_files` refactor** — normalize file metadata/index rows and their update paths.
- [ ] **Standardize errors** across file_editing — single error shape/status vocabulary instead of per-module strings.
- [ ] **120s-sleep behavior** — the legacy fixed sleep in the editing loop: replace with event-driven wait or configurable strategy.
- [ ] **CLI command leakage** — audit `cli.commands` for shelled-out / ungoverned commands that bypass the governed edit path.
- [ ] **`__init__.py` cleanup** — remove obsolete re-exports in `file_editing/__init__.py`.

### 5.3 UNATTENDED plan §15 open decisions (parked, with defaults)

1. Hook failure: fix-forward (leave disk dirty; CRITICAL fix) unless `git.revert_on_hook_failure` set — current behavior is fix-forward.
2. Create-file policy: clean relative paths OK; add prefix policy only if junk root files recur.
3. `config.json` as agent edit target: gitignored config stays human-only.
4. Reviewer sees hook output: developer primary; orchestrator summary; reviewer optional.
5. API/network failure streaks: pause + single CRITICAL summary after N consecutive failures (shipped — `NetworkBusyLoopGuard`).

## 6. Cold-soak SQLite project ingest (NUC / 2-core / ≥8 GB)

**Status:** OPEN — design only (2026-08-31). No branch yet.

**Constraint (intentional):** soaks do **not** copy `.PrizmForge/`. Every soak
start is a **cold full rebuild** of `prizmforge.db`. Do not plan cross-soak
hash-skip, leftover `project_files.content_hash`, or “second run is cheaper.”
The only clock that matters is **one** `cmd_init()` on a wiped DB.

**Symptom:** on a 2-core NUC, soak start spends a long time in
`🔄 Auto-indexing project files...` before iteration 1. Root is not “SQLite
is slow”; it is how init talks to SQLite.

**Hot path today**

- `main.py` → `init_db()` → `cmd_init()` (`cli/commands.py`) when
  `auto_init_on_start` is true (unattended default).
- `os.walk(project_directory)` then, **per text file**:
  1. `sync_file_to_database` — new connection, `INSERT OR REPLACE` full blob
     into `project_files`, `estimate_tokens`, **commit**.
  2. `generate_file_summary` + `save_file_summary` — **another** connection +
     commit.
  3. `initialize_file_lines` (`file_editing/writer.py`) — **another**
     connection, `DELETE FROM file_lines`, then **one `INSERT` per line** in a
     Python `for` loop (`uuid4` + md5 per line), **commit**.
- Then a fourth connection for the deleted-file pass.
- Then `refresh_target_indexes(..., force=True)`.

`initialize_file_lines` uses `file_editing.db.get_db_connection()`, which does
**not** apply `core.db_connection` pragmas. Those commits often run at SQLite
default `synchronous=FULL` (fsync per file). Runtime connections already use
`journal_mode=DELETE` + `synchronous=NORMAL` (lock-safe for soak; terrible for
bulk load). ~40k Python source lines ⇒ tens of thousands of single-row inserts
and three transactions per file.

**Non-goals**

- Do not persist `.PrizmForge/` between soaks to make init faster.
- Do not thread-pool ingest (one SQLite writer; two cores).
- Do not leave `synchronous=OFF` / `locking_mode=EXCLUSIVE` on after init.
- Do not switch the live soak DB to WAL for this item unless measured on the
  NUC; locking work assumed DELETE.
- Do not treat “daemon owns the DB” as the fix for *this* window. Init should
  be one exclusive bulk transaction, then hand the DB back.

### 6.1 Init connection + one transaction

- [ ] **`cmd_init` holds one writer** — open a single
      `core.db_connection.get_db_connection()` (or a dedicated
      `get_init_db_connection()`) for the whole walk. Pass `conn` into
      `sync_file_to_database`, `save_file_summary`, and `initialize_file_lines`
      (the last already accepts `conn=`). Commit **once** after all files + the
      deleted-file pass.
- [ ] **Never open `file_editing.db.get_db_connection()` during init** — that
      helper skips bulk pragmas and defaults to FULL sync. Either route init
      through `core.db_connection` or apply the same pragmas there (prefer the
      former so there is one writer policy).
- [ ] **Deleted-file pass uses the same `conn`** — no extra context manager.

### 6.2 Init-only pragmas (restore before iteration 1)

On the init connection, **before** the walk (8 GB floor; 2-core NUC):

```sql
PRAGMA journal_mode = MEMORY;
PRAGMA synchronous = OFF;
PRAGMA temp_store = MEMORY;
PRAGMA cache_size = -524288;     -- 512 MiB page cache
PRAGMA mmap_size = 268435456;    -- 256 MiB mmap
PRAGMA locking_mode = EXCLUSIVE;
PRAGMA busy_timeout = 5000;
```

After the single commit, **before** `cmd_init` returns:

```sql
PRAGMA locking_mode = NORMAL;
PRAGMA synchronous = NORMAL;
PRAGMA journal_mode = DELETE;
```

- `MEMORY` journal: box-crash mid-init already throws the DB away; an exception
  mid-walk can still roll back a half-built index. Prefer this over
  `journal_mode=OFF` first.
- `cache_size` 512 MiB + `mmap` 256 MiB is the intended 8 GB split. Do not
  grab multiple GB; agents + Python need the rest.
- Document in a comment that these pragmas are **init-window only**.

### 6.3 `file_lines` bulk insert

- [ ] **`_initialize_lines_impl`: `executemany`** — build the row tuples in
      Python, one `executemany` per file (or chunks of 5k–10k rows if a file
      is huge). Same columns:
      `(line_guid, file_id, sort_order, content, content_hash, version, is_deleted)`.
      Keep `uuid4` + line md5; they are cheap next to per-row `execute`.
- [ ] **Optional:** if secondary indexes on `file_lines` exist besides UNIQUE
      `line_guid`, create them **after** the bulk load (`ANALYZE` once). Do
      not drop UNIQUE `line_guid`.

### 6.4 Same-process only (not cross-soak)

- [ ] Hash short-circuit is **in-process only** (second `cmd_init()` in the
      same soak, or a mid-soak restart that did *not* wipe the live DB).
      Default soak still pays full rebuild. Do not advertise “next soak is
      faster.”

### 6.5 Work that is not required for iteration 1

- [ ] Throttle per-file `✅ {path}` prints (every 50 files + a final tally).
- [ ] `refresh_target_indexes(..., force=True)` runs **after** the DB commit
      (keep it on the cold-soak bill, or `force=False` only when an in-process
      index already exists — never assume a previous soak left one).
- [ ] `project_files.content` + `file_summaries` may stay in the same
      transaction; do not add extra commits. Do not drop `file_lines` (governed
      editor). Folding `project_files` into a later metadata-only table is
      §5.2 tech-debt, not this item.

### 6.6 Files to touch

- `cli/commands.py` — `cmd_init` transaction + pragma window + print throttle.
- `file_editing/writer.py` — `_initialize_lines_impl` `executemany`.
- `core/file_operations.py` — accept optional `conn=` on
  `sync_file_to_database` / `save_file_summary`.
- `core/db_connection.py` — optional `get_init_db_connection()` so soak
  connections never inherit init pragmas.
- `tests/unit/` — new tests (no live endpoints):
  - init of N small files uses **one** commit path (spy `commit` / count
    connections).
  - `initialize_file_lines` writes expected line count + reconstructs content.
  - after init helper returns, `PRAGMA journal_mode` is `delete` and
    `synchronous` is not `OFF`.
  - `file_editing.db.get_db_connection` is not used on the init path.

### 6.7 Acceptance

- Cold soak (no `.PrizmForge/` copied) still produces a complete `files` +
  `file_lines` + `project_files` index; governed reconstruct matches disk.
- Wall-clock of `cmd_init` on the NUC drops from “noticeable stall” to a short
  burst; log the four buckets: walk+read, DB writes, deleted-file pass,
  symbol index.
- First orchestrator call still sees DELETE + NORMAL; no new dual-writer /
  `database is locked` storms vs current soak baseline.
- Gate: existing file-line / proposal / git-closed-loop tests stay green;
  ruff clean on touched files.

**Verify on the NUC, not only CI:** CI disks hide fsync cost. Time a wiped
`cmd_init()` before and after on the same tree.


## 7. Optional PostgreSQL via SQLAlchemy (SQLite remains default)

**Status:** OPEN — design only (2026-08-31). No branch yet. Depends on §6
(cold-soak ingest) only in the sense that **init bulk-load must stay a
first-class path** on both backends; do not block §6 on this.

**Why:** SQLite is correct for NUC soaks, hermetic tests, and wiped
`.PrizmForge/` isolation. A shared or multi-writer deploy (later federation
§5.1, long-lived operator DB, concurrent soaks against one store) needs a
server engine. The product switch is **configuration**, not a fork.

**Default stays SQLite.** Postgres is opt-in. CI and `utils/run_tests.sh`
stay on SQLite unless an explicit extra job is added.

### 7.1 Decision: SQLAlchemy Core first, not ORM-everywhere

The schema lives as a large raw-SQL string in `core/db.py` (`init_db`,
`_apply_schema`, `_migrate_schema`) plus two connection helpers
(`core/db_connection.py`, `file_editing/db.py`) and dozens of
`conn.execute("""...""")` call sites. An overnight ORM rewrite of
`file_lines` / proposals / workers will stall the mutation path.

- **Phase A:** SQLAlchemy **engine + connection** facade. Call sites keep
  textual SQL (`sqlalchemy.text`) until each module is touched for another
  reason.
- **Phase B:** SQLAlchemy `MetaData` / `Table` models for schema create +
  migrations (replace the string blob + `PRAGMA table_info` ALTER loop).
- **Phase C (optional, later):** ORM mapped classes only where it removes
  duplication (e.g. `edit_proposals`, `agent_feedback`). Line store and
  archives can stay Core/`executemany` forever.

Do not introduce Django, Tortoise, or a second query layer.

**Dependencies (pin in extras, not required for default install):**

```text
sqlalchemy>=2.0,<3
psycopg[binary]>=3.1    # Postgres driver only when backend=postgresql
```

Suggested extra: `pip install -e ".[postgres]"`. SQLite uses SQLAlchemy’s
bundled `sqlite3` dialect — no extra package.

### 7.2 Configuration (files, not env-only)

Add a top-level `database` object to `config.json` / `example_config.json`.
Document in `docs/CONFIGURATION.md`. Secrets stay in `api_key.json` (or a
sibling gitignored file), never in `config.json`.

```json
"database": {
  "backend": "sqlite",
  "sqlite": {
    "path": null
  },
  "postgresql": {
    "host": "127.0.0.1",
    "port": 5432,
    "name": "prizmforge",
    "user": "prizmforge",
    "sslmode": "prefer",
    "connect_timeout_s": 10
  }
}
```

- `backend`: `sqlite` (default) | `postgresql`. Unknown value → `ValueError`
  at `validate_config`.
- `sqlite.path`: `null` keeps today’s rule (`PRIZMFORGE_DB_PATH` else
  `<project>/.PrizmForge/agents.db`).
- Postgres password: `api_key.json` → `keys.database.password` (or
  `keys.postgresql.password`). Mirror endpoint-key style. Empty password +
  `backend=postgresql` → fail closed at startup.
- Optional override URL (operator/CI only): env `PRIZMFORGE_DATABASE_URL`
  wins over `backend`+fields. Allowed schemes: `sqlite`, `sqlite+pysqlite`,
  `postgresql`, `postgresql+psycopg`. Reject `postgres://` ambiguity or
  normalize it once in code.

`validate_config` checks types only. Reachability is `init_db()` /
preflight, not config parse (so unit tests can load configs without a
server).

Unattended preflight (`core/preflight.py`): if `backend=postgresql`,
require the extra installed and a successful `SELECT 1` before soak start.

### 7.3 Single engine facade

Replace the split `sqlite3.connect` world with one module, e.g.
`core/db_engine.py`:

- `get_engine()` — process singleton, built from config.
- `session_scope()` / `connection_scope()` — context manager that yields a
  connection with `commit`/`rollback` matching `get_db_connection`.
- `get_db_path()` remains for SQLite file location and diagnostics; Postgres
  returns the sanitized URL (`password` redacted).

**SQLite engine kwargs (preserve soak locking story after §6 init window):**

- `connect_args={"timeout": 30}` (or current values).
- `poolclass=NullPool` (or `StaticPool` + `check_same_thread=False` only if
  a measured single-connection soak needs it). Default: **NullPool** so we
  do not invent a second writer pool on the file DB.
- On connect: `PRAGMA journal_mode=DELETE`, `synchronous=NORMAL`,
  `temp_store=MEMORY`, `foreign_keys=ON` — same as `core/db_connection.py`
  today. §6 init pragmas stay a **separate** connect event or
  `execution_options` used only by `cmd_init`.

**Postgres engine kwargs:**

- `poolclass=QueuePool`, small pool (`pool_size=5`, `max_overflow=5`) on an
  8 GB NUC; configurable later.
- `pool_pre_ping=True`.
- `isolation_level` default (READ COMMITTED). Do not copy SQLite’s
  `EXCLUSIVE` / `journal_mode` onto Postgres.
- `statement_timeout` via `SET` on connect if we see runaway queries.

**Deprecate, then delete:**

- `file_editing.db.get_db_connection` — must call the facade (it currently
  skips pragmas; that is already a soak footgun).
- Raw `sqlite3.connect` in `core/db.py` `init_db`, `core/model_health.py`,
  workers, `utils/query_developer_responses.py`.
- Keep `sqlite3` only inside the SQLite dialect connect hook and tests that
  assert PRAGMA.

`DatabaseRetryError` + wall-clock commit budget stay for SQLite lock/busy.
On Postgres map deadlocks / `lock_not_available` to the same exception so
callers do not grow a second retry vocabulary.

### 7.4 Dialect-safe SQL (inventory before rewrite)

Textual SQL that is **SQLite-only** today and must be parameterized or
branched:

| Pattern | SQLite today | Postgres |
|---|---|---|
| Surrogate keys | `INTEGER PRIMARY KEY AUTOINCREMENT` | `INTEGER GENERATED BY DEFAULT AS IDENTITY` (or `SERIAL`) |
| Upsert | `INSERT OR REPLACE` (`project_files`, `file_summaries`) | `INSERT … ON CONFLICT (file_path) DO UPDATE SET …` |
| Instant | `datetime('now')`, `CURRENT_TIMESTAMP` | `NOW()`, `CURRENT_TIMESTAMP` |
| Booleans | `INTEGER 0/1` | keep `SMALLINT`/`INTEGER` in v1 (do not flip to native `BOOLEAN` mid-migration) |
| Singleton rows | `CHECK (id = 1)` (`cli_checkpoints`, `reporter_state`) | same CHECK, or `INSERT … ON CONFLICT (id)` |
| Introspection | `PRAGMA table_info`, `sqlite_master` | `information_schema.columns` / Alembic |
| Bulk init | §6 `executemany` + MEMORY journal | `psycopg` `executemany` or `COPY` for `file_lines` only if measured |
| FKs | `PRAGMA foreign_keys=ON` | always on |

Rules:

- No `SELECT *` new code; column lists survive dialect type drift.
- Placeholders: SQLAlchemy `text("… WHERE file_path = :path")` bound
  params. Ban `f"SELECT … {table}"` except for the existing export helper
  after an allowlist.
- `lastrowid` after `INSERT INTO files` must use
  `inserted_primary_key` / `RETURNING file_id` on Postgres.
- `Row` access: keep both index and key (`row["file_id"]`) via
  `mappings()`.

Phase A may wrap the worst call sites (`INSERT OR REPLACE`, `lastrowid`,
`datetime('now')`) in `core/db_sql.py` helpers keyed by dialect name.

### 7.5 Schema create + migrations

Today: one SQL blob + additive `_ensure_column` for old files.

Target:

- [ ] **SQLAlchemy `MetaData` in `core/schema.py`** — one `Table()` per
      existing table (start with the critical set: `files`, `file_lines`,
      `edit_proposals`, `messages`, `tasks`, `errors`, `agent_feedback`,
      `project_files`, `events`). Remaining tables can stay in the blob for
      one PR if listed explicitly.
- [ ] **`init_db()`** becomes `metadata.create_all(engine)` + dialect
      connect pragmas (SQLite only).
- [ ] **Alembic** (`alembic/`) for additive migrations from that point.
      First revision = “schema as of this PR” (empty upgrade on a fresh
      `create_all`). Stop hand-written `_ensure_column` for new columns.
- [ ] SQLite file DBs from older soaks: still support `_migrate_schema`
      **or** one-shot “wipe and recreate” because soaks already throw
      `.PrizmForge/` away. Do not invent a production SQLite upgrade story
      beyond current additive columns unless an operator keeps a durable
      file DB.

Postgres: never run `PRAGMA`. Never run §6 `journal_mode=MEMORY`. Init
performance work for Postgres is a different checklist (`COPY` / unlogged
`file_lines` during load, then `ALTER TABLE … SET LOGGED`) — park unless a
soak actually uses Postgres.

### 7.6 Product behavior that must not change

- Default `backend=sqlite`, path under `.PrizmForge/`, wiped per soak.
- Governed reconstruct (`file_lines` + `sort_order` + `is_deleted`) identical.
- Tests use tmp SQLite; no Docker required for `run_tests.sh --normal`.
- `log_error` stays non-blocking (short timeout / best-effort) on both
  backends.
- Dual-writer rule on SQLite is unchanged: one writer during materialize;
  do not open a second engine against the same file.

### 7.7 Phased delivery

- [ ] **7.A — Config + engine + SQLite parity**  
      `database` block, `get_engine()`, migrate `init_db` +
      `get_db_connection` + `file_editing.db` to the facade. Behavior on
      SQLite indistinguishable. Gate green. No Postgres CI yet.
- [ ] **7.B — Dialect helpers + lastrowid/upsert**  
      Fix the inventory in §7.4 at the highest-traffic writers
      (`file_operations`, `writer.initialize_file_lines`,
      `proposal_builder`, `db_helpers`). Unit tests run the same SQL
      helpers against a SQLite engine.
- [ ] **7.C — Postgres smoke (optional extra)**  
      `tests/integration/test_postgres_smoke.py` marked `@pytest.mark.postgres`,
      skipped without `PRIZMFORGE_DATABASE_URL`. Creates schema, indexes one
      file, reconstructs lines, writes one proposal row. Document compose
      snippet in `docs/soak_runbook.md` (do not make compose the default
      soak).
- [ ] **7.D — Alembic + MetaData**  
      Move off the schema string. One documented `alembic upgrade head` for
      durable Postgres; SQLite soaks still `create_all` on empty file.

### 7.8 Files to touch (7.A minimum)

- `core/config.py` + `docs/CONFIGURATION.md` + `example_config.json`
- `example_api_key.json` — `keys.database.password` placeholder
- `core/db_engine.py` (new), `core/db.py`, `core/db_connection.py`,
  `file_editing/db.py`
- `core/preflight.py` — Postgres reachability
- `pyproject.toml` / install extras
- `tests/unit/test_db_engine.py` — backend selection, URL redaction,
  SQLite PRAGMA on connect, reject unknown backend
- `tests/unit/test_db_retry_patience.py` — still valid on SQLite engine

### 7.9 Acceptance

- `backend` omitted or `"sqlite"` → bit-identical operator story to
  current `main` (path, pragmas after init, tests).
- `backend: "postgresql"` without password / extra / server → **fail
  closed** with an actionable message, no silent SQLite fallback.
- No password in logs, events, or `get_db_path()` print.
- Ruff clean; normal gate does not require Postgres.
- §6 init pragmas still compile and apply **only** when dialect is SQLite.

### 7.10 Out of scope

- Multi-tenant Postgres, read replicas, federation Stage 2.
- Moving agent JSON blobs into JSONB in the first Postgres PR (TEXT is
  fine; JSONB is a later migration).
- Replacing the message bus with Redis/NATS.
- SQLAlchemy 1.4 APIs (`Query`, `sessionmaker` legacy binds).

