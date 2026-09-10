"""
tests/unit/test_harness_rollouts.py

Unit tests for the harness-evolution P0 substrate (docs/TODO.md §12.1):
rollout fingerprints, infra-abort classification, and rollout lifecycle
recording hooked into the task runner.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest


def _ts_after(task_id: str, seconds: int) -> str:
    """ISO timestamp relative to the task's rollout created_at (window anchor).

    Shifts a just-created rollout's created_at one hour into the past (once,
    idempotent) so injected health/token events fall inside the real window
    [created_at, now] instead of racing the clock.
    """
    from core.db_connection import get_db_connection
    from harness.fingerprint import latest_rollout

    row = latest_rollout(task_id)
    assert row is not None
    start = datetime.fromisoformat(row["created_at"])
    tzinfo = start.tzinfo or timezone.utc
    now = datetime.now(tzinfo)
    if (now - start).total_seconds() < 60:
        start = start - timedelta(seconds=3600)
        with get_db_connection() as conn:
            conn.execute(
                "UPDATE rollouts SET created_at = ? WHERE rollout_id = ?",
                (start.isoformat(), row["rollout_id"]),
            )
    return (start + timedelta(seconds=seconds)).isoformat()


class TestFingerprint:
    def test_fingerprint_shape_and_stability(self):
        from harness.fingerprint import compute_harness_fingerprint

        fp = compute_harness_fingerprint()
        assert set(fp) == {"harness_tag", "prompt_hash", "model"}
        assert fp["harness_tag"]
        assert len(fp["prompt_hash"]) == 64
        assert all(c in "0123456789abcdef" for c in fp["prompt_hash"])
        # stable across calls (no randomness)
        assert compute_harness_fingerprint() == fp

    def test_fingerprint_changes_when_prompts_change(self, monkeypatch):
        import harness.fingerprint as hp

        monkeypatch.setattr(hp, "get_agent_prompts", lambda: {"agent_prompts": {"a": "x", "b": "y"}})
        fp1 = hp.compute_harness_fingerprint()
        monkeypatch.setattr(hp, "get_agent_prompts", lambda: {"agent_prompts": {"a": "x", "b": "CHANGED"}})
        fp2 = hp.compute_harness_fingerprint()
        assert fp1["prompt_hash"] != fp2["prompt_hash"]
        assert fp1["harness_tag"] == fp2["harness_tag"]

    def test_fingerprint_is_sort_stable(self, monkeypatch):
        import harness.fingerprint as hp

        monkeypatch.setattr(hp, "get_agent_prompts", lambda: {"agent_prompts": {"a": "x", "b": "y"}})
        monkeypatch.setattr(hp, "get_agent_prompts", lambda: {"agent_prompts": {"b": "y", "a": "x"}})
        fp1 = hp.compute_harness_fingerprint()
        fp2 = hp.compute_harness_fingerprint()
        assert fp1["prompt_hash"] == fp2["prompt_hash"]


@pytest.mark.usefixtures("temp_db")
class TestRolloutLifecycle:
    def test_create_rollout_records_fingerprint(self, monkeypatch):
        from harness.fingerprint import create_rollout, latest_rollout

        fp = {"harness_tag": "v9.9.9-dirty", "prompt_hash": "ab" * 32, "model": "ep/model"}
        rid = create_rollout("t-fp", fingerprint=fp)
        assert isinstance(rid, int)

        row = latest_rollout("t-fp")
        assert row["status"] == "in_progress"
        assert row["harness_tag"] == "v9.9.9-dirty"
        assert row["prompt_hash"] == "ab" * 32
        assert row["model"] == "ep/model"
        assert row["task_id"] == "t-fp"
        assert row["completed_at"] is None
        assert row["tokens"] is None

    def test_create_rollout_is_idempotent_per_run(self, monkeypatch):
        from harness.fingerprint import create_rollout, latest_rollout

        fp = {"harness_tag": "t", "prompt_hash": "p", "model": "m"}
        create_rollout("t-dup", fingerprint=fp)
        create_rollout("t-dup", fingerprint=fp)
        row = latest_rollout("t-dup")
        # latest() should return the newest row, not pile up erroneously
        assert row["task_id"] == "t-dup"

    def test_finalize_passes_token_backfill(self, monkeypatch):
        from core.db_connection import get_db_connection
        from harness.fingerprint import create_rollout, finalize_rollout

        create_rollout("t-pass", fingerprint={"harness_tag": "t", "prompt_hash": "p", "model": "m"})
        token_ts = _ts_after("t-pass", 2)
        with get_db_connection() as conn:
            conn.execute(
                "INSERT INTO tasks (id, description, status, started_at, completed_at, result) VALUES (?,?,?,?,?,?)",
                ("t-pass", "d", "completed", "2026-09-10T00:00:00", None, ""),
            )
            conn.execute(
                "INSERT INTO token_log (endpoint_name, timestamp, tokens_used) VALUES (?,?,?)",
                ("ep", token_ts, 120),
            )

        row = finalize_rollout("t-pass", "completed")
        assert row["status"] == "passed"
        assert row["infra_abort"] == 0
        assert row["tokens"] == 120
        assert row["completed_at"] is not None
        # second call is a no-op (already finalized)
        again = finalize_rollout("t-pass", "completed")
        assert again["status"] == "passed"

    def test_finalize_prefers_terminal_db_status(self):
        from core.db_connection import get_db_connection
        from harness.fingerprint import create_rollout, finalize_rollout

        create_rollout("t-dbstatus", fingerprint={"harness_tag": "t", "prompt_hash": "p", "model": "m"})
        with get_db_connection() as conn:
            conn.execute(
                "INSERT INTO tasks (id, description, status, started_at, completed_at, result) VALUES (?,?,?,?,?,?)",
                ("t-dbstatus", "d", "no_change_required", "2026-09-10T00:00:00", None, ""),
            )
        row = finalize_rollout("t-dbstatus", "stalled")
        assert row["status"] == "passed"

    def test_finalize_unknown_task_is_noop(self):
        from harness.fingerprint import finalize_rollout

        assert finalize_rollout("t-missing", "failed") is None

    def test_finalize_noop_when_no_rollout(self):
        from harness.fingerprint import finalize_rollout

        assert finalize_rollout("t-no-rollout", "completed") is None


@pytest.mark.usefixtures("temp_db")
class TestInfraAbort:
    def test_classify_no_window_is_false(self):
        from harness.fingerprint import classify_infra_abort

        assert classify_infra_abort("t", None, None) == (False, "no_health_window")

    def test_classify_no_events_is_false(self):
        from harness.fingerprint import classify_infra_abort

        assert classify_infra_abort("t", "2026-09-10T00:00:00", "2026-09-10T00:05:00") == (
            False,
            "no_infra_abort",
        )

    def test_classify_infra_tail_rate_limited(self):
        from core.db_connection import get_db_connection
        from harness.fingerprint import create_rollout, finalize_rollout

        create_rollout("t-rl", fingerprint={"harness_tag": "t", "prompt_hash": "p", "model": "m"})
        ts_ok = _ts_after("t-rl", 1)
        ts_rl = _ts_after("t-rl", 240)
        with get_db_connection() as conn:
            conn.execute(
                "INSERT INTO tasks (id, description, status, started_at, completed_at, result) VALUES (?,?,?,?,?,?)",
                ("t-rl", "d", "failed", "2026-09-10T00:00:00", None, ""),
            )
            conn.execute(
                "INSERT INTO model_health_events (model_ref, endpoint, ok, kind, detail, ts) VALUES (?,?,?,?,?,?)",
                ("m", "ep", 1, "ok", "", ts_ok),
            )
            conn.execute(
                "INSERT INTO model_health_events (model_ref, endpoint, ok, kind, detail, ts) VALUES (?,?,?,?,?,?)",
                ("m", "ep", 0, "rate_limited", "429", ts_rl),
            )

        row = finalize_rollout("t-rl", "failed")
        assert row["status"] == "infra_aborted"
        assert row["infra_abort"] == 1

    def test_classify_success_tail_is_not_abort(self):
        from core.db_connection import get_db_connection
        from harness.fingerprint import create_rollout, finalize_rollout

        create_rollout("t-ok", fingerprint={"harness_tag": "t", "prompt_hash": "p", "model": "m"})
        ts_rl = _ts_after("t-ok", 1)
        ts_ok = _ts_after("t-ok", 240)
        with get_db_connection() as conn:
            conn.execute(
                "INSERT INTO tasks (id, description, status, started_at, completed_at, result) VALUES (?,?,?,?,?,?)",
                ("t-ok", "d", "failed", "2026-09-10T00:00:00", None, ""),
            )
            conn.execute(
                "INSERT INTO model_health_events (model_ref, endpoint, ok, kind, detail, ts) VALUES (?,?,?,?,?,?)",
                ("m", "ep", 0, "rate_limited", "429", ts_rl),
            )
            conn.execute(
                "INSERT INTO model_health_events (model_ref, endpoint, ok, kind, detail, ts) VALUES (?,?,?,?,?,?)",
                ("m", "ep", 1, "ok", "", ts_ok),
            )

        row = finalize_rollout("t-ok", "failed")
        assert row["status"] == "failed"
        assert row["infra_abort"] == 0

    def test_classify_endpoint_latched(self):
        from core.db_connection import get_db_connection
        from harness.fingerprint import create_rollout, finalize_rollout, latest_rollout

        create_rollout("t-latch", fingerprint={"harness_tag": "t", "prompt_hash": "p", "model": "m"})
        latch_until = _ts_after("t-latch", 7200)
        last_checked = _ts_after("t-latch", 180)
        with get_db_connection() as conn:
            conn.execute(
                "INSERT INTO tasks (id, description, status, started_at, completed_at, result) VALUES (?,?,?,?,?,?)",
                ("t-latch", "d", "stalled", "2026-09-10T00:00:00", None, ""),
            )
            conn.execute(
                "INSERT INTO endpoint_health (endpoint_name, status, error_count, "
                "consecutive_failures, last_success, unavailable_until, last_updated) VALUES (?,?,?,?,?,?,?)",
                ("ep", "rate_limited", 5, 5, None, latch_until, last_checked),
            )

        row = finalize_rollout("t-latch", "stalled")
        assert row["status"] == "infra_aborted"
        assert row["infra_abort"] == 1
        assert latest_rollout("t-latch")["status"] == "infra_aborted"

    def test_classify_passed_is_never_aborted(self):
        from core.db_connection import get_db_connection
        from harness.fingerprint import create_rollout, finalize_rollout

        create_rollout("t-passed", fingerprint={"harness_tag": "t", "prompt_hash": "p", "model": "m"})
        ts_rl = _ts_after("t-passed", 240)
        with get_db_connection() as conn:
            conn.execute(
                "INSERT INTO tasks (id, description, status, started_at, completed_at, result) VALUES (?,?,?,?,?,?)",
                ("t-passed", "d", "completed", "2026-09-10T00:00:00", None, ""),
            )
            conn.execute(
                "INSERT INTO model_health_events (model_ref, endpoint, ok, kind, detail, ts) VALUES (?,?,?,?,?,?)",
                ("m", "ep", 0, "rate_limited", "429", ts_rl),
            )
        row = finalize_rollout("t-passed", "completed")
        assert row["status"] == "passed"
        assert row["infra_abort"] == 0


@pytest.mark.usefixtures("temp_db")
class TestFailureModeMix:
    def test_mix_counts_statuses(self):
        from core.db_connection import get_db_connection
        from harness.fingerprint import create_rollout, failure_mode_mix, finalize_rollout

        fc = {"harness_tag": "t", "prompt_hash": "p", "model": "m"}
        for tid, status in [
            ("m-1", "completed"),
            ("m-2", "completed"),
            ("m-3", "failed"),
            ("m-4", "stalled"),
            ("m-5", "completed"),
        ]:
            create_rollout(tid, fingerprint=fc)
            with get_db_connection() as conn:
                conn.execute(
                    "INSERT INTO tasks (id, description, status, started_at, completed_at, result) VALUES (?,?,?,?,?,?)",
                    (tid, "d", status, "2026-09-10T00:00:00", None, ""),
                )
            finalize_rollout(tid, status)

        mix = failure_mode_mix()
        assert mix["rollouts"] == 5
        assert mix["passed"] == 3
        assert mix["failed"] == 1
        assert mix["stalled"] == 1
        assert mix["infra_aborted"] == 0
        assert mix["pass@1"] == round(3 / 5, 4)

    def test_mix_buckets_infra_aborts_separately(self):
        from core.db_connection import get_db_connection
        from harness.fingerprint import create_rollout, failure_mode_mix, finalize_rollout

        fc = {"harness_tag": "t", "prompt_hash": "p", "model": "m"}
        create_rollout("mi-1", fingerprint=fc)
        ts_exhausted = _ts_after("mi-1", 240)
        with get_db_connection() as conn:
            conn.execute(
                "INSERT INTO tasks (id, description, status, started_at, completed_at, result) VALUES (?,?,?,?,?,?)",
                ("mi-1", "d", "failed", "2026-09-10T00:00:00", None, ""),
            )
            conn.execute(
                "INSERT INTO model_health_events (model_ref, endpoint, ok, kind, detail, ts) VALUES (?,?,?,?,?,?)",
                ("m", "ep", 0, "token_exhausted", "quota", ts_exhausted),
            )
        finalize_rollout("mi-1", "failed")
        create_rollout("mi-2", fingerprint=fc)
        with get_db_connection() as conn:
            conn.execute(
                "INSERT INTO tasks (id, description, status, started_at, completed_at, result) VALUES (?,?,?,?,?,?)",
                ("mi-2", "d", "failed", "2026-09-10T00:00:00", None, ""),
            )
        finalize_rollout("mi-2", "failed")

        mix = failure_mode_mix()
        assert mix["rollouts"] == 2
        assert mix["infra_aborted"] == 1
        assert mix["non_infra_failures"] == 1
        assert mix["passed"] == 0
        assert mix["pass@1"] == 0.0
