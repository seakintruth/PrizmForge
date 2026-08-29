import hashlib
import json
import os
import sqlite3
import subprocess
import tempfile
from datetime import datetime
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

    One rule for both lookups in this file: ``file_path`` is UNIQUE, so a path
    maps to exactly one ``files`` row regardless of ``is_deleted``; a
    soft-deleted row is resurrected at initialize time. Do NOT filter on
    ``is_deleted`` here, or re-creating a deleted path would collide with the
    UNIQUE constraint.
    """
    row = conn.execute(
        "SELECT file_id FROM files WHERE file_path = ?",
        (target_file_path,),
    ).fetchone()
    if row:
        return row[0]
    try:
        with get_db_connection() as short:
            cursor = short.execute(
                """INSERT INTO files (file_path, current_version, is_deleted, has_been_written_to_disk)
                   VALUES (?, 1, 0, 0)""",
                (target_file_path,),
            )
            return cursor.lastrowid
    except sqlite3.IntegrityError:
        # Lost the race with a concurrent materialize for the same new path —
        # reuse the row the winner committed.
        with get_db_connection() as short:
            row = short.execute(
                "SELECT file_id FROM files WHERE file_path = ?",
                (target_file_path,),
            ).fetchone()
            if row:
                return row[0]
        raise


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
        log_error("HIGH", "file_editing", "initialize", str(e), file_path=file_path)
        return {"status": "error", "message": str(e)}


def _initialize_lines_impl(conn, file_path: str, content: str) -> dict[str, Any]:
    # 1. Get or create file record. file_path is UNIQUE, so reuse the existing
    # row even when soft-deleted; resurrecting keeps one live row per path.
    cursor = conn.execute(
        "SELECT file_id, is_deleted FROM files WHERE file_path = ?",
        (file_path,),
    )
    row = cursor.fetchone()

    if row:
        file_id = row["file_id"] if hasattr(row, "keys") else row[0]
        is_deleted = row["is_deleted"] if hasattr(row, "keys") else row[1]
        if is_deleted:
            conn.execute("UPDATE files SET is_deleted = 0 WHERE file_id = ?", (file_id,))
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


def _delete_file_from_disk(file_path: str, project_dir: Path) -> dict[str, Any]:
    """Remove a governed-deleted file from disk (contained).

    Both ValueError (path escapes the project root) and OSError (unlink
    failure — permission, missing dir) are surfaced as error results so
    materialize records a write-log 'error' row instead of leaving the
    governed store deleted while the disk file survives (residual P8).
    """
    try:
        resolved = _resolve_contained_path(file_path, project_dir)
        if resolved.exists():
            resolved.unlink()
        return {"status": "success", "file_path": str(resolved)}
    except ValueError as e:
        log_error("HIGH", "file_editing", "writer", str(e))
        return {"status": "error", "message": str(e)}
    except OSError as e:
        log_error("HIGH", "file_editing", "writer", f"disk removal failed: {e}")
        return {"status": "error", "message": f"disk removal failed: {e}"}


def _run_ruff_precheck(path: Path | None, project_dir: Path, rel_path: str) -> dict[str, Any]:
    """Optional in-process ruff pre-check before git (plan §7.2).

    Fast-feedfback fast-path only: the pre-commit hook remains authoritative
    when git is enabled. Returns ``{}`` when disabled via
    ``file_editing.in_process_ruff_check`` or when ruff is unavailable, so the
    git-only path is unchanged.
    """
    try:
        from core.config import get_config

        cfg = get_config().get("file_editing", {}) or {}
        if not cfg.get("in_process_ruff_check"):
            return {}
    except Exception:
        return {}
    if path is None or not path.exists():
        return {}
    try:
        proc = subprocess.run(
            ["ruff", "check", str(path)],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return {}
    if proc.returncode == 0:
        return {"attempted": True, "ok": True}
    return {
        "attempted": True,
        "ok": False,
        "code": proc.returncode,
        "stderr": (proc.stdout or "") + (proc.stderr or ""),
        "file_path": rel_path,
    }


def _record_lint_failure(task_id: str | None, proposal_id: str, lint_result: dict[str, Any]) -> None:
    """Surface an in-process ruff pre-check failure after the write transaction.

    Runs post-commit (mirroring the git-failure log placement): the feedback /
    event INSERTs use their own connections and would deadlock inside the open
    materialize transaction.
    """
    from core.db_connection import get_db_connection as _core_db
    from core.db_helpers import save_agent_feedback
    from core.events import publish_event

    publish_event(
        "edit.lint_failed",
        source="writer",
        task_id=task_id,
        proposal_id=proposal_id,
        payload=lint_result,
    )
    excerpt = (lint_result.get("stderr") or "")[:500]
    try:
        with _core_db() as conn:
            existing = conn.execute(
                "SELECT id FROM agent_feedback WHERE file_event_id = ? LIMIT 1",
                (proposal_id,),
            ).fetchone()
        if not existing:
            save_agent_feedback(
                agent_name="ruff_precheck",
                file_path=lint_result.get("file_path") or "",
                priority="CRITICAL",
                category="bug",
                message=f"in-process ruff pre-check failed (code={lint_result.get('code')}): {excerpt}",
                suggestion="Fix the ruff violations before continuing.",
                task_id=task_id or "",
                file_event_id=proposal_id,
            )
    except Exception as e:
        log_error("MEDIUM", "file_editing", "lint_feedback", f"Failed to record lint feedback: {e}", proposal_id=proposal_id)
    print(f"   🔴 In-process ruff pre-check failed (code={lint_result.get('code')})")
    print(f"      Excerpt: {excerpt[:200]}")


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
                "HIGH",
                "file_editing",
                "writer",
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
        log_error("HIGH", "file_editing", "writer", str(e), proposal_id=proposal_id)
        return {"status": "error", "message": str(e)}
    except Exception as e:
        log_error("HIGH", "file_editing", "writer", str(e), proposal_id=proposal_id)
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
            "MEDIUM",
            "file_editing",
            "invalidation",
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
            log_error("MEDIUM", "file_editing", "materialize", f"Payload parse warning: {e}", proposal_id=proposal_id)

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
        lint_failed = None

        for target_path in affected_paths:
            op_file_id = before_state[target_path]["file_id"]
            content_after = reconstruct_file_content(conn, op_file_id) or ""
            hash_after = _compute_hash(content_after)

            _deleted_row = conn.execute("SELECT is_deleted FROM files WHERE file_id = ?", (op_file_id,)).fetchone()
            is_deleted = bool(_deleted_row[0] if _deleted_row else 0)

            write_started_at = datetime.now().isoformat()
            if is_deleted:
                res = _delete_file_from_disk(target_path, project_dir)
            else:
                res = write_file_to_disk(target_path, content_after, proposal_id)
            write_results.append(res)
            write_completed_at = datetime.now().isoformat()

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
                        "MEDIUM",
                        "file_editing",
                        "path_normalize",
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
                            "LOW",
                            "file_editing",
                            "index_refresh",
                            f"Symbol index refresh failed: {_idx_err}",
                            proposal_id=proposal_id,
                        )

                # Update files table (skipped for deletions — row stays is_deleted)
                if not is_deleted:
                    conn.execute(
                        "UPDATE files SET has_been_written_to_disk = 1, current_version = current_version + 1 WHERE file_id = ?",
                        (op_file_id,),
                    )
                write_log_status = "deleted" if is_deleted else "success"
                conn.execute(
                    "INSERT INTO file_write_log (proposal_id, file_id, status, started_at, completed_at) VALUES (?, ?, ?, ?, ?)",
                    (proposal_id, op_file_id, write_log_status, write_started_at, write_completed_at),
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
                        "MEDIUM",
                        "file_editing",
                        "file_modifications",
                        f"Failed to record modification: {e}",
                        proposal_id=proposal_id,
                    )

                # ----------------------------------------------------------
                # Optional in-process ruff pre-check (plan §7.2)
                # ----------------------------------------------------------
                precheck = {}
                if lint_failed is None:
                    precheck = _run_ruff_precheck(resolved_path, project_dir, rel_path or target_path)
                    if precheck.get("attempted") and not precheck.get("ok"):
                        lint_failed = precheck
                        # Residual P5: a file whose write passed the ruff
                        # pre-check is NOT "success" — flip its write-log row so
                        # the audit trail carries the actual single status.
                        conn.execute(
                            "UPDATE file_write_log SET status = 'lint_failed' WHERE proposal_id = ? AND file_id = ?",
                            (proposal_id, op_file_id),
                        )

                # ----------------------------------------------------------
                # Git add + commit using the structured git_commit() helper
                # ----------------------------------------------------------
                if lint_failed is None and resolved_path is not None and rel_path is not None:
                    git_result = git_commit(
                        rel_path,
                        f"[PrizmForge] Agent edit via proposal {proposal_id[:8]}",
                        delete=is_deleted,
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
                    "INSERT INTO file_write_log (proposal_id, file_id, status, started_at, completed_at) VALUES (?, ?, 'error', ?, ?)",
                    (proposal_id, op_file_id, write_started_at, write_completed_at),
                )

        # Invalidate overlapping proposals (existing logic)
        affected_guids_json = proposal["affected_line_guids"]
        affected = json.loads(affected_guids_json) if affected_guids_json else []
        invalidate_other_proposals(conn, proposal_id, affected)

        overall_success = all(r.get("status") == "success" for r in write_results)
        if not overall_success:
            status = "error"
        elif lint_failed is not None:
            status = "lint_failed"
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

    # Surface the lint failure AFTER the write transaction has committed
    # (same reasoning as the git log below).
    if lint_failed is not None:
        log_error(
            "CRITICAL",
            "file_editing",
            "ruff_precheck",
            f"in-process ruff pre-check failed (code={lint_failed.get('code')}): " + (lint_failed.get("stderr") or "")[:500],
            proposal_id=proposal_id,
            file_path=lint_failed.get("file_path"),
            task_id=task_id,
        )
        _record_lint_failure(task_id, proposal_id, lint_failed)

    return {
        "status": status,
        "proposal_id": proposal_id,
        "materialized_files": list(affected_paths),
        "results": write_results,
        "git_failed": git_failed,
        "lint_failed": lint_failed,
    }
