# PrizmForge Roadmap / TODO

This file lists **only work that still needs to be accomplished**.

Completed work is **not repeated here**. Implementation, PR numbers, soak
post-mortems, and acceptance evidence live in **git history**
(`git log`, merged PRs #108–#121, and
`docs/UNATTENDED_CLOSED_LOOP_CAPABILITIES.md`). Do not paste shipped
checklists back into this tracker.

**Last updated:** 2026-09-06

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
| **§10 Soak4 mutation path (Gemini will not drive the shell)** | **P0** | Worktree and evidence work. Developer on Gemini Enterprise never inspects or edits the task file. 0 proposals. Do this before ingest or more latch work. |
| §6 Next-soak 429 dump | **P0** | Unpaid soak check |
| §8 Operator soak A-1 | **ran** | Soak4 ran after #121; remaining mutation work is §10 |
| §5 Optional SQL hygiene | **P2** | Identifier quoting + comment-aware DDL split |
| §3 Seed-path / scope | **watch** | Next soak with background agents on |
| §2.3 Protocol nits | **watch** | Only if the next soak shows them |
| §1 NUC `cmd_init` timing | **P1 operator** | Code shipped in #121; still time on the box |
| §7 Closed-loop / mini-swe | **MEDIUM** | Unblocked by #121; needs live hooks / endpoints |
| §9 Annexes | **LOW** | WAL-as-default, Postgres, federation |

---

## 0. Current state & next focus

- **`main` already has (PR #121):** `seen_endpoints` recurse, latch-only
  `is_available()`, per-endpoint 4h + daily `TokenBudget`, fail-closed
  workspace evidence, zero-command seed latch, task status vocabulary
  (`failed` / `timed_out` / `no_change_required` / `stalled`), demotion
  exclusions (`key_locked`, `unauthorized`, `token_budget`,
  `token_exhausted`, `no_alternate_endpoint`), `Retry-After` on
  `rate_limited` events, cold `cmd_init` one-writer ingest. Do not
  re-implement those.
- **Next (run now):** §10 — Soak4 mutation path. Worktree and evidence
  already work; Gemini Enterprise will not drive the shell. Do this
  before ingest or more latch work. Optional SQL (§5) stays unblocked
  but is not the gate.
- **Company endpoints** still need a **manual unlock ~every 8 hours**
  and **must keep falling back** when one key locks.
- **Trajectories (do not merge):** `soak/doc-run-a-1` /
  `docs/soak-a-1-shell-trajectories/`; `soak/4-tmp-reporting` /
  `docs/soak-a-4-example-tmp/`.

---

## 10. Soak4 — make the mini-swe mutation path produce a proposal

**Priority:** P0
**Evidence (do not merge):** `soak/4-tmp-reporting` /
`docs/soak-a-4-example-tmp/shell_trajectories/`
(34 JSON files: `task_001` turns 1–30, `task_002` turns 1–4) and
`docs/soak-a-4-example-tmp/agents.db`.
**Live soak:** Windows Soak4-target, after PR #121 (`feat/roadmap-priority-0`).
**Last updated:** 2026-09-06

The worktree is fine. Gemini Enterprise never acts as a shell agent.
That is the mutation failure.

### 10.0 What already works (do not reopen)

- Disposable worktree (`/tmp/pf-shelldev-*/wt` ↔
  `C:/Users/…/Temp/pf-shelldev-*/wt`) contains the repo.
- Evidence command exit 0, `marker_found=true` for
  `workflow/__init__.py`, `task_path_exists=true`.
- Fail-closed “no FINISH until evidence” (PR #121).
- Zero-command seed latch fires and blocks a second developer
  dispatch (ROADMAP §3).
- Endpoint backoff on 407 / 503 (operator win on this soak).
- `CREATE TABLE` drift and cold ingest are **not** this item.

### 10.1 Soak4 facts (DB + trajectories)

Funnel on `docs/soak-a-4-example-tmp/agents.db`:

```text
tasks=2  developer_replies=103  replies_with_command=35
commands_ok=33  shell_events=46  proposals=0  writes=0  file_mods=0
```

Protocol histogram (103 = all developer rows):

| `response_format_status` | n | Typical prompt_len | What it is |
|---|---:|---:|---|
| `PROSE_OR_UNSUPPORTED_FORMAT` | 45 | 329 | Gemini Enterprise refusal (“no shell / upload files / I am a conversational assistant”). Invents `/home/bard` empty. |
| `VALID_BASH_BLOCK` | 35 | 2333 | Almost all are the **injected evidence line**. Response ~55–60 chars = copied fence. |
| `VALID_FINISH_SESSION` | 23 | 416 | Post-evidence “you may finish” turn. Many rows only *mention* the token. |

No developer `command` is `sed`/`python`/`cat` of
`workflow/task_runner.py`. `commands_executed` in trajectories is 0 or 1
(evidence only). Session headers:

| File | `exit_status` | After evidence? |
|---|---|---|
| `task_001-turn1` | `LlmUnavailable` (`kind=unknown` ×4) | Yes — `ls` stdout is last message |
| `task_001-turn25` | same | Yes |
| `task_002-turn1` | same | Yes |
| `task_002-turn4` | `RepeatedFormatError` | No command |

Turn 25 states the policy in plain language: “as **Gemini Enterprise**,
I operate as a conversational AI… I do not support the automated
script runner protocol.”

Soak-local token use on this run is ~**2M**, not 148M. The RC line
`Budget: 99.0% (148,497,489 / 150,000,000)` is the **shared 4h window**,
already near the cap from earlier work. Task_002 still ended
`failed (token budget exhausted: files_modified=0)` because that
window was ~99% when the latch was yielding to reviewers.
`Work:` stayed **0.0s**.

### 10.2 Session loop (every turn)

1. User/system ask for one closed bash block; first command must be
   evidence.
2. Model replies as a chatbot. Parser:
   `prose_or_unsupported_format`.
3. Finish before evidence is refused (correct).
4. 2333-char inject embeds the evidence fence. Model often **copies**
   it (sometimes unclosed). Runner executes it. Exit 0.
5. Next LLM call is still “emit bash.” Model essays again, or the
   call returns `kind=unknown` ×4 → `LlmUnavailable`.
6. If a finish is accepted first, the summary is “no shell / upload
   files,” not an edit.
7. Proposal builder never sees a dirty tree → 0 `edit_proposals`.
8. Latch treats the session as zero useful commands → orchestrator
   keeps voting `developer` → yield to jr_reviewer / security_reviewer
   until the **window** is exhausted.

Telling the model “you have a real shell” **causes** the essay. That
is not a fence-normalizer bug.

### 10.3 Harness bugs visible in the same dump

- [x] **Finish classifier is too loose.** Rows 67, 77, 124, 245, 248,
      268, 277, 288 parsed as `VALID_FINISH_SESSION` while the body is
      an essay that only *mentions* the token. Require the first
      non-empty line to be exactly `FINISH_EDIT_SESSION`. Reject a
      finish whose summary claims no filesystem / upload-files /
      “Gemini Enterprise” after `marker_found=true`.
      (Shipped: `is_canonical_finish` in `shell_protocol.py` +
      `finish_claims_no_shell` rejection.)
- [x] **Archive `command` is not always model-authored.** Every
      `prompt_len=2333` row stores the injected evidence line, even
      when `response` is “### System Access Limitations” (id 86).
      Store `injected_command` vs `model_command` separately, or only
      write `command` when the parsed bash block is what ran.
      (Shipped: `_record_step` stores `command=None` unless it ran.)
- [x] **`echo "I do not have shell access…"` is a valid bash block**
      (ids 209, 304) with `command_exit_code` NULL. Do not count that
      as evidence. Evidence is only the configured
      `pwd && git rev-parse --show-toplevel && ls -la && test -f <marker>`
      line with exit 0. (Shipped: `is_evidence_command` rejects it.)
- [x] **`kind=unknown` after a good `ls` is unlogged.**
      `model_health_events` on this DB was empty. Dump the raw HTTP
      body once per unknown; classify empty / safety / policy
      separately from transport. Do not tear the session down as
      `LlmUnavailable` until that dump exists.
      (Shipped: `model_health_events.detail`, `_dump_unknown_llm_body_once`,
      structured-only classifier; a non-empty extract is never classified
      and an empty/policy body falls back like `bad_payload`.)
- [x] **Latch: evidence-only ≠ zero-command.** If
      `commands_executed >= 1` and `marker_found`, do **not** freeze
      developer for the rest of the duration on `LlmUnavailable` or
      “no mutation.” Allow at least one retry. Otherwise one policy
      rant + one `ls` burns the remaining window on reviewers
      (`Work: 0.0s`). (Shipped: `_is_zero_command_seed_failure`.)

### 10.4 Required mutation-path changes

Primary files: `workflow/shell_developer.py`,
`workflow/shell_protocol.py`, `workflow/task_runner.py`,
`core/model_health.py` / `agents/base.py` (unknown-kind dump),
developer model routing in config, tests under
`tests/unit/test_shell_developer_protocol_recovery.py`.

#### 10.4.1 Evidence is in-process (no LLM)

- [x] Before the first `call_endpoint` for a shell session, the
      runner itself executes:

      ```bash
      pwd && git rev-parse --show-toplevel && ls -la && test -f workflow/__init__.py
      ```

      Persist cwd, git_root, exit, stdout excerpt, `marker_found`,
      `task_path_exists` (already on the trajectory object).
- [x] If marker missing or exit ≠ 0: emit
      `shell_workspace_validation_failed`, abort. Do not ask the
      model to prove the tree exists.
- [x] Do **not** put “you have a real shell / do not ask the user to
      upload files” sermons in the first user turn. That text is
      what triggers the Enterprise refusal.

#### 10.4.2 First model turn is inspect-the-target, not prove-cwd

- [x] After in-process evidence, the first user message is only:

      ```text
      Workspace listing (already executed, exit 0):
      <stdout>

      Target file: <seed path, e.g. workflow/task_runner.py>

      Reply with exactly one closed bash block. First command must be:
      sed -n '1,80p' <seed path>
      ```

      Use the resolved seed path; do not hard-code only
      `__init__.py`.
- [x] Reject `FINISH_EDIT_SESSION` until **one non-evidence command**
      against the target path has run (or a documented “target
      missing after evidence” abort).
- [x] After that `sed -n` / `nl` succeeds, the model may edit with
      further bash or finish with a real rationale. Finish with
      “no shell” after evidence stdout is
      `shell_session_no_mutation` + retry, not session-complete.

#### 10.4.3 Developer model is not optional

- [x] Do not assign `gemini-3.1-pro-preview` on `api.genai.mil`
      (Gemini Enterprise chat) as `developer` / shell implementation.
      Orchestrator and reviewers may stay on that endpoint.
      (Revised PR #123: an Enterprise-chat developer is now **attempted** via
      the chat-JSON-table protocol — an append-only JSON step-row table the
      model completes for the next `bash` command — instead of hard-aborting;
      if that session errors, the turn falls back to an `edit_payload`
      mutation in the same turn. `shell_developer.json_table="off"` restores
      the historical abort-on-fence-refusal behavior.)
- [x] Config: `agents.developer.model` (or
      `shell_developer.model`) must be a model that will emit a
      **second** closed bash block after seeing command stdout.
      Document the soak-proven refusal so a future config cannot
      silently point developer back at Enterprise chat.
      (Shipped: `example_config.json` `_note_model` warning.)
- [x] If the only available endpoint is Enterprise chat, skip the
      shell developer and fail the task as
      `developer_model_not_shell_capable` rather than looping 30
      evidence-only turns.
      (Revised PR #123: instead of failing as not-shell-capable, an
      Enterprise-chat model is driven with the chat-JSON-table protocol; a
      failed chat session falls back to `edit_payload` in the same turn, so
      the task still gets a mutation attempt and is never burned on 30
      evidence-only loops.)

#### 10.4.4 Proposal path (only after a dirty tree)

- [ ] On `FINISH_EDIT_SESSION` or session end, if `git status` /
      worktree diff is non-empty, `collect_changes` →
      `edit_proposals` must run even when the last LLM call was
      `unknown`. Today 33 successful commands still yield 0
      proposals because the tree never changed.
      (Wiring exists — `run_shell_developer_turn` collects changes after
      the session and gates them. NOT proven against a Soak4-shaped
      fixture yet; tick only once the §10.7 acceptance query shows
      `other_cmds > 0` and `edit_proposals > 0` on a seed naming an
      existing file.)
- [ ] Acceptance query (same DB shape as Soak4):

      ```sql
      -- other_cmds must be > 0 and proposals > 0 on a seed that
      -- names an existing file
      SELECT
        SUM(CASE WHEN command LIKE '%git rev-parse%' THEN 1 ELSE 0 END)
          AS evidence_cmds,
        SUM(CASE WHEN command LIKE '%git rev-parse%' THEN 0 ELSE 1 END)
          AS other_cmds
      FROM agent_responses_archive
      WHERE agent_name='developer' AND command IS NOT NULL;
      SELECT COUNT(*) FROM edit_proposals;
      ```

### 10.5 Tests (fixtures from Soak4)

Add to `tests/unit/test_shell_developer_protocol_recovery.py`
(and a thin `task_runner` latch test):

- [x] First assistant message is the Enterprise refusal (no bash).
      Expected: format error; evidence already ran in-process so
      no 2333-char “emit ls” inject.
- [x] Finish whose body discusses `FINISH_EDIT_SESSION` but does not
      start with that line → not `VALID_FINISH_SESSION`.
- [x] Finish that claims no filesystem after `marker_found=true` →
      rejected.
- [x] `echo "I do not have shell access"` is not evidence.
- [x] In-process evidence failure (empty temp dir) →
      `shell_workspace_validation_failed`, no LLM.
- [x] In-process evidence success + model emits
      `sed -n '1,80p' workflow/task_runner.py` → command runs,
      session continues.
- [x] Session with `commands_executed>=1` and `marker_found` plus
      `LlmUnavailable` does **not** set the zero-command latch.
- [x] `kind=unknown` records a model-health row with body excerpt.
- [x] (PR #122 follow-up) A 200 with `safetyRatings`/filter metadata
      **plus non-empty text** still returns the text; a true empty/policy
      body marks the endpoint failed and falls back; seed-prose version /
      domain tokens (`gemini-3.1`, `api.genai.mil`) do not abort.

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

---

## 8. Operator soak A-1 — ran (Soak4); remaining work is §10

**Priority:** ran (Soak4 after #121). Mutation failure tracked in §10.
**Live tree:** Windows Soak4-target

Code for recursive fallback, per-endpoint budget, and fail-closed
evidence **shipped in #121**. Soak4 confirmed worktree + evidence.
Gemini Enterprise still will not drive the shell — that is §10, not
a re-run of this 15-minute checklist.

### 8.1 Soak-watches (Soak4 already showed them — implement under §10)

- Finish-before-evidence injects burned full sessions: Soak4. Cap and
  fail-closed belong in §10.3 / §10.4, not a re-soak of this list.
- Evidence POSIX `test -f` / `ls` listing `workflow/` **worked** on
  Soak4 (`marker_found=true`). Do not reopen.

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
passed; criterion 6 failed (chat refusals / 0 proposals). Remaining
gate is §10.7, with developer ≠ Enterprise chat.

Historical pass criteria (kept for the next *non-Enterprise* soak):

1. Evidence command runs; `workflow/__init__.py` is in stdout. **met**
2. Lock endpoint A → one fallback to B; no `RecursionError`.
3. Burn A's token window → B used; burn both → clean stop.
4. Task status is `completed`, `no_change_required`, or `failed` with a
   reason — never stuck `in_progress`.
5. `--diagnostic` on the **target** DB matches the trajectory files.
6. No twelve `shell_session_no_mutation` chat refusals. **failed → §10**

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

- [ ] Quote SQL identifiers in `cli/commands.py` DB exports
      (`cmd_export_db`, `cmd_export_specific_tables`,
      `table_has_task_id`). `_quote_identifier()` = double-quote +
      escape embedded `"`. (`sqlite_master name=?` is already
      parameterized.)
- [ ] Comment/string-aware DDL split in `core/db.py`
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
| 1 | **§10 Soak4 mutation path** | §10.7 acceptance 1–7; developer ≠ Enterprise chat |
| 2 | §5 optional SQL quoting + DDL split | Export uses quoted ids; `;` in comments/strings does not split DDL |
| 3 | §1 NUC wiped `cmd_init` timing | Short burst; DELETE+NORMAL after return |
| 4 | §6 next-soak 429 dump | One dump; `Work:` not 0.0s from support latch |
| 5 | §7 live-hook / mini-swe e2e | When endpoints and a hook-fail copy exist |
