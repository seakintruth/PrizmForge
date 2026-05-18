#!/usr/bin/env python3
"""
PrizmForge
Main entry point

IMPORTANT: Run this from the directory containing config.json
"""

import sys
from pathlib import Path
from core.config import get_config, get_agent_prompts, find_config_file
from core.db import init_db
from interactive import interactive_loop
from core.cli_modes import get_cli_mode_from_config, UnattendedConfig, CLIMode

def main():
    """Initialize and start system"""
    print("\n" + "="*60)
    print("🚀 PrizmForge")
    print("="*60)
    
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
        print(f"\n❌ ERROR: Missing configuration files:")
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
    
    # Check API keys for configured endpoints
    endpoints_config = config.get("endpoints", {})
    missing_keys = []
    placeholder_keys = []
    
    for endpoint_name, endpoint_config in endpoints_config.items():
        api_key_name = endpoint_config.get("api_key_name", "api_key")
        api_key_value = config.get(api_key_name, "")
        
        if not api_key_value:
            missing_keys.append(f"{endpoint_name} (needs '{api_key_name}')")
        elif "YOUR_" in api_key_value.upper():
            placeholder_keys.append(f"{endpoint_name} ('{api_key_name}' = placeholder)")
    
    if missing_keys:
        print(f"\n❌ ERROR: Missing API keys:")
        for key in missing_keys:
            print(f"  • {key}")
        print("\nPlease edit api_key.json with your keys\n")
        sys.exit(1)
    
    if placeholder_keys:
        print(f"\n❌ ERROR: Placeholder API keys detected:")
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

    
    print(f"✅ API keys configured for {len(endpoints_config)} endpoint(s)")

    # Initialize database
    init_db()

    print("\n🔄 Auto-indexing project files...")
    try:
        from cli.commands import cmd_init
        from utils.git_operations import ensure_git_initialized
        
        # Ensure git is initialized
        if config.get("git", False):
            git_available = ensure_git_initialized()
            if not git_available and config.get("git_auto_commit", False):
                print("⚠️  Warning: git_auto_commit enabled but git unavailable")
                print("   Changes will NOT be version controlled!")
        
        cmd_init()
    except Exception as e:
        print(f"⚠️  Auto-init failed (non-fatal): {e}")
        print("   Files will be indexed on first task")

    # Show resolved project directory
    project_dir = Path(config.get("project_directory", "./project"))
    project_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"📁 Project directory: {project_dir.absolute()}")
    
    # Verify path is writable
    test_file = project_dir / ".test_write"
    try:
        test_file.touch()
        test_file.unlink()
        print(f"✅ Project directory is writable")
    except Exception as e:
        print(f"⚠️  Warning: Project directory may not be writable: {e}")
    
    print("\n✅ System initialized")
    print("="*60)
    
    # Start interactive loop with configured mode
    interactive_loop(mode=mode, unattended_config=unattended_config)

if __name__ == "__main__":
    main()