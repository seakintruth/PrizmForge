"""
Unattended preflight checks (config-only runs).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple


def preflight_unattended(config: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Returns (ok, errors).
    Does not prompt. Test mode skips API key requirements.
    """
    errors: List[str] = []
    from core.cli_modes import get_cli_mode_from_config, CLIMode
    from core.llm_test_mode import test_mode_enabled

    mode = get_cli_mode_from_config(config)
    if mode != CLIMode.UNATTENDED:
        # Not an error for other modes; caller decides
        return True, []

    # project directory
    pd = config.get("project_directory") or "./project"
    try:
        from core.config import find_config_file

        base = find_config_file("config.json").parent
    except Exception:
        base = Path.cwd()
    project_dir = Path(pd).expanduser()
    if not project_dir.is_absolute():
        project_dir = (base / project_dir).resolve()
    try:
        project_dir.mkdir(parents=True, exist_ok=True)
        test = project_dir / ".prizmforge_write_test"
        test.write_text("ok", encoding="utf-8")
        test.unlink()
    except Exception as e:
        errors.append(f"project_directory not writable: {project_dir} ({e})")

    if not test_mode_enabled(config):
        endpoints = config.get("endpoints") or {}
        valid = 0
        for name, ep in endpoints.items():
            if not isinstance(ep, dict):
                continue
            key_name = ep.get("api_key_name", "api_key")
            # keys may live in api_key.json merged into config or separate
            val = config.get(key_name) or ""
            if not val:
                try:
                    import json
                    from core.config import find_config_file

                    key_file = find_config_file("api_key.json")
                    keys = json.loads(key_file.read_text(encoding="utf-8"))
                    val = keys.get(key_name, "")
                except Exception:
                    val = ""
            if val and "YOUR_" not in str(val).upper():
                valid += 1
        if valid == 0 and endpoints:
            errors.append(
                "No valid API keys for configured endpoints "
                "(set keys or enable llm.test_mode / PRIZMFORGE_TEST_MODE=1)"
            )

    ok = len(errors) == 0
    return ok, errors
