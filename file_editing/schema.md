# Governed File Editing Schema (Deprecated)

> **Note:** As of May 2026, the schema definitions below have been consolidated into `core/db.py`.  
> This file is kept for documentation and historical reference only.

## Tables

### `files`

Stores metadata about files under governance.

```sql
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
```

### `file_lines`

Line-level storage with stable GUIDs for precise editing.

```sql
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
```

### `edit_proposals`

Tracks proposed edits through the governed workflow (pending → under_review → approved/rejected).

```sql
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
```

### `file_documentation`

Per-file documentation managed through the governed path.

```sql
CREATE TABLE IF NOT EXISTS file_documentation (
    doc_id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id INTEGER NOT NULL,
    content TEXT,
    version INTEGER DEFAULT 1,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (file_id) REFERENCES files(file_id)
);
```

### `file_write_log`

Audit log of materializations.

```sql
CREATE TABLE IF NOT EXISTS file_write_log (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    proposal_id TEXT,
    file_id INTEGER,
    status TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    FOREIGN KEY (proposal_id) REFERENCES edit_proposals(proposal_id)
);
```

### `llm_interactions`

Optional logging of LLM calls related to editing.

```sql
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
```

## Indexes

```sql
CREATE INDEX IF NOT EXISTS idx_file_lines_file_id ON file_lines(file_id);
CREATE INDEX IF NOT EXISTS idx_file_lines_sort_order ON file_lines(sort_order);
CREATE INDEX IF NOT EXISTS idx_edit_proposals_status ON edit_proposals(status);
CREATE INDEX IF NOT EXISTS idx_edit_proposals_file ON edit_proposals(target_file_id);
```

---

**Consolidation Note**

All table creation is now performed in `core/db.py` inside `init_db()`.  
The `file_editing/` package now focuses on editing logic (`editing.py`, `edit_payload.py`, `writer.py`) rather than schema management.