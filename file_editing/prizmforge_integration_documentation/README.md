# PrizmForge Integration Layer

This directory contains the bridge between the core **governed file editing system** 
(`file_editing/`) and the main PrizmForge multi-agent architecture.

## Components

- `helpers/proposal_builder.py` — Converts Developer agent output into structured `EditPayload` proposals.
- `prompts/` — Prompt updates for Developer and Reviewer agents to support the governed editing path.

## Philosophy

We follow the **governed path only**:
1. Developer produces structured output → `EditPayload`
2. `create_proposal_from_developer_output()` creates a proposal
3. Reviewer reviews the proposal
4. On approval → `FileWriterAgent` materializes to disk + git

This replaces raw diff patching with auditable, reviewer-gated edits.