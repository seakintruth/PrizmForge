# Benchmark v1 — §12.2 P1 boxed benchmark (internal soak-task set)

Status: **planned** — this spec drives the §12.2 build (docs/TODO.md).
Scope: a deterministic, zero-new-dep coding-task benchmark over **crafted
canonical tasks**, driving existing `run_task_cycle` sequentially and scoring
each trial with a **verifier**.

## 1. Decisions (locked 2026-09-10)

- **Verifier = FINISH-evidence gate + content assertions.**
  A trial passes only when it (a) finished with a real session / terminal
  status (no zero-command finish, no stall/timeout) and (b) the governed file
  state satisfies the task's content contract. FINISH-evidence-only would be
  weak (Soak18 confound), so content is asserted too.
- **Task set = 5 crafted canonical tasks** (expand to 8 later). Independent of
  soak history so the benchmark is stable and reproducible.
- **Concurrency = sequential k trials per task.** SQLite stays single-writer
  (DELETE + NORMAL, §9.4); no parallel worktree driver in v1.
- **Dependency posture = unchanged.** Stdlib + existing machinery only
  (`run_task_cycle`, `initialize_file_lines`, `get_file_content_from_db`,
  `harness/fingerprint.py` rollouts, `failure_mode_mix`).

## 2. Task manifest

`harness/benchmark/tasks.json` — one entry per task:

```json
{
  "task_id": "t01_rename_constant",
  "seed": "Rename OLD to NEW in app.py",
  "k": 2,
  "fixture": {"app.py": "value = OLD\n"},
  "contract": [
    {"file_path": "app.py", "fragment": "value = NEW\n", "mode": "contains"}
  ]
}
```

| id | seed | fixture | contract |
|---|---|---|---|
| t01 | Rename OLD to NEW in app.py | app.py `value = OLD\n` | contains `value = NEW\n` |
| t02 | Change add() to accept a third parameter c and return a+b+c | app.py `def add(a,b):\n    return a + b\n` | contains `def add(a, b, c):` and `return a + b + c` |
| t03 | app.py has a syntax error; fix the function definition | app.py `def broken(:\n    pass\n` | contains `def broken():` |
| t04 | app.py calls json.dumps but never imports json; add the missing import | app.py `def use_json():\n    return json.dumps({})\n` | contains `import json` |
| t05 | Replace the TODO comment in app.py with a DONE marker | app.py `# TODO: implement\nclass C:\n    pass\n` | contains `# DONE` |

`mode` ∈ {`contains`, `exact`, `absent`}. Rendered contract for the
fingerprint lives in `harness/benchmark/` — it is **not** part of the agent
prompts, so it does not feed `_prompt_hash()`.

## 3. Verifier

`harness/verify.py` → `verify_trial(task, rollout_row) -> Verdict`:

1. **Evidence gate**: `rollout_row["status"] == "passed"` (which already
   excludes stalled / timed_out / failed / zero-command-failed runs).
2. **Infra/timing** (checked before the gate): `rollout_row["infra_abort"]`
   or status `infra_aborted` → verdict `infra_aborted` (counts as a pass@1
   failure, excluded from root-cause blaming — §12.1).
3. **Content check**: for each `contract` assertion, read governed content
   via `core.file_operations.get_file_content_from_db(file_path)` and compare
   by `mode`. Any miss → `failed` with note `content:<path>:<mode>`.
4. Otherwise → `passed`.

Verdict values: `passed | failed | infra_aborted`. Every claim carries a note
and a `component_hint` from the fixed enum (§4.3 of the design doc):

```
component_hint ∈ {harness_prompt, tool, middleware, skill, memory,
                  subagent, worktree, endpoint, task_contract,
                  parallel_worker, database, verifier}
```

## 4. Driver + accounting

`harness/benchmark/driver.py` → `run_trial(...)` / `run_benchmark(...)`:

- For each task in the manifest, in order, for `trial` in `1..k` (sequential):
  1. Re-init fixture: write fixture files under the bench project dir and
     `initialize_file_lines(path, content)` into governed DB (deterministic
     base per trial).
  2. `task_id = "<task_id>_i<iter>_t<trial>"`.
  3. `create_rollout(task_id, iteration=<iter>, fingerprint=...)` tag the
     `contract_hash` (sha256 of the task's manifest entry).
  4. `run_task_cycle(task_id, seed, max_turns)`.
  5. `finalize_rollout(task_id, <task status>)` (idempotent).
  6. `verify_trial(task, latest_rollout(task_id))` → write verdict +
     verdict_note onto the rollout row.
- Emit `runs/<iter>/results.json` (resolved under the bench project dir):
  `{iteration, created_at, harness_fingerprint, max_turns, tasks: [{task_id, k,
  passed, infra_aborted, trials: [{trial, verdict, note, tokens}]}], pass@1}`.
- pass@1 = `passed_trials / (tasks * k)`; infra_aborted + stalled +
  timed_out count as failures (`PASS1_FAILURE_STATUSES`), and
  `failure_mode_mix(iteration)` stays the source of truth for the split.

## 5. CLI

```
python -m harness.benchmark --iter 1 --max-turns 5 [--project-dir PATH]
```

Installs a bench config (temp project dir, background agents off, `mock`
default endpoint) over the module-level `get_config()` bindings for the
duration of the run (same technique as the integration tests), runs the
benchmark, prints pass@1 + failure-mode split, and writes `runs/<iter>/`.

## 6. Out of scope (v1)

Terminal-Bench 2 / SWE-bench-verified, Docker OS sandboxing, parallel worktree
trials, entrypoint/command verifiers (the shell-sandbox limitation), editing
`harness/` by the loop (§12.5), attribution ablations (§12.6), cross-model
transfer.