"""Tests for prioritizer circuit breaker (soak P2 fix).

Soak evidence: 1,071 prioritizer API errors in bursts of up to 31/s — a failed
batch advanced the loop instantly, so an endpoint outage turned one cycle into
~17 rapid failing batches, repeated every cycle.
"""

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


def _make_worker(monkeypatch, fail_batches=True, n_items=90):
    w = PrioritizerWorker()
    calls = {"n": 0}

    def fake_batch(batch):
        calls["n"] += 1
        return fail_batches  # True == success

    monkeypatch.setattr(w, "_categorize_batch", fake_batch)
    monkeypatch.setattr(w, "_get_all_feedback", lambda: [FakeItem(i) for i in range(n_items)])
    monkeypatch.setattr(w, "_filter_low_quality_feedback", lambda items: (items, 0))
    monkeypatch.setattr(w, "_score_within_categories", lambda items: {})
    monkeypatch.setattr(w, "_cross_category_ranking", lambda by_cat: [])
    monkeypatch.setattr(w, "_post_results", lambda ranked: None)
    monkeypatch.setattr("agents.prioritizer_worker.time.sleep", lambda s: None)
    return w, calls


def test_all_items_categorized_skips_api(temp_db, monkeypatch):
    """When nothing is uncategorized, no batches are attempted at all."""
    w = PrioritizerWorker()
    monkeypatch.setattr(w, "_get_all_feedback", lambda: [FakeItem(0)])
    # mark item categorized via the worker's own categorize step
    item = w._get_all_feedback()[0]
    item.category = "bug"
    calls = {"n": 0}

    def fake_batch(batch):
        calls["n"] += 1
        return True

    monkeypatch.setattr(w, "_categorize_batch", fake_batch)
    result = w._categorize_feedback([item])
    assert calls["n"] == 0
    assert result == [item]


def test_circuit_breaker_aborts_after_consecutive_failures(temp_db, monkeypatch):
    w, calls = _make_worker(monkeypatch, fail_batches=False, n_items=150)  # False == failing batches

    # _categorize_batch returns False → failure; breaker must stop the loop
    # after max_consecutive failures instead of running all 5 batches.
    w._run_full_prioritization_cycle()
    assert calls["n"] == 3, f"expected abort after 3 batches, ran {calls['n']}"
    assert w.circuit_open_until > 0


def test_successful_batches_do_not_trip_breaker(temp_db, monkeypatch):
    w, calls = _make_worker(monkeypatch, fail_batches=True)  # True == success
    w._run_full_prioritization_cycle()
    assert calls["n"] == 3  # 90 items / batch size 30
    assert w.circuit_open_until == 0


def test_open_circuit_probes_single_batch(temp_db, monkeypatch):
    """Open circuit no longer idles: the next cycle runs exactly ONE probe batch."""
    import agents.prioritizer_worker as pw

    w, calls = _make_worker(monkeypatch, fail_batches=False)  # False == failing
    w.circuit_open_until = pw.time.time() + 9999
    w._run_full_prioritization_cycle()
    assert calls["n"] == 1  # probe, not full cycle (would be 3)
    # a single failed probe does not clear the armed circuit
    assert w.circuit_open_until > pw.time.time()


def test_successful_probe_reopens_circuit(temp_db, monkeypatch):
    import agents.prioritizer_worker as pw

    w, _calls = _make_worker(monkeypatch, fail_batches=True)
    w.circuit_open_until = pw.time.time() + 9999
    monkeypatch.setattr(w, "_categorize_batch", lambda b: True)  # probe succeeds
    w._run_full_prioritization_cycle()
    assert w.circuit_open_until == 0.0
    assert w.consecutive_batch_failures == 0
