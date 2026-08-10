"""
Hardening tests for secondary plan S6:
- Path containment / traversal rejection
- Edit mode selection + fallback chain
- Hash conflict (optimistic concurrency)
- Missing GUID rejection
"""

import hashlib
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _hash(content: str) -> str:
    return hashlib.md5(content.encode(usedforsecurity=False)).hexdigest()


# ---------------------------------------------------------------------------
# Path containment
# ---------------------------------------------------------------------------


class TestPathContainment:
    def test_legitimate_relative_write(self, monkeypatch, tmp_path):
        proj = tmp_path / "project"
        proj.mkdir()
        (proj / "src").mkdir()

        monkeypatch.setenv("PRIZMFORGE_DB_PATH", str(tmp_path / "t.db"))
        from core import config as config_mod

        original = config_mod.get_config

        def fake_config():
            cfg = dict(original())
            cfg["project_directory"] = str(proj)
            return cfg

        monkeypatch.setattr(config_mod, "get_config", fake_config)

        from file_editing.writer import write_file_to_disk

        result = write_file_to_disk("src/hello.py", "print(1)\n")
        assert result["status"] == "success"
        assert (proj / "src" / "hello.py").read_text() == "print(1)\n"

    def test_traversal_rejected(self, monkeypatch, tmp_path):
        proj = tmp_path / "project"
        proj.mkdir()
        monkeypatch.setenv("PRIZMFORGE_DB_PATH", str(tmp_path / "t.db"))

        from core import config as config_mod

        original = config_mod.get_config

        def fake_config():
            cfg = dict(original())
            cfg["project_directory"] = str(proj)
            return cfg

        monkeypatch.setattr(config_mod, "get_config", fake_config)

        from file_editing.writer import write_file_to_disk

        result = write_file_to_disk("../../etc/passwd", "pwned\n")
        assert result["status"] == "error"
        assert "escape" in result["message"].lower()

    def test_absolute_outside_rejected(self, monkeypatch, tmp_path):
        proj = tmp_path / "project"
        proj.mkdir()
        outside = tmp_path / "outside.py"
        monkeypatch.setenv("PRIZMFORGE_DB_PATH", str(tmp_path / "t.db"))

        from core import config as config_mod

        original = config_mod.get_config

        def fake_config():
            cfg = dict(original())
            cfg["project_directory"] = str(proj)
            return cfg

        monkeypatch.setattr(config_mod, "get_config", fake_config)

        from file_editing.writer import write_file_to_disk

        result = write_file_to_disk(str(outside), "nope\n")
        assert result["status"] == "error"
        assert "escape" in result["message"].lower()


# ---------------------------------------------------------------------------
# Mode selection + fallback
# ---------------------------------------------------------------------------


class TestEditModeSelector:
    def test_small_file_prefers_full_replace(self):
        from workflow.edit_mode_selector import MODE_FULL_REPLACE, select_edit_mode

        d = select_edit_mode(file_line_count=40, instructions="rewrite helper")
        assert d.selected_mode == MODE_FULL_REPLACE

    def test_rename_prefers_find_replace(self):
        from workflow.edit_mode_selector import MODE_FIND_REPLACE, select_edit_mode

        d = select_edit_mode(file_line_count=400, instructions="rename old_name to new_name")
        assert d.selected_mode == MODE_FIND_REPLACE

    def test_large_prefers_guid(self):
        from workflow.edit_mode_selector import MODE_GUID, select_edit_mode

        d = select_edit_mode(
            file_line_count=900,
            instructions="refactor the architecture across modules",
        )
        assert d.selected_mode == MODE_GUID

    def test_fallback_chain_order(self):
        from workflow.edit_mode_selector import next_fallback_mode

        mode = "guid"
        tried = []
        while mode:
            tried.append(mode)
            mode = next_fallback_mode(mode, already_tried=tried)
        assert tried == ["guid", "diff", "find_replace", "full_replace"]

    def test_validator_detects_empty_ops(self):
        from core.edit_response_validator import EditFailureReason, validate_developer_edit_response

        r = validate_developer_edit_response('{"target_file_path":"a.py","summary":"x","operations":[],"rationale":"enough text"}')
        assert not r.is_valid
        assert r.reason == EditFailureReason.EMPTY_OPERATIONS

    def test_validator_detects_find_replace(self):
        from core.edit_response_validator import validate_developer_edit_response

        r = validate_developer_edit_response('{"target_file_path":"a.py","find":"old","replace":"new"}')
        assert r.is_valid
        assert r.detected_mode == "find_replace"


# ---------------------------------------------------------------------------
# Hash conflict + missing GUID (governed apply path)
# ---------------------------------------------------------------------------


@pytest.fixture
def governed_db(monkeypatch, tmp_path):
    db_path = tmp_path / "gov.db"
    monkeypatch.setenv("PRIZMFORGE_DB_PATH", str(db_path))
    from core.db import init_db

    init_db()
    return db_path


class TestConcurrencyAndGuids:
    def test_hash_mismatch_returns_conflicted(self, governed_db):
        from file_editing.db import get_db_connection
        from file_editing.editing import apply_edit_proposal
        from file_editing.writer import initialize_file_lines
        from workflow.proposal_builder import create_proposal_from_developer_output

        initialize_file_lines("demo/sample.py", "def hello():\n    print('world')\n")

        # Capture the real GUID for line 2
        with get_db_connection() as conn:
            rows = conn.execute("SELECT line_guid, content FROM file_lines WHERE is_deleted=0 ORDER BY sort_order").fetchall()
            guids = [r[0] for r in rows]
            assert len(guids) >= 2
            target_guid = guids[1]

        payload = {
            "target_file_path": "demo/sample.py",
            "summary": "Update print statement",
            "rationale": "Change the printed message for clarity",
            "operations": [
                {
                    "type": "replace_block",
                    "start_line_guid": target_guid,
                    "new_content": ["    print('updated')"],
                    "rationale": "Replace print line",
                }
            ],
        }
        prop = create_proposal_from_developer_output(payload, 1, "demo/sample.py")
        assert prop["status"] == "success"
        pid = prop["proposal_id"]

        # Corrupt the hash to simulate concurrent edit
        with get_db_connection() as conn:
            conn.execute(
                "UPDATE file_lines SET content_hash = 'deadbeef' WHERE line_guid = ?",
                (target_guid,),
            )
            conn.execute(
                "UPDATE edit_proposals SET status = 'approved' WHERE proposal_id = ?",
                (pid,),
            )

        result = apply_edit_proposal(pid)
        assert result["status"] == "conflicted"

    def test_missing_guid_returns_conflicted(self, governed_db):
        from file_editing.db import get_db_connection
        from file_editing.editing import apply_edit_proposal
        from file_editing.writer import initialize_file_lines
        from workflow.proposal_builder import create_proposal_from_developer_output

        initialize_file_lines("demo/g.py", "x = 1\ny = 2\n")

        payload = {
            "target_file_path": "demo/g.py",
            "summary": "Replace missing guid",
            "rationale": "Attempt to edit a non-existent line guid",
            "operations": [
                {
                    "type": "replace_block",
                    "start_line_guid": "guid-does-not-exist",
                    "new_content": ["z = 3"],
                    "rationale": "Replace nonexistent line",
                }
            ],
        }
        prop = create_proposal_from_developer_output(payload, 1, "demo/g.py")
        assert prop["status"] == "success"
        pid = prop["proposal_id"]

        with get_db_connection() as conn:
            conn.execute(
                "UPDATE edit_proposals SET status = 'approved' WHERE proposal_id = ?",
                (pid,),
            )

        result = apply_edit_proposal(pid)
        assert result["status"] == "conflicted"

    def test_find_replace_still_works(self, governed_db):
        from file_editing.db import get_db_connection, reconstruct_file_content
        from file_editing.editing import apply_edit_proposal
        from file_editing.writer import initialize_file_lines
        from workflow.proposal_builder import create_proposal_from_developer_output

        initialize_file_lines("demo/r.py", "a = old\nb = old\n")
        payload = {
            "target_file_path": "demo/r.py",
            "summary": "Rename old to new",
            "rationale": "Consistent naming across the module",
            "operations": [
                {
                    "type": "find_replace",
                    "find": "old",
                    "replace": "new",
                    "rationale": "Rename identifier",
                }
            ],
        }
        prop = create_proposal_from_developer_output(
            payload,
            1,
            "demo/r.py",
            selected_mode="guid",
            fallback_used=True,
            final_mode="find_replace",
        )
        assert prop["status"] == "success"
        assert prop["fallback_used"] is True
        pid = prop["proposal_id"]

        with get_db_connection() as conn:
            conn.execute(
                "UPDATE edit_proposals SET status = 'approved' WHERE proposal_id = ?",
                (pid,),
            )

        result = apply_edit_proposal(pid)
        assert result["status"] == "success"

        with get_db_connection() as conn:
            fid = conn.execute("SELECT file_id FROM files WHERE file_path='demo/r.py'").fetchone()[0]
            content = reconstruct_file_content(conn, fid)
        assert content == "a = new\nb = new\n"


class TestRepoRootContainment:
    def test_get_repo_root_returns_path(self):
        from core.config import get_repo_root

        root = get_repo_root()
        assert root.is_absolute()

    def test_ensure_project_directory_under_repo(self, tmp_path, monkeypatch):
        from core import config as config_mod

        # Use a subdir of real repo root via monkeypatch of get_repo_root
        fake_repo = tmp_path / "repo"
        fake_repo.mkdir()
        (fake_repo / "config.json").write_text("{}")
        proj = fake_repo / "project_data"
        monkeypatch.setattr(config_mod, "get_repo_root", lambda: fake_repo.resolve())
        path = config_mod.ensure_project_directory({"project_directory": str(proj)})
        assert path.exists()
        assert path.resolve().relative_to(fake_repo.resolve())

    def test_ensure_project_directory_rejects_escape(self, tmp_path, monkeypatch):
        import pytest

        from core import config as config_mod

        fake_repo = tmp_path / "repo"
        fake_repo.mkdir()
        outside = tmp_path / "outside"
        monkeypatch.setattr(config_mod, "get_repo_root", lambda: fake_repo.resolve())
        with pytest.raises(ValueError, match="repo root"):
            config_mod.ensure_project_directory({"project_directory": str(outside)})
