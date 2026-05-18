"""Database initialization and schema"""
import sqlite3
from pathlib import Path

def get_db_path() -> str:
    """Get database path.
    
    Respects PRIZMFORGE_DB_PATH environment variable if set (useful for testing).
    Falls back to config-driven path otherwise.
    """
    import os
    env_path = os.environ.get("PRIZMFORGE_DB_PATH")
    if env_path:
        return env_path

    from core.config import get_config
    config = get_config()
    project_dir = Path(config.get("project_directory", "./project"))
    prizmfoundry_dir = project_dir / ".PrizmForge"
    prizmfoundry_dir.mkdir(parents=True, exist_ok=True)
    return str(prizmfoundry_dir / "agents.db")

def init_db():
    """Initialize database with complete schema"""
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    
    conn.executescript("""
        -- Messages between agents
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            from_agent TEXT,
            to_agent TEXT,
            content TEXT,
            task_id TEXT,
            priority TEXT DEFAULT 'MEDIUM',
            read INTEGER DEFAULT 0
        );
        
        -- Tasks
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            description TEXT,
            status TEXT,
            started_at TEXT,
            completed_at TEXT,
            result TEXT
        );
        
        -- Token usage log
        CREATE TABLE IF NOT EXISTS token_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            tokens_used INTEGER
        );
        
        -- Conversation history
        CREATE TABLE IF NOT EXISTS conversation_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT,
            agent TEXT,
            role TEXT,
            content TEXT,
            raw_response TEXT,
            parsed_decision TEXT,
            timestamp TEXT
        );
        
        -- Project files (content stored in DB)
        CREATE TABLE IF NOT EXISTS project_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT UNIQUE,
            content TEXT,
            content_hash TEXT,
            last_modified TEXT,
            size_bytes INTEGER,
            file_type TEXT,
            indexed_at TEXT,
            is_binary INTEGER DEFAULT 0,
            estimated_tokens INTEGER DEFAULT 0 
        );
        
        -- File summaries
        CREATE TABLE IF NOT EXISTS file_summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT UNIQUE,
            summary TEXT,
            key_functions TEXT,
            dependencies TEXT,
            purpose TEXT,
            line_count INTEGER,
            generated_at TEXT,
            estimated_tokens INTEGER DEFAULT 0,  -- NEW: Tokens for summary,
            FOREIGN KEY (file_path) REFERENCES project_files(file_path)
        );
        
        -- File metadata bus (for orchestrator)
        CREATE TABLE IF NOT EXISTS file_metadata_bus (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT,
            operation TEXT,
            metadata TEXT,
            summary TEXT,
            task_id TEXT,
            timestamp TEXT
        );
        
        -- Project structure analysis
        CREATE TABLE IF NOT EXISTS project_structure (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            description TEXT,
            technologies TEXT,
            purpose TEXT,
            architecture TEXT,
            indexed_at TEXT
        );
        
        -- File modifications tracking
        CREATE TABLE IF NOT EXISTS file_modifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT,
            operation TEXT,
            content_before TEXT,
            content_after TEXT,
            content_hash_before TEXT,
            content_hash_after TEXT,
            changed_by TEXT,
            task_id TEXT,
            git_commit_hash TEXT,
            timestamp TEXT
        );
        
        -- Agent feedback (from background agents)
        CREATE TABLE IF NOT EXISTS agent_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_name TEXT,
            file_path TEXT,
            priority TEXT,
            category TEXT,
            message TEXT,
            suggestion TEXT,
            task_id TEXT,
            file_event_id TEXT,
            addressed INTEGER DEFAULT 0,
            addressed_by TEXT,
            addressed_at TEXT,
            timestamp TEXT
        );
        
        -- File events (for background processing)
        CREATE TABLE IF NOT EXISTS file_events (
            id TEXT PRIMARY KEY,
            file_path TEXT,
            operation TEXT,
            content_hash TEXT,
            task_id TEXT,
            timestamp TEXT,
            processed INTEGER DEFAULT 0
        );
        
        -- Agent processing status
        CREATE TABLE IF NOT EXISTS agent_processing_status (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_event_id TEXT,
            agent_name TEXT,
            status TEXT,
            started_at TEXT,
            completed_at TEXT,
            error TEXT
        );
        
        -- NEW: Archived context summaries
        CREATE TABLE IF NOT EXISTS archived_context (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT,
            turn_range TEXT,
            summary TEXT,
            key_decisions TEXT,
            files_modified TEXT,
            archived_at TEXT,
            original_message_count INTEGER
        );
        
        -- NEW: All raw agent responses (never deleted)
        CREATE TABLE IF NOT EXISTS agent_responses_archive (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT,
            agent_name TEXT,
            prompt TEXT,
            response TEXT,
            parse_success INTEGER,
            parse_error TEXT,
            timestamp TEXT
        );

                               -- Track what each background agent has reviewed
        CREATE TABLE IF NOT EXISTS agent_review_tracking (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_name TEXT,
            file_path TEXT,
            last_reviewed_at TEXT,
            content_hash_reviewed TEXT,
            feedback_count INTEGER DEFAULT 0,
            UNIQUE(agent_name, file_path)
        );

        -- Endpoint health tracking
        CREATE TABLE IF NOT EXISTS endpoint_health (
            endpoint_name TEXT PRIMARY KEY,
            status TEXT,
            error_count INTEGER DEFAULT 0,
            consecutive_failures INTEGER DEFAULT 0,
            last_success TEXT,
            unavailable_until TEXT,
            last_updated TEXT
        );
        
                            
        -- Add project_reports table for human-readable audit reports
        CREATE TABLE IF NOT EXISTS project_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_start TEXT NOT NULL,
            report_end TEXT NOT NULL,
            trigger_type TEXT NOT NULL,
            file_path TEXT NOT NULL,
            summary TEXT,
            stats_json TEXT,
            generated_at TEXT NOT NULL,
            task_id TEXT
        );
        
        
        CREATE TABLE IF NOT EXISTS reporter_state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            last_report_time TEXT,
            last_report_file_count INTEGER DEFAULT 0,
            last_report_line_delta INTEGER DEFAULT 0
        );

                               -- Indexes for performance
        CREATE INDEX IF NOT EXISTS idx_messages_to_agent ON messages(to_agent, read);
        CREATE INDEX IF NOT EXISTS idx_messages_task ON messages(task_id);
        CREATE INDEX IF NOT EXISTS idx_feedback_task ON agent_feedback(task_id);
        CREATE INDEX IF NOT EXISTS idx_feedback_addressed ON agent_feedback(addressed);
        CREATE INDEX IF NOT EXISTS idx_feedback_priority ON agent_feedback(priority);
        CREATE INDEX IF NOT EXISTS idx_file_path ON project_files(file_path);
        CREATE INDEX IF NOT EXISTS idx_file_summaries_path ON file_summaries(file_path);
        CREATE INDEX IF NOT EXISTS idx_archived_task ON archived_context(task_id);
        CREATE INDEX IF NOT EXISTS idx_responses_task ON agent_responses_archive(task_id);
        CREATE INDEX IF NOT EXISTS idx_responses_agent ON agent_responses_archive(agent_name);
        CREATE INDEX IF NOT EXISTS idx_review_tracking_agent ON agent_review_tracking(agent_name);
        CREATE INDEX IF NOT EXISTS idx_review_tracking_file ON agent_review_tracking(file_path);
        CREATE INDEX IF NOT EXISTS idx_endpoint_health ON endpoint_health(endpoint_name);
        CREATE INDEX IF NOT EXISTS idx_project_reports_generated_at ON project_reports(generated_at DESC);

        -- ============================================================
        -- Governed File Editing Tables (consolidated from file_editing/)
        -- ============================================================

        CREATE TABLE IF NOT EXISTS files (
            file_id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT UNIQUE NOT NULL,
            current_version INTEGER DEFAULT 1,
            is_deleted INTEGER DEFAULT 0,
            has_been_written_to_disk INTEGER DEFAULT 0,
            git_comment TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

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
        );

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

        CREATE TABLE IF NOT EXISTS file_documentation (
            doc_id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id INTEGER NOT NULL,
            content TEXT,
            version INTEGER DEFAULT 1,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (file_id) REFERENCES files(file_id)
        );

        CREATE TABLE IF NOT EXISTS file_write_log (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            proposal_id TEXT,
            file_id INTEGER,
            status TEXT,
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            FOREIGN KEY (proposal_id) REFERENCES edit_proposals(proposal_id)
        );

        CREATE TABLE IF NOT EXISTS llm_interactions (
            interaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_name TEXT,
            prompt TEXT,
            response TEXT,
            prompt_tokens INTEGER,
            response_tokens INTEGER,
            model TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_file_lines_file_id ON file_lines(file_id);
        CREATE INDEX IF NOT EXISTS idx_file_lines_sort_order ON file_lines(sort_order);
        CREATE INDEX IF NOT EXISTS idx_edit_proposals_status ON edit_proposals(status);
        CREATE INDEX IF NOT EXISTS idx_edit_proposals_file ON edit_proposals(target_file_id);

    """)

    conn.commit()
    conn.close()
    print(f"✅ Database initialized: {db_path}")