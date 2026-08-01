# Flexible Plan — Forge Federation

**Working Name:** Forge Federation  
**Framing:** A Stewardship-oriented Constitutional Polycentric Republic for multi-paradigm, governed code improvement.

## Overview

Forge Federation builds on the existing PrizmForge foundation. Rather than immediately building a multi-Territory system, we will first enhance the current PrizmForge codebase with better governance and quality mechanisms while treating it as **a single Territory**.

The longer-term vision is to support multiple semi-sovereign mental model ecosystems (Territories) coordinated through a **Stewardship Governance layer** and a **Spider Web discrimination layer**. However, we will only expand beyond a single Territory when there is clear evidence that doing so improves outcomes.

Development will follow a flexible, sprint-based approach with a strong emphasis on **YAGNI** (You Aren't Gonna Need It) to avoid over-engineering.

## Development Philosophy

- Work in short, focused sprints.
- Prioritize **working, demonstrable improvements** to the existing system over architectural ambition.
- Apply **YAGNI** aggressively — only add complexity when it is clearly justified by results.
- Protect against “Tamagotchi” development by keeping experimentation contained and measurable.
- Use the **commercial LLM API** primarily for high-value reasoning and evaluation.
- Use local hardware for volume, persistence, and lower-stakes work.
- Reassess scope and direction after each sprint.

## Architecture Alignment

We are following a staged evolution:

- **Stage 0 (Current)**: Legacy PrizmForge with a single implicit Territory and explicit flow control via the Resource Controller and Prioritizer.
- **Stage 1 (Next)**: Enhanced single-Territory system with improved filtering, light work partitioning, and basic governance.
- **Stage 2 (Future)**: Full Forge Federation with multiple Territories using a hybrid **Core Philosophy + Role** model.

Early work will focus on strengthening the existing system rather than building out multiple Territories.

## Sprint Guidelines

- Define one clear, narrow outcome per sprint.
- Explicitly state what is in scope and out of scope.
- Prefer small, shippable improvements over large redesigns.
- Document decisions and learnings at the end of each sprint.
- Adjust scope between sprints based on what was learned.

## Phased Direction (Flexible)

### Phase 1: Enhance Existing PrizmForge (Next Several Sprints)
**Goal:** Improve throughput and quality on the current system while maintaining strong safety.

**Focus:**
- Strengthen upstream filtering and prioritization (building on the existing Resource Controller and Prioritizer).
- Introduce basic work partitioning to reduce the single Developer bottleneck.
- Add lightweight governance mechanisms (e.g., simple moot-style processes for prioritization and conflict resolution).
- Improve evaluation and discrimination capabilities incrementally.
- Maintain the existing governed editing pipeline.

**Success Criteria:**
- Measurable improvement in idea quality reaching implementation.
- Reduced friction in the implementation path through better partitioning or filtering.
- Introduction of lightweight governance without excessive complexity.

### Phase 2: Evaluate Expansion (When Ready)
**Goal:** Determine whether moving beyond a single Territory provides meaningful value.

**Focus:**
- Compare outcomes between the enhanced single-Territory system and limited multi-Territory experiments.
- Refine the Spider Web discrimination layer.
- Assess governance needs as complexity increases.

**Success Criteria:**
- Clear data on whether additional Territories improve code improvement outcomes enough to justify added complexity.

### Phase 3: Broader Federation Capabilities (Future)
**Goal:** Move toward the full Forge Federation vision if justified.

This phase will only be pursued after Phase 1 and Phase 2 demonstrate clear value.

## Resource Strategy

| Work Type                              | Primary Location              | Notes |
|----------------------------------------|-------------------------------|-------|
| High-value reasoning & evaluation      | Commercial LLM API            | Used for proposals, critique, synthesis, and governance logic |
| High-volume / background agents        | Local CPUs                    | Monitoring, simple maintenance, and supporting processes |
| Lighter specialized models             | 1080ti                        | Where suitable for lower-stakes tasks |
| Persistent / always-on processes       | Local                         | Minimize unnecessary API usage |

**Guiding Rule:** Use the commercial LLM API for anything that directly affects code quality or governance decisions. Use local hardware for volume and persistence.

## Current Priorities

1. Focus on enhancing the **existing PrizmForge system** (Stage 0 → Stage 1).
2. Improve filtering and prioritization to address the high idea-to-adoption ratio.
3. Introduce light work partitioning and basic governance mechanisms.
4. Maintain strong safety while increasing implementation throughput.
5. Apply YAGNI discipline — avoid building multi-Territory support until it is clearly needed.

## Open Questions

- What is the minimum effective form of governance to add in the near term?
- How should we measure whether work partitioning is successful?
- When (if ever) should we introduce a second Territory?
- How aggressively should we expand the Spider Web discrimination layer?
- What specific metrics will we use to decide whether to move beyond a single Territory?

## Working Agreements

- We will treat added complexity as a cost that must be justified.
- We will prioritize improvements to the existing PrizmForge system over building new architectural layers.
- Scope will be actively managed to avoid speculative generalization.
- Success is defined by better code improvement outcomes, not by the number of Territories or architectural sophistication.

---

This plan is intentionally lightweight and meant to evolve. It prioritizes pragmatic improvement of the current system while keeping the door open for the longer-term Forge Federation vision.
