"""
tests/unit/test_benchmark_driver.py

Unit tests for the §12.2 sequential driver (docs/benchmark_v1.md §4): trial
sequencing, rollout tagging, verdict persistence, and results.json emission —
with run_task_cycle monkeypatched so no real LLM is touched.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

_MINIMAL_TASK = {"task_id": "t_a", "seed": "s", "fixture": {"f.py": "x"}, "contract": []}

_SOLVED = {
    "t01_rename_constant": {"app.py": "value = NEW\n"},
    "t02_update_signature": {"app.py": "def add(a, b, c):\n    return a + b + c\n"},
    "t03_fix_syntax_error": {"app.py": "def broken():\n    pass\n"},
    "t04_add_missing_import": {"app.py": "import json\n\ndef use_json():\n    return json.dumps({})\n"},
    "t05_todo_to_marker": {"app.py": "# DONE: implement\nclass C:\n    pass\n"},
}


def _solved_runner():
    from core.db_helpers import create_task, mark_task_status
    from file_editing.writer import initialize_file_lines

    def _run(task_id: str, user_command: str, max_turns: int = 20, time_box_minutes=None):
        create_task(task_id, user_command)
        key = task_id.split("_i")[0]
        if key in _SOLVED:
            for path, content in _SOLVED[key].items():
                initialize_file_lines(path, content)
            mark_task_status(task_id, "completed", "solved")
        else:
            mark_task_status(task_id, "failed", "unsolved")

    return _run


@pytest.fixture
def bench_env(temp_db, tmp_path, monkeypatch):
    import workflow.task_runner as tr

    monkeypatch.setattr(tr, "run_task_cycle", _solved_runner())
    from harness.benchmark.config import use_bench_config

    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    return project_dir, use_bench_config


@pytest.fixture
def rename_task():
    from harness.benchmark.tasks import load_default_tasks

    return next(t for t in load_default_tasks() if t.task_id == "t01_rename_constant")


@pytest.mark.usefixtures("temp_db")
class TestRunTrial:
    def test_trial_passed(self, bench_env, rename_task):
        from harness.benchmark.driver import run_trial

        project_dir, use_bench_config = bench_env
        with use_bench_config(project_dir):
            res = run_trial(rename_task, iteration=1, trial=1, max_turns=5, project_dir=project_dir)

        assert res["verdict"] == "passed"
        assert res["note"] == "content_ok"
        assert res["trial"] == 1

    def test_trial_writes_rollout_and_verdict(self, bench_env, rename_task):
        from core.db_connection import get_db_connection
        from harness.benchmark.driver import run_trial
        from harness.fingerprint import latest_rollout

        project_dir, use_bench_config = bench_env
        with use_bench_config(project_dir):
            run_trial(rename_task, iteration=1, trial=1, max_turns=5, project_dir=project_dir)

        task_id = "t01_rename_constant_i1_t1"
        row = latest_rollout(task_id)
        assert row is not None
        assert row["iteration"] == 1
        assert row["status"] == "passed"
        assert row["verdict"] == "passed"
        assert row["contract_hash"] == rename_task.contract_hash
        with get_db_connection() as conn:
            task = conn.execute("SELECT status FROM tasks WHERE id = ?", (task_id,)).fetchone()
            assert task[0] == "completed"

    def test_trial_fail_keeps_fixture(self, bench_env, monkeypatch, rename_task):
        """An unsolved trial leaves the fixture so the content check fails."""
        import workflow.task_runner as tr
        from core.db_helpers import create_task, mark_task_status
        from harness.benchmark.config import use_bench_config
        from harness.benchmark.driver import run_trial

        def _unsolved(task_id, user_command, max_turns=20, time_box_minutes=None):
            create_task(task_id, user_command)
            mark_task_status(task_id, "failed", "unsolved")

        monkeypatch.setattr(tr, "run_task_cycle", _unsolved)
        project_dir, _use = bench_env
        with use_bench_config(project_dir):
            res = run_trial(rename_task, iteration=1, trial=2, max_turns=5, project_dir=project_dir)

        assert res["verdict"] == "failed"
        assert res["note"] == "status:failed"


@pytest.mark.usefixtures("temp_db")
class TestRunBenchmark:
    def test_results_json_and_pass1(self, bench_env, tmp_path):
        from harness.benchmark.driver import run_benchmark
        from harness.benchmark.tasks import parse_bench_task

        project_dir, _use = bench_env
        task = parse_bench_task(
            {
                "task_id": "t01_rename_constant",
                "seed": "Rename OLD to NEW in app.py",
                "fixture": {"app.py": "value = OLD\n"},
                "contract": [{"file_path": "app.py", "fragment": "value = NEW\n", "mode": "contains"}],
                "k": 2,
            }
        )

        results = run_benchmark(iteration=7, tasks=[task], max_turns=5, project_dir=project_dir)

        assert results["iteration"] == 7
        assert results["total_trials"] == 2
        assert results["passed_trials"] == 2
        assert results["pass@1"] == 1.0
        assert results["tasks"][0]["task_id"] == "t01_rename_constant"
        assert results["tasks"][0]["k"] == 2

        results_file = Path(results["runs_dir"]) / "results.json"
        assert results_file.exists()
        on_disk = json.loads(results_file.read_text(encoding="utf-8"))
        assert on_disk["pass@1"] == 1.0
        assert on_disk["tasks"][0]["trials"][0]["verdict"] == "passed"

    def test_mixed_verdicts(self, bench_env, tmp_path, monkeypatch):
        import workflow.task_runner as tr
        from core.db_helpers import create_task, mark_task_status
        from file_editing.writer import initialize_file_lines
        from harness.benchmark.driver import run_benchmark
        from harness.benchmark.tasks import parse_bench_task

        def _half_solved(task_id, user_command, max_turns=20, time_box_minutes=None):
            create_task(task_id, user_command)
            if task_id.startswith("t02"):
                mark_task_status(task_id, "failed", "unsolved")
            else:
                initialize_file_lines("app.py", "value = NEW\n")
                mark_task_status(task_id, "completed", "solved")

        monkeypatch.setattr(tr, "run_task_cycle", _half_solved)
        project_dir, _use = bench_env
        pass_task = parse_bench_task(
            {
                "task_id": "t01_rename_constant",
                "seed": "Rename OLD to NEW in app.py",
                "fixture": {"app.py": "value = OLD\n"},
                "contract": [{"file_path": "app.py", "fragment": "value = NEW\n", "mode": "contains"}],
                "k": 1,
            }
        )
        fail_task = parse_bench_task(
            {
                "task_id": "t02_unsolved",
                "seed": "nope",
                "fixture": {"app.py": "value = OLD\n"},
                "contract": [{"file_path": "app.py", "fragment": "value = NEW\n", "mode": "contains"}],
                "k": 1,
            }
        )

        results = run_benchmark(iteration=8, tasks=[pass_task, fail_task], max_turns=5, project_dir=project_dir)

        assert results["total_trials"] == 2
        assert results["passed_trials"] == 1
        assert results["pass@1"] == 0.5
        assert results["tasks"][0]["trials"][0]["verdict"] == "passed"
        assert results["tasks"][1]["trials"][0]["verdict"] == "failed"


class TestTaskManifestSchema:
    """§13.6 — tasks.json schema_version is honored by the loader."""

    def test_manifest_reports_schema_version(self, tmp_path):
        from harness.benchmark.tasks import load_task_manifest

        p = tmp_path / "tasks.json"
        p.write_text(
            json.dumps({"schema_version": 1, "default_k": 1, "tasks": [_MINIMAL_TASK]}),
            encoding="utf-8",
        )
        manifest = load_task_manifest(p)
        assert manifest["schema_version"] == 1
        assert manifest["tasks"][0].task_id == "t_a"

    def test_manifest_missing_schema_defaults_to_supported(self, tmp_path):
        from harness.benchmark.tasks import load_task_manifest

        p = tmp_path / "tasks.json"
        p.write_text(json.dumps({"tasks": [_MINIMAL_TASK]}), encoding="utf-8")
        assert load_task_manifest(p)["schema_version"] == 1

    def test_manifest_refuses_unknown_future_version(self, tmp_path):
        from harness.benchmark.tasks import load_task_manifest

        p = tmp_path / "tasks.json"
        p.write_text(
            json.dumps({"schema_version": 99, "tasks": [_MINIMAL_TASK]}),
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="schema_version 99"):
            load_task_manifest(p)
