import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any
from uuid import uuid4

from core.content_safety import validate_source_content
from utils.git_operations import git_commit

from .db import get_db_connection, log_error, reconstruct_file_content
from .editing import apply_edit_proposal

# =============================================================================
# PrizmForge/file_editing/writer.py
# Version: 1.5 - Path normalization against configured project_directory
# Purpose: FileWriterAgent - Materializes proposals to disk + git + invalidation
# =============================================================================


def _compute_hash(content: str) -> str:
    return hashlib.md5(content.encode(), usedforsecurity=False).hexdigest()


def _get_or_create_file_id_short(conn, target_file_path: str) -> int:
    """File-id lookup that never turns the caller's connection into a writer.

    ``materialize_proposal`` captures before-state on its main connection and
    then calls ``apply_edit_proposal`` (which writes on its own connection).
    If this lookup INSERTs on the main connection it holds a RESERVED lock
    during the apply phase, and the second writer busy-waits ~30s before
    dying with SQLITE_BUSY. Allocate any missing row on a short-lived
    connection (committed immediately) so the main connection stays read-only.
    """
    row = conn.execute(
        "SELECT file_id FROM files WHERE file_path = ? AND is_deleted = 0",
        (target_file_path,),
    ).fetchone()
    if row:
        return row[0]
    with get_db_connection() as short:
        cursor = short.execute(
            """INSERT INTO files (file_path, current_version, is_deleted, has_been_written_to_disk)
               VALUES (?, 1, 0, 0)""",
            (target_file_path,),
        )
        return cursor.lastrowid


def initialize_file_lines(file_path: str, content: str, conn=None) -> dict[str, Any]:
    """
    Initialize a file in the governed editing system with line-level GUIDs.

    This should be called during project indexing to populate the files + file_lines tables.

    Pass the caller's open connection via ``conn`` when the caller is already
    inside a write transaction: opening a second writer connection while one
    already holds a RESERVED lock busy-waits ~30s then dies with SQLITE_BUSY.
    """
    try:
        if conn is not None:
            return _initialize_lines_impl(conn, file_path, content)
        with get_db_connection() as conn:
            return _initialize_lines_impl(conn, file_path, content)
    except Exception as e:
        log_error("file_editing", "initialize", "HIGH", str(e), file_path=file_path)
        return {"status": "error", "message": str(e)}


def _initialize_lines_impl(conn, file_path: str, content: str) -> dict[str, Any]:
    # 1. Get or create file record
    cursor = conn.execute("SELECT file_id FROM files WHERE file_path = ?", (file_path,))
    row = cursor.fetchone()

    if row:
        file_id = row["file_id"] if hasattr(row, "keys") else row[0]
        # Delete existing lines (we're re-initializing)
        conn.execute("DELETE FROM file_lines WHERE file_id = ?", (file_id,))
    else:
        # Create new file record
        cursor = conn.execute(
            """
            INSERT INTO files (file_path, current_version, is_deleted, has_been_written_to_disk)
            VALUES (?, 1, 0, 1)
        """,
            (file_path,),
        )
        file_id = cursor.lastrowid

    # 2. Split content into lines and create line records
    lines = content.split("\n")
    initial_gap = 1024.0

    for i, line_content in enumerate(lines):
        line_guid = str(uuid4())
        sort_order = (i + 1) * initial_gap
        content_hash = _compute_hash(line_content)

        conn.execute(
            """
            INSERT INTO file_lines
            (line_guid, file_id, sort_order, content, content_hash, version, is_deleted)
            VALUES (?, ?, ?, ?, ?, 1, 0)
        """,
            (line_guid, file_id, sort_order, line_content, content_hash),
        )

    return {"status": "success", "file_id": file_id, "line_count": len(lines)}


def _resolve_contained_path(file_path: str, project_dir: Path) -> Path:
    """
    Resolve file_path and ensure it remains inside project_dir.
    Raises ValueError on containment failure.
    """
    root = project_dir.expanduser().resolve()
    candidate = Path(file_path).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    # resolve(strict=False) canonicalizes .. and symlinks where possible
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as e:
        raise ValueError(f"Path escapes project directory: {file_path!r} → {resolved} (root={root})") from e
    return resolved


def write_file_to_disk(file_path: str, content: str, proposal_id: str | None = None) -> dict[str, Any]:
    """Atomic write using temp file + os.replace(), with project-root containment."""
    try:
        from core.config import get_config

        config = get_config()
        project_dir = Path(config.get("project_directory", "./project"))

        path = _resolve_contained_path(file_path, project_dir)

        safety = validate_source_content(content, file_path=str(path))
        if not safety.get("ok"):
            log_error(
                "file_editing",
                "writer",
                "HIGH",
                safety.get("message", "content rejected"),
                proposal_id=proposal_id,
            )
            return {
                "status": "error",
                "message": safety.get("message", "content rejected"),
            }

        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", delete=False, dir=path.parent, suffix=".tmp", encoding="utf-8") as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        os.replace(tmp_path, str(path))
        return {"status": "success", "file_path": str(path)}
    except ValueError as e:
        # Containment / path policy failure
        log_error("file_editing", "writer", "HIGH", str(e), proposal_id=proposal_id)
        return {"status": "error", "message": str(e)}
    except Exception as e:
        log_error("file_editing", "writer", "HIGH", str(e), proposal_id=proposal_id)
        return {"status": "error", "message": str(e)}


def invalidate_other_proposals(conn, current_proposal_id: str, affected_guids: list[str]):
    """After successful write, mark overlapping pending proposals as needs_revalidation."""
    if not affected_guids:
        return
    try:
        # Get all pending/approved proposals (excluding the current one)
        cursor = conn.execute(
            """
            SELECT proposal_id, affected_line_guids
            FROM edit_proposals
            WHERE proposal_id != ?
            AND status IN ('pending', 'under_review', 'approved')
        """,
            (current_proposal_id,),
        )

        other_proposals = cursor.fetchall()

        invalidated_count = 0
        for other_proposal in other_proposals:
            other_id = other_proposal["proposal_id"]
            other_guids_json = other_proposal["affected_line_guids"]

            if not other_guids_json:
                continue

            # Parse the affected GUIDs
            other_guids = json.loads(other_guids_json)

            # Check for overlap
            if set(affected_guids) & set(other_guids):
                # Mark as needs revalidation
                conn.execute(
                    """
                    UPDATE edit_proposals
                    SET status = 'needs_revalidation'
                    WHERE proposal_id = ?
                """,
                    (other_id,),
                )
                invalidated_count += 1

        if invalidated_count > 0:
            print(f"🔄 Invalidated {invalidated_count} overlapping proposal(s) after {current_proposal_id[:8]}")

    except Exception as e:
        log_error(
            "file_editing",
            "invalidation",
            "MEDIUM",
            str(e),
            proposal_id=current_proposal_id,
        )


def materialize_proposal(proposal_id: str) -> dict[str, Any]:  # noqa: C901
    """
    Apply proposal (if needed), write ALL modified files in the proposal to disk,
    record the change in file_modifications, invalidate overlapping proposals,
    and perform git commit if enabled.
    """
    from core.config import get_config
    from file_editing.edit_payload import EditPayload

    with get_db_connection() as conn:
        proposal = conn.execute("SELECT * FROM edit_proposals WHERE proposal_id = ?", (proposal_id,)).fetchone()

        if not proposal:
            return {"status": "error", "message": "Proposal not found"}

        # Single source of truth for the project root
        project_dir = Path(get_config().get("project_directory", "./project")).resolve()

        # ------------------------------------------------------------------
        # 1. Capture BEFORE state for every file that will be touched
        # ------------------------------------------------------------------
        affected_paths: set[str] = set()
        if proposal["target_file_path"]:
            affected_paths.add(proposal["target_file_path"])

        try:
            payload = EditPayload.model_validate_json(proposal["edit_payload"])
            for op in payload.operations:
                op_path = getattr(op, "target_file_path", None)
                if op_path:
                    affected_paths.add(op_path)
        except Exception as e:
            log_error("file_editing", "materialize", "MEDIUM", f"Payload parse warning: {e}", proposal_id=proposal_id)

        before_state: dict[str, dict] = {}
        for path in affected_paths:
            fid = _get_or_create_file_id_short(conn, path)
            content = reconstruct_file_content(conn, fid) or ""
            before_state[path] = {
                "file_id": fid,
                "content": content,
                "hash": _compute_hash(content),
            }

        # ------------------------------------------------------------------
        # 2. Apply the proposal in the database if not already applied
        # ------------------------------------------------------------------
        if proposal["status"] != "applied":
            apply_result = apply_edit_proposal(proposal_id)
            if apply_result.get("status") != "success":
                terminal = apply_result.get("status") or "error"
                if terminal not in ("conflicted", "error", "failed"):
                    terminal = "error"
                try:
                    conn.execute(
                        "UPDATE edit_proposals SET status = ? WHERE proposal_id = ? AND status = 'approved'",
                        (terminal, proposal_id),
                    )
                except Exception as e:
                    print(f"    ⚠️  Exception handled in writer.py: {e}")
                return apply_result

        # ------------------------------------------------------------------
        # 3. Materialize each affected file to disk + record audit row
        # ------------------------------------------------------------------
        write_results = []
        task_id = proposal["task_id"] if "task_id" in proposal.keys() else None
        git_failed = None

        for target_path in affected_paths:
            op_file_id = before_state[target_path]["file_id"]
            content_after = reconstruct_file_content(conn, op_file_id) or ""
            hash_after = _compute_hash(content_after)

            res = write_file_to_disk(target_path, content_after, proposal_id)
            write_results.append(res)

            if res.get("status") == "success":
                # ----------------------------------------------------------
                # Normalize path against the configured project_directory.
                # Prefer the absolute path returned by write_file_to_disk
                # when available; otherwise force containment ourselves.
                # ----------------------------------------------------------
                written_path = res.get("file_path") or target_path
                try:
                    resolved_path = _resolve_contained_path(written_path, project_dir)
                    rel_path = str(resolved_path.relative_to(project_dir)).replace("\\", "/")
                except ValueError as path_err:
                    log_error(
                        "file_editing",
                        "path_normalize",
                        "MEDIUM",
                        f"Could not normalize path inside project_directory: {path_err}",
                        proposal_id=proposal_id,
                    )
                    resolved_path = None
                    rel_path = None

                # Refresh symbol index (only when we have a clean relative path)
                if rel_path and rel_path.endswith(".py"):
                    try:
                        from core.index_context import refresh_file_symbols

                        refresh_file_symbols(rel_path, content_after)
                    except Exception as _idx_err:
                        log_error(
                            "file_editing",
                            "index_refresh",
                            "LOW",
                            f"Symbol index refresh failed: {_idx_err}",
                            proposal_id=proposal_id,
                        )

                # Update files table
                conn.execute(
                    "UPDATE files SET has_been_written_to_disk = 1, current_version = current_version + 1 WHERE file_id = ?",
                    (op_file_id,),
                )
                conn.execute(
                    "INSERT INTO file_write_log (proposal_id, file_id, status) VALUES (?, ?, 'success')",
                    (proposal_id, op_file_id),
                )

                # ----------------------------------------------------------
                # Record the change in file_modifications
                # ----------------------------------------------------------
                try:
                    conn.execute(
                        """
                        INSERT INTO file_modifications
                            (file_path, operation, content_before, content_after,
                             content_hash_before, content_hash_after,
                             changed_by, task_id, timestamp)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                        """,
                        (
                            target_path,
                            "materialize",
                            before_state[target_path]["content"],
                            content_after,
                            before_state[target_path]["hash"],
                            hash_after,
                            "developer",
                            task_id,
                        ),
                    )
                except Exception as e:
                    log_error(
                        "file_editing",
                        "file_modifications",
                        "MEDIUM",
                        f"Failed to record modification: {e}",
                        proposal_id=proposal_id,
                    )

                # ----------------------------------------------------------
                # Git add + commit using the structured git_commit() helper
                # ----------------------------------------------------------
                if resolved_path is not None and rel_path is not None:
                    git_result = git_commit(
                        rel_path,
                        f"[PrizmForge] Agent edit via proposal {proposal_id[:8]}",
                    )
                    if not git_result.get("ok") and git_result.get("attempted"):
                        # Keep the FIRST failure: a later file's success must
                        # never clear an earlier hook failure (multi-file
                        # proposals carry the failure to the caller).
                        if git_failed is None:
                            git_failed = git_result
            else:
                conn.execute(
                    "UPDATE edit_proposals SET status = 'error' WHERE proposal_id = ?",
                    (proposal_id,),
                )
                conn.execute(
                    "INSERT INTO file_write_log (proposal_id, file_id, status) VALUES (?, ?, 'error')",
                    (proposal_id, op_file_id),
                )

        # Invalidate overlapping proposals (existing logic)
        affected_guids_json = proposal["affected_line_guids"]
        affected = json.loads(affected_guids_json) if affected_guids_json else []
        invalidate_other_proposals(conn, proposal_id, affected)

        overall_success = all(r.get("status") == "success" for r in write_results)
        if not overall_success:
            status = "error"
        elif git_failed is not None:
            status = "git_failed"
        else:
            status = "success"

    # Log the hook failure AFTER the write transaction has committed: a
    # log_error inside the open transaction hits "database is locked" and its
    # errors row is silently dropped, breaking the closed loop.
    if git_failed is not None:
        log_error(
            "CRITICAL",
            "file_editing",
            "git_commit",
            f"git {git_failed.get('stage', '?')} failed (code={git_failed.get('code')}): " + (git_failed.get("stderr") or "")[:500],
            proposal_id=proposal_id,
            file_path=git_failed.get("file_path"),
            task_id=task_id,
        )

    return {
        "status": status,
        "proposal_id": proposal_id,
        "materialized_files": list(affected_paths),
        "results": write_results,
        "git_failed": git_failed,
    }
