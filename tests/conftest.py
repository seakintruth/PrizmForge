"""
Pytest fixtures for PrizmForge tests.

Isolation rules:
- Never write agents.db, reports, or exports into the real repo tree.
- Every test gets a private temp workspace (project + .PrizmForge).
- DB schema is initialized only when a test requests temp_db (or via
  fixtures that depend on it), so pure unit tests stay fast.
- Never inherit live background_agents from the developer's config.json.
  Tests that intentionally exercise the pool must opt in and use MockLLM.

Duration tracking:
- Call-phase reports are recorded via pytest_runtest_logreport (works on
  the xdist master, not only on workers).
- On session finish a JSON file is written under the *repo* reports dir
  (not the isolated temp workspace). Override with PRIZMFORGE_DURATION_REPORT.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Repo-local paths that must never be used as test side-effect targets
_REPO_PRIZMFORGE = PROJECT_ROOT / ".PrizmForge"


def _force_test_safe_config(cfg: dict, project_dir: str) -> dict:
    """Return a config dict that cannot spawn live LLM workers by default.

    Overrides (not setdefault) so values from the developer's real config.json
    cannot leak into the test process.
    """
    out = dict(cfg) if isinstance(cfg, dict) else {}
    out["project_directory"] = project_dir
    out["git"] = False
    out["git_auto_commit"] = False
    # CRITICAL: override, do not setdefault — real config often enables these
    out["background_agents_enabled"] = False
    out["background_agents"] = {}
    out["background_feeder"] = {}
    return out


# Modules that do `from core.config import get_config` (local name binding).
# Patching only core.config.get_config is NOT enough for these sites.
_GET_CONFIG_PATCH_TARGETS = (
    "core.config.get_config",
    "agents.parallel_workers.get_config",
    "agents.resource_controller_worker.get_config",
    "agents.reporter_worker.get_config",
    "agents.orchestrator.get_config",
    "workflow.task_runner.get_config",
)


def _patch_get_config_everywhere(monkeypatch, getter) -> None:
    """Replace get_config at the module and at every known import site."""
    for target in _GET_CONFIG_PATCH_TARGETS:
        try:
            monkeypatch.setattr(target, getter)
        except (AttributeError, ImportError):
            # Module may not be imported yet; later imports still pick up
            # core.config.get_config when using attribute access.
            pass


# ---------------------------------------------------------------------------
# Per-test duration tracking (for slow/normal rebalance)
# ---------------------------------------------------------------------------


def _duration_report_path() -> Path:
    """Resolve where to write the duration JSON (repo reports, not temp ws)."""
    env = os.environ.get("PRIZMFORGE_DURATION_REPORT", "").strip()
    if env:
        return Path(env)
    batch = os.environ.get("PRIZMFORGE_BATCH_NAME", "").strip() or "session"
    stamp = os.environ.get("PRIZMFORGE_REPORT_STAMP", "").strip()
    if not stamp:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    reports = PROJECT_ROOT / ".PrizmForge" / "reports"
    return reports / f"test-durations-{batch}-{stamp}.json"


def pytest_configure(config) -> None:
    # Only collect on the controller / non-xdist process.
    worker = getattr(config, "workerinput", None)
    config._prizmforge_duration_records = [] if worker is None else None


def pytest_runtest_logreport(report) -> None:
    """Record call-phase durations on the master (xdist-safe)."""
    if report.when != "call":
        return
    # Access config via the report's location is awkward; use the global
    # pytest config from the current session when available.
    config = getattr(pytest_runtest_logreport, "_config", None)
    if config is None:
        return
    records = getattr(config, "_prizmforge_duration_records", None)
    if records is None:
        return
    # Markers are not always on the report under xdist; parse nodeid keywords
    # is unreliable. Prefer report.keywords (pytest sets marker names True).
    keywords = getattr(report, "keywords", {}) or {}
    markers = sorted(
        name
        for name, val in keywords.items()
        if val is True and name not in {"", report.outcome} and not name.startswith("test_") and name not in {"pytestmark", "parametrize"}
    )
    # Explicit slow check is what the analyzer cares about most.
    is_slow = bool(keywords.get("slow")) or "slow" in markers
    records.append(
        {
            "nodeid": report.nodeid,
            "duration_s": round(float(report.duration), 4),
            "outcome": report.outcome,
            "markers": markers,
            "slow": is_slow,
            "file": report.nodeid.split("::", 1)[0],
        }
    )


def pytest_sessionstart(session) -> None:
    # Stash config so logreport can find the record list without item.
    pytest_runtest_logreport._config = session.config  # type: ignore[attr-defined]


def pytest_sessionfinish(session, exitstatus) -> None:
    records = getattr(session.config, "_prizmforge_duration_records", None)
    if not records:
        return
    path = _duration_report_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "exitstatus": int(exitstatus),
            "batch": os.environ.get("PRIZMFORGE_BATCH_NAME", "session"),
            "count": len(records),
            "tests": sorted(records, key=lambda r: r["duration_s"], reverse=True),
        }
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

        latest = path.parent / "test-durations-latest.json"
        merged_tests = list(payload["tests"])
        if latest.exists():
            try:
                prev = json.loads(latest.read_text(encoding="utf-8"))
                if isinstance(prev, dict) and isinstance(prev.get("tests"), list):
                    by_id = {t["nodeid"]: t for t in prev["tests"] if "nodeid" in t}
                    for t in merged_tests:
                        by_id[t["nodeid"]] = t
                    merged_tests = sorted(by_id.values(), key=lambda r: r["duration_s"], reverse=True)
            except (json.JSONDecodeError, OSError, TypeError):
                pass
        latest.write_text(
            json.dumps(
                {
                    "generated_at": payload["generated_at"],
                    "exitstatus": payload["exitstatus"],
                    "batch": "merged",
                    "count": len(merged_tests),
                    "tests": merged_tests,
                    "source": str(path.name),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"    duration report: {path}")
    except OSError as e:
        print(f"    ⚠️  duration report write failed: {e}")


@pytest.fixture(autouse=True)
def _isolate_prizmforge_workspace(tmp_path_factory, monkeypatch):
    """
    Force all tests into a per-test temp workspace.

    Sets:
      - PRIZMFORGE_DB_PATH → <tmp>/.PrizmForge/agents.db
      - core.config.get_config() project_directory → <tmp>/project
      - background_agents_enabled=False and background_agents={} (hard override)
      - get_config local bindings in parallel_workers / RC / reporter / etc.

    Does NOT call init_db (keeps pure unit tests light). Tests that touch
    the DB should request the temp_db fixture (or one that depends on it).
    """
    base = tmp_path_factory.mktemp("prizmforge_ws")
    project = base / "project"
    project.mkdir(parents=True, exist_ok=True)
    prizm = base / ".PrizmForge"
    prizm.mkdir(parents=True, exist_ok=True)
    reports = prizm / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    db_path = prizm / "agents.db"

    monkeypatch.setenv("PRIZMFORGE_DB_PATH", str(db_path))
    monkeypatch.setenv("PRIZMFORGE_TEST_PROJECT_DIR", str(project))
    monkeypatch.setenv("PRIZMFORGE_TEST_WORKSPACE", str(base))

    from core import config as core_config

    _orig_get_config = core_config.get_config

    def _isolated_get_config():
        try:
            cfg = _orig_get_config()
        except Exception:
            cfg = {}
        return _force_test_safe_config(cfg, str(project))

    _patch_get_config_everywhere(monkeypatch, _isolated_get_config)

    yield {
        "base": base,
        "project": project,
        "prizmforge": prizm,
        "db_path": db_path,
        "reports": reports,
    }

    if _REPO_PRIZMFORGE.exists():
        agents = _REPO_PRIZMFORGE / "agents.db"
        if agents.exists() and agents.stat().st_size == 0:
            try:
                agents.unlink()
            except OSError:
                pass


@pytest.fixture(scope="function")
def temp_db(monkeypatch, _isolate_prizmforge_workspace):
    """
    Initialize a fresh agents.db under the isolated workspace and return its path.

    Dependent fixtures (isolated_project, etc.) use this so schema exists without
    writing into the real repo .PrizmForge directory.
    """
    from core.db import init_db

    db_path = _isolate_prizmforge_workspace["db_path"]
    p = Path(db_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists():
        try:
            p.unlink()
        except OSError:
            pass

    init_db()

    yield db_path

    try:
        if p.exists():
            p.unlink()
    except OSError:
        pass


@pytest.fixture
def mock_minimal_config(monkeypatch, _isolate_prizmforge_workspace):
    """
    Minimal valid configuration pointed at the isolated temp project.

    No shared /tmp/test_project — each test gets its own directory under
    the autouse workspace. background_agents is always empty so pool.start()
    cannot launch live LLM workers unless a test explicitly re-enables them
    and patches call_agent.
    """
    project_dir = str(_isolate_prizmforge_workspace["project"])
    Path(project_dir).mkdir(parents=True, exist_ok=True)

    minimal_config = {
        "project_directory": project_dir,
        "git": False,
        "git_auto_commit": False,
        "background_agents_enabled": False,
        "background_agents": {},
        "background_feeder": {},
        "default_endpoint": "mock",
        "endpoints": {
            "mock": {
                "base_url": "http://localhost:9999/v1/chat/completions",
                "api_key_name": "mock_key",
                "include_model_in_payload": True,
                "response_path": ["choices", 0, "message", "content"],
                "priority": 10,
                "rate_limit_per_minute": 60,
            }
        },
        "models": {
            "mock-model": {
                "endpoint": "mock",
                "max_output_tokens": 1024,
                "max_context_tokens": 100000,
                "temperature": 0.5,
            }
        },
        "agent_model_preferences": {
            "developer": "mock-model",
            "reviewer": "mock-model",
            "orchestrator": "mock-model",
        },
        "token_budget": {"max_tokens_per_4h": 1_000_000},
        "default_model": "mock-model",
    }

    _patch_get_config_everywhere(monkeypatch, lambda: minimal_config)
    return minimal_config


@pytest.fixture
def isolated_project(mock_minimal_config, temp_db, _isolate_prizmforge_workspace):
    """
    Full isolation pack: config + initialized DB + project path.

    Prefer this for worker/lifecycle/integration-style tests.
    """
    return {
        "config": mock_minimal_config,
        "db_path": temp_db,
        "project": _isolate_prizmforge_workspace["project"],
        "workspace": _isolate_prizmforge_workspace["base"],
        "reports": _isolate_prizmforge_workspace["reports"],
    }


@pytest.fixture
def capsys_and_temp_db(temp_db, capsys):
    """Convenience fixture that combines temp DB + output capture."""
    return {"db_path": temp_db, "capsys": capsys}


@pytest.fixture
def mock_openai_chat(monkeypatch):
    """
    Mock OpenAI-compatible chat completion at the HTTP layer (requests.post).

    Stdlib-only — does not require pytest-mock or responses.
    """
    from tests.mocks.openai import make_requests_response

    state = {"response_text": "Mocked response", "status_code": 200}

    def _fake_post(*args, **kwargs):
        return make_requests_response(
            state["response_text"],
            status_code=state["status_code"],
        )

    monkeypatch.setattr("agents.base.requests.post", _fake_post)
    try:
        import requests as _requests

        monkeypatch.setattr(_requests, "post", _fake_post)
    except Exception as e:
        print(f"    ⚠️  Exception handled in conftest.py: {e}")

    def _configure(response_text: str = "Mocked response", status_code: int = 200):
        state["response_text"] = response_text
        state["status_code"] = status_code
        return state

    return _configure


@pytest.fixture
def mock_llm():
    """
    High-level scriptable LLM mock (patches call_agent / call_endpoint).
    """
    from tests.mocks.openai import MockLLM

    return MockLLM()


@pytest.fixture
def mock_llm_patched(mock_llm):
    """
    Same as mock_llm, but already patches call_agent for the duration of the test.
    """
    with mock_llm.patch_call_agent():
        yield mock_llm
