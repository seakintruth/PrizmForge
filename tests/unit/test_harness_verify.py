"""
tests/unit/test_harness_verify.py

Unit tests for the §12.2 verifier (docs/benchmark_v1.md §3): verdict rules,
infra-abort exclusion, content assertions, and verdict recording onto
rollouts rows.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def rename_task():
    from harness.benchmark.tasks import parse_bench_task

    return parse_bench_task(
        {
            "task_id": "t01_rename_constant",
            "seed": "Rename OLD to NEW in app.py",
            "fixture": {"app.py": "value = OLD\n"},
            "contract": [{"file_path": "app.py", "fragment": "value = NEW\n", "mode": "contains"}],
        }
    )


class TestVerdictRules:
    def test_no_rollout_fails(self, rename_task):
        from harness.verify import FAILED, verify_trial

        v = verify_trial(rename_task, None)
        assert v.verdict == FAILED
        assert v.note == "no_rollout"
        assert v.component_hint == "verifier"

    def test_infra_abort_rollout_is_infra_aborted(self, rename_task):
        from harness.verify import INFRA_ABORTED, verify_trial

        v = verify_trial(rename_task, {"infra_abort": 1, "status": "failed"})
        assert v.verdict == INFRA_ABORTED
        assert v.component_hint == "endpoint"

    def test_infra_aborted_status_is_infra_aborted(self, rename_task):
        from harness.verify import INFRA_ABORTED, verify_trial

        v = verify_trial(rename_task, {"infra_abort": 0, "status": "infra_aborted"})
        assert v.verdict == INFRA_ABORTED

    def test_non_passed_status_fails(self, rename_task):
        from harness.verify import FAILED, verify_trial

        for status in ("failed", "stalled", "timed_out", "cancelled"):
            v = verify_trial(rename_task, {"infra_abort": 0, "status": status})
            assert v.verdict == FAILED
            assert v.note == f"status:{status}"
            assert v.component_hint == "task_contract"

    def test_passed_without_content_fails(self, rename_task):
        from harness.verify import FAILED, verify_trial

        # No DB rows for app.py -> get_file_content_from_db returns None
        v = verify_trial(rename_task, {"infra_abort": 0, "status": "passed"})
        assert v.verdict == FAILED
        assert v.note == "content:app.py:contains"

    def test_component_hint_validation(self):
        from harness.verify import COMPONENT_HINTS, Verdict

        assert "task_contract" in COMPONENT_HINTS
        assert "endpoint" in COMPONENT_HINTS
        assert "verifier" in COMPONENT_HINTS
        with pytest.raises(ValueError):
            Verdict("passed", note="x", component_hint="not_a_hint")


@pytest.mark.usefixtures("temp_db")
class TestContentAssertions:
    def test_passed_with_content_passes(self, rename_task):
        from file_editing.writer import initialize_file_lines
        from harness.verify import PASSED, verify_trial

        initialize_file_lines("app.py", "value = NEW\n")
        v = verify_trial(rename_task, {"infra_abort": 0, "status": "passed"})
        assert v.verdict == PASSED
        assert v.note == "content_ok"

    def test_exact_mode(self):
        from file_editing.writer import initialize_file_lines
        from harness.benchmark.tasks import parse_bench_task
        from harness.verify import FAILED, PASSED, verify_trial

        task = parse_bench_task(
            {
                "task_id": "t",
                "seed": "s",
                "fixture": {"a.py": "x\n"},
                "contract": [{"file_path": "a.py", "fragment": "x\n", "mode": "exact"}],
            }
        )
        initialize_file_lines("a.py", "x\n")
        assert verify_trial(task, {"infra_abort": 0, "status": "passed"}).verdict == PASSED
        initialize_file_lines("a.py", "y\n")
        assert verify_trial(task, {"infra_abort": 0, "status": "passed"}).verdict == FAILED

    def test_absent_mode(self):
        from file_editing.writer import initialize_file_lines
        from harness.benchmark.tasks import parse_bench_task
        from harness.verify import FAILED, PASSED, verify_trial

        task = parse_bench_task(
            {
                "task_id": "t",
                "seed": "s",
                "fixture": {"a.py": "tmp\n"},
                "contract": [{"file_path": "a.py", "fragment": "tmp", "mode": "absent"}],
            }
        )
        initialize_file_lines("a.py", "clean\n")
        assert verify_trial(task, {"infra_abort": 0, "status": "passed"}).verdict == PASSED
        initialize_file_lines("a.py", "tmp\n")
        assert verify_trial(task, {"infra_abort": 0, "status": "passed"}).verdict == FAILED


@pytest.mark.usefixtures("temp_db")
class TestRecordVerdict:
    def test_record_verdict_updates_rollout(self):
        from harness.benchmark.tasks import parse_bench_task
        from harness.fingerprint import create_rollout, latest_rollout
        from harness.verify import PASSED, Verdict, record_verdict

        task = parse_bench_task(
            {
                "task_id": "t-r",
                "seed": "s",
                "fixture": {"a.py": "x\n"},
                "contract": [{"file_path": "a.py", "fragment": "x", "mode": "contains"}],
            }
        )
        rid = create_rollout("t-r")
        record_verdict(rid, Verdict(PASSED, note="content_ok", component_hint="verifier"), task.contract_hash)

        row = latest_rollout("t-r")
        assert row["verdict"] == PASSED
        assert row["verdict_note"] == "content_ok"
        assert row["contract_hash"] == task.contract_hash
