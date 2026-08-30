"""Operator helpers: list / fetch / assign models and edit agent prompts.

Does not talk to the live unattended loop. Fetch is the only network call
and is injectable so unit tests stay hermetic.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.config import find_config_file, get_package_root
from core.endpoint_manager import EndpointManager

#: Agents that should stay on the stronger model under budget pressure.
CRITICAL_AGENTS = (
    "orchestrator",
    "developer",
    "reviewer",
    "researcher",
    "prioritizer",
    "security_reviewer",
    "deployment_validator",
)

#: Agents that can drop to a cheaper / faster model.
CHEAP_AGENTS = (
    "jr_reviewer",
    "jr_researcher",
    "tech_writer",
    "file_manager",
    "archivist",
    "project_reporter",
    "resource_controller",
)

TIER_AGENTS: dict[str, tuple[str, ...]] = {
    "critical": CRITICAL_AGENTS,
    "cheap": CHEAP_AGENTS,
}

STUB_MODEL = {
    "max_output_tokens": 16384,
    "max_context_tokens": 128000,
    "temperature": 0.7,
    "description": "registered via models_cli",
}

Fetcher = Callable[[str, dict[str, str], dict[str, str] | None], tuple[int, Any]]


def models_url(base_url: str) -> str:
    """Derive the OpenAI-compatible GET /models URL from a chat completions base."""
    url = (base_url or "").rstrip("/")
    suffix = "/chat/completions"
    if url.endswith(suffix):
        return url[: -len(suffix)] + "/models"
    if url.endswith("/models"):
        return url
    return url + "/models"


def catalog_path(config: dict[str, Any] | None = None) -> Path:
    """Cache file: <config_dir or package root>/.PrizmForge/models_catalog.json."""
    raw = (config or {}).get("_config_dir")
    root = Path(raw) if raw else get_package_root()
    return root / ".PrizmForge" / "models_catalog.json"


def load_raw_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_raw_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def config_file_path(override: str | None = None) -> Path:
    if override:
        return Path(override).resolve()
    found = find_config_file("config.json")
    if not found.exists():
        raise FileNotFoundError(f"config.json not found at {found}")
    return found.resolve()


def prompts_file_path(config_path: Path) -> Path:
    sibling = config_path.parent / "agent_prompts.json"
    if sibling.exists():
        return sibling
    found = find_config_file("agent_prompts.json")
    return found


def parse_model_ids(payload: Any) -> list[str]:
    """Accept OpenAI {data:[{id:...}]} or a bare list of ids/objects."""
    ids: list[str] = []
    if isinstance(payload, dict):
        rows = payload.get("data") or payload.get("models") or []
    elif isinstance(payload, list):
        rows = payload
    else:
        rows = []
    for row in rows:
        if isinstance(row, str) and row:
            ids.append(row)
        elif isinstance(row, dict):
            mid = row.get("id") or row.get("name")
            if mid:
                ids.append(str(mid))
    seen: set[str] = set()
    out: list[str] = []
    for mid in ids:
        if mid not in seen:
            seen.add(mid)
            out.append(mid)
    return out


def list_registered(config: dict[str, Any]) -> list[str]:
    mgr = EndpointManager(config)
    return sorted(mgr.list_all_model_references())


def list_assignments(config: dict[str, Any]) -> dict[str, str]:
    prefs = config.get("agent_model_preferences") or {}
    return {k: v for k, v in prefs.items() if isinstance(v, str) and not str(k).startswith("_")}


def catalog_refs(catalog: dict[str, Any]) -> set[str]:
    refs: set[str] = set()
    for ep_name, entry in (catalog.get("endpoints") or {}).items():
        for mid in entry.get("models") or []:
            refs.add(f"{ep_name}/{mid}")
    return refs


def available_refs(config: dict[str, Any], catalog: dict[str, Any] | None = None) -> list[str]:
    """Registered endpoint/model refs first, then extras from the fetch cache."""
    regs = list_registered(config)
    extra = sorted(catalog_refs(catalog or {}) - set(regs))
    return regs + extra


def resolve_choice(raw: str, numbered: list[str]) -> str:
    """Map a typed answer to a model ref: index into `numbered`, or a literal ref."""
    text = raw.strip()
    if not text:
        raise ValueError("empty choice")
    if text.isdigit():
        idx = int(text)
        if 1 <= idx <= len(numbered):
            return numbered[idx - 1]
        raise ValueError(f"choice {idx} is out of range 1..{len(numbered) or 0}")
    return text


def _api_key(config: dict[str, Any], endpoint_name: str, ep_cfg: dict[str, Any]) -> str:
    keys = config.get("_api_keys") or {}
    entry = keys.get(endpoint_name) or {}
    if not isinstance(entry, dict):
        return ""
    custom = ep_cfg.get("api_key_name", "api_key")
    val = entry.get(custom) or entry.get("api_key") or ""
    return str(val)


def _default_fetcher(url: str, headers: dict[str, str], proxies: dict[str, str] | None) -> tuple[int, Any]:
    from core.http_client import get_json

    resp = get_json(url, headers=headers, timeout=25, proxies=proxies)
    try:
        data = resp.json()
    except Exception:
        data = resp.text
    return resp.status_code, data


def fetch_catalog(
    config: dict[str, Any],
    *,
    fetcher: Fetcher | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    """GET /models for each endpoint. Returns {fetched_at, endpoints: {name: {...}}}."""
    fetch = fetcher or _default_fetcher
    proxy = config.get("proxy") if isinstance(config.get("proxy"), dict) else None
    proxies = None
    if proxy:
        proxies = {k: v for k, v in proxy.items() if k in ("http", "https") and v}

    catalog: dict[str, Any] = {
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "endpoints": {},
    }
    for ep_name, ep_cfg in (config.get("endpoints") or {}).items():
        if not isinstance(ep_cfg, dict):
            continue
        base = ep_cfg.get("base_url") or ""
        url = models_url(str(base))
        key = _api_key(config, ep_name, ep_cfg)
        headers = {"Accept": "application/json"}
        if key and "YOUR_" not in key.upper():
            headers["Authorization"] = f"Bearer {key}"
        entry: dict[str, Any] = {"url": url, "ok": False, "models": [], "error": None}
        try:
            status, body = fetch(url, headers, proxies)
            if status == 200:
                ids = parse_model_ids(body)
                entry["ok"] = True
                entry["models"] = ids
            else:
                entry["error"] = f"HTTP {status}"
        except Exception as exc:
            entry["error"] = f"{type(exc).__name__}: {exc}"
        catalog["endpoints"][ep_name] = entry

    if persist:
        path = catalog_path(config)
        path.parent.mkdir(parents=True, exist_ok=True)
        save_raw_json(path, catalog)
    return catalog


def load_catalog(config: dict[str, Any]) -> dict[str, Any]:
    path = catalog_path(config)
    if not path.is_file():
        return {"fetched_at": None, "endpoints": {}}
    try:
        data = load_raw_json(path)
    except Exception:
        return {"fetched_at": None, "endpoints": {}}
    if not isinstance(data, dict):
        return {"fetched_at": None, "endpoints": {}}
    data.setdefault("endpoints", {})
    return data


def resolve_or_none(config: dict[str, Any], reference: str) -> str | None:
    if not reference:
        return None
    mgr = EndpointManager(config)
    if mgr.model_reference_exists(reference):
        key = mgr._resolve_key(reference)
        return key or reference
    return None


def ensure_registered(raw_config: dict[str, Any], reference: str) -> str:
    """If reference is endpoint/model, add a stub under endpoints.X.models. Return the full ref."""
    endpoints = raw_config.setdefault("endpoints", {})
    if not isinstance(endpoints, dict):
        raise ValueError("endpoints must be an object")
    if "/" not in reference:
        raise ValueError(f"Cannot register bare id '{reference}' — use endpoint/model")
    head, rest = reference.split("/", 1)
    if head not in endpoints:
        raise ValueError(f"Unknown endpoint '{head}'. Known: {sorted(endpoints)}")
    ep_cfg = endpoints[head]
    if not isinstance(ep_cfg, dict):
        raise ValueError(f"endpoints.{head} must be an object")
    models = ep_cfg.setdefault("models", {})
    if not isinstance(models, dict):
        raise ValueError(f"endpoints.{head}.models must be an object")
    if rest not in models:
        models[rest] = dict(STUB_MODEL)
    return f"{head}/{rest}"


def assign_agents(
    raw_config: dict[str, Any],
    agents: list[str],
    reference: str,
    *,
    register: bool = False,
    also_default: bool = False,
    catalog: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Patch agent_model_preferences (and optional default_model). Mutates raw_config."""
    resolved = resolve_or_none(raw_config, reference)
    if resolved is None:
        in_catalog = reference in catalog_refs(catalog or {})
        if register and "/" in reference:
            if catalog is not None and not in_catalog:
                raise ValueError(f"'{reference}' is not in the last fetch cache. Run `models fetch` or pass a registered endpoint/model.")
            resolved = ensure_registered(raw_config, reference)
        elif in_catalog:
            raise ValueError(f"'{reference}' is in the fetch cache but not in config. Re-run with --register to add a stub under endpoints.*.models.")
        else:
            known = list_registered(raw_config)
            raise ValueError(f"Unknown model '{reference}'. Registered: {known[:12]}{'\u2026' if len(known) > 12 else ''}")

    prefs = raw_config.setdefault("agent_model_preferences", {})
    if not isinstance(prefs, dict):
        raise ValueError("agent_model_preferences must be an object")
    for agent in agents:
        name = agent.strip()
        if not name or name.startswith("_"):
            continue
        prefs[name] = resolved
    if also_default:
        raw_config["default_model"] = resolved
    return raw_config


def assign_tier(
    raw_config: dict[str, Any],
    tier: str,
    reference: str,
    **kwargs: Any,
) -> dict[str, Any]:
    key = tier.strip().lower()
    agents = TIER_AGENTS.get(key)
    if agents is None:
        raise ValueError(f"Unknown tier '{tier}'. Use: {', '.join(sorted(TIER_AGENTS))}")
    return assign_agents(raw_config, list(agents), reference, **kwargs)


def validate_assignments(
    config: dict[str, Any],
    prompts: dict[str, Any] | None = None,
) -> list[str]:
    """Return problem strings (empty = ok). Does not raise."""
    problems: list[str] = []
    mgr = EndpointManager(config)
    for agent, ref in list_assignments(config).items():
        if not mgr.model_reference_exists(ref):
            problems.append(f"agent_model_preferences.{agent}: unknown model '{ref}'")
    dm = config.get("default_model")
    if dm and not mgr.model_reference_exists(str(dm)):
        problems.append(f"default_model: unknown model '{dm}'")

    def _walk(node: Any, path: str) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                if str(k).startswith("_"):
                    continue
                _walk(v, f"{path}.{k}")
        elif isinstance(node, str) and node:
            if not mgr.model_reference_exists(node):
                problems.append(f"{path}: unknown model '{node}'")

    _walk((config.get("resource_controller") or {}).get("model_downgrades") or {}, "model_downgrades")

    if prompts is not None:
        pref_agents = set(list_assignments(config))
        prompt_agents = {k for k in prompts if not str(k).startswith("_")}
        missing = sorted(pref_agents - prompt_agents)
        for name in missing:
            problems.append(f"agent_prompts.json missing entry for '{name}'")
    return problems


def prompt_text(prompts: dict[str, Any], agent: str) -> str:
    entry = prompts.get(agent)
    if entry is None:
        raise KeyError(f"No prompt for '{agent}'. Known: {sorted(k for k in prompts if not str(k).startswith('_'))}")
    if isinstance(entry, str):
        return entry
    if isinstance(entry, dict):
        text = entry.get("system_prompt")
        if isinstance(text, str):
            return text
        raise KeyError(f"agent '{agent}' has no system_prompt field")
    raise KeyError(f"agent '{agent}' prompt is not a string or object")


def set_prompt_text(prompts: dict[str, Any], agent: str, text: str) -> dict[str, Any]:
    entry = prompts.get(agent)
    if isinstance(entry, dict):
        entry["system_prompt"] = text
    else:
        prompts[agent] = {"role": agent, "system_prompt": text}
    return prompts
