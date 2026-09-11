# PrizmForge Harness Evolution — Design

**Status:** draft design only — not implemented
**Date:** 2026-09-09
This document designs the three observability pillars of a harness-evolution
loop — **component**, **experience**, and **decision** observability — expressed
against PrizmForge's existing substrate: governed
editing, the reviewer gate, `events`, `undo_proposal`, git, and the background
agent pool. It is a design spec, not a gap analysis; decisions are left open in
[§8 Open decisions](#8-open-decisions).

Related current-state docs: [`architecture.md`](architecture.md),
[`UNATTENDED_CLOSED_LOOP_CAPABILITIES.md`](UNATTENDED_CLOSED_LOOP_CAPABILITIES.md),
[`mini_swe_agent.md`](mini_swe_agent.md).

---

## Table of Contents

- [1. Background & design principles](#1-background--design-principles)
- [2. Harness workspace](#2-harness-workspace)
- [3. Component observability — harness substrate](#3-component-observability--harness-substrate)
- [4. Experience observability — trajectory evidence corpus](#4-experience-observability--trajectory-evidence-corpus)
- [5. Decision observability — change manifest](#5-decision-observability--change-manifest)
- [6. Evolve Agent + closed loop](#6-evolve-agent--closed-loop)
- [7. Evaluation & metrics](#7-evaluation--metrics)
- [8. Open decisions](#8-open-decisions)

---

## 1. Background & design principles

Harness optimization can be turned into a closed loop driven by a separate
agent, with the base model held fixed and only the explicit harness edited. The
central claim of this design: each phase of the loop must be *observable*,
represented as structured, layered artifacts another agent can read and act on.
Expected value concentrates in tools, middleware, and long-term memory rather
than in the system prompt, so a decoupled substrate is required to make those
components editable.

PrizmForge already owns the machinery the loop needs for safety: a governed mutation
path (`EditPayload → Proposal → Reviewer → materialize_proposal()`), file-level
git versioning, `undo_proposal` snapshots, and an observability layer (`events`,
`errors`, endpoint/token health). What it lacks is a harness substrate that makes
*five* additional component types editable, a trajectory-distillation pipeline,
and a change-manifest loop that verifies and reverts harness edits.

Design principles:

1. **Reuse, do not rebuild.** The evolution loop rides the governed mutation
   path and reviewer gate; it does not add a parallel editing mechanism.
2. **Every harness edit is a file.** A logical edit is one commit, yielding
   file-level diffs and rollback for free (existing git + `undo_proposal`).
3. **Target-code loop and harness-evolution loop are separate concerns.** The
   existing loop improves `project_directory`; the evolution loop improves
   PrizmForge's own harness. They must not share an editor surface.

---

## 2. Harness workspace

New top-level workspace, versioned as its own git history so every evolution
iteration is taggable and revertible at file granularity:

```
harness/
  system_prompt/            # system prompt fragments (per agent role)
    developer.md
    reviewer.md
  tools/
    descriptions/           # tool description files (one per tool)
    implementations/        # tool implementations (shell_developer.py is reused)
  middleware/               # NEW — pre/post-step hooks
  skills/                   # NEW — reusable procedural lessons
  subagents/                # sub-agent configuration files
  memory/                   # NEW — long-term memory lessons
  manifest/                 # change manifests, one JSON per iteration
  README.md                 # mount-point map
```

The existing `agent_prompts.json` / `config.json` remain the operator-owned
source until the evolution loop is implemented; the workspace above is the
evolved, file-level representation the Evolve Agent edits.

---

## 3. Component observability — harness substrate

### 3.1 Component → mount-point mapping

| Component type | PrizmForge current home | Status | Evolved mount point |
|---|---|---|---|
| system prompt | `agent_prompts.json` (per role) | present | `harness/system_prompt/<role>.md` |
| tool description | `agent_schemas/developer.json`, config tool defs | partial | `harness/tools/descriptions/<tool>.md` |
| tool implementation | `workflow/shell_developer.py`, `file_editing/` | present | `harness/tools/implementations/<tool>.py` |
| middleware | — none — | missing | `harness/middleware/<hook>.py` |
| skill | — none — (`Federation/` is governance docs only) | missing | `harness/skills/<skill>.md` |
| sub-agent configuration | `config.json` `agent_model_preferences`, `background_agents` | present | `harness/subagents/<role>.json` |
| long-term memory | `archivist` → `archived_context` (automatic compression, not editable lessons) | partial | `harness/memory/*.md` |

### 3.2 Middleware design (new)

Middleware are orthogonal hooks that wrap a step without requiring prompt edits.
One file per hook, declared by filename, e.g.:

```python
# harness/middleware/finish_closure_check.py
HOOK_POINTS = ["pre_finish"]  # pre_finish | post_resume | post_edit | pre_finish


def run(ctx) -> MiddlewareResult:
    """Force one evaluator-isomorphic closure check before FINISH_EDIT_SESSION."""
    if not ctx.has_flag("closure_checked"):
        return MiddlewareResult(block=True, reason="closure_checked_missing")
    return MiddlewareResult(block=False)
```

`ctx` exposes read-only trajectory state (last command, file-change set,
`workspace_evidence`) plus a *write-only* flags surface (`ctx.set_flag`). The
finish-hook enforces a single evaluator-isomorphic closure check before emitting
`FINISH_EDIT_SESSION`.

### 3.3 Skill design (new)

Skills are concise, referencable procedural files loaded into context when the
agent invokes them by name (explicit action space, no implicit prompt prose):

```markdown
# skills/verify_closure.md
## When
Before declaring a task complete after edits.

## Steps
1. Re-run the target's test/entrypoint in the worktree.
2. Diff observed output against the task contract.
3. Only then emit FINISH_EDIT_SESSION.
```

### 3.4 Long-term memory design (new)

A curated, editable lessons store — not automatic archivist compression. One
`.md` per lesson, named by the boundary-case it encodes:

```markdown
# memory/queued_over_limit_cancellation.md
## Boundary case
Task queues a >limit operation instead of cancelling it.
## Rule
Queued-over-limit must cancel, never enqueue.
## Evidence ref
trajectory:task/<id>/...  report:<task_id>
```

### 3.5 Rollback

Because each logical harness edit is one file and one git commit:

- **Revert** = `git revert <edit_commit>` on the harness workspace.
- **Undo** = `undo_proposal(<proposal_id>)` reusing existing pre-apply snapshots
  when the edit went through the governed pipeline.

---

## 4. Experience observability — trajectory evidence corpus

### 4.1 Layered layout

Raw rollouts already exist (`.PrizmForge/shell_trajectories/`). Add a distilled,
progressive-disclosure corpus branching from it:

```
runs/<iteration>/
  raw/                       # existing shell_trajectories (unchanged)
  cleaned/                   # strip base64, dedup repeated tool output
    <task_id>.jsonl
  analysis/
    <task_id>.md             # per-task root-cause / success pattern
  overview.md                # benchmark-level aggregation (entry point)
  index.json                 # drill-down map: overview -> tasks -> traces
```

### 4.2 Cleaning pass

The cleaning pass drops base64-encoded blobs and dedups repeated tool output.
Reuse Soak4-era cleanup heuristics: drop `data:...;base64,...` blobs and collapse
identical consecutive tool-result frames, then write `<task_id>.jsonl`.

### 4.3 Debugger producer role

A support-layer worker (same pattern as `agents/parallel_workers.py`) consumes
`runs/<iteration>/cleaned/` and emits `analysis/<task_id>.md` + `overview.md`.

Prompt sketch (one-shot, per task):

```text
You are the Agent Debugger. Read <task_id>'s cleaned trajectory files.
Produce ONLY a JSON report with:
- task_id
- passed: bool
- root_causes: [ {evidence_file, inferred_root_cause, component_hint} ]
  where component_hint is one of:
  harness_prompt | tool | middleware | skill | memory | subagent |
  worktree | endpoint | task_contract | parallel_worker | database | verifier
- success_patterns: [ ... ] (when passed)

Ground every claim in a file path. Do not speculate past the evidence.
```

`overview.md` is then aggregated: failing tasks grouped by `component_hint`,
passing tasks grouped by `success_patterns`, with the `index.json` drill-down
paths attached so the Evolve Agent can verify claims progressively (raw traces
stay available and untouched).

---

## 5. Decision observability — change manifest

### 5.1 Schema (file-level JSON per iteration)

`harness/manifest/iteration-<t>.json`:

```json
{
  "iteration": 5,
  "base_harness_tag": "iter-4",
  "base_pass1": 0.718,
  "edits": [
    {
      "edit_id": "iter-5-01",
      "component_type": "long_term_memory",
      "target_file": "harness/memory/queued_over_limit_cancellation.md",
      "commit": "abc1234",
      "evidence_refs": ["runs/4/analysis/task-17.md", "runs/4/cleaned/task-17.jsonl"],
      "inferred_root_cause": "Queued >limit op instead of cancelling",
      "predicted_fixes": ["task-17", "task-22"],
      "predicted_regressions": ["task-41"],
      "rationale": "12 boundary-case lessons; adds cancellation closure rule."
    }
  ]
}
```

`predicted_fixes` / `predicted_regressions` name **specific tasks** so the next
round can compute per-edit verdict precision/recall.

### 5.2 Next-round attribution (SQL sketch)

Verdict query — intersect prior predictions with observed task-level deltas:

```sql
WITH prior AS (
  SELECT json_each.value AS edit_id
  FROM json_each(
    (SELECT payload FROM harness_change_manifest WHERE iteration = :prior_iter)
  ),
  json_each(edits) AS e,
  json_each(e.value -> 'predicted_fixes') AS fix
  -- (flatten edits[].predicted_fixes[]; edit_id = e.value->>'edit_id')
),
deltas AS (
  SELECT task_id
  FROM task_outcomes t_cur JOIN task_outcomes t_prev
    ON t_cur.task_id = t_prev.task_id
  WHERE t_cur.iteration = :cur_iter AND t_prev.iteration = :prior_iter
    AND t_cur.passed = 1 AND t_prev.passed = 0   -- fixed this round
),
verdicts AS (
  SELECT edit_id,
         SUM(CASE WHEN fix.task_id IN (SELECT task_id FROM deltas) THEN 1 ELSE 0 END) AS fixes_confirmed,
         COUNT(fix.task_id) AS fixes_predicted
  FROM prior
  GROUP BY edit_id
)
SELECT edit_id, fixes_confirmed, fixes_predicted, fixes_confirmed / fixes_predicted AS precision
FROM verdicts;
```

Concretely: store the manifest JSON (or its parsed columns) in a
`harness_change_manifest(iteration, payload JSON)` table, and task outcomes in
`task_outcomes(iteration, task_id, passed, tokens)`.

### 5.3 Rollback rule

An edit is **reverted** at file granularity when its verdict fails a threshold:
- `confirms == 0` (no predicted fix landed), **and**
- regressions landed that it flagged or that outnumber confirmed fixes.

Revert = `git revert <edit.commit>` on the harness workspace (or
`undo_proposal` if governed). Reverting happens *before* the next distillation so
the verdict lands inside the evidence corpus the Evolve Agent reads — the edit
becomes a falsifiable contract, not a rationale.

### 5.4 Controllability constraints

The Evolve Agent writes **only** inside `harness/` (and the versioned
`agent_prompts.json`-equivalent files). Read-only, uneditable surfaces:

- `runs/` (rollout artifacts)
- tracer / verifier / sandbox configuration
- LLM endpoint + model configuration (`config.json` `endpoints`, `default_model`)

Seed prompt files are marked non-deletable. These restrictions block the
self-modifier shortcuts (disable verifier, swap model, raise budget) and keep
every recorded gain attributable to harness edits.

---

## 6. Evolve Agent + closed loop

### 6.1 Role prompt sketch

```text
You are the Evolve Agent. You improve the coding-agent HARNESS, not the target
repository.

Constraints:
- Write ONLY under harness/ (system_prompt/, tools/, middleware/, skills/,
  subagents/, memory/, manifest/).
- runs/, tracer/verifier/sandbox, and LLM endpoint config are READ-ONLY.
- The seed system prompt is non-deletable.
- Every edit MUST carry a manifest entry: evidence refs, inferred root cause,
  predicted_fixes (task ids), predicted_regressions (task ids).

Inputs per iteration: runs/<iter>/overview.md, runs/<iter>/analysis/*.md,
runs/<iter>/index.json, and prior manifest verdicts.

Output: structured edit list (JSON), committed one logical edit per commit.
```

### 6.2 Phase list

For `t = 1..N`, all on a fixed base model `M` and benchmark `D`:

1. **Rollout** — `k >= 2` rollouts per task under harness `H_{t-1}`.
2. **Clean** — strip base64, dedup tool output → `runs/<t>/cleaned/`.
3. **Attribute** (t ≥ 2) — run §5.2 verdict on prior manifest `C_{t-1}` using
   `T_{t-1}` vs `T_t`; **Rollback** any failed edits via git revert.
4. **Debug/Distill** — debugger worker emits per-task analysis + overview.
5. **Evolve** — Evolve Agent edits `harness/` + writes manifest `C_t`.
6. **Commit** — tag iteration in harness git (`iter-<t>`).
7. **Track best** — `H_best ← H_t` when `Pass@1(T_t) > Pass@1(H_best)`.

### 6.3 Seed harness minimality

Decide (see §8) whether the seed is the current full PrizmForge harness or a
minimal bash-only harness. Minimality preserves edit attribution (every added
component must earn its place against measured rollouts); starting from the
current full system makes each measured delta noisy.

---

## 7. Evaluation & metrics

Metrics reported per harness configuration:

- **pass@1** — mean binary success over `k` rollouts per task; infrastructure-
  aborted / timeout trials count as failures.
- **tokens/trial** — mean prompt+completion tokens, excluding aborted trials.
- **Cross-benchmark transfer** — frozen harness re-run on SWE-bench-verified
  without re-evolution (success rate + token cost).
- **Cross-model transfer** — frozen harness re-run on alternate bases.
- **Component ablation** — swap a single evolved component into the seed
  (`+ memory only`, `+ tool only`, `+ middleware only`, `+ system_prompt only`)
  to attribute the gain, e.g. tools/middleware/memory carry value while the
  prompt alone may regress.

**Prerequisite (Phase 0, out of scope of this design):** PrizmForge currently has
**no coding-task benchmark harness**. Terminal-Bench 2 and SWE-bench-verified
integration — sandboxed execution + verifier + tracer + concurrency, per
[`mini_swe_agent.md`](mini_swe_agent.md), which already flags shell-escape
sandbox pairing as a known limitation — must land before any rollout/attribution
loop can run.

---

## 8. Open decisions

| # | Decision | Options | Notes |
|---|---|---|---|
| 1 | Benchmark & where it runs | Terminal-Bench-class vs. internal soak-task set | Sandboxing is a prerequisite (`mini_swe_agent.md` known limitation) |
| 2 | Seed harness | Current full harness vs. minimal bash-only | Minimality preserves attribution (§6.3) |
| 3 | Middleware hook points | `pre_finish` / `post_resume` / `post_edit` only, or expandable | Start with a fixed enum to keep the action space explicit |
| 4 | Manifest storage | JSON files vs. `harness_change_manifest` SQL table | Files = free diffs/rollback; table = easy verdict queries. Adopt files, mirror into table for the verdict SQL |
| 5 | Compute budget per iteration | Rollouts needed per iteration, concurrency | RC-style budgets (`max_tokens_per_4h`) should gate, not be bypassed by the loop |
| 6 | Evolve Agent's own model | Same base model as code agent vs. separate | All role agents share one base model — isolates the gain to harness edits |