"""Database initialization and schema"""

import sqlite3
from pathlib import Path


def get_db_path() -> str:
    """Get database path under the target project (not /tmp)."""
    import os

    env_path = os.environ.get("PRIZMFORGE_DB_PATH")
    if env_path:
        path = Path(env_path).expanduser()
        if not path.is_absolute():
            path = (Path.cwd() / path).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        return str(path)

    from core.config import find_config_file, get_config

    config = get_config()
    project_dir = Path(config.get("project_directory", "./project")).expanduser()
    if not project_dir.is_absolute():
        try:
            base = find_config_file("config.json").parent
        except Exception:
            base = Path.cwd()
        project_dir = (base / project_dir).resolve()
    prizmforge_dir = project_dir / ".PrizmForge"
    prizmforge_dir.mkdir(parents=True, exist_ok=True)
    return str(prizmforge_dir / "agents.db")


def _apply_schema(conn: sqlite3.Connection, schema_sql: str) -> None:
    """Run DDL one statement at a time (avoids executescript disk I/O issues)."""
    buf = []
    for line in schema_sql.splitlines():
        buf.append(line)
        if line.strip().endswith(";"):
            stmt = chr(10).join(buf).strip()
            buf = []
            if not stmt:
                continue
            # Renamed 'l' -> 'stmt_line' to resolve ruff E741 ambiguous variable name
            meaningful = [stmt_line for stmt_line in stmt.splitlines() if stmt_line.strip() and not stmt_line.strip().startswith("--")]
            if meaningful:
                try:
                    conn.execute(stmt)
                except sqlite3.OperationalError as e:
                    # Index on a column not yet present (pre-migration DB) — continue
                    msg = str(e).lower()
                    if "no such column" in msg or "already exists" in msg:
                        print(f"   ℹ️  Schema statement skipped: {e}")
                    else:
                        raise
    tail = chr(10).join(buf).strip()
    if tail and any(raw_line.strip() and not raw_line.strip().startswith("--") for raw_line in tail.splitlines()):
        conn.execute(tail)


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    """Return existing column names for a table (empty set if missing)."""
    try:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    except sqlite3.Error:
        return set()
    # PRAGMA table_info: cid, name, type, notnull, dflt_value, pk
    return {row[1] for row in rows}


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, coltype: str) -> None:
    """ADD COLUMN if missing. Safe on existing DBs (CREATE IF NOT EXISTS never alters)."""
    if column in _table_columns(conn, table):
        return
    try:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}")
        print(f"   🔧 Migrated {table}.{column} ({coltype})")
    except sqlite3.OperationalError as e:
        # Race or already-added by concurrent init
        if "duplicate column" not in str(e).lower():
            print(f"   ⚠️  Could not add {table}.{column}: {e}")


def _migrate_schema(conn: sqlite3.Connection) -> None:
    """
    Apply additive column migrations for DBs created before schema changes.
    CREATE TABLE IF NOT EXISTS does not add new columns to existing tables.
    """
    # edit_proposals: task_id required by reporting + query_developer_responses
    for col, coltype in (
        ("task_id", "TEXT"),
        ("selected_mode", "TEXT"),
        ("fallback_used", "INTEGER DEFAULT 0"),
        ("final_mode", "TEXT"),
        ("target_file_path", "TEXT"),
        ("rationale", "TEXT"),
        ("reviewed_at", "TIMESTAMP"),
        ("write_started_at", "TIMESTAMP"),
        ("write_completed_at", "TIMESTAMP"),
        ("write_start_line_guid", "TEXT"),
        ("write_end_line_guid", "TEXT"),
        ("reviewed_by_agent_id", "INTEGER"),
        ("proposed_by_agent_id", "INTEGER"),
        ("affected_line_guids", "TEXT"),
        ("expected_hashes", "TEXT"),
        ("status", "TEXT DEFAULT 'pending'"),
        ("edit_payload", "TEXT"),
        ("target_file_id", "INTEGER"),
        ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
    ):
        _ensure_column(conn, "edit_proposals", col, coltype)

    try:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_edit_proposals_task ON edit_proposals(task_id)")
    except sqlite3.OperationalError as e:
        print(f"   ⚠️  idx_edit_proposals_task: {e}")


def init_db():
    """Initialize database with complete schema"""
    try:
        db_path = get_db_path()
        print(f"🔍 Initializing database at: {db_path}")

        conn = sqlite3.connect(db_path, timeout=60.0)
        cursor = conn.cursor()
        try:
            cursor.execute("PRAGMA journal_mode=OFF;")
            cursor.execute("PRAGMA synchronous=OFF;")
            cursor.execute("PRAGMA temp_store=MEMORY;")
        except Exception as e:
            print(f"    ⚠️  Exception handled in db.py: {e}")
        # foreign_keys after schema apply (some mounts fail mid-DDL with FKs on)

        _schema_sql = """
            -- ============================================================
            -- Core Agent Communication Tables
            -- ============================================================

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

            -- ============================================================
            -- Error Logging Table (ADDED)
            -- ============================================================

            CREATE TABLE IF NOT EXISTS errors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                level TEXT NOT NULL,
                message TEXT NOT NULL,
                context TEXT,
                file_path TEXT,
                function_name TEXT,
                task_id TEXT,
                agent_name TEXT,
                stack_trace TEXT,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP
            );

            -- ============================================================
            -- Project Files and Indexing
            -- ============================================================

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
                estimated_tokens INTEGER DEFAULT 0,
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

            -- ============================================================
            -- Agent Feedback and Processing
            -- ============================================================

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

            CREATE TABLE IF NOT EXISTS agent_profiles (
                agent_name TEXT PRIMARY KEY,
                profile_json TEXT,
                last_updated TEXT
            );

            CREATE TABLE IF NOT EXISTS resource_model_overrides (
                agent_name TEXT PRIMARY KEY,
                override_model TEXT,
                applied_at TEXT
            );

            CREATE TABLE IF NOT EXISTS cli_checkpoints (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                mode TEXT,
                start_time TEXT,
                task_counter INTEGER,
                total_files_modified INTEGER,
                total_iterations INTEGER,
                current_task_id TEXT,
                checkpoint_time TEXT
            );

            CREATE TABLE IF NOT EXISTS resource_decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                task_id TEXT,
                level TEXT,
                budget_percentage REAL,
                tokens_remaining INTEGER,
                burn_rate REAL,
                feeder_interval INTEGER,
                active_agents TEXT,
                rate_limit INTEGER,
                reasoning TEXT
            );

            CREATE TABLE IF NOT EXISTS endpoint_fallbacks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                task_id TEXT,
                agent_name TEXT,
                original_endpoint TEXT,
                fallback_endpoint TEXT,
                reason TEXT
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

            -- ============================================================
            -- Context Management and Archiving
            -- ============================================================

            -- Archived context summaries
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

            -- All raw agent responses (never deleted)
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

            -- ============================================================
            -- System Health and Monitoring
            -- ============================================================

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

            -- Per-model outcome events for recency-weighted flakiness tracking
            CREATE TABLE IF NOT EXISTS model_health_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                model_ref TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                ok INTEGER NOT NULL,
                latency_ms INTEGER DEFAULT 0,
                kind TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_model_health_events_ref_ts ON model_health_events(model_ref, ts);

            -- Project reports for human-readable audit reports
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

            -- Reporter state tracking
            CREATE TABLE IF NOT EXISTS reporter_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                last_report_time TEXT,
                last_report_file_count INTEGER DEFAULT 0,
                last_report_line_delta INTEGER DEFAULT 0
            );

            -- ============================================================
            -- Governed File Editing Tables
            -- ============================================================

            -- Files being edited
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

            -- File lines with GUID-based addressing
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

            -- Edit proposals for review workflow
            CREATE TABLE IF NOT EXISTS edit_proposals (
                proposal_id TEXT PRIMARY KEY,
                task_id TEXT,
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
                write_end_line_guid TEXT,
                selected_mode TEXT,
                fallback_used INTEGER DEFAULT 0,
                final_mode TEXT
            );

            -- File documentation
            CREATE TABLE IF NOT EXISTS file_documentation (
                doc_id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id INTEGER NOT NULL,
                content TEXT,
                version INTEGER DEFAULT 1,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (file_id) REFERENCES files(file_id)
            );

            -- File write audit log
            CREATE TABLE IF NOT EXISTS file_write_log (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                proposal_id TEXT,
                file_id INTEGER,
                status TEXT,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                FOREIGN KEY (proposal_id) REFERENCES edit_proposals(proposal_id)
            );

            -- LLM interactions log
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

            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT,
                ts TEXT,
                type TEXT NOT NULL,
                source TEXT,
                payload_json TEXT,
                proposal_id TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_events_task ON events(task_id);
            CREATE INDEX IF NOT EXISTS idx_events_type ON events(type);

            -- Structural symbol index (hybrid plan: sqlite source of truth)
            CREATE TABLE IF NOT EXISTS file_symbols (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT NOT NULL,
                kind TEXT NOT NULL,
                name TEXT NOT NULL,
                qualname TEXT NOT NULL,
                lineno INTEGER,
                updated_at TEXT NOT NULL,
                UNIQUE(file_path, kind, qualname)
            );
            CREATE INDEX IF NOT EXISTS idx_file_symbols_path ON file_symbols(file_path);
            CREATE INDEX IF NOT EXISTS idx_file_symbols_kind ON file_symbols(kind);


            -- ============================================================
            -- Indexes for Performance
            -- ============================================================

            -- Core messaging indexes
            CREATE INDEX IF NOT EXISTS idx_messages_to_agent ON messages(to_agent, read);
            CREATE INDEX IF NOT EXISTS idx_messages_task ON messages(task_id);
            CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);

            -- Error logging indexes
            CREATE INDEX IF NOT EXISTS idx_errors_timestamp ON errors(timestamp DESC);
            CREATE INDEX IF NOT EXISTS idx_errors_level ON errors(level);
            CREATE INDEX IF NOT EXISTS idx_errors_task ON errors(task_id);
            CREATE INDEX IF NOT EXISTS idx_errors_agent ON errors(agent_name);

            -- Feedback and task indexes
            CREATE INDEX IF NOT EXISTS idx_feedback_task ON agent_feedback(task_id);
            CREATE INDEX IF NOT EXISTS idx_feedback_addressed ON agent_feedback(addressed);
            CREATE INDEX IF NOT EXISTS idx_feedback_priority ON agent_feedback(priority);

            -- File-related indexes
            CREATE INDEX IF NOT EXISTS idx_file_path ON project_files(file_path);
            CREATE INDEX IF NOT EXISTS idx_file_summaries_path ON file_summaries(file_path);
            CREATE INDEX IF NOT EXISTS idx_file_events_processed ON file_events(processed);

            -- Archive indexes
            CREATE INDEX IF NOT EXISTS idx_archived_task ON archived_context(task_id);
            CREATE INDEX IF NOT EXISTS idx_responses_task ON agent_responses_archive(task_id);
            CREATE INDEX IF NOT EXISTS idx_responses_agent ON agent_responses_archive(agent_name);

            -- Review tracking indexes
            CREATE INDEX IF NOT EXISTS idx_review_tracking_agent ON agent_review_tracking(agent_name);
            CREATE INDEX IF NOT EXISTS idx_review_tracking_file ON agent_review_tracking(file_path);

            -- Health and reporting indexes
            CREATE INDEX IF NOT EXISTS idx_endpoint_health ON endpoint_health(endpoint_name);
            CREATE INDEX IF NOT EXISTS idx_project_reports_generated_at ON project_reports(generated_at DESC);

            -- File editing indexes
            CREATE INDEX IF NOT EXISTS idx_file_lines_file_id ON file_lines(file_id);
            CREATE INDEX IF NOT EXISTS idx_file_lines_sort_order ON file_lines(sort_order);
            CREATE INDEX IF NOT EXISTS idx_edit_proposals_status ON edit_proposals(status);
            CREATE INDEX IF NOT EXISTS idx_edit_proposals_file ON edit_proposals(target_file_id);
            -- idx_edit_proposals_task created in _migrate_schema after column ensure
        """
        _apply_schema(conn, _schema_sql)
        _migrate_schema(conn)
        try:
            cursor.execute("PRAGMA foreign_keys = ON;")
        except Exception as e:
            print(f"    ⚠️  Exception handled in db.py: {e}")
        conn.commit()

        # Verify critical tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
        tables = [row[0] for row in cursor.fetchall()]

        critical_tables = ["files", "file_lines", "errors", "messages", "tasks"]
        missing_tables = [t for t in critical_tables if t not in tables]

        if missing_tables:
            conn.close()
            raise RuntimeError(f"❌ Failed to create tables: {missing_tables}")

        conn.close()
        print(f"✅ Database initialized successfully: {db_path}")
        print(f"   📊 Total tables created: {len(tables)}")
        return True

    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        import traceback

        traceback.print_exc()
        raise


if __name__ == "__main__":
    # Allow running this script directly to initialize DB
    init_db()
