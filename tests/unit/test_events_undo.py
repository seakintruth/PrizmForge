"""Phase D1/D2 — mutation events and proposal undo."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def test_publish_and_list_events(temp_db):
    from core.events import list_events, publish_event

    eid = publish_event(
        "proposal.created",
        source="test",
        task_id="t1",
        proposal_id="p1",
        payload={"a": 1},
    )
    assert eid is not None
    rows = list_events(task_id="t1")
    assert any(r["type"] == "proposal.created" for r in rows)


def test_undo_restores_content(temp_db):
    from file_editing.db import get_db_connection, reconstruct_file_content
    from file_editing.editing import apply_edit_proposal
    from file_editing.undo import snapshot_before_apply, undo_proposal
    from file_editing.writer import initialize_file_lines
    from workflow.proposal_builder import create_proposal_from_developer_output

    initialize_file_lines("undo/demo.py", "a = 1\n")
    prop = create_proposal_from_developer_output(
        {
            "target_file_path": "undo/demo.py",
            "summary": "change value",
            "rationale": "Modify constant for undo test case",
            "operations": [
                {
                    "type": "find_replace",
                    "find": "a = 1",
                    "replace": "a = 2",
                    "rationale": "bump",
                }
            ],
        },
        1,
        "undo/demo.py",
    )
    assert prop["status"] == "success"
    pid = prop["proposal_id"]
    with get_db_connection() as conn:
        conn.execute(
            "UPDATE edit_proposals SET status = 'approved' WHERE proposal_id = ?",
            (pid,),
        )
    snapshot_before_apply(pid)
    assert apply_edit_proposal(pid)["status"] == "success"
    with get_db_connection() as conn:
        fid = conn.execute("SELECT file_id FROM files WHERE file_path = ?", ("undo/demo.py",)).fetchone()[0]
        assert "a = 2" in reconstruct_file_content(conn, fid)
    und = undo_proposal(pid, write_disk=False)
    assert und["status"] == "success"
    with get_db_connection() as conn:
        fid = conn.execute("SELECT file_id FROM files WHERE file_path = ?", ("undo/demo.py",)).fetchone()[0]
        assert "a = 1" in reconstruct_file_content(conn, fid)


def test_undo_without_snapshot_errors(temp_db):
    from file_editing.undo import undo_proposal

    result = undo_proposal("nonexistent-proposal-id", write_disk=False)
    assert result["status"] == "error"
    assert "snapshot" in result["message"].lower() or "no snapshot" in result["message"].lower()


def test_proposal_created_emits_event(temp_db):
    from core.events import list_events
    from workflow.proposal_builder import create_proposal_from_developer_output

    prop = create_proposal_from_developer_output(
        {
            "target_file_path": "evt/new.py",
            "summary": "emit event on create",
            "rationale": "Verify proposal.created is published to event log",
            "operations": [
                {
                    "type": "create_file",
                    "target_file_path": "evt/new.py",
                    "initial_content": ["print(1)"],
                    "rationale": "bootstrap",
                }
            ],
        },
        1,
        "evt/new.py",
    )
    assert prop["status"] == "success"
    rows = list_events(event_type="proposal.created", limit=20)
    assert any(r.get("proposal_id") == prop["proposal_id"] for r in rows)


def test_create_file_then_materialize(temp_db, tmp_path, monkeypatch):
    """create_file apply + materialize writes under project dir."""
    from core import config as config_mod
    from file_editing.db import get_db_connection
    from file_editing.editing import apply_edit_proposal
    from file_editing.writer import materialize_proposal
    from workflow.proposal_builder import create_proposal_from_developer_output

    project_dir = tmp_path / "proj"
    project_dir.mkdir()

    def fake_config():
        return {
            "project_directory": str(project_dir),
            "background_agents_enabled": False,
            "git": False,
            "token_budget": {"max_tokens_per_4h": 1_000_000},
        }

    monkeypatch.setattr(config_mod, "get_config", fake_config)

    prop = create_proposal_from_developer_output(
        {
            "target_file_path": "pkg/hello.py",
            "summary": "create hello module",
            "rationale": "Materialize a brand new file via create_file op",
            "operations": [
                {
                    "type": "create_file",
                    "target_file_path": "pkg/hello.py",
                    "initial_content": ["def hi():", "    return 1"],
                    "rationale": "new module",
                }
            ],
        },
        1,
        "pkg/hello.py",
    )
    assert prop["status"] == "success"
    with get_db_connection() as conn:
        conn.execute(
            "UPDATE edit_proposals SET status = 'approved' WHERE proposal_id = ?",
            (prop["proposal_id"],),
        )
    assert apply_edit_proposal(prop["proposal_id"])["status"] == "success"
    mat = materialize_proposal(prop["proposal_id"])
    assert mat.get("status") == "success"
    disk = project_dir / "pkg" / "hello.py"
    assert disk.exists()
    assert "def hi" in disk.read_text(encoding="utf-8")
