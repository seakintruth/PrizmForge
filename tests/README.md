# PrizmForge Test Suite

Deterministic tests for governed multi-agent editing. **No network required** for the default suite. Designed for Advana / SageMaker environments (pytest + pytest-mock + stdlib mocks).

> **Architecture, gap analysis, and multi-platform strategy** live in [`LLM_CONTEXT.md`](LLM_CONTEXT.md).
> This README is the operational entry point only.

## Quick start

```bash
# From repo root (prefer project .venv)
./utils/setup.sh && source .venv/bin/activate   # or .venv\\Scripts\\activate on Windows

# Preferred runners (resolve .venv automatically)
./utils/run_tests.sh --normal --batched -j 2    # merge gate (~5s on typical hosts)
./utils/run_tests.sh --full --batched -j 2      # includes slow
./utils/run_tests.sh --quick                    # curated smoke subset

# Direct pytest (markers only; no batch isolation matrix)
pytest tests/ -m "not slow and not serial" -q
pytest tests/ -m "serial and not slow" -q -n 0
```

**Without pytest** (ultra-minimal image):

```bash
python -m utils.run_critical_tests
```

**Optional real-model smoke** (skips without API keys / network):

```bash
python -m utils.smoke_real_model
```

**Duration rebalance** (after a full batched run):

```bash
./utils/run_tests.sh --full --batched -j 2
python utils/analyze_test_durations.py
```

---

## Markers (orthogonal axes)

Registered in `pytest.ini`. **Do not conflate them.**

| Marker | Meaning | Scheduling |
|--------|---------|------------|
| `@pytest.mark.slow` | Long-running (measured duration gate) | Excluded from `--normal`; runs under `--full` / `--only-slow` |
| `@pytest.mark.serial` | Isolation required (shared pool/DB/process state) | Always `-j 1`; still runs under `--normal` when **not** slow |

A test may be any combination:

| Combination | Batch (`--batched`) | In `--normal`? |
|-------------|---------------------|----------------|
| neither | `unit` / `integration` / `root` at `-j N` | yes |
| `serial` only | `serial` at `-j 1` | yes |
| `slow` only | `slow-parallel` at `-j N` | no |
| `slow` + `serial` | `slow-serial` at `-j 1` | no |

**Guidance**

- Mark **slow** from measured call time (promote ≥ ~2s; demote < ~0.5–1s). Prefer per-method markers over class-level when a class mixes fast helpers with pool start/stop.
- Mark **serial** when the test uses process-global pools, shared sqlite without full isolation, or must not share a worker with peers.
- `utils/run_tests.sh` still has a short `SERIAL_PATHS` safety net for modules not yet annotated; prefer markers and delete path entries as they land.

```bash
# Examples
pytest tests/ -m "not slow" -q                  # normal gate (may still mix serial under xdist if not batched)
./utils/run_tests.sh --normal --batched -j 2    # preferred: serial isolated at -j 1
./utils/run_tests.sh --full --batched -j 2      # + slow-parallel + slow-serial
./utils/run_tests.sh --batch slow-serial -j 1
```

---

## Gates

| Gate | Command | Intent |
|------|---------|--------|
| **Quick** | `./utils/run_tests.sh --quick` | Curated smoke subset |
| **Normal** | `./utils/run_tests.sh --normal --batched -j 2` | Merge / GHA — all non-slow (serial-but-fast included) |
| **Full** | `./utils/run_tests.sh --full --batched -j 2` | Complete matrix including slow |
| **Only slow** | `./utils/run_tests.sh --only-slow --batched -j 2` | Duration / pool stress only |
| **Live** | `python -m utils.smoke_real_model` | Optional real API (not a merge gate) |
| **Lint** | `ruff check .` and `ruff format --check .` | GHA `code-quality` job |

Per-batch logs and duration JSON land under `.PrizmForge/reports/`:

- `pytest-batch-<name>-<stamp>.log`
- `test-durations-<name>-<stamp>.json`
- `pytest-full-summary-<stamp>.txt`
- `test-durations-latest.json` (merged view for `analyze_test_durations.py`)

The runner writes each batch log by redirect-then-cat (not `tee`) so failures are preserved under Git Bash / MSYS.

### MockLLM import sites

`call_agent` is patched at all entries in `tests.mocks.openai.CALL_AGENT_PATCH_TARGETS`.
New modules that `from agents.base import call_agent` must call `register_call_agent_patch_target(...)`.

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

Path containment remains covered by `test_path_normalization.py` (writer). Edit op parse/apply matrix lives in `test_edit_contracts.py` (fast; not slow).

---

## Production hardening scope

Automated tests cover: orchestrator routing, backlog override, multi-turn cycle, reviewer reject, background pool lifecycle, RC optimizer shapes, HTTP 401/429 shapes, governed edit pipeline, **binary content rejection** (MSI/PE/OLE — not text scripts), and the high-priority pure modules above.

**Out of CI scope:** real-model quality, multi-hour unattended (see soak runbooks under `.PrizmForge/reports/` when present).

## Philosophy (operational)

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

Fixtures (see `conftest.py`): `mock_llm`, `mock_llm_patched`, `mock_openai_chat`, `temp_db`, `mock_minimal_config`, `isolated_project`, `_isolate_prizmforge_workspace` (autouse).

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
├── README.md                 # this file — operational commands & rules
├── LLM_CONTEXT.md            # durable architecture, gaps, multi-platform strategy
├── mocks/openai.py           # MockLLM + CALL_AGENT_PATCH_TARGETS
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
│   ├── test_parallel_workers.py   # module serial; start/stop methods slow
│   ├── test_worker_lifecycle.py   # module serial; start/stop methods slow
│   ├── test_edit_contracts.py
│   ├── test_path_normalization.py
│   ├── test_content_safety.py
│   └── ...
└── test_governed_editing.py  # root-level governed path tests (serial)
```

---

## Dependencies

From repo root `requirements-dev.txt` (Advana-friendly floors):

```text
pytest>=9.0.3          # some hosts cannot go above 9.0.3; CI may use newer
pytest-mock>=3.12.0
pytest-xdist
pytest-timeout
# optional: black>=24.4.2, isort>=7.0.0, ruff, mypy
```

Runtime remains minimal (`requirements.txt`).

## Moving toward TDD (beyond unit tests and coverage)

PrizmForge is largely **test-supported** today (tests follow implementation), not pure classic TDD.
The suite already goes past "unit + coverage %": workflow integration, agent/LLM boundary mocks, and contract/snapshot checks. Coverage is a **signal**, not the definition of quality.

### What the current framework accomplishes

| Layer | Where | Role |
|-------|--------|------|
| **Unit** | `tests/unit/` | Validators, config, parsers, schemas, endpoints, content safety, symbol index, CLI pieces |
| **Integration / workflow** | `tests/integration/`, cycle / edit workflow tests | Governed edit path: modes → payload → proposal → apply/materialize-style outcomes |
| **Agent / LLM boundary** | `MockLLM`, `llm.test_mode`, `mock_responses` queues | Agent JSON and multi-turn behavior **without live models** |
| **Contracts / snapshots** | Prompt snapshots, edit contracts, table fuzz | Schema and prompt regression guards |
| **Gates** | Quick / normal / full / only-slow / live + ruff | Cheap inner loop vs heavier paths; live API is optional and non-merge |

**Not primary today:** Gherkin BDD, formal ATDD tooling, UI component tests, browser E2E, multi-hour live unattended as CI.

### Process guidance

- Normal batched gate = inner unit + serial-but-fast + tight contracts (~5s).
- Slow = pool lifecycle / RC / multi-turn / unattended mock stress (`--full`).
- Live model smoke stays optional and non-blocking for merge.
- New features: prefer **outer failing test first**, then inner units.
- When generating tests with an agent: inject focal signatures, fixture inventory, and forbidden hollow patterns; fill bodies inside a fixed skeleton; reject soft asserts in post-process.

Related: repo-level **RMF / RAISE / STIG** expectations live in [`COMPLIANCE.md`](../docs/COMPLIANCE.md) (authorization artifacts are separate from the pytest suite).
