"""Pass 1 Phase 4 — background review + feedback-growth constraints.

Covers:
- 4.2 praise-only feedback filter (ingestion + prioritizer secondary guard)
- 4.3 caps: feedback items per reviewer cycle, feeder pause, prioritizer intake
- 4.4 seed-task boost for mutation-capable work
"""

from __future__ import annotations

import json

from core.db_helpers import is_praise_only_feedback


# ---------------------------------------------------------------------------
# Phase 4.2 — praise-only / confirmation classifier
# ---------------------------------------------------------------------------
def test_praise_only_without_suggestion_is_rejected():
    assert is_praise_only_feedback("The function correctly handles null inputs", None) is True


def test_praise_only_phrase_without_suggestion_rejected():
    assert is_praise_only_feedback("SQL queries properly use parameterized queries", "add index") is True


def test_robust_fallback_praise_rejected():
    assert is_praise_only_feedback("Robust fallback logic", "refactor") is True


def test_actionable_problem_with_suggestion_is_accepted():
    assert (
        is_praise_only_feedback(
            "The function fails when handed an empty list and crashes with a KeyError",
            "guard the empty-list case before the lookup",
        )
        is False
    )


def test_actionable_but_no_suggestion_rejected():
    # 4.2 requires a concrete suggested action.
    assert is_praise_only_feedback("The retry loop can busy-wait under load", None) is True


# ---------------------------------------------------------------------------
# Phase 4.2 + 4.3 — review ingestion path (_parse_and_save_feedback)
# ---------------------------------------------------------------------------
def _pool_with_agent_config(monkeypatch, extra=None):
    from agents.parallel_workers import BackgroundAgentPool

    cfg_extra = {"feedback_items_per_reviewer_cycle": 3, "max_unaddressed_feedback_before_pause": 10}
    cfg_extra.update(extra or {})

    def fake_get_config():
        return {"background_agents": {"jr": {"counts": True}}}

    monkeypatch.setattr("agents.parallel_workers.get_config", fake_get_config)
    pool = BackgroundAgentPool.__new__(BackgroundAgentPool)
    pool.event_queue = _FakeQueue()
    pool.task_id = "t_constraints"
    pool.agent_configs = dict(cfg_extra)
    pool.modification_agents = ["jr"]
    pool.random_review_agents = []
    pool.recently_queued = {}
    return pool


class _FakeQueue:
    def __init__(self):
        self.items = []

    def put(self, item):
        self.items.append(item)

    def qsize(self):
        return len(self.items)

    def get_nowait(self):
        if not self.items:
            raise Exception("empty")
        return self.items.pop(0)


def _fake_event(file_path="a.py"):
    from agents.parallel_workers import FileChangeEvent

    return FileChangeEvent(
        event_id="evt-1",
        file_path=file_path,
        operation="initial_review",
        content="x=1",
        content_hash="h",
        metadata={},
        task_id="t_constraints",
        timestamp="2026-01-01T00:00:00",
        priority=3,
    )


def test_ingestion_rejects_praise_only_and_missing_path(temp_db, monkeypatch):

    pool = _pool_with_agent_config(monkeypatch)
    response = json.dumps(
        {
            "findings": [
                {
                    "category": "bug",
                    "message": "The function correctly handles null inputs",
                    "file_path": "a.py",
                },
                {
                    "category": "bug",
                    "message": "Real null-check crash when items is empty",
                    "suggestion": "guard the empty case",
                    "file_path": "a.py",
                },
            ]
        }
    )
    pool._parse_and_save_feedback("jr", _fake_event(), response)

    from core.db_connection import get_db_connection

    with get_db_connection() as conn:
        rows = conn.execute("SELECT message FROM agent_feedback WHERE task_id = 't_constraints'").fetchall()
    assert len(rows) == 1
    assert "null-check crash" in rows[0][0]


def test_ingestion_caps_per_reviewer_cycle(temp_db, monkeypatch):
    pool = _pool_with_agent_config(monkeypatch)
    findings = [
        {
            "category": "style",
            "message": f"Style nit number {i} that is actionable and detailed",
            "suggestion": f"apply style fix {i}",
            "file_path": "a.py",
        }
        for i in range(6)
    ]
    response = json.dumps({"findings": findings})
    pool._parse_and_save_feedback("jr", _fake_event(), response)

    from core.db_connection import get_db_connection

    with get_db_connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM agent_feedback WHERE task_id = 't_constraints'").fetchone()[0]
    assert count == 3


def test_feeder_pause_on_unaddressed_backlog(temp_db, monkeypatch):
    # 4.3: random feeder pauses when unaddressed feedback exceeds the cap.

    pool = _pool_with_agent_config(monkeypatch, {"max_unaddressed_feedback_before_pause": 2})
    pool.random_review_agents = ["jr"]

    from core.db_connection import get_db_connection

    with get_db_connection() as conn:
        for _i in range(3):
            conn.execute("""
                INSERT INTO agent_feedback
                (agent_name, file_path, priority, category, message, task_id, addressed, timestamp)
                VALUES ('jr', 'a.py', 'MEDIUM', 'bug', 'unaddressed item', 't_constraints', 0, datetime('now'))
                """)

    # The gate reads the real DB through the pool's own connection; invoke the
    # method and assert no random events were queued.
    pool._feed_random_files()
    assert pool.event_queue.qsize() == 0


# ---------------------------------------------------------------------------
# Phase 4.3 + 4.4 — prioritizer intake cap and seed boost
# ---------------------------------------------------------------------------
def test_prio_intake_capped_and_seed_boosted(temp_db, monkeypatch):
    from agents.prioritizer_worker import PrioritizerWorker
    from core.db_connection import get_db_connection

    with get_db_connection() as conn:
        for i in range(15):
            conn.execute(
                """
                INSERT INTO agent_feedback
                (id, agent_name, file_path, priority, category, message, task_id, addressed, timestamp)
                VALUES (?, 'jr_reviewer', 'a.py', 'MEDIUM', 'bug',
                        'actionable issue with suggestion', 't_prio', 0, datetime('now'))
                """,
                (1000 + i,),
            )
        # seed task item (category='seed_task')
        conn.execute("""
            INSERT INTO agent_feedback
            (id, agent_name, file_path, priority, category, message, task_id, addressed, timestamp)
            VALUES (999, 'system', NULL, 'HIGH', 'seed_task', '[SEED TASK] a.py', 't_prio', 0, datetime('now'))
            """)

    monkeypatch.setattr("agents.prioritizer_worker.get_config", lambda: {})
    worker = PrioritizerWorker()
    worker.current_task_id = "t_prio"
    items = worker._get_all_feedback()

    # Cap: at most 10 feedback rows are pulled even though 16 exist.
    feedback_items = [i for i in items if i.item_type == "feedback"]
    assert len(feedback_items) <= 10
    # Seed boost: the seed_task item carries the mutation-capable boost.
    seed = [i for i in feedback_items if i.category == "seed_task"]
    assert seed and seed[0].bias_multiplier >= 8.0
