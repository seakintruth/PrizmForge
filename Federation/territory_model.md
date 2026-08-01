# Territory Model — Hybrid Core + Role Design

## Overview

In Forge Federation, **Territories** represent distinct mental models that can participate in governed code improvement. Rather than defining each Territory as a rigid, monolithic entity, we use a **hybrid composable model** inspired by systems like Dungeons & Dragons (races + classes).

This approach separates:

- **Core Philosophy** — The fundamental worldview and values of the Territory.
- **Role** — The functional specialization or approach the Territory uses.

This design allows flexibility while maintaining enough structure for governance, coordination, and safety.

## Design Goals

- Enable meaningful diversity of reasoning styles without excessive complexity.
- Support experimentation while protecting against "Tamagotchi" over-engineering.
- Keep the core engine stable by moving Territory definition into configuration.
- Allow Territories to be composed rather than endlessly duplicated.
- Provide clear boundaries for governance and the Spider Web discrimination layer.

## Core Philosophy (The "Race")

The **Core Philosophy** defines a Territory’s fundamental values and beliefs about what constitutes good improvement.

### Categories

| Category              | Examples                        | Focus                              |
|-----------------------|---------------------------------|------------------------------------|
| Value-Based           | Stewardship, Craft/Aesthetic    | Long-term care, elegance, ethics   |
| Epistemological       | Scientific, Empirical/Pragmatic | How we determine what is "good"    |
| Evolutionary          | Evolutionary, Regenerative      | Change through variation or renewal|
| Structural            | Polycentric, Hierarchical       | How decisions and power are organized |
| Temporal              | Long-term Optimization, Short-term Optimization | Time horizon and priorities     |

Each Territory must have **exactly one Core Philosophy**. This provides stable identity and serves as the primary input for constitutional constraints.

## Role (The "Class")

The **Role** defines *how* a Territory operates and what functional strengths it brings.

### Categories

| Category                | Examples                          | Primary Strength                     |
|-------------------------|-----------------------------------|--------------------------------------|
| Critical / Analytical   | Adversarial, Auditor              | Finding flaws and ensuring quality   |
| Generative              | Synthesizer, Experimenter, Regenerator | Creating or combining new solutions |
| Operational             | Implementer, Prioritizer          | Execution and throughput             |
| Coordination            | Facilitator, Archivist            | Managing interaction and knowledge   |
| Maintenance             | Maintainer                        | Preserving stability and clarity     |

A Territory has **one primary Role** and may optionally have **one secondary Role**.

## Incompatibility Matrix

Not all combinations of Core Philosophy and Role are healthy. The system maintains an **incompatibility matrix** to prevent problematic pairings.

Examples of poor fits include:

- **Stewardship** + **Experimenter** (primary)
- **Scientific** + **Experimenter** (primary)
- **Polycentric** + strong Hierarchical behavior
- **Evolutionary** + **Auditor** (primary)
- **Regenerative** + **Maintainer** (primary)

This matrix is enforced at the configuration level when Territories are defined.

## Architectural Split: Hardcoded vs. Configured

To keep the system maintainable and reduce Tamagotchi-style development, we separate concerns:

| Layer                        | Hardcoded / Structural                  | Configured / Prompt-based                  | Notes |
|-----------------------------|-----------------------------------------|--------------------------------------------|-------|
| **Core Philosophy**         | Identity + Incompatibility rules        | Behavioral expression                      | Core identity should be queryable |
| **Role**                    | Assignment system                       | How the role thinks and behaves            | Roles are mostly prompt-driven |
| **Governance (Moots)**      | Mechanics, voting, enforcement          | Interpretation of principles               | Must remain reliable |
| **Spider Web**              | Pipeline structure + routing            | Evaluation criteria                        | Structure is fixed, judgment is flexible |
| **Territory Definition**    | Schema and validation                   | JSON/config + optional UI                  | Primary place for experimentation |
| **Agent Behavior**          | Role assignment                         | Reasoning style, collaboration, tone       | Highly prompt-driven |

### Key Principle

- **Structure and safety** live in code.
- **Identity, philosophy, and behavior** live in configuration and prompts.

This allows us to experiment with new Territories through configuration and a D&D-style UI rather than by modifying core logic.

## Reducing Tamagotchi Tendencies

By moving Territory creation and customization into human-readable configuration (JSON/database) and a potential UI, we aim to:

- Keep the core engine focused on governance, safety, and execution.
- Allow creative exploration without constantly changing production code.
- Make it easier to apply **YAGNI** — many Territories can be defined, but only a few need to be active.
- Shift "fun" experimentation into configuration rather than codebase modification.

## Territory Composition Rules (Current)

- Every Territory must have **exactly one Core Philosophy**.
- Every Territory has **one primary Role** (secondary Role is optional).
- New Territory definitions must pass validation against the incompatibility matrix.
- Territory definitions are loaded at runtime from configuration.

## Future Considerations

- Should Territories be allowed to change Roles over time?
- How should the Governance layer apply constitutional constraints to composite Territories?
- What level of UI support should exist for creating and managing Territories?
- How do we prevent configuration-level "Tamagotchi" behavior (endless creation of new Territory combinations)?

## Related Documents

- `federation/hybrid_territory_design.md` (earlier exploration)
- `system_mental_model_progression_plans.md`
- `mental_model_territories.md`

---

**Status**: Ideation / Planning. This model is part of the Stage 2 (Forge Federation) vision and is currently documented only.
