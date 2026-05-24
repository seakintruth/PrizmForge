# System Mental Model Progression Plans

**Purpose**  
This document defines the evolution path of PrizmForge from its current state toward a more capable governed system. It separates the active codebase from the longer-term vision and provides clear criteria for progressing between stages.

**Important Distinction**
- The main `PrizmForge/` directory contains the working codebase.
- The `federation/` directory contains **only documentation** of the future vision.

---

## Current State: Stage 0 – Legacy PrizmForge

**Mental Model**: Single-threaded governed editor with parallel observers and explicit flow control.

### Key Characteristics
- A single `Developer` agent performs all code mutations (primary bottleneck).
- Background agents generate a high volume of ideas (\~100:1 idea-to-adoption ratio).
- The **Resource Controller** throttles new idea generation once the idea stack reaches \~100–200 items.
- The **Prioritizer + Archivist** consolidate and manage the idea queue.
- All changes go through a strict serial pipeline with strong safety (line GUIDs, optimistic concurrency, content hashing, and reviewer gate).

### Primary Problems
This stage has two distinct issues:

1. **Filtering Problem**: Too many low-value or low-priority ideas reach the implementation stage.
2. **Throughput Problem**: Even good ideas move slowly because implementation is serialized through one Developer agent.

**Status**: Active development. This is where work will remain for the next several sprints.

---

## Stage 1 – Enhanced PrizmForge (Next Target)

**Mental Model**: Strengthened single-Territory system with better filtering and controlled parallelism.

### Goals
- Improve the idea adoption ratio by strengthening filtering and prioritization.
- Increase implementation throughput without breaking safety guarantees.
- Introduce lightweight governance mechanisms.
- Create a stable foundation before considering multiple Territories.

### Planned Improvements

| Area                    | Approach                                      | Notes |
|-------------------------|-----------------------------------------------|-------|
| **Filtering**           | Enhance Prioritizer + early discrimination    | Focus on reducing low-value ideas upstream |
| **Implementation**      | Introduce basic work partitioning             | Allow non-overlapping changes to proceed with minimal conflict risk |
| **Governance**          | Add lightweight moot-style mechanisms         | Used for prioritization decisions and conflict resolution |
| **Quality**             | Incremental multi-stage evaluation            | Build on existing reviewer patterns |

### Stage 1 Success Metrics
- Improve idea adoption ratio (target: move meaningfully below 100:1)
- Increase number of implemented changes per sprint
- Maintain or improve safety metrics (zero governance-related rollbacks)
- Reduce average time from idea generation to implementation decision

### Key Risks & Assumptions
- **Risk**: Work partitioning may introduce subtle race conditions or increase proposal rejection rate.
- **Risk**: "Lightweight governance" could become heavier than intended.
- **Assumption**: The biggest limiter is currently implementation capacity rather than idea quality.

**Status**: Target for the next several sprints. All changes remain in the main `PrizmForge/` codebase.

---

## Stage 2 – Forge Federation (Longer-Term Vision)

**Mental Model**: Stewardship-oriented Constitutional Polycentric Republic.

### Core Concepts
- **Stewardship Governance Layer**: Explicit constitutional rules and moots for system-level decisions.
- **Spider Web Discrimination Layer**: Robust, multi-stage quality filtering and selective response.
- **Multiple Territories**: Semi-sovereign mental models that can specialize and interact.
- Strong emphasis on **YAGNI** — complexity is only added when it delivers clear value.

**Status**: Documentation only. All planning and exploration for this stage lives in the `federation/` directory.

---

## Development Principles

- **YAGNI First**: Only add mechanisms when there is evidence they are needed.
- **Protect Safety**: The governed editing model (line GUIDs, optimistic concurrency, reviewer gates) remains non-negotiable.
- **Measure Outcomes**: Success is judged by code quality and implementation throughput, not architectural complexity.
- **Start Narrow**: Begin with one Territory. Expand only when justified by results.

---

## Where Things Live

| Item                              | Location                  | Purpose |
|-----------------------------------|---------------------------|--------|
| Active PrizmForge codebase        | `PrizmForge/`             | Current working system |
| Stage 1 improvements              | `PrizmForge/`             | Pragmatic enhancements |
| Federation vision & planning      | `federation/`             | Future architecture documentation only |
| Key Components                    | `core/`, `agents/`, etc.  | Resource Controller, Prioritizer, Governed Editing Pipeline |

---

## Stage Transition Criteria

**Move from Stage 0 to Stage 1 when:**
- The Resource Controller and Prioritizer are effectively managing idea flow.
- We have a workable approach for safe work partitioning.
- We can demonstrate improved idea adoption or implementation velocity.

**Move from Stage 1 to Stage 2 when:**
- Stage 1 improvements have delivered clear gains in throughput or quality.
- There is evidence that a single Territory is becoming a constraint.
- The cost of adding and coordinating additional Territories is justified.

---

## Summary

| Stage | Name                    | Territories | Primary Focus                     | Risk Level | Location          |
|-------|-------------------------|-------------|-----------------------------------|------------|-------------------|
| 0     | Legacy PrizmForge       | 1           | Safe governed editing             | Low        | Main codebase     |
| 1     | Enhanced PrizmForge     | 1           | Throughput + filtering            | Medium     | Main codebase     |
| 2     | Forge Federation        | 1 → Many    | Multi-paradigm governed evolution | Higher     | `federation/` (docs) |

This document will be updated as we progress and learn.
