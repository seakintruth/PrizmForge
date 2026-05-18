# =============================================================================
# file_editing/schema.py
# DEPRECATED - Schema has been consolidated into core/db.py
# This file is kept only for reference. Do not use for initialization.
# See file_editing/schema.md for documentation.
# =============================================================================

# NOTE: All table creation now happens in core/db.py:init_db()


import sqlite3
from pathlib import Path

SCHEMA_VERSION = "1.2"

def get_db_path() -> str:
    return str(Path("/home/workdir/artifacts/PrizmForge/prizmforge.db"))

def initialize_database(db_path: str = None):
    if db_path is None:
        db_path = get_db_path()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS files (
            file_id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT UNIQUE NOT NULL,
            current_version INTEGER DEFAULT 1,
            is_deleted INTEGER DEFAULT 0,
            has_been_written_to_disk INTEGER DEFAULT 0,
            git_comment TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS file_lines (
            line_guid TEXT PRIMARY KEY,
            file_id INTEGER NOT NULL,
            sort_order REAL NOT NULL,
            content TEXT NOT NULL,
            content_hash TEXT,
            is_deleted INTEGER DEFAULT 0,
            version INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (file_id) REFERENCES files(file_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS edit_proposals (
            proposal_id TEXT PRIMARY KEY,
            target_file_id INTEGER,
            target_file_path TEXT,
            edit_payload TEXT NOT NULL,
            affected_line_guids TEXT,
            expected_hashes TEXT,
            status TEXT DEFAULT 'pending',
            proposed_by_agent_id INTEGER,
            reviewed_by_agent_id INTEGER,
            rationale TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            reviewed_at TIMESTAMP,  
            write_started_at TIMESTAMP,
            write_completed_at TIMESTAMP,
            write_start_line_guid TEXT,
            write_end_line_guid TEXT
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS file_documentation (
            doc_id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id INTEGER NOT NULL,
            content TEXT,
            version INTEGER DEFAULT 1,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (file_id) REFERENCES files(file_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS errors (
            error_id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT,
            severity TEXT DEFAULT 'ERROR',
            message TEXT,
            stack_trace TEXT,
            file_path TEXT,
            line_number INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS file_write_log (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            proposal_id TEXT,
            file_id INTEGER,
            status TEXT,
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            FOREIGN KEY (proposal_id) REFERENCES edit_proposals(proposal_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS llm_interactions (
            interaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_name TEXT,
            prompt TEXT,
            response TEXT,
            prompt_tokens INTEGER,
            response_tokens INTEGER,
            model TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_file_lines_file_id ON file_lines(file_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_file_lines_sort_order ON file_lines(sort_order)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_edit_proposals_status ON edit_proposals(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_edit_proposals_file ON edit_proposals(target_file_id)")

    conn.commit()
    conn.close()
    print(f"Database initialized at {db_path} (schema v{SCHEMA_VERSION})")