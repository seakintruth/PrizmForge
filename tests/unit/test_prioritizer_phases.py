"""Prioritizer scoring, ranking, and post_results (no long-lived worker)."""

from __future__ import annotations

import json

from agents.prioritizer_worker import FeedbackItem, PrioritizerWorker


def _fb(
    raw_id: int,
    *,
    message: str = "Concrete null-check gap in parser",
    category: str = "bug",
    priority: str = "HIGH",
    score: float = 0.0,
    file_path: str = "app.py",
) -> FeedbackItem:
    return FeedbackItem(
        id=str(raw_id),
        from_agent="jr_reviewer",
        file_path=file_path,
        priority=priority,
        category=category,
        message=message,
        suggestion="add guard",
        timestamp="2026-01-01T00:00:00",
        raw_id=raw_id,
        item_type="feedback",
        score=score,
    )


def test_score_category_applies_mock_scores(mock_llm, temp_db):
    worker = PrioritizerWorker()
    worker.current_task_id = "t_score"
    items = [_fb(1, message="Critical auth bypass path"), _fb(2, message="Minor style nit in imports")]

    mock_llm.set_response(
        "prioritizer",
        json.dumps({"scored": [{"id": "1", "score": 95}, {"id": "2", "score": 20}]}),
    )
    with mock_llm.patch_call_agent():
        worker._score_category("bug", items)

    by_id = {i.id: i.score for i in items}
    assert by_id["1"] == 95
    assert by_id["2"] == 20


def test_cross_category_ranking_fallback_sorts_by_score(mock_llm, temp_db):
    """When ranking LLM returns nothing, top items by score are kept."""
    worker = PrioritizerWorker()
    worker.current_task_id = "t_rank"
    by_cat = {
        "bug": [_fb(1, score=10), _fb(2, score=90)],
        "style": [_fb(3, score=50, category="style")],
    }
    mock_llm.set_response("prioritizer", "")  # empty → fallback sort
    with mock_llm.patch_call_agent():
        ranked = worker._cross_category_ranking(by_cat)

    assert ranked
    assert ranked[0].score >= ranked[-1].score
    assert ranked[0].id == "2"


def test_cross_category_ranking_uses_llm_order(mock_llm, temp_db):
    worker = PrioritizerWorker()
    worker.current_task_id = "t_rank2"
    by_cat = {"bug": [_fb(1, score=10), _fb(2, score=90)]}
    mock_llm.set_response(
        "prioritizer",
        json.dumps(
            {
                "top_suggestions": [
                    {"id": "1", "final_score": 150, "rank": 1},
                    {"id": "2", "final_score": 40, "rank": 2},
                ]
            }
        ),
    )
    with mock_llm.patch_call_agent():
        ranked = worker._cross_category_ranking(by_cat)

    assert [r.id for r in ranked] == ["1", "2"]
    assert ranked[0].score == 150


def test_post_results_writes_orchestrator_message(temp_db):
    worker = PrioritizerWorker()
    worker.current_task_id = "t_post"
    worker._post_results([_fb(7, score=88, message="Ship blocker in login flow")])

    from core.db_connection import get_db_connection

    with get_db_connection() as conn:
        row = conn.execute("""
            SELECT from_agent, to_agent, content, priority
            FROM messages
            WHERE task_id = 't_post'
            ORDER BY id DESC LIMIT 1
            """).fetchone()
    assert row is not None
    assert row[0] == "prioritizer"
    assert row[1] == "orchestrator"
    assert "PRIORITIZED" in row[2] or "login" in row[2].lower()
    assert row[3] == "HIGH"
