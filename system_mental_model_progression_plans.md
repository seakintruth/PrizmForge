# System Mental Model Progression Plans

**Purpose**  
This document defines the high-level mental model and evolution path for PrizmForge. It distinguishes between the working codebase and the longer-term architectural vision.

**Important Distinction**
- The main **PrizmForge** directory contains the active, production codebase.
- The **`federation/`** directory contains **only documentation** describing the future vision. No implementation code for the full Federation model currently lives in the main codebase.

We expect to remain on **Stage 0** for the next several sprints while making targeted, high-value improvements.

---

## Current Stage: Stage 0 – Legacy PrizmForge

**Mental Model**: Single-threaded governed editor with parallel observers and explicit flow control.

### Characteristics
- One `Developer` agent performs all code mutations (primary bottleneck).
- Background agents (Class 2 and Class 3) generate ideas and feedback in parallel.
- **Explicit governance** exists through Layer 2 agents, particularly the **Resource Controller** and **Prioritizer**.
- The **Resource Manager** actively throttles idea generation when the idea stack reaches capacity (approximately 100–200 ideas), preventing uncontrolled growth.
- The **Prioritizer + Archivist** work together to consolidate, rank, and archive ideas, providing structured flow control.
- All changes still flow through a strict, serial pipeline with strong safety guarantees (line GUIDs, optimistic concurrency, content hashing, and reviewer gate).
- Despite governance mechanisms, idea adoption remains low relative to generation volume (\~100:1 ratio).

### Current Strengths
- Strong safety and auditability through the governed editing pipeline.
- Explicit resource and idea flow management via the Resource Controller and Prioritizer.
- Clear separation between proposal creation and materialization.
- Some consolidation and archival of ideas through the Archivist.

### Current Weaknesses
- Implementation remains serialized through a single Developer agent.
- Even with throttling and prioritization, the volume of ideas significantly outpaces the rate of adoption and implementation.
- Governance and prioritization are focused more on controlling input volume than on increasing safe implementation throughput.
- Limited ability to safely parallelize code changes across multiple developers or agents.

**Status**: Active codebase. This is where all near-term development will occur.

---

## Stage 1 – Enhanced PrizmForge (Next Target)

**Mental Model**: Enhanced single-Territory governed system with improved filtering and light parallelism.

### Goals
- Reduce the implementation bottleneck without compromising safety.
- Improve the ratio of ideas that get adopted.
- Add lightweight governance and quality mechanisms.
- Create a stable base that can later support additional Territories.

### Planned Improvements
- Explicitly treat the current system as **one Territory**.
- Strengthen upstream filtering and prioritization (building on the existing Prioritizer and Resource Controller).
- Introduce basic work partitioning so the Developer can safely handle non-overlapping changes.
- Add lightweight governance capabilities (simple moot-style or review mechanisms for higher-level decisions).
- Improve quality evaluation incrementally (multi-stage evaluation without over-engineering).
- Maintain the existing governed editing pipeline as the foundation.

### Constraints for Stage 1
- Stay within the existing PrizmForge codebase.
- Apply **YAGNI** strictly — only add what is necessary to improve throughput and quality.
- Do **not** build full multi-Territory support yet.
- Focus on measurable improvements to code change velocity and reliability.

**Status**: Planning / Early implementation. This is the focus for the next several sprints.

---

## Stage 2 – Forge Federation (Longer-Term Vision)

**Mental Model**: Stewardship-oriented Constitutional Polycentric Republic.

### Core Concepts
- **Stewardship Governance Layer** (top layer): Provides long-term values and constitutional constraints. Uses moots for rule changes.
- **Spider Web Discrimination Layer** (cross-cutting): Stronger, multi-stage quality filtering, critique, and selective response.
- **Multiple Territories**: Different mental models operating as semi-sovereign ecosystems that can propose, critique, and implement changes.
- **Federated Coordination**: Structured interaction between Territories rather than pure emergence.
- Strong application of **YAGNI** — additional complexity is only added when clearly justified by results.

### Key Differences from Stage 0/1
- Multiple mental models can contribute to code changes.
- Governance is explicit and constitutional.
- Better balance between idea generation and disciplined implementation.
- Designed for long-term evolution rather than short-term safety alone.

**Status**: Documentation only.

All exploration and documentation for Stage 2 lives in the **`federation/`** directory. No implementation of the full Federation model will be added to the main PrizmForge codebase until Stage 1 is stable and the value of expansion is proven.

---

## Development Philosophy

- **Start Simple**: Begin with one Territory and only expand when there is clear evidence of benefit.
- **YAGNI First**: Avoid speculative complexity. Every new mechanism must justify itself.
- **Protect the Core**: The governed editing safety model (line GUIDs, proposals, optimistic concurrency) remains foundational.
- **Measure Real Outcomes**: Success is defined by improvements in code quality and implementation throughput, not by architectural sophistication or number of agents.
- **Separate Concerns**: The working codebase (Stage 0 → Stage 1) and the future vision (Stage 2) are intentionally separated.

---

## Where Things Live

| Component                        | Location                  | Notes |
|----------------------------------|---------------------------|-------|
| Current PrizmForge codebase      | Root of `PrizmForge/`     | Active development (Stage 0 → Stage 1) |
| Stage 1 improvements             | Root of `PrizmForge/`     | Pragmatic enhancements to existing system |
| Federation vision & documentation| `federation/` directory   | Documentation and planning only |
| Full multi-Territory implementation | Not yet started        | Will only be introduced after Stage 1 proves value |

---

## Current Sprint Focus

For the next several sprints, the team will remain focused on **Stage 0 → Stage 1** improvements inside the main PrizmForge codebase. This includes:

- Building on the existing Resource Controller and Prioritizer to further improve idea quality and flow.
- Introducing light work partitioning to reduce the single Developer bottleneck.
- Adding lightweight governance and enhanced quality mechanisms.
- Maintaining strong safety while increasing implementation throughput.

Expansion into multiple Territories and the full Federation model is intentionally deferred.

---

## Summary

| Stage | Name                    | # of Territories | Focus                              | Location of Work      | Expected Duration |
|-------|-------------------------|------------------|------------------------------------|-----------------------|-------------------|
| 0     | Legacy PrizmForge       | 1 (implicit)     | Safe single-threaded editing with explicit flow control | Main codebase     | Current           |
| 1     | Enhanced PrizmForge     | 1 (explicit)     | Throughput + quality improvements  | Main codebase         | Next several sprints |
| 2     | Forge Federation        | 1 → Many         | Multi-paradigm governed improvement| `federation/` (docs)  | Future            |

This progression keeps the project grounded, reduces risk of over-engineering, and provides a clear path from the current working system toward the longer-term vision.
