# Mental Model Territories

**Project:** Forge Federation (working name)  
**Framing:** A Stewardship-oriented Constitutional Polycentric Republic for multi-agent code improvement.

---

## Overview

Forge Federation is designed as a **Stewardship-oriented Constitutional Polycentric Republic**. Multiple distinct mental models operate as semi-sovereign **Territories** with protected autonomy, while a higher **Stewardship Governance layer** provides constitutional constraints and long-term orientation. A **Spider Web discrimination layer** runs across the system to distinguish high-value output from noise.

This architecture allows different reasoning paradigms to coexist and compete without any single model permanently dominating governance or evaluation.

---

## Core Architecture Layers

### 1. Stewardship Governance Layer (Constitutional Layer)

The top-level governance layer. It defines long-term values, hard constraints, and system-level rules through deliberative processes (**Moots**).

**Core Principles:**
- Protect long-term maintainability and future maintainers
- Preserve optionality and reversibility of changes
- Resist short-term optimization that creates long-term harm
- Protect the autonomy and diversity of multiple mental models
- Maintain accountability through real stakes and feedback

### 2. Spider Web Discrimination Layer (Cross-Cutting)

A system-wide capability (not a Territory) responsible for quality filtering and selective response. It helps the system distinguish valuable output from noise through multi-stage evaluation, explicit signals, and repair mechanisms.

### 3. Territories (Mental Model Ecosystems)

Territories are the primary units of reasoning and action. Each Territory operates according to a distinct mental model while remaining subject to constitutional constraints.

---

## Territory Model

Forge Federation uses a **hybrid Territory model** consisting of two parts:

- **Core Philosophy**: The fundamental worldview and values of the Territory.
- **Role**: The functional specialization or approach the Territory applies.

This model provides both identity and flexibility. Territories are intended to be defined primarily through configuration rather than hardcoded logic.

For detailed definitions, see:
- [`territory_core_details.md`](territory_core_details.md) — Full list and categorization of Core Philosophies
- [`territory_role_details.md`](territory_role_details.md) — Full list and categorization of Roles

### Incompatibility Matrix

Not all combinations of Core Philosophy and Role are compatible. An incompatibility matrix is maintained to prevent problematic pairings (e.g., **Stewardship** + **Experimenter**, **Scientific** + **Experimenter** as primary). 

See [`territory_core_details.md`](territory_core_details.md) for the full matrix.

---

## How Territories Interact

Territories can:
- Propose changes to the codebase
- Critique proposals from other Territories
- Participate in Moots for system-level decisions
- Develop internal strategies aligned with their Core Philosophy and Role

Influence between Territories is mediated through **trust/reputation** and demonstrated success in producing accepted, high-quality changes.

---

## Development Approach

Development follows a staged, YAGNI-driven approach:

- **Stage 0 (Current)**: Legacy PrizmForge with a single implicit Territory.
- **Stage 1 (Next)**: Enhanced single-Territory system with improved filtering, light work partitioning, and basic governance.
- **Stage 2 (Future)**: Full Forge Federation with multiple Territories.

For the detailed progression plan, see [`system_mental_model_progression_plans.md`](system_mental_model_progression_plans.md).

---

## Related Documents

| Document | Purpose |
|---------|---------|
| [`territory_core_details.md`](territory_core_details.md) | Detailed definitions and categories of Core Philosophies |
| [`territory_role_details.md`](territory_role_details.md) | Detailed definitions and categories of Roles |
| [`territory_model.md`](territory_model.md) | Overview of the hybrid Territory design |
| [`system_mental_model_progression_plans.md`](system_mental_model_progression_plans.md) | Evolution stages and development strategy |

---

*This document serves as the central overview and reference for mental models in Forge Federation.*
