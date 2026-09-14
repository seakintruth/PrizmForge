"""
tests/unit/test_harness_verify.py

Unit tests for the §12.2 verifier (docs/benchmark_v1.md §3): verdict rules,
infra-abort exclusion, content assertions, and verdict recording onto
rollouts rows.
"""

from __future__ import annotations

import pytest

from core.db_connection import get_db_connection


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
class TestCommandVerifier:
    """§14.3 command mode: exit-0 pass, evidence gate, timeout, injectable runner."""

    def _terminal_task(self, command="test -f done.txt"):
        from harness.benchmark.tasks import parse_bench_task

        return parse_bench_task(
            {
                "task_id": "c1_flag",
                "kind": "terminal",
                "seed": "create done.txt in the repo",
                "fixture": {"app/code.py": "x = 1\n"},
                "verifier": {"command": command, "timeout": 30},
                "contract": [],
            }
        )

    def _base_rollout(self, task_id="c1_flag_i1_t1"):
        return {"infra_abort": 0, "status": "passed", "task_id": task_id}

    def _write_evidence(self, proposal_id="p-1", task_id="c1_flag_i1_t1"):
        with get_db_connection() as conn:
            conn.execute(
                "INSERT INTO edit_proposals (proposal_id, task_id, target_file_path, edit_payload, status) VALUES (?, ?, 'app/done.txt', '{}', 'applied')",
                (proposal_id, task_id),
            )
            conn.execute(
                "INSERT INTO file_write_log (proposal_id, file_id, status, started_at, completed_at) VALUES (?, 1, 'success', '2026-01-01', '2026-01-01')",
                (proposal_id,),
            )

    def test_exit_zero_passes_with_evidence(self):
        from harness.verify import PASSED, verify_trial

        self._write_evidence()
        task = self._terminal_task()
        v = verify_trial(task, self._base_rollout(), workdir=".", runner=lambda cmd, t: (0, ""))
        assert v.verdict == PASSED
        assert v.note == "command_ok"

    def test_default_runner_runs_real_command_in_workdir(self, tmp_path):
        from harness.verify import FAILED, PASSED, verify_trial

        self._write_evidence(proposal_id="p-ok")
        task = self._terminal_task(command="test -f done.txt")
        (tmp_path / "done.txt").write_text("x\n", encoding="utf-8")
        assert verify_trial(task, self._base_rollout(), workdir=tmp_path).verdict == PASSED
        (tmp_path / "done.txt").unlink()
        assert verify_trial(task, self._base_rollout(), workdir=tmp_path).verdict == FAILED

    def test_exit_zero_without_evidence_fails(self):
        from harness.verify import FAILED, verify_trial

        task = self._terminal_task()
        v = verify_trial(task, self._base_rollout(), workdir=".", runner=lambda cmd, t: (0, ""))
        assert v.verdict == FAILED
        assert v.note == "no_governed_edit_evidence"
        assert v.component_hint == "verifier"

    def test_exit_one_fails_with_stderr(self):
        from harness.verify import FAILED, verify_trial

        self._write_evidence(proposal_id="p-2")
        task = self._terminal_task(command="nonexistent-checker 42")
        v = verify_trial(
            task,
            self._base_rollout(),
            workdir=".",
            runner=lambda cmd, t: (1, "boom: missing target\nextra-line"),
        )
        assert v.verdict == FAILED
        assert "command:1:" in v.note
        assert "boom" in v.note

    def test_missing_workdir_fails_closed(self):
        from harness.verify import FAILED, verify_trial

        self._write_evidence()
        task = self._terminal_task()
        v = verify_trial(task, self._base_rollout())
        assert v.verdict == FAILED
        assert v.note == "verifier_aborted:no_workdir"

    def test_runner_receives_verifier_timeout(self):
        from harness.verify import PASSED, verify_trial

        self._write_evidence(proposal_id="p-3")
        task = self._terminal_task(command="true")
        calls: list[int] = []

        def _runner(cmd, timeout):
            calls.append(timeout)
            return 0, "ok"

        v = verify_trial(task, self._base_rollout(), workdir=".", runner=_runner)
        assert v.verdict == PASSED
        assert calls == [30]

    def test_timeout_exit_124_is_timed_out(self):
        from harness.verify import FAILED, verify_trial

        self._write_evidence(proposal_id="p-4")
        task = self._terminal_task(command="sleepy")
        v = verify_trial(
            task,
            self._base_rollout(),
            workdir=".",
            runner=lambda cmd, t: (124, "[test command timed out after 1s]"),
        )
        assert v.verdict == FAILED
        assert "command:timed_out" in v.note

    def test_run_shell_test_semantics(self):
        from workflow.shell_developer import run_shell_test

        code, _ = run_shell_test("true", 5, "/")
        assert code == 0
        code, _ = run_shell_test("false --boom 42", 5, "/")
        assert code != 0

    def test_infra_abort_preempts_command(self):
        from harness.verify import INFRA_ABORTED, verify_trial

        task = self._terminal_task()
        rollout = {**self._base_rollout(), "infra_abort": 1}
        v = verify_trial(task, rollout, workdir=".", runner=lambda cmd, t: (0, ""))
        assert v.verdict == INFRA_ABORTED


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


@pytest.mark.usefixtures("temp_db")
class TestDiskSourceFallback:
    """§13.5 — disk source under the bench project dir as DB fallback, recorded."""

    def test_disk_fallback_satisfies_when_db_empty(self, tmp_path):
        from harness.benchmark.tasks import parse_bench_task
        from harness.verify import PASSED, verify_trial

        (tmp_path / "app").mkdir()
        (tmp_path / "app" / "main.py").write_text("value = DISK\n")
        task = parse_bench_task(
            {
                "task_id": "t",
                "seed": "s",
                "contract": [{"file_path": "app/main.py", "fragment": "DISK", "mode": "contains"}],
            }
        )
        v = verify_trial(task, {"infra_abort": 0, "status": "passed"}, workdir=str(tmp_path))
        assert v.verdict == PASSED
        assert v.note == "content_ok:disk"

    def test_db_wins_when_both_present(self, tmp_path):
        from file_editing.writer import initialize_file_lines
        from harness.benchmark.tasks import parse_bench_task
        from harness.verify import PASSED, verify_trial

        (tmp_path / "app").mkdir()
        # Disk disagrees; DB is authoritative when present.
        (tmp_path / "app" / "main.py").write_text("value = DISK\n")
        initialize_file_lines("app/main.py", "value = DB\n")
        task = parse_bench_task(
            {
                "task_id": "t",
                "seed": "s",
                "contract": [{"file_path": "app/main.py", "fragment": "DB", "mode": "contains"}],
            }
        )
        v = verify_trial(task, {"infra_abort": 0, "status": "passed"}, workdir=str(tmp_path))
        assert v.verdict == PASSED
        assert v.note == "content_ok"

    def test_disk_failure_records_source(self, tmp_path):
        from harness.benchmark.tasks import parse_bench_task
        from harness.verify import FAILED, verify_trial

        (tmp_path / "app").mkdir()
        (tmp_path / "app" / "main.py").write_text("value = DISK\n")
        task = parse_bench_task(
            {
                "task_id": "t",
                "seed": "s",
                "contract": [{"file_path": "app/main.py", "fragment": "MISSING", "mode": "contains"}],
            }
        )
        v = verify_trial(task, {"infra_abort": 0, "status": "passed"}, workdir=str(tmp_path))
        assert v.verdict == FAILED
        assert v.note == "content:app/main.py:contains:disk"

    def test_outside_workdir_never_reads_disk(self, tmp_path):
        from harness.benchmark.tasks import parse_bench_task
        from harness.verify import FAILED, verify_trial

        outside = tmp_path / "outside"
        outside.mkdir()
        (outside / "main.py").write_text("value = OUTSIDE\n")
        task = parse_bench_task(
            {
                "task_id": "t",
                "seed": "s",
                "contract": [{"file_path": "main.py", "fragment": "OUTSIDE", "mode": "contains"}],
            }
        )
        v = verify_trial(task, {"infra_abort": 0, "status": "passed"}, workdir=str(tmp_path))
        assert v.verdict == FAILED
        assert v.note == "content:main.py:contains"
