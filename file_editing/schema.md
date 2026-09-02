# Governed File Editing Schema

> **Historical note:** Table definitions used to live in this file (and in a
> removed `file_editing/schema.py`). They were consolidated into
> `core/db.py` → `init_db()` (May 2026). This page is a pointer only — do not
> copy CREATE TABLE statements from here; they would drift.

**Canonical schema:** `core/db.py` (`init_db()` and `_migrate_schema()`).

**Documented dump:** `docs/architecture.md` (Database Schema).

The `file_editing/` package focuses on editing logic (`editing.py`,
`edit_payload.py`, `writer.py`) rather than schema management.
