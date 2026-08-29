"""Sequential-agent network busy-loop guard (plan §8.4 residual, §15 decision 5).

Verifies: outage-phrase detection, the \"pause once + single CRITICAL\" guard
semantics, and end-to-end wiring in ``run_task_cycle`` for both the failsafe
orchestrator outage and the healthy-orchestrator/outaged-developer case.
"""

from workflow.task_runner import NETWORK_FAILURE_PAUSE_THRESHOLD, NetworkBusyLoopGuard, _is_network_failure_text


class FakeTokenBudget:
    def can_spend(self, _n):
        return True


class FakeNoop:
    def get_current_decision(self):
        return None

    def temporarily_disable_throttling(self, **_):
        return None


class FakePool:
    def queue_file_change(self, **_):
        return None


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------


class TestDetection:
    def test_matches_outage_phrasings(self):
        for text in (
            "session LlmUnavailable: endpoint down",
            "LlmUnavailable",
            "endpoint unavailable or token budget exhausted",
            "network error calling developer",
            "no network",
        ):
            assert _is_network_failure_text(text), text

    def test_does_not_match_normal_results(self):
        for text in (
            "",
            None,
            "session Finished: fixed the bug",
            "proposal rejected by reviewer",
            "edit failed: conflict",
        ):
            assert not _is_network_failure_text(text), text


# ---------------------------------------------------------------------------
# Guard semantics
# ---------------------------------------------------------------------------


class TestGuard:
    def test_single_failure_does_not_pause(self):
        guard = NetworkBusyLoopGuard()
        assert guard.record_failure() is False
        assert guard.pause_requested is False

    def test_threshold_pauses_and_surfaces_once_until_success(self, temp_db):
        guard = NetworkBusyLoopGuard()
        guard.record_failure()
        guard.surface("net1")
        assert guard.record_failure() is True
        guard.surface("net1")

        # Surface is sticky until a success: further failures never re-write.
        guard.consume_pause()
        # consume cleared the pause flag, so the very next failure re-pauses
        # (returns True); every subsequent failure while already paused is a
        # no-op (False) and surface stays quiet.
        assert guard.record_failure() is True
        for _ in range(9):
            assert guard.record_failure() is False
            guard.surface("net1")
        assert guard.pause_requested is True  # re-paused after consume

    def test_success_resets_episode(self):
        guard = NetworkBusyLoopGuard()
        guard.record_failure()
        guard.record_success()
        guard.record_failure()
        guard.record_success()
        assert guard.pause_requested is False

    def test_threshold_constant_is_two(self):
        assert NETWORK_FAILURE_PAUSE_THRESHOLD == 2


# ---------------------------------------------------------------------------
# End-to-end: healthy orchestrator + outaged developer never spuriously pauses
# ---------------------------------------------------------------------------


class TestWiringDeveloperOutage:
    def test_single_agent_outage_does_not_trigger_pause(self, temp_db, mock_minimal_config, monkeypatch):
        """A sole developer outage resets the streak on the next orchestrator
        success, so the threshold (two sequential agents) is never reached and
        no CRITICAL is written — the guard targets multi-agent outages."""
        from core.db_connection import get_db_connection
        from workflow import task_runner

        calls = {"orchestrator": 0, "developer": 0}

        def fake_orchestrator(*_a, **_k):
            calls["orchestrator"] += 1
            return {"next_agent": "developer", "instructions": "fix x", "files_needed": [], "reasoning": "r", "model": None}

        def fake_dispatch(**kwargs):
            calls["developer"] += 1
            return {"status": "error", "message": "session LlmUnavailable: endpoint down"}

        monkeypatch.setattr("workflow.task_runner.time.sleep", lambda _s: None)
        monkeypatch.setattr("workflow.task_runner.call_orchestrator", fake_orchestrator)
        monkeypatch.setattr("workflow.task_runner._dispatch_developer", fake_dispatch)
        mock_minimal_config["developer"] = {"implementation": "shell"}

        task_runner.run_task_cycle("net_loop_io", "fix the flaky test", max_turns=3)

        assert calls["orchestrator"] == 3
        assert calls["developer"] == 3

        with get_db_connection() as conn:
            crit = conn.execute("SELECT COUNT(*) FROM messages WHERE task_id = 'net_loop_io' AND priority = 'CRITICAL'").fetchone()[0]
        assert crit == 0


# ---------------------------------------------------------------------------
# End-to-end: full outage (orchestrator failsafe) pauses every other turn
# ---------------------------------------------------------------------------


class TestWiringFullOutage:
    def test_failsafe_outage_pauses_and_surfaces_single_critical(self, temp_db, mock_minimal_config, monkeypatch):
        from agents import resource_controller_worker
        from core.db_connection import get_db_connection
        from workflow import task_runner

        calls = {"orchestrator": 0}

        def fake_orchestrator(*_a, **_k):
            calls["orchestrator"] += 1
            return None

        monkeypatch.setattr("workflow.task_runner.time.sleep", lambda _s: None)
        monkeypatch.setattr("workflow.task_runner.call_orchestrator", fake_orchestrator)
        monkeypatch.setattr("agents.base.get_token_budget", lambda: FakeTokenBudget())
        monkeypatch.setattr(
            resource_controller_worker,
            "get_resource_controller",
            lambda: FakeNoop(),
        )
        monkeypatch.setattr("workflow.task_runner.get_agent_pool", lambda: FakePool())

        task_runner.run_task_cycle("net_loop_out", "fix everything", max_turns=5)

        # Active iterations 1, 2, 4 (turns 3 and 5 are paused). Each active
        # iteration retries the orchestrator 3x (max_orchestrator_retries).
        assert calls["orchestrator"] == 3 * 3

        with get_db_connection() as conn:
            crit = conn.execute(
                "SELECT COUNT(*) FROM messages WHERE task_id = 'net_loop_out' "
                "AND priority = 'CRITICAL' AND content LIKE '%pausing scheduling for one iteration%'"
            ).fetchone()[0]
        assert crit == 1
