# PrizmForge Test Suite

Deterministic tests for governed multi-agent editing. **No network required** for the default suite. Designed for Advana / SageMaker environments (pytest + pytest-mock + stdlib mocks).

## Quick start

```bash
# From repo root
pip install -r requirements-dev.txt   # pytest, pytest-mock (+ optional black/flake8)

pytest tests/ -m "not slow" -q        # full CI-friendly suite
pytest tests/ -v                      # verbose
bash utils/run_fast_tests.sh          # inner-loop fast gate
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

Last full run (reference): **274+ passed**, 2 deselected (`@pytest.mark.slow`).

---

## Production hardening scope

Automated tests cover: orchestrator routing, backlog override, multi-turn cycle, reviewer reject,
background pool lifecycle, RC optimizer shapes, HTTP 401/429 shapes, governed edit pipeline,
**binary content rejection** (MSI/PE/OLE — not text scripts).

**Out of CI scope:** real-model quality, multi-hour unattended (see `report/soak_runbook.md`).

## Gates (production hardening)

| Gate | Command | Intent |
|------|---------|--------|
| **Fast** | `bash utils/run_fast_tests.sh` | Edit contracts, golden path, cycle, events/undo, hardening, mocks |
| **Full** | `pytest tests/ -m "not slow" -q` | Merge / Advana CI |
| **Slow** | `pytest tests/ -m slow` | Concurrent worker stress |
| **Live** | `python -m utils.smoke_real_model` | Optional real API (not a merge gate) |

### MockLLM import sites

`call_agent` is patched at all entries in `tests.mocks.openai.CALL_AGENT_PATCH_TARGETS`.
New modules that `from agents.base import call_agent` must call `register_call_agent_patch_target(...)`.

## Philosophy

1. **Mock LLMs by default** — `MockLLM` / `mock_openai_chat` (stdlib `unittest.mock`; no `responses` package).
2. **Real sqlite + temp filesystem** for file-editing paths.
3. **Assert outcomes** (file content, proposal status, counters) — not just "no exception."
4. **Zero new runtime deps** — tests use pytest + pytest-mock from the Advana-approved set.
5. **More in-repo code > exotic test packages** (no Hypothesis required; hand-rolled fuzz tables instead).

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

Fixtures (see `conftest.py`): `mock_llm`, `mock_llm_patched`, `mock_openai_chat`, `temp_db`, `mock_minimal_config`.

---

## Content safety (binary rejection)

`core/content_safety.py` is covered by `tests/unit/test_content_safety.py`.

| Allowed | Blocked |
|---------|---------|
| Text source (`.py`, `.ps1`, `.bat`, `.cmd`, `.js`, …) | PE/`MZ`, ELF, OLE/CFB (MSI), Mach-O magic |
| Normal UTF-8 source | NUL bytes / high non-text ratio |
| | Paths that are binary formats only (`.msi`, `.exe`, `.dll`, …) |

Text scripting languages are **not** blocked by extension. Only **binary** payloads and binary package/executable extensions.

Config: `content_safety.disallow_binary_content` (default true); `content_safety.blocked_extensions` (default `[]` allow-list of blocked-set suffixes).

---

## Directory structure (high level)

```
tests/
├── conftest.py
├── mocks/openai.py              # MockLLM + CALL_AGENT_PATCH_TARGETS
├── integration/
│   ├── test_golden_path.py
│   ├── test_edit_workflows.py
│   ├── test_run_task_cycle.py   # multi-turn + REJECT
│   └── test_file_editing_pipeline.py
├── unit/
│   ├── test_edit_contracts.py
│   ├── test_content_safety.py   # binary / MSI rejection
│   ├── test_backlog_override.py
│   ├── test_orchestrator_decisions.py
│   ├── test_events_undo.py
│   ├── test_endpoint_failures.py
│   ├── test_hardening.py
│   └── ...
└── README.md
```

---

## Markers

```bash
pytest tests/ -m "not slow"    # default CI-friendly run
pytest tests/ -m slow          # concurrent worker stress only
```

Registered in `pytest.ini` (`slow`).

---

## Dependencies

From repo root `requirements-dev.txt` (Advana-friendly):

```text
pytest>=7.4.0
pytest-mock>=3.12.0
# optional: black, flake8
```

Runtime remains `requests` only (`requirements.txt`).

## Moving toward TDD (beyond unit tests and coverage)

PrizmForge is largely **test-supported** today (tests follow implementation), not pure classic TDD.
The suite already goes past “unit + coverage %”: workflow integration, agent/LLM boundary mocks,
and contract/snapshot checks. Coverage is a **signal**, not the definition of quality.

### What the current framework accomplishes

| Layer | Where | Role |
|-------|--------|------|
| **Unit** | `tests/unit/` | Isolates validators, content safety, symbol index, CLI pieces, HTTP shapes, backlog rules, LLM test mode |
| **Integration / workflow** | `tests/integration/`, cycle / edit workflow tests | Governed edit path: modes → payload → proposal → apply/materialize-style outcomes |
| **Agent / LLM boundary** | `MockLLM`, `llm.test_mode`, `mock_responses` queues | Agent JSON and multi-turn behavior **without live models** |
| **Contracts / snapshots** | Prompt snapshots, edit contracts, table fuzz | Schema and prompt regression guards |
| **Gates** | Fast / full / slow / live | Cheap inner loop vs heavier paths; live API is optional and non-merge |

**Not primary today:** Gherkin BDD, formal ATDD tooling, UI component tests, browser E2E, multi-hour live unattended as CI.

### Models that help *this* repo

Prioritized for multi-agent, governed edits, config-only unattended, Advana limits:

1. **Double-loop TDD (preferred)** — Outer: failing acceptance/integration test for a workflow outcome (e.g. seed task materializes files under `test_mode`, MSI `full_replace` rejected, unattended preflight exit). Inner: classic red–green–refactor on pure modules (`content_safety`, `symbol_index`, preflight, mode selection).
2. **Classic TDD (inner loop)** — For **new** pure logic only; less natural for the whole task-runner until thinner.
3. **Integration-first outer tests** — Treat edit pipeline + orchestrator decisions as the product API; write those tests before changing mutation/reviewer/materialize behavior.
4. **API / contract TDD** — Orchestrator JSON, developer `EditPayload`, reviewer decision, MockLLM queues are the “service API.”
5. **ATDD as exit criteria** — Encode PO/dev/tester criteria in pytest names and asserts (exit codes, files on disk, no stdin); no extra ATDD product required.
6. **BDD (Cucumber)** — Optional later for stakeholder-readable scenarios; prefer narrative pytest names for now.
7. **Component testing** — Low priority (no UI component tree as the core product).
8. **System / E2E** — Few, slow, headless: unattended + `llm.test_mode` + fixed `mock_responses` (not browser packs).

### Target layout (more than unit + coverage)

| Layer | Example |
|-------|---------|
| Inner unit | Content safety, symbol upsert, preflight errors |
| Agent contract | Developer must emit `full_replace` / `create_file` under mock queues |
| Workflow integration | Proposal → approve → apply → files under `project_directory` |
| Acceptance (outer) | Unattended seed task produces expected app files; binary payloads rejected |
| Coverage | Guidance on **changed** modules; do not chase raw % on task_runner first |

### Process guidance

- Fast gate = inner unit + tight contracts.
- Slow = concurrent workers + optional full mock unattended.
- Live model smoke stays optional and non-blocking for merge.
- New features: prefer **outer failing test first**, then inner units.

Related: repo-level **RMF / RAISE / STIG** expectations live in [`COMPLIANCE.md`](../COMPLIANCE.md) (authorization artifacts are separate from the pytest suite).
