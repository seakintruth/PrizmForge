# PrizmForge Integration Layer

Bridge notes between the governed file editing system (`file_editing/`) and
the main PrizmForge multi-agent architecture. Prompt text here is historical
guidance; live prompts live in `agent_prompts.json`.

## Components

- `workflow/proposal_builder.py` — Converts Developer agent output into
  structured `EditPayload` proposals (`create_proposal_from_developer_output`).
- `file_editing/writer.py` — Materializes approved proposals to disk + git
  (`materialize_proposal`). There is no separate `FileWriterAgent` class.
- `prompts/` — Historical prompt-update notes for Developer and Reviewer.
  Authoritative prompts are `agent_prompts.json`.

## Philosophy

We follow the **governed path only**:
1. Developer produces structured output → `EditPayload`
2. `create_proposal_from_developer_output()` creates a proposal
3. Reviewer reviews the proposal
4. On approval → `materialize_proposal()` writes to disk + git

This replaces raw diff patching with auditable, reviewer-gated edits.
