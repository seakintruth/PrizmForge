"""
PrizmForge Core Architectural Test Suite

Coverage:
- Phase 1: Task Queue Progression & Priority Rules
- Phase 2: Clean LLM Fallback Re-Prompting
- Phase 3: Closed-Loop Reviewer Rejection Feedback
- Phase 4: Exact Response-to-Modification SQL Linking
- Phase 5: Complete Database Export Scope

Execution:
    c:/git/programs/Python31209/python.exe -m pytest tests/integration/test_prizmforge_architecture.py -v
"""

import sqlite3
from unittest.mock import patch

import pytest

# =========================================================================
# FIXTURES
# =========================================================================


@pytest.fixture
def memory_db():
    """In-memory SQLite database with PrizmForge schemas."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE tasks (
            id TEXT PRIMARY KEY,
            description TEXT,
            status TEXT,
            started_at TEXT,
            completed_at TEXT
        );

        CREATE TABLE edit_proposals (
            proposal_id TEXT PRIMARY KEY,
            task_id TEXT,
            target_file_path TEXT,
            rationale TEXT,
            status TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE agent_responses_archive (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            agent_name TEXT,
            task_id TEXT,
            prompt TEXT,
            response TEXT,
            parse_success INTEGER DEFAULT 1,
            parse_error TEXT
        );

        CREATE TABLE agent_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT,
            file_path TEXT,
            agent_name TEXT,
            message TEXT,
            suggestion TEXT,
            priority TEXT DEFAULT 'HIGH',
            category TEXT,
            addressed INTEGER DEFAULT 0,
            addressed_by TEXT,
            addressed_at TEXT,
            timestamp TEXT
        );
    """)
    conn.commit()
    yield conn
    conn.close()


# =========================================================================
# PHASE 1: SEED TASK QUEUE PROGRESSION
# =========================================================================


def test_resolve_task_description_scalar_precedence():
    """Phase 1: Scalar seed_task executes on run 0, then seed_tasks list cycles."""
    from interactive import resolve_task_description

    config = {"seed_task": "Urgent Scalar Task", "seed_tasks": ["Queue Task 1", "Queue Task 2"]}

    assert resolve_task_description(config, 0) == "Urgent Scalar Task"
    assert resolve_task_description(config, 1) == "Queue Task 1"
    assert resolve_task_description(config, 2) == "Queue Task 2"


# =========================================================================
# PHASE 2: CLEAN FALLBACK RE-PROMPTING
# =========================================================================


def test_build_generation_prompt_fallback_injection():
    """Phase 2: Injects FULL_REPLACE warning banner when fallback_used=True."""
    from workflow.developer_edit import _build_generation_prompt

    prompt = _build_generation_prompt(
        instructions="Refactor auth loop",
        edit_method="full_replace",
        files_content=["def auth(): pass"],
        requested_files=["auth.py"],
        task_id="task_001",
        fallback_used=True,
        previous_reason="GUID parsing error",
    )

    assert "CRITICAL FALLBACK INSTRUCTION — FULL FILE REPLACE REQUIRED" in prompt
    assert "Previous Failure Reason: GUID parsing error" in prompt


# =========================================================================
# PHASE 3: CLOSED-LOOP REVIEWER FEEDBACK
# =========================================================================


def test_closed_loop_reviewer_feedback(memory_db):
    """Phase 3: Unaddressed Reviewer feedback is extracted and injected into Developer prompt."""
    cursor = memory_db.cursor()
    cursor.execute("""
        INSERT INTO agent_feedback (task_id, file_path, agent_name, message, addressed, timestamp)
        VALUES ('task_001', 'main.py', 'reviewer', 'Proposal 42 REJECTED: Syntax error on line 10', 0, '2026-01-01T00:00:00')
        """)
    memory_db.commit()

    # get_db_connection is a context manager — yield the in-memory conn
    class _CM:
        def __enter__(self):
            return memory_db

        def __exit__(self, *args):
            return False

    with patch("workflow.developer_edit.get_db_connection", return_value=_CM()):
        from workflow.developer_edit import _build_generation_prompt

        prompt = _build_generation_prompt(
            instructions="Update main.py",
            edit_method="guid",
            files_content=["print('hello')"],
            requested_files=["main.py"],
            task_id="task_001",
        )
        assert "PREVIOUS ATTEMPT REJECTED BY REVIEWER — CORRECTION REQUIRED" in prompt
        assert "Syntax error on line 10" in prompt


# =========================================================================
# PHASE 4: EXACT SQL RESPONSE LINKING
# =========================================================================


def test_sql_response_exact_matching(memory_db):
    """Phase 4: Developer attempt N links strictly to Reviewer APPROVE response N+1/N+2."""
    cursor = memory_db.cursor()
    cursor.execute("INSERT INTO tasks VALUES ('task_001', 'Test Task', 'in_progress', 'now', NULL)")
    # Minimal columns for query_developer_responses joins; schema here is test-local
    cursor.execute("INSERT INTO edit_proposals (proposal_id, task_id, target_file_path, status) VALUES ('p1', 'task_001', 'app.py', 'applied')")

    # Developer Attempt 1 -> Rejected
    cursor.execute("INSERT INTO agent_responses_archive (id, agent_name, task_id, prompt, response) VALUES (1, 'developer', 'task_001', 'p1', 'r1')")
    cursor.execute(
        "INSERT INTO agent_responses_archive "
        "(id, agent_name, task_id, prompt, response) "
        "VALUES (2, 'reviewer', 'task_001', 'p2', '{\"decision\": \"REJECT\"}')"
    )

    # Developer Attempt 2 -> Approved
    cursor.execute("INSERT INTO agent_responses_archive (id, agent_name, task_id, prompt, response) VALUES (3, 'developer', 'task_001', 'p3', 'r3')")
    cursor.execute(
        "INSERT INTO agent_responses_archive "
        "(id, agent_name, task_id, prompt, response) "
        "VALUES (4, 'reviewer', 'task_001', 'p4', '{\"decision\": \"APPROVE\"}')"
    )
    memory_db.commit()

    class _CM:
        def __enter__(self):
            return memory_db

        def __exit__(self, *args):
            return False

    with patch("utils.query_developer_responses.get_db_connection", return_value=_CM()):
        from utils.query_developer_responses import list_recent_developer_responses

        ids = list_recent_developer_responses(task_id="task_001", modified_only=True)
        assert ids == [3]


# =========================================================================
# PHASE 5: COMPLETE DATABASE EXPORT SCOPE
# =========================================================================


def test_export_db_full_scope(memory_db, tmp_path):
    """Phase 5: Exporting without task_id dumps all tasks across all tables."""
    cursor = memory_db.cursor()
    cursor.execute("INSERT INTO tasks VALUES ('task_001', 'T1', 'completed', 'now', 'now')")
    cursor.execute("INSERT INTO tasks VALUES ('task_002', 'T2', 'completed', 'now', 'now')")
    memory_db.commit()

    class _CM:
        def __enter__(self):
            return memory_db

        def __exit__(self, *args):
            return False

    with patch("cli.commands.get_db_connection", return_value=_CM()):
        from cli.commands import cmd_export_db

        export_dir = tmp_path / "exports"
        cmd_export_db(output_dir=export_dir, task_id=None)

        content = (export_dir / "tasks.csv").read_text(encoding="utf-8")
        assert "task_001" in content
        assert "task_002" in content
