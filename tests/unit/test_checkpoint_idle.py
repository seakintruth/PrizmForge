"""CLI checkpoint persistence and unattended idle/checkpoint contracts."""

from __future__ import annotations

from datetime import datetime, timedelta

from core.cli_modes import CLIMode, CLIState, UnattendedConfig


def test_should_checkpoint_first_always_true():
    state = CLIState(mode=CLIMode.UNATTENDED, start_time=datetime.now())
    assert state.should_checkpoint(15) is True


def test_should_checkpoint_respects_interval():
    state = CLIState(mode=CLIMode.UNATTENDED, start_time=datetime.now())
    state.update_checkpoint()
    # Just checkpointed → not due yet
    assert state.should_checkpoint(60) is False
    # Backdate last checkpoint beyond interval
    state.last_checkpoint = datetime.now() - timedelta(minutes=61)
    assert state.should_checkpoint(60) is True


def test_save_and_load_checkpoint_roundtrip(temp_db):
    from interactive import load_checkpoint, save_checkpoint

    state = CLIState(
        mode=CLIMode.UNATTENDED,
        start_time=datetime.now(),
        task_counter=3,
        total_files_modified=7,
        total_iterations=12,
        current_task_id="task_003",
    )
    save_checkpoint(state)
    assert state.last_checkpoint is not None

    loaded = load_checkpoint()
    assert loaded is not None
    assert loaded.task_counter == 3
    assert loaded.total_files_modified == 7
    assert loaded.total_iterations == 12
    assert loaded.current_task_id == "task_003"
    assert loaded.mode == CLIMode.UNATTENDED


def test_unattended_counts_file_modifications_for_task(temp_db):
    """Mirror interactive.py's per-task files_changed query."""
    from core.db_connection import get_db_connection

    task_id = "task_idle_1"
    with get_db_connection() as conn:
        for path in ("a.py", "b.py", "a.py"):  # a.py twice → distinct = 2
            conn.execute(
                """
                INSERT INTO file_modifications
                (file_path, operation, task_id, timestamp)
                VALUES (?, 'materialize', ?, datetime('now'))
                """,
                (path, task_id),
            )

    with get_db_connection() as conn:
        files_changed = conn.execute(
            """
            SELECT COUNT(DISTINCT file_path)
            FROM file_modifications
            WHERE task_id = ?
            """,
            (task_id,),
        ).fetchone()[0]

    assert files_changed == 2

    state = CLIState(mode=CLIMode.UNATTENDED, start_time=datetime.now())
    state.total_files_modified += files_changed
    assert state.total_files_modified == 2


def test_min_idle_config_defaults_and_override():
    cfg = UnattendedConfig.from_config(
        {"cli_mode": {"unattended": {"min_idle_minutes": 30, "checkpoint_interval_minutes": 15}}}
    )
    assert cfg.min_idle_minutes == 30.0
    assert cfg.checkpoint_interval_minutes == 15
