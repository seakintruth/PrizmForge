# PrizmForge Test Suite — LLM / Architectural Context

This file is the **durable context document** for agents and long-term architectural memory about the testing framework.

- **Operational commands, pure-suite inventory, assertion rules, and day-to-day gates** live in [`README.md`](README.md).
- Do not duplicate command lists or assertion rules here.

**Last major update:** 2026-08-16 (PR #67 pure coverage + documentation consolidation).

---

## Purpose

PrizmForge executes autonomous software modifications through a strict two-path design:

- **Governed Sequential Mutation Path**: Orchestrator → Developer (`EditPayload`) → Proposal → Reviewer (Safety Gate) → Materialization (`file_lines` DB + Disk + Git).
- **Parallel Background Analysis Path**: Non-mutating diagnostic agents (`jr_reviewer`, `security_reviewer`, `tech_writer`, `deployment_validator`, `archivist`, `prioritizer`, `resource_controller`) continuously analyzing code and posting structured feedback.

The test suite exists to protect the mutation path against the unique failure modes of autonomous agents: repository corruption, path escapes, binary injection, unbounded token spend, and concurrent overwrite of line-GUID state.

---

## Status — High-priority pure unit coverage (PR #67)

Phases 1–5 are **complete** and hollow-assertion cleaned:

1. **Edit pipeline** — `edit_response_validator`, `edit_mode_selector`, `edit_payload`, `proposal_builder`
2. **Config helpers** — `normalize_path`, `find_config_file`, `validate_config`, repo root / project directory
3. **JSON / response parsing** — `JSONParser` strategies, `ResponseParser`
4. **Agent schema contracts** — validate, fallback schemas, prompt schema builders
5. **Failure boundaries** — `EndpointManager`, `RateLimiter` (mocked-time limits)

Path containment remains in `test_path_normalization.py`.  
Op parse/apply matrix remains in `test_edit_contracts.py`.

See `tests/README.md` for the exact pure-suite command and the assertion-strength rules that must be followed when extending these tests.

---

## 7-Layer QA Architecture

| Layer | Description | Current emphasis |
| :--- | :--- | :--- |
| 1 | Unit Testing (pytest + stdlib mocks + sandboxed fixtures) | **Primary** — pure modules complete for high-risk gates |
| 2 | Integration Testing (Multi-Agent Workflow, DB Lifecycle & Proposal Undo) | Present (golden path, edit workflows, cycle) |
| 3 | Property & Static Analysis (hand-rolled fuzz + ruff + optional mypy) | Fuzz tables + GHA `ruff check` / `format --check` |
| 4 | Functional & API Endpoint Testing | CLI-focused today; REST is aspirational |
| 5 | Performance & Load Testing | Pool/lifecycle stress under `@slow` |
| 6 | Security Auditing (Ruff S-Rules + Content Safety Guards) | Content safety + path containment tests |
| 7 | CI/CD Automation Pipeline | GHA: auto-fix → ruff check → normal suite |

---

## Current State Audit & Gap Matrix

Most core testing capabilities are already built and functional:

- Hermetic LLM isolation via `MockLLM` / `mock_openai_chat` (zero network leakage).
- Governed editing & concurrency tests (`test_governed_editing.py`, integration edit workflows).
- High-priority pure gates (PR #67) listed above.
- Proposal undo & event logging.
- Binary content safety (magic-byte + extension rejection).
- Path containment & hardening.
- Background worker lifecycle under isolation fixtures.
- Batched CLI runners (`utils/run_tests.sh`, `utils/run_critical_tests.py`).

### Gap / Remaining Work

| Dimension | Existing State | Remaining / Optional |
| :--- | :--- | :--- |
| 1. Unit Testing | High-priority pure modules covered with non-hollow asserts | Broader module-by-module expansion; keep assertion-strength rules |
| 2. Integration Testing | Golden path, edit workflows, task cycle | Multi-turn rollback under concurrent mutations |
| 3. Property & Typing | Hand-rolled fuzz tables; GHA ruff | Optional Hypothesis; mypy not a hard GHA gate today |
| 4. Functional API | CLI + DB coverage | FastAPI/httpx only if/when REST surface lands |
| 5. Performance / Load | `@slow` worker stress | Formal benchmark suite only if needed |
| 6. Security Auditing | Content safety + containment tests | Expand Ruff `S` selection in CI if desired |
| 7. CI/CD Pipeline | auto-fix → code-quality (ruff) → normal tests | Ensure `test/**` branches always receive PR checks (already on `pull_request`) |

---

## Strategic Justification

Protecting against autonomous agent threat vectors is the primary ROI:

- Path containment prevents agents from writing outside the designated project directory.
- Binary rejection prevents PE/MSI/OLE payloads from being written as “source”.
- Line-GUID optimistic concurrency + proposal integrity prevent silent overwrites.
- Rate / token budgets prevent runaway cost loops.

Pure unit coverage on the modules that **gate** those paths delivers higher leverage than chasing global coverage percentage on `task_runner` first.

---

## Multi-Platform CI Notes

**Active primary CI:** GitHub Actions (`.github/workflows/python-package.yml`)

Current gates on `pull_request` to `main`/`develop`:

1. Auto-Fix & Push — `ruff check --fix`, `black`, `isort`, `ruff format` (bot commit, often `[skip ci]`)
2. Code Quality — `ruff check .` and `ruff format --check .`
3. Normal Test Suite — `./utils/run_tests.sh --normal -j 4 --timeout 30`

Parity templates (GitLab CI, AWS CodeBuild) should enforce the same two hard gates: ruff check/format + the normal test runner. Coverage fail-under and mypy remain optional, not required for pure-suite merge readiness.

Local pre-push alignment:

```bash
ruff check .
ruff format --check .
./utils/run_tests.sh --normal -j 4 --timeout 30
```

Known lint pitfalls when adding tests: Ruff `RUF043` requires escaping metacharacters in `pytest.raises(..., match=...)`. Complex multi-branch validators may need `# noqa: C901` when the branching *is* the product surface.

---

## Guidance for Agents Extending the Suite

1. Read this file for philosophy and remaining gaps.
2. Read `README.md` for the exact pure-suite command, assertion-strength rules, and fixtures.
3. Prefer matrices and explicit injected signatures over free-form “interesting” cases.
4. Never introduce hollow assertions (`assert callable(...)`, always-true ORs, conditional success paths).
5. Keep new documentation in the correct place: operational → README, architectural intent → this file.
