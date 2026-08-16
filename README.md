![PrizmForge Logo](assets/logos/logo.png)

# PrizmForge

**Autonomous multi-agent software engineering system with governed self-editing.**

PrizmForge enables AI agents to safely modify a project repository, even a copy of their own codebase through a structured proposal and review process, while maintaining full auditability and human oversight.

## Core Philosophy

- **Governed mutation**: All code changes go through a proposal → review → materialization pipeline with line-level GUID concurrency control.
- **Parallel analysis**: Background agents provide continuous feedback without mutation rights.
- **Hermetic testing**: Zero-network default suite with MockLLM; Advana / air-gapped friendly.

## Quick Start

```bash
# 1. Bootstrap a local virtual environment and install dependencies
./utils/setup.sh

# 2. Activate the environment
source .venv/bin/activate          # Linux / macOS
# .venv\Scripts\activate           # Windows

# 3. Copy configuration templates (if needed)
cp example_config.json config.json
cp example_api_key.json api_key.json   # add real keys, or use llm.test_mode

# 4. Run
python main.py
```

`utils/setup.sh` creates (or reuses) a project-root `.venv` and installs both runtime (`requirements.txt`) and development (`requirements-dev.txt`) dependencies. Use `--force` to recreate the venv or `--python /path/to/python` to select a specific interpreter.

For detailed configuration options see **[CONFIGURATION.md](CONFIGURATION.md)**.  
For the test suite see **[tests/README.md](tests/README.md)** (and the architectural context in **[tests/LLM_CONTEXT.md](tests/LLM_CONTEXT.md)**).

## Architecture

### System Architecture Diagram

(See repository assets for current diagrams.)

- **Mutation path** (sequential, governed): Developer → EditPayload → Proposal → Reviewer (Approve → Materialization | Deny with Comments → Developer)
- **Analysis path** (parallel): Background agents provide continuous feedback without mutation rights

## Dependencies

Designed for **Advana Nexus / SageMaker**-friendly installs (popular DS/DE packages only).

| File | Purpose |
|------|---------|
| `requirements.txt` | **Runtime only:** `requests>=2.31.0` |
| `requirements-dev.txt` | Tests: `pytest`, `pytest-mock`. Optional: `black`, `isort`, `ruff`, `mypy` |

```bash
# Preferred: one-command bootstrap (creates .venv + installs both files)
./utils/setup.sh

# Manual alternative
pip install -r requirements.txt          # runtime
pip install -r requirements-dev.txt      # development / CI
```

LLM calls in tests use a **stdlib MockLLM** (`tests/mocks/openai.py`) — no OpenAI SDK, no network.

The **CLI** (`python interactive.py` / `python main.py`) is the supported user interface.

## Testing

Full operational details, assertion rules, pure-suite inventory, and preferred runners live in **[tests/README.md](tests/README.md)**.  
Architectural context, gap analysis, and multi-platform notes live in **[tests/LLM_CONTEXT.md](tests/LLM_CONTEXT.md)**.

```bash
# Preferred CI / local normal gate
./utils/run_tests.sh --normal -j 4

# Full suite (host-aware)
./utils/run_tests.sh --full --batched

# Slow / concurrent worker stress
pytest tests/ -m slow -q

# Ultra-minimal host (no pytest)
python -m utils.run_critical_tests

# Optional real-model smoke (requires keys / network)
python -m utils.smoke_real_model
```

High-priority pure modules that gate the governed edit path are listed in `tests/README.md` (PR #67 coverage).

## Compliance & authorization

Program RMF / Navy RAISE / DISA ASD STIG-oriented requirements and artifact expectations: **[COMPLIANCE.md](COMPLIANCE.md)**.

## Export

```bash
python utils/export_project_zip.py
python utils/export_project_zip.py --skip-consolidate
```

Does **not** run tests. For the normal gate use `./utils/run_tests.sh --normal -j 4`.

## Configuration

See **[CONFIGURATION.md](CONFIGURATION.md)** for the full `config.json` schema.

Primary entrypoint is **`python main.py`** (mode comes from `config.json` → `cli_mode.mode`).  
Semi-attended sessions also accept typed commands (see help inside the session).

### First-time setup (detailed)

```bash
# Preferred bootstrap
./utils/setup.sh
source .venv/bin/activate

# Copy templates if needed
cp example_config.json config.json
cp example_api_key.json api_key.json
```

## CLI & utilities

```bash
python interactive.py
python main.py
python utils/export_project_zip.py
python utils/export_project_zip.py --skip-consolidate
python utils/export_project_zip.py --out /path/to/out.zip

# Tests (see tests/README.md for full details)
./utils/run_tests.sh --normal -j 4
pytest tests/ -m "not slow" -q
python -m utils.run_critical_tests
```

## Test mode

```bash
PRIZMFORGE_TEST_MODE=1 python main.py
```

Mock responses can be scripted under `llm.mock_responses` (string or list queue per agent). See `CONFIGURATION.md`.

## Project Status

PrizmForge is under active development. The governed editing system represents the current production methodology for safe autonomous modifications.

For detailed architecture, see **[architecture.md](architecture.md)**.

## License

MIT  
See repository for license information.
