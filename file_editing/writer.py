# =============================================================================
# PrizmForge/file_editing/writer.py
# Version: 1.4 - Critical column name fixes + improved invalidation + init files
# Purpose: FileWriterAgent - Materializes proposals to disk + git + invalidation
# =============================================================================

import os
import tempfile
import subprocess
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional, List
from uuid import uuid4
import json

from .db import get_db_connection, log_error, reconstruct_file_content
from .editing import apply_edit_proposal
from core.content_safety import validate_source_content

def _compute_hash(content: str) -> str:
    return hashlib.md5(content.encode()).hexdigest()

def initialize_file_lines(file_path: str, content: str) -> Dict[str, Any]:
    """
    Initialize a file in the governed editing system with line-level GUIDs.
    
    This should be called during project indexing to populate the files + file_lines tables.
    """
    try:
        with get_db_connection() as conn:
            # 1. Get or create file record
            cursor = conn.execute(
                "SELECT file_id FROM files WHERE file_path = ?",
                (file_path,)
            )
            row = cursor.fetchone()
            
            if row:
                file_id = row["file_id"] if hasattr(row, "keys") else row[0]
                # Delete existing lines (we're re-initializing)
                conn.execute("DELETE FROM file_lines WHERE file_id = ?", (file_id,))
            else:
                # Create new file record
                cursor = conn.execute("""
                    INSERT INTO files (file_path, current_version, is_deleted, has_been_written_to_disk)
                    VALUES (?, 1, 0, 1)
                """, (file_path,))
                file_id = cursor.lastrowid
            
            # 2. Split content into lines and create line records
            lines = content.split('\n')
            INITIAL_GAP = 1024.0
            
            for i, line_content in enumerate(lines):
                line_guid = str(uuid4())
                sort_order = (i + 1) * INITIAL_GAP
                content_hash = _compute_hash(line_content)
                
                conn.execute("""
                    INSERT INTO file_lines 
                    (line_guid, file_id, sort_order, content, content_hash, version, is_deleted)
                    VALUES (?, ?, ?, ?, ?, 1, 0)
                """, (line_guid, file_id, sort_order, line_content, content_hash))
            
            return {
                "status": "success",
                "file_id": file_id,
                "line_count": len(lines)
            }
            
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
    except ValueError:
        raise ValueError(
            f"Path escapes project directory: {file_path!r} → {resolved} (root={root})"
        )
    return resolved


def write_file_to_disk(file_path: str, content: str, proposal_id: Optional[str] = None) -> Dict[str, Any]:
    """Atomic write using temp file + os.replace(), with project-root containment."""
    try:
        from core.config import get_config
        config = get_config()
        project_dir = Path(config.get("project_directory", "./project"))

        path = _resolve_contained_path(file_path, project_dir)

        safety = validate_source_content(content, file_path=str(path))
        if not safety.get("ok"):
            log_error("file_editing", "writer", "HIGH", safety.get("message", "content rejected"),
                      proposal_id=proposal_id)
            return {"status": "error", "message": safety.get("message", "content rejected")}

        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode='w', delete=False, dir=path.parent, suffix='.tmp', encoding='utf-8') as tmp:
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


def invalidate_other_proposals(conn, current_proposal_id: str, affected_guids: List[str]):
    """After successful write, mark overlapping pending proposals as needs_revalidation."""
    if not affected_guids:
        return
    try:
        # Get all pending/approved proposals (excluding the current one)
        cursor = conn.execute("""
            SELECT proposal_id, affected_line_guids
            FROM edit_proposals
            WHERE proposal_id != ? 
            AND status IN ('pending', 'under_review', 'approved')
        """, (current_proposal_id,))
        
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
                conn.execute("""
                    UPDATE edit_proposals 
                    SET status = 'needs_revalidation'
                    WHERE proposal_id = ?
                """, (other_id,))
                invalidated_count += 1

        if invalidated_count > 0:
            print(f"🔄 Invalidated {invalidated_count} overlapping proposal(s) after {current_proposal_id[:8]}")
    
    except Exception as e:
        log_error("file_editing", "invalidation", "MEDIUM", str(e), proposal_id=current_proposal_id)

def materialize_proposal(proposal_id: str) -> Dict[str, Any]:
    """Apply proposal (if needed), write to disk, invalidate overlapping proposals, optional git commit."""
    with get_db_connection() as conn:
        proposal = conn.execute(
            "SELECT * FROM edit_proposals WHERE proposal_id = ?", (proposal_id,)
        ).fetchone()

        if not proposal:
            return {"status": "error", "message": "Proposal not found"}

        # Apply if not already applied
        if proposal["status"] != "applied":
            apply_result = apply_edit_proposal(proposal_id)
            if apply_result.get("status") != "success":
                # Ensure proposal is left in a terminal, observable state
                terminal = apply_result.get("status") or "error"
                if terminal not in ("conflicted", "error", "failed"):
                    terminal = "error"
                try:
                    conn.execute(
                        "UPDATE edit_proposals SET status = ? WHERE proposal_id = ? AND status = 'approved'",
                        (terminal, proposal_id),
                    )
                except Exception:
                    pass
                return apply_result

        # Get file path - sqlite3.Row supports dict-like access with []
        file_row = conn.execute(
            "SELECT file_path FROM files WHERE file_id = ?", (proposal["target_file_id"],)
        ).fetchone()
        
        # ✅ FIX: Use [] access instead of .get()
        if file_row:
            target_path = file_row["file_path"]
        else:
            # Fallback to proposal's target_file_path
            target_path = proposal["target_file_path"]

        content = reconstruct_file_content(conn, proposal["target_file_id"])
        result = write_file_to_disk(target_path, content, proposal_id)

        if result.get("status") == "success":
            try:
                from core.index_context import refresh_file_symbols
                # relative path for DB
                rel = str(target_path).replace("\\", "/")
                try:
                    from core.config import get_config
                    pd = Path(get_config().get("project_directory", "./project")).resolve()
                    rel = str(Path(target_path).resolve().relative_to(pd)).replace("\\", "/")
                except Exception:
                    rel = Path(target_path).name
                if rel.endswith(".py"):
                    refresh_file_symbols(rel, content)
            except Exception as _idx_err:
                log_error(
                    "file_editing",
                    "index_refresh",
                    "LOW",
                    f"symbol index after materialize failed: {_idx_err}",
                    proposal_id=proposal_id,
                )
            # Update file metadata (correct column: file_id)
            conn.execute(
                "UPDATE files SET has_been_written_to_disk = 1, current_version = current_version + 1 WHERE file_id = ?",
                (proposal["target_file_id"],)
            )
            # Log write
            conn.execute(
                "INSERT INTO file_write_log (proposal_id, file_id, status) VALUES (?, ?, 'success')",
                (proposal_id, proposal["target_file_id"])
            )

            # Invalidate other proposals (core safety feature)
            # ✅ FIX: Use [] access or handle None
            affected_guids_json = proposal["affected_line_guids"]
            if affected_guids_json:
                affected = json.loads(affected_guids_json)
            else:
                affected = []
            
            invalidate_other_proposals(conn, proposal_id, affected)

            # Optional git commit (best effort)
            try:
                project_root = Path(target_path).parent
                subprocess.run(["git", "add", target_path], cwd=project_root, check=False, timeout=10)
                subprocess.run(
                    ["git", "commit", "-m", f"[PrizmForge] Agent edit via proposal {proposal_id[:8]}"],
                    cwd=project_root, check=False, timeout=10
                )
            except Exception:
                pass  # Git is optional
        else:
            # Disk write failed after successful apply — mark proposal terminal
            try:
                conn.execute(
                    "UPDATE edit_proposals SET status = 'error' WHERE proposal_id = ?",
                    (proposal_id,),
                )
                conn.execute(
                    "INSERT INTO file_write_log (proposal_id, file_id, status) VALUES (?, ?, 'error')",
                    (proposal_id, proposal["target_file_id"]),
                )
            except Exception:
                pass

        return result