"""§16.1 map-first reviewer feed: map, need_files/covered parsing, slices, blast radius."""

import sqlite3
from typing import ClassVar

from core.db import get_db_path
from core.review_feed import (
    MAX_LINES_PER_SLICE,
    MAX_SLICE_TOTAL_LINES,
    SliceSpec,
    blast_radius_paths,
    build_reviewer_map,
    extract_covered,
    extract_need_files,
    serve_need_files,
    should_skip_review_path,
)


def _connect():
    return sqlite3.connect(get_db_path())


def _seed_files(conn, rows):
    """Seed project_files rows: (path, content, hash, modified, size, type, binary)."""
    for row in rows:
        path, content, digest, modified, size, ftype, binary = row
        conn.execute(
            """
            INSERT INTO project_files
            (file_path, content, content_hash, last_modified, size_bytes, file_type, is_binary)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (path, content, digest, modified, size, ftype, 1 if binary else 0),
        )


def _seed_summaries(conn, rows):
    for path, summary, purpose, line_count in rows:
        conn.execute(
            """
            INSERT INTO file_summaries (file_path, summary, purpose, line_count, generated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (path, summary, purpose, line_count, "2026-01-01T00:00:00"),
        )


def _seed_symbols(conn, rows):
    for path, kind, name, lineno in rows:
        conn.execute(
            """
            INSERT INTO file_symbols (file_path, kind, name, qualname, lineno, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (path, kind, name, name, lineno, "2026-01-01T00:00:00"),
        )


def _seed_governed_lines(conn, path, contents):
    conn.execute(
        "INSERT INTO files (file_path) VALUES (?)",
        (path,),
    )
    file_id = conn.execute("SELECT file_id FROM files WHERE file_path = ?", (path,)).fetchone()[0]
    for i, text in enumerate(contents, start=1):
        conn.execute(
            """
            INSERT INTO file_lines (line_guid, file_id, sort_order, content, is_deleted, version)
            VALUES (?, ?, ?, ?, 0, 1)
            """,
            (f"{path}::{i}", file_id, float(i), text),
        )
    return file_id


class TestSkipReviewPath:
    def test_binaries_logos_always_skipped(self):
        assert should_skip_review_path("assets/logo.png") is True
        assert should_skip_review_path("vendor/lib.so", seed_named=True) is True
        assert should_skip_review_path("static/icon.ico") is True

    def test_lockfiles_skipped_unless_seed_named(self):
        assert should_skip_review_path("poetry.lock") is True
        assert should_skip_review_path("poetry.lock", seed_named=True) is False
        assert should_skip_review_path("package-lock.json") is True
        assert should_skip_review_path("package-lock.json", seed_named=True) is False

    def test_todo_skipped_unless_seed_named(self):
        assert should_skip_review_path("docs/TODO.md") is True
        assert should_skip_review_path("docs/TODO.md", seed_named=True) is False
        assert should_skip_review_path("docs/PLAN.md") is False

    def test_source_kept(self):
        assert should_skip_review_path("core/db.py") is False


class TestParseNeedFilesAndCovered:
    def test_extract_valid_need_files(self):
        data = {
            "need_files": [
                {"file_path": "core/db.py", "start": 150, "end": 300, "why": "check schema"},
            ],
            "covered": [],
        }
        specs = extract_need_files(data)
        assert specs == [SliceSpec("core/db.py", 150, 300, "check schema")]

    def test_extract_aliases_and_swapped_range(self):
        data = {
            "need_files": [
                {"file": "workflow/task_runner.py", "from": 40, "to": 10, "reason": "loop"},
                {"path": "x.py", "lines_lo": 5, "lines_hi": 9},
            ],
        }
        specs = extract_need_files(data)
        assert specs[0] == SliceSpec("workflow/task_runner.py", 10, 40, "loop")
        assert specs[1] == SliceSpec("x.py", 5, 9, "")

    def test_zero_range_is_whole_file_not_need(self):
        data = {"need_files": [{"file_path": "a.py", "start": 0, "end": 0}]}
        assert extract_need_files(data) == []

    def test_fail_closed_on_shape(self):
        assert extract_need_files({"need_files": "oops"}) == []
        assert extract_need_files({"need_files": [{"file_path": "a.py"}]}) == []
        assert extract_need_files({"need_files": [{"start": 1, "end": 2}]}) == []
        assert extract_need_files({"need_files": [{"file_path": "a.py", "start": -5, "end": 1}]}) == []
        assert extract_need_files(None) == []
        assert extract_need_files("not-a-dict") == []

    def test_slice_cap_enforced(self):
        data = {"need_files": [{"file_path": f"f{i}.py", "start": 1, "end": 10} for i in range(10)]}
        assert len(extract_need_files(data)) <= 3

    def test_extract_covered(self):
        data = {
            "covered": [
                {"file_path": "a.py", "start": 0, "end": 0},
                {"file": "b.py", "start": 10, "end": 20},
            ]
        }
        covered = extract_covered(data)
        assert covered[0].lines_lo == 0 and covered[0].lines_hi == 0
        assert covered[1].file_path == "b.py"
        assert (covered[1].lines_lo, covered[1].lines_hi) == (10, 20)

    def test_extract_covered_fail_closed(self):
        assert extract_covered({"covered": []}) == []
        assert extract_covered({"covered": "x"}) == []
        assert extract_covered({"covered": [{"start": 1}]}) == []


class TestBuildReviewerMap:
    def test_map_is_structural_never_bodies(self, temp_db):
        conn = _connect()
        _seed_files(
            conn,
            [
                ("core/db.py", "HUNK_SOURCE_SECRET = 'top-secret'\ndef real_impl(): ...\n", "h1", "2026-01-01", 200, ".py", False),
                ("core/review_feed.py", "# real body body body\n...\n", "h2", "2026-01-01", 120, ".py", False),
                ("assets/logo.png", b"\x89PNG", "h3", "2026-01-01", 100, ".png", True),
            ],
        )
        _seed_summaries(
            conn,
            [
                ("core/db.py", "DB schema + init", "sqlite bootstrap", 200),
                ("core/review_feed.py", "Map-first review feed", "review context", 120),
            ],
        )
        _seed_symbols(
            conn,
            [
                ("core/db.py", "FUNCTION", "get_db_path", 12),
                ("core/db.py", "FUNCTION", "init_db", 30),
                ("core/review_feed.py", "FUNCTION", "build_reviewer_map", 5),
            ],
        )
        conn.commit()
        conn.close()

        output = build_reviewer_map(sqlite3.connect(get_db_path()), focus_path="core/review_feed.py")
        assert "core/review_feed.py" in output
        assert "core/db.py" in output
        assert "assets/logo.png" not in output  # binary filtered
        assert "get_db_path" in output  # symbols
        assert "init_db" in output
        assert "top-secret" not in output  # never a source body
        assert "real_impl()" not in output
        # focus path sorted first
        assert output.index("core/review_feed.py") < output.index("core/db.py")

    def test_map_row_cap(self, temp_db):
        conn = _connect()
        _seed_files(
            conn,
            [(f"pkg/f{i:03d}.py", "body", f"h{i}", "2026-01-01", 10, ".py", False) for i in range(120)],
        )
        _seed_summaries(
            conn,
            [(f"pkg/f{i:03d}.py", f"summary {i}", "p", 10) for i in range(120)],
        )
        conn.commit()
        conn.close()

        output = build_reviewer_map(sqlite3.connect(get_db_path()), max_rows=80)
        # one file per row; cap enforced
        assert output.count("- pkg/") == 80


class TestServeNeedFiles:
    def test_serves_exact_window_from_governed_db(self, temp_db):
        conn = _connect()
        _seed_governed_lines(conn, "sample.py", [f"line {i}" for i in range(1, 301)])
        conn.commit()
        conn.close()

        block = serve_need_files(
            sqlite3.connect(get_db_path()),
            [SliceSpec("sample.py", 10, 13, "need to see the header")],
        )
        assert "**sample.py** (lines 10-13)" in block
        assert "requested for: need to see the header" in block
        assert "10: line 10" in block
        assert "13: line 13" in block
        assert "14: line 14" not in block

    def test_window_clamped_to_slice_max(self, temp_db):
        conn = _connect()
        _seed_governed_lines(conn, "big.py", [f"line {i}" for i in range(1, 2001)])
        conn.commit()
        conn.close()

        block = serve_need_files(
            sqlite3.connect(get_db_path()),
            [SliceSpec("big.py", 1, 5000)],
        )
        assert "(lines 1-200)" in block
        assert MAX_LINES_PER_SLICE == 200

    def test_hard_total_line_cap(self, temp_db):
        conn = _connect()
        _seed_governed_lines(conn, "a.py", [f"a{i}" for i in range(1, 1001)])
        _seed_governed_lines(conn, "b.py", [f"b{i}" for i in range(1, 1001)])
        conn.commit()
        conn.close()

        block = serve_need_files(
            sqlite3.connect(get_db_path()),
            [SliceSpec("a.py", 1, 1000), SliceSpec("b.py", 1, 1000)],
            max_total_lines=250,
        )
        assert MAX_SLICE_TOTAL_LINES == 500
        assert "(lines 1-200)" in block
        # second slice squeezed by the remaining budget (50 lines)
        assert "(lines 1-50)" in block
        assert "total line cap" in block

    def test_junk_paths_refused(self, temp_db):
        conn = _connect()
        conn.commit()
        conn.close()
        block = serve_need_files(
            sqlite3.connect(get_db_path()),
            [SliceSpec("assets/logo.png", 1, 10)],
        )
        assert block == ""

    def test_empty_specs(self, temp_db):
        assert serve_need_files(sqlite3.connect(get_db_path()), []) == ""


class TestBlastRadius:
    CANDIDATES: ClassVar[list[tuple[str, str]]] = [
        ("pkg/mod.py", "import pkg.core\n\ndef compute(x):\n    return x + 1\n"),
        ("pkg/core.py", "def base():\n    return 42\n"),
        ("pkg/mid.py", "import pkg.mod\n\ndef mid():\n    return compute(1)\n"),
        ("tests/test_mod.py", "from pkg.mod import compute\n\ndef test_compute():\n    assert compute(1) == 2\n"),
        ("tests/test_mid.py", "from pkg.mid import mid\n\ndef test_mid():\n    assert mid() is not None\n"),
    ]

    def _seed(self, changed_path, symbols):
        conn = _connect()
        _seed_files(
            conn,
            [(p, c, f"h{p}", "2026-01-01", len(c), ".py", False) for p, c in self.CANDIDATES],
        )
        _seed_symbols(conn, symbols)
        conn.commit()
        conn.close()

    def test_junk_changed_path_returns_empty(self, temp_db):
        conn = _connect()
        conn.commit()
        conn.close()
        assert blast_radius_paths(sqlite3.connect(get_db_path()), "assets/logo.png") == []

    def test_finds_symbol_consumers_and_importers(self, temp_db, capsys):
        self._seed(
            "pkg/mod.py",
            [
                ("pkg/mod.py", "FUNCTION", "compute", 4),
                ("tests/test_mod.py", "FUNCTION", "test_compute", 3),
            ],
        )
        result = blast_radius_paths(
            sqlite3.connect(get_db_path()),
            "pkg/mod.py",
            candidates=self.CANDIDATES,
            max_paths=6,
        )
        assert result[0] == "pkg/mod.py"
        body = set(result[1:])
        # symbol_index consumer AND import-scan importer are both discovered
        assert "tests/test_mod.py" in body
        # pkg/mid.py imports pkg.mod -> level-1 importer
        assert "pkg/mid.py" in body

    def test_depth_two_transitive(self, temp_db):
        self._seed(
            "pkg/mod.py",
            [
                ("pkg/mod.py", "FUNCTION", "compute", 4),
                ("tests/test_mod.py", "FUNCTION", "test_compute", 3),
            ],
        )
        result = blast_radius_paths(
            sqlite3.connect(get_db_path()),
            "pkg/mod.py",
            candidates=self.CANDIDATES,
            max_paths=6,
        )
        body = set(result[1:])
        # pkg/mid.py (level 1) imports pkg.mod; tests/test_mid.py (level 2)
        # imports pkg.mid -> the transitive blast radius is included.
        assert "pkg/mid.py" in body
        assert "tests/test_mid.py" in body

    def test_unrelated_file_not_in_radius(self, temp_db):
        candidates = [*self.CANDIDATES, ("pkg/other.py", "def totally_unrelated():\n    print('hi')\n")]
        self._seed(
            "pkg/mod.py",
            [
                ("pkg/mod.py", "FUNCTION", "compute", 4),
                ("tests/test_mod.py", "FUNCTION", "test_compute", 3),
            ],
        )
        result = blast_radius_paths(
            sqlite3.connect(get_db_path()),
            "pkg/mod.py",
            candidates=candidates,
            max_paths=6,
        )
        assert "pkg/other.py" not in result


class TestPoolRewiringHooks:
    def test_background_agents_random_review_defaults_off(self, temp_db, isolated_project):
        """§16.1: the example config defaults random_review to off."""
        import json
        from pathlib import Path

        example = json.loads(Path("example_config.json").read_text(encoding="utf-8"))
        agents = example["background_agents"]
        for name, cfg in agents.items():
            if isinstance(cfg, dict) and "random_review" in cfg:
                assert cfg["random_review"] is False, f"{name} must default random_review off"


class TestCoverageSweepLedger:
    """§16.2: sweep picks hash-miss, then never-seen, then fan-in; receipts."""

    def _seed_project(self, conn, files):
        """files: {path: (content, line_count)}"""
        for path, (content, line_count) in files.items():
            _seed_files(
                conn,
                [(path, content, f"hash-{path}", "2026-01-01", len(content), ".py", False)],
            )
            _seed_summaries(conn, [(path, "purpose", "p", line_count)])
            _seed_governed_lines(conn, path, [f"line {i}" for i in range(1, line_count + 1)])

    def test_hash_miss_beats_never_seen(self, temp_db):
        from core.review_feed import coverage_sweep_next

        conn = _connect()
        self._seed_project(
            conn,
            {
                "a.py": ("# a\n" * 50, 50),
                "b.py": ("# b\n" * 200, 200),
            },
        )
        # b.py was reviewed before with a stale hash -> hash miss.
        conn.execute(
            "INSERT INTO agent_review_tracking (agent_name, file_path, last_reviewed_at, content_hash_reviewed, feedback_count)"
            " VALUES ('jr_reviewer', 'b.py', '2026-01-01T00:00:00', 'OLD-HASH', 1)"
        )
        conn.commit()
        conn.close()

        spec = coverage_sweep_next(sqlite3.connect(get_db_path()), agent_name="jr_reviewer")
        assert spec is not None
        assert spec.file_path == "b.py"  # hash miss prioritized over never-seen a.py
        span = spec.end - spec.start + 1
        assert 80 <= span <= 120

    def test_never_seen_next_after_hash_miss_covered(self, temp_db):
        from core.review_feed import coverage_sweep_next

        conn = _connect()
        self._seed_project(
            conn,
            {
                "a.py": ("# a\n" * 50, 50),
                "b.py": ("# b\n" * 200, 200),
            },
        )
        # b.py fully covered (current hash) -> a.py (never seen) becomes next.
        conn.execute(
            "INSERT INTO agent_review_tracking (agent_name, file_path, last_reviewed_at, content_hash_reviewed, feedback_count)"
            " VALUES ('jr_reviewer', 'b.py', '2026-01-01T00:00:00', 'hash-b.py', 1)"
        )
        conn.execute(
            "INSERT INTO review_coverage (agent_name, file_path, lines_lo, lines_hi, content_hash, covered_at)"
            " VALUES ('jr_reviewer', 'b.py', 1, 200, 'hash-b.py', '2026-01-01T00:00:00')"
        )
        conn.commit()
        conn.close()

        spec = coverage_sweep_next(sqlite3.connect(get_db_path()), agent_name="jr_reviewer")
        assert spec is not None and spec.file_path == "a.py"
        assert spec.start == 1 and spec.end == 50

    def test_sweep_returns_none_when_fully_covered(self, temp_db):
        from core.review_feed import coverage_sweep_next

        conn = _connect()
        self._seed_project(conn, {"a.py": ("# a\n" * 90, 90)})
        conn.execute(
            "INSERT INTO agent_review_tracking (agent_name, file_path, last_reviewed_at, content_hash_reviewed, feedback_count)"
            " VALUES ('jr_reviewer', 'a.py', '2026-01-01T00:00:00', 'hash-a.py', 1)"
        )
        conn.execute(
            "INSERT INTO review_coverage (agent_name, file_path, lines_lo, lines_hi, content_hash, covered_at)"
            " VALUES ('jr_reviewer', 'a.py', 1, 90, 'hash-a.py', '2026-01-01T00:00:00')"
        )
        conn.commit()
        conn.close()

        spec = coverage_sweep_next(sqlite3.connect(get_db_path()), agent_name="jr_reviewer")
        assert spec is None

    def test_diagnostic_percent_and_oldest_uncovered(self, temp_db):
        from core.review_feed import coverage_diagnostic, format_coverage_diagnostic

        conn = _connect()
        self._seed_project(
            conn,
            {
                "a.py": ("# a\n" * 100, 100),  # fully covered (hash match => all 100)
                "b.py": ("# b\n" * 200, 200),  # partially covered => 120 lines
            },
        )
        conn.execute(
            "INSERT INTO agent_review_tracking (agent_name, file_path, last_reviewed_at, content_hash_reviewed, feedback_count)"
            " VALUES ('jr_reviewer', 'a.py', '2026-01-01T00:00:00', 'hash-a.py', 1)"
        )
        conn.execute(
            "INSERT INTO agent_review_tracking (agent_name, file_path, last_reviewed_at, content_hash_reviewed, feedback_count)"
            " VALUES ('jr_reviewer', 'b.py', '2026-01-01T00:00:00', 'hash-b.py', 1)"
        )
        # a.py whole-file receipt (0,0) at the current hash -> 100 lines.
        conn.execute(
            "INSERT INTO review_coverage (agent_name, file_path, lines_lo, lines_hi, content_hash, covered_at)"
            " VALUES ('jr_reviewer', 'a.py', 0, 0, 'hash-a.py', '2026-01-01T00:00:00')"
        )
        # b.py lines 1-120 (current hash) -> 120 lines.
        conn.execute(
            "INSERT INTO review_coverage (agent_name, file_path, lines_lo, lines_hi, content_hash, covered_at)"
            " VALUES ('jr_reviewer', 'b.py', 1, 120, 'hash-b.py', '2026-01-01T00:00:00')"
        )
        # Stale receipt for b.py lines 150-200 (old content hash) -> invalidated.
        conn.execute(
            "INSERT INTO review_coverage (agent_name, file_path, lines_lo, lines_hi, content_hash, covered_at)"
            " VALUES ('jr_reviewer', 'b.py', 150, 200, 'STALE', '2026-01-01T00:00:00')"
        )
        conn.commit()
        conn.close()

        stats = coverage_diagnostic(sqlite3.connect(get_db_path()))
        assert stats["total_source_lines"] == 300
        agent = stats["per_agent"]["jr_reviewer"]
        assert agent["covered_lines"] == 220  # 100 + 120; stale receipt ignored
        assert agent["percent"] == round(220 / 300 * 100, 2)
        assert agent["oldest_uncovered_path"] == "b.py"
        text = format_coverage_diagnostic(stats)
        assert "jr_reviewer" in text

    def test_hollow_receipt_detection(self):
        from agents.parallel_workers import BackgroundAgentPool

        is_hollow = BackgroundAgentPool._is_hollow_receipt
        assert is_hollow({"findings": [], "covered": [], "summary": "ok"}) is True
        assert is_hollow({"findings": [], "covered": [{"file_path": "a.py", "start": 1, "end": 50}]}) is False
        assert is_hollow({"findings": [{"file_path": "a.py", "message": "x" * 20}]}) is False
        assert is_hollow(None) is True
        assert is_hollow("junk") is True
