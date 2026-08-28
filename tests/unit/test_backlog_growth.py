"""Workstream B — backlog consolidation under growth (§4).

Acceptance criteria (§4.6):
  1. Synthetic test: insert 100 near-duplicate findings → ≤ K rows retained.
  2. At simulated unaddressed>200, the agent pool does not start random
     feeder reviews.
  3. Metrics in project report: unaddressed, posted_this_hour,
     addressed_this_hour, stuck_ids.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from core.db_connection import get_db_connection
from core.db_helpers import backlog_metrics, mark_feedback_addressed, save_agent_feedback
from workflow.backlog import (
    apply_backlog_overrides,
    fetch_top_feedback,
    normalize_backlog_tiers,
    resolve_backlog_tier,
    tier_pool_policy,
)


def _insert_direct(conn, *, i: int = 0, task_id: str = "t", stuck: int = 0, **kw):
    conn.execute(
        """
        INSERT INTO agent_feedback
        (agent_name, file_path, priority, category, message, suggestion, task_id, addressed, stuck, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
        """,
        (
            kw.get("agent_name", "jr_reviewer"),
            kw.get("file_path", f"mod{i}.py"),
            kw.get("priority", "HIGH"),
            kw.get("category", "style"),
            kw.get("message", f"issue {i}"),
            kw.get("suggestion", f"fix {i}"),
            task_id,
            stuck,
            datetime.now().isoformat(),
        ),
    )


class TestDedupeOnInsert:
    def test_100_near_duplicate_findings_kept_rows(self, temp_db):
        # 100 findings that differ only in whitespace/case/punctuation, so
        # they share one normalized dedupe key.
        variants = ("Missing  timeout  on /login -- check!", "missing timeout on login - check", "Missing timeout on /login: check!")
        for i in range(100):
            save_agent_feedback(
                agent_name="jr_reviewer",
                file_path="auth.py",
                priority="HIGH",
                category="security",
                message=variants[i % len(variants)],
                suggestion="Add a timeout",
                task_id="t_dedupe",
                file_event_id=f"e{i}",
            )
        with get_db_connection() as conn:
            rows = conn.execute("SELECT id, dup_count FROM agent_feedback WHERE task_id = 't_dedupe'").fetchall()
            total = conn.execute("SELECT COUNT(*) FROM agent_feedback WHERE task_id = 't_dedupe'").fetchone()[0]
        assert total <= 5, f"expected near-duplicate collapse, kept {total} rows"
        assert len(rows) == 1 and rows[0][1] == 100

    def test_distinct_messages_stay_separate(self, temp_db):
        save_agent_feedback(
            agent_name="r",
            file_path="a.py",
            priority="LOW",
            category="style",
            message="rename variable",
            suggestion=None,
            task_id="t2",
            file_event_id="e1",
        )
        save_agent_feedback(
            agent_name="r",
            file_path="a.py",
            priority="LOW",
            category="style",
            message="add docstring",
            suggestion=None,
            task_id="t2",
            file_event_id="e2",
        )
        with get_db_connection() as conn:
            total = conn.execute("SELECT COUNT(*) FROM agent_feedback WHERE task_id = 't2'").fetchone()[0]
        assert total == 2

    def test_dedupe_respects_dedupe_window(self, temp_db):
        old = (datetime.now() - timedelta(hours=2)).isoformat()
        with get_db_connection() as conn:
            conn.execute(
                """
                INSERT INTO agent_feedback
                (agent_name, file_path, priority, category, message, task_id, addressed, dup_key, timestamp)
                VALUES ('r', 'a.py', 'HIGH', 'bug', 'same message', 't3', 0, ?, ?)
                """,
                ("same message", old),
            )
        save_agent_feedback(
            agent_name="r",
            file_path="a.py",
            priority="HIGH",
            category="bug",
            message="Same   MESSAGE",
            suggestion=None,
            task_id="t3",
            file_event_id="e9",
        )
        with get_db_connection() as conn:
            total = conn.execute("SELECT COUNT(*) FROM agent_feedback WHERE task_id = 't3'").fetchone()[0]
        assert total == 2, "row outside the dedupe window must not be refreshed"

    def test_dedupe_disabled_keeps_every_row(self, temp_db, mock_minimal_config):
        mock_minimal_config["feedback"] = {"dedupe": {"enabled": False}}
        for i in range(25):
            save_agent_feedback(
                agent_name="r",
                file_path="a.py",
                priority="HIGH",
                category="bug",
                message="same message",
                suggestion=None,
                task_id="t4",
                file_event_id=f"e{i}",
            )
        with get_db_connection() as conn:
            total = conn.execute("SELECT COUNT(*) FROM agent_feedback WHERE task_id = 't4'").fetchone()[0]
        assert total == 25


class TestTierPolicy:
    def test_resolve_boundaries(self, mock_minimal_config):
        assert resolve_backlog_tier(49) == "normal"
        assert resolve_backlog_tier(50) == "soft"
        assert resolve_backlog_tier(100) == "soft"
        assert resolve_backlog_tier(101) == "hard"
        assert resolve_backlog_tier(200) == "hard"
        assert resolve_backlog_tier(201) == "freeze"

    def test_config_overrides_tiers(self):
        cfg = {"feedback": {"tiers": {"soft_start": 10, "hard_start": 20, "freeze_at": 30}}}
        assert normalize_backlog_tiers(cfg) == {"soft_start": 10, "hard_start": 20, "freeze_at": 30}
        assert resolve_backlog_tier(31, cfg) == "freeze"
        assert resolve_backlog_tier(21, cfg) == "hard"
        assert resolve_backlog_tier(11, cfg) == "soft"

    def test_freeze_policy_disables_feeders(self):
        policy = tier_pool_policy("freeze")
        assert policy["background_feeders"] is False
        assert policy["level"] == "BACKLOG_PROCESSING"
        assert policy["active_agents"] == ["prioritizer"]

    def test_hard_policy_disables_feeders(self):
        policy = tier_pool_policy("hard")
        assert policy["background_feeders"] is False
        assert policy["level"] == "BACKLOG_WARNING"

    def test_soft_and_normal_keep_feeders(self):
        for tier in ("soft", "normal"):
            assert tier_pool_policy(tier)["background_feeders"] is True

    def test_resource_controller_freeze_at_unaddressed_200(self, temp_db, monkeypatch):
        # Simulated unaddressed > 200 → the pool must not start random feeders.
        monkeypatch.setattr(
            "agents.resource_controller_worker.get_config",
            lambda: {"feedback": {}},
        )
        from agents.resource_controller_worker import HeuristicOptimizer

        optimizer = HeuristicOptimizer()
        with get_db_connection() as conn:
            for i in range(220):
                _insert_direct(conn, i=i, task_id="t_rc")
        state = SimpleNamespace(api_rate_limit=60, budget_percentage=0.9)
        decision = optimizer._check_feedback_backlog(state)
        assert decision is not None
        assert decision.level == "BACKLOG_PROCESSING"
        assert decision.background_feeder_interval == 9999
        assert decision.active_agents == ["prioritizer"]


class TestStuckIdTracking:
    def test_repeated_targeting_marks_stuck_and_skips_it(self, temp_db):
        # Two items; the older one keeps getting targeted without success.
        # stuck_threshold comes from config defaults (3).
        with get_db_connection() as conn:
            _insert_direct(conn, i=0, task_id="t_stuck")
            _insert_direct(conn, i=1, task_id="t_stuck")
            for _ in range(4):
                decision = apply_backlog_overrides("t_stuck", {"next_agent": "developer"}, conn, force_threshold=0)
            assert decision["addressing_feedback_ids"] == [2], "second item should be targeted after first is stuck"
            stuck = conn.execute("SELECT id FROM agent_feedback WHERE task_id = 't_stuck' AND stuck = 1").fetchall()
            top = fetch_top_feedback(conn, "t_stuck")
        assert [r[0] for r in stuck] == [1], "first (oldest) item should be flagged stuck"
        assert top[3] == "mod1.py", "stuck item must not be re-selected"


class TestReportMetrics:
    def test_backlog_metrics_include_required_keys(self, temp_db):
        save_agent_feedback(
            agent_name="r",
            file_path="a.py",
            priority="HIGH",
            category="bug",
            message="open item",
            suggestion=None,
            task_id="t_m1",
            file_event_id="e1",
        )
        with get_db_connection() as conn:
            _insert_direct(conn, i=1, task_id="t_m1", stuck=1)
            metrics = backlog_metrics(conn, task_id="t_m1")
        assert set(metrics) == {"unaddressed", "posted_this_hour", "addressed_this_hour", "stuck_ids"}
        assert metrics["unaddressed"] == 2
        assert metrics["addressed_this_hour"] == 0
        assert metrics["stuck_ids"] == [2]

    def test_pending_addressed_and_critical_do_not_break_metrics(self, temp_db):
        save_agent_feedback(
            agent_name="r",
            file_path="c.py",
            priority="CRITICAL",
            category="security",
            message="critical open",
            suggestion=None,
            task_id="t_m2",
            file_event_id="e3",
        )
        mark_feedback_addressed([], "developer")
        with get_db_connection() as conn:
            metrics = backlog_metrics(conn, task_id="t_m2")
        assert metrics["unaddressed"] == 1

    def test_reporter_gather_embeds_backlog_metrics(self, temp_db, mock_minimal_config):
        from agents.reporter_worker import ProjectReporterWorker

        save_agent_feedback(
            agent_name="r",
            file_path="a.py",
            priority="HIGH",
            category="bug",
            message="reported item",
            suggestion=None,
            task_id="t_rep",
            file_event_id="e5",
        )
        reporter = ProjectReporterWorker()
        data = reporter._gather_report_data()
        assert "backlog_metrics" in data
        assert data["backlog_metrics"]["unaddressed"] >= 1
        prompt = reporter._build_prompt(data)
        assert "Backlog Health" in prompt
        assert "Unaddressed:" in prompt

    def test_reporter_run_metrics_success_ratio_and_git_fails(self, temp_db, mock_minimal_config):
        from agents.reporter_worker import ProjectReporterWorker

        now = datetime.now().isoformat()
        with get_db_connection() as conn:
            for pid, status, fallback in (
                ("m1", "applied", 0),
                ("m2", "applied", 1),
                ("m3", "git_failed", 0),
            ):
                conn.execute(
                    """
                    INSERT INTO edit_proposals
                    (proposal_id, task_id, target_file_path, edit_payload, status,
                     selected_mode, fallback_used, final_mode, created_at, rationale)
                    VALUES (?,?,?,?,?,?,?,?,?,?)
                    """,
                    (pid, "t_rm", "app.py", "{}", status, "find_replace", fallback, "find_replace", now, "long enough rationale"),
                )
                if status == "git_failed":
                    conn.execute(
                        "INSERT INTO events (task_id, ts, type, source, payload_json, proposal_id) VALUES (?,?,?,?,?,?)",
                        ("t_rm", now, "edit.git_failed", "developer", '{"stage":"pre-commit","code":1}', pid),
                    )

        reporter = ProjectReporterWorker()
        data = reporter._gather_report_data()
        rm = data["run_metrics"]
        assert rm["materialize_total"] == 3
        assert rm["materialize_success"] == 2
        assert rm["materialize_success_ratio"] == pytest.approx(2 / 3)
        assert rm["fallback_rate"] == pytest.approx(1 / 3)
        assert rm["git_fail_count"] == 1

        prompt = reporter._build_prompt(data)
        assert "Run Metrics" in prompt
        assert "Proposals: 3" in prompt
        assert "Git failures: 1" in prompt
        assert "Circuit opens: 0" in prompt

    def test_reporter_counts_circuit_opens(self, temp_db, mock_minimal_config):
        from datetime import datetime

        from agents.reporter_worker import ProjectReporterWorker

        now = datetime.now().isoformat()
        with get_db_connection() as conn:
            conn.execute(
                "INSERT INTO events (task_id, ts, type, source, payload_json, proposal_id) VALUES (?,?,?,?,?,?)",
                ("t_cb", now, "prioritizer.circuit_open", "prioritizer_worker", '{"cooldown_seconds":120}', None),
            )

        reporter = ProjectReporterWorker()
        data = reporter._gather_report_data()
        assert data["run_metrics"]["circuit_open_count"] == 1
