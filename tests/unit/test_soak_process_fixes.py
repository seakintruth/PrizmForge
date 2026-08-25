"""Tests for soak-round process fixes: category normalization, finish gate,
task finalization."""

import pytest

from core.db_helpers import normalize_category


# =========================================================================
# P4: category normalization
# =========================================================================
class TestNormalizeCategory:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            # separator / case canonicalization
            ("code-smell", "maintainability"),
            ("code_smell", "maintainability"),
            ("Code Smell", "maintainability"),
            ("test-coverage", "test"),
            ("test_coverage", "test"),
            ("coverage-gap", "test"),
            ("test_gap", "test"),
            ("test-quality", "test"),
            ("Test Quality", "test"),
            ("security", "security"),
            ("SECURITY", "security"),
            ("bug", "bug"),
            ("performance", "performance"),
            ("documentation", "documentation"),
            ("architecture", "architecture"),
            ("style", "style"),
            # alias folding
            ("vulnerability", "security"),
            ("defect", "bug"),
            ("optimization", "performance"),
            ("refactoring", "maintainability"),
            ("robustness", "maintainability"),
            ("readability", "maintainability"),
            ("tech-debt", "maintainability"),
            ("docs", "documentation"),
            ("design", "architecture"),
            ("formatting", "style"),
            ("regression", "test"),
            ("compatibility", "other"),
            ("dependency", "other"),
            ("accessibility", "other"),
        ],
    )
    def test_maps_to_canonical(self, raw, expected):
        assert normalize_category(raw) == expected

    @pytest.mark.parametrize("raw", ["seed_task", "review_rejection", "uncategorized"])
    def test_process_categories_pass_through(self, raw):
        assert normalize_category(raw) == raw

    def test_unknown_becomes_other(self):
        assert normalize_category("quantum-entanglement") == "other"

    def test_empty_becomes_other(self):
        assert normalize_category("") == "other"
        assert normalize_category(None) == "other"


# =========================================================================
# P1: finish gate + task finalization
# =========================================================================
class TestFinishGate:
    def test_critical_always_blocks(self, temp_db):
        from workflow.task_runner import _finish_gate_blocked

        blocked, reason = _finish_gate_blocked(critical_count=1, high_pending=0, highs_pending_turns=99, grace=3)
        assert blocked
        assert "CRITICAL" in reason

    def test_high_blocks_within_grace(self, temp_db):
        from workflow.task_runner import _finish_gate_blocked

        blocked, _ = _finish_gate_blocked(critical_count=0, high_pending=5, highs_pending_turns=1, grace=3)
        assert blocked

    def test_high_stops_blocking_after_grace(self, temp_db):
        from workflow.task_runner import _finish_gate_blocked

        blocked, _ = _finish_gate_blocked(critical_count=0, high_pending=5, highs_pending_turns=3, grace=3)
        assert not blocked

    def test_nothing_pending_never_blocks(self, temp_db):
        from workflow.task_runner import _finish_gate_blocked

        blocked, _ = _finish_gate_blocked(0, 0, 0, 3)
        assert not blocked


class TestFinalizeTask:
    def test_completed_when_files_modified(self, temp_db):
        from core.db_connection import get_db_connection
        from workflow.task_runner import _finalize_task

        with get_db_connection() as conn:
            conn.execute("INSERT INTO tasks (id, description, status) VALUES ('t1', 'd', 'in_progress')")

        _finalize_task("t1", {"files_modified": 2}, reason="timeboxed")

        with get_db_connection() as conn:
            row = conn.execute("SELECT status, completed_at, result FROM tasks WHERE id='t1'").fetchone()
        assert row[0] == "completed"
        assert row[1] is not None
        assert "timeboxed" in row[2]

    def test_stalled_when_no_files_modified(self, temp_db):
        from core.db_connection import get_db_connection
        from workflow.task_runner import _finalize_task

        with get_db_connection() as conn:
            conn.execute("INSERT INTO tasks (id, description, status) VALUES ('t2', 'd', 'in_progress')")

        _finalize_task("t2", {"files_modified": 0}, reason="max_turns")

        with get_db_connection() as conn:
            row = conn.execute("SELECT status, result FROM tasks WHERE id='t2'").fetchone()
        assert row[0] == "stalled"
        assert "max_turns" in row[1]

    def test_does_not_downgrade_completed(self, temp_db):
        from core.db_connection import get_db_connection
        from workflow.task_runner import _finalize_task

        with get_db_connection() as conn:
            conn.execute("INSERT INTO tasks (id, description, status, completed_at, result) VALUES ('t3', 'd', 'completed', 'x', 'done')")

        _finalize_task("t3", {"files_modified": 0}, reason="late call")

        with get_db_connection() as conn:
            row = conn.execute("SELECT status, completed_at, result FROM tasks WHERE id='t3'").fetchone()
        assert row[0] == "completed"
        assert row[1] == "x"
