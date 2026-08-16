# PrizmForge Test Suite

Deterministic tests for governed multi-agent editing. **No network required** for the default suite. Designed for Advana / SageMaker environments (pytest + pytest-mock + stdlib mocks).

## Quick start

```bash
# From repo root
pip install -r requirements-dev.txt   # pytest, pytest-mock (+ optional black/flake8)

pytest tests/ -m "not slow" -q        # full CI-friendly suite
pytest tests/ -v                      # verbose
bash utils/run_tests.sh --normal -j 4 # preferred CI entry (batched runner)
pytest tests/ -m slow -q              # concurrent worker stress only
```

**Without pytest** (ultra-minimal image):

```bash
python -m utils.run_critical_tests
```

**Optional real-model smoke** (skips without API keys / network):

```bash
python -m utils.smoke_real_model
```

---

## High-priority pure unit suite (PR #67)

These modules gate governed edits, containment, LLM response handling, contracts, and failure boundaries. Prefer this list when expanding coverage before broader integration work.

| Phase | Module | Test file |
|-------|--------|-----------|
| 1 Edit pipeline | `edit_response_validator`, `edit_mode_selector`, `edit_payload`, `proposal_builder` | `test_edit_response_validator.py`, `test_edit_mode_selector.py`, `test_edit_payload.py`, `test_proposal_builder.py` |
| 2 Config | `core.config` path/validate helpers | `test_config.py` |
| 3 JSON / response | `json_parser`, `response_parser` | `test_json_parser.py`, `test_response_parser.py` |
| 4 Schemas | `agent_schemas` | `test_agent_schemas.py` |
| 5 Failure boundaries | `endpoint_manager`, `rate_limiter` | `test_endpoint_manager.py`, `test_rate_limiter.py` |

```bash
pytest tests/unit/test_edit_response_validator.py \
       tests/unit/test_edit_mode_selector.py \
       tests/unit/test_edit_payload.py \
       tests/unit/test_proposal_builder.py \
       tests/unit/test_config.py \
       tests/unit/test_json_parser.py \
       tests/unit/test_response_parser.py \
       tests/unit/test_agent_schemas.py \
       tests/unit/test_endpoint_manager.py \
       tests/unit/test_rate_limiter.py -q
```

### Assertion strength (no hollow tests)

1. **Assert outcomes**, not existence — no `assert callable(...)` smoke tests.
2. **No always-true ORs** — e.g. do not accept `selected_mode == input` as proof a fallback tag was persisted.
3. **No conditional pass** — `if result is not None: assert ...` must become `assert result is not None` when the case claims success.
4. **Prefer exact values** for auto-fills, mode tags, cooldown defaults, and DB rows.
5. Soft `in (A, B)` is allowed only when two failure reasons are both correct for the same input shape (e.g. extraction vs parse).

Path containment remains covered by `test_path_normalization.py` (writer). Edit op parse/apply matrix lives in `test_edit_contracts.py` (some apply cases marked `slow`).

---

## Production hardening scope

Automated tests cover: orchestrator routing, backlog override, multi-turn cycle, reviewer reject,
background pool lifecycle, RC optimizer shapes, HTTP 401/429 shapes, governed edit pipeline,
**binary content rejection** (MSI/PE/OLE — not text scripts), high-priority pure modules above.

**Out of CI scope:** real-model quality, multi-hour unattended (see soak runbooks under `.PrizmForge/reports/` when present).

## Gates (production hardening)

| Gate | Command | Intent |
|------|---------|--------|
| **Fast / normal** | `./utils/run_tests.sh --normal -j 4` | Merge / GHA `test-normal` job |
| **Full** | `./utils/run_tests.sh --full --batched` | Host-aware full matrix |
| **Slow** | `pytest tests/ -m slow` | Concurrent worker stress |
| **Live** | `python -m utils.smoke_real_model` | Optional real API (not a merge gate) |
| **Lint** | `ruff check .` and `ruff format --check .` | GHA `code-quality` job |

### MockLLM import sites

`call_agent` is patched at all entries in `tests.mocks.openai.CALL_AGENT_PATCH_TARGETS`.
New modules that `from agents.base import call_agent` must call `register_call_agent_patch_target(...)`.

## Philosophy

1. **Mock LLMs by default** — `MockLLM` / `mock_openai_chat` (stdlib `unittest.mock`; no `responses` package).
2. **Real sqlite + temp filesystem** for file-editing paths.
3. **Assert outcomes** (file content, proposal status, counters, exact failure reasons) — not just "no exception."
4. **Zero new runtime deps** — tests use pytest + pytest-mock from the Advana-approved set.
5. **More in-repo code > exotic test packages** (no Hypothesis required; hand-rolled fuzz tables instead).
6. **Explicit context over free-form generation** — when adding tests, inject signatures, fixtures, and exemplar patterns; prefer matrices over inventing three "interesting" cases.

---

## Mocking LLMs

```python
def test_flow(mock_llm):
    mock_llm.set_response("orchestrator", '{"next_agent": "developer", ...}')
    mock_llm.set_responses("developer", ["plan text", '{"operations": [...]}'])
    mock_llm.set_response("reviewer", '{"decision": "APPROVE", "reason": "ok"}')

    with mock_llm.patch_call_agent():
        from agents.base import call_agent

        ...
```

Fixtures (see `conftest.py`): `mock_llm`, `mock_llm_patched`, `mock_openai_chat`, `temp_db`, `mock_minimal_config`, `_isolate_prizmforge_workspace` (autouse).

---

## Content safety (binary rejection)

`core/content_safety.py` is covered by `tests/unit/test_content_safety.py`.

| Allowed | Blocked |
|---------|---------|
| Text source (`.py`, `.ps1`, `.bat`, `.cmd`, `.js`, ...) | PE/`MZ`, ELF, OLE/CFB (MSI), Mach-O magic |
| Normal UTF-8 source | NUL bytes / high non-text ratio |
| | Paths that are binary formats only (`.msi`, `.exe`, `.dll`, ...) |

Text scripting languages are **not** blocked by extension. Only **binary** payloads and binary package/executable extensions.

Config: `content_safety.disallow_binary_content` (default true); `content_safety.blocked_extensions` (default `[]` allow-list of blocked-set suffixes).

---

## Directory structure (high level)

```
tests/
├── conftest.py
├── README.md
├── doc_todo_architecture.md          # gap analysis / aspirational 7-layer plan
├── doc_todo_multi_platform_ci_cd.md  # GitHub / GitLab / CodeCommit parity notes
├── mocks/openai.py                   # MockLLM + CALL_AGENT_PATCH_TARGETS
├── integration/
│   ├── test_golden_path.py
│   ├── test_edit_workflows.py
│   ├── test_run_task_cycle.py
│   └── ...
├── unit/
│   ├── test_edit_response_validator.py
│   ├── test_edit_mode_selector.py
│   ├── test_edit_payload.py
│   ├── test_proposal_builder.py
│   ├── test_config.py
│   ├── test_json_parser.py
│   ├── test_response_parser.py
│   ├── test_agent_schemas.py
│   ├── test_endpoint_manager.py
│   ├── test_rate_limiter.py
│   ├── test_edit_contracts.py
│   ├── test_path_normalization.py
│   ├── test_content_safety.py
│   └── ...
└── test_governed_editing.py          # root-level governed path tests
```

---

## Markers

```bash
pytest tests/ -m "not slow"    # default CI-friendly run
pytest tests/ -m slow          # concurrent worker / heavy apply contracts
```

Registered in `pytest.ini` (`slow`). A `serial` marker may land from the slow/serial-decouple work; until then, isolation is enforced via the batched runner / `SERIAL_PATHS` safety net in `utils/run_tests.sh`.

---

## Dependencies

From repo root `requirements-dev.txt` (Advana-friendly):

```text
pytest>=7.4.0,<9.1   # some hosts cap at 9.0.3
pytest-mock>=3.12.0
# optional: black, isort, ruff, mypy
```

Runtime remains minimal (`requirements.txt`).

## Moving toward TDD (beyond unit tests and coverage)

PrizmForge is largely **test-supported** today (tests follow implementation), not pure classic TDD.
The suite already goes past “unit + coverage %”: workflow integration, agent/LLM boundary mocks,
and contract/snapshot checks. Coverage is a **signal**, not the definition of quality.

### What the current framework accomplishes

| Layer | Where | Role |
|-------|--------|------|
| **Unit** | `tests/unit/` | Validators, config, parsers, schemas, endpoints, content safety, symbol index, CLI pieces |
| **Integration / workflow** | `tests/integration/`, cycle / edit workflow tests | Governed edit path: modes → payload → proposal → apply/materialize-style outcomes |
| **Agent / LLM boundary** | `MockLLM`, `llm.test_mode`, `mock_responses` queues | Agent JSON and multi-turn behavior **without live models** |
| **Contracts / snapshots** | Prompt snapshots, edit contracts, table fuzz | Schema and prompt regression guards |
| **Gates** | Fast / full / slow / live + ruff | Cheap inner loop vs heavier paths; live API is optional and non-merge |

**Not primary today:** Gherkin BDD, formal ATDD tooling, UI component tests, browser E2E, multi-hour live unattended as CI.

### Process guidance

- Fast gate = inner unit + tight contracts.
- Slow = concurrent workers + optional full mock unattended.
- Live model smoke stays optional and non-blocking for merge.
- New features: prefer **outer failing test first**, then inner units.
- When generating tests with an agent: inject focal signatures, fixture inventory, and forbidden hollow patterns; fill bodies inside a fixed skeleton; reject soft asserts in post-process.

Related: repo-level **RMF / RAISE / STIG** expectations live in [`COMPLIANCE.md`](../COMPLIANCE.md) (authorization artifacts are separate from the pytest suite).
