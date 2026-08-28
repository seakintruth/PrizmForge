"""Workstream F: file_write_log.started_at / completed_at populated on materialize."""

from __future__ import annotations


def test_materialize_populates_file_write_log_timestamps(temp_db, tmp_path, monkeypatch):
    """A successful materialize records started_at and completed_at for every write."""
    import core.config as config_mod
    from core.db_connection import get_db_connection
    from file_editing.editing import apply_edit_proposal
    from file_editing.writer import initialize_file_lines, materialize_proposal
    from workflow.proposal_builder import create_proposal_from_developer_output

    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    rel = "app.py"
    (project_dir / rel).write_text("a=1\nb=2\n", encoding="utf-8")

    original_get_config = config_mod.get_config

    def _cfg():
        c = dict(original_get_config())
        c["project_directory"] = str(project_dir)
        return c

    config_mod.get_config = _cfg
    try:
        with get_db_connection() as conn:
            initialize_file_lines(rel, "a=1\nb=2\n", conn=conn)

        payload = {
            "target_file_path": rel,
            "summary": "bump constant to new value",
            "rationale": "test rationale for the constant bump",
            "operations": [
                {
                    "type": "find_replace",
                    "find": "a=1",
                    "replace": "a=42",
                    "rationale": "test rationale for the constant bump",
                }
            ],
        }
        prop = create_proposal_from_developer_output(
            payload,
            proposed_by_agent_id=1,
            target_file_path=rel,
            selected_mode="find_replace",
            fallback_used=False,
            final_mode="find_replace",
        )
        assert prop["status"] == "success"
        proposal_id = prop["proposal_id"]

        with get_db_connection() as conn:
            conn.execute("UPDATE edit_proposals SET status = 'approved' WHERE proposal_id = ?", (proposal_id,))

        apply_result = apply_edit_proposal(proposal_id)
        assert apply_result.get("status") == "success"

        mat = materialize_proposal(proposal_id)
        assert mat.get("status") == "success"

        with get_db_connection() as conn:
            rows = conn.execute(
                "SELECT status, started_at, completed_at FROM file_write_log WHERE proposal_id = ?",
                (proposal_id,),
            ).fetchall()
        assert rows, "expected at least one file_write_log row"
        for row in rows:
            assert row[0] == "success"
            assert row[1] is not None and str(row[1]) != "", f"started_at missing: {row}"
            assert row[2] is not None and str(row[2]) != "", f"completed_at missing: {row}"
            assert str(row[1]) <= str(row[2]), f"started_at after completed_at: {row}"
    finally:
        config_mod.get_config = original_get_config
