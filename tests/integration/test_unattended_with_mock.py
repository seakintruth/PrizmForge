# tests/integration/test_unattended_with_mock.py
import threading
import time
from pathlib import Path

import pytest

from main import main

# Runs main() in a thread against process globals; measured ~9s.
pytestmark = [pytest.mark.slow, pytest.mark.serial]

# Headroom for main() to boot and honor a shutdown signal. Test-mode iterations
# are network-free, so this budget is defensive margin for slow CI.
_SHUTDOWN_BUDGET_SEC = 90


def test_unattended_run_with_mock_using_repo_root(monkeypatch):
    # Ensure the test runs with repo root as cwd so main() finds config.json,
    # api_key.json, agent_prompts.json (find_config_file walks up from cwd).
    repo_root = Path(__file__).resolve().parents[2]  # tests/integration -> tests -> repo root
    monkeypatch.chdir(repo_root)

    # PRIZMFORGE_TEST_MODE short-circuits call_agent to a scripted mock BEFORE
    # any endpoint/provider dispatch (agents.base.call_agent), so it works
    # regardless of the real config.json llm.test_mode flag or default provider.
    # The older requests.post mock never intercepted this dispatch path: the
    # real orchestrator call then failed and its retry+backoff loop kept the
    # thread alive past the shutdown window.
    monkeypatch.setenv("PRIZMFORGE_TEST_MODE", "1")

    # Start main() in a background thread. main's own get_config is patched by
    # conftest (isolated workspace), so runtime state never touches the real
    # config's project_directory; config-file discovery still uses the repo
    # root via find_config_file.
    th = threading.Thread(target=main, daemon=True)
    th.start()

    # Let it boot (config load + auto-init), then signal graceful shutdown.
    time.sleep(5)
    import interactive

    interactive._shutdown_requested = True

    # Poll for exit instead of a fixed join so slow init/checkpointing cannot
    # flake the assertion.
    deadline = time.monotonic() + _SHUTDOWN_BUDGET_SEC
    while th.is_alive() and time.monotonic() < deadline:
        time.sleep(0.5)
    assert not th.is_alive()
