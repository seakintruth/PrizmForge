"""
tests/unit/test_harness_corpus.py

Unit tests for the §12.3 trajectory corpus (docs/TODO.md §12.3,
HARNESS_EVOLUTION_DESIGN §4): base64-drop + consecutive-frame-dedup cleaning,
the Debugger producer (enum-validated component hints), and the corpus pipeline
(cleaned/ + analysis/ + overview.md + index.json). LLM calls are stubbed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


def _raw_trajectory(*messages: dict) -> dict:
    return {
        "trajectory_format": "prizmforge-shell-developer-1.0",
        "exit_status": "Completed",
        "finished_at": "2026-09-10T00:00:01Z",
        "messages": list(messages),
    }


def _write_raw(raw_dir: Path, name: str, data: dict) -> Path:
    p = raw_dir / name
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


class TestDropBase64:
    def test_data_uri_blob_is_dropped(self):
        from harness.cleaning import drop_base64

        text = "here: data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNgYGBgAAAABQABh6FO1AAAAABJRU5ErkJggg== and after"
        out = drop_base64(text)
        assert "base64,iVBORw0KGgo" not in out
        assert "and after" in out

    def test_long_base64_run_is_replaced(self):
        from harness.cleaning import drop_base64

        blob = "A" * 200
        out = drop_base64(f"prefix {blob} suffix")
        assert "[base64 payload dropped]" in out
        assert "suffix" in out

    def test_code_indented_text_survives(self):
        from harness.cleaning import drop_base64

        code = "path = /home/user/project/src/main.py\nsha = 'a1b2c3d4...'\n"
        assert drop_base64(code) == code


class TestCleanFramesAndTask:
    def test_consecutive_duplicates_collapse_with_count(self):
        from harness.cleaning import clean_frames

        frames = [
            {"role": "user", "content": "A", "turn": 1},
            {"role": "user", "content": "A", "turn": 1},
            {"role": "assistant", "content": "B", "turn": 1},
            {"role": "user", "content": "A", "turn": 2},
        ]
        cleaned = clean_frames(frames)
        assert [f["content"] for f in cleaned] == ["A", "B", "A"]
        assert [f["dup_count"] for f in cleaned] == [2, 1, 1]

    def test_base64_dropped_then_dedup_on_cleaned_content(self):
        from harness.cleaning import clean_frames

        frames = [
            {"role": "user", "content": f"out {('B' * 150)} x", "turn": 1},
            {"role": "user", "content": f"out {('B' * 150)} x", "turn": 1},
        ]
        cleaned = clean_frames(frames)
        assert len(cleaned) == 1
        assert cleaned[0]["dup_count"] == 2
        assert "[base64 payload dropped]" in cleaned[0]["content"]

    def test_clean_task_into_merges_and_sorts_turns(self, tmp_path):
        from harness.cleaning import clean_task_into

        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        _write_raw(
            raw_dir,
            "t-sk-turn1-20260910T000000Z.json",
            _raw_trajectory(
                {"role": "system", "content": "SYS"},
                {"role": "assistant", "content": "assistant turn1"},
            ),
        )
        _write_raw(
            raw_dir,
            "t-sk-turn2-20260910T000100Z.json",
            _raw_trajectory(
                {"role": "user", "content": "user turn2"},
            ),
        )

        out_dir = tmp_path / "cleaned"
        frames = clean_task_into("t-sk", [raw_dir / "t-sk-turn1-20260910T000000Z.json", raw_dir / "t-sk-turn2-20260910T000100Z.json"], out_dir)
        assert [f["role"] for f in frames] == ["system", "assistant", "user"]
        assert [f["turn"] for f in frames] == [1, 1, 2]

        lines = (out_dir / "t-sk.jsonl").read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 3
        first = json.loads(lines[0])
        assert first["role"] == "system"
        assert "_seq" not in first

    def test_raw_files_never_touched(self, tmp_path):
        from harness.cleaning import clean_task_into

        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        p = _write_raw(
            raw_dir,
            "t-ro-turn1-20260910T000000Z.json",
            _raw_trajectory({"role": "assistant", "content": "orig blob " + "C" * 150}),
        )
        before = p.read_text(encoding="utf-8")
        clean_task_into("t-ro", [p], tmp_path / "cleaned")
        assert p.read_text(encoding="utf-8") == before

    def test_group_raw_by_task_with_hyphen_ids(self, tmp_path):
        from harness.cleaning import group_raw_by_task, task_id_from_source

        assert task_id_from_source("t01-rename-const_i7_t2-turn1-20260910T000000Z.json") == "t01-rename-const_i7_t2"

        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        _write_raw(raw_dir, "t01-rename-const_i7_t2-turn1-20260910T000000Z.json", _raw_trajectory())
        _write_raw(raw_dir, "t01-rename-const_i7_t2-turn2-20260910T000100Z.json", _raw_trajectory())
        _write_raw(raw_dir, "t05_todo-turn1-20260910T000200Z.json", _raw_trajectory())
        grouped = group_raw_by_task(raw_dir)
        assert set(grouped) == {"t01-rename-const_i7_t2", "t05_todo"}
        assert len(grouped["t01-rename-const_i7_t2"]) == 2


class TestDebuggerParse:
    def test_parse_fenced_json_report(self):
        from harness.debugger import parse_report

        text = (
            "```json\n"
            '{"task_id": "t1", "passed": true, "success_patterns": ["inspect first"], '
            '"root_causes": [{"evidence_file": "cleaned/t1.jsonl", '
            '"inferred_root_cause": "latch storm", "component_hint": "endpoint"}]}\n'
            "```\n"
        )
        report = parse_report("t1", text)
        assert report.passed is True
        assert report.success_patterns == ("inspect first",)
        assert report.root_causes[0].component_hint == "endpoint"
        assert report.root_causes[0].inferred_root_cause == "latch storm"
        assert report.inference_error == ""

    def test_invalid_component_hint_is_reported_not_crashed(self):
        from harness.debugger import parse_report

        text = (
            '{"task_id": "t1", "passed": false, "root_causes": ['
            '{"evidence_file": "cleaned/t1.jsonl", "inferred_root_cause": "r", "component_hint": "harness_prompt"},'
            '{"evidence_file": "x", "inferred_root_cause": "r2", "component_hint": "made_up"}]}'
        )
        report = parse_report("t1", text)
        assert len(report.root_causes) == 1
        assert report.root_causes[0].component_hint == "harness_prompt"
        assert "invalid_component_hints:made_up" in report.inference_error

    def test_unparseable_report(self):
        from harness.debugger import parse_report

        report = parse_report("t1", "not json at all")
        assert report.passed is None
        assert report.inference_error == "unparseable_report"

    def test_task_id_mismatch_noted(self):
        from harness.debugger import parse_report

        report = parse_report("t1", '{"task_id": "OTHER", "passed": true, "root_causes": []}')
        assert "task_id_mismatch:OTHER" in report.inference_error


class TestAnalyzeTask:
    def _json_for(self, task_id: str) -> str:
        return json.dumps(
            {
                "task_id": task_id,
                "passed": True,
                "root_causes": [],
                "success_patterns": ["read task, mutate"],
            }
        )

    def _frames(self):
        from harness.cleaning import extract_frames

        return extract_frames(
            _raw_trajectory({"role": "assistant", "content": "inspect first.zip"}),
            source="t-a-turn1-20260910T000000Z.json",
        )

    def test_analyze_task_calls_llm_and_parses(self):
        from harness.debugger import analyze_task

        calls = []

        def stub_llm(messages, model=None, task_id="", agent_name=""):
            calls.append((model, task_id, agent_name, messages))
            return (self._json_for("t-a"), 5)

        report = analyze_task("t-a", self._frames(), llm=stub_llm)
        assert report.passed is True
        assert report.inference_error == ""
        assert calls[0][1] == "debugger:t-a"
        assert calls[0][2] == "debugger"
        assert any(msg["role"] == "system" for msg in calls[0][3])

    def test_llm_error_degrades_to_inference_error(self):
        from harness.debugger import analyze_task

        def stub_llm(messages, model=None, task_id="", agent_name=""):
            raise RuntimeError("boom")

        report = analyze_task("t-a", self._frames(), llm=stub_llm)
        assert report.passed is None
        assert report.inference_error.startswith("llm_error:")

    def test_empty_llm_response(self):
        from harness.debugger import analyze_task

        report = analyze_task("t-a", self._frames(), llm=lambda *a, **k: (None, 0))
        assert report.inference_error == "empty_llm_response"

    def test_run_producer_parallel(self):
        from harness.debugger import run_producer

        def stub_llm(messages, model=None, task_id="", agent_name=""):
            tid = task_id.removeprefix("debugger:")
            return (self._json_for(tid), 1)

        frames = self._frames()
        reports = run_producer({"t-a": frames, "t-b": frames}, llm=stub_llm, max_workers=2)
        assert sorted(reports) == ["t-a", "t-b"]
        for tid in ("t-a", "t-b"):
            assert reports[tid].passed is True


class TestRenderMarkdown:
    def test_common_analysis_md_carries_evidence(self):
        from harness.debugger import DebuggerReport, RootCause, render_analysis_md

        report = DebuggerReport(
            task_id="t1",
            passed=False,
            root_causes=(RootCause("cleaned/t1.jsonl", "storm", "endpoint"),),
            success_patterns=(),
        )
        md = render_analysis_md("t1", report)
        assert "# t1" in md
        assert "**endpoint**" in md
        assert "`cleaned/t1.jsonl`" in md
        assert "cleaned/t1.jsonl" in md  # drill-down link


@pytest.fixture
def stub_llm_factory():
    def make():
        def stub_llm(messages, model=None, task_id="", agent_name=""):
            tid = task_id.removeprefix("debugger:")
            return (
                json.dumps(
                    {
                        "task_id": tid,
                        "passed": "t01_rename" in tid,
                        "root_causes": (
                            [{"evidence_file": f"cleaned/{tid}.jsonl", "inferred_root_cause": "latch storm", "component_hint": "endpoint"}]
                            if "t01_rename" not in tid
                            else []
                        ),
                        "success_patterns": ["read task, mutate"] if "t01_rename" in tid else [],
                    }
                ),
                1,
            )

        return stub_llm

    return make


class TestCorpusPipeline:
    def test_produce_corpus_emits_layered_artifacts(self, tmp_path, stub_llm_factory):
        from harness.corpus import produce_corpus

        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        _write_raw(
            raw_dir,
            "t01_rename_constant_i9_t1-turn1-20260910T000000Z.json",
            _raw_trajectory(
                {"role": "system", "content": "SYS"},
                {"role": "assistant", "content": "blob " + "D" * 150},
            ),
        )
        _write_raw(
            raw_dir,
            "t05_todo_to_marker_i9_t1-turn1-20260910T000100Z.json",
            _raw_trajectory(
                {"role": "assistant", "content": "same"},
                {"role": "assistant", "content": "same"},
            ),
        )
        results_file = tmp_path / "results.json"
        results_file.write_text(
            json.dumps(
                {
                    "iteration": 9,
                    "tasks": [
                        {"task_id": "t01_rename_constant", "k": 1, "trials": [{"trial": 1, "verdict": "passed"}]},
                        {"task_id": "t05_todo_to_marker", "k": 1, "trials": [{"trial": 1, "verdict": "failed"}]},
                    ],
                }
            ),
            encoding="utf-8",
        )
        runs_dir = tmp_path / "runs" / "iter_9"

        summary = produce_corpus(
            9,
            raw_dir=raw_dir,
            runs_dir=runs_dir,
            results=json.loads(results_file.read_text(encoding="utf-8")),
            llm=stub_llm_factory(),
            max_workers=2,
        )
        assert summary["cleaned"] == 2
        assert summary["analysis"] == 2

        cleaned = runs_dir / "cleaned" / "t01_rename_constant_i9_t1.jsonl"
        assert cleaned.exists()
        frame = json.loads(cleaned.read_text(encoding="utf-8").splitlines()[1])
        assert "[base64 payload dropped]" in frame["content"]

        analysis = runs_dir / "analysis" / "t01_rename_constant_i9_t1.md"
        assert analysis.exists()
        assert "passed: True" in analysis.read_text(encoding="utf-8")

        t05 = runs_dir / "cleaned" / "t05_todo_to_marker_i9_t1.jsonl"
        lines = t05.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1, "consecutive duplicate frames must collapse"
        assert json.loads(lines[0])["dup_count"] == 2

        index = json.loads((runs_dir / "index.json").read_text(encoding="utf-8"))
        assert index["entry"] == "overview.md"
        assert index["iteration"] == 9
        t05_entry = index["tasks"]["t05_todo_to_marker_i9_t1"]
        assert t05_entry["verdict"] == "failed"
        assert t05_entry["component_hints"] == ["endpoint"]
        assert t05_entry["cleaned"] == "cleaned/t05_todo_to_marker_i9_t1.jsonl"
        assert len(t05_entry["raw"]) == 1
        assert "inference_error" in t05_entry

        overview = (runs_dir / "overview.md").read_text(encoding="utf-8")
        assert "### endpoint" in overview
        assert "t05_todo_to_marker_i9_t1" in overview
        assert "## Passing tasks by success pattern" in overview
        assert "t01_rename_constant_i9_t1" in overview

    def test_produce_corpus_empty_raw(self, tmp_path, stub_llm_factory):
        from harness.corpus import produce_corpus

        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        runs_dir = tmp_path / "runs" / "iter_1"
        summary = produce_corpus(1, raw_dir=raw_dir, runs_dir=runs_dir, llm=stub_llm_factory())
        assert summary["cleaned"] == 0
        assert summary["analysis"] == 0
        index = json.loads((runs_dir / "index.json").read_text(encoding="utf-8"))
        assert index["tasks"] == {}
