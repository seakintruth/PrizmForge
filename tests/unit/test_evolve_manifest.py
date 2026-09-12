"""Unit tests for harness evolution decision artifacts (§12.4).

Change-manifest recording, task-outcome mirroring, the §5.2 edit verdict SQL,
and the §5.3 rollback rule.
"""

from __future__ import annotations

import json

import pytest


@pytest.fixture
def sample_manifest():
    return {
        "iteration": 1,
        "base_harness_tag": "iter-0",
        "base_pass1": 0.5,
        "edits": [
            {
                "edit_id": "iter-1-01",
                "component_type": "system_prompt",
                "target_file": "harness/system_prompt/developer.md",
                "commit": "deadbeef",
                "evidence_refs": ["runs/0/analysis/task-17.md"],
                "inferred_root_cause": "ignores fails",
                "predicted_fixes": ["task-17", "task-22"],
                "predicted_regressions": ["task-41"],
                "rationale": "lesson coverage",
            }
        ],
    }


def test_schema_version_bumped_and_tables_present(temp_db):
    from core.db_connection import get_db_connection

    with get_db_connection() as conn:
        names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert "harness_change_manifest" in names
    assert "task_outcomes" in names


def test_record_and_read_manifest_roundtrip(temp_db, sample_manifest):
    from harness.evolve import read_change_manifest, record_change_manifest

    assert record_change_manifest(1, sample_manifest) is True
    assert read_change_manifest(1) == sample_manifest

    # Upsert overwrites the payload.
    record_change_manifest(1, {"iteration": 1, "edits": []})
    assert read_change_manifest(1) == {"iteration": 1, "edits": []}
    assert read_change_manifest(999) is None


def test_write_manifest_file(temp_db, tmp_path, sample_manifest):
    from harness.evolve import read_change_manifest, write_manifest_file

    base = tmp_path / "manifests"
    path = write_manifest_file(1, sample_manifest, base=base)
    assert path == base / "iteration-1.json"
    assert json.loads(path.read_text(encoding="utf-8"))["iteration"] == 1
    assert read_change_manifest(1)["edits"][0]["edit_id"] == "iter-1-01"


def test_task_outcomes_roundtrip_and_upsert(temp_db):
    from harness.evolve import load_task_outcomes, record_task_outcomes

    assert (
        record_task_outcomes(
            2,
            [
                {"task_id": "task-17", "passed": 1, "tokens": 1200},
                {"task_id": "task-41", "passed": 0, "tokens": 900, "result": "infra_aborted"},
            ],
        )
        == 2
    )

    # Upsert updates passed/tokens for an existing (iteration, task_id).
    record_task_outcomes(2, [{"task_id": "task-17", "passed": 0, "tokens": 1300}])
    rows = {r["task_id"]: r for r in load_task_outcomes(2)}
    assert rows["task-17"]["passed"] == 0
    assert rows["task-17"]["tokens"] == 1300
    assert rows["task-41"]["passed"] == 0
    assert rows["task-41"]["result"] == "infra_aborted"


def test_edit_verdicts_confirms_predicted_fix(temp_db, sample_manifest):
    from harness.evolve import edit_verdicts, record_change_manifest, record_task_outcomes

    record_change_manifest(1, sample_manifest)
    record_task_outcomes(1, [{"task_id": "task-17", "passed": 0, "tokens": 1}])
    record_task_outcomes(
        2,
        [
            {"task_id": "task-17", "passed": 1, "tokens": 100},
            {"task_id": "task-22", "passed": 0, "tokens": 100},
        ],
    )

    verdicts = edit_verdicts(1, 2)
    assert len(verdicts) == 1
    v = verdicts[0]
    assert v["edit_id"] == "iter-1-01"
    assert v["fixes_confirmed"] == 1
    assert v["fixes_predicted"] == 2
    assert v["precision"] == 0.5


def test_edit_verdicts_requires_valid_prior_context(temp_db, sample_manifest):
    from harness.evolve import edit_verdicts

    # No manifest / no flipped outcomes behave gracefully.
    assert edit_verdicts(1, 2) == []
    assert edit_verdicts(2, 2) == []
    assert edit_verdicts(3, 2) == []


def test_outcomes_from_results(temp_db):
    from harness.evolve import load_task_outcomes, record_iteration_outcomes

    results = {
        "tasks": [
            {
                "task_id": "task-17",
                "passed": 2,
                "infra_aborted": 0,
                "trials": [
                    {"verdict": "passed", "tokens": 100},
                    {"verdict": "passed", "tokens": 200},
                ],
            },
            {
                "task_id": "task-41",
                "passed": 0,
                "infra_aborted": 1,
                "trials": [{"verdict": "infra_aborted", "tokens": None}],
            },
        ]
    }
    assert record_iteration_outcomes(3, results) == 2
    rows = {r["task_id"]: r for r in load_task_outcomes(3)}
    assert rows["task-17"]["passed"] == 1
    assert rows["task-17"]["tokens"] == 300
    assert rows["task-41"]["passed"] == 0
    assert rows["task-41"]["result"] == "infra_aborted"


def test_revert_candidates_rollback_rule(temp_db, sample_manifest):
    from harness.evolve import record_change_manifest, record_task_outcomes, revert_candidates

    record_change_manifest(1, sample_manifest)
    # Nothing the edit predicted got fixed; its flagged regression (task-41) landed.
    record_task_outcomes(
        1,
        [
            {"task_id": "task-17", "passed": 0, "tokens": 1},
            {"task_id": "task-41", "passed": 1, "tokens": 1},
        ],
    )
    record_task_outcomes(
        2,
        [
            {"task_id": "task-17", "passed": 0, "tokens": 100},
            {"task_id": "task-41", "passed": 0, "tokens": 100},
        ],
    )

    candidates = revert_candidates(1, 2)
    assert len(candidates) == 1
    c = candidates[0]
    assert c["edit_id"] == "iter-1-01"
    assert c["action"] == "git revert deadbeef"
    assert c["fixes_confirmed"] == 0
    assert "task-41" in c["flagged_regressions_landed"]


def test_revert_candidates_skips_when_fix_confirms(temp_db, sample_manifest):
    from harness.evolve import record_change_manifest, record_task_outcomes, revert_candidates

    record_change_manifest(1, sample_manifest)
    # task-17 fixed (confirm >= 1) → even with a landed flagged regression, no revert.
    record_task_outcomes(
        1,
        [
            {"task_id": "task-17", "passed": 0, "tokens": 1},
            {"task_id": "task-41", "passed": 1, "tokens": 1},
        ],
    )
    record_task_outcomes(
        2,
        [
            {"task_id": "task-17", "passed": 1, "tokens": 100},
            {"task_id": "task-41", "passed": 0, "tokens": 100},
        ],
    )

    assert revert_candidates(1, 2) == []
