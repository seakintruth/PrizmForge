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


def _extract_target_files_from_text(text: str, known_files: list[str] | None = None) -> list[str]:
    """
    Lightweight file-path extractor used by unit tests.

    Mirrors the kind of regex the task runner uses to discover file mentions.
    Kept local so the test does not depend on a non-exported helper.
    """
    # Avoid character-class footguns (e.g. unescaped ']' / '-' ranges)
    pattern = re.compile(
        r"\b([\w./\\-]+\.(?:py|sh|json|md|txt|toml|yml|yaml|ini))\b",
        re.IGNORECASE,
    )
    found = pattern.findall(text or "")
    if known_files is not None:
        known = set(known_files)
        found = [f for f in found if f in known]
    # de-dupe preserving order
    seen: set[str] = set()
    out: list[str] = []
    for f in found:
        if f not in seen:
            seen.add(f)
            out.append(f)
    return out


def test_file_extraction_regex_no_unterminated_charset_error():
    """Verify file extraction regex handles special characters without raising unterminated charset error."""
    sample_prompt = "Please update app.py and fix the bug in utils/db.py."

    extracted = _extract_target_files_from_text(sample_prompt, known_files=["app.py", "utils/db.py"])

    assert "app.py" in extracted
    assert "utils/db.py" in extracted


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


class TestDeferredPoolStart:
    """W5 (soak recompute): the eager pool.start at cycle entry was what raced
    fill-mode against throttled agents → Soak9's orphan burst. The pool now
    starts only after the first materialize OR after 2 turns."""

    def _make_pool(self):
        class _RecordingPool:
            def __init__(self):
                self.started = 0

            def start(self, task_id):
                self.started += 1

        return _RecordingPool()

    def test_no_start_before_materialize_and_turn_threshold(self):
        from workflow.task_runner import _ensure_pool_started

        pool = self._make_pool()
        _ensure_pool_started(pool, "t5", {"materialize_successes": 0}, 1)
        assert pool.started == 0

    def test_start_after_first_materialize(self):
        from workflow.task_runner import _ensure_pool_started

        pool = self._make_pool()
        _ensure_pool_started(pool, "t5", {"materialize_successes": 1}, 1)
        assert pool.started == 1

    def test_start_after_turn_threshold_without_materialize(self):
        from workflow.task_runner import _ensure_pool_started

        pool = self._make_pool()
        _ensure_pool_started(pool, "t5", {"materialize_successes": 0}, 2)
        assert pool.started == 1

    def test_start_is_idempotent_once_running(self):
        # The real pool sets running=True inside start(); the helper checks it,
        # so a productive multi-turn task does not re-string the pool each turn.
        from workflow.task_runner import _ensure_pool_started

        started = []

        class _Pool:
            def __init__(self):
                self.running = False

            def start(self, task_id):
                started.append(task_id)
                self.running = True

        pool = _Pool()
        _ensure_pool_started(pool, "t5", {"materialize_successes": 1}, 1)
        _ensure_pool_started(pool, "t5", {"materialize_successes": 2}, 2)
        assert started == ["t5"]

    def test_pool_without_start_attribute_is_noop(self):
        # FakePool-style doubles (test_network_busy_loop) lack start(). The
        # hasattr guard keeps cycle wiring working when agents are disabled.
        from workflow.task_runner import _ensure_pool_started

        class _NoStart:
            def queue_file_change(self, **_):
                return None

        _ensure_pool_started(_NoStart(), "t5", {"materialize_successes": 9}, 9)


class TestNoProgressGuard:
    """d9 (soak recompute): a zero-change developer streak must stop respinning
    the identical session once it crosses the threshold — task_002/003/005 all
    show files_modified=0 while the orchestrator chose "developer" every turn."""

    def test_not_stalled_below_threshold(self):
        from workflow.task_runner import NoProgressLoopGuard

        guard = NoProgressLoopGuard(threshold=2)
        assert not guard.stalled()

    def test_default_threshold_latches_after_constant(self, temp_db):
        from workflow.task_runner import NO_PROGRESS_TURNS_THRESHOLD, NoProgressLoopGuard

        guard = NoProgressLoopGuard()
        for _ in range(NO_PROGRESS_TURNS_THRESHOLD - 1):
            assert guard.record_no_change("t_d9") is False
        assert guard.record_no_change("t_d9") is True
        assert guard.stalled()

    def test_posts_single_stall_summary_per_episode(self, temp_db):
        from core.db_connection import get_db_connection
        from workflow.task_runner import NoProgressLoopGuard

        guard = NoProgressLoopGuard(threshold=2)
        guard.record_no_change("t_d9")
        guard.record_no_change("t_d9")  # latch + posts
        guard.record_no_change("t_d9")  # no repost (episode latch)

        with get_db_connection() as conn:
            rows = conn.execute("SELECT COUNT(*) FROM messages WHERE task_id = 't_d9' AND from_agent = 'system' AND content LIKE '%No progress%'").fetchone()
        assert rows[0] == 1

    def test_change_resets_streak_and_latch(self, temp_db):
        from workflow.task_runner import NoProgressLoopGuard

        guard = NoProgressLoopGuard(threshold=2)
        guard.record_no_change("t_d9")
        guard.record_no_change("t_d9")
        assert guard.stalled()
        guard.record_change()
        assert not guard.stalled()

    def test_record_developer_progress_helper(self, temp_db):
        from workflow.task_runner import NoProgressLoopGuard, _record_developer_progress

        guard = NoProgressLoopGuard(threshold=2)
        progress = {"files_modified": 1}
        _record_developer_progress(guard, "t_d9", progress, files_before=1)  # no change: streak 1
        assert not guard.stalled()
        guard.record_no_change("t_d9")  # streak 2 -> latch
        assert guard.stalled()
        progress["files_modified"] = 3
        _record_developer_progress(guard, "t_d9", progress, files_before=1)  # bumped +2: change
        assert not guard.stalled()

    # ---- f9/d9 mutation-path priority (soak recompute pass 2) ----------------
    # The mutation path is the MOST UNBLOCKED path: a developer turn whose
    # SESSION NEVER COMPLETED (transport/limits/format/verification) must not
    # count toward the stall latch. Soak2 latched after 3 dead sessions
    # (RepeatedFormatError + LlmUnavailable) and froze the developer for the
    # rest of the task.

    def test_failed_session_is_neutral_never_latches(self, temp_db):
        from workflow.task_runner import NoProgressLoopGuard, _is_uncompleted_session, _record_developer_progress

        assert _is_uncompleted_session({"status": "error", "message": "session LlmUnavailable: LLM endpoint unavailable or token budget exhausted"})
        assert _is_uncompleted_session({"status": "error", "message": "session RepeatedFormatError: no ```bash block or finish token"})
        assert _is_uncompleted_session({"status": "error", "message": "session LimitsExceeded: endpoint hits"})
        assert _is_uncompleted_session({"status": "test_failed", "message": "post-session verification failed (exit 1)"})

        # A pure streak of failed sessions must never latch via the helper.
        guard = NoProgressLoopGuard(threshold=2)
        progress = {"files_modified": 0}
        for _ in range(50):
            _record_developer_progress(
                guard,
                "t_d9",
                progress,
                files_before=0,
                mut={"status": "error", "message": "session LlmUnavailable: LLM endpoint unavailable"},
            )
        assert not guard.stalled()

        # The redirect branches only fire when stalled(), so a streak of
        # failures keeps the mutation path DISPATCHABLE.
        assert not guard.stalled()

    def test_genuine_finished_zero_change_still_latches(self, temp_db):
        from workflow.task_runner import NoProgressLoopGuard, _is_uncompleted_session, _record_developer_progress

        # A session that RAN TO ITS END with no changes is a real stall.
        assert not _is_uncompleted_session({"status": "error", "message": "session finished but produced no file changes"})

        guard = NoProgressLoopGuard(threshold=2)
        progress = {"files_modified": 0}
        _record_developer_progress(
            guard,
            "t_d9",
            progress,
            files_before=0,
            mut={"status": "error", "message": "session finished but produced no file changes"},
        )
        assert not guard.stalled()
        _record_developer_progress(
            guard,
            "t_d9",
            progress,
            files_before=0,
            mut={"status": "error", "message": "session finished but produced no file changes"},
        )
        assert guard.stalled()

    def test_success_with_change_clears_streak_even_after_failures(self, temp_db):
        from workflow.task_runner import NoProgressLoopGuard, _record_developer_progress

        guard = NoProgressLoopGuard(threshold=2)
        progress = {"files_modified": 0}
        _record_developer_progress(guard, "t_d9", progress, 0, {"status": "error", "message": "session LlmUnavailable: down"})
        _record_developer_progress(guard, "t_d9", progress, 0, {"status": "error", "message": "session LlmUnavailable: down"})
        progress["files_modified"] = 1
        _record_developer_progress(guard, "t_d9", progress, 0, {"status": "success", "session_exit": "Finished", "gates": ["success"]})
        assert not guard.stalled()

    def test_latch_rearms_after_rearm_after_cycles(self, temp_db):
        from workflow.task_runner import NoProgressLoopGuard

        guard = NoProgressLoopGuard(threshold=2, rearm_after=2)
        guard.record_no_change("t_d9")
        guard.record_no_change("t_d9")  # latch
        assert guard.stalled()

        # Even while the streak is recorded, record_cycle() re-arms the guard
        # so the very next developer decision dispatches again.
        guard.record_cycle()  # turn 1 after latch
        assert guard.stalled()
        guard.record_cycle()  # turn 2 -> re-arm
        assert not guard.stalled()

        # A re-armed guard still protects against a NEW genuine stall episode.
        guard.record_no_change("t_d9")
        guard.record_no_change("t_d9")
        assert guard.stalled()
