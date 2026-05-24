# Flexible Plan — Forge Federation

**Working Name:** Forge Federation (name still under discussion)  
**Goal:** Build a governed, multi-paradigm agent system for reliable, long-term improvement of existing codebases.  
**Approach:** Short, focused sprints with clear deliverables. Avoid long-term rigid planning.

## Development Philosophy

- Work in **short, focused sprints** (typically 1–3 weeks of real effort).
- Prioritize **working prototypes** over perfect architecture early on.
- Keep scope narrow enough to finish something meaningful in each sprint.
- Leverage existing permissive-license frameworks heavily (CrewAI, LangGraph, etc.).
- Use the work API budget for high-value reasoning and evaluation.
- Use local hardware (120 CPU cores + 1080ti) for volume, persistence, and lower-stakes work.
- Reassess direction after each sprint based on what was actually built and learned.
- Draw inspiration from mydeadinternet.com (moots, territories, claims, trust, adversarial design) and game systems like Endless Sky, while adapting them to code improvement.

## Sprint Guidelines

- Define a **single, clear outcome** per sprint.
- Define what “done” looks like before starting.
- Explicitly decide what we are **not** building in the current sprint.
- Prefer small, shippable increments over big redesigns.
- Document learnings and blockers at the end of each sprint.

## High-Level Phases (Flexible)

These phases are directional, not fixed timelines.

### Phase 1: Foundation (First 2–4 sprints)
**Goal:** Get a minimal working system with multiple ecosystems and basic coordination.

**Focus areas:**
- Choose core orchestration tools (CrewAI + LangGraph recommended)
- Create 2–3 initial mental model ecosystems with distinct focuses
- Build a basic message bus / coordination layer
- Implement simple suggestion → evaluation → decision cycles
- Get end-to-end code materialization working (start with full file replacement)
- Establish basic logging and visibility

**Success criteria:**
- Can run multiple distinct agent groups that propose and apply changes
- Basic coordination between groups exists
- Changes can be materialized to disk safely

### Phase 2: Governance Layer (Next 2–3 sprints)
**Goal:** Add higher-order rules and basic inter-ecosystem dynamics.

**Focus areas:**
- Lightweight moot-style constitutional mechanism
- Basic trust / reputation scoring between ecosystems
- Simple territory-style organization
- Initial claims or proposal tracking with consequences
- Early adversarial evaluation patterns

**Success criteria:**
- Ecosystems can influence each other through structured mechanisms
- There is a way to propose and enact higher-order rules
- Basic accountability and feedback exists between groups

### Phase 3: Depth & Self-Correction (Following sprints)
**Goal:** Add robustness, evaluation quality, and maintenance behaviors.

**Focus areas:**
- Stronger multi-judge evaluation
- Maintenance and self-correction layers (pruning, vindication-style recovery)
- Expanded number of ecosystems (if valuable)
- Improved observability and debugging tools
- Better handling of inter-ecosystem relationships (cooperation, tension, resource dynamics)

**Success criteria:**
- The system can run for longer periods with less manual intervention
- Evaluation quality is noticeably better than single-judge approaches
- Clear visibility into what each ecosystem is doing and why

### Phase 4: Hardening & Direction Setting
**Goal:** Decide what the system should become long-term and stabilize the core.

**Focus areas:**
- Refine constitutional and governance mechanisms
- Evaluate whether to expand into more sophisticated economic/reputation models
- Decide on final name and branding
- Improve documentation and onboarding
- Determine which parts should be hardened vs kept experimental

## Resource Strategy

| Work Type                              | Primary Location          | Notes |
|----------------------------------------|---------------------------|-------|
| High-value reasoning & evaluation      | Work API (50M tokens/day) | Use for proposals, judging, synthesis, and moots |
| High-volume / background agents        | Local CPUs (120 cores)    | Heartbeat agents, monitoring, simple maintenance |
| Lighter or specialized models          | 1080ti                    | Quantized models for lower-stakes tasks |
| Persistent / always-on processes       | Local                     | Avoid burning API budget unnecessarily |

## Current Priorities (Starting Point)

1. Define the **minimum interesting MVP** we want after the first 2–3 sprints.
2. Choose the core technical stack (orchestration + message bus).
3. Create the first 2–3 mental model ecosystems with clear differentiation.
4. Get a working proposal → evaluation → materialization loop.
5. Establish basic sprint rhythm and documentation habits.

## Open Questions (to revisit regularly)

- How many ecosystems do we actually need in the early versions?
- How formal should the constitutional/moot layer be at the start?
- What is the right balance between competition and cooperation between ecosystems?
- How heavily should we lean into MDI-style mechanisms (claims, trust decay, adversarial stages) versus keeping things simpler?
- When should we revisit the project name?

## Working Agreements

- We will favor **progress over perfection** in early sprints.
- We will document decisions and learnings as we go.
- We will regularly ask: “Is this still the right direction, or are we overbuilding?”
- Scope can (and should) be adjusted between sprints based on what we learn.

---

This plan is intentionally lightweight and meant to be updated frequently. The goal is to maintain momentum while staying flexible about both scope and direction.
