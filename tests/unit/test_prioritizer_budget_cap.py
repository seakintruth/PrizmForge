"""Tests for prioritizer per-cycle batch cap.

Soak evidence: each prioritization cycle processed all 267 uncategorized
items in one go -- 9 batches x 1 API call each = 9 calls, plus 8 scoring
calls = 17+ calls per cycle, all competing with the developer for rate
limit. Capping at 3 batches per cycle (90 items) limits API consumption
and lets items carry over to the next cycle.
"""

from __future__ import annotations

from agents.prioritizer_worker import PrioritizerWorker


class FakeItem:
    def __init__(self, i):
        self.id = f"fb_{i}"
        self.category = "uncategorized"
        self.file_path = None
        self.from_agent = "reviewer"
        self.priority = "LOW"
        self.message = f"issue {i}"
        self.suggestion = None
        self.raw_id = i
        self.bias_multiplier = 1.0
        self.score = 0.0


def _make_worker(monkeypatch, n_items=100):
    w = PrioritizerWorker()
    batch_calls = {"n": 0}

    def fake_batch(batch):
        batch_calls["n"] += 1
        return True  # success

    monkeypatch.setattr(w, "_categorize_batch", fake_batch)
    monkeypatch.setattr(w, "_get_all_feedback", lambda: [FakeItem(i) for i in range(n_items)])
    monkeypatch.setattr(w, "_filter_low_quality_feedback", lambda items: (items, 0))
    monkeypatch.setattr(w, "_score_within_categories", lambda items: {})
    monkeypatch.setattr(w, "_cross_category_ranking", lambda by_cat: [])
    monkeypatch.setattr(w, "_post_results", lambda ranked: None)
    monkeypatch.setattr("agents.prioritizer_worker.time.sleep", lambda s: None)
    return w, batch_calls


class TestPrioritizerBatchCap:
    def test_caps_at_max_batches_per_cycle(self, monkeypatch):
        """With 100 uncategorized items, only MAX_BATCHES_PER_CYCLE batches run."""
        w, batch_calls = _make_worker(monkeypatch, n_items=100)
        w.consecutive_batch_failures = 0
        w.circuit_open_until = 0.0

        items = [FakeItem(i) for i in range(100)]
        w._categorize_feedback(items)

        max_batches = getattr(w, "max_batches_per_cycle", 3)
        assert batch_calls["n"] <= max_batches

    def test_all_items_when_under_cap(self, monkeypatch):
        """With fewer items than the cap, all batches run."""
        w, batch_calls = _make_worker(monkeypatch, n_items=50)
        w.consecutive_batch_failures = 0
        w.circuit_open_until = 0.0

        items = [FakeItem(i) for i in range(50)]
        w._categorize_feedback(items)

        # 50 items / 30 per batch = 2 batches
        assert batch_calls["n"] == 2

    def test_probe_mode_still_single_batch(self, monkeypatch):
        """In probe mode, exactly one batch runs regardless of cap."""
        w, batch_calls = _make_worker(monkeypatch, n_items=100)
        w.consecutive_batch_failures = 0
        w.circuit_open_until = 0.0

        items = [FakeItem(i) for i in range(100)]
        w._categorize_feedback(items, probe_mode=True)

        assert batch_calls["n"] == 1

    def test_no_batches_when_all_categorized(self, monkeypatch):
        """When nothing is uncategorized, zero batches run."""
        w, batch_calls = _make_worker(monkeypatch, n_items=10)
        items = [FakeItem(i) for i in range(10)]
        for item in items:
            item.category = "bug"

        w._categorize_feedback(items)
        assert batch_calls["n"] == 0
