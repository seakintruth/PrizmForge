"""
Developer mutation pipeline extracted from task_runner.

Flow (after files are known):
  mode select → load files → generate/validate with fallback →
  normalize payload → create proposal → reviewer → materialize

Primary entry: run_developer_mutation(...)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from agents.base import call_agent
from core.db_connection import get_db_connection
from core.db_helpers import post_message
from core.edit_response_validator import validate_developer_edit_response
from core.events import publish_event
from core.file_operations import format_file_with_guids, get_file_content_from_db
from core.index_context import load_symbol_json_context
from file_editing.undo import snapshot_before_apply
from file_editing.writer import materialize_proposal
from workflow.edit_mode_selector import DEFAULT_FALLBACK_ORDER, MODE_DIFF, MODE_FULL_REPLACE, MODE_GUID, next_fallback_mode, select_edit_mode
from workflow.proposal_builder import create_proposal_from_developer_output, update_proposal_status


# =========================================================================
# 🎯 PHASE 3: CLOSED-LOOP REVIEWER FEEDBACK EXTRACTION
# =========================================================================
def fetch_latest_reviewer_feedback(task_id: str, target_file: str) -> dict | None:
    """
    Fetches the most recent unaddressed Reviewer rejection reason and suggestions
    for a given task and target file.

    Schema (core/db.py agent_feedback):
      message, suggestion, timestamp — NOT feedback_text / created_at
    Schema (edit_proposals):
      proposal_id PK, task_id (when present)
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # agent_feedback: message + optional suggestion; order by timestamp then id
            cursor.execute(
                """
                SELECT id, message, suggestion
                FROM agent_feedback
                WHERE task_id = ?
                  AND file_path = ?
                  AND agent_name = 'reviewer'
                  AND addressed = 0
                ORDER BY COALESCE(timestamp, '') DESC, id DESC
                LIMIT 1
                """,
                (task_id, target_file),
            )

            fb_row = cursor.fetchone()
            if fb_row:
                msg = (fb_row[1] or "").strip()
                sug = (fb_row[2] or "").strip()
                reason = msg
                if sug:
                    reason = f"{msg}\nSuggestion: {sug}" if msg else sug
                return {"feedback_id": fb_row[0], "reason": reason or "Reviewer rejection (no detail)"}

            # Prefer rejected proposals for this task+file; fall back to file-only
            cursor.execute(
                """
                SELECT proposal_id, rationale
                FROM edit_proposals
                WHERE target_file_path = ?
                  AND status = 'rejected'
                  AND (task_id = ? OR task_id IS NULL)
                ORDER BY
                    CASE WHEN task_id = ? THEN 0 ELSE 1 END,
                    COALESCE(created_at, '') DESC
                LIMIT 1
                """,
                (target_file, task_id, task_id),
            )

            prop_row = cursor.fetchone()
            if prop_row:
                return {
                    "proposal_id": prop_row[0],
                    "reason": prop_row[1] or "Proposal rejected by Reviewer",
                }

    except Exception as e:
        print(f"   ⚠️ Could not fetch reviewer feedback: {e}")

    return None


def _build_generation_prompt(
    *,
    instructions: str,
    edit_method: str,
    files_content: list[str],
    requested_files: list[str],
    task_id: str,
    fallback_used: bool = False,
    previous_reason: str | None = None,
) -> str:
    """Build prompt for Developer LLM, injecting clean fallback warnings & Reviewer feedback."""
    joined = "\n\n".join(files_content) if files_content else "No existing files."

    index_snip = ""
    try:
        index_snip = load_symbol_json_context(
            file_paths=requested_files or None,
            max_rows=50,
            label="Symbols for target files",
        )
    except Exception as e:
        print(f"    ⚠️  Exception handled in developer_edit.py: {e}")

    parts = [
        instructions,
        index_snip,
        f"**Required edit mode: {edit_method}**",
        f"Target files to create/update: {', '.join(requested_files)}",
        "",
        "File content:",
        joined,
        "",
    ]

    # 🎯 PHASE 3 INJECTION: Check and inject Reviewer rejections into Developer prompt
    primary_target = requested_files[0] if requested_files else ""
    reviewer_feedback = fetch_latest_reviewer_feedback(task_id, primary_target)
    if reviewer_feedback:
        reviewer_banner = (
            "======================================================================\n"
            "⚠️ PREVIOUS ATTEMPT REJECTED BY REVIEWER — CORRECTION REQUIRED\n"
            "======================================================================\n"
            f"Reviewer Feedback / Rejection Reason:\n{reviewer_feedback['reason']}\n\n"
            "ACTION REQUIRED:\n"
            "- Modify your code specifically to address the Reviewer's criticism.\n"
            "- Do NOT repeat the exact same syntax, replacement characters, or edits.\n"
            "======================================================================\n\n"
        )
        parts.append(reviewer_banner)

    # 🎯 PHASE 2 INJECTION: Explicit clean re-prompting context on mode fallback
    if fallback_used or edit_method == MODE_FULL_REPLACE:
        fallback_banner = (
            "======================================================================\n"
            "⚠️ CRITICAL FALLBACK INSTRUCTION — FULL FILE REPLACE REQUIRED\n"
            "======================================================================\n"
            "You are operating in FULL_REPLACE mode (or falling back after a failed edit).\n\n"
            "REQUIREMENTS FOR 'new_content':\n"
            "1. You MUST supply the COMPLETE file content from Line 1 through the END.\n"
            "2. DO NOT provide partial line snippets, placeholders, or truncated code.\n"
            "3. Ensure all existing functions and imports are fully preserved.\n"
            "======================================================================\n"
        )
        if previous_reason:
            fallback_banner += f"Previous Failure Reason: {previous_reason}\n\n"
        parts.append(fallback_banner)

    parts.extend(
        [
            "CRITICAL INSTRUCTIONS FOR FILE CREATION & MODIFICATION:",
            '- To create a new file or completely write a file, use operation type "create_file" or "full_replace".',
            '- "create_file" format: {"type": "create_file", "target_file_path": "app.py", "initial_content": ["line1", "line2"], "rationale": "..."}',
            '- "full_replace" format: {"type": "full_replace", "target_file_path": "app.py", "new_content": "full source text", "rationale": "..."}',
            "- Respond ONLY with valid JSON matching the developer schema.",
        ]
    )

    return "\n".join(parts)


def _normalize_payload(data: dict, edit_method: str, requested_files: list[str]) -> dict:
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

    if not out.get("summary"):
        out["summary"] = out.get("rationale") or f"Edit {out.get('target_file_path', 'file')}"
    if not out.get("rationale"):
        out["rationale"] = out.get("summary") or "Developer edit mutation"
    return out


def run_developer_mutation(  # noqa: C901
    *,
    task_id: str,
    instructions: str,
    user_command: str,
    requested_files: list[str],
    conversation_context: list | None,
    model_choice: str | None,
    preferred_modes: list[str] | None,
    fallback_order: list[str] | None,
    small_file_threshold: int,
    progress: dict[str, Any],
    decision: dict[str, Any],
    current_turn: int,
) -> dict[str, Any]:
    """
    Execute mode selection through materialize for one developer turn.
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
    files_content: list[str] = []
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

    modes_tried: list[str] = []
    response = None
    validation = None
    fallback_used = False
    last_reason = None
    max_mode_attempts = len(mode_decision.fallback_chain) or 4

    # Keep a clean base context. We will deliberately not pass the full
    # conversation history on fallback attempts.
    base_context = conversation_context or []

    for _attempt in range(max_mode_attempts):
        modes_tried.append(edit_method)
        print(f"   🧪 Generating edit (mode={edit_method}, attempt={_attempt + 1})")

        # ------------------------------------------------------------------
        # FORCE CLEAN RE-QUERY WHEN MODE CHANGES
        # ------------------------------------------------------------------
        if fallback_used:
            clean_instructions = (
                f"**NEW ATTEMPT - PREVIOUS EDIT MODE FAILED**\n\n"
                f"Previous mode(s) tried: {', '.join(modes_tried[:-1])}\n"
                f"Failure reason: {last_reason or 'validation failed'}\n\n"
                f"You must now produce a valid edit using **only** the mode: `{edit_method}`.\n"
                f"Do not refer to any previous JSON you may have generated.\n"
                f"Start fresh.\n\n"
                f"Original task instructions:\n{instructions}"
            )
            current_context = []
        else:
            clean_instructions = instructions
            current_context = base_context

        gen_prompt = _build_generation_prompt(
            instructions=clean_instructions,
            edit_method=edit_method,
            files_content=files_content,
            requested_files=requested_files,
            task_id=task_id,
            fallback_used=fallback_used,
            previous_reason=last_reason,
        )

        progress["developer_calls"] = progress.get("developer_calls", 0) + 1
        response = call_agent(
            "developer",
            gen_prompt,
            task_id,
            current_context,
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
                last_reason = "Empty LLM response"
                continue
            break

        validation = validate_developer_edit_response(response)
        if validation.is_valid:
            print(f"   ✅ Valid edit payload ({validation.detected_mode})")
            break

        reason = getattr(validation.reason, "value", validation.reason) or "invalid"
        last_reason = str(reason)
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
        task_id=task_id,
    )
    if prop.get("status") != "success":
        progress["edit_failures"] = progress.get("edit_failures", 0) + 1
        print(f"   ❌ Proposal creation failed: {prop}")
        return {"status": "error", "message": "proposal failed", "detail": prop}

    proposal_id = prop["proposal_id"]
    print(f"   📦 Proposal created: {proposal_id}")

    # ---------------------------------------------------------------------------
    # Reviewer execution
    # ---------------------------------------------------------------------------
    progress["reviewer_calls"] = progress.get("reviewer_calls", 0) + 1

    original_content = get_file_content_from_db(target_file_path) or ""

    final_mode = data.get("_final_mode") or edit_method or validation.detected_mode or "unknown"

    reviewer_prompt = f"""You are the safety gate for a governed code-editing system.

    **File under review:** `{target_file_path}`
    **Final edit mode used:** `{final_mode}`
    **Fallback used:** {fallback_used}

    --------------------------------------------------
    ORIGINAL FILE CONTENT (before any change)
    --------------------------------------------------
    ```python
    {original_content}
    ```

    --------------------------------------------------
    PROPOSED EDIT PAYLOAD
    --------------------------------------------------
    {json.dumps(data, indent=2)[:6000]}

    --------------------------------------------------
    INSTRUCTIONS
    --------------------------------------------------
    Decide whether this change is safe and correct to apply.

    Respond with ONLY valid JSON in this exact shape:
    {{
    "decision": "APPROVE" | "REJECT",
    "reason": "concise explanation",
    "suggestions": ["optional", "list", "of", "improvements"]
    }}

    Rules:
    - REJECT if the change appears truncated, removes large amounts of existing code without clear justification, or introduces obvious errors.
    - REJECT if the payload does not match the declared edit mode.
    - APPROVE only when the change is coherent and the resulting file would still be valid.
    """

    reviewer_response = call_agent("reviewer", reviewer_prompt, task_id)

    decision_result = "REJECT"
    reason = "No response from reviewer; failing closed to REJECT"
    suggestions: list[str] = []
    if reviewer_response:
        try:
            decision_data = json.loads(reviewer_response)
            decision_result = str(decision_data.get("decision", "REJECT")).upper()
            reason = decision_data.get("reason", "")
            suggestions = decision_data.get("suggestions") or []
        except Exception:
            decision_result = "REJECT"
            reason = "reviewer response not JSON; failing closed to REJECT"

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

        try:
            with get_db_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO agent_feedback
                    (task_id, file_path, agent_name, message, suggestion,
                     priority, category, addressed, timestamp)
                    VALUES (?, ?, 'reviewer', ?, ?, 'HIGH', 'review_rejection', 0, ?)
                    """,
                    (
                        task_id,
                        target_file_path,
                        f"Proposal {proposal_id} REJECTED: {reason}",
                        "; ".join(suggestions) if suggestions else None,
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
        except Exception as e:
            print(f"   ⚠️ Failed to log reviewer rejection to feedback table: {e}")

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
