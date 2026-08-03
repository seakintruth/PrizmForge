from typing import Dict, List, Optional

"""
Developer mutation pipeline extracted from task_runner.

Flow (after files are known):
  mode select → load files → generate/validate with fallback →
  normalize payload → create proposal → reviewer → materialize

Primary entry: run_developer_mutation(...)
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from agents.base import call_agent
from core.db_connection import get_db_connection
from core.db_helpers import post_message
from core.edit_response_validator import validate_developer_edit_response
from core.events import publish_event
from core.file_operations import format_file_with_guids, get_file_content_from_db
from file_editing.undo import snapshot_before_apply
from file_editing.writer import materialize_proposal
from workflow.edit_mode_selector import (
    DEFAULT_FALLBACK_ORDER,
    MODE_DIFF,
    MODE_FULL_REPLACE,
    MODE_GUID,
    next_fallback_mode,
    select_edit_mode,
)
from workflow.proposal_builder import create_proposal_from_developer_output, update_proposal_status


def run_developer_mutation(
    *,
    task_id: str,
    instructions: str,
    user_command: str,
    requested_files: List[str],
    conversation_context: Optional[list],
    model_choice: Optional[str],
    preferred_modes: Optional[List[str]],
    fallback_order: Optional[List[str]],
    small_file_threshold: int,
    progress: Dict[str, Any],
    decision: Dict[str, Any],
    current_turn: int,
) -> Dict[str, Any]:
    """
    Execute mode selection through materialize for one developer turn.

    Returns a result dict: {status, proposal_id?, edit_method?, fallback_used?}
    Updates progress counters in-place.
    """
    if not requested_files:
        print("   ❌ No files for developer mutation")
        progress["edit_failures"] = progress.get("edit_failures", 0) + 1
        return {"status": "error", "message": "no files"}

    primary_file = requested_files[0]
    primary_content = get_file_content_from_db(primary_file) or ""
    primary_lines = primary_content.count("\n") + (1 if primary_content else 0)

    mode_decision = select_edit_mode(
        file_line_count=primary_lines,
        instructions=instructions or user_command,
        files_needed=requested_files,
        preferred_modes=preferred_modes,
        fallback_order=fallback_order or list(DEFAULT_FALLBACK_ORDER),
        small_file_threshold_lines=small_file_threshold,
    )
    edit_method = mode_decision.selected_mode
    original_selected_mode = edit_method
    print(f"   🎯 Selected edit mode: {edit_method} ({mode_decision.reason})")

    print("   📝 Phase 2: Loading files...")
    files_content: List[str] = []
    for fpath in requested_files:
        try:
            if edit_method == MODE_GUID:
                file_formatted = format_file_with_guids(fpath)
            else:
                content = get_file_content_from_db(fpath)
                file_formatted = f"```python {fpath}\n{content}\n```"
            files_content.append(file_formatted)
            print(f"      • {fpath} ({file_formatted.count(chr(10))} lines)")
        except Exception as e:
            print(f"      ⚠️  Failed to load {fpath}: {e}")

    if not files_content:
        print("   ❌ No files loaded successfully")
        progress["edit_failures"] = progress.get("edit_failures", 0) + 1
        return {"status": "error", "message": "no file content"}

    modes_tried: List[str] = []
    response = None
    validation = None
    fallback_used = False
    max_mode_attempts = len(mode_decision.fallback_chain) or 4

    for _attempt in range(max_mode_attempts):
        modes_tried.append(edit_method)
        print(f"   🧪 Generating edit (mode={edit_method}, attempt={_attempt + 1})")

        gen_prompt = _build_generation_prompt(
            instructions=instructions,
            edit_method=edit_method,
            files_content=files_content,
            requested_files=requested_files,
        )
        progress["developer_calls"] = progress.get("developer_calls", 0) + 1
        response = call_agent(
            "developer",
            gen_prompt,
            task_id,
            conversation_context,
            model_choice,
        )
        if not response:
            next_mode = next_fallback_mode(
                edit_method,
                fallback_chain=mode_decision.fallback_chain,
                already_tried=modes_tried,
            )
            if next_mode:
                print(f"   ↪️  Empty response; falling back {edit_method} → {next_mode}")
                edit_method = next_mode
                fallback_used = True
                continue
            break

        validation = validate_developer_edit_response(response)
        if validation.is_valid:
            print(f"   ✅ Valid edit payload ({validation.detected_mode})")
            break

        reason = getattr(validation.reason, "value", validation.reason) or "invalid"
        print(f"   ⚠️  Invalid developer JSON ({reason})")
        next_mode = next_fallback_mode(
            edit_method,
            fallback_chain=mode_decision.fallback_chain,
            already_tried=modes_tried,
        )
        if next_mode:
            post_message(
                "developer",
                "orchestrator",
                f"Edit failure ({reason}); trying fallback {edit_method} → {next_mode}",
                task_id,
                "HIGH",
            )
            edit_method = next_mode
            fallback_used = True
            continue
        post_message(
            "developer",
            "orchestrator",
            f"Edit failure ({reason}); fallback chain exhausted (tried: {modes_tried}). Preview: {(response or '')[:180]}...",
            task_id,
            "HIGH",
        )
        break

    if not validation or not validation.is_valid:
        progress["edit_failures"] = progress.get("edit_failures", 0) + 1
        return {"status": "error", "message": "no valid edit payload"}

    progress["valid_edit_payloads"] = progress.get("valid_edit_payloads", 0) + 1
    if fallback_used:
        progress["fallback_successes"] = progress.get("fallback_successes", 0) + 1
        publish_event(
            "edit.fallback_used",
            source="developer_edit",
            task_id=task_id,
            payload={"modes_tried": modes_tried, "final_mode": edit_method},
        )

    data = validation.data or {}
    data = _normalize_payload(data, edit_method, requested_files)
    edit_method = data.get("_final_mode", edit_method)
    target_file_path = data.get("target_file_path") or requested_files[0]

    prop = create_proposal_from_developer_output(
        data,
        proposed_by_agent_id=1,
        target_file_path=target_file_path,
        selected_mode=original_selected_mode,
        fallback_used=fallback_used,
        final_mode=validation.detected_mode or edit_method,
    )
    if prop.get("status") != "success":
        progress["edit_failures"] = progress.get("edit_failures", 0) + 1
        print(f"   ❌ Proposal creation failed: {prop}")
        return {"status": "error", "message": "proposal failed", "detail": prop}

    proposal_id = prop["proposal_id"]
    print(f"   📦 Proposal created: {proposal_id}")

    # Reviewer
    progress["reviewer_calls"] = progress.get("reviewer_calls", 0) + 1
    reviewer_prompt = (
        f"Review this edit proposal for {target_file_path}.\n"
        f"Payload:\n{json.dumps(data, indent=2)[:4000]}\n\n"
        'Respond with JSON: {"decision":"APPROVE"|"REJECT","reason":"...","suggestions":[]}'
    )
    reviewer_response = call_agent("reviewer", reviewer_prompt, task_id)
    decision_result = "APPROVE"
    reason = ""
    suggestions: List[str] = []
    if reviewer_response:
        try:
            decision_data = json.loads(reviewer_response)
            decision_result = str(decision_data.get("decision", "APPROVE")).upper()
            reason = decision_data.get("reason", "")
            suggestions = decision_data.get("suggestions") or []
        except Exception:
            # Non-JSON reviewer: default approve with note
            decision_result = "APPROVE"
            reason = "reviewer response not JSON; defaulting to APPROVE"

    if suggestions:
        suggestion_text = "\n".join([f"- {s}" for s in suggestions])
        post_message(
            "reviewer",
            "prioritizer",
            f"Suggestions from Reviewer for Proposal {proposal_id}:\n{suggestion_text}",
            task_id,
            "MEDIUM",
        )

    if decision_result == "REJECT":
        print(f"   ❌ Reviewer rejected proposal: {reason}")
        update_proposal_status(proposal_id, "rejected")
        publish_event(
            "proposal.rejected",
            source="reviewer",
            task_id=task_id,
            proposal_id=proposal_id,
            payload={"reason": reason},
        )
        post_message(
            "reviewer",
            "orchestrator",
            f"Proposal {proposal_id} REJECTED.\nReason: {reason}",
            task_id,
            "HIGH",
        )
        return {
            "status": "rejected",
            "proposal_id": proposal_id,
            "edit_method": edit_method,
            "fallback_used": fallback_used,
        }

    print(f"   ✅ Reviewer approved proposal {proposal_id}")
    update_proposal_status(proposal_id, "approved")
    publish_event("proposal.approved", source="reviewer", task_id=task_id, proposal_id=proposal_id)
    print("   📝 Materializing changes to disk...")
    snapshot_before_apply(proposal_id)
    mat = materialize_proposal(proposal_id)
    if mat.get("status") == "success":
        publish_event(
            "edit.materialized",
            source="writer",
            task_id=task_id,
            proposal_id=proposal_id,
            payload=mat if isinstance(mat, dict) else {},
        )
        progress["files_modified"] = progress.get("files_modified", 0) + 1
        progress["materialize_successes"] = progress.get("materialize_successes", 0) + 1
        progress["last_file_change"] = current_turn
    else:
        publish_event(
            "edit.failed",
            source="writer",
            task_id=task_id,
            proposal_id=proposal_id,
            payload=mat if isinstance(mat, dict) else {},
        )
        progress["edit_failures"] = progress.get("edit_failures", 0) + 1
        print(f"   ⚠️  Materialize status: {mat}")

    addressing_ids = decision.get("addressing_feedback_ids") or []
    if addressing_ids and mat.get("status") == "success":
        from datetime import datetime, timezone

        with get_db_connection() as conn:
            for fb_id in addressing_ids:
                conn.execute(
                    """
                    UPDATE agent_feedback
                    SET addressed = 1, addressed_by = 'developer', addressed_at = ?
                    WHERE id = ?
                    """,
                    (datetime.now(timezone.utc).isoformat(), fb_id),
                )

    return {
        "status": mat.get("status", "error"),
        "proposal_id": proposal_id,
        "edit_method": edit_method,
        "fallback_used": fallback_used,
        "materialize": mat,
    }


def _build_generation_prompt(
    *,
    instructions: str,
    edit_method: str,
    files_content: List[str],
    requested_files: List[str],
) -> str:
    joined = "\n\n".join(files_content)
    index_snip = ""
    try:
        from core.index_context import load_index_text, load_symbol_json_context

        index_snip = load_symbol_json_context(
            file_paths=requested_files or None,
            max_rows=50,
            label="Symbols for target files",
        )
        if not index_snip.strip():
            raw_idx = load_index_text(which="production", max_chars=6_000)
            if raw_idx.strip():
                index_snip = "\n**Structural index (Markdown fallback):**\n" + raw_idx + "\n"
        elif index_snip and not index_snip.startswith("\n"):
            index_snip = "\n" + index_snip
    except Exception:
        pass
    parts = [
        instructions,
        index_snip,
        f"**Required edit mode: {edit_method}**",
        f"Target files: {', '.join(requested_files)}",
        "",
        "File content:",
        joined,
        "",
        "Output ONLY valid JSON for the edit payload (see developer schema). Prefer the requested mode.",
    ]
    return "\n".join(parts)


def _normalize_payload(data: dict, edit_method: str, requested_files: List[str]) -> dict:
    """Normalize top-level full_replace / diff shapes into operations form."""
    out = dict(data)
    if not out.get("target_file_path") and requested_files:
        out["target_file_path"] = requested_files[0]

    if "operations" not in out:
        if "new_content" in out:
            out["operations"] = [
                {
                    "type": "full_replace",
                    "new_content": out.get("new_content"),
                    "rationale": out.get("rationale") or out.get("summary") or "full replace",
                }
            ]
            out["_final_mode"] = MODE_FULL_REPLACE
        elif "diff" in out:
            out["operations"] = [
                {
                    "type": "apply_diff",
                    "diff": out.get("diff"),
                    "rationale": out.get("rationale") or out.get("summary") or "apply diff",
                }
            ]
            out["_final_mode"] = MODE_DIFF
        elif out.get("find") is not None:
            out["operations"] = [
                {
                    "type": "find_replace",
                    "find": out.get("find"),
                    "replace": out.get("replace", ""),
                    "rationale": out.get("rationale") or "find replace",
                }
            ]
    # Ensure summary/rationale meet minimums when possible
    if not out.get("summary"):
        out["summary"] = out.get("rationale") or f"Edit {out.get('target_file_path', 'file')}"
    if not out.get("rationale"):
        out["rationale"] = out.get("summary") or "Developer edit mutation"
    return out
