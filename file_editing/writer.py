# =============================================================================
# PrizmForge/file_editing/writer.py
# Version: 1.3 - Critical column name fixes + improved invalidation
# Purpose: FileWriterAgent - Materializes proposals to disk + git + invalidation
# =============================================================================

import os
import tempfile
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, List
import json

from .db import get_db_connection, log_error, reconstruct_file_content
from .editing import apply_edit_proposal


def write_file_to_disk(file_path: str, content: str, proposal_id: Optional[str] = None) -> Dict[str, Any]:
    """Atomic write using temp file + os.replace()."""
    try:
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.NamedTemporaryFile(mode='w', delete=False, dir=path.parent, suffix='.tmp', encoding='utf-8') as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        os.replace(tmp_path, str(path))
        return {"status": "success", "file_path": str(path)}
    except Exception as e:
        log_error("file_editing", "writer", "HIGH", str(e), proposal_id=proposal_id)
        return {"status": "error", "message": str(e)}


def invalidate_other_proposals(conn, current_proposal_id: str, affected_guids: List[str]):
    """After successful write, mark overlapping pending proposals as needs_revalidation."""
    if not affected_guids:
        return
    try:
        # Use a simple but effective approach: mark any proposal that shares at least one affected line_guid
        for guid in affected_guids:
            conn.execute("""
                UPDATE edit_proposals 
                SET status = 'needs_revalidation'
                WHERE proposal_id != ? 
                  AND status IN ('pending', 'under_review', 'approved')
                  AND affected_line_guids LIKE '%' || ? || '%'
            """, (current_proposal_id, guid))

        print(f"🔄 Invalidated overlapping proposals after {current_proposal_id}")
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
                return apply_result

        # Get file path (note: schema uses file_path, not path)
        file_row = conn.execute(
            "SELECT file_path FROM files WHERE file_id = ?", (proposal["target_file_id"],)
        ).fetchone()
        target_path = file_row["file_path"] if file_row else proposal.get("target_file_path", "")

        content = reconstruct_file_content(conn, proposal["target_file_id"])
        result = write_file_to_disk(target_path, content, proposal_id)

        if result.get("status") == "success":
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
            affected = json.loads(proposal.get("affected_line_guids") or "[]")
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

        return result
