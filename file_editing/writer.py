import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any
from uuid import uuid4

from core.content_safety import validate_source_content

from .db import get_db_connection, log_error, reconstruct_file_content
from .editing import apply_edit_proposal

# =============================================================================
# PrizmForge/file_editing/writer.py
# Version: 1.4 - Critical column name fixes + improved invalidation + init files
# Purpose: FileWriterAgent - Materializes proposals to disk + git + invalidation
# =============================================================================


def _compute_hash(content: str) -> str:
    return hashlib.md5(content.encode(), usedforsecurity=False).hexdigest()


def initialize_file_lines(file_path: str, content: str) -> dict[str, Any]:
    """
    Initialize a file in the governed editing system with line-level GUIDs.

    This should be called during project indexing to populate the files + file_lines tables.
    """
    try:
        with get_db_connection() as conn:
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

    except Exception as e:
        log_error("file_editing", "initialize", "HIGH", str(e), file_path=file_path)
        return {"status": "error", "message": str(e)}


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
    from file_editing.edit_payload import EditPayload
    from workflow.proposal_builder import _get_or_create_file_id

    with get_db_connection() as conn:
        proposal = conn.execute("SELECT * FROM edit_proposals WHERE proposal_id = ?", (proposal_id,)).fetchone()

        if not proposal:
            return {"status": "error", "message": "Proposal not found"}

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
            fid = _get_or_create_file_id(conn, path)
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

        for target_path in affected_paths:
            op_file_id = before_state[target_path]["file_id"]
            content_after = reconstruct_file_content(conn, op_file_id) or ""
            hash_after = _compute_hash(content_after)

            res = write_file_to_disk(target_path, content_after, proposal_id)
            write_results.append(res)

            if res.get("status") == "success":
                # Refresh symbol index (existing logic)
                try:
                    from core.config import get_config
                    from core.index_context import refresh_file_symbols

                    pd = Path(get_config().get("project_directory", "./project")).resolve()
                    rel = str(Path(target_path).resolve().relative_to(pd)).replace("\\", "/")
                    if rel.endswith(".py"):
                        refresh_file_symbols(rel, content_after)
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
                # NEW: Record the change in file_modifications
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

                # Optional git commit (existing logic)
                try:
                    project_root = Path(target_path).parent
                    subprocess.run(["git", "add", target_path], cwd=project_root, check=False, timeout=10)
                    subprocess.run(
                        ["git", "commit", "-m", f"[PrizmForge] Agent edit via proposal {proposal_id[:8]}"], cwd=project_root, check=False, timeout=10
                    )
                except Exception as e:
                    print(f"    ⚠️  Exception handled in writer.py: {e}")
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
        return {
            "status": "success" if overall_success else "error",
            "proposal_id": proposal_id,
            "materialized_files": list(affected_paths),
            "results": write_results,
        }
