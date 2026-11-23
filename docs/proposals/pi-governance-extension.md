# prizmforge-pi-governance

**Status:** design sketch (not implemented)
**Date:** 2026-11-22
**Proposed package name:** `prizmforge-pi-governance`

A TypeScript [Pi](https://docs.pi.dev/latest/extensions) extension that overlays PrizmForge's governed-mutation intent onto the Pi coding agent: collect writes as proposals, require a fail-closed verdict, then materialize, log, and undo. It is a governance overlay, not a port of the PrizmForge runtime.

## 1. Goal

Give a Pi session a hard gate in front of repository mutation that is recognizably PrizmForge:

- The model may explore freely (reads, and non-mutating inspection).
- Intended file changes are captured as a **proposal**, not applied immediately.
- A **human or second-model verdict** must explicitly `APPROVE` before materialization.
- Missing, unparseable, or unavailable verdicts **REJECT** (fail closed), including when there is no UI.
- Sensitive paths (`.env`, `.git`, secrets, and similar) are hard-denied.
- Every proposal lifecycle event is written to an append-only session audit log.
- An approved, applied proposal can be undone from a pre-apply snapshot (file bytes, with optional git restore).

## 2. Non-goals

This extension will **not**:

- Reimplement PrizmForge's multi-agent orchestrator, background worker pool, resource controller, token budgets, or unattended closed-loop scheduler.
- Reproduce the line-GUID `file_lines` database, structured `EditPayload` schema, or `agents.db`.
- Provide OS isolation by itself. Hooks are policy. Real sandboxing is composed from an existing Pi package or a container/VM.
- Replace Pi, or require operators to abandon Pi's built-in tools for all work.
- Automatically start a fleet of analysis subagents (compose [pi-subagents](https://pi.dev/packages/pi-subagents) later if wanted).

## 3. Mapping PrizmForge controls to Pi hooks

| PrizmForge control | Pi mechanism | Fit |
| --- | --- | --- |
| Reviewer safety gate before disk writes | `pi.on("tool_call")` returns `{ block: true, reason }` until `/approve`; `ctx.ui.confirm` / `ctx.ui.select` for humans; `ctx.modelRegistry.complete` / `streamSimple` for a second model | Feasible |
| Fail closed on empty or unparseable reviewer output | Same policy as `workflow/reviewer_gate.py`: only an explicit `APPROVE` applies; everything else rejects. No UI → block | Feasible |
| Path containment under repo root | Resolve `event.input.path` against `ctx.cwd` (and a configured root); block escapes | Feasible |
| Hard-deny secrets / caches (`.env`, `.git`, `api_key.json`, …) | `tool_call` deny list on `write` / `edit` / `read`, plus bash-path checks where practical | Feasible |
| Binary / installer rejection | Inspect proposed bytes on write/edit before queueing | Feasible (MVP or shortly after) |
| Mutation audit log | `pi.appendEntry("prizmforge-proposal", data)` (custom entries are not sent to the LLM) | Feasible |
| Proposal undo / pre-apply snapshot | File pre-images always; optional `pi.exec("git", ["restore", …])` for tracked files | Partial |
| Optimistic concurrency (content hashes) and overlapping-proposal invalidation | Hash at queue time; re-check at apply; mark siblings stale | Phase 2 |
| Background agents with no write rights | Out of scope; optional later via subagents with write tools deactivated (`pi.setActiveTools`) | Partial, later |
| Disposable git worktree developer sessions | Out of scope for MVP | Not in MVP |
| Hooks as an OS sandbox | Not possible. Extensions run in-process with Pi's permissions ([Run Pi safely](https://docs.pi.dev/latest/security)) | Not feasible alone |

## 4. Architecture

Compose three layers rather than writing a new permission engine:

1. **Policy and OS sandbox (existing package).** Prefer [pi-permission-modes](https://pi.dev/packages/pi-permission-modes): allow/ask/deny, protected paths, and an OS sandbox for in-project `bash` (`bubblewrap` / `sandbox-exec` / Windows sandbox-runtime). Alternatively compose [@gotgenes/pi-permission-system](https://pi.dev/packages/@gotgenes/pi-permission-system) with a sandbox package such as [pi-sandbox](https://pi.dev/packages/pi-sandbox).
2. **Custom extension (`prizmforge-pi-governance`).** Owns the proposal buffer, verdict, commands, audit log, and undo.
3. **Host isolation (operator).** For enclave or self-edit work, still run Pi in a container/VM as Pi's own security docs recommend. The extension does not replace that.

**Recommended default composition:** run permission-modes in a sandboxed mode that does **not** prompt on every in-project `write`/`edit` (for example Build), so this extension is the only write gate. Keep permission-modes hard-denies for `.git` / `.env` / privilege escalation, and keep in-project `bash` OS-sandboxed. Double-prompting is an integration risk; see Open questions.

Handler order is extension load order. `tool_call` handlers can block; earlier handlers' mutations to `event.input` are visible to later ones. Load the sandbox/policy package first, then this extension.

## 5. Custom extension design

### 5.1 `tool_call` interception

Subscribe to `tool_call` (fires after `tool_execution_start`, before the tool runs; **can block**). Narrow with `isToolCallEventType` from `@earendil-works/pi-coding-agent`.

Documented built-in tools to handle:

- `write` and `edit` — always intercept. Official `protected-paths.ts` reads `event.input.path`. Queue the intended mutation and `return { block: true, reason }` so the built-in tool does not write.
- `bash` — inspect `event.input.command`. Hard-deny obvious escapes and writes into denied paths when they can be parsed. Mutating commands that cannot be proven read-only should be blocked or queued as a proposal, not executed. Command parsing will be imperfect; the OS sandbox layer is the backstop.
- `read` — do not queue; optionally hard-deny reads of secret paths so contents never enter the prompt.

`user_bash` (`!` / `!!`) is a separate event and is **not** gated by default: it is the operator's own shell. This is a documented gap (the same choice `pi-agent-modes` makes). An optional config flag may warn or block later.

**Known limit (documented by Pi):** `pi.setActiveTools()` does not stop tools with `codemode` or `deferred` exposure from being called from codemode scripts. Do not treat "hide `write`/`edit`" as sufficient. Interception on `tool_call` remains the authority.

### 5.2 Write buffer (proposal)

A proposal is an in-memory record, also persisted with `pi.appendEntry` so it survives `/reload` and session restart:

- `id`, `status` (`pending` / `approved` / `rejected` / `applied` / `undone` / `conflicted` / `needs_revalidation`)
- target paths, a stored snapshot of the intended tool name + input, and a pre-image of the files if they exist
- timestamps and the verdict (`human` or `model`, reason text)

MVP stores whatever `event.input` contained. Exact `write`/`edit` field names beyond `path` are **unverified** in the public examples (only `path` is shown). Implementation should narrow with `isToolCallEventType` and persist the typed input, not assume a `contents` field name.

On `/approve`, the extension materializes the stored change itself (path-checked file writes). There is no documented Pi API to "replay" a blocked tool call; do not invent one. Use `withFileMutationQueue()` when applying from a tool path so applies participate in Pi's per-file queue. Whether that helper is valid inside a **command** handler is **unverified** — if it is not, apply through a small internal helper and note the race with concurrent built-in edits.

### 5.3 Verdict (human or second model), fail closed

Config selects `human`, `model`, or `human_then_model`.

- **Human:** `ctx.ui.select` or `ctx.ui.confirm`. If `!ctx.hasUI`, block and reject. Official `permission-gate.ts` already fail-closes without a UI.
- **Model:** resolve a reviewer with `ctx.modelRegistry.find(provider, id)` and call `ctx.modelRegistry.complete(model, context, options)` or `streamSimple(...)`. The exact `context` argument shape is **unverified** (the docs name the methods but do not show a full call). Prompt the reviewer for strict JSON `{ "decision": "APPROVE" | "REJECT", "reason": "..." }`. Only a parseable, explicit `APPROVE` applies. Empty, non-JSON, unknown, or failed calls `REJECT`, matching `workflow/reviewer_gate.py`.
- Same-model reviews should be configurable (default: allowed, but warn). `ctx.signal` should be passed when the call happens during a turn.

### 5.4 Hard path denies

Always deny, with no prompt, writes (and optionally reads) whose resolved path is outside the project root or matches a deny list. Defaults:

- `.env`, `.env.*`
- `.git/`
- `api_key.json`, `**/.ssh/**`, `**/.aws/**`
- `**/node_modules/**` (write deny; read may stay allowed)

Resolve against `ctx.cwd`, follow the path as far as is practical, and compare the real path to the repo root. Symlink escape is a residual risk; the OS sandbox and running Pi in a container are the real boundary.

### 5.5 Commands

Register with `pi.registerCommand` (documented):

| Command | Behavior |
| --- | --- |
| `/proposals` | List pending and recent proposals (id, paths, status). |
| `/approve [id]` | Fail-closed verdict already obtained or implied by the operator; snapshot; materialize; append audit entry. Default to the latest pending id. |
| `/reject [id]` | Mark rejected, feed the reason back (notify, and optionally `pi.sendMessage` so the model can adapt). |
| `/undo [id]` | Restore the pre-apply git stash or file snapshot for an applied proposal. |

### 5.6 Audit log

`pi.appendEntry("prizmforge-proposal", { ... })` on create, approve, reject, apply, apply-failure, and undo. Custom entries do not enter LLM context. Restore state in `session_start` by walking `ctx.sessionManager.getEntries()`.

### 5.7 Undo

On approve, **before** materialize, always copy pre-images of the target paths into a session-private snapshot (create vs. modify vs. delete recorded). That snapshot is the authoritative undo source. `git stash push` alone is **not** sufficient: on a clean tree it no-ops or errors and would not capture committed file state.

When `undo.strategy` is `git_restore` and `cwd` is a git work tree, also record whether each path matched `HEAD`. Undo then prefers `pi.exec("git", ["restore", "--source=HEAD", "--", ...paths], { cwd })` for those tracked files, and otherwise writes the file snapshot back. `pi.exec` runs **without a shell** (documented). If git is missing or the path was untracked, use the file snapshot.

Undo requires an explicit proposal id (same rule as PrizmForge's `undo_proposal`).

## 6. Config schema (proposed)

This is **this extension's** config, not a Pi built-in. Delivery vehicle (settings file vs. package config) is an open question.

```json
{
  "reviewer": {
    "mode": "human",
    "model": { "provider": "", "id": "" },
    "failClosedWithoutUi": true
  },
  "paths": {
    "projectRoot": ".",
    "denyWrite": [".env", ".env.*", ".git/", "api_key.json", "**/.ssh/**", "**/.aws/**", "**/node_modules/**"],
    "denyRead": ["api_key.json", "**/.ssh/**", "**/.aws/**"]
  },
  "contentSafety": {
    "disallowBinaryContent": true,
    "blockedExtensions": [".exe", ".dll", ".msi"]
  },
  "buffer": {
    "interceptWriteEdit": true,
    "queueMutatingBash": true
  },
  "undo": { "strategy": "git_restore" },
  "gateUserBash": false
}
```

`reviewer.mode` is `"human"` | `"model"` | `"human_then_model"`. `undo.strategy` is `"git_restore"` (file snapshot plus `git restore` when paths matched HEAD) or `"file_snapshot"`.

## 7. Phased milestones

**MVP**

- `tool_call` interception for `write` / `edit` (always) and mutating `bash` (best effort).
- Proposal buffer + `/proposals`, `/approve`, `/reject`, `/undo`.
- Human or second-model verdict; no UI or bad verdict → reject.
- Hard path denies as above.
- `appendEntry` audit + restore on `session_start`.
- Undo from pre-apply file snapshots, with optional `git restore` for tracked files.
- Compose with pi-permission-modes (or gotgenes + sandbox); document the recommended mode.

**Phase 2**

- Content-hash (or equivalent digest) captured when the proposal is queued; re-check immediately before apply; mark `conflicted` on mismatch.
- Invalidate or flag `needs_revalidation` for other pending proposals that touch the same paths.
- Content-safety binary rejection on proposed payloads (if not already in MVP).

**Later (optional)**

- Git worktree isolation for a developer-style session.
- Optional read-only reviewer subagent.
- Tighter bash parsing, or refusing unsandboxed bash entirely.

## 8. Threat model and limits

Treat model-generated tool calls as untrusted. This extension reduces accidental or prompt-injected writes to a repo; it does **not** create a security boundary.

- The extension runs **inside the Pi process** with the operator's OS permissions. A buggy or malicious extension, or any unsandboxed child, can bypass hooks.
- `tool_call` hooks do not constrain unsandboxed `bash` that evades the parser (wrappers, `bash -c`, unexpected tools). Compose an OS sandbox and/or run Pi in a container.
- `user_bash` is ungated by default.
- `codemode` / `deferred` tools may remain callable after `setActiveTools` hides `write`/`edit`.
- File tools themselves are not OS-sandboxed by permission-modes (only the model's `bash` tool is); policy hooks plus this buffer are what govern `write`/`edit`.
- A second-model reviewer can be prompt-injected by the same untrusted tree it is asked to judge. Prefer a human verdict for high-risk or self-edit work, and review a copy of the repo rather than `main`.
- Audit logs in the session file may contain paths, snippets, and reasons; treat session export as sensitive.

## 9. Open questions

1. How should permission-modes (or the gotgenes gate) be configured so this extension owns write approval without double prompts?
2. Should mutating `bash` be queued as a proposal, or simply denied until the operator uses `/approve` on file proposals only?
3. What is the exact `write`/`edit` input schema, and the exact `modelRegistry.complete(model, context, options)` `context` shape, in the Pi version we target?
4. Is `withFileMutationQueue()` safe to call from a slash-command handler?
5. Where does extension config live (`~/.pi/agent/`, project `.pi/`, or package settings)?
6. Should `/reject` inject a steer message into the session (`pi.sendMessage`) by default?

## 10. TypeScript skeletons

APIs below are taken from the [Pi Extensions](https://docs.pi.dev/latest/extensions) docs and official examples. Anything unverified is marked.

```typescript
import {
  type ExtensionAPI,
  isToolCallEventType,
} from "@earendil-works/pi-coding-agent";

export default function (pi: ExtensionAPI) {
  pi.on("session_start", async (_event, ctx) => {
    for (const entry of ctx.sessionManager.getEntries()) {
      if (entry.type === "custom" && entry.customType === "prizmforge-proposal") {
        // Reconstruct the in-memory proposal list from entry.data
      }
    }
  });

  pi.on("tool_call", async (event, ctx) => {
    if (isToolCallEventType("write", event) || isToolCallEventType("edit", event)) {
      // event.input.path is used this way in official protected-paths.ts
      const path = event.input.path as string;
      if (isHardDenied(path, ctx.cwd)) {
        return { block: true, reason: `Path "${path}" is protected` };
      }
      queueProposal(event.toolName, event.input);
      pi.appendEntry("prizmforge-proposal", { path, status: "pending" });
      if (!ctx.hasUI) {
        return {
          block: true,
          reason: "No UI for approval; failing closed",
        };
      }
      return { block: true, reason: "Queued as a proposal; use /proposals" };
    }

    if (isToolCallEventType("bash", event)) {
      const command = event.input.command; // typed as { command: string; timeout?: number }
      if (looksLikeDeniedPathWrite(command)) {
        return { block: true, reason: "bash would touch a protected path" };
      }
    }
    return undefined;
  });

  pi.registerCommand("proposals", {
    description: "List governed file-change proposals",
    handler: async (_args, ctx) => {
      ctx.ui.notify(formatProposalList(), "info");
    },
  });

  pi.registerCommand("approve", {
    description: "Approve and materialize a pending proposal",
    handler: async (args, ctx) => {
      const id = (args || "").trim() || latestPendingId();
      // Always snapshot pre-images first, then materialize.
      // No documented "replay tool call" API — write the stored bytes yourself.
      await snapshotPreImages(id, ctx.cwd);
      await materializeProposal(id, ctx.cwd);
      // Optional git-backed undo for tracked files that matched HEAD:
      // await pi.exec("git", ["restore", "--source=HEAD", "--", ...paths], { cwd: ctx.cwd });
      pi.appendEntry("prizmforge-proposal", { id, status: "applied" });
    },
  });

  pi.registerCommand("reject", {
    description: "Reject a pending proposal",
    handler: async (args, ctx) => {
      ctx.ui.notify(`Rejected ${args || "latest"}`, "info");
    },
  });

  pi.registerCommand("undo", {
    description: "Restore the pre-apply snapshot for a proposal",
    handler: async (args, ctx) => {
      ctx.ui.notify(`Undo ${args || ""}`.trim(), "info");
    },
  });
}

// Second-model verdict — method names are documented; argument shape is not fully shown.
async function modelVerdict(
  ctx: { modelRegistry: { find: Function; complete: Function } },
  provider: string,
  id: string,
  prompt: string,
) {
  const model = ctx.modelRegistry.find(provider, id);
  if (!model) return { decision: "REJECT", reason: "Reviewer model not found" };
  // UNVERIFIED: exact `context` / `options` types for complete().
  const message = await ctx.modelRegistry.complete(model, /* context */ prompt, {});
  return parseApproveOrReject(message); // anything other than explicit APPROVE → REJECT
}
```

`parseApproveOrReject` and helpers such as `isHardDenied` are this design's, not Pi APIs.

## 11. References

- Pi Extensions: <https://docs.pi.dev/latest/extensions>
- Run Pi safely: <https://docs.pi.dev/latest/security>
- Upstream extensions doc: <https://github.com/badlogic/pi-mono/blob/main/packages/coding-agent/docs/extensions.md>
- Official examples (`permission-gate.ts`, `protected-paths.ts`): <https://github.com/badlogic/pi-mono/tree/main/packages/coding-agent/examples/extensions>
- pi-permission-modes: <https://pi.dev/packages/pi-permission-modes>
- @gotgenes/pi-permission-system: <https://pi.dev/packages/@gotgenes/pi-permission-system>
- pi-sandbox: <https://pi.dev/packages/pi-sandbox>
- pi-advisor-flow (optional later reviewer): <https://pi.dev/packages/pi-advisor-flow>
- pi-subagents (optional later): <https://pi.dev/packages/pi-subagents>
- PrizmForge governed editing and reviewer gate: [README.md](../../README.md), [docs/architecture.md](../architecture.md), `workflow/reviewer_gate.py`
