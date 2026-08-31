# Shell Developer (mini-swe-agent style) — Capability Runbook

This document expands the README's [Governed Editing](../README.md) section into a
guide for the **shell developer** (`developer.implementation = "shell"`): how to
enable it, what a session does, and how to operate it safely on a target repo.

It is a **current‑behavior** document — the shell developer shipped and stabilized
across review, cold‑start, and soak rounds. Open follow‑ups live in
[`docs/ROADMAP_TODO.md`](ROADMAP_TODO.md) §3 (mini‑swe agent open items); the
authoritative `config.json` schema is [`docs/CONFIGURATION.md`](CONFIGURATION.md).

---

## 1. What it is

The shell developer is a native port of
[mini-swe-agent](https://github.com/SWE-agent/mini-swe-agent) (MIT) that replaces
the legacy structured `EditPayload` developer. Instead of emitting a JSON payload
blind, the model works **inside a disposable `git worktree`** with real bash: it
can read files, edit them, and run tests before it submits anything.

Everything it produces still flows through the **governed mutation path**:

```
shell session (worktree + bash)
  → changed files → EditPayload proposals (create_file / full_replace)
  → Reviewer gate (fails closed) → materialize (disk + git)
```

All model calls route through `call_endpoint()`, so rate limiting, token budget,
endpoint health, and fallback governance apply unchanged. Background agents can
never mutate; the shell developer is the only write path, and only via an
approved proposal.

---

## 2. Enabling and configuring

### 2.1 Enable

```json
"developer": { "implementation": "shell" }
```

- `"shell"` is the default in `example_config.json`. The code fallback when the
  key is absent is `"edit_payload"` (legacy).
- The shell implementation **requires git** (`git worktree`). `utils/setup.sh`
  already checks for git and warns in the setup summary if it is missing.

### 2.2 Recommended profile

```json
"shell_developer": {
  "step_limit": 30,
  "wall_time_limit_minutes": 20,
  "command_timeout_seconds": 120,
  "test_timeout_seconds": 600,
  "max_output_chars": 6000,
  "max_consecutive_format_errors": 3,
  "test_command": "python -m pytest tests/ -x -q",
  "on_test_failure": "discard",
  "model": null,
  "worktree_parent": ""
}
```

| Key | Default | Meaning |
|-----|---------|---------|
| `step_limit` | `30` | Max model replies per session. |
| `wall_time_limit_minutes` | `20` | Wall-clock session cap; also caps each command's timeout to the remaining budget. |
| `command_timeout_seconds` | `120` | Per-bash-command timeout. |
| `test_timeout_seconds` | `600` | Timeout for `test_command`. |
| `max_output_chars` | `6000` | Command output truncated to this size when fed back to the model. |
| `max_file_bytes` | `512_000` | Files larger than this are skipped at proposal time (status `S`). |
| `max_consecutive_format_errors` | `3` | Abort after N replies with no bash block or finish token. |
| `test_command` | `""` | Post-session verification. Empty disables the verify step. |
| `on_test_failure` | `discard` | `discard` (fail closed) or `propose_anyway`; invalid values fall back to `discard` with a warning. |
| `model` | `null` | Session model override; `null` uses the orchestrator decision model, then `default_model`. |
| `worktree_parent` | `""` | Where scratch worktrees are created (default: system temp). |

---

## 3. How a session runs

1. **Worktree creation** — a disposable `git worktree` of the project is created
   and synced with governed state (`sync_governed_state()`): every tracked,
   non-deleted governed file is rewritten from the DB and DB-deleted files are
   removed. A **baseline tree** is snapshotted right after sync
   (`git add -A` + `git write-tree`) so only agent-authored work counts as
   "change" — pre-existing DB/HEAD drift is never attributed to the model.
2. **Control loop** — each model reply runs the **last** ```bash fenced block in
   the worktree, feeds the output back, and repeats. Sessions end on the
   `FINISH_EDIT_SESSION` sentinel, `step_limit`, the wall-clock limit, or
   `max_consecutive_format_errors`.
   - A reply containing both a command **and** the finish token executes the
     command first, then asks the model to confirm finishing (forced finish
     after 3 deferrals).
3. **Verification** (optional) — when `test_command` is set, it runs post-session
   against the edited worktree.
   - Exit `0` → the exit code + output tail are embedded in the proposal
     rationale as evidence for the Reviewer.
   - Non-zero + `on_test_failure: discard` → the session is **discarded**
     (fail closed). Non-zero + `propose_anyway` → proposals proceed.
4. **Collection** — `collect_changes()` diffs against the baseline and maps to
   operations: `A→create_file`, `M→full_replace`, `D→delete_file`, oversize
   files → `S` (skipped, logged with size).
5. **Governed handoff** — changed files become EditPayload proposals through the
   standard `create_proposal_from_developer_output()` path, pass the Reviewer
   gate, and materialize. The Reviewer gate **fails closed**: a missing,
   unparseable, or unknown `decision` REJECTs the proposal.

---

## 4. Safety notes

- **The worktree is disposable.** Anything the agent does outside the worktree is
  not collected; `collect_changes()` compares against the post-sync baseline, so
  uncommitted materializations already in the DB are never re-proposed as agent
  work.
- **Shell escape is a known limitation.** Bash runs with `cwd=worktree` but is
  not OS-sandboxed; only worktree-internal changes are collected. For enclave
  deployment, pair with container / approved-workstation controls (roadmap §3).
- **`delete_file` is governed.** Deletions map to the governed `delete_file`
  operation at proposal time — the reviewer gate must approve before any removal.
- **Binary/secret guards still apply** — content safety and repo-policy filters
  run on the governed write path regardless of the developer implementation.

---

## 5. Audit artifacts

Every session trajectory is serialized to
`.PrizmForge/shell_trajectories/<task>-turn<N>-<UTC>.json` (RMF evidence): the
model/command/observation transcripts for the session. Packaging
(`utils/export_project_zip.py`) excludes `shell_trajectories/`, `*.db`, and
`.sqlite*` so no runtime artifacts leak into a packaged archive.

---

## 6. Rollback

Set the legacy structured flow — no code change:

```json
"developer": { "implementation": "edit_payload" }
```

(or remove the `developer` key entirely).

---

## 7. Troubleshooting

| Symptom | Next step |
|---------|-----------|
| Session never starts / immediate abort | Git missing or not a repo — the shell implementation requires `git worktree`. |
| "Verification failed … policy=discard" | `test_command` exited non-zero and the edit was discarded by design. Fix `test_command` (path, virtualenv) or accept `propose_anyway`. |
| `⚠️ Skipping oversize file` | File exceeds `max_file_bytes`; raise it or split the change. |
| Changes outside the worktree missing | Intended — only worktree-internal (post-baseline) diffs are collected. |
| Repeated format errors abort the session | Endpoint flakiness/format drift — check `health` / `--model-health`; the no-progress guard treats this as neutral (never freezes mutation). |

---

## 8. History

Shipped and merged into `main` 2026-08-23 → 2026-08-28 across review,
cold-start, and soak process-eval rounds (gates 616 → 623 → 693 → 724) plus
post-merge residuals in the 2026-08-29 closed-loop batch. MIT attribution and
material differences from upstream: `THIRD_PARTY_NOTICES.md`. All remaining
follow-ups and shipped-plan provenance are tracked in
[`docs/ROADMAP_TODO.md`](ROADMAP_TODO.md) §3.