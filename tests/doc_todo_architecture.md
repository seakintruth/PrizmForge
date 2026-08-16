# PrizmForge Production-Grade Test Suite & Deployment Architecture

This document provides the testing framework overview, gap analysis audit, and deployment architecture notes for PrizmForge—an LLM-driven governed code editing and multi-agent orchestration system.

**Status note (2026-08-16, PR #67):** High-priority pure unit coverage phases 1–5 are implemented and hollow-assertion cleaned:

1. Edit pipeline (`edit_response_validator`, `edit_mode_selector`, `edit_payload`, `proposal_builder`)
2. Config helpers (`normalize_path`, `find_config_file`, `validate_config`, repo root / project dir)
3. JSON / response parsing (`JSONParser` strategies, `ResponseParser`)
4. Agent schema contracts (`validate`, fallback schemas, prompt schema builders)
5. Failure boundaries (`EndpointManager`, `RateLimiter` with mocked-time limits)

Path containment remains in `test_path_normalization.py`. Op parse/apply matrix remains in `test_edit_contracts.py`. See `tests/README.md` for the pure-suite command and assertion-strength rules.

Sections below retain the longer aspirational 7-layer plan and historical gap matrix; treat completed pure coverage as closed for prioritization.

---

1. Executive Summary & Architecture Overview

PrizmForge executes autonomous software modifications through a strict two-path design:

- **Governed Sequential Mutation Path**: Orchestrator → Developer (`EditPayload`) → Proposal → Reviewer (Safety Gate) → Materialization (`file_lines` DB + Disk + Git).

- **Parallel Background Analysis Path**: Non-mutating diagnostic agents (`jr_reviewer`, `security_reviewer`, `tech_writer`, `deployment_validator`, `archivist`, `prioritizer`, `resource_controller`) continuously analyzing code and posting structured feedback.

To ensure stability, zero network leakage in CI, strict path containment, optimistic concurrency validation, and memory safety, this framework implements a layered QA suite tailored for air-gapped and mirror-restricted environments (such as Advana PyPI).

## 7-Layer QA Architecture
| Layer | Description | Current emphasis |
| :--- | :--- | :--- |
|  1 | Unit Testing (pytest + stdlib mocks + sandboxed fixtures) | **Primary — pure modules complete for high-risk gates** |
|  2 | Integration Testing (Multi-Agent Workflow, DB Lifecycle & Proposal Undo) | Present (golden path, edit workflows, cycle) |
|  3 | Property & Static Analysis (hand-rolled fuzz + ruff + optional mypy) | Fuzz tables + GHA ruff check/format |
|  4 | Functional & API Endpoint Testing | CLI-focused today; REST is aspirational |
|  5 | Performance & Load Testing | Pool/lifecycle stress under `@slow` |
|  6 | Security Auditing (Ruff S-Rules + Content Safety Guards) | Content safety + path containment tests |
|  7 | CI/CD Automation Pipeline | GHA: auto-fix → ruff check → normal suite |

2. Actual Current State Audit & Gap Analysis

A review of the repository context reveals that most core testing capabilities are already built and functional:

- **Hermetic LLM Isolation (`tests/mocks/openai.py`)**: `MockLLM` and `mock_openai_chat` provide in-memory, stdlib-only mocking for all LLM calls across agents (`CALL_AGENT_PATCH_TARGETS`), ensuring zero network leakage or API costs during test runs.

- **Governed Editing & Concurrency (`tests/test_governed_editing.py`, `tests/integration/test_edit_workflows.py`)**: Tests line-level GUID operations and optimistic concurrency hash mismatch detection.

- **High-priority pure gates (PR #67)**: Edit response validation matrix, mode selection heuristics, EditPayload coercion, proposal `task_id`/mode metadata, config path/validate helpers, JSONParser/ResponseParser strategies, agent schema validate/fallback, EndpointManager health/fallback, RateLimiter window eviction.

- **Proposal Undo & Event Logging (`tests/unit/test_events_undo.py`)**: Verifies `undo_proposal` content restoration and event bus publication.

- **Binary Content Safety (`tests/unit/test_content_safety.py`)**: Enforces magic-byte rejection (`MZ`, `ELF`, `OLE/CFB`) and path extension guards while permitting text scripts.

- **Path Containment & Hardening (`tests/unit/test_path_normalization.py`, `test_hardening.py`)**: Rejects directory traversal and enforces project directory containment.

- **Background Worker Lifecycle (`tests/unit/test_parallel_workers.py`, `tests/unit/test_worker_lifecycle.py`)**: Pool, feeder, and lifecycle under isolation fixtures.

- **CLI & Shell Test Runners (`utils/run_tests.sh`, `utils/run_critical_tests.py`)**: Batched pytest execution and stdlib-only critical runner for minimal hosts.

### Gap Analysis & Advana PyPI Mirror Adaptation Matrix

| Dimension | Existing State | Remaining / optional |
| :--- | :--- | :--- |
| **1. Unit Testing** | High-priority pure modules covered with non-hollow asserts | Broader module-by-module expansion; keep assertion-strength rules |
| **2. Integration Testing** | Golden path, edit workflows, task cycle | Multi-turn rollback under concurrent mutations |
| **3. Property & Typing** | Hand-rolled fuzz tables; GHA `ruff check` / `format --check` | Optional Hypothesis; mypy not a hard GHA gate today |
| **4. Functional API** | CLI + DB coverage | FastAPI/httpx only if/when REST surface lands |
| **5. Performance / Load** | `@slow` worker stress | Formal benchmark suite only if needed |
| **6. Security Auditing** | Content safety + containment tests | Expand Ruff `S` selection in CI if desired |
| **7. CI/CD Pipeline** | auto-fix → code-quality (ruff) → normal tests | Ensure `test/**` branches always get PR checks (already on `pull_request`) |

3. Layer 1 notes

Isolated unit tests cover core utilities without network calls or persistent disk side effects. Prefer matrices over free-form cases. Fixtures in `conftest.py` force per-test workspaces and hard-disable background agents so live workers cannot spawn.

**Anti-patterns (hollow tests):** `assert callable(...)`, always-true `OR` branches, `if result is not None` success paths, truthy-only rationale checks. See `tests/README.md`.

4–9. Layers 2–7

Historical sample snippets for integration, Hypothesis, FastAPI, Locust, and full multi-version coverage gates remain useful as **templates** if those layers are built out. They are not required for merge readiness of the pure-coverage work. Current production CI is defined in `.github/workflows/python-package.yml`:

1. Auto-fix (ruff --fix, black, isort, ruff format) and push
2. `ruff check .` + `ruff format --check .`
3. `./utils/run_tests.sh --normal -j 4 --timeout 30`

10. Strategic justification

Protecting against autonomous agent threat vectors remains the primary ROI: path containment, binary rejection, governed proposal integrity, and token/rate budgets. Pure unit coverage on the modules that **gate** those paths is higher leverage than chasing global coverage % on `task_runner` first.
