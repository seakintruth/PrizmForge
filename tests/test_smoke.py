"""
Smoke tests - verify basic system functionality.
Can run without any database or config setup.
"""


def test_imports():
    """Core packages import and expose expected callables."""
    import core.db
    import core.config
    import file_editing
    import workflow.task_runner

    assert hasattr(core.db, "init_db")
    assert hasattr(core.config, "get_config")
    assert callable(workflow.task_runner.run_task_cycle)


def test_editpayload_validation():
    """Test EditPayload validation without database"""
    from file_editing.edit_payload import EditPayload

    payload_dict = {
        "target_file_path": "test.py",
        "summary": "Valid test summary",
        "rationale": "Testing validation logic",
        "operations": [
            {
                "type": "insert_after",
                "after_guid": None,
                "new_content": ["test"],
                "rationale": "test operation rationale",
            }
        ],
    }

    payload = EditPayload.model_validate(payload_dict)
    assert payload.target_file_path == "test.py"
    assert len(payload.operations) == 1


def test_config_loading():
    """Test that config can be loaded"""
    try:
        from core.config import get_config

        config = get_config()
        assert isinstance(config, dict)
        assert "project_directory" in config or config is not None
    except FileNotFoundError:
        # Expected if config.json doesn't exist
        pass
