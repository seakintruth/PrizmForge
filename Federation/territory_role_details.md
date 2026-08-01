# Territory Role Details

This document defines the **Roles** used in Forge Federation’s hybrid Territory model.

## Overview

While a **Core Philosophy** defines *what* a Territory fundamentally values, a **Role** defines *how* the Territory operates and contributes to code improvement.

Roles act as specializations. They allow Territories to have focused capabilities while still being grounded in a Core Philosophy.

### Role Composition Rules

- Every Territory has **exactly one Primary Role**.
- A Territory **may** have one optional **Secondary Role**.
- Roles should generally be compatible with the Territory’s Core Philosophy (see Incompatibility Matrix in `territory_core_details.md`).
- Role behavior is primarily expressed through system prompts and context, while Role assignment is tracked structurally.

---

## Role Categories

Roles are grouped into five categories:

| Category                | Focus                              | Example Roles              |
|-------------------------|------------------------------------|----------------------------|
| **Critical / Analytical** | Evaluation, critique, and quality  | Adversarial, Auditor       |
| **Generative**            | Creation and transformation        | Synthesizer, Experimenter, Regenerator |
| **Operational**           | Execution and delivery             | Implementer, Prioritizer   |
| **Coordination**          | Interaction and knowledge flow     | Facilitator, Archivist     |
| **Maintenance**           | Stability and long-term health     | Maintainer                 |

---

## Detailed Role Definitions

### Critical / Analytical Roles

#### Adversarial
- **Description**: Actively challenges proposals, ideas, and assumptions. Looks for edge cases, risks, and flaws.
- **Strengths**: Uncovers hidden problems and improves robustness.
- **Weaknesses**: Can become overly negative or slow down progress if not balanced.
- **Best Paired With**: Most Core Philosophies (especially Stewardship and Scientific).
- **Primary Output**: Critiques, risk assessments, red-team reports.

#### Auditor
- **Description**: Focuses on compliance, standards, correctness, and consistency.
- **Strengths**: Enforces quality and reduces defects.
- **Weaknesses**: Can slow down innovation and exploration.
- **Best Paired With**: Scientific, Stewardship, Hierarchical.
- **Primary Output**: Audit reports, compliance checks, standards enforcement.

### Generative Roles

#### Synthesizer
- **Description**: Excels at combining ideas, patterns, and solutions from multiple sources into coherent outcomes.
- **Strengths**: Creates novel and integrated solutions.
- **Weaknesses**: Can lose depth or focus when combining too many inputs.
- **Best Paired With**: Evolutionary, Scientific, Craft/Aesthetic.
- **Primary Output**: Integrated designs, refactored solutions, synthesized approaches.

#### Experimenter
- **Description**: Generates and tests many variations to explore possibilities.
- **Strengths**: High capacity for discovery and breaking new ground.
- **Weaknesses**: High failure rate and potential for instability.
- **Best Paired With**: Evolutionary (primary), Scientific (with caution).
- **Primary Output**: Prototypes, variants, experimental changes.

#### Regenerator
- **Description**: Performs large-scale rewrites by extracting intent and rebuilding cleaner implementations.
- **Strengths**: Effectively reduces accumulated technical debt and complexity.
- **Weaknesses**: Risk of losing valuable implicit knowledge or behavior.
- **Best Paired With**: Regenerative (core), Stewardship (with care).
- **Primary Output**: Major refactors and system renewals.

### Operational Roles

#### Implementer
- **Description**: Focuses on turning ideas, plans, and specifications into working, maintainable code.
- **Strengths**: Strong execution and delivery focus.
- **Weaknesses**: Can undervalue exploration and long-term considerations.
- **Best Paired With**: Most Core Philosophies.
- **Primary Output**: Code changes, features, and implementations.

#### Prioritizer
- **Description**: Ranks and sequences work items based on value, risk, and impact.
- **Strengths**: Improves overall throughput and focus.
- **Weaknesses**: Can become overly mechanical or miss important nuance.
- **Best Paired With**: Scientific, Hierarchical, Short-term Optimization.
- **Primary Output**: Prioritized work queues and sequencing recommendations.

### Coordination Roles

#### Facilitator
- **Description**: Helps coordinate between Territories, resolves conflicts, and improves collaboration.
- **Strengths**: Reduces friction between different mental models.
- **Weaknesses**: Can become a bottleneck if over-relied upon.
- **Best Paired With**: Polycentric, Stewardship.
- **Primary Output**: Coordinated plans, resolved conflicts, improved cross-Territory communication.

#### Archivist
- **Description**: Captures decisions, historical context, and institutional knowledge.
- **Strengths**: Prevents repeated mistakes and preserves important context.
- **Weaknesses**: Can slow down decision-making and momentum.
- **Best Paired With**: Stewardship, Regenerative.
- **Primary Output**: Decision records, documentation, and knowledge repositories.

### Maintenance Roles

#### Maintainer
- **Description**: Focuses on keeping existing systems understandable, stable, and healthy over time.
- **Strengths**: Protects long-term clarity and reduces degradation.
- **Weaknesses**: Can resist necessary change or innovation.
- **Best Paired With**: Stewardship, Craft/Aesthetic.
- **Primary Output**: Refactoring, cleanup, documentation improvements, and stability work.

---

## Role Interaction Guidelines

- A **Primary Role** defines the main contribution and behavior of the Territory.
- A **Secondary Role** should complement the Primary Role rather than contradict it.
- Roles influence how a Territory interacts with the **Spider Web discrimination layer** and other Territories.
- When evaluating proposals, the system may consider both the Core Philosophy and Role(s) of the originating Territory.

---

## Summary Table

| Role            | Category             | Primary Strength             | Common Pairings                  | Caution With                  |
|-----------------|----------------------|------------------------------|----------------------------------|-------------------------------|
| Adversarial     | Critical             | Finding flaws                | Stewardship, Scientific          | Overly negative tone          |
| Auditor         | Critical             | Compliance & consistency     | Scientific, Stewardship          | Slowing innovation            |
| Synthesizer     | Generative           | Combining ideas              | Evolutionary, Scientific         | Losing depth                  |
| Experimenter    | Generative           | Exploration                  | Evolutionary                     | Instability                   |
| Regenerator     | Generative           | Large-scale renewal          | Regenerative                     | Loss of history               |
| Implementer     | Operational          | Execution                    | Most philosophies                | Undervaluing exploration      |
| Prioritizer     | Operational          | Throughput                   | Scientific, Hierarchical         | Overly mechanical             |
| Facilitator     | Coordination         | Cross-Territory collaboration| Polycentric, Stewardship         | Becoming a bottleneck         |
| Archivist       | Coordination         | Knowledge preservation       | Stewardship, Regenerative        | Slowing progress              |
| Maintainer      | Maintenance          | Long-term stability          | Stewardship, Craft/Aesthetic     | Resisting necessary change    |

---

**Status**: Planning / Ideation. This document supports the Stage 2 (Forge Federation) vision and is intended to be used alongside `territory_core_details.md`.
