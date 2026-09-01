# Soak Runbook — live self-edit analysis with `utils/soak-setup.sh`

A **soak** runs a full PrizmForge control loop against a *copy of PrizmForge
itself*: the controller plans, edits, audits and reports on the target, which
is another checkout of the same repository. Observed over hours it gives a
full-cycle behavioural picture — prioritisation, mutation, endpoint
adaptation, budget discipline and self-editing — from copies of the codebase
editing themselves.

This runbook documents `./utils/soak-setup.sh` **as it stands** and how to
turn a soak's artifacts into an analysis report.

---

## 1. Layout

All soak state lives **outside the PrizmForge source repo**, under `SOAK_ROOT`.
The default is `PrizmForge-Soak/` one directory above the repo, so a soak never
sits on a git-ignored path of the enclosing repo (which would defeat the shell
developer's edit collection). Override with `SOAK_ROOT=/path`:

```
<repo>/utils/soak-setup.sh                           this script
<parent>/PrizmForge-Soak/SoakN/PrizmForge            controller copy (runs ./main.py)
<parent>/PrizmForge-Soak/SoakN-target/PrizmForge     edit target     (the copy being mutated)
<parent>/PrizmForge-Soak/SoakN-target/PrizmForge/
   .PrizmForge/agents.db                             runtime analytics DB (generated)
```

- The controller's `config.json` is rewritten so
  `project_directory = "../../SoakN-target/PrizmForge"`.
- The source repo's **`.git` history is copied** into both the controller and
  the target, and each gets its own branch (`soak/N` for the controller,
  `soak/N-target` for the target) at the source's HEAD. The source must be
  clean (no tracked, uncommitted changes) so the copied working tree matches
  HEAD — `soak-setup.sh` fails early otherwise. The target's repo is what the
  mini-swe shell developer's git-worktree machinery needs: it lets
  `git rev-parse` resolve to the target itself and `collect_changes()` stage +
  diff tracked edits so governed proposals can materialize. Previously the
  target was created *without git*, which silently produced zero collected
  edits.
- Analytics (`agents.db`) are generated at runtime inside the
  **target's** `.PrizMForge/` — the state dir name is `.PrizmForge` but both
  casings (`.prizmforge`) are treated identically. `main.py` stdout stays on
  the controller terminal (default buffering); nothing is written to a file.

## 2. Copy hygiene — what never crosses into a soak

`copy_tree` excludes, at any depth:

`.PrizmForge/`, `.prizmforge/`, `shell_trajectories/`,
`*.db`, `*.db-wal`, `*.db-shm`, `__pycache__/`, `.pytest_cache/`,
`.mypy_cache/`, `.ruff_cache/`, `*.pyc`.

The source's `.git` **is** copied (so soaks start with full history and a
clean HEAD). What is excluded:

- A soak always **starts with fresh process + analytics state**. The target
  generates its own `.PrizMForge/agents.db`, so no prior `endpoint_health`
  cooldowns, `resource_decisions` or token budgets are inherited — anything a
  run shows about throttling or budget is *its own* behaviour.
- No local dev state (API locks, trajectories, secrets in DBs) leaks into a
  soak copy.
- `git status` in a soak side is clean at start (enforced by the clean-source
  check) and each side branches from the copied HEAD.

### Retention across rounds

Running soak `N` first reduces every earlier soak to its **analytics only**:

- controller + target trees of `Soak1..Soak(N-1)` are purged of everything
  except their `.PrizMForge` / `.prizmforge` directory (which holds
  `agents.db`, reports, indexes). Where a soak produced no
  analytics it is emptied entirely.
- Re-running the *same* `N` with `--force` first **shelves** the current
  analytics into `$SOAK_ROOT/archive/SoakN.../PrizmForge/.PrizmForge/` before
  the tree is rebuilt, so history is never silently destroyed.

So the steady-state footprint of `$SOAK_ROOT` is a handful of analytics dirs,
not full repo copies.

## 3. Requirements

- `rsync` (fallback to `cp` works but is slower and heavier),
  `python3`, `git`.
- The source repo must contain a runnable `config.json` and `main.py`.
  Both `config.json` and `api_key.json` are git-ignored in the source, so
  they come from the local working tree (and are copied into each soak).

## 4. Usage

```
./utils/soak-setup.sh              # next unused N, then start main.py
./utils/soak-setup.sh 10           # explicit N
./utils/soak-setup.sh --dry-run    # print plan only (no changes)
./utils/soak-setup.sh --no-run     # copy + branch, do not start main.py
./utils/soak-setup.sh 10 --force   # overwrite existing Soak10 trees
SOURCE_REPO=/path ./utils/soak-setup.sh --dry-run
SOAK_ROOT=/path ./utils/soak-setup.sh --dry-run
```

The script:
1. Picks `N` (next unused, monotonic over existing `Soak*` dirs).
2. Fails early if the source repo has tracked, uncommitted changes (so the
   copied tree matches the copied HEAD).
3. Purges `Soak1..Soak(N-1)` to analytics (see §2).
4. Copies source (including its `.git`) → controller and → target, excluding
   analytics/caches.
5. Rewrites the controller `project_directory` and validates it resolves.
6. Checks out branch `soak/N` in the **controller** and `soak/N-target` in the
   **target**, both at the copied HEAD.
7. Runs `main.py` with stdout on the controller terminal (default
   buffering — no file capture).

A typical start:

```
./utils/soak-setup.sh 4
```

watch the terminal, then later:

```
./utils/soak-setup.sh 5          # purges Soak1..4, starts the next round
```

## 5. Runtime expectations

- `config.json` currently self-clips the local allowance to
  **16 calls/min per endpoint** (`rate_limit_per_minute`), below the free-tier
  ceiling, so a soak mostly paces itself instead of hammering the provider.
- Both configured endpoints are free-tier model lists
  (`openrouter/free`, `...:free`, opencode `*-free`). Free tiers do return
  429s under burst, so expect periodic:
  `Rate limit (...) sleeping Ns` → on 429 `agents/base.py` sleeps
  `Retry-After` (default 60 s) and falls back to the other endpoint → the
  orchestration layer persists `RATE_LIMITED` (2-min) and escalating
  `KEY_LOCKED` (30-min) cooldowns into `endpoint_health`. **This is expected
  cheap-tier behaviour, not a setup bug** — a run's throttling is entirely
  its own (fresh DB every soak).
- Orchestration treats transport failures as **neutral** (d9 / "mutation path
  is the most unblocked path"): a failed session never freezes the
  developer, and the loop re-arms each cycle, so the developer retries the
  mutation path as soon as an endpoint recovers.

## 6. Full-cycle analysis

After (or mid) soak, interrogate the **target** analytics:

| Artifact | What it answers |
|---|---|
| controller terminal `main.py` output | Whole-loop narrative: iterations, agent dispatch, sleeps, fallbacks, decisions, errors. |
| `.PrizmForge/agents.db` | Structured state (tables below). |
| `.PrizmForge/reports/`, `.PrizmForge/indexes/` | Reporter artifacts and the built `INDEX.md` symbol map. |
| controller `audit/` | Prompts/responses trail of the loop's own reviewing agents. |

Key tables in `agents.db` (read-only; `sqlite3`, or copy the DB out):

- `endpoint_health` — `endpoint_name, status, error_count,
  consecutive_failures, last_success, unavailable_until, last_updated`.
  The rate-limit/health narrative of the run.
- `resource_decisions` — orchestration decisions: active agents, budget %,
  tokens remaining, per-agent cadence, rate-limit adjustments.
- `token_log` — daily/4h budget burn over time.
- `tasks` — task lifecycle (created → picked → completed/stalled).
- `file_modifications` + `file_write_log` — exactly what the target was
  mutated with: the self-edit trail.
- `events`, `errors`, `llm_interactions`, `messages` — the event/call trail.
- `model_health_events`, `endpoint_fallbacks` — model ranking changes and
  fallback switches.
- `reporter_state` — what the reporter last published.

Suggested analysis loop:

1. **Continuity:** read the controller terminal output for hard stalls vs
   pacing; confirm
   "Rate limit" episodes correlate with `endpoint_health` cooldowns and not
   with deadlocks.
2. **Mutation:** count `file_modifications` per task; confirm stall tasks ran
   to genuine "finished with no change", not transport-freezes (d9 makes
   failed sessions neutral).
3. **Planning quality:** correlate `tasks` with `resource_decisions` — did
   the prioritizer keep a focused queue, or did backlog churn dominate?
4. **Budget:** trace `token_log` against `resource_decisions` budget %.
5. **Self-editing:** diff `file_write_log` targets to see which parts of the
   copy PrizmForge chose to modify — the self-edit signature.

## 7. Operations notes

- **Never edit anything under `$SOAK_ROOT`.** It is disposable analysis state.
  Changes belong in the main repo; re-`soak-setup` to bake them into a copy.
- Soak numbering is monotonic; purged dirs still occupy their number.
- `--force` on an existing `N` shelves that soak's analytics into
  `$SOAK_ROOT/archive/` first — nothing is ever destroyed out of hand.
- Anything that starts with `.retain-` in `$SOAK_ROOT` is a leftover of a
  purge that was interrupted; it is safe to delete.