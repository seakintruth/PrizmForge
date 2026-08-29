"""Fail-closed reviewer gate regression tests (PR-83 residual P1 + gate consolidation).

The legacy edit_payload developer (workflow/developer_edit.py) used to default
APPROVE on empty / unparseable / decision-less reviewer output. Both developer
paths now share `workflow/reviewer_gate.py`, which REJECTs anything that is not
an explicit, parseable APPROVE. These tests lock that behavior and the
acceptance criteria from UNATTENDED_CLOSED_LOOP_PLAN.md §5.2/§5.3.
"""

from __future__ import annotations

import json

import pytest

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_proposal(ops, *, target="pkg/app.py"):
    """Create a governed proposal in the temp DB and return its id."""
    from workflow.proposal_builder import create_proposal_from_developer_output

    prop = create_proposal_from_developer_output(
        {
            "target_file_path": target,
            "summary": "governed edit",
            "rationale": "test proposal",
            "operations": ops,
        },
        1,
        target,
    )
    assert prop["status"] == "success", prop
    return prop["proposal_id"]


def _feedback_rows_for(proposal_id):
    from file_editing.db import get_db_connection

    with get_db_connection() as conn:
        return conn.execute(
            "SELECT agent_name, priority, category, message, suggestion, addressed FROM agent_feedback WHERE message LIKE ? ORDER BY id",
            (f"Proposal {proposal_id} REJECTED%",),
        ).fetchall()


# ---------------------------------------------------------------------------
# parse_reviewer_verdict: pure fail-closed verdict parsing
# ---------------------------------------------------------------------------


class TestParseReviewerVerdict:
    @pytest.mark.parametrize("raw", [None, "", "   ", "\n"])
    def test_empty_response_rejects(self, raw):
        from workflow.reviewer_gate import parse_reviewer_verdict

        verdict = parse_reviewer_verdict(raw)
        assert verdict.decision == "REJECT"

    def test_valid_approve(self):
        from workflow.reviewer_gate import parse_reviewer_verdict

        verdict = parse_reviewer_verdict('{"decision": "APPROVE", "reason": "looks safe", "suggestions": ["add a test"]}')
        assert verdict.decision == "APPROVE"
        assert verdict.reason == "looks safe"
        assert verdict.suggestions == ["add a test"]
        assert not verdict.rejected

    def test_lowercase_approve_normalizes(self):
        from workflow.reviewer_gate import parse_reviewer_verdict

        verdict = parse_reviewer_verdict('{"decision": "approve"}')
        assert verdict.decision == "APPROVE"

    def test_markdown_fenced_approve_parses(self):
        from workflow.reviewer_gate import parse_reviewer_verdict

        verdict = parse_reviewer_verdict('```json\n{"decision": "APPROVE", "reason": "ok"}\n```')
        assert verdict.decision == "APPROVE"

    def test_prose_response_rejects(self):
        from workflow.reviewer_gate import parse_reviewer_verdict

        verdict = parse_reviewer_verdict("This change looks great, ship it!")
        assert verdict.decision == "REJECT"

    def test_prose_with_brace_mention_still_rejects(self):
        from workflow.reviewer_gate import parse_reviewer_verdict

        verdict = parse_reviewer_verdict("Approving now {but this is not json}")
        assert verdict.decision == "REJECT"

    def test_missing_decision_key_rejects(self):
        from workflow.reviewer_gate import parse_reviewer_verdict

        # Historical fail-open case: a valid JSON object without "decision"
        # used to default to APPROVE.
        verdict = parse_reviewer_verdict('{"reason": "no decision here"}')
        assert verdict.decision == "REJECT"

    def test_unknown_decision_value_rejects(self):
        from workflow.reviewer_gate import parse_reviewer_verdict

        verdict = parse_reviewer_verdict('{"decision": "MAYBE"}')
        assert verdict.decision == "REJECT"

    def test_explicit_reject_works(self):
        from workflow.reviewer_gate import parse_reviewer_verdict

        verdict = parse_reviewer_verdict('{"decision": "REJECT", "reason": "truncated", "suggestions": ["rewrite"]}')
        assert verdict.decision == "REJECT"
        assert verdict.suggestions == ["rewrite"]
        assert verdict.rejected

    def test_defaults_for_blank_fields(self):
        from workflow.reviewer_gate import parse_reviewer_verdict

        verdict = parse_reviewer_verdict('{"decision": "APPROVE"}')
        assert verdict.reason == ""
        assert verdict.suggestions == []

    def test_string_suggestions_split_into_list(self):
        # Residual P10: reviewers sometimes return suggestions as a single
        # newline/comma-separated string instead of a list.
        from workflow.reviewer_gate import parse_reviewer_verdict

        verdict = parse_reviewer_verdict('{"decision": "APPROVE", "reason": "ok", "suggestions": "add a test\\nrename flag\\n"}')
        assert verdict.suggestions == ["add a test", "rename flag"]

        comma = parse_reviewer_verdict('{"decision": "APPROVE", "reason": "ok", "suggestions": "add a test, rename flag"}')
        assert comma.suggestions == ["add a test", "rename flag"]


# ---------------------------------------------------------------------------
# handle_reviewer_rejection: shared bookkeeping (status + feedback + event)
# ---------------------------------------------------------------------------


class TestHandleReviewerRejection:
    def test_records_rejection(self, temp_db):
        from file_editing.db import get_db_connection
        from workflow.reviewer_gate import handle_reviewer_rejection

        pid = _make_proposal([{"type": "create_file", "target_file_path": "pkg/app.py", "initial_content": ["x = 1"]}])

        handle_reviewer_rejection(
            proposal_id=pid,
            target_file_path="pkg/app.py",
            task_id="T-reject",
            reason="truncated replacement",
            suggestions=["restore imports"],
        )

        with get_db_connection() as conn:
            status = conn.execute("SELECT status FROM edit_proposals WHERE proposal_id = ?", (pid,)).fetchone()
            assert status is not None and status[0] == "rejected"

            fb = _feedback_rows_for(pid)
            assert len(fb) == 1
            assert fb[0]["agent_name"] == "reviewer"
            assert fb[0]["priority"] == "HIGH"
            assert fb[0]["category"] == "review_rejection"
            assert "truncated replacement" in fb[0]["message"]
            assert "restore imports" in fb[0]["suggestion"]
            assert int(fb[0]["addressed"]) == 0

            ev = conn.execute(
                "SELECT type, proposal_id, payload_json FROM events WHERE type = 'proposal.rejected' AND proposal_id = ?",
                (pid,),
            ).fetchall()
            assert len(ev) == 1
            assert "truncated replacement" in ev[0]["payload_json"]


# ---------------------------------------------------------------------------
# Legacy developer path: run_developer_mutation must now fail closed
# ---------------------------------------------------------------------------


class TestLegacyDeveloperFailClosed:
    def _seed_file(self, body="value = OLD\n"):
        """Write a governed file under the test project dir so materialize can land."""
        from core.config import get_config
        from file_editing.writer import initialize_file_lines

        project_dir = __import__("pathlib").Path(get_config()["project_directory"])
        (project_dir / "app.py").write_text(body)
        initialize_file_lines("app.py", body)
        return body.replace("OLD", "NEW")

    def test_non_json_reviewer_response_rejects(self, temp_db, mock_llm):
        from file_editing.db import get_db_connection
        from workflow.developer_edit import run_developer_mutation

        new_body = self._seed_file()
        mock_llm.set_response(
            "developer",
            json.dumps(
                {
                    "target_file_path": "app.py",
                    "new_content": new_body,
                    "summary": "bump constant",
                    "rationale": "whole-file replace",
                }
            ),
        )
        mock_llm.set_response("reviewer", "This looks fine, approved.")

        progress: dict = {}
        with mock_llm.patch_call_agent():
            result = run_developer_mutation(
                task_id="T-failclosed",
                instructions="bump constant",
                user_command="bump",
                requested_files=["app.py"],
                conversation_context=[],
                model_choice=None,
                preferred_modes=["find_replace"],
                fallback_order=["find_replace"],
                small_file_threshold=180,
                progress=progress,
                decision={},
                current_turn=1,
            )

        assert result["status"] == "rejected", result
        assert progress.get("files_modified", 0) == 0
        assert progress.get("materialize_successes", 0) == 0

        with get_db_connection() as conn:
            status = conn.execute("SELECT status FROM edit_proposals WHERE proposal_id = ?", (result["proposal_id"],)).fetchone()
            assert status[0] == "rejected"
            fb = _feedback_rows_for(result["proposal_id"])
            assert len(fb) == 1 and fb[0]["category"] == "review_rejection"
            assert not conn.execute("SELECT 1 FROM events WHERE type = 'edit.materialized'").fetchone()

    def test_fenced_approve_still_materializes(self, temp_db, mock_llm):
        from workflow.developer_edit import run_developer_mutation

        new_body = self._seed_file()
        mock_llm.set_response(
            "developer",
            json.dumps(
                {
                    "target_file_path": "app.py",
                    "new_content": new_body,
                    "summary": "bump constant",
                    "rationale": "whole-file replace",
                }
            ),
        )
        mock_llm.set_response("reviewer", '```json\n{"decision": "APPROVE", "reason": "ok"}\n```')

        progress: dict = {}
        with mock_llm.patch_call_agent():
            result = run_developer_mutation(
                task_id="T-fenced",
                instructions="bump",
                user_command="bump",
                requested_files=["app.py"],
                conversation_context=[],
                model_choice=None,
                preferred_modes=["find_replace"],
                fallback_order=["find_replace"],
                small_file_threshold=180,
                progress=progress,
                decision={},
                current_turn=1,
            )

        # git is disabled in tests, so an approved proposal materializes.
        assert result["status"] == "success", result
        assert progress.get("files_modified", 0) == 1


# ---------------------------------------------------------------------------
# Shell developer path: gate consolidation must not regress fail-closed
# ---------------------------------------------------------------------------


class TestShellGateFailClosed:
    def test_non_json_reviewer_response_rejects(self, temp_db, monkeypatch):
        from file_editing.db import get_db_connection
        from workflow.shell_developer import SessionResult, _gate_and_materialize

        pid = _make_proposal([{"type": "create_file", "target_file_path": "pkg/app.py", "initial_content": ["x = 1"]}])
        monkeypatch.setattr(
            "agents.base.call_agent",
            lambda agent_name, prompt, task_id, *a, **k: "definitely approve this one",
        )

        progress = {"edit_failures": 0}
        status = _gate_and_materialize(
            proposal_id=pid,
            payload_dict={},
            target_file_path="pkg/app.py",
            diff_text="",
            result=SessionResult(),
            fallback_used=False,
            task_id="T-shell-fc",
            progress=progress,
            current_turn=1,
        )

        assert status == "rejected"
        assert progress.get("files_modified", 0) == 0
        with get_db_connection() as conn:
            status_row = conn.execute("SELECT status FROM edit_proposals WHERE proposal_id = ?", (pid,)).fetchone()
            assert status_row[0] == "rejected"
            assert len(_feedback_rows_for(pid)) == 1


# ---------------------------------------------------------------------------
# Gate helper: single same-prompt retry on infra rejects (soak fix)
# ---------------------------------------------------------------------------


class TestRequestReviewRetry:
    """request_review_verdict: one retry for infra rejects, never for transport/semantic."""

    def _run(self, monkeypatch, responses):
        from workflow.reviewer_gate import request_review_verdict

        calls: list[tuple] = []

        def fake_call_agent(agent_name, prompt, task_id, *a, **k):
            calls.append((agent_name, prompt, task_id))
            return responses.pop(0) if responses else None

        monkeypatch.setattr("agents.base.call_agent", fake_call_agent)
        verdict = request_review_verdict("review the diff", "t_retry")
        return verdict, calls

    def test_approve_first_is_single_call(self, monkeypatch):
        verdict, calls = self._run(monkeypatch, ['{"decision": "APPROVE", "reason": "ok"}'])
        assert verdict.decision == "APPROVE"
        assert not verdict.rejected
        assert len(calls) == 1

    def test_semantic_reject_is_never_retried(self, monkeypatch):
        verdict, calls = self._run(monkeypatch, ['{"decision": "REJECT", "reason": "unsafe"}'])
        assert verdict.decision == "REJECT"
        assert not verdict.infra_reject
        assert len(calls) == 1

    def test_transport_none_is_never_retried(self, monkeypatch):
        verdict, calls = self._run(monkeypatch, [None])
        assert verdict.decision == "REJECT"
        assert verdict.infra_reject
        assert len(calls) == 1

    def test_empty_then_valid_approve_retries_once(self, monkeypatch):
        verdict, calls = self._run(monkeypatch, ["", '{"decision": "APPROVE", "reason": "recovered"}'])
        assert verdict.decision == "APPROVE"
        assert len(calls) == 2

    def test_empty_persists_capped_at_two_attempts(self, monkeypatch):
        verdict, calls = self._run(monkeypatch, ["", ""])
        assert verdict.decision == "REJECT"
        assert verdict.infra_reject
        assert len(calls) == 2

    def test_garbage_then_garbage_rejects_real_json_of_intent(self, monkeypatch):
        verdict, calls = self._run(monkeypatch, ["all good here", "yep looks fine"])
        assert verdict.decision == "REJECT"
        assert verdict.infra_reject
        assert len(calls) == 2

    def test_unknown_decision_retries_then_rejects_on_again(self, monkeypatch):
        verdict, calls = self._run(
            monkeypatch,
            ['{"decision": "MAYBE"}', '{"decision": "MAYBE"}'],
        )
        assert verdict.decision == "REJECT"
        assert len(calls) == 2

    def test_calls_used_reflects_actual_plays(self, monkeypatch):
        # Residual P10: the gate counts the retry as a reviewer call; callers
        # sum verdict.calls_used into progress["reviewer_calls"].
        single, calls = self._run(monkeypatch, ['{"decision": "APPROVE", "reason": "ok"}'])
        assert len(calls) == 1 and single.calls_used == 1

        retried, calls = self._run(monkeypatch, ["", '{"decision": "APPROVE", "reason": "recovered"}'])
        assert len(calls) == 2 and retried.calls_used == 2
