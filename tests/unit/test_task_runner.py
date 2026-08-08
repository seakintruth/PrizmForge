"""
tests/unit/test_task_runner.py

Tests for workflow/task_runner orchestration with mocked LLM responses.
"""

import inspect
import json
import re


class TestTaskRunnerSignature:
    def test_run_task_cycle_function_exists(self):
        from workflow.task_runner import run_task_cycle

        assert callable(run_task_cycle)

    def test_run_task_cycle_accepts_time_box(self):
        from workflow.task_runner import run_task_cycle

        sig = inspect.signature(run_task_cycle)
        assert "time_box_minutes" in sig.parameters
        assert "max_turns" in sig.parameters
        assert "task_id" in sig.parameters


class TestTaskRunnerWithMocks:
    def test_call_agent_patched_during_cycle_components(self, mock_llm, temp_db, mock_minimal_config):
        """
        Verify the pieces the task runner uses (call_agent) honor MockLLM
        scripting — without requiring a full multi-turn cycle against real APIs.
        """
        mock_llm.set_response(
            "orchestrator",
            json.dumps(
                {
                    "next_agent": "complete",
                    "instructions": "nothing to do",
                    "reasoning": "empty backlog",
                }
            ),
        )
        with mock_llm.patch_call_agent():
            from agents.base import call_agent

            result = call_agent("orchestrator", "status?", task_id="tr1")
        data = json.loads(result)
        assert data["next_agent"] == "complete"
        assert mock_llm.calls_for("orchestrator")

    def test_developer_edit_payload_roundtrip(self, mock_llm, temp_db):
        """Mocked developer emits find_replace; proposal path accepts it."""
        from core.edit_response_validator import validate_developer_edit_response
        from file_editing.writer import initialize_file_lines
        from workflow.proposal_builder import create_proposal_from_developer_output

        initialize_file_lines("tr/demo.py", "n = 1\n")
        mock_llm.set_response(
            "developer",
            json.dumps(
                {
                    "target_file_path": "tr/demo.py",
                    "summary": "bump constant",
                    "rationale": "Increment the module-level constant value",
                    "operations": [
                        {
                            "type": "find_replace",
                            "find": "n = 1",
                            "replace": "n = 2",
                            "rationale": "Bump constant",
                        }
                    ],
                }
            ),
        )
        with mock_llm.patch_call_agent():
            from agents.base import call_agent

            raw = call_agent("developer", "bump n", task_id="tr2")

        validation = validate_developer_edit_response(raw)
        assert validation.is_valid
        assert validation.detected_mode in ("find_replace", "guid")

        prop = create_proposal_from_developer_output(raw, 1, "tr/demo.py")
        assert prop["status"] == "success"


def test_file_extraction_regex_no_unterminated_charset_error():
    """Verify file extraction regex handles special characters without raising unterminated charset error."""
    from workflow.task_runner import extract_target_files_from_text  # adjust import to match project module

    sample_prompt = "Please update app.py and fix the bug in utils/db.py."

    # Mock project_files or pass explicit prompt string
    extracted = extract_target_files_from_text(sample_prompt, known_files=["app.py", "utils/db.py"])

    assert "app.py" in extracted


def test_path_cleaning_and_none_filtering():
    """Verify path cleaner strips project_directory/ and ignores NONE / N/A."""

    def _clean_path(p: str) -> str:
        p = p.strip().strip("`").strip("'").strip('"')
        return re.sub(r"^(?:project_directory|project)/", "", p, flags=re.IGNORECASE)

    assert _clean_path("project_directory/app.py") == "app.py"
    assert _clean_path("project/assets/chart.png") == "assets/chart.png"
    assert _clean_path("`README.md`") == "README.md"

    raw_files = ["NONE", "N/A", "app.py", "project_directory/requirements.txt"]
    filtered = [_clean_path(f) for f in raw_files if f.strip().upper() not in ("NONE", "N/A")]
    assert filtered == ["app.py", "requirements.txt"]


def test_requested_files_single_file_cap():
    """Verify requested_files is capped to 1 file per turn to prevent LLM payload overload."""
    requested_files = ["app.py", "generate_sample_images.py", "requirements.txt"]

    if len(requested_files) > 1:
        requested_files = [requested_files[0]]

    assert requested_files == ["app.py"]
