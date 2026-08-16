# tests/integration/test_unattended_with_mock.py
import threading
import time
from pathlib import Path

import pytest

from main import main

# Runs main() in a thread against process globals; duration report 6.2s.
pytestmark = [pytest.mark.slow, pytest.mark.serial]


def test_unattended_run_with_mock_using_repo_root(tmp_path, mock_openai_chat, monkeypatch):
    # Ensure the test runs with repo root as cwd so main() finds config.json, api_key.json, agent_prompts.json
    repo_root = Path(__file__).resolve().parents[2]  # tests/integration -> tests -> repo root
    monkeypatch.chdir(repo_root)

    # Optionally create ExampleProject in repo root (main will auto-init if configured)
    example_dir = repo_root / "ExampleProject"
    example_dir.mkdir(exist_ok=True)

    # Provide a mocked LLM response
    mock_openai_chat(response_text='{"next_agent":"background","reasoning":"noop"}')

    # Start main() in background thread
    th = threading.Thread(target=main, daemon=True)
    th.start()

    # Let it run briefly then signal shutdown
    time.sleep(4)
    import interactive

    interactive._shutdown_requested = True

    th.join(timeout=10)
    assert not th.is_alive()
