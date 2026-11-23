# prizmforge-pi-governance

**Status:** design sketch (not implemented)
**Date:** 2026-11-23
**Proposed package name:** `prizmforge-pi-governance`
**Supersedes:** the human-approval-centric sketch merged in PR #160. Human review happens only before merge, not on every change.

A TypeScript [Pi](https://docs.pi.dev/latest/extensions) overlay that ports PrizmForge's *unattended* governed loop onto the Pi coding agent: a long-running orchestrator drives a developer agent and several independent reviewer agents. Reviewer agents, not a human, must fail-closed agree before work progresses. The only human step is reviewing the pull request before merge. Agents never merge.

## 1. Goal

Run for hours with no stdin, the way PrizmForge's unattended closed loop does today (`docs/UNATTENDED_CLOSED_LOOP_CAPABILITIES.md`, `workflow/`, `agents/`, `workflow/reviewer_gate.py`):

- A sequential mutation path: orchestrator → developer (branch or worktree) → proposal → **multi-agent reviewer gate** → tests/CI → commit on the branch → open or update a PR → next item.
- Several independent reviewer agents (separate Pi sessions or subagents, different models or prompts, **read-only tools**) must agree before a proposal proceeds.
- Gates **block by default**. A missing, unparseable, or unclear verdict is a `REJECT`. Nothing auto-approves. Rejected work returns to the developer with the reviewers' comments.
- The loop covers security scans, maintenance and dependency upkeep, lint and test fixes, and small feature improvements, drawn from a backlog.
- Automatic safety rails — path denies, sandbox, audit log, token budgets, stall limits, tests and CI — run without a human in the loop.
- A human reviews the PR and merges it, or does not. That is the only required human gate.

## 2. Non-goals

This design will **not**:

- Stop for per-change human approval, `ctx.ui.confirm` prompts, or a required `/approve` step. Those are optional overrides, off by default.
- Let agents merge to the default branch, or push to `main` / `master`.
- Reimplement PrizmForge's SQLite `file_lines` / `EditPayload` / `agents.db` schema. The *loop and gate* transfer; the storage does not have to.
- Treat hooks as OS isolation. Compose a sandbox package, and for enclave or self-edit work run Pi in a container/VM.
- Make reviewer "read-only" a prompt convention only. Tool access must be enforced.
- Require an interactive TUI. The default run is headless.

## 3. Mapping PrizmForge controls to Pi

| PrizmForge control | Pi mechanism | Fit |
| --- | --- | --- |
| Unattended closed loop (no stdin, hours-long) | Host orchestrator using the [SDK](https://docs.pi.dev/latest/sdk) (`createAgentSession`, `session.prompt`) and/or [RPC / print / JSON modes](https://docs.pi.dev/latest/cli-integration) (`pi --mode rpc`, `pi --print`, `pi --mode json`) | Feasible |
| Orchestrator decides next agent (`developer` / `background` / `complete`) | Host loop that starts or prompts child sessions; must not let the developer self-approve | Feasible |
| Developer works in a disposable git worktree | Orchestrator creates a branch and `git worktree` via `pi.exec` (no shell) or a host `git` call; developer session `cwd` is that worktree | Feasible |
| Structured proposal, then reviewer gate | Buffer developer `write`/`edit` (and mutating `bash`) as a proposal; do not materialize until the reviewer panel agrees | Feasible |
| Fail-closed reviewer (`workflow/reviewer_gate.py`) | Each reviewer returns strict JSON `APPROVE`/`REJECT`; empty, non-JSON, unknown, or failed calls are `REJECT` | Feasible |
| Several analysis agents with no write rights (`jr_reviewer`, `security_reviewer`, …) | Independent reviewer sessions/subagents with `write`/`edit` deactivated and `tool_call` hard-blocks; different models or prompts | Feasible, with enforcement |
| Background findings → prioritizer → backlog | Orchestrator-owned backlog (security, maintenance, deps, lint/tests, small features). A full prioritizer port is later | Partial in MVP |
| Tests as a fail-closed verify gate | Run `test_command` after reviewer agreement; non-zero exit discards or returns the proposal | Feasible |
| Git commit on success; hook failure becomes developer feedback | `pi.exec("git", …)` in the worktree; never `merge` or `gh pr merge` | Feasible |
| Human reviews only at merge | Agents open or update a PR on the branch; they cannot merge | Feasible (`gh` / API via the host; exact tool is an open question) |
| Path containment; secrets never served | `tool_call` hard-denies on `.env`, `.git`, `api_key.json`, `~/.ssh`, and paths outside the worktree/repo root | Feasible |
| Append-only mutation log | `pi.appendEntry("prizmforge-proposal", data)` plus a host-level run log | Feasible |
| Token budgets, stall / no-progress latch, duration cap | Orchestrator enforces `max_tokens_*`, `max_duration_hours`, and a re-arming stall latch (network failures are neutral, as in PrizmForge) | Feasible |
| OS sandbox | Compose [pi-permission-modes](https://pi.dev/packages/pi-permission-modes) or [@gotgenes/pi-permission-system](https://pi.dev/packages/@gotgenes/pi-permission-system) plus a sandbox package | Compose, not rewrite |
| Optimistic concurrency and overlapping-proposal invalidation | Hash at queue time; re-check at apply | Phase 2 |
| Hooks as a security boundary | Not possible. Extensions run in-process with Pi's permissions ([Run Pi safely](https://docs.pi.dev/latest/security)) | Not feasible alone |

## 4. Architecture

```
Host orchestrator  (Node/Bun SDK and/or RPC client; no TUI)
    │
    ├─ backlog: security, maintenance/deps, lint+tests, small features
    ├─ budgets, stall latch, duration cap
    │
    ├─ developer session   (worktree/branch; write tools allowed only there)
    │     └─ tool_call buffers mutations as a proposal
    │
    ├─ reviewer panel      (N independent sessions or subagents)
    │     ├─ security reviewer     (read-only tools, model/prompt A)
    │     ├─ correctness reviewer  (read-only tools, model/prompt B)
    │     └─ …maintainability / tests, as configured
    │           all required verdicts must be explicit APPROVE
    │           any REJECT or invalid verdict → back to developer
    │
    ├─ test_command / CI gate
    ├─ commit on the branch; open or update PR
    └─ agents never merge
```

Three layers, plus a host:

1. **Host orchestrator.** A small TypeScript program is the PrizmForge orchestrator analogue. It should use the documented SDK (`createAgentSession`) for in-process control and/or RPC (`pi --mode rpc`, `RpcClient.promptAndWait()`) when child isolation is wanted. Print or JSON mode fits one-shot reviewer jobs. TUI-only extension UI is unavailable or degraded outside interactive mode; the design must not depend on it.
2. **Policy and OS sandbox (existing package).** Prefer pi-permission-modes in a sandboxed, non-prompting in-project mode (for example Build), or the gotgenes permission system plus a sandbox package. This extension is the proposal gate; the sandbox is the bash backstop. Double-prompting must not occur, because there is no operator to answer prompts.
3. **Custom extension (`prizmforge-pi-governance`).** Loaded in developer and reviewer sessions. In the developer session it buffers writes into proposals and denies forbidden paths. In reviewer sessions it enforces read-only tools and a strict verdict schema. It records audit entries and will not run `git merge`, `git push` to protected branches, or `gh pr merge`.

**Recommended default composition:** sandbox/policy package first, then this extension, then an orchestrator that drives [pi-subagents](https://pi.dev/packages/pi-subagents) (scout / worker / reviewer roles) where they help. [pi-advisor-flow](https://pi.dev/packages/pi-advisor-flow) may supply an extra non-mutating opinion; it is not a substitute for the required reviewer panel, and its gates stay automatic.

Project trust in non-interactive modes will not show a prompt. Unattended runs need `--approve`, a saved `/trust` decision, or an explicit `defaultProjectTrust` so project extensions load predictably. Use `--no-approve` only when project-local extensions must stay unloaded. See [Run Pi safely](https://docs.pi.dev/latest/security).

## 5. The unattended loop

Mirrors PrizmForge's sequential path, with a *panel* of reviewers instead of a single reviewer agent:

1. Orchestrator picks the next backlog item (seed tasks, then findings from security/maintenance/lint/test reviewers).
2. It creates or reuses a topic branch and a disposable worktree. The developer session's `cwd` is that worktree.
3. The developer agent works. `write` / `edit` (and mutating `bash`) are queued as a proposal, not applied to the operator's primary tree. Applying inside the worktree after a passing gate is allowed; escaping the worktree is not.
4. The orchestrator starts the configured reviewer agents **in parallel**, each a separate session or subagent, each with a different model and/or system prompt, each with write tools removed.
5. Every required reviewer must return a parseable `{ "decision": "APPROVE" | "REJECT", "reason": "...", "suggestions": [] }`. Aggregation is fail-closed: one `REJECT`, timeout, crash, empty body, or unknown decision rejects the whole proposal. There is no default quorum that can outvote a required rejecter.
6. On reject, comments are posted back to the developer session (`pi.sendMessage` / `sendUserMessage` with a documented delivery mode) and the developer revises. Cycle caps prevent infinite retry (see stall limits).
7. On agreement, run `test_command`. Non-zero exit is fail-closed (PrizmForge's `on_test_failure: discard` analogue) unless config explicitly says otherwise.
8. On test success, commit on the branch (hooks captured; hook failure becomes developer feedback, not a silent skip). Open or update a PR targeting the default branch. **Stop.** Do not merge.
9. Repeat until the duration cap, budget, empty backlog (if configured), or stall latch says to stop.

Work types in the default backlog: security findings, dependency and maintenance upkeep, lint and test failures, and small scoped features. Large or ambiguous work stays out of the unattended loop until a seed task or a human-authored issue describes it.

## 6. Custom extension design

### 6.1 `tool_call` interception

Subscribe to `tool_call` (can block). Narrow with `isToolCallEventType` from `@earendil-works/pi-coding-agent`.

- **Developer session:** intercept `write` and `edit` (official examples use `event.input.path`). Queue the intended mutation. Intercept `bash`; hard-deny escapes and writes outside the worktree or into denied paths; queue or block other mutations. Exact `write`/`edit` fields beyond `path` are **unverified** — persist the typed `event.input`.
- **Reviewer session:** `write` and `edit` always `{ block: true, reason }`. `bash` only if it can be shown read-only; otherwise block. Do not rely on `pi.setActiveTools` alone: tools with `codemode` or `deferred` exposure can remain callable after tools are hidden (documented).
- **All sessions:** hard-deny merges and default-branch promotion (`git merge`, `git pull` into protected branches, `gh pr merge`, and equivalents) even if a model tries them via `bash`.

`user_bash` (`!` / `!!`) should not appear in unattended mode. If it does, block it under the same path and merge denials.

### 6.2 Reviewer panel (the actual gate)

Reviewers are independent Pi sessions or pi-subagents, not a human dialog.

- Each reviewer gets the diff, the task, test output if any, and a strict verdict schema.
- Required reviewers are listed in config. All required agents must `APPROVE`.
- Different models or prompts are a hard recommendation; same-model rubber-stamping is a known weakness (see threat model).
- pi-subagents ships a `reviewer` role, but stock review is by convention and does not start automatically. This design *drives* those (or equivalent) sessions and *enforces* read-only tools. Per-agent permission YAML in [@gotgenes/pi-subagents](https://pi.dev/packages/@gotgenes/pi-subagents) may help; treat stock enforcement as **unverified**.
- Verdict parsing follows `workflow/reviewer_gate.py`: only an explicit, case-insensitive `APPROVE` in a parseable decision object proceeds.

Headless reviewer jobs can be `pi --print` / `--mode json` (one-shot) or RPC/SDK (long-lived). `session.prompt()` in the SDK resolves when the run finishes. In RPC, a successful `prompt` response is not completion; wait for `agent_settled` (or use `RpcClient.promptAndWait()`).

### 6.3 Commands (observability and optional override)

Unattended runs must not block on commands. Register with `pi.registerCommand`:

| Command | Default in unattended | Role |
| --- | --- | --- |
| `/status`, `/proposals` | On | Show loop state, pending proposals, last verdicts. |
| `/pause`, `/resume`, `/stop` | On | Operator control of the host loop; not a per-diff review. |
| `/approve [id]`, `/reject [id]` | **Off** (`commands.humanOverride: false`) | Optional override if an operator is watching. Not part of the default path. |

### 6.4 Hard path denies, audit, budgets, stall

Same automatic rails as the previous sketch, now without a human prompt path:

- Deny writes (and secret reads) under `.env`, `.git/`, `api_key.json`, `**/.ssh/**`, `**/.aws/**`, and any path outside the worktree or repo root.
- `pi.appendEntry("prizmforge-proposal", …)` on queue, verdict, apply, test failure, commit, PR open, and reject-to-developer. Restore on `session_start`. The host should keep a run-level log as well, because reviewer sessions may not share one session file.
- Token and duration caps from config, analogous to `resource_controller.max_tokens_per_day`, `token_budget.max_tokens_per_4h`, and `cli_mode.unattended.max_duration_hours`.
- Stall latch: only *finished, zero-change* developer turns accumulate; transport/format failures are neutral and the latch re-arms (PrizmForge Operator Principle #1 / no-progress guard). A cap on reject-revise cycles per task is required.

Undo of a materialized worktree change, if needed, is automatic snapshot restore on test/hook failure, not a human `/undo` gate. File pre-images are authoritative; `git restore --source=HEAD` may be used for tracked files that matched `HEAD`. `git stash push` alone is not sufficient on a clean tree.

### 6.5 Opening a PR, never merging

After a passing test gate and commit, the host opens or updates a pull request against the default branch. The exact implementation (`gh pr create`, a documented git/host API, or an extension tool) is an **open question**; do not invent a Pi PR API. Whatever is used, merge commands are hard-denied in `tool_call` and in the orchestrator.

## 7. Config schema (proposed)

This is **this extension's** (and orchestrator's) config, not a Pi built-in.

```json
{
  "mode": "unattended",
  "reviewer": {
    "required": [
      { "name": "security", "model": { "provider": "", "id": "" }, "prompt": "security_reviewer" },
      { "name": "correctness", "model": { "provider": "", "id": "" }, "prompt": "jr_reviewer" }
    ],
    "failClosed": true,
    "timeoutSeconds": 300
  },
  "commands": { "humanOverride": false },
  "paths": {
    "projectRoot": ".",
    "denyWrite": [".env", ".env.*", ".git/", "api_key.json", "**/.ssh/**", "**/.aws/**", "**/node_modules/**"],
    "denyRead": ["api_key.json", "**/.ssh/**", "**/.aws/**"]
  },
  "contentSafety": {
    "disallowBinaryContent": true,
    "blockedExtensions": [".exe", ".dll", ".msi"]
  },
  "loop": {
    "workTypes": ["security", "maintenance", "dependencies", "lint_tests", "small_features"],
    "testCommand": "python -m pytest tests/ -x -q",
    "onTestFailure": "discard",
    "maxDurationHours": 8,
    "maxRevisionsPerItem": 3,
    "maxTokensPerDay": 0,
    "maxTokensPer4h": 0
  },
  "git": {
    "branchPrefix": "pf/",
    "useWorktree": true,
    "openPullRequest": true,
    "allowMerge": false
  }
}
```

`mode` may be `"unattended"` (default) or `"interactive"` (optional `/approve` override enabled). `onTestFailure` is `"discard"` | `"propose_anyway"`; default `"discard"`.

## 8. Phased milestones

**MVP**

- Headless orchestrator (SDK and/or RPC) running the loop with no per-change human prompts.
- Developer session in a branch/worktree; mutations buffered as proposals.
- At least two required, independent, read-only reviewer agents; fail-closed agreement; rejects return to the developer.
- `test_command` gate; commit on the branch; open or update a PR; merge denied.
- Hard path denies, audit log, composed sandbox, duration/token/stall limits.
- Backlog covering security, maintenance/deps, lint/tests, and small features (even if prioritization is simple).

**Phase 2**

- Content-hash checks at apply time; invalidate overlapping pending proposals.
- Richer backlog prioritization (critical security first, dedupe, backpressure).
- Tightening of reviewer tool policy and CI integration (wait on a PR check, still no merge).
- Content-safety binary rejection if not already in MVP.

**Later (optional)**

- Fuller parity with PrizmForge background workers (researcher, tech writer, deployment validator) as read-only feeders.
- Worktree cleanup and run resume across orchestrator restarts.

## 9. Threat model and limits

Unattended multi-agent mutation raises the stakes. Rails are automatic; they are not a substitute for isolation or for a human merge review.

- Extensions and the SDK host run with the operator's OS permissions. Hooks are policy, not a sandbox. Compose OS sandboxing and/or a container, especially for self-edit.
- A developer `bash` that evades the parser can leave the worktree. Change sets outside the worktree must not be collected (same known limitation as PrizmForge's shell developer).
- Reviewer agents can be prompt-injected by the tree they review. Mitigations: more than one independent model or prompt, fail-closed parsing, tests/CI, and a human merge review. Do not let a developer model approve its own work.
- `setActiveTools` is insufficient against `codemode` / `deferred` tools; `tool_call` remains authoritative.
- Project trust and extension loading must be decided non-interactively (`--approve` / saved trust). A wrong trust decision can load or skip project extensions silently.
- Agents must not merge. Deny merge commands even if a reviewer panel has approved the diff.
- Session and host logs may contain diffs and secrets-adjacent paths; treat exports as sensitive.
- Budget and stall limits prevent runaway spend and infinite revise loops; they do not detect a wrong-but-well-formed approval.

## 10. Open questions

1. SDK in-process vs. RPC child processes for the developer and each reviewer — isolation vs. simplicity. A mixed approach (RPC for the developer, print/JSON for reviewers) may be enough for MVP.
2. How to open PRs portably (`gh`, SCM API, or something already in a Pi package) without inventing an API.
3. How reliably stock pi-subagents can enforce read-only tools vs. needing our `tool_call` policy (or the gotgenes fork).
4. Whether required reviewers are always unanimous, or a later config may allow optional (non-blocking) reviewers alongside required ones. MVP is unanimous among *required* reviewers.
5. How permission-modes should be configured so it never prompts in unattended runs.
6. Where config lives (`~/.pi/agent/`, project `.pi/`, or a host file next to the orchestrator).

## 11. TypeScript skeletons

APIs below are taken from the [Extensions](https://docs.pi.dev/latest/extensions), [SDK](https://docs.pi.dev/latest/sdk), and [CLI integration](https://docs.pi.dev/latest/cli-integration) docs. Anything unverified is marked.

```typescript
import {
  type ExtensionAPI,
  isToolCallEventType,
} from "@earendil-works/pi-coding-agent";

export default function (pi: ExtensionAPI) {
  const role = loadRole(); // "developer" | "reviewer" | "orchestrator-host"

  pi.on("session_start", async (_event, ctx) => {
    if (role === "reviewer") {
      const active = pi.getActiveTools().filter(
        (name) => name !== "write" && name !== "edit",
      );
      pi.setActiveTools(active);
    }
    for (const entry of ctx.sessionManager.getEntries()) {
      if (entry.type === "custom" && entry.customType === "prizmforge-proposal") {
        // Reconstruct proposal state from entry.data
      }
    }
  });

  pi.on("tool_call", async (event, ctx) => {
    if (isMergeAttempt(event)) {
      return { block: true, reason: "Agents never merge" };
    }

    if (isToolCallEventType("write", event) || isToolCallEventType("edit", event)) {
      const path = event.input.path as string; // as in official protected-paths.ts
      if (role === "reviewer" || isHardDenied(path, ctx.cwd)) {
        return { block: true, reason: `Blocked write to ${path}` };
      }
      queueProposal(event.toolName, event.input);
      pi.appendEntry("prizmforge-proposal", { path, status: "pending" });
      return { block: true, reason: "Queued for the reviewer panel" };
    }

    if (isToolCallEventType("bash", event) && role === "reviewer") {
      if (!isProvenReadOnly(event.input.command)) {
        return { block: true, reason: "Reviewers cannot run mutating bash" };
      }
    }
    return undefined;
  });

  pi.registerCommand("status", {
    description: "Show unattended loop and proposal status",
    handler: async (_args, ctx) => {
      ctx.ui.notify(formatStatus(), "info");
    },
  });
}
```

Host orchestrator sketch (SDK is documented; wiring of N reviewers is this design's):

```typescript
import { createAgentSession } from "@earendil-works/pi-coding-agent";

// In-process host. For a process boundary, use RpcClient and
// `pi --mode rpc` instead; wait for agent_settled, not the prompt ack.
const { session: developer } = await createAgentSession({ cwd: worktreePath });
try {
  await developer.prompt(taskPrompt);
  const verdicts = await runReviewerPanel(proposal); // each reviewer fail-closed
  if (!allRequiredApproved(verdicts)) {
    await developer.prompt(`Revise; reviewers rejected:\n${format(verdicts)}`);
    return;
  }
  // Host runs test_command, then git commit on the branch.
  // UNVERIFIED: exact host API for opening a PR. Do not merge.
} finally {
  developer.dispose();
}
```

Second-model reviewer via the registry (method names documented; argument shape is not fully shown):

```typescript
const model = ctx.modelRegistry.find(provider, id);
if (!model) return { decision: "REJECT", reason: "Reviewer model not found" };
// UNVERIFIED: exact `context` / `options` types for complete().
const message = await ctx.modelRegistry.complete(model, /* context */ prompt, {});
return parseApproveOrReject(message); // anything but explicit APPROVE → REJECT
```

`parseApproveOrReject`, `runReviewerPanel`, and path helpers are this design's, not Pi APIs. Prefer separate reviewer *sessions* over a single in-process `complete()` call so tool policy and prompts stay isolated; `complete()` is a fallback for a narrow verdict, not the panel itself.

## 12. References

- Pi Extensions: <https://docs.pi.dev/latest/extensions>
- Run Pi safely: <https://docs.pi.dev/latest/security>
- CLI integration (print, JSON, RPC): <https://docs.pi.dev/latest/cli-integration>
- RPC mode: <https://docs.pi.dev/latest/rpc>
- SDK: <https://docs.pi.dev/latest/sdk>
- Official examples: <https://github.com/badlogic/pi-mono/tree/main/packages/coding-agent/examples/extensions>
- pi-permission-modes: <https://pi.dev/packages/pi-permission-modes>
- @gotgenes/pi-permission-system: <https://pi.dev/packages/@gotgenes/pi-permission-system>
- pi-subagents: <https://pi.dev/packages/pi-subagents>
- pi-advisor-flow: <https://pi.dev/packages/pi-advisor-flow>
- PrizmForge unattended loop and gate: [docs/UNATTENDED_CLOSED_LOOP_CAPABILITIES.md](../UNATTENDED_CLOSED_LOOP_CAPABILITIES.md), [docs/architecture.md](../architecture.md), `workflow/reviewer_gate.py`, `agents/orchestrator.py`, `workflow/task_runner.py`
