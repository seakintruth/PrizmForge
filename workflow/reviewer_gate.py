"""Shared reviewer-gate logic (Workstream A / PR-83 residual P1).

Both developer paths - the legacy structured ``edit_payload`` agent
(workflow/developer_edit.py) and the shell developer
(workflow/shell_developer.py) - must judge proposals with identical
fail-closed semantics: any empty, unparseable, or unknown verdict REJECTs the
proposal. Gate authority must not depend on endpoint health.

This module owns only the verdict decision and the rejection bookkeeping.
Prompt construction stays with each caller because the evidence differs
(session diff vs. edit payload).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from core.db_connection import get_db_connection
from core.db_helpers import post_message
from core.events import publish_event
from core.json_parser import parse_json_response
from workflow.proposal_builder import update_proposal_status

_DEFAULT_REJECT_EMPTY = "Reviewer unavailable (empty response) - failing closed"
_DEFAULT_REJECT_PARSE = "Reviewer response could not be parsed - failing closed"
_DEFAULT_REJECT_DECISION = "Reviewer response missing a valid decision - failing closed"


@dataclass
class ReviewerVerdict:
    """Normalized result of a reviewer verdict, always APPROVE or REJECT."""

    decision: str
    reason: str
    suggestions: list[Any] = field(default_factory=list)
    infra_reject: bool = False
    calls_used: int = 1

    @property
    def rejected(self) -> bool:
        return self.decision == "REJECT"


def parse_reviewer_verdict(reviewer_response: Any) -> ReviewerVerdict:
    """Fail-closed review of an LLM verdict.

    APPROVE is returned only for an explicit, case-insensitive ``APPROVE``
    embedded in a parseable decision object. Everything else - empty output,
    non-JSON, markdown-fenced garbage, or an unknown/missing ``decision`` value
    - REJECTs. The strict key validation makes a missing ``decision`` resolve
    to REJECT, never to the historical APPROVE default.

    ``infra_reject`` is True when no valid decision was extracted at all
    (empty/unparseable/unknown verdict) - the transient-failure class that a
    single same-prompt retry may recover from. A semantic ``REJECT`` (the
    reviewer parsed real JSON and said no) is never retried.
    """
    response = str(reviewer_response or "").strip()
    if not response:
        return ReviewerVerdict(decision="REJECT", reason=_DEFAULT_REJECT_EMPTY, infra_reject=True)

    data = parse_json_response(
        response,
        expected_keys=["decision"],
        strict=True,
        agent_name="reviewer",
    )
    if not data:
        return ReviewerVerdict(decision="REJECT", reason=_DEFAULT_REJECT_PARSE, infra_reject=True)

    decision = str(data.get("decision", "")).upper()
    if decision not in ("APPROVE", "REJECT"):
        return ReviewerVerdict(
            decision="REJECT",
            reason=f"Reviewer returned an unknown verdict {decision!r} - failing closed",
            infra_reject=True,
        )

    # `suggestions` may arrive as a single newline/comma-separated string
    # rather than a list (residual P10); split so the string form does not
    # produce one giant str() blob in post_reviewer_suggestions.
    raw_suggestions = data.get("suggestions")
    if isinstance(raw_suggestions, str) and raw_suggestions.strip():
        suggestions = [line.strip() for line in raw_suggestions.replace("\r", "").split("\n") if line.strip()]
        if len(suggestions) == 1 and "," in suggestions[0]:
            suggestions = [part.strip() for part in suggestions[0].split(",") if part.strip()]
    else:
        suggestions = list(raw_suggestions or [])

    return ReviewerVerdict(
        decision=decision,
        reason=str(data.get("reason") or ""),
        suggestions=suggestions,
    )


def request_review_verdict(
    reviewer_prompt: str,
    task_id: str,
    *,
    max_attempts: int = 2,
) -> ReviewerVerdict:
    """Invoke the gate reviewer with ONE same-prompt retry on transient failures.

    Fail-closed must not double as "drop valid work on one blank response":
    soak evidence (2026-08-28) shows a correct SQL-injection fix rejected on an
    empty reviewer stream and then shelved. Retry policy:

    - Retry only when the first attempt is an *infra* reject (empty /
      unparseable / unknown verdict - no valid decision extracted).
    - Never retry a semantic ``REJECT``.
    - Never retry a ``None`` transport failure - that storm is the §8.4
      busy-loop guard's domain, and PR #93 forbids stricter-prompt escalation.
    - Cap at ``max_attempts`` total calls (2 by default), same prompt each time.
    """
    from agents.base import call_agent

    response = call_agent("reviewer", reviewer_prompt, task_id)
    verdict = parse_reviewer_verdict(response)
    if verdict.rejected and verdict.infra_reject and response is not None and max_attempts > 1:
        print("   🔁 Reviewer returned a transient (empty/unparseable) verdict — retrying once")
        response = call_agent("reviewer", reviewer_prompt, task_id)
        verdict = parse_reviewer_verdict(response)
        verdict.calls_used = 2  # residual P10: count plays as reviewer_calls
    return verdict


def post_reviewer_suggestions(proposal_id: str, task_id: str, suggestions: list[Any]) -> None:
    """Surface reviewer suggestions to the prioritizer at MEDIUM priority."""
    if not suggestions:
        return
    suggestion_text = "\n".join([f"- {s}" for s in suggestions])
    post_message(
        "reviewer",
        "prioritizer",
        f"Suggestions from Reviewer for Proposal {proposal_id}:\n{suggestion_text}",
        task_id,
        "MEDIUM",
    )


def log_reviewer_rejection(
    task_id: str,
    target_file_path: str,
    proposal_id: str,
    reason: str,
    suggestions: list[Any],
) -> None:
    """Write the rejection to agent_feedback so the loop sees it next turn."""
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
                    "; ".join(str(s) for s in suggestions) if suggestions else None,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
    except Exception as e:  # feedback logging must never break the gate
        print(f"   ⚠️ Failed to log reviewer rejection to feedback table: {e}")


def handle_reviewer_rejection(
    *,
    proposal_id: str,
    target_file_path: str,
    task_id: str,
    reason: str,
    suggestions: list[Any],
) -> None:
    """Shared bookkeeping for a REJECT verdict.

    Marks the proposal rejected, records feedback, publishes the
    ``proposal.rejected`` event, and notifies the orchestrator so the next
    developer turn can address the rejection (the previous-attempt injection).
    """
    update_proposal_status(proposal_id, "rejected")
    log_reviewer_rejection(task_id, target_file_path, proposal_id, reason, suggestions)
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
