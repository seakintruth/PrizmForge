from typing import Optional

from typing import Dict, Optional

"""Configuration management"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

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


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
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

    with open(config_file, "r", encoding="utf-8") as f:
        config = json.load(f)

    # Normalize project_directory path
    if "project_directory" in config:
        config["project_directory"] = str(normalize_path(config["project_directory"]))

    # Load API keys from same directory as config
    config_dir = config_file.parent
    api_key_file = config_dir / "api_key.json"

    try:
        with open(api_key_file, "r", encoding="utf-8") as f:
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
            with open(alt_api_key, "r", encoding="utf-8") as f:
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

    validate_config(config)

    return config


def get_repo_root() -> Path:
    """
    Repository root for containment: directory that holds config.json
    (or CWD fallback when config has not been loaded yet).
    """
    try:
        return find_config_file("config.json").parent.resolve()
    except Exception:
        return Path.cwd().resolve()


def ensure_project_directory(config: Optional[Dict[str, Any]] = None) -> Path:
    """
    Resolve project_directory, ensure it exists (create if missing),
    and require it stays under repo root.
    """
    if config is None:
        config = get_config()
    raw = config.get("project_directory") or "./project"
    repo = get_repo_root()
    path = Path(str(raw)).expanduser()
    if not path.is_absolute():
        path = (repo / path).resolve()
    else:
        path = path.resolve()
    try:
        path.relative_to(repo)
    except ValueError:
        raise ValueError(f"project_directory must stay under repo root: {path} is outside {repo}")
    path.mkdir(parents=True, exist_ok=True)
    return path


def validate_config(config: Dict[str, Any]) -> None:
    """
    Lightweight schema validation for required settings.
    Raises ValueError with a clear message on failure.
    """
    errors = []

    # project_directory is required for path containment and must stay under repo root
    pd = config.get("project_directory")
    if not pd or not isinstance(pd, str):
        errors.append("project_directory is required and must be a non-empty string")
    else:
        try:
            repo = get_repo_root()
            path = Path(pd).expanduser()
            if not path.is_absolute():
                path = (repo / path).resolve()
            else:
                path = path.resolve()
            try:
                path.relative_to(repo)
            except ValueError:
                errors.append(f"project_directory {path} escapes repo root {repo}")
        except Exception as e:
            errors.append(f"project_directory could not be validated: {e}")

    # file_editing section: accept legacy method or new multi-mode keys
    fe = config.get("file_editing")
    if fe is not None and not isinstance(fe, dict):
        errors.append("file_editing must be an object/dict when present")
    elif isinstance(fe, dict):
        method = fe.get("method")
        preferred = fe.get("preferred_modes")
        fallback = fe.get("fallback_order")
        known = {
            "guid",
            "guid_sloc",
            "find_replace",
            "full_replace",
            "diff",
            "planned_diff",
        }
        if method is not None and method not in known:
            errors.append(f"file_editing.method {method!r} is not recognized; expected one of {sorted(known)}")
        if preferred is not None:
            if not isinstance(preferred, list) or not preferred:
                errors.append("file_editing.preferred_modes must be a non-empty list when present")
            else:
                bad = [m for m in preferred if m not in known]
                if bad:
                    errors.append(f"file_editing.preferred_modes has unknown modes: {bad}")
        if fallback is not None:
            if not isinstance(fallback, list) or not fallback:
                errors.append("file_editing.fallback_order must be a non-empty list when present")
            else:
                bad = [m for m in fallback if m not in known]
                if bad:
                    errors.append(f"file_editing.fallback_order has unknown modes: {bad}")
        threshold = fe.get("small_file_threshold_lines")
        if threshold is not None and (not isinstance(threshold, int) or threshold < 1):
            errors.append("file_editing.small_file_threshold_lines must be a positive integer")

    cs = config.get("content_safety")
    if cs is not None:
        if not isinstance(cs, dict):
            errors.append("content_safety must be an object/dict when present")
        else:
            if "disallow_binary_content" in cs and not isinstance(cs["disallow_binary_content"], bool):
                errors.append("content_safety.disallow_binary_content must be a boolean")
            be = cs.get("blocked_extensions")
            if be is not None:
                if not isinstance(be, list) or not all(isinstance(x, str) for x in be):
                    errors.append("content_safety.blocked_extensions must be a list of strings")

    if errors:
        raise ValueError("config.json validation failed:\n  - " + "\n  - ".join(errors))


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

    with open(prompts_file, "r", encoding="utf-8") as f:
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
