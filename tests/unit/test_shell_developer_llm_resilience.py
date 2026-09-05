"""Soak10 follow-up — shell developer LLM resilience + model-health metadata.

The Soak10 post-mortem showed the shell developer session dying with
``LlmUnavailable`` after N successful calls, with no recorded failure reason
(model_health_events had zero ok=0 rows and the endpoint stayed healthy). The
trajectory could not say whether the failure was rate-limiting, a local health
latch, or token-budget.

These tests lock in the fix:
- _llm re-resolves the model the way call_agent does (explicit override >
  resource-controller > agent_model_preferences) and records the resolved model.
- a failure kind read back from model_health_events decides retry-vs-give-up:
  transient kinds (rate_limited / 5xx / timeout / latch) back off and retry;
  permanent kinds (key_locked / token_budget / ...) do not burn retries.
- the trajectory exposes that metadata (model_stats, last_llm_failure).
"""

from __future__ import annotations

import workflow.shell_developer as sd


def _session(**cfg_overrides):
    worktree = _FakeWorktree()
    config = sd.ShellDeveloperConfig(
        step_limit=5,
        llm_failure_max_retries=3,
        llm_retry_backoff_seconds=1,
        **cfg_overrides,
    )
    return sd.ShellDeveloperSession(config, worktree=worktree, task_id="T-resilience")


class _FakeWorktree:
    def run_command(self, command, timeout=120):
        return 0, "ok"

    def run_test_command(self, command, timeout=600):
        return 0, "ok"


def _install_rc_stub(monkeypatch):
    """Neutral resource controller: never emits an override."""

    class _RC:
        def get_model_override(self, agent_name):
            return None

    monkeypatch.setattr("agents.resource_controller_worker.get_resource_controller", lambda: _RC())


def _install_endpoint_manager(monkeypatch):
    """Install a deterministic endpoint manager so resolution is order-proof.

    get_endpoint_manager() caches a singleton built from the first config seen,
    so an earlier full-suite test (e.g. a mock-minimal config with no
    agent_model_preferences) can pollute the global. Building a fresh manager
    here keeps the resolution-parity assertions stable in any order."""
    from core.endpoint_manager import EndpointManager

    config = {
        "default_endpoint": "openrouter",
        "default_model": "openrouter/openrouter/free",
        "endpoints": {
            "openrouter": {
                "base_url": "https://openrouter.ai/api/v1/chat/completions",
                "api_key_name": "OPENROUTER_API_KEY",
                "include_model_in_payload": True,
                "response_path": ["choices", 0, "message", "content"],
                "priority": 10,
                "rate_limit_per_minute": 60,
                "models": {"openrouter/free": {"max_output_tokens": 8192, "max_context_tokens": 120000}},
            }
        },
        "agent_model_preferences": {"developer": "openrouter/openrouter/free"},
        "fallback_settings": {"enabled": True, "max_fallback_attempts": 2},
    }
    manager = EndpointManager(config)
    monkeypatch.setattr("core.endpoint_manager.get_endpoint_manager", lambda: manager)
    return manager


def _install_llm_script(monkeypatch, script, kinds):
    """Make sd.call_endpoint follow a response script while classifying every
    failure via _recent_failure_kind. Returns captured (model, sleeps)."""
    state = {"i": 0, "models": [], "sleeps": []}

    def fake_call_endpoint(messages, **kwargs):
        i = state["i"]
        state["i"] += 1
        state["models"].append(kwargs.get("model"))
        if i >= len(script):
            return None, 0
        return script[i], 10

    def fake_recent_failure_kind(model_ref, max_age_s=30):
        i = min(state["i"] - 1, len(kinds) - 1)
        return kinds[i] if kinds else ""

    def fake_sleep(seconds):
        state["sleeps"].append(seconds)

    monkeypatch.setattr(sd, "call_endpoint", fake_call_endpoint)
    monkeypatch.setattr(sd, "_recent_failure_kind", fake_recent_failure_kind)
    monkeypatch.setattr(sd.time, "sleep", fake_sleep)
    return state


def _capture_health_records(monkeypatch):
    records = []
    monkeypatch.setattr(sd, "record_model_outcome", lambda model_ref, **kw: records.append({"model": model_ref, **kw}))
    return records


# ---------------------------------------------------------------------------
# Transient → back off and retry instead of killing the session
# ---------------------------------------------------------------------------
def test_transient_failure_backs_off_retries_and_finishes(monkeypatch):
    _install_rc_stub(monkeypatch)
    _install_endpoint_manager(monkeypatch)
    states = _install_llm_script(
        monkeypatch,
        script=[None, None, f"Done.\n{sd.FINISH_TOKEN}\nComplete."],
        kinds=["rate_limited", "rate_limited"],
    )
    records = _capture_health_records(monkeypatch)

    session = _session()
    result = session.run("task")

    assert result.exit_status == "Finished"
    assert result.llm_attempts == 3  # two failures + one success
    assert result.llm_failure_kinds == {"rate_limited": 2}
    assert result.last_llm_failure["kind"] == "rate_limited"
    assert result.last_llm_failure["attempt"] == 2
    assert states["sleeps"] == [1, 2]  # linear backoff: base*(attempt)
    # Every call rode the resolved model (agent prefs), not cfg.model (None).
    assert states["models"] == ["openrouter/openrouter/free"] * 3
    assert session.resolved_model == "openrouter/openrouter/free"
    # Model-health records followed the resolved model too, never None.
    assert records and all(r["model"] == "openrouter/openrouter/free" for r in records)


def test_all_transient_failures_gives_up_truthfully_with_metadata(monkeypatch):
    _install_rc_stub(monkeypatch)
    _install_endpoint_manager(monkeypatch)
    states = _install_llm_script(monkeypatch, script=[None, None, None, None], kinds=["rate_limited"] * 4)
    _capture_health_records(monkeypatch)

    session = _session()
    result = session.run("task")

    assert result.exit_status == "LlmUnavailable"
    assert result.llm_attempts == 4  # max_retries + initial
    assert result.llm_failure_kinds == {"rate_limited": 4}
    assert result.last_llm_failure["kind"] == "rate_limited"
    assert states["sleeps"] == [1, 2, 3]
    assert "rate_limited" in result.summary


def test_permanent_failure_does_not_retry(monkeypatch):
    _install_rc_stub(monkeypatch)
    _install_endpoint_manager(monkeypatch)
    states = _install_llm_script(monkeypatch, script=[None, None, None], kinds=["key_locked"])
    _capture_health_records(monkeypatch)

    session = _session()
    result = session.run("task")

    assert result.exit_status == "LlmUnavailable"
    assert result.llm_attempts == 1  # permanent → no retries burned
    assert result.llm_failure_kinds == {"key_locked": 1}
    assert states["sleeps"] == []
    assert "key_locked" in result.summary


# ---------------------------------------------------------------------------
# Model resolution parity with call_agent
# ---------------------------------------------------------------------------
def test_resolve_developer_model_uses_agent_prefs_when_no_override(monkeypatch):
    _install_rc_stub(monkeypatch)
    _install_endpoint_manager(monkeypatch)
    session = _session()
    # cfg.model is None (orchestrator passed no model) → agent prefs is used,
    # matching agents/base.py call_agent for the "developer" agent.
    assert session._resolve_developer_model() == "openrouter/openrouter/free"


def test_resolve_developer_model_prefers_rc_override(monkeypatch):
    _install_endpoint_manager(monkeypatch)

    class _RC:
        def get_model_override(self, agent_name):
            return "openrouter/openrouter/free"

    monkeypatch.setattr("agents.resource_controller_worker.get_resource_controller", lambda: _RC())
    session = _session()
    assert session._resolve_developer_model() == "openrouter/openrouter/free"


def test_resolve_developer_model_ignores_unknown_override(monkeypatch):
    _install_endpoint_manager(monkeypatch)

    class _RC:
        def get_model_override(self, agent_name):
            return "fake/does-not-exist"

    monkeypatch.setattr("agents.resource_controller_worker.get_resource_controller", lambda: _RC())
    session = _session()
    # An unknown override is NOT trusted blindly (call_agent rule) — the
    # configured agent preference wins instead.
    assert session._resolve_developer_model() == "openrouter/openrouter/free"


# ---------------------------------------------------------------------------
# Trajectory metadata
# ---------------------------------------------------------------------------
def test_serialize_exposes_failure_metadata(monkeypatch):
    _install_rc_stub(monkeypatch)
    _install_endpoint_manager(monkeypatch)
    _install_llm_script(
        monkeypatch,
        script=[None, None, None, None],
        kinds=["server_error", "server_error", "timeout", "timeout"],
    )
    _capture_health_records(monkeypatch)

    session = _session()
    result = session.run("task")
    blob = session.serialize()

    assert result.exit_status == "LlmUnavailable"
    assert blob["model_stats"]["api_calls"] == 4
    assert blob["model_stats"]["llm_attempts"] == 4
    assert blob["model_stats"]["resolved_model"] == "openrouter/openrouter/free"
    assert blob["model_stats"]["failed_calls"] == 4
    assert blob["model_stats"]["failure_kinds"] == {"server_error": 2, "timeout": 2}
    assert blob["last_llm_failure"]["kind"] == "timeout"
    assert blob["last_llm_failure"]["model_ref"] == "openrouter/openrouter/free"


# ---------------------------------------------------------------------------
# Real model-health round trip — NOT monkeypatched through _recent_failure_kind.
# The Soak11 post-mortem caught _recent_failure_kind calling the
# get_db_connection() context manager without ``with``, so it ALWAYS raised and
# every shell failure printed "(unknown)". These tests exercise the actual
# write-then-read path against a real file so that regression cannot hide
# behind a mocked call_endpoint / monkeypatched classifier again.
# ---------------------------------------------------------------------------
def _real_health_db(monkeypatch, tmp_path):
    monkeypatch.setenv("PRIZMFORGE_DB_PATH", str(tmp_path / "agents.db"))
    monkeypatch.setattr("core.model_health.get_config", lambda: {"model_health": {"enabled": True}})


def test_recent_failure_kind_reads_recorded_event_real_db(monkeypatch, tmp_path):
    _real_health_db(monkeypatch, tmp_path)

    sd.record_model_outcome("openrouter/openrouter/free", endpoint="openrouter", ok=False, kind="rate_limited")

    assert sd._recent_failure_kind("openrouter/openrouter/free", max_age_s=999999) == "rate_limited"


def test_recent_failure_kind_real_db_missing_refs_return_empty(monkeypatch, tmp_path):
    _real_health_db(monkeypatch, tmp_path)

    sd.record_model_outcome("openrouter/openrouter/free", endpoint="openrouter", ok=False, kind="rate_limited")
    sd.record_model_outcome("openrouter/openrouter/free", endpoint="openrouter", ok=True)

    assert sd._recent_failure_kind(None) == ""
    assert sd._recent_failure_kind("never/used-ref", max_age_s=999999) == ""
    # A later successful event must not erase the most recent failure kind.
    assert sd._recent_failure_kind("openrouter/openrouter/free", max_age_s=999999) == "rate_limited"
