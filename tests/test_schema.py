"""
tests/test_schema.py

Tests focused on database schema initialization and structure.
These tests verify that init_db() creates all expected tables correctly.
"""

import pytest
import sqlite3
import tempfile
import os


def test_init_db_creates_all_tables():
    """
    Verify that init_db() creates both core tables and governed editing tables.
    Deletes any pre-existing DB at the test location to ensure clean state.
    """
    from core.db import init_db

    # Create temporary database path
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    # Ensure clean state - delete if exists
    if os.path.exists(db_path):
        try:
            os.unlink(db_path)
        except OSError:
            pass

    # Set environment variable so get_db_path() uses our temp DB
    os.environ["PRIZMFORGE_DB_PATH"] = db_path

    # Initialize database (consolidated schema)
    init_db()

    # Connect and inspect tables
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    existing_tables = {row[0] for row in cursor.fetchall()}
    conn.close()

    # Cleanup
    try:
        os.unlink(db_path)
    except OSError:
        pass

    # Core system tables we expect
    core_tables = {
        "messages", "tasks", "token_log", "conversation_history",
        "project_files", "agent_feedback", "project_reports"
    }

    # Governed editing tables
    governed_tables = {
        "files", "file_lines", "edit_proposals",
        "file_documentation", "file_write_log"
    }

    missing_core = core_tables - existing_tables
    missing_governed = governed_tables - existing_tables

    assert not missing_core, f"Missing core tables after init_db(): {missing_core}"
    assert not missing_governed, f"Missing governed editing tables after init_db(): {missing_governed}"
