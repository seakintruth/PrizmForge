"""Configuration management"""
import json
from pathlib import Path
from typing import Dict, Any
import os

_config_cache = None
_prompts_cache = None

def normalize_path(path_str: str) -> Path:
    """
    Normalize a path string to a Path object, handling:
    - Absolute paths (Windows and Unix)
    - Relative paths
    - Forward and backslashes
    - User home expansion (~)
    """
    if not path_str:
        return Path(".")
    
    # Expand user home directory
    path_str = os.path.expanduser(path_str)
    
    # Convert to Path object (handles forward/backslashes automatically)
    path = Path(path_str)
    
    # If absolute, use as-is
    if path.is_absolute():
        return path.resolve()
    
    # If relative, resolve relative to current working directory
    return path.resolve()

def find_config_file(filename: str) -> Path:
    """
    Find config file by searching:
    1. Current working directory
    2. Parent directory (one level up)
    3. Script's directory
    4. Script's parent directory
    """
    # Try current working directory
    cwd_path = Path.cwd() / filename
    if cwd_path.exists():
        return cwd_path
    
    # Try parent of current working directory
    parent_path = Path.cwd().parent / filename
    if parent_path.exists():
        return parent_path
    
    # Try script's directory (go up from core/ to root)
    script_dir = Path(__file__).parent.parent
    script_path = script_dir / filename
    if script_path.exists():
        return script_path
    
    # Try one level up from script
    script_parent = script_dir.parent / filename
    if script_parent.exists():
        return script_parent
    
    # Default to current directory
    return Path.cwd() / filename
def load_config(config_path: str = None) -> Dict[str, Any]:
    """Load configuration from JSON file"""
    if config_path is None:
        config_file = find_config_file("config.json")
    else:
        config_file = Path(config_path)
    
    if not config_file.exists():
        raise FileNotFoundError(
            f"config.json not found. Searched:\n"
            f"  - {Path.cwd() / 'config.json'}\n"
            f"  - {Path.cwd().parent / 'config.json'}\n"
            f"  - {Path(__file__).parent.parent / 'config.json'}\n"
            f"\nPlease create config.json in the root directory."
        )
    
    with open(config_file, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # Normalize project_directory path
    if "project_directory" in config:
        config["project_directory"] = str(normalize_path(config["project_directory"]))
    
    # Load API keys from same directory as config
    config_dir = config_file.parent
    api_key_file = config_dir / "api_key.json"
    
    try:
        with open(api_key_file, 'r', encoding='utf-8') as f:
            api_data = json.load(f)
            
            # Load ALL keys from api_key.json into config
            # This supports multiple endpoints with different keys
            for key_name, key_value in api_data.items():
                config[key_name] = key_value
            
            # Also set "api_key" for backward compatibility
            # (use first key found as default)
            if "api_key" not in config and api_data:
                config["api_key"] = list(api_data.values())[0]
                
    except FileNotFoundError:
        # Try alternate location
        alt_api_key = find_config_file("api_key.json")
        if alt_api_key.exists():
            with open(alt_api_key, 'r', encoding='utf-8') as f:
                api_data = json.load(f)
                
                # Load ALL keys
                for key_name, key_value in api_data.items():
                    config[key_name] = key_value
                
                # Set default "api_key"
                if "api_key" not in config and api_data:
                    config["api_key"] = list(api_data.values())[0]
        else:
            config["api_key"] = ""
    
    # Store config directory for reference
    config["_config_dir"] = str(config_dir)
    
    return config

def load_agent_prompts() -> Dict[str, Any]:
    """Load agent prompts from same directory as config"""
    prompts_file = find_config_file("agent_prompts.json")
    
    if not prompts_file.exists():
        raise FileNotFoundError(
            f"agent_prompts.json not found. Searched:\n"
            f"  - {Path.cwd() / 'agent_prompts.json'}\n"
            f"  - {Path.cwd().parent / 'agent_prompts.json'}\n"
            f"\nPlease ensure agent_prompts.json is in the same directory as config.json"
        )
    
    with open(prompts_file, 'r', encoding='utf-8') as f:
        prompts = json.load(f)
    
    return prompts

def get_config() -> Dict[str, Any]:
    """Get cached configuration"""
    global _config_cache
    if _config_cache is None:
        _config_cache = load_config()
    return _config_cache

def get_agent_prompts() -> Dict[str, Any]:
    """Get cached agent prompts"""
    global _prompts_cache
    if _prompts_cache is None:
        _prompts_cache = load_agent_prompts()
    return _prompts_cache

def get_config_dir() -> Path:
    """Get directory where config files are located"""
    config = get_config()
    return Path(config.get("_config_dir", Path.cwd()))

def reload_config():
    """Force reload configuration"""
    global _config_cache, _prompts_cache
    _config_cache = load_config()
    _prompts_cache = load_agent_prompts()