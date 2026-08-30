"""Configuration management"""

import json
import os
import threading
from pathlib import Path
from typing import Any

_config_cache = None
_prompts_cache = None
_config_load_lock = threading.Lock()


def get_package_root() -> Path:
    """PrizmForge repository root: the directory that contains the ``core`` package."""
    return Path(__file__).resolve().parent.parent


def normalize_path(path_str: str, base: Path | None = None) -> Path:
    """
    Normalize a path string to a Path object, handling:
    - Absolute paths (Windows and Unix)
    - Relative paths
    - Forward and backslashes
    - User home expansion (~)

    Relative paths resolve against ``base`` when given, otherwise against
    the PrizmForge package root — never against the process cwd.
    """
    if not path_str:
        return Path(".")

    path_str = os.path.expanduser(path_str)
    path = Path(path_str)

    if path.is_absolute():
        return path.resolve()

    anchor = Path(base) if base is not None else get_package_root()
    return (anchor / path).resolve()


def find_config_file(filename: str) -> Path:
    """
    Find config file by searching:
    1. Current working directory
    2. Parent directory (one level up)
    3. PrizmForge package root (parent of core/)
    4. Package root's parent
    """
    cwd_path = Path.cwd() / filename
    if cwd_path.exists():
        return cwd_path

    parent_path = Path.cwd().parent / filename
    if parent_path.exists():
        return parent_path

    script_dir = get_package_root()
    script_path = script_dir / filename
    if script_path.exists():
        return script_path

    script_parent = script_dir.parent / filename
    if script_parent.exists():
        return script_parent

    return script_dir / filename


def _load_api_keys(config_dir: Path) -> dict[str, Any]:
    """Load structured API keys (``{"keys": {...}}``) from a config directory.

    Returns {} when api_key.json is absent; raises ValueError when the file
    exists but lacks the structured ``keys`` mapping.
    """
    api_key_file = config_dir / "api_key.json"
    if not api_key_file.exists():
        return {}
    with open(api_key_file, encoding="utf-8") as f:
        api_data = json.load(f)
    structured = api_data.get("keys")
    if not isinstance(structured, dict):
        raise ValueError('api_key.json must use the structured form: {"keys": {"<endpoint_name>": {"api_key": "..."}}}. See example_api_key.json.')
    return structured


def load_config(config_path: str | None = None) -> dict[str, Any]:
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
            f"  - {get_package_root() / 'config.json'}\n"
            f"\nPlease create config.json in the root directory."
        )

    with open(config_file, encoding="utf-8") as f:
        config = json.load(f)

    config_dir = config_file.parent.resolve()

    # Relative project_directory is anchored to the config file, not cwd.
    if "project_directory" in config:
        config["project_directory"] = str(normalize_path(config["project_directory"], base=config_dir))

    # API keys: prefer <config_dir>/api_key.json, then a discoverable copy,
    # else none.
    api_key_file = config_dir / "api_key.json"
    if api_key_file.exists():
        config["_api_keys"] = _load_api_keys(config_dir)
    else:
        alt_api_key = find_config_file("api_key.json")
        if alt_api_key.exists():
            config["_api_keys"] = _load_api_keys(alt_api_key.parent)
        else:
            config["_api_keys"] = {}

    config["_config_dir"] = str(config_dir)

    validate_config(config)

    return config


def get_repo_root() -> Path:
    """
    Repository root for containment: directory that holds config.json
    (or the package root when that file is missing).
    """
    found = find_config_file("config.json")
    if found.exists():
        return found.parent.resolve()
    return get_package_root()


def ensure_project_directory(config: dict[str, Any] | None = None) -> Path:
    """
    Resolve project_directory and ensure it exists (creates directory if missing).
    Allows target project_directory to be anywhere on disk (including outside the PrizmForge repository).
    """
    if config is None:
        config = get_config()
    raw = config.get("project_directory") or "./project"
    path = Path(str(raw)).expanduser()
    if not path.is_absolute():
        path = normalize_path(str(raw), base=get_repo_root())
    else:
        path = path.resolve()

    path.mkdir(parents=True, exist_ok=True)
    return path


def validate_config(config: dict[str, Any]) -> None:  # noqa: C901
    """
    Lightweight schema validation for required settings.
    Raises ValueError with a clear message on failure.
    """
    errors = []

    pd = config.get("project_directory")
    if not pd or not isinstance(pd, str):
        errors.append("project_directory is required and must be a non-empty string")
    else:
        try:
            path = Path(pd).expanduser()
            if not path.is_absolute():
                path = normalize_path(pd, base=get_repo_root())
            else:
                path = path.resolve()

            path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            errors.append(f"project_directory could not be validated: {e}")

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

    endpoints = config.get("endpoints")
    endpoint_names: set[str] = set()
    model_keys: set[str] = set()
    bare_model_names: dict[str, list[str]] = {}

    if endpoints is not None and not isinstance(endpoints, dict):
        errors.append("endpoints must be an object/dict mapping name → endpoint settings")
    elif isinstance(endpoints, dict):
        for ep_name, ep_cfg in endpoints.items():
            endpoint_names.add(ep_name)
            if not isinstance(ep_cfg, dict):
                errors.append(f"endpoints.{ep_name} must be an object")
                continue
            base_url = ep_cfg.get("base_url")
            if not base_url or not isinstance(base_url, str):
                errors.append(f"endpoints.{ep_name}.base_url is required (string)")
            priority = ep_cfg.get("priority", 50)
            if not isinstance(priority, int):
                errors.append(f"endpoints.{ep_name}.priority must be an integer")

            models = ep_cfg.get("models", {})
            if models is None:
                models = {}
            if not isinstance(models, dict):
                errors.append(f"endpoints.{ep_name}.models must be an object mapping model id → settings")
                continue
            for m_name, m_cfg in models.items():
                model_keys.add(f"{ep_name}/{m_name}")
                bare_model_names.setdefault(m_name, []).append(ep_name)
                if m_cfg is not None and not isinstance(m_cfg, dict):
                    errors.append(f"endpoints.{ep_name}.models.{m_name} must be an object when present")

        de = config.get("default_endpoint")
        if de and de not in endpoint_names:
            errors.append(f"default_endpoint '{de}' does not match any entry in endpoints ({sorted(endpoint_names)})")

        def _ref_ok(ref: str) -> bool:
            if "/" in ref:
                head, _rest = ref.split("/", 1)
                if head in endpoint_names:
                    return ref in model_keys
                return any(k.endswith(f"/{ref}") for k in model_keys)
            return len(bare_model_names.get(ref, [])) >= 1

        dm = config.get("default_model")
        if dm:
            dm_head = dm.split("/", 1)[0] if "/" in dm else None
            if not _ref_ok(dm):
                errors.append(f"default_model '{dm}' is not a known model. Known: {sorted(model_keys)[:20]}{'\u2026' if len(model_keys) > 20 else ''}")
            elif dm_head is None and len(bare_model_names[dm]) > 1:
                errors.append(
                    f"default_model '{dm}' is ambiguous — it exists on multiple endpoints ({bare_model_names[dm]}). Use the full 'endpoint/model' form."
                )

        prefs = config.get("agent_model_preferences") or {}
        if not isinstance(prefs, dict):
            errors.append("agent_model_preferences must be an object/dict when present")
        else:
            for agent, ref in prefs.items():
                if str(ref).startswith("_"):
                    continue
                if not _ref_ok(ref):
                    errors.append(f"agent_model_preferences.{agent}: unknown or ambiguous model reference '{ref}'")

        downgrades = ((config.get("resource_controller") or {}).get("model_downgrades")) or {}
        stack = [downgrades]
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                for _k, v in node.items():
                    stack.append(v)
            elif isinstance(node, str) and node:
                if not _ref_ok(node):
                    errors.append(f"resource_controller.model_downgrades: unknown model reference '{node}'")

    if errors:
        raise ValueError("config.json validation failed:\n  - " + "\n  - ".join(errors))


def load_agent_prompts() -> dict[str, Any]:
    """Load agent prompts from same directory as config"""
    prompts_file = find_config_file("agent_prompts.json")

    if not prompts_file.exists():
        raise FileNotFoundError(
            f"agent_prompts.json not found. Searched:\n"
            f"  - {Path.cwd() / 'agent_prompts.json'}\n"
            f"  - {Path.cwd().parent / 'agent_prompts.json'}\n"
            f"  - {get_package_root() / 'agent_prompts.json'}\n"
            f"\nPlease ensure agent_prompts.json is in the same directory as config.json"
        )

    with open(prompts_file, encoding="utf-8") as f:
        prompts = json.load(f)

    return prompts


def get_config() -> dict[str, Any]:
    """Get cached configuration"""
    global _config_cache
    if _config_cache is None:
        with _config_load_lock:
            if _config_cache is None:
                _config_cache = load_config()
    return _config_cache


def get_agent_prompts() -> dict[str, Any]:
    """Get cached agent prompts"""
    global _prompts_cache
    if _prompts_cache is None:
        with _config_load_lock:
            if _prompts_cache is None:
                _prompts_cache = load_agent_prompts()
    return _prompts_cache


def get_config_dir() -> Path:
    """Get directory where config files are located"""
    config = get_config()
    return Path(config.get("_config_dir", get_package_root()))


def reload_config():
    """Force reload configuration"""
    global _config_cache, _prompts_cache
    with _config_load_lock:
        _config_cache = load_config()
        _prompts_cache = load_agent_prompts()
