# Flexible Plan — Forge Federation

**Working Name:** Forge Federation  
**Framing:** A Stewardship-oriented Constitutional Polycentric Republic for multi-paradigm, governed code improvement.

## Overview

Forge Federation builds on the original PrizmForge foundation by introducing multiple semi-sovereign **mental model ecosystems** (Territories) coordinated through a higher **Stewardship Governance layer** and supported by a **Spider Web discrimination layer**.

The system is designed to allow different reasoning paradigms to operate with protected autonomy while maintaining long-term orientation, quality control, and constitutional constraints.

Development will follow a flexible, sprint-based approach rather than rigid long-term timelines.

## Development Philosophy

- Work in short, focused sprints (typically 1–3 weeks of effort).
- Prioritize **working, demonstrable increments** over complete architecture.
- Keep scope narrow enough to finish something meaningful in each sprint.
- Heavily leverage existing permissive-license frameworks (CrewAI, LangGraph, etc.).
- Use the work API budget primarily for high-value reasoning and evaluation.
- Use local hardware for volume, persistence, and lower-stakes background work.
- Reassess scope and direction after each sprint.
- Draw useful patterns from systems like mydeadinternet.com while adapting them to code improvement needs.

## Architecture Alignment

The plan is organized around three core layers:

- **Stewardship Governance Layer** — Constitutional layer. Provides long-term values and hard constraints. Uses moots for changing system-level rules.
- **Spider Web Discrimination Layer** — Cross-cutting quality and filtering layer. Focuses on distinguishing valuable output from noise and enabling selective response.
- **Territories** — Semi-sovereign mental model ecosystems that propose, critique, and implement changes under constitutional constraints.

Early sprints will focus on getting these layers working together at a basic level rather than implementing every Territory or advanced mechanism immediately.

## Sprint Guidelines

- Define one clear outcome per sprint.
- Explicitly state what is **in scope** and what is **out of scope**.
- Prefer small, shippable progress over large redesigns.
- Document key decisions and learnings at the end of each sprint.
- Adjust scope between sprints based on what was learned.

## Phased Direction (Flexible)

These phases are directional and will be adjusted as needed.

### Phase 1: Foundation (First 3–4 sprints)
**Goal:** Establish a working multi-ecosystem system with basic coordination and code changes.

**Focus:**
- Select core orchestration tools (CrewAI + LangGraph)
- Create 2–3 initial Territories with distinct focuses
- Build a basic message bus and coordination cycles
- Implement end-to-end proposal → evaluation → materialization flow (starting with full file replacement)
- Establish basic logging and visibility

**Success Criteria:**
- Multiple Territories can propose and apply changes
- Basic coordination exists between them
- Changes can be safely written to disk with clear provenance

### Phase 2: Governance Layer (Next 2–3 sprints)
**Goal:** Introduce constitutional mechanisms and basic inter-Territory dynamics.

**Focus:**
- Lightweight Moot-style process for constitutional changes
- Basic trust/reputation scoring between Territories
- Initial territory-style organization
- Simple claims or proposal tracking with consequences

**Success Criteria:**
- There is a working mechanism for proposing and enacting higher-order rules
- Territories have measurable influence based on outcomes
- Basic accountability exists between ecosystems

### Phase 3: Discrimination & Robustness (Following sprints)
**Goal:** Strengthen quality control and self-correction.

**Focus:**
- Multi-stage evaluation using Spider Web principles
- Adversarial critique stages
- Basic maintenance and pruning behaviors
- Improved observability

**Success Criteria:**
- The system can filter low-quality proposals more reliably
- Clear visibility into why proposals succeed or fail

### Phase 4: Expansion & Hardening
**Goal:** Expand capabilities and stabilize the core system.

**Focus:**
- Evaluate adding additional Territories
- Refine interaction patterns between Territories
- Improve documentation and long-term maintainability
- Decide on final name and long-term scope

## Resource Strategy

| Work Type                              | Primary Location          | Notes |
|----------------------------------------|---------------------------|-------|
| High-value reasoning & evaluation      | Work API (50M tokens/day) | Proposals, critique, synthesis, and moots |
| High-volume / background agents        | Local CPUs                | Heartbeat agents, monitoring, simple tasks |
| Lighter specialized models             | 1080ti                    | Quantized models where suitable |
| Persistent / always-on processes       | Local                     | Minimize API usage for long-running agents |

**Guiding Rule:** Use the API budget for anything that directly affects code quality or governance decisions. Use local hardware for volume and persistence.

## Current Priorities (Starting Point)

1. Define the minimum interesting MVP after the first 2–3 sprints.
2. Finalize core technical stack for orchestration and coordination.
3. Create the first 2–3 Territories with clear differentiation.
4. Deliver a working proposal → evaluation → materialization loop.
5. Establish sprint rhythm and lightweight documentation habits.

## Open Questions

- How formal should the initial Moot process be?
- What is the right balance between autonomy and coordination in early sprints?
- How should trust/reputation between Territories be calculated initially?
- When should we expand beyond the initial three Territories?
- How aggressively should we incorporate Spider Web discrimination mechanisms in the first few sprints?

## Working Agreements

- Scope can and should be adjusted between sprints.
- We will favor consistent, visible progress over attempting to build everything at once.
- We will regularly ask whether current direction still serves the long-term vision of a Stewardship-oriented Constitutional Polycentric Republic.

---

This plan is intentionally lightweight and meant to evolve. It provides enough structure to maintain momentum while remaining flexible to new learnings and constraints.
