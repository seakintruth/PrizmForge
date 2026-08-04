import hashlib
import json
import sqlite3
from typing import Any, Dict, Optional
from uuid import uuid4

from core.content_safety import validate_source_content

from .db import get_db_connection, log_error

# =============================================================================
# PrizmForge/file_editing/editing.py
# Version: 1.6 - Range-based editing + Detailed operation results
# Purpose: Core editing engine with optimistic validation, safe range operations,
#          and detailed feedback on lines affected.
# =============================================================================


# =============================================================================
# Configuration
# =============================================================================
INITIAL_GAP = 1024.0
MIN_GAP_THRESHOLD = 0.001
RENUMBER_GAP = 1024.0


def _compute_hash(content: str) -> str:
    return hashlib.md5(content.encode()).hexdigest()


def _validate_guid_exists(conn: sqlite3.Connection, file_id: int, line_guid: str) -> bool:
    if not line_guid:
        return False
    row = conn.execute(
        "SELECT 1 FROM file_lines WHERE line_guid = ? AND file_id = ? AND is_deleted = 0",
        (line_guid, file_id),
    ).fetchone()
    return row is not None


def _validate_operation_guids(conn: sqlite3.Connection, file_id: int, op) -> bool:
    """
    Validate that referenced line GUIDs exist for the given operation.
    Supports replace_block, delete_lines, and insert_after.
    find_replace does not use GUIDs and always passes.
    """
    if op.type in (
        "find_replace",
        "full_replace",
        "apply_diff",
        "create_file",
        "update_documentation",
    ):
        return True  # content-level ops; no GUID references
    if op.type == "replace_block":
        if not _validate_guid_exists(conn, file_id, op.start_line_guid):
            return False
        if getattr(op, "end_line_guid", None) and not _validate_guid_exists(conn, file_id, op.end_line_guid):
            return False
        return True

    elif op.type == "delete_lines":
        if not _validate_guid_exists(conn, file_id, op.start_line_guid):
            return False
        if getattr(op, "end_line_guid", None) and not _validate_guid_exists(conn, file_id, op.end_line_guid):
            return False
        return True

    elif op.type == "insert_after":
        # after_guid can be None (for new/empty files)
        after_guid = getattr(op, "after_guid", None)
        if after_guid is None:
            return True
        return _validate_guid_exists(conn, file_id, after_guid)

    # Unknown operation type — be conservative
    return False


def get_insert_sort_order(conn: sqlite3.Connection, file_id: int, after_guid: Optional[str] = None) -> float:
    try:
        if after_guid is None:
            min_row = conn.execute(
                "SELECT MIN(sort_order) FROM file_lines WHERE file_id = ? AND is_deleted = 0",
                (file_id,),
            ).fetchone()
            if min_row and min_row[0] is not None:
                return min_row[0] - (INITIAL_GAP / 2)
            return INITIAL_GAP / 2

        row = conn.execute(
            "SELECT sort_order FROM file_lines WHERE line_guid = ? AND is_deleted = 0",
            (after_guid,),
        ).fetchone()
        if row:
            current = row[0]
            next_row = conn.execute(
                """SELECT sort_order FROM file_lines
                   WHERE file_id = ? AND sort_order > ? AND is_deleted = 0
                   ORDER BY sort_order LIMIT 1""",
                (file_id, current),
            ).fetchone()

            if next_row and next_row[0] is not None:
                gap = next_row[0] - current
                if gap < MIN_GAP_THRESHOLD:
                    renumber_sort_orders(conn, file_id)
                    return get_insert_sort_order(conn, file_id, after_guid)
                return current + (gap / 2)
            return current + INITIAL_GAP

        max_row = conn.execute(
            "SELECT MAX(sort_order) FROM file_lines WHERE file_id = ? AND is_deleted = 0",
            (file_id,),
        ).fetchone()
        return (max_row[0] or 0.0) + INITIAL_GAP

    except Exception as e:
        log_error("file_editing", "get_insert_sort_order", "HIGH", str(e), file_id=file_id)
        raise


def renumber_sort_orders(conn: sqlite3.Connection, file_id: int) -> None:
    try:
        cursor = conn.execute(
            """
            SELECT line_guid FROM file_lines
            WHERE file_id = ? AND is_deleted = 0
            ORDER BY sort_order
        """,
            (file_id,),
        )
        line_guids = [row[0] for row in cursor.fetchall()]

        for i, line_guid in enumerate(line_guids):
            new_sort = (i + 1) * RENUMBER_GAP
            conn.execute(
                "UPDATE file_lines SET sort_order = ? WHERE line_guid = ?",
                (new_sort, line_guid),
            )

        log_error(
            "file_editing",
            "renumber_sort_orders",
            "INFO",
            f"Renumbered {len(line_guids)} lines",
            file_id=file_id,
        )
    except Exception as e:
        log_error("file_editing", "renumber_sort_orders", "HIGH", str(e), file_id=file_id)
        raise


def validate_proposal(conn, proposal: dict) -> bool:
    if not proposal.get("expected_hashes"):
        return True
    try:
        expected = json.loads(proposal["expected_hashes"])
        affected = json.loads(proposal.get("affected_line_guids", "[]"))
        for guid in affected:
            row = conn.execute(
                "SELECT content_hash FROM file_lines WHERE line_guid = ? AND is_deleted = 0",
                (guid,),
            ).fetchone()
            if not row or row[0] != expected.get(guid):
                log_error(
                    "file_editing",
                    "validation",
                    "HIGH",
                    f"Hash mismatch on line {guid}",
                    proposal_id=proposal.get("proposal_id"),
                )
                return False
        return True
    except Exception as e:
        log_error(
            "file_editing",
            "validation",
            "HIGH",
            str(e),
            proposal_id=proposal.get("proposal_id"),
        )
        return False


# =============================================================================
# Core Apply Functions with Detailed Return Values
# =============================================================================


def apply_replace_block(conn: sqlite3.Connection, file_id: int, op) -> Dict[str, Any]:
    """
    Replace a range of lines.
    Returns detailed information about the operation.
    """
    start_guid = op.start_line_guid
    end_guid = getattr(op, "end_line_guid", None)
    new_content = getattr(op, "new_content", [])

    # Get sort orders
    start_row = conn.execute(
        "SELECT sort_order FROM file_lines WHERE line_guid = ? AND file_id = ? AND is_deleted = 0",
        (start_guid, file_id),
    ).fetchone()

    if not start_row:
        return {"status": "error", "message": f"Start GUID not found: {start_guid}"}

    start_sort = start_row[0]
    end_sort = start_sort

    if end_guid:
        end_row = conn.execute(
            "SELECT sort_order FROM file_lines WHERE line_guid = ? AND file_id = ? AND is_deleted = 0",
            (end_guid, file_id),
        ).fetchone()
        if end_row:
            end_sort = end_row[0]

    # Count lines that will be deleted
    count_row = conn.execute(
        """
        SELECT COUNT(*) FROM file_lines
        WHERE file_id = ?
          AND sort_order >= ?
          AND sort_order <= ?
          AND is_deleted = 0
    """,
        (file_id, start_sort, end_sort),
    ).fetchone()
    lines_deleted = count_row[0] if count_row else 0

    # Soft delete the range
    conn.execute(
        """
        UPDATE file_lines
        SET is_deleted = 1
        WHERE file_id = ?
          AND sort_order >= ?
          AND sort_order <= ?
          AND is_deleted = 0
    """,
        (file_id, start_sort, end_sort),
    )

    # Insert new lines
    for i, line in enumerate(new_content):
        new_guid = str(uuid4())
        conn.execute(
            """
            INSERT INTO file_lines
                (line_guid, file_id, sort_order, content, content_hash, version, is_deleted)
            VALUES (?, ?, ?, ?, ?, 1, 0)
        """,
            (new_guid, file_id, start_sort + (i * 0.5), line, _compute_hash(line)),
        )

    return {
        "status": "success",
        "lines_deleted": lines_deleted,
        "lines_inserted": len(new_content),
    }


def apply_insert_after(conn: sqlite3.Connection, file_id: int, op) -> Dict[str, Any]:
    """Insert new lines after a specific GUID."""
    after_guid = getattr(op, "after_guid", None)
    new_contents = getattr(op, "new_content", [])

    if not new_contents:
        return {"status": "success", "lines_inserted": 0}

    current_after = after_guid
    for content in new_contents:
        new_sort = get_insert_sort_order(conn, file_id, current_after)
        new_guid = str(uuid4())
        conn.execute(
            """
            INSERT INTO file_lines
                (line_guid, file_id, sort_order, content, content_hash, version, is_deleted)
            VALUES (?, ?, ?, ?, ?, 1, 0)
        """,
            (new_guid, file_id, new_sort, content, _compute_hash(content)),
        )
        current_after = new_guid

    return {"status": "success", "lines_inserted": len(new_contents)}


def apply_delete_lines(conn: sqlite3.Connection, file_id: int, op) -> Dict[str, Any]:
    """
    Delete a range of lines using start_line_guid and optional end_line_guid.
    """
    start_guid = op.start_line_guid
    end_guid = getattr(op, "end_line_guid", None)

    start_row = conn.execute(
        "SELECT sort_order FROM file_lines WHERE line_guid = ? AND file_id = ? AND is_deleted = 0",
        (start_guid, file_id),
    ).fetchone()

    if not start_row:
        return {"status": "error", "message": f"Start GUID not found: {start_guid}"}

    start_sort = start_row[0]
    end_sort = start_sort

    if end_guid:
        end_row = conn.execute(
            "SELECT sort_order FROM file_lines WHERE line_guid = ? AND file_id = ? AND is_deleted = 0",
            (end_guid, file_id),
        ).fetchone()
        if end_row:
            end_sort = end_row[0]

    # Count lines in range
    count_row = conn.execute(
        """
        SELECT COUNT(*) FROM file_lines
        WHERE file_id = ?
          AND sort_order >= ?
          AND sort_order <= ?
          AND is_deleted = 0
    """,
        (file_id, start_sort, end_sort),
    ).fetchone()
    lines_deleted = count_row[0] if count_row else 0

    # Soft delete the range
    conn.execute(
        """
        UPDATE file_lines
        SET is_deleted = 1
        WHERE file_id = ?
          AND sort_order >= ?
          AND sort_order <= ?
          AND is_deleted = 0
    """,
        (file_id, start_sort, end_sort),
    )

    return {"status": "success", "lines_deleted": lines_deleted}


def apply_update_documentation(conn: sqlite3.Connection, file_id: int, op):
    new_content = getattr(op, "new_content", "")
    conn.execute(
        """
        INSERT INTO file_documentation (file_id, content, version, updated_at)
        VALUES (?, ?, 1, datetime('now'))
        ON CONFLICT(file_id) DO UPDATE SET
            content = excluded.content,
            version = file_documentation.version + 1,
            updated_at = datetime('now')
    """,
        (file_id, new_content),
    )


def apply_find_replace(conn: sqlite3.Connection, file_id: int, op) -> Dict[str, Any]:
    """
    Apply a find/replace operation to the entire file content.

    This is intentionally simple and robust: reconstruct → replace → re-initialize
    lines. It is the preferred fallback when GUID-based editing fails under
    constrained LLMs.
    """
    import re

    from .db import reconstruct_file_content
    from .writer import initialize_file_lines

    # Resolve file path for re-initialization
    row = conn.execute("SELECT file_path FROM files WHERE file_id = ? AND is_deleted = 0", (file_id,)).fetchone()
    if not row:
        return {"status": "error", "message": f"file_id {file_id} not found"}

    file_path = row["file_path"] if isinstance(row, sqlite3.Row) else row[0]
    original = reconstruct_file_content(conn, file_id)

    find = getattr(op, "find", "")
    replace = getattr(op, "replace", "")
    use_regex = bool(getattr(op, "regex", False))
    count = getattr(op, "count", None)

    if not find:
        return {"status": "error", "message": "find string is empty"}

    try:
        if use_regex:
            flags = 0
            pattern = re.compile(find, flags)
            if count is None:
                new_content, n = pattern.subn(replace, original)
            else:
                new_content, n = pattern.subn(replace, original, count=count)
        else:
            if count is None:
                n = original.count(find)
                new_content = original.replace(find, replace)
            else:
                n = min(count, original.count(find))
                new_content = original.replace(find, replace, count)

        if n == 0:
            return {
                "status": "success",
                "replacements": 0,
                "message": "No matches found; file unchanged",
            }

        # Re-initialize line storage with the new content
        init_result = initialize_file_lines(file_path, new_content)
        if init_result.get("status") != "success":
            return {
                "status": "error",
                "message": f"Re-initialize after find_replace failed: {init_result.get('message')}",
            }

        return {
            "status": "success",
            "replacements": n,
            "message": f"Applied {n} replacement(s)",
        }
    except re.error as e:
        return {"status": "error", "message": f"Invalid regex: {e}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def apply_full_replace(conn: sqlite3.Connection, file_id: int, op) -> Dict[str, Any]:
    """
    Replace the entire file content. Used for small files and as a reliable fallback.
    Reconstructs line storage from the provided new_content.
    """
    from .writer import initialize_file_lines

    row = conn.execute("SELECT file_path FROM files WHERE file_id = ? AND is_deleted = 0", (file_id,)).fetchone()
    if not row:
        return {"status": "error", "message": f"file_id {file_id} not found"}

    file_path = row["file_path"] if isinstance(row, sqlite3.Row) else row[0]
    new_content = getattr(op, "new_content", "") or ""
    if isinstance(new_content, list):
        new_content = "\n".join(str(line) for line in new_content)

    if not str(new_content).strip():
        return {"status": "error", "message": "new_content is empty"}

    safety = validate_source_content(new_content, file_path=file_path)
    if not safety.get("ok"):
        return {"status": "error", "message": safety.get("message", "content rejected")}

    init_result = initialize_file_lines(file_path, new_content)
    if init_result.get("status") != "success":
        return {
            "status": "error",
            "message": f"Re-initialize after full_replace failed: {init_result.get('message')}",
        }

    return {
        "status": "success",
        "lines": init_result.get("line_count"),
        "message": f"Full file replaced ({init_result.get('line_count', '?')} lines)",
    }


def apply_diff(conn: sqlite3.Connection, file_id: int, op) -> Dict[str, Any]:
    """
    Apply a unified diff to file content.
    Uses a simple line-oriented algorithm suitable for LLM-generated patches.
    """
    from .db import reconstruct_file_content
    from .writer import initialize_file_lines

    row = conn.execute("SELECT file_path FROM files WHERE file_id = ? AND is_deleted = 0", (file_id,)).fetchone()
    if not row:
        return {"status": "error", "message": f"file_id {file_id} not found"}

    file_path = row["file_path"] if isinstance(row, sqlite3.Row) else row[0]
    original = reconstruct_file_content(conn, file_id)
    diff_text = getattr(op, "diff", "") or ""

    try:
        # Prefer stdlib if the diff is a proper unified diff from difflib
        original_lines = original.splitlines(keepends=True)
        # Normalize diff line endings
        diff_lines = diff_text.splitlines(keepends=True)

        # Try difflib.restore / manual application via patch-like logic
        # Simple approach: extract '+' lines and context using difflib.unified_diff inverse
        # Fall back to applying with a minimal hunk parser
        new_lines = _apply_unified_diff(original_lines, diff_lines)
        if new_lines is None:
            return {
                "status": "error",
                "message": "Failed to apply unified diff (no matching context)",
            }

        new_content = "".join(new_lines)
        # Ensure trailing newline consistency
        if original.endswith("\n") and not new_content.endswith("\n"):
            new_content += "\n"

        init_result = initialize_file_lines(file_path, new_content)
        if init_result.get("status") != "success":
            return {
                "status": "error",
                "message": f"Re-initialize after apply_diff failed: {init_result.get('message')}",
            }

        return {
            "status": "success",
            "lines": init_result.get("line_count"),
            "message": f"Diff applied ({init_result.get('line_count', '?')} lines)",
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


def _apply_unified_diff(original_lines, diff_lines):
    """
    Minimal unified-diff applicator.
    Returns new list of lines, or None on failure.
    """
    # Strip optional file headers
    i = 0
    while i < len(diff_lines) and (
        diff_lines[i].startswith("---")
        or diff_lines[i].startswith("+++")
        or diff_lines[i].startswith("Index:")
        or diff_lines[i].startswith("diff ")
    ):
        i += 1

    list(original_lines)
    # Work with lines without requiring keepends consistency
    src = [l.rstrip("\n\r") for l in original_lines]
    out = []
    src_idx = 0

    while i < len(diff_lines):
        line = diff_lines[i]
        raw = line.rstrip("\n\r")

        if raw.startswith("@@"):
            # Parse hunk header: @@ -start,count +start,count @@
            import re

            m = re.search(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", raw)
            if not m:
                i += 1
                continue
            old_start = int(m.group(1)) - 1  # 0-based
            # Copy unchanged lines up to hunk start
            while src_idx < old_start and src_idx < len(src):
                out.append(src[src_idx] + "\n")
                src_idx += 1
            i += 1
            continue

        if raw.startswith(" "):
            # Context line – must match
            expected = raw[1:]
            if src_idx >= len(src) or src[src_idx] != expected:
                # Try to resync: search forward a little
                found = False
                for look in range(src_idx, min(src_idx + 20, len(src))):
                    if src[look] == expected:
                        while src_idx < look:
                            out.append(src[src_idx] + "\n")
                            src_idx += 1
                        found = True
                        break
                if not found:
                    return None
            out.append(src[src_idx] + "\n")
            src_idx += 1
            i += 1
        elif raw.startswith("-"):
            # Deletion – skip source line
            expected = raw[1:]
            if src_idx < len(src) and src[src_idx] == expected:
                src_idx += 1
            else:
                # Soft: skip if nearby
                for look in range(src_idx, min(src_idx + 5, len(src))):
                    if src[look] == expected:
                        src_idx = look + 1
                        break
            i += 1
        elif raw.startswith("+"):
            # Addition
            out.append(raw[1:] + "\n")
            i += 1
        elif raw.startswith("\\"):
            # "\ No newline at end of file"
            i += 1
        else:
            i += 1

    # Copy remaining source lines
    while src_idx < len(src):
        out.append(src[src_idx] + "\n")
        src_idx += 1

    return out


def apply_create_file(conn: sqlite3.Connection, file_id: int, op) -> Dict[str, Any]:
    """
    Create a new file in the governed store from a create_file operation.

    Called only from apply_edit_proposal after reviewer approval.
    Producer: developer agent EditPayload (type create_file).
    """
    from .writer import initialize_file_lines

    # Prefer op path; fall back to files table for this file_id
    file_path = getattr(op, "target_file_path", None)
    if not file_path:
        row = conn.execute(
            "SELECT file_path FROM files WHERE file_id = ? AND is_deleted = 0",
            (file_id,),
        ).fetchone()
        if not row:
            return {"status": "error", "message": f"file_id {file_id} not found"}
        file_path = row["file_path"] if isinstance(row, sqlite3.Row) else row[0]

    # Refuse if THIS path already has live lines (not the proposal's primary file_id)
    row_existing = conn.execute(
        "SELECT file_id FROM files WHERE file_path = ? AND is_deleted = 0",
        (file_path,),
    ).fetchone()
    check_id = None
    if row_existing:
        check_id = row_existing["file_id"] if hasattr(row_existing, "keys") else row_existing[0]
    if check_id is not None:
        existing = conn.execute(
            "SELECT COUNT(*) FROM file_lines WHERE file_id = ? AND is_deleted = 0",
            (check_id,),
        ).fetchone()
        count = existing[0] if existing else 0
        if count > 0:
            return {
                "status": "error",
                "message": (f"create_file refused: {file_path!r} already has {count} lines (use full_replace to overwrite)"),
            }

    initial = getattr(op, "initial_content", None) or []
    if isinstance(initial, str):
        content = initial
    else:
        content = "\n".join(str(line) for line in initial)
    if content and not content.endswith("\n"):
        # normalize: join without forcing trailing newline beyond list semantics
        pass
    if not str(content).strip() and initial != [] and initial != [""]:
        # empty file is allowed if explicitly empty list; non-empty required only when content is whitespace-only from bad data
        pass

    safety = validate_source_content(content if content is not None else "", file_path=file_path)
    if not safety.get("ok"):
        return {"status": "error", "message": safety.get("message", "content rejected")}

    init_result = initialize_file_lines(file_path, content if content is not None else "")
    if init_result.get("status") != "success":
        return {
            "status": "error",
            "message": f"create_file initialize failed: {init_result.get('message')}",
        }

    return {
        "status": "success",
        "file_id": init_result.get("file_id", file_id),
        "lines": init_result.get("line_count"),
        "message": f"Created file {file_path} ({init_result.get('line_count', 0)} lines)",
    }


def apply_edit_proposal(proposal_id: str) -> Dict[str, Any]:
    with get_db_connection() as conn:
        proposal_row = conn.execute("SELECT * FROM edit_proposals WHERE proposal_id = ?", (proposal_id,)).fetchone()

        if not proposal_row or proposal_row["status"] != "approved":
            return {"status": "error", "message": "Proposal not approved"}

        if not validate_proposal(conn, dict(proposal_row)):
            log_error(
                "file_editing",
                "apply",
                "HIGH",
                "Optimistic validation failed",
                proposal_id=proposal_id,
            )
            return {"status": "conflicted"}

        try:
            from .edit_payload import EditPayload

            payload = EditPayload.model_validate_json(proposal_row["edit_payload"])
            file_id = proposal_row["target_file_id"]

            # Strict GUID validation
            for op in payload.operations:
                if not _validate_operation_guids(conn, file_id, op):
                    log_error(
                        "file_editing",
                        "apply",
                        "HIGH",
                        f"Referenced line GUID not found in operation: {op.type}",
                        proposal_id=proposal_id,
                    )
                    return {
                        "status": "conflicted",
                        "message": "Referenced line GUID not found",
                    }

            operation_results = []

            for op in payload.operations:
                if op.type == "replace_block":
                    result = apply_replace_block(conn, file_id, op)
                    operation_results.append(result)
                elif op.type == "insert_after":
                    result = apply_insert_after(conn, file_id, op)
                    operation_results.append(result)
                elif op.type == "delete_lines":
                    result = apply_delete_lines(conn, file_id, op)
                    operation_results.append(result)
                elif op.type == "update_documentation":
                    apply_update_documentation(conn, file_id, op)
                elif op.type == "find_replace":
                    result = apply_find_replace(conn, file_id, op)
                    operation_results.append(result)
                elif op.type == "full_replace":
                    result = apply_full_replace(conn, file_id, op)
                    operation_results.append(result)
                elif op.type == "apply_diff":
                    result = apply_diff(conn, file_id, op)
                    operation_results.append(result)
                elif op.type == "create_file":
                    result = apply_create_file(conn, file_id, op)
                    operation_results.append(result)
                else:
                    operation_results.append(
                        {
                            "status": "error",
                            "message": f"Unknown operation type: {getattr(op, 'type', op)}",
                        }
                    )

            # Any failed op => terminal error, do not mark applied
            failed = [r for r in operation_results if isinstance(r, dict) and r.get("status") not in ("success", None)]
            # update_documentation may return None historically — treat missing status as ok only for empty dict issues
            failed = [r for r in operation_results if isinstance(r, dict) and r.get("status") == "error"]
            if failed:
                conn.execute(
                    "UPDATE edit_proposals SET status = 'error' WHERE proposal_id = ?",
                    (proposal_id,),
                )
                return {
                    "status": "error",
                    "proposal_id": proposal_id,
                    "message": failed[0].get("message", "operation failed"),
                    "operations": operation_results,
                }

            conn.execute(
                "UPDATE edit_proposals SET status = 'applied' WHERE proposal_id = ?",
                (proposal_id,),
            )

            return {
                "status": "success",
                "proposal_id": proposal_id,
                "operations": operation_results,
            }

        except Exception as e:
            log_error("file_editing", "apply", "HIGH", str(e), proposal_id=proposal_id)
            return {"status": "error", "message": str(e)}
