#!/usr/bin/env python3
"""
PrizmForge
Main entry point

IMPORTANT: Run this from the directory containing config.json
"""

import sys
from pathlib import Path

from core.cli_modes import CLIMode, UnattendedConfig, get_cli_mode_from_config
from core.config import find_config_file, get_agent_prompts, get_config
from core.db import init_db
from interactive import interactive_loop


def main():
    """Initialize and start system"""
    print("\n" + "=" * 60)
    print("🚀 PrizmForge")
    print("=" * 60)

    # Check for all required config files
    required_files = ["config.json", "api_key.json", "agent_prompts.json"]
    missing_files = []

    for filename in required_files:
        try:
            config_file = find_config_file(filename)
            if not config_file.exists():
                missing_files.append(filename)
        except:
            missing_files.append(filename)

    if missing_files:
        print("\n❌ ERROR: Missing configuration files:")
        for f in missing_files:
            print(f"  • {f}")
        print("\nPlease ensure all files exist in the same directory.")
        print("Run deploy_v3.py if you haven't already.\n")
        sys.exit(1)

    config_file = find_config_file("config.json")
    print(f"\n📁 Config directory: {config_file.parent}")

    # Load config
    try:
        config = get_config()
        prompts = get_agent_prompts()
        print(f"✅ Loaded {len(prompts)} agent prompts")
    except Exception as e:
        print(f"\n❌ ERROR loading config: {e}\n")
        sys.exit(1)

    # Get CLI mode from config
    mode = get_cli_mode_from_config(config)
    print(f"🎛️  CLI Mode: {mode.value.upper().replace('_', ' ')}")

    # Load unattended config if needed
    unattended_config = None
    if mode == CLIMode.UNATTENDED:
        unattended_config = UnattendedConfig.from_config(config)
        print(f"   Duration: {unattended_config.max_duration_hours}h")
        print(f"   Max iterations per task: {unattended_config.max_iterations_per_task}")
        print(f"   Checkpoint interval: {unattended_config.checkpoint_interval_minutes}m")

        from core.preflight import preflight_unattended

        ok, errs = preflight_unattended(config)
        if not ok:
            print("\n❌ Unattended preflight failed:")
            for e in errs:
                print(f"  • {e}")
            if getattr(unattended_config, "exit_on_preflight_failure", True):
                sys.exit(2)

    # Check API keys for configured endpoints
    endpoints_config = config.get("endpoints", {})
    missing_keys = []
    placeholder_keys = []
    valid_endpoints = []

    for endpoint_name, endpoint_config in endpoints_config.items():
        api_key_name = endpoint_config.get("api_key_name", "api_key")
        api_key_value = config.get(api_key_name, "")

        if not api_key_value:
            missing_keys.append(f"{endpoint_name} (needs '{api_key_name}')")
        elif "YOUR_" in api_key_value.upper():
            placeholder_keys.append(f"{endpoint_name} ('{api_key_name}' = placeholder)")
        else:
            valid_endpoints.append(endpoint_name)

    # test_mode / PRIZMFORGE_TEST_MODE: allow dry run without real keys
    from core.llm_test_mode import test_mode_enabled

    in_test_mode = test_mode_enabled(config)
    if in_test_mode:
        print("🧪 llm.test_mode active — API keys not required (mock LLM)")

    # Only error if NO valid endpoints exist (unless test mode)
    if not valid_endpoints and not in_test_mode:
        print("\n❌ ERROR: No valid API keys configured.")
        print("\nAt least one endpoint needs a valid API key.")

        if missing_keys:
            print("\nMissing keys:")
            for key in missing_keys:
                print(f"  • {key}")

        if placeholder_keys:
            print("\nPlaceholder keys detected:")
            for key in placeholder_keys:
                print(f"  • {key}")

        print("\nPlease edit api_key.json with actual API keys:")
        print("  Example api_key.json:")
        print("  {")
        for endpoint_name, endpoint_config in endpoints_config.items():
            api_key_name = endpoint_config.get("api_key_name", "api_key")
            print(f'    "{api_key_name}": "your-actual-key-here",')
        print("  }")
        print("\n🔑 Get your keys:")
        for ep_name, ep_config in endpoints_config.items():
            key_url = ep_config.get("key_management_url", "Contact system administrator")
            print(f"  • {ep_name.title()}: {key_url}")
        print()
        sys.exit(1)

    # Warnings for optional endpoints
    if missing_keys or placeholder_keys:
        print("\n⚠️  Warning: Some endpoints are not configured (fallback unavailable):")
        for key in missing_keys:
            print(f"  • {key}")
        for key in placeholder_keys:
            print(f"  • {key}")
        print(f"\n✅ Valid endpoints: {', '.join(valid_endpoints)}")
        print()
    else:
        print(f"✅ API keys configured for {len(endpoints_config)} endpoint(s)")

    print(f"✅ API keys configured for {len(endpoints_config)} endpoint(s)")

    # Initialize database
    init_db()

    do_auto_init = True
    if unattended_config is not None:
        do_auto_init = bool(getattr(unattended_config, "auto_init_on_start", True))
    if do_auto_init:
        print("\n🔄 Auto-indexing project files...")
        try:
            from cli.commands import cmd_init
            from utils.git_operations import ensure_git_initialized

            if config.get("git", False):
                git_available = ensure_git_initialized()
                if not git_available and config.get("git_auto_commit", False):
                    print("⚠️  Warning: git_auto_commit enabled but git unavailable")
                    print("   Changes will NOT be version controlled!")

            cmd_init()
        except Exception as e:
            print(f"⚠️  Auto-init failed (non-fatal): {e}")
            print("   Files will be indexed on first task")
    else:
        print("\n⏭️  Skipping auto-init (auto_init_on_start=false)")

    # Show resolved project directory
    project_dir = Path(config.get("project_directory", "./project"))
    project_dir.mkdir(parents=True, exist_ok=True)

    print(f"📁 Project directory: {project_dir.absolute()}")

    # Verify path is writable
    test_file = project_dir / ".test_write"
    try:
        test_file.touch()
        test_file.unlink()
        print("✅ Project directory is writable")
    except Exception as e:
        print(f"⚠️  Warning: Project directory may not be writable: {e}")

    print("\n✅ System initialized")
    print("=" * 60)

    # Start interactive loop with configured mode
    interactive_loop(mode=mode, unattended_config=unattended_config)


if __name__ == "__main__":
    main()
