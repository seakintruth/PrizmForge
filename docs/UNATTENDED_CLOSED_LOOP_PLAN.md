# Unattended Closed-Loop Hardening Plan

**Status:** planning capture (2026-08-16; updated with diagnostic dump)  
**Progress tracker:** no workstream has shipped yet — all acceptance criteria in §3–§8 are unchecked/open. Update this header and tick the §16 checklist items as phases land.  
**Context:** Self-edit unattended runs on a *copy* of PrizmForge (Gemini; multi-hour soaks)  
**Goal:** Turn observed failure modes into durable product workstreams so future development does not rediscover them ad hoc.

Related existing work:

- Path token sanitization / FILES_NEEDED extraction (`workflow/path_targets.py`)
- Orthogonal test markers + batched runner (`tests/README.md`)
- Governed edit path (proposal → reviewer → materialize)

This document is the backlog map for **closed-loop** behavior: every write, git/hook outcome, and feedback item must feed the sequential mutation path with enough signal to finish work instead of thrashing.

---

## 1. Problem summary (from live runs)

| Observation | Effect |
|-------------|--------|
| Pre-commit / git stdout visible only on console | Broken tree (`core/agent_schemas.py` syntax) blocked every later commit; orchestrator never prioritized fixing it |
| Feedback backlog 278→301+ items | Permanent `BACKLOG OVERRIDE`; prioritizer churn; high token burn; little completion |
| Materialize success ≠ git success | Disk/DB updated, hook failed, agents assumed progress |
| `config.json` gitignored | `git add` refused; still treated as a normal edit target |
| Weak edit validation | “Valid edit payload” then proposal fail (`find_replace` missing fields; `type: "guid"`) |
| Phase-1 developer often returns prose | Extra repair calls every iteration |
| After materialize, no targeted re-verify of *changed* paths | Stale feedback + new random peer-review noise |
| API/network error storms (see §1.1) | Orchestrator/developer HIGH errors with no recovery path into feedback |
| Diagnostic dump shows write success without git events | Confirms Workstream A gap is measurable in DB, not only console |

### 1.1 Evidence from FULL DIAGNOSTIC DUMP (copy DB, task_009 era)

Source: operator dump against  
`PrizmForge_Experimental/.PrizmForge/agents.db` (tables: edit_proposals, file_write_log, errors, events).

**Edit proposals (full_replace / fallback slice — 30 rows sampled)**

- Heavy **`full_replace` as final_mode**, often after `fallback_used=1` from `find_replace` or `guid`.
- Multiple **applied** rows on the same path (e.g. `utils/build_preview.sh`, `utils/query_developer_responses.py`, `utils/run_codemodes.py`) — re-edit churn without clear “done” signal.
- **Reviewer rejections work** when semantics are wrong (e.g. `core/rate_limiter.py`: lock released during `sleep` — rejected twice with coherent reasons). That path is healthier than git/hook failures, which never appear as proposal status.
- `selected_mode` vs `final_mode` divergence is common; fallback is doing real work, but **fallback success is not correlated with git cleanliness** in this dump.

**file_write_log (30 rows)**

- Every row `status=success`.
- **`started_at` / `completed_at` empty** — write observability is incomplete; cannot reconstruct duration or order vs git from this table alone.
- Success here means “writer path reported success,” not “hook/commit succeeded.”

**Errors**

- **HIGH:** long streak of `orchestrator` / `developer` *failed to return a response (API/Network error)* for `task_009` (proxy/API outages). Logged in `errors` table — good.
- **CRITICAL:** 0 rows.
- Keyword scans for `full_replace` / `materialize` in errors: **0 rows**.
- Implication: **pre-commit / git failures are not promoted into `errors` or CRITICAL feedback.** Console-only failures match the empty CRITICAL set.

**Events (lifecycle — 60 rows sampled)**

- Present: `proposal.created`, `proposal.approved`, `proposal.rejected`, `edit.fallback_used`, `edit.materialized` (payload often `{"status": "success", ...}`).
- **Absent:** `edit.git_failed`, `edit.hook_failed`, or any payload carrying ruff/pre-commit stdout.
- `edit.materialized` fires on writer success — **same blind spot as console soak**: events claim success while hooks may have failed.

**Line-count tail (truncation candidates)**

- Includes `.ruff_cache/*`, `api_key.json`, and other non-source paths.
- Agents should not treat cache or secrets as edit/truncation candidates (ties to Workstream E).

**Diagnostic meta-gap**

- The dump is excellent for proposal/event forensics but **cannot answer “did git commit succeed?”** until Workstream A emits structured outcomes into `events` / `errors` / feedback.

---

## 2. Design principles

1. **Single mutation authority** — Only the governed sequential loop writes; background agents never “fix” by side channel.
2. **Verify after approve** — Reviewer JSON approval is necessary but not sufficient when git/hooks exist; materialize must report *verification* outcome.
3. **Signal over volume** — Prefer fewer, higher-quality feedback items as backlog grows; intake control is a feature, not a throttle bug.
4. **Fail closed on poison files** — A syntax-broken tracked file that fails pre-commit is CRITICAL and blocks broad edit ambition until cleared.
5. **Copy-first for self-edit** — Production patterns must be safe on a working copy; never assume the agent tree is clean.
6. **Tests lock gates** — Hand-rolled tables over Hypothesis; assert outcomes (status, paths, messages), not “no exception.”
7. **Diagnostics must close the loop** — If an outcome matters to the next agent turn, it must appear in DB events/errors/feedback, not only stdout.

---

## 3. Workstream A — Git / pre-commit closed loop

### 3.1 Intent

Capture full outcome of `git add` / `git commit` (and any hook output) and route it into the agent system so the next developer turn can fix the real failure.

### 3.2 Current gap

- Hook output streams to the human console only.
- Materialize can look successful while commit failed.
- Reviewer never sees hook results (and should not be the primary consumer).
- **Diagnostic confirmation:** `edit.materialized` + `file_write_log.status=success` with **zero** git/hook error rows and **zero** CRITICAL errors after known hook-failure soaks.

### 3.3 Target behavior

```
approve → write disk → git add/commit (if enabled)
                │
                ├─ success → event edit.materialized + optional targeted re-queue
                └─ failure → status materialize_failed / git_failed
                             event edit.git_failed
                             CRITICAL feedback → developer (+ short orchestrator note)
                             errors row (level CRITICAL or HIGH) with hook excerpt
                             do not increment “clean commit” counters
```

### 3.4 Implementation sketch

| Component | Change |
|-----------|--------|
| Git helper (`utils/git_operations.py` or writer) | Run subprocess with captured stdout/stderr; return `{ok, code, stdout, stderr, combined}` |
| `materialize_proposal` | Persist capture on proposal row or `events.payload_json`; set status fields distinctly for disk-ok/git-fail |
| Message bus | `post_message(system → developer, CRITICAL)` with truncated log (e.g. 4–8 KiB) + path to full report under `.PrizmForge/reports/` |
| Orchestrator context | One-line summary: “Git/pre-commit failed for proposal X; see feedback #N” |
| Config | `git.fail_materialize_on_hook: true` (default true when git enabled) |
| Diagnostic tooling | FULL DUMP sections should list latest `edit.git_failed` / hook report paths |

### 3.5 Who consumes what

| Consumer | Content |
|----------|---------|
| **Developer** (primary) | Full preview of ruff/flake errors, file paths, “fix these before new features” |
| **Orchestrator** | Compact status for prioritization / stop thrashing other items |
| **Reviewer** | Optional only if we add an explicit re-review-after-hook mode; not required on first pass |
| **Prioritizer** | Pin CRITICAL git-fail items above stylistic backlog |

### 3.6 Patterns to encode

- **Pattern: Verification gate after safety gate** — Reviewer = safety/semantics; hooks = repo policy/syntax.
- **Pattern: Artifact + pointer** — Full log on disk; bus carries summary + path (avoid 50k-char messages).
- **Pattern: Idempotent failure feedback** — Same proposal_id should not spam unlimited CRITICAL duplicates; upsert or dedupe by proposal_id.
- **Pattern: Event truth** — `edit.materialized` means disk+git policy satisfied; never emit it for disk-only success when git is enabled.

### 3.7 Acceptance criteria

- [ ] Unit test: mock git failure → materialize result not `success`; event emitted; feedback row created.
- [ ] Integration: intentional syntax break → next developer prompt includes hook excerpt.
- [ ] Ignored paths (`config.json`): explicit branch — skip git or fail with clear “path is gitignored” message, never silent success.
- [ ] Diagnostic dump: at least one non-success path visible under events/errors after a forced hook failure.

### 3.8 Non-goals

- Replacing pre-commit with in-process ruff only (hooks stay source of truth when present).
- Auto-amending commits without a new proposal.

---

## 4. Workstream B — Backlog consolidation under growth

### 4.1 Intent

As `unaddressed` grows, the system must **reduce noise and freeze intake**, not only “score harder.”

### 4.2 Current gap

- Prioritizer cycles through hundreds of items while jr_reviewer still posts.
- OVERRIDE sticks on the same feedback id across many iterations without completion signal.
- Token burn remains high with low materialize success rate.
- **Diagnostic:** repeated applied proposals on the same files suggest feedback not closed after write success → more backlog work on already-touched paths.

### 4.3 Target policy (tiered)

| Unaddressed count | Intake | Processing |
|-------------------|--------|------------|
| < 50 | Normal background agents | Normal prioritizer top-K |
| 50–100 | Soft: disable lowest-value agents; dedupe on insert | Top-K smaller; age MEDIUM faster |
| 100–200 | Hard: pause jr_researcher/tech_writer/security; only jr_reviewer on *changed* files | BACKLOG_PROCESSING; single active item |
| > 200 | Freeze almost all feedback agents; prioritizer + developer only | Mandatory consolidate pass (merge duplicates) before new posts |

Exact thresholds should be config (`feedback.tiers`).

### 4.4 Consolidation operations

1. **Dedupe on insert** — Same `(file_path, category, normalized_message_hash)` within window → increment counter / refresh timestamp, do not new row.
2. **Cluster for prioritizer** — Phase-1 group by file; one “bucket” per file with max severity.
3. **Address on success** — Materialize success for `path` auto-`addressed=1` for open items on that path matching proposal `addressing_feedback_ids` or same category+file when confidence high.
4. **Age/dismiss** — Existing aging; tighten when in BACKLOG_PROCESSING.
5. **Stuck-item detection** — Same feedback id targeted N times without materialize success → demote or reclassify as blocked (needs human / needs different mode).

### 4.5 Patterns

- **Pattern: Backpressure** — Queue depth controls producers (background agents), not only consumers.
- **Pattern: Single active repair** — One CRITICAL/HIGH work item “in hand” during backlog mode.
- **Pattern: Completion is a first-class event** — Addressing feedback is part of materialize success, not a best-effort afterthought.

### 4.6 Acceptance criteria

- [ ] Synthetic test: insert 100 near-duplicate findings → ≤ K rows retained.
- [ ] At simulated unaddressed>200, agent pool does not start random feeder reviews.
- [ ] Metrics in project report: unaddressed, posted_this_hour, addressed_this_hour, stuck_ids.

---

## 5. Workstream C — Post-materialize re-verify and task refresh

### 5.1 Intent

After a **successful** materialize (disk + git when required), refresh system state for *touched files only*.

### 5.2 Target pipeline

```
materialize success(path, proposal_id)
  → sync_file_to_database + symbol index for path
  → invalidate overlapping pending proposals (existing)
  → mark related feedback addressed / needs_revalidation
  → queue high-priority FileChangeEvent for path
       agents: deployment_validator, jr_reviewer only
       not: full random peer-review storm
  → orchestrator message: “path changed; verify before next feature”
```

### 5.3 On materialize **failure** (git/hook)

```
→ CRITICAL feedback with log
→ queue developer with files cited in hook output (parsed paths)
→ do not queue broad “improvements” on unrelated files
```

### 5.4 Patterns

- **Pattern: Localized verify** — Change radius = modified paths (+ imports only if cheap later).
- **Pattern: Task refresh, not task explosion** — Update existing feedback/tasks; do not create parallel duplicate tasks per agent.

### 5.5 Acceptance criteria

- [ ] After mock successful materialize, exactly one high-priority queue entry for that path (or bounded set).
- [ ] After git failure, no “celebration” counters; developer receives path list from parsed ruff output when possible.

---

## 6. Workstream D — Edit payload / developer phase robustness

### 6.1 Intent

Align “valid edit” with “proposal_builder will accept,” and harden phase-1 extraction (partially started with `path_targets`).

### 6.2 Concrete gaps from the runs

| Symptom | Fix |
|---------|-----|
| Valid payload then `FindReplace` missing `find`/`replace` | Validator must require fields per `type`; or normalize before is_valid |
| `Unknown operation type: 'guid'` | Reject mode names as op types; map only known op enum |
| Phase-1 prose always | Prefer structured JSON for phase-1 or treat FILES_NEEDED-only as success without “JSON repair” spam |
| Markdown paths | `sanitize_path_token` / extract helpers (keep tests green; no leading-dot strip) |
| Root junk creates (`database.py`) | Optional policy: create_file requires known prefix or explicit task allow-list |
| Frequent fallback to `full_replace` | Prefer smaller modes when valid; track fallback rate in reporter; avoid full_replace loops on same file without reviewer delta |

### 6.3 Patterns

- **Pattern: One schema, two gates** — Validator and proposal_builder share the same op schema module.
- **Pattern: Fail early** — Invalid ops never reach reviewer.
- **Pattern: Hand-rolled fuzz tables** — Expand `test_path_targets` / edit contracts for each new reject rule.

### 6.4 Acceptance criteria

- [ ] Table tests: op type `guid` → invalid.
- [ ] Table tests: `find_replace` without find → invalid.
- [ ] No proposal row created for invalid ops.

---

## 7. Workstream E — Repo policy awareness (gitignore, hooks, secrets)

### 7.1 Intent

Agents must know **repo constraints** that are not in Python schemas.

### 7.2 Items

- Respect `.gitignore` for commit targets; avoid editing secrets (`api_key.json`) — indexer should skip or redact.
- **Diagnostic:** line-count listing included `api_key.json` and `.ruff_cache/*` — exclude from agent file lists / truncation candidates.
- Detect pre-commit presence; surface “this repo enforces ruff on commit” in developer system context when git enabled.
- Optional: run `ruff check` on touched files **in-process** before git for faster feedback (hook remains authoritative).

### 7.3 Patterns

- **Pattern: Environment card** — Short machine-readable “repo facts” injected into developer/orchestrator (gitignore hits, hook enabled, test command).

---

## 8. Workstream F — Observability and operator UX

### 8.1 Intent

Make unattended runs diagnosable without reading a 50k-line console scroll.

### 8.2 Artifacts

| Artifact | Content |
|----------|---------|
| `.PrizmForge/reports/git-commit-*.log` | Full hook output per attempt |
| `events` table | `edit.materialized`, `edit.git_failed`, `feedback.deduped`, `backlog.tier_changed` |
| `file_write_log` | Populate `started_at` / `completed_at`; distinguish disk vs git outcome if split |
| `errors` table | Network/API already logged as HIGH; add CRITICAL (or HIGH) for hook failures |
| Project reporter | Unaddressed, burn rate, materialize success ratio, fallback rate, stuck feedback ids, git_fail count |
| Checkpoint | Last git failure summary for resume |
| Diagnostic dump | Sections for git/hook outcomes; hide secrets from line-count / file lists |

### 8.3 Patterns

- **Pattern: Structured events over stdout archaeology**
- **Pattern: Always-on counters** in task summary (extend with git_fail + fallback counts)
- **Pattern: Dump completeness** — If the operator cannot see hook failure in FULL DIAGNOSTIC DUMP, the product gap is not closed

### 8.4 API / network resilience (from error streak)

- Diagnostic shows repeated orchestrator/developer API failures with no CRITICAL escalation and no “pause task / surface to human” beyond existing proxy pause behavior.
- Follow-up (not Phase 1 blocking): circuit-breaker metrics in reporter; avoid busy-looping iterations when both sequential agents fail network in the same turn.

---

## 9. Recommended delivery phases

### Phase 0 — Stabilize the copy under test (operator)

- Stop the run or let it idle on proxy errors.
- Manually fix or revert poison files (`core/agent_schemas.py`).
- Snapshot DB + git log for postmortem (retain FULL DIAGNOSTIC DUMP).

### Phase 1 — Git closed loop (highest ROI)

1. Capture subprocess output in git path.
2. Fail materialize on non-zero hook when git enabled.
3. CRITICAL feedback + `edit.git_failed` event + errors row.
4. Stop emitting unqualified `edit.materialized` success when git failed.
5. Tests + confirm dump shows the failure.

### Phase 2 — Edit validation alignment

1. Shared op schema checks in validator.
2. Reject `guid` as type; require find/replace fields.
3. Fuzz tables.

### Phase 3 — Backlog backpressure

1. Config tiers.
2. Dedupe on insert.
3. Earlier agent pause.
4. Stuck-id handling.
5. Address-on-success for applied proposals (reduce same-file re-edit loops).

### Phase 4 — Post-materialize localized verify

1. Success path: bounded re-queue.
2. Failure path: parse hook paths → developer targets.
3. Auto-address feedback on success.

### Phase 5 — Repo policy + observability polish

1. Gitignore-aware targeting; exclude secrets/cache from agent file lists.
2. Fill `file_write_log` timestamps; reporter metrics; dump sections.
3. Docs in `docs/architecture.md` (short subsection + link here).

---

## 10. Dependency graph (simplified)

```text
Phase 1 git capture ──────────────┐
                                  ├──► Phase 4 failure path (hook → developer files)
Phase 2 validator ────────────────┤
                                  ├──► fewer false “success” proposals
Phase 3 backlog tiers ────────────┴──► Phase 4 success path does not refill ocean
```

Path sanitization is **orthogonal** and should stay green throughout.

---

## 11. Test strategy (patterns)

| Layer | What |
|-------|------|
| Unit | Git result dataclass; validator tables; dedupe hash; path sanitize (existing) |
| Integration | materialize + fake pre-commit script exit 1 → feedback row + event |
| Not in CI by default | Full unattended multi-hour; keep as manual soak on a copy |
| Markers | New tests **not slow** unless they start real pools; git mock tests stay fast |
| Diagnostics | Golden assertions on dump sections after forced hook fail (optional util test) |

---

## 12. Config sketch (future)

```json
{
  "git": {
    "enabled": true,
    "fail_materialize_on_hook": true,
    "capture_hook_output": true,
    "hook_log_max_chars": 8000
  },
  "feedback": {
    "max_unaddressed": 200,
    "dedupe_window_minutes": 60,
    "tiers": {
      "soft": 50,
      "hard": 100,
      "freeze": 200
    },
    "stuck_attempts": 5
  },
  "post_materialize": {
    "requeue_agents": ["deployment_validator", "jr_reviewer"],
    "auto_address_same_file": true
  }
}
```

Names illustrative — align with `docs/CONFIGURATION.md` when implementing.

---

## 13. Risks and mitigations

| Risk | Mitigation |
|------|------------|
| CRITICAL spam from repeated git fails | Dedupe by proposal_id / content hash |
| Pausing background agents hides real issues | Still allow forced `background` / on-demand review of touched files |
| In-process ruff drifts from hook | Hook remains authoritative; in-process is advisory only |
| Self-edit on main | Keep policy: unattended self-edit only on copies |
| full_replace churn on same file | Cap consecutive full_replace on one path; require reviewer delta or human |

---

## 14. Success metrics (soak on a copy)

After Phases 1–4, a 1–2h unattended run should show:

- Materialize success ratio rising vs proposal count.
- Unaddressed feedback stable or falling after initial spike, not monotonic climb past 300.
- At least one git/hook failure that **changes subsequent developer targeting** (observable in **events/errors/feedback**, not only console).
- No infinite OVERRIDE on a single feedback id without stuck detection.
- Zero “valid payload” followed by proposal_builder schema errors for known op types.
- FULL DIAGNOSTIC DUMP includes git/hook outcome rows when failures occur.
- `file_write_log` timestamps populated for new writes.

---

## 15. Open decisions (capture for later)

1. Should git-hook failure **revert** the disk write, or leave disk dirty and demand a fix-forward proposal?
2. Create-file policy: allow any clean relative path, or require directory prefixes (`workflow/`, `core/`, …)?
3. Is `config.json` ever a legitimate agent edit target in project mode, or always human-only?
4. Should reviewer see hook output on a second pass, or only developer?
5. Should API/network failure streaks auto-pause the task cycle (beyond proxy wait) and write a single CRITICAL summary?

Default recommendations if undecided:

1. Fix-forward (leave disk; CRITICAL fix) unless `git.revert_on_hook_failure` is set.
2. Clean relative paths OK; add prefix policy only if junk root files recur.
3. Treat gitignored config as human-only for commit; optional in-memory/runtime edits out of scope.
4. Developer primary; orchestrator summary; reviewer optional.
5. After N consecutive sequential-agent network failures in one iteration, pause and surface once (avoid error table floods).

---

## 16. Document maintenance

- Update this file when a phase ships (checkboxes + “Done in PR #…”).
- Fold new FULL DIAGNOSTIC DUMP takeaways into §1.1 (date the snapshot).
- Link short pointers from `docs/architecture.md` (Error/Observability or new “Unattended verification” bullet) and `tests/LLM_CONTEXT.md` gap matrix when behavior lands.
- Do not duplicate operational test commands here — those stay in `tests/README.md`.
