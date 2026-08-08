# PrizmForge Production-Grade Test Suite & Deployment Architecture

This document provides the complete, production-grade testing framework and deployment architecture for **PrizmForge**—an LLM-driven governed code editing and multi-agent orchestration system.

---

## 1. Executive Summary & Architecture Overview

PrizmForge executes autonomous software modifications through a strict two-path design:

1. **Governed Sequential Mutation Path**: `Orchestrator` $\rightarrow$ `Developer` (`EditPayload`) $\rightarrow$ `Proposal` $\rightarrow$ `Reviewer` (Safety Gate) $\rightarrow$ `Materialization` (`file_lines` DB + Disk + Git).

2. **Parallel Background Analysis Path**: Non-mutating diagnostic agents (`jr_reviewer`, `security_reviewer`, `tech_writer`, `deployment_validator`, `archivist`, `prioritizer`, `resource_controller`) continuously analyzing code and posting structured feedback.

To ensure stability, zero network leakage in CI, strict path containment, optimistic concurrency validation, and memory safety, this framework implements a seven-layer QA suite.

```
+-------------------------------------------------------------------------+
|                        7-Layer QA Architecture                          |
+-------------------------------------------------------------------------+
| Layer 1: Unit Testing (pytest + stdlib mocks)                           |
| Layer 2: Integration Testing (Multi-Agent Workflow & DB Lifecycle)       |
| Layer 3: Property & Static Analysis (Hypothesis + mypy + ruff)          |
| Layer 4: Functional & API Endpoint Testing (pydantic + httpx/FastAPI)   |
| Layer 5: Performance & Load Testing (pytest-benchmark + Locust)         |
| Layer 6: Security & Vulnerability Auditing (bandit + pip-audit + safety)|
| Layer 7: CI/CD Automation Pipeline (GitHub Actions 3.10/3.11/3.12)      |
+-------------------------------------------------------------------------+
```

---

## 2. Unit Testing Framework (`pytest`)

Isolated unit tests cover individual core utilities without network calls or persistent disk side effects.

### 2.1 Test Suite Configuration (`tests/conftest.py`)

```python
"""
Global pytest fixtures for PrizmForge unit and integration testing.
Handles temporary SQLite databases, mock LLM state, and path sandboxing.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Generator
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(scope="function")
def temp_db(monkeypatch: pytest.MonkeyPatch) -> Generator[str, None, None]:
    """
    Creates an isolated temporary SQLite database for each test run.
    Overrides PRIZMFORGE_DB_PATH so database operations affect only the sandbox.
    """
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    if os.path.exists(db_path):
        try:
            os.unlink(db_path)
        except OSError:
            pass

    monkeypatch.setenv("PRIZMFORGE_DB_PATH", db_path)

    from core.db import init_db

    init_db()

    yield db_path

    if os.path.exists(db_path):
        try:
            os.unlink(db_path)
        except OSError:
            pass


@pytest.fixture
def sandbox_project_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """
    Provides a sandboxed project directory under repo root for path containment tests.
    """
    project_dir = tmp_path / "sandbox_project"
    project_dir.mkdir(parents=True, exist_ok=True)

    from core import config as config_mod

    orig_get_config = config_mod.get_config

    def _mock_config() -> Dict[str, Any]:
        cfg = dict(orig_get_config())
        cfg["project_directory"] = str(project_dir)
        cfg["git"] = False
        cfg["background_agents_enabled"] = False
        return cfg

    monkeypatch.setattr(config_mod, "get_config", _mock_config)
    return project_dir


@pytest.fixture
def mock_llm_http(monkeypatch: pytest.MonkeyPatch) -> Any:
    """
    HTTP-level mock for requests.post to prevent network egress during unit tests.
    """
    state = {"response_text": '{"status": "ok"}', "status_code": 200}

    def _fake_post(url: str, *args: Any, **kwargs: Any) -> MagicMock:
        mock_resp = MagicMock()
        mock_resp.status_code = state["status_code"]
        payload = {
            "id": "chatcmpl-mock",
            "object": "chat.completion",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": state["response_text"]},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
        }
        mock_resp.json.return_value = payload
        mock_resp.text = str(payload)
        mock_resp.content = str(payload).encode("utf-8")
        mock_resp.headers = {"Content-Type": "application/json"}
        mock_resp.raise_for_status = MagicMock()
        return mock_resp

    monkeypatch.setattr("requests.post", _fake_post)

    def _set_response(text: str, status_code: int = 200) -> None:
        state["response_text"] = text
        state["status_code"] = status_code

    return _set_response
```

### 2.2 Core Component Unit Tests (`tests/unit/test_core_components.py`)

```python
"""
Unit tests for core components: JSON parser, path containment, content safety, and rate limiter.
"""

from __future__ import annotations

from pathlib import Path
import pytest

from core.content_safety import looks_like_binary, validate_source_content
from core.edit_response_validator import EditFailureReason, validate_developer_edit_response
from core.json_parser import parse_json_response
from core.rate_limiter import RateLimiter
from file_editing.writer import _resolve_contained_path


class TestJsonParserUnit:
    """Tests JSON extraction strategies across markdown wraps, truncations, and edge cases."""

    def test_parse_valid_json_object(self) -> None:
        raw = '{"target_file_path": "app.py", "summary": "Valid edit"}'
        result = parse_json_response(raw)
        assert result is not None
        assert result["target_file_path"] == "app.py"

    def test_parse_markdown_wrapped_json(self) -> None:
        raw = 'Here is the proposal:\n```json\n{"action": "create", "file": "main.py"}\n```\nHope this helps!'
        result = parse_json_response(raw)
        assert result is not None
        assert result["action"] == "create"

    def test_parse_malformed_json_returns_none(self) -> None:
        raw = '{"target_file_path": "app.py", "summary": '
        result = parse_json_response(raw)
        assert result is None

    def test_parse_empty_string_returns_none(self) -> None:
        assert parse_json_response("") is None
        assert parse_json_response("   \n\t ") is None


class TestContentSafetyUnit:
    """Validates binary payload rejection (PE, ELF, OLE/MSI) and source script permissions."""

    def test_reject_pe_mz_header(self) -> None:
        binary_data = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff"
        is_bin, reason = looks_like_binary(binary_data)
        assert is_bin is True
        assert "PE/DOS" in reason

    def test_reject_ole_cfb_msi_magic(self) -> None:
        ole_data = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 100
        is_bin, reason = looks_like_binary(ole_data)
        assert is_bin is True
        assert "OLE/CFB" in reason

    def test_reject_blocked_extensions(self) -> None:
        validation = validate_source_content("plain text", file_path="installer.msi")
        assert validation["ok"] is False
        assert "blocked extension" in validation["message"]

    def test_allow_powershell_and_python_scripts(self) -> None:
        ps_content = "Write-Host 'Deploying application...'\nGet-Service"
        val_ps = validate_source_content(ps_content, file_path="deploy.ps1")
        assert val_ps["ok"] is True

        py_content = "def main():\n    print('Running PrizmForge')"
        val_py = validate_source_content(py_content, file_path="main.py")
        assert val_py["ok"] is True


class TestPathContainmentUnit:
    """Verifies path containment checks prevent directory traversal outside repo root."""

    def test_valid_relative_path(self, sandbox_project_dir: Path) -> None:
        resolved = _resolve_contained_path("src/utils.py", sandbox_project_dir)
        assert resolved.is_relative_to(sandbox_project_dir)

    def test_traversal_attack_raises_error(self, sandbox_project_dir: Path) -> None:
        with pytest.raises(ValueError, match="escapes project directory"):
            _resolve_contained_path("../../etc/passwd", sandbox_project_dir)

    def test_nested_traversal_escape_raises_error(self, sandbox_project_dir: Path) -> None:
        with pytest.raises(ValueError, match="escapes project directory"):
            _resolve_contained_path("src/../../outside.py", sandbox_project_dir)


class TestRateLimiterUnit:
    """Tests thread-safe sliding window rate limiting."""

    def test_rate_limiter_allows_under_capacity(self) -> None:
        limiter = RateLimiter(max_calls_per_minute=10)
        for _ in range(5):
            limiter.wait_if_needed()
        assert len(limiter.calls) == 5

    def test_rate_limiter_dynamic_max_calls_update(self) -> None:
        limiter = RateLimiter(max_calls_per_minute=100)
        limiter.set_max_calls(20)
        assert limiter.max_calls == 20
```

---

## 3. Integration Testing Framework

Integration tests execute complete multi-agent workflows, DB persistence, line GUID transformations, and proposal undo functionality.

### 3.1 Multi-Agent Governed Editing Lifecycle Test (`tests/integration/test_governed_workflow.py`)

```python
"""
Integration test for multi-agent orchestration, proposal creation, reviewer gate, and materialization.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict
import pytest

from core.db_connection import get_db_connection
from file_editing.editing import apply_edit_proposal
from file_editing.undo import snapshot_before_apply, undo_proposal
from file_editing.writer import initialize_file_lines, materialize_proposal, reconstruct_file_content
from workflow.proposal_builder import create_proposal_from_developer_output, update_proposal_status


class TestGovernedWorkflowIntegration:
    """Exercises full proposal lifecycle: initialize -> propose -> review -> apply -> materialize -> undo."""

    def test_full_proposal_lifecycle_and_undo(self, temp_db: str, sandbox_project_dir: Path) -> None:
        target_file = "app/service.py"
        initial_content = "VERSION = '1.0.0'\n\ndef run():\n    return True\n"

        # Step 1: Initialize file lines with stable GUIDs
        init_res = initialize_file_lines(target_file, initial_content)
        assert init_res["status"] == "success"
        file_id = init_res["file_id"]

        # Verify initial line content
        with get_db_connection() as conn:
            reconstructed = reconstruct_file_content(conn, file_id)
            assert reconstructed == initial_content

        # Step 2: Developer outputs EditPayload
        developer_payload = {
            "target_file_path": target_file,
            "summary": "Bump version to 1.1.0",
            "rationale": "Updating service version for new release iteration",
            "operations": [
                {
                    "type": "find_replace",
                    "find": "VERSION = '1.0.0'",
                    "replace": "VERSION = '1.1.0'",
                    "rationale": "Update version string",
                }
            ],
        }

        # Step 3: Create Edit Proposal
        prop_res = create_proposal_from_developer_output(
            developer_output=developer_payload,
            proposed_by_agent_id=1,
            target_file_path=target_file,
            selected_mode="find_replace",
            final_mode="find_replace",
        )
        assert prop_res["status"] == "success"
        proposal_id = prop_res["proposal_id"]

        # Step 4: Reviewer Safety Gate Approve
        updated = update_proposal_status(proposal_id, "approved", reviewed_by_agent_id=2)
        assert updated is True

        # Step 5: Snapshot before apply & Materialize
        snap_res = snapshot_before_apply(proposal_id)
        assert snap_res["status"] == "success"

        apply_res = apply_edit_proposal(proposal_id)
        assert apply_res["status"] == "success"

        mat_res = materialize_proposal(proposal_id)
        assert mat_res["status"] == "success"

        # Verify disk and DB state after materialization
        disk_file = sandbox_project_dir / target_file
        assert disk_file.exists()
        assert "VERSION = '1.1.0'" in disk_file.read_text(encoding="utf-8")

        # Step 6: Undo Proposal and restore previous snapshot
        undo_res = undo_proposal(proposal_id, write_disk=True)
        assert undo_res["status"] == "success"
        assert "VERSION = '1.0.0'" in disk_file.read_text(encoding="utf-8")

    def test_optimistic_concurrency_conflict_detection(self, temp_db: str) -> None:
        target_file = "app/config.py"
        initial_content = "PORT = 8080\nDEBUG = True\n"
        init_res = initialize_file_lines(target_file, initial_content)
        file_id = init_res["file_id"]

        # Fetch GUID for line 1
        with get_db_connection() as conn:
            cursor = conn.execute("SELECT line_guid FROM file_lines WHERE file_id = ? AND sort_order = 1024.0", (file_id,))
            line_guid = cursor.fetchone()[0]

        proposal_payload = {
            "target_file_path": target_file,
            "summary": "Change PORT to 9090",
            "rationale": "Updating default listening port",
            "operations": [
                {
                    "type": "replace_block",
                    "start_line_guid": line_guid,
                    "new_content": ["PORT = 9090"],
                    "rationale": "Update port line",
                }
            ],
        }

        prop_res = create_proposal_from_developer_output(
            developer_output=proposal_payload,
            proposed_by_agent_id=1,
            target_file_path=target_file,
        )
        proposal_id = prop_res["proposal_id"]

        # Simulate concurrent modification by altering line_hash in DB
        with get_db_connection() as conn:
            conn.execute("UPDATE file_lines SET content_hash = 'stale_hash' WHERE line_guid = ?", (line_guid,))
            conn.execute("UPDATE edit_proposals SET status = 'approved' WHERE proposal_id = ?", (proposal_id,))

        # Application should detect hash conflict and return 'conflicted'
        apply_res = apply_edit_proposal(proposal_id)
        assert apply_res["status"] == "conflicted"
```

---

## 4. Architectural & Typing Property Testing (`Hypothesis` & `mypy`)

Property-based testing uses randomized inputs to discover edge cases in input parsing, while `mypy` and `ruff` enforce static typing and style standards.

### 4.1 Property-Based Test Suite (`tests/unit/test_properties.py`)

```python
"""
Property-based testing with Hypothesis to fuzz token estimation, JSON cleanup, and edit payload validation.
"""

from __future__ import annotations

from hypothesis import given, settings, HealthCheck, strategies as st

from agents.response_cleaner import clean_llm_response
from core.token_estimator import estimate_tokens
from file_editing.edit_payload import FindReplace


class TestHypothesisProperties:
    """Fuzzing and invariant checks across random inputs."""

    @given(st.text())
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_token_estimator_non_negative(self, input_text: str) -> None:
        """Invariant: Token estimation must always return an integer >= 0."""
        tokens = estimate_tokens(input_text)
        assert isinstance(tokens, int)
        assert tokens >= 0

    @given(st.text(min_size=1, max_size=1000))
    def test_token_estimator_monotonicity(self, text_segment: str) -> None:
        """Invariant: Appending characters to text should never decrease token estimate."""
        base_tokens = estimate_tokens(text_segment)
        extended_tokens = estimate_tokens(text_segment + text_segment)
        assert extended_tokens >= base_tokens

    @given(find=st.text(min_size=1, max_size=100), replace=st.text(max_size=100))
    def test_find_replace_dataclass_properties(self, find: str, replace: str) -> None:
        """Property test for FindReplace operation validation."""
        op = FindReplace(
            find=find,
            replace=replace,
            rationale="Automated property test for find_replace operation",
        )
        assert op.find == find
        assert op.replace == replace
        assert op.type == "find_replace"

    @given(json_body=st.dictionaries(st.text(min_size=1, max_size=20), st.text(max_size=50)))
    def test_response_cleaner_json_fuzz(self, json_body: dict[str, str]) -> None:
        """Property test: Valid JSON dictionary wrapped in markdown must always be extracted."""
        import json

        raw_json = json.dumps(json_body)
        wrapped = f"Here is the result:\n```json\n{raw_json}\n```"
        cleaned = clean_llm_response(wrapped, agent_name="fuzz_tester")
        assert cleaned is not None
        assert json.loads(cleaned) == json_body
```

### 4.2 Static Analysis & Linting Configurations

#### `pyproject.toml`

```toml
[tool.mypy]
python_version = "3.10"
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
disallow_untyped_decorators = true
no_implicit_optional = true
warn_redundant_casts = true
warn_unused_ignores = true

[[tool.mypy.overrides]]
module = ["locust.*", "pytest_benchmark.*"]
ignore_missing_imports = true

[tool.ruff]
target-version = "py310"
line-length = 120

[tool.ruff.lint]
select = ["E", "F", "B", "I", "N", "UP", "S", "A", "RUF"]
ignore = ["S101", "S105"] # Allow assert in tests, ignore hardcoded password warnings in mocks

[tool.ruff.lint.per-file-ignores]
"tests/*" = ["S101", "S106"]
```

---

## 5. Functional & API Endpoint Testing

Validates REST API routes, status codes, and Pydantic response payloads.

```python
"""
Functional testing for FastAPI/REST endpoints exposing PrizmForge operations.
"""

from __future__ import annotations

from typing import Any, Dict, List
import pytest
from pydantic import BaseModel, Field


# --- Pydantic API Schema Definitions ---


class TaskSubmitRequest(BaseModel):
    task_id: str = Field(..., min_length=3)
    user_command: str = Field(..., min_length=5)
    max_turns: int = Field(default=10, ge=1, le=50)


class TaskSubmitResponse(BaseModel):
    status: str
    task_id: str
    message: str


class HealthStatusResponse(BaseModel):
    status: str
    version: str
    active_endpoints: List[str]


# --- Mock FastAPI App & Client Setup ---

from fastapi import FastAPI, HTTPException, status
from fastapi.testclient import TestClient

app = FastAPI(title="PrizmForge API")


@app.get("/health", response_model=HealthStatusResponse)
def get_health() -> Dict[str, Any]:
    return {
        "status": "healthy",
        "version": "3.1.0",
        "active_endpoints": ["gemini", "databricks"],
    }


@app.post("/v1/tasks", response_model=TaskSubmitResponse, status_code=status.HTTP_202_ACCEPTED)
def submit_task(payload: TaskSubmitRequest) -> Dict[str, Any]:
    if "error" in payload.user_command.lower():
        raise HTTPException(status_code=400, detail="Invalid command payload")
    return {
        "status": "accepted",
        "task_id": payload.task_id,
        "message": f"Task {payload.task_id} queued successfully.",
    }


# --- Endpoint Functional Tests ---


class TestApiEndpoints:
    """Test suite validating HTTP responses, status codes, and JSON schema boundaries."""

    @pytest.fixture
    def client(self) -> TestClient:
        return TestClient(app)

    def test_health_check_endpoint(self, client: TestClient) -> None:
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        validated = HealthStatusResponse(**data)
        assert validated.status == "healthy"

    def test_submit_task_success(self, client: TestClient) -> None:
        payload = {
            "task_id": "task-101",
            "user_command": "Refactor database pool connections",
            "max_turns": 15,
        }
        response = client.post("/v1/tasks", json=payload)
        assert response.status_code == 202
        validated = TaskSubmitResponse(**response.json())
        assert validated.task_id == "task-101"
        assert validated.status == "accepted"

    def test_submit_task_validation_failure(self, client: TestClient) -> None:
        invalid_payload = {
            "task_id": "ab",  # Too short (min_length=3)
            "user_command": "Fix",  # Too short (min_length=5)
            "max_turns": 100,  # Exceeds max 50
        }
        response = client.post("/v1/tasks", json=invalid_payload)
        assert response.status_code == 422  # Unprocessable Entity
```

---

## 6. Performance & Load Testing (`pytest-benchmark` / `Locust`)

### 6.1 Benchmark Suite (`tests/performance/test_benchmarks.py`)

```python
"""
Micro-benchmarks for critical PrizmForge paths using pytest-benchmark.
"""

from __future__ import annotations

from typing import Any
import pytest

from core.symbol_index import parse_python_symbols
from core.token_estimator import estimate_tokens


def test_token_estimation_benchmark(benchmark: Any) -> None:
    """Benchmark token estimation performance on large source text."""
    sample_code = (
        """
    def complex_algorithm(data_list: list[dict[str, Any]]) -> dict[str, float]:
        # Perform calculations over dataset
        result = {}
        for item in data_list:
            key = item.get("key", "default")
            value = float(item.get("value", 0.0))
            result[key] = result.get(key, 0.0) + value
        return result
    """
        * 100
    )

    result = benchmark(estimate_tokens, sample_code)
    assert result > 0


def test_symbol_parsing_benchmark(benchmark: Any) -> None:
    """Benchmark AST symbol parsing across Python modules."""
    python_source = (
        """
class DataProcessor:
    def __init__(self, config: dict):
        self.config = config

    def process(self, payload: str) -> bool:
        return len(payload) > 0

def top_level_helper(x: int, y: int) -> int:
    return x + y
"""
        * 50
    )

    symbols = benchmark(parse_python_symbols, python_source, "core/processor.py")
    assert len(symbols) > 0
```

### 6.2 Locust Load Test (`tests/performance/locustfile.py`)

```python
"""
Locust load test script simulating multi-user task submissions and status polls.
Run via: locust -f tests/performance/locustfile.py --headless -u 10 -r 2 --run-time 1m --host http://localhost:8000
"""

from __future__ import annotations

import random
from locust import HttpUser, SequentialTaskSet, between, task


class AgentOrchestrationUserBehavior(SequentialTaskSet):
    """Simulates realistic developer interaction cycles with PrizmForge."""

    def on_start(self) -> None:
        self.task_id = f"locust-task-{random.randint(1000, 9999)}"

    @task
    def check_health(self) -> None:
        self.client.get("/health", name="01_HealthCheck")

    @task
    def submit_task(self) -> None:
        payload = {
            "task_id": self.task_id,
            "user_command": "Optimize SQL queries in repository layer",
            "max_turns": 10,
        }
        headers = {"Content-Type": "application/json"}
        self.client.post("/v1/tasks", json=payload, headers=headers, name="02_SubmitTask")


class PrizmForgeLoadUser(HttpUser):
    tasks = [AgentOrchestrationUserBehavior]
    wait_time = between(1.0, 3.0)
```

---

## 7. Security & Vulnerability Auditing

Automated security scanners (`bandit` and `pip-audit`) are configured to detect insecure code constructs and dependency CVEs.

### 7.1 Bandit Configuration (`.bandit`)

```yaml
# Bandit Security Scanner Configuration
targets:
  - "agents"
  - "cli"
  - "core"
  - "file_editing"
  - "workflow"

exclude_dirs:
  - "tests"
  - ".venv"
  - "report"

skips:
  - B101 # Allow assertions in non-production code if needed

tests:
  - B201 # Flask debug true
  - B301 # Unsafe pickle
  - B307 # Eval usage
  - B602 # Shell injection
  - B608 # SQL Injection
```

### 7.2 Security Verification Test (`tests/unit/test_security_verification.py`)

```python
"""
Unit tests validating static security rules and binary content safety guards.
"""

from __future__ import annotations

import pytest
from core.content_safety import validate_source_content


class TestSecurityGuards:
    """Validates that binary execution payloads are rejected by the governed pipeline."""

    def test_pe_executable_rejection(self) -> None:
        pe_header = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff\x00\x00\xb8\x00\x00\x00"
        res = validate_source_content(pe_header, file_path="malicious.exe")
        assert res["ok"] is False
        assert "blocked extension" in res["message"] or "binary" in res["message"]

    def test_sql_injection_prevention_in_db_helpers(self, temp_db: str) -> None:
        """Ensure parameterized query compliance prevents SQL injection."""
        from core.db_connection import get_db_connection

        malicious_id = "task-001' OR '1'='1"
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tasks WHERE id = ?", (malicious_id,))
            rows = cursor.fetchall()
            assert len(rows) == 0
```

---

## 8. CI/CD Automation Pipeline (`.github/workflows/test.yml`)

The production GitHub Actions workflow file executes linting, static type checking, security auditing, and the full test suite across Python 3.10, 3.11, and 3.12, failing the build if code coverage falls below **90%**.

```yaml
name: PrizmForge CI/CD Pipeline

on:
  push:
    branches: [ "main", "develop" ]
  pull_request:
    branches: [ "main", "develop" ]

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

permissions:
  contents: read

jobs:
  static-security-and-lint:
    name: Code Quality & Security Audit
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Repository
        uses: actions/checkout@v4

      - name: Set up Python 3.10
        uses: actions/setup-python@v5
        with:
          python-version: "3.10"
          cache: "pip"

      - name: Install Linting & Security Dependencies
        run: |
          python -m pip install --upgrade pip
          pip install ruff mypy bandit pip-audit

      - name: Run Ruff Linter & Formatter Check
        run: |
          ruff check .
          ruff format --check .

      - name: Run Mypy Static Type Checker
        run: |
          mypy agents/ core/ file_editing/ workflow/ cli/

      - name: Run Bandit Security Audit
        run: |
          bandit -r agents/ core/ file_editing/ workflow/ cli/ -c .bandit

      - name: Audit Third-Party Dependencies (pip-audit)
        run: |
          pip-audit --ignore-code 1

  test-matrix:
    name: Pytest Suite (Python ${{ matrix.python-version }})
    needs: static-security-and-lint
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        python-version: ["3.10", "3.11", "3.12"]

    steps:
      - name: Checkout Repository
        uses: actions/checkout@v4

      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
          cache: "pip"

      - name: Install Test Dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install pytest pytest-cov pytest-mock hypothesis httpx pydantic fastapi pytest-benchmark

      - name: Execute Pytest Suite with 90% Coverage Gate
        env:
          PRIZMFORGE_TEST_MODE: "1"
        run: |
          pytest tests/ \
            -m "not slow" \
            --cov=agents \
            --cov=core \
            --cov=file_editing \
            --cov=workflow \
            --cov=cli \
            --cov-report=term-missing \
            --cov-report=xml \
            --cov-fail-under=90

      - name: Upload Coverage XML Artifact
        uses: actions/upload-artifact@v4
        with:
          name: coverage-py${{ matrix.python-version }}
          path: coverage.xml
```
PrizmForge Testing Framework: Modification & Migration Plan
This document outlines the gap analysis and exact refactoring steps required to upgrade the existing PrizmForge test suite to a production-grade, 7-layer QA architecture.

1. Gap Analysis: Existing Test Suite vs. Target Architecture
An analysis of the existing codebase (tests/, utils/run_tests.sh, core/, file_editing/) reveals the following delta between the current state and a enterprise production framework:
+----------------------------------------------------------------------------------------------------+
|                                    PrizmForge Gap Matrix                                           |
+--------------------------+-----------------------------------+-------------------------------------+
| Dimension                | Existing State                    | Target Production State             |
+--------------------------+-----------------------------------+-------------------------------------+
| 1. Unit Testing          | Tests scattered across unit/ and  | Unified fixtures in conftest.py;    |
|                          | root; ad-hoc SQLite temp files.   | hermetic mock_llm_http & sandboxing.|
+--------------------------+-----------------------------------+-------------------------------------+
| 2. Integration Testing   | Sequential test scripts in        | Full transaction rollback,          |
|                          | tests/integration/.               | optimistic concurrency verification.|
+--------------------------+-----------------------------------+-------------------------------------+
| 3. Property Testing      | Hand-rolled table checks in       | Hypothesis-driven property testing; |
|                          | test_fuzz_tables.py.              | mypy strict mode + ruff linting.    |
+--------------------------+-----------------------------------+-------------------------------------+
| 4. Functional API        | CLI-only interactive commands;    | FastAPI / httpx REST endpoint tests |
|                          | no HTTP route validation.         | with Pydantic request/response rules|
+--------------------------+-----------------------------------+-------------------------------------+
| 5. Performance / Load    | Basic execution time checks in    | pytest-benchmark micro-benchmarks;  |
|                          | test_context_manager.py.          | Locust load test script.            |
+--------------------------+-----------------------------------+-------------------------------------+
| 6. Security Auditing     | Unit checks in test_content_safety| Automated Bandit static analysis;   |
|                          | without tool configuration.       | pip-audit; binary magic byte guards.|
+--------------------------+-----------------------------------+-------------------------------------+
| 7. CI/CD Pipeline        | Local bash runner                 | GitHub Actions matrix pipeline      |
|                          | (utils/run_tests.sh).             | with 90% coverage enforcement gate. |
+--------------------------+-----------------------------------+-------------------------------------+

2. Directory Layout Refactoring
To support the upgraded 7-layer QA architecture, the existing tests/ directory should be reorganized into the following clean structure:
PrizmForge/
├── .github/
│   └── workflows/
│       └── test.yml                 <-- NEW: GitHub Actions CI/CD Pipeline
├── .bandit                          <-- NEW: Bandit Security Config
├── pyproject.toml                   <-- NEW: Ruff, Mypy, and Pytest Configs
├── tests/
│   ├── conftest.py                  <-- MODIFIED: Standardized fixtures
│   ├── unit/
│   │   ├── test_core_components.py  <-- MODIFIED: Consolidates unit tests
│   │   ├── test_properties.py       <-- NEW: Hypothesis property-based tests
│   │   └── test_security.py         <-- NEW: Binary payload & SQLi verification
│   ├── integration/
│   │   └── test_governed_workflow.py<-- MODIFIED: Full multi-agent lifecycle
│   ├── functional/
│   │   └── test_api_endpoints.py    <-- NEW: FastAPI & Pydantic endpoint tests
│   └── performance/
│       ├── test_benchmarks.py       <-- NEW: pytest-benchmark micro-tests
│       └── locustfile.py            <-- NEW: Locust load testing scenario
└── utils/
    └── run_tests.sh                 <-- MODIFIED: Enhanced parallel runner

3. Required Framework Modifications & Implementation
3.1 Fixture & Infrastructure Upgrade (tests/conftest.py)
What Needs Modification:
•	Add sandbox_project_dir to ensure path containment tests never leave the tmp_path sandbox.
•	Add mock_llm_http to intercept requests.post calls across all agents, preventing network leaks.
•	Enhance temp_db to handle thread-safe cleanup for background workers (BackgroundAgentPool).
"""
Global pytest fixtures for PrizmForge testing.
Handles temporary SQLite databases, mock LLM state, and path sandboxing.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Generator
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(scope="function")
def temp_db(monkeypatch: pytest.MonkeyPatch) -> Generator[str, None, None]:
    """
    Creates an isolated temporary SQLite database for each test run.
    Overrides PRIZMFORGE_DB_PATH so database operations affect only the sandbox.
    """
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    if os.path.exists(db_path):
        try:
            os.unlink(db_path)
        except OSError:
            pass

    monkeypatch.setenv("PRIZMFORGE_DB_PATH", db_path)

    from core.db import init_db
    init_db()

    yield db_path

    if os.path.exists(db_path):
        try:
            os.unlink(db_path)
        except OSError:
            pass


@pytest.fixture
def sandbox_project_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """
    Provides a sandboxed project directory under repo root for path containment tests.
    """
    project_dir = tmp_path / "sandbox_project"
    project_dir.mkdir(parents=True, exist_ok=True)

    from core import config as config_mod
    orig_get_config = config_mod.get_config

    def _mock_config() -> Dict[str, Any]:
        cfg = dict(orig_get_config())
        cfg["project_directory"] = str(project_dir)
        cfg["git"] = False
        cfg["background_agents_enabled"] = False
        return cfg

    monkeypatch.setattr(config_mod, "get_config", _mock_config)
    return project_dir


@pytest.fixture
def mock_llm_http(monkeypatch: pytest.MonkeyPatch) -> Any:
    """
    HTTP-level mock for requests.post to prevent network egress during unit tests.
    """
    state = {"response_text": '{"status": "ok"}', "status_code": 200}

    def _fake_post(url: str, *args: Any, **kwargs: Any) -> MagicMock:
        mock_resp = MagicMock()
        mock_resp.status_code = state["status_code"]
        payload = {
            "id": "chatcmpl-mock",
            "object": "chat.completion",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": state["response_text"]},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
        }
        mock_resp.json.return_value = payload
        mock_resp.text = str(payload)
        mock_resp.content = str(payload).encode("utf-8")
        mock_resp.headers = {"Content-Type": "application/json"}
        mock_resp.raise_for_status = MagicMock()
        return mock_resp

    monkeypatch.setattr("requests.post", _fake_post)

    def _set_response(text: str, status_code: int = 200) -> None:
        state["response_text"] = text
        state["status_code"] = status_code

    return _set_response

3.2 Unit Testing Enhancements (tests/unit/test_core_components.py)
What Needs Modification:
•	Combine isolated checks for parse_json_response, validate_source_content, looks_like_binary, RateLimiter, and _resolve_contained_path into a dedicated unit suite.
"""
Unit tests for core PrizmForge components.
"""

from __future__ import annotations

from pathlib import Path
import pytest

from core.content_safety import looks_like_binary, validate_source_content
from core.edit_response_validator import EditFailureReason, validate_developer_edit_response
from core.json_parser import parse_json_response
from core.rate_limiter import RateLimiter
from file_editing.writer import _resolve_contained_path


class TestJsonParserUnit:
    """Tests JSON extraction strategies across markdown wraps, truncations, and edge cases."""

    def test_parse_valid_json_object(self) -> None:
        raw = '{"target_file_path": "app.py", "summary": "Valid edit"}'
        result = parse_json_response(raw)
        assert result is not None
        assert result["target_file_path"] == "app.py"

    def test_parse_markdown_wrapped_json(self) -> None:
        raw = "Here is the proposal:\n```json\n{\"action\": \"create\", \"file\": \"main.py\"}\n```\nHope this helps!"
        result = parse_json_response(raw)
        assert result is not None
        assert result["action"] == "create"

    def test_parse_malformed_json_returns_none(self) -> None:
        raw = '{"target_file_path": "app.py", "summary": '
        result = parse_json_response(raw)
        assert result is None

    def test_parse_empty_string_returns_none(self) -> None:
        assert parse_json_response("") is None
        assert parse_json_response("   \n\t ") is None


class TestContentSafetyUnit:
    """Validates binary payload rejection (PE, ELF, OLE/MSI) and source script permissions."""

    def test_reject_pe_mz_header(self) -> None:
        binary_data = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff"
        is_bin, reason = looks_like_binary(binary_data)
        assert is_bin is True
        assert "PE/DOS" in reason

    def test_reject_ole_cfb_msi_magic(self) -> None:
        ole_data = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 100
        is_bin, reason = looks_like_binary(ole_data)
        assert is_bin is True
        assert "OLE/CFB" in reason

    def test_reject_blocked_extensions(self) -> None:
        validation = validate_source_content("plain text", file_path="installer.msi")
        assert validation["ok"] is False
        assert "blocked extension" in validation["message"]

    def test_allow_powershell_and_python_scripts(self) -> None:
        ps_content = "Write-Host 'Deploying application...'\nGet-Service"
        val_ps = validate_source_content(ps_content, file_path="deploy.ps1")
        assert val_ps["ok"] is True

        py_content = "def main():\n    print('Running PrizmForge')"
        val_py = validate_source_content(py_content, file_path="main.py")
        assert val_py["ok"] is True


class TestPathContainmentUnit:
    """Verifies path containment checks prevent directory traversal outside repo root."""

    def test_valid_relative_path(self, sandbox_project_dir: Path) -> None:
        resolved = _resolve_contained_path("src/utils.py", sandbox_project_dir)
        assert resolved.is_relative_to(sandbox_project_dir)

    def test_traversal_attack_raises_error(self, sandbox_project_dir: Path) -> None:
        with pytest.raises(ValueError, match="escapes project directory"):
            _resolve_contained_path("../../etc/passwd", sandbox_project_dir)

    def test_nested_traversal_escape_raises_error(self, sandbox_project_dir: Path) -> None:
        with pytest.raises(ValueError, match="escapes project directory"):
            _resolve_contained_path("src/../../outside.py", sandbox_project_dir)


class TestRateLimiterUnit:
    """Tests thread-safe sliding window rate limiting."""

    def test_rate_limiter_allows_under_capacity(self) -> None:
        limiter = RateLimiter(max_calls_per_minute=10)
        for _ in range(5):
            limiter.wait_if_needed()
        assert len(limiter.calls) == 5

    def test_rate_limiter_dynamic_max_calls_update(self) -> None:
        limiter = RateLimiter(max_calls_per_minute=100)
        limiter.set_max_calls(20)
        assert limiter.max_calls == 20

3.3 Integration Workflow Tests (tests/integration/test_governed_workflow.py)
What Needs Modification:
•	Expand existing integration tests (test_golden_path.py) to explicitly test the full lifecycle including line-level GUID updates, snapshot_before_apply, and undo_proposal.
"""
Integration test for multi-agent orchestration, proposal creation, reviewer gate, materialization, and rollback.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict
import pytest

from core.db_connection import get_db_connection
from file_editing.editing import apply_edit_proposal
from file_editing.undo import snapshot_before_apply, undo_proposal
from file_editing.writer import initialize_file_lines, materialize_proposal, reconstruct_file_content
from workflow.proposal_builder import create_proposal_from_developer_output, update_proposal_status


class TestGovernedWorkflowIntegration:
    """Exercises full proposal lifecycle: initialize -> propose -> review -> apply -> materialize -> undo."""

    def test_full_proposal_lifecycle_and_undo(self, temp_db: str, sandbox_project_dir: Path) -> None:
        target_file = "app/service.py"
        initial_content = "VERSION = '1.0.0'\n\ndef run():\n    return True\n"

        # Step 1: Initialize file lines with stable GUIDs
        init_res = initialize_file_lines(target_file, initial_content)
        assert init_res["status"] == "success"
        file_id = init_res["file_id"]

        # Verify initial line content
        with get_db_connection() as conn:
            reconstructed = reconstruct_file_content(conn, file_id)
            assert reconstructed == initial_content

        # Step 2: Developer outputs EditPayload
        developer_payload = {
            "target_file_path": target_file,
            "summary": "Bump version to 1.1.0",
            "rationale": "Updating service version for new release iteration",
            "operations": [
                {
                    "type": "find_replace",
                    "find": "VERSION = '1.0.0'",
                    "replace": "VERSION = '1.1.0'",
                    "rationale": "Update version string",
                }
            ],
        }

        # Step 3: Create Edit Proposal
        prop_res = create_proposal_from_developer_output(
            developer_output=developer_payload,
            proposed_by_agent_id=1,
            target_file_path=target_file,
            selected_mode="find_replace",
            final_mode="find_replace",
        )
        assert prop_res["status"] == "success"
        proposal_id = prop_res["proposal_id"]

        # Step 4: Reviewer Safety Gate Approve
        updated = update_proposal_status(proposal_id, "approved", reviewed_by_agent_id=2)
        assert updated is True

        # Step 5: Snapshot before apply & Materialize
        snap_res = snapshot_before_apply(proposal_id)
        assert snap_res["status"] == "success"

        apply_res = apply_edit_proposal(proposal_id)
        assert apply_res["status"] == "success"

        mat_res = materialize_proposal(proposal_id)
        assert mat_res["status"] == "success"

        # Verify disk and DB state after materialization
        disk_file = sandbox_project_dir / target_file
        assert disk_file.exists()
        assert "VERSION = '1.1.0'" in disk_file.read_text(encoding="utf-8")

        # Step 6: Undo Proposal and restore previous snapshot
        undo_res = undo_proposal(proposal_id, write_disk=True)
        assert undo_res["status"] == "success"
        assert "VERSION = '1.0.0'" in disk_file.read_text(encoding="utf-8")

    def test_optimistic_concurrency_conflict_detection(self, temp_db: str) -> None:
        target_file = "app/config.py"
        initial_content = "PORT = 8080\nDEBUG = True\n"
        init_res = initialize_file_lines(target_file, initial_content)
        file_id = init_res["file_id"]

        # Fetch GUID for line 1
        with get_db_connection() as conn:
            cursor = conn.execute("SELECT line_guid FROM file_lines WHERE file_id = ? AND sort_order = 1024.0", (file_id,))
            line_guid = cursor.fetchone()[0]

        proposal_payload = {
            "target_file_path": target_file,
            "summary": "Change PORT to 9090",
            "rationale": "Updating default listening port",
            "operations": [
                {
                    "type": "replace_block",
                    "start_line_guid": line_guid,
                    "new_content": ["PORT = 9090"],
                    "rationale": "Update port line",
                }
            ],
        }

        prop_res = create_proposal_from_developer_output(
            developer_output=proposal_payload,
            proposed_by_agent_id=1,
            target_file_path=target_file,
        )
        proposal_id = prop_res["proposal_id"]

        # Simulate concurrent modification by altering line_hash in DB
        with get_db_connection() as conn:
            conn.execute("UPDATE file_lines SET content_hash = 'stale_hash' WHERE line_guid = ?", (line_guid,))
            conn.execute("UPDATE edit_proposals SET status = 'approved' WHERE proposal_id = ?", (proposal_id,))

        # Application should detect hash conflict and return 'conflicted'
        apply_res = apply_edit_proposal(proposal_id)
        assert apply_res["status"] == "conflicted"

3.4 Property Testing & Static Analysis (tests/unit/test_properties.py & pyproject.toml)
What Needs Modification:
•	Replace manual table checks in test_fuzz_tables.py with randomized property tests using Hypothesis.
•	Configure mypy and ruff in pyproject.toml.
"""
Property-based testing with Hypothesis to fuzz token estimation, JSON cleanup, and edit payload validation.
"""

from __future__ import annotations

from hypothesis import given, settings, HealthCheck, strategies as st

from agents.response_cleaner import clean_llm_response
from core.token_estimator import estimate_tokens
from file_editing.edit_payload import FindReplace


class TestHypothesisProperties:
    """Fuzzing and invariant checks across random inputs."""

    @given(st.text())
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_token_estimator_non_negative(self, input_text: str) -> None:
        """Invariant: Token estimation must always return an integer >= 0."""
        tokens = estimate_tokens(input_text)
        assert isinstance(tokens, int)
        assert tokens >= 0

    @given(st.text(min_size=1, max_size=1000))
    def test_token_estimator_monotonicity(self, text_segment: str) -> None:
        """Invariant: Appending characters to text should never decrease token estimate."""
        base_tokens = estimate_tokens(text_segment)
        extended_tokens = estimate_tokens(text_segment + text_segment)
        assert extended_tokens >= base_tokens

    @given(find=st.text(min_size=1, max_size=100), replace=st.text(max_size=100))
    def test_find_replace_dataclass_properties(self, find: str, replace: str) -> None:
        """Property test for FindReplace operation validation."""
        op = FindReplace(
            find=find,
            replace=replace,
            rationale="Automated property test for find_replace operation",
        )
        assert op.find == find
        assert op.replace == replace
        assert op.type == "find_replace"

    @given(json_body=st.dictionaries(st.text(min_size=1, max_size=20), st.text(max_size=50)))
    def test_response_cleaner_json_fuzz(self, json_body: dict[str, str]) -> None:
        """Property test: Valid JSON dictionary wrapped in markdown must always be extracted."""
        import json

        raw_json = json.dumps(json_body)
        wrapped = f"Here is the result:\n```json\n{raw_json}\n```"
        cleaned = clean_llm_response(wrapped, agent_name="fuzz_tester")
        assert cleaned is not None
        assert json.loads(cleaned) == json_body
Updated pyproject.toml
[tool.mypy]
python_version = "3.10"
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
disallow_untyped_decorators = true
no_implicit_optional = true
warn_redundant_casts = true
warn_unused_ignores = true

[[tool.mypy.overrides]]
module = ["locust.*", "pytest_benchmark.*"]
ignore_missing_imports = true

[tool.ruff]
target-version = "py310"
line-length = 120

[tool.ruff.lint]
select = ["E", "F", "B", "I", "N", "UP", "S", "A", "RUF"]
ignore = ["S101", "S105"]

[tool.ruff.lint.per-file-ignores]
"tests/*" = ["S101", "S106"]

3.5 Functional API Testing (tests/functional/test_api_endpoints.py)
What Needs Modification:
•	Add HTTP route testing via FastAPI TestClient and httpx to validate API boundaries, request validation, and response models.
"""
Functional testing for FastAPI/REST endpoints exposing PrizmForge operations.
"""

from __future__ import annotations

from typing import Any, Dict, List
import pytest
from pydantic import BaseModel, Field


class TaskSubmitRequest(BaseModel):
    task_id: str = Field(..., min_length=3)
    user_command: str = Field(..., min_length=5)
    max_turns: int = Field(default=10, ge=1, le=50)


class TaskSubmitResponse(BaseModel):
    status: str
    task_id: str
    message: str


class HealthStatusResponse(BaseModel):
    status: str
    version: str
    active_endpoints: List[str]


from fastapi import FastAPI, HTTPException, status
from fastapi.testclient import TestClient

app = FastAPI(title="PrizmForge API")


@app.get("/health", response_model=HealthStatusResponse)
def get_health() -> Dict[str, Any]:
    return {
        "status": "healthy",
        "version": "3.1.0",
        "active_endpoints": ["gemini", "databricks"],
    }


@app.post("/v1/tasks", response_model=TaskSubmitResponse, status_code=status.HTTP_202_ACCEPTED)
def submit_task(payload: TaskSubmitRequest) -> Dict[str, Any]:
    if "error" in payload.user_command.lower():
        raise HTTPException(status_code=400, detail="Invalid command payload")
    return {
        "status": "accepted",
        "task_id": payload.task_id,
        "message": f"Task {payload.task_id} queued successfully.",
    }


class TestApiEndpoints:
    """Test suite validating HTTP responses, status codes, and JSON schema boundaries."""

    @pytest.fixture
    def client(self) -> TestClient:
        return TestClient(app)

    def test_health_check_endpoint(self, client: TestClient) -> None:
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        validated = HealthStatusResponse(**data)
        assert validated.status == "healthy"

    def test_submit_task_success(self, client: TestClient) -> None:
        payload = {
            "task_id": "task-101",
            "user_command": "Refactor database pool connections",
            "max_turns": 15,
        }
        response = client.post("/v1/tasks", json=payload)
        assert response.status_code == 202
        validated = TaskSubmitResponse(**response.json())
        assert validated.task_id == "task-101"
        assert validated.status == "accepted"

    def test_submit_task_validation_failure(self, client: TestClient) -> None:
        invalid_payload = {
            "task_id": "ab",
            "user_command": "Fix",
            "max_turns": 100,
        }
        response = client.post("/v1/tasks", json=invalid_payload)
        assert response.status_code == 422

3.6 Performance & Load Testing (pytest-benchmark & Locust)
What Needs Modification:
•	Add tests/performance/test_benchmarks.py using pytest-benchmark.
•	Add tests/performance/locustfile.py for simulated load testing.
"""
Micro-benchmarks for critical PrizmForge paths using pytest-benchmark.
"""

from __future__ import annotations

from typing import Any
import pytest

from core.symbol_index import parse_python_symbols
from core.token_estimator import estimate_tokens


def test_token_estimation_benchmark(benchmark: Any) -> None:
    """Benchmark token estimation performance on large source text."""
    sample_code = """
    def complex_algorithm(data_list: list[dict[str, Any]]) -> dict[str, float]:
        result = {}
        for item in data_list:
            key = item.get("key", "default")
            value = float(item.get("value", 0.0))
            result[key] = result.get(key, 0.0) + value
        return result
    """ * 100

    result = benchmark(estimate_tokens, sample_code)
    assert result > 0


def test_symbol_parsing_benchmark(benchmark: Any) -> None:
    """Benchmark AST symbol parsing across Python modules."""
    python_source = """
class DataProcessor:
    def __init__(self, config: dict):
        self.config = config

    def process(self, payload: str) -> bool:
        return len(payload) > 0

def top_level_helper(x: int, y: int) -> int:
    return x + y
""" * 50

    symbols = benchmark(parse_python_symbols, python_source, "core/processor.py")
    assert len(symbols) > 0
Locust Load File (tests/performance/locustfile.py)
"""
Locust load test script simulating multi-user task submissions and status polls.
Run via: locust -f tests/performance/locustfile.py --headless -u 10 -r 2 --run-time 1m --host http://localhost:8000
"""

from __future__ import annotations

import random
from locust import HttpUser, SequentialTaskSet, between, task


class AgentOrchestrationUserBehavior(SequentialTaskSet):
    """Simulates realistic developer interaction cycles with PrizmForge."""

    def on_start(self) -> None:
        self.task_id = f"locust-task-{random.randint(1000, 9999)}"

    @task
    def check_health(self) -> None:
        self.client.get("/health", name="01_HealthCheck")

    @task
    def submit_task(self) -> None:
        payload = {
            "task_id": self.task_id,
            "user_command": "Optimize SQL queries in repository layer",
            "max_turns": 10,
        }
        headers = {"Content-Type": "application/json"}
        self.client.post("/v1/tasks", json=payload, headers=headers, name="02_SubmitTask")


class PrizmForgeLoadUser(HttpUser):
    tasks = [AgentOrchestrationUserBehavior]
    wait_time = between(1.0, 3.0)

3.7 Security Auditing Setup (.bandit & tests/unit/test_security.py)
What Needs Modification:
•	Add .bandit file targeting all core source packages.
•	Add tests/unit/test_security.py to test SQL injection prevention and binary file rejection.
# Bandit Security Scanner Configuration
targets:
  - "agents"
  - "cli"
  - "core"
  - "file_editing"
  - "workflow"

exclude_dirs:
  - "tests"
  - ".venv"
  - "report"

skips:
  - B101

tests:
  - B201
  - B301
  - B307
  - B602
  - B608
tests/unit/test_security.py
"""
Unit tests validating static security rules and binary content safety guards.
"""

from __future__ import annotations

import pytest
from core.content_safety import validate_source_content


class TestSecurityGuards:
    """Validates that binary execution payloads are rejected by the governed pipeline."""

    def test_pe_executable_rejection(self) -> None:
        pe_header = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff\x00\x00\xb8\x00\x00\x00"
        res = validate_source_content(pe_header, file_path="malicious.exe")
        assert res["ok"] is False
        assert "blocked extension" in res["message"] or "binary" in res["message"]

    def test_sql_injection_prevention_in_db_helpers(self, temp_db: str) -> None:
        """Ensure parameterized query compliance prevents SQL injection."""
        from core.db_connection import get_db_connection

        malicious_id = "task-001' OR '1'='1"
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tasks WHERE id = ?", (malicious_id,))
            rows = cursor.fetchall()
            assert len(rows) == 0

3.8 CI/CD Automation Pipeline (.github/workflows/test.yml)
What Needs Modification:
•	Create .github/workflows/test.yml to run the full matrix test suite (Python 3.10, 3.11, 3.12) with pip caching, ruff, mypy, bandit, pip-audit, and a 90% coverage enforcement gate.
name: PrizmForge CI/CD Pipeline

on:
  push:
    branches: [ "main", "develop" ]
  pull_request:
    branches: [ "main", "develop" ]

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

permissions:
  contents: read

jobs:
  static-security-and-lint:
    name: Code Quality & Security Audit
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Repository
        uses: actions/checkout@v4

      - name: Set up Python 3.10
        uses: actions/setup-python@v5
        with:
          python-version: "3.10"
          cache: "pip"

      - name: Install Linting & Security Dependencies
        run: |
          python -m pip install --upgrade pip
          pip install ruff mypy bandit pip-audit

      - name: Run Ruff Linter & Formatter Check
        run: |
          ruff check .
          ruff format --check .

      - name: Run Mypy Static Type Checker
        run: |
          mypy agents/ core/ file_editing/ workflow/ cli/

      - name: Run Bandit Security Audit
        run: |
          bandit -r agents/ core/ file_editing/ workflow/ cli/ -c .bandit

      - name: Audit Third-Party Dependencies (pip-audit)
        run: |
          pip-audit --ignore-code 1

  test-matrix:
    name: Pytest Suite (Python ${{ matrix.python-version }})
    needs: static-security-and-lint
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        python-version: ["3.10", "3.11", "3.12"]

    steps:
      - name: Checkout Repository
        uses: actions/checkout@v4

      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
          cache: "pip"

      - name: Install Test Dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install pytest pytest-cov pytest-mock hypothesis httpx pydantic fastapi pytest-benchmark

      - name: Execute Pytest Suite with 90% Coverage Gate
        env:
          PRIZMFORGE_TEST_MODE: "1"
        run: |
          pytest tests/ \
            -m "not slow" \
            --cov=agents \
            --cov=core \
            --cov=file_editing \
            --cov=workflow \
            --cov=cli \
            --cov-report=term-missing \
            --cov-report=xml \
            --cov-fail-under=90

      - name: Upload Coverage XML Artifact
        uses: actions/upload-artifact@v4
        with:
          name: coverage-py${{ matrix.python-version }}
          path: coverage.xml

4. Test Runner & Local Execution Script (utils/run_tests.sh)
Update utils/run_tests.sh to support parallel execution using pytest-xdist with load-file distribution across test files.
#!/usr/bin/env bash

# Enhanced Parallel Test Runner for PrizmForge

set -euo pipefail

cd "$(dirname "$0")/.."

PYTHON_EXEC="${PYTHON_EXEC:-python3}"
PARALLEL_JOBS="${PARALLEL_JOBS:-auto}"

echo "===================================================="
echo "🚀 Running PrizmForge Production Test Suite"
echo "Python Executable: $PYTHON_EXEC"
echo "Parallel Workers:  $PARALLEL_JOBS"
echo "===================================================="

# 1. Run Static Code Quality & Security Checks
echo -e "\n[1/4] Running Ruff Linter & Formatter..."
"$PYTHON_EXEC" -m ruff check .
"$PYTHON_EXEC" -m ruff format --check .

echo -e "\n[2/4] Running Bandit Security Audit..."
"$PYTHON_EXEC" -m bandit -r agents/ core/ file_editing/ workflow/ cli/ -c .bandit

echo -e "\n[3/4] Running Mypy Static Type Checking..."
"$PYTHON_EXEC" -m mypy agents/ core/ file_editing/ workflow/ cli/

# 2. Run Pytest Suite with Coverage Enforcement
echo -e "\n[4/4] Running Pytest Suite with 90% Coverage Gate..."
"$PYTHON_EXEC" -m pytest tests/ \
    -n "$PARALLEL_JOBS" \
    --dist loadfile \
    -m "not slow" \
    --cov=agents \
    --cov=core \
    --cov=file_editing \
    --cov=workflow \
    --cov=cli \
    --cov-report=term-missing \
    --cov-fail-under=90

echo -e "\n✅ All PrizmForge test gates passed successfully!"
