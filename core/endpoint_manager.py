"""Multi-endpoint manager for different API providers"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from core.db_connection import get_db_connection

logger = logging.getLogger(__name__)


class EndpointStatus(Enum):
    """Endpoint status values"""

    HEALTHY = "healthy"
    RATE_LIMITED = "rate_limited"
    TOKEN_EXHAUSTED = "token_exhausted"
    KEY_LOCKED = "key_locked"
    SERVER_ERROR = "server_error"
    UNAVAILABLE = "unavailable"


class EndpointConfig:
    """Configuration for a specific endpoint"""

    def __init__(self, name: str, config: dict[str, Any]):
        self.name = name
        self.base_url = config.get("base_url")
        self.api_key_name = config.get("api_key_name", "api_key")
        self.include_model_in_payload = config.get("include_model_in_payload", True)
        self.response_path = config.get("response_path", ["choices", 0, "message", "content"])
        self.key_management_url = config.get("key_management_url", "")
        self.description = config.get("description", "")
        self.priority = config.get("priority", 50)
        self.rate_limit_per_minute = config.get("rate_limit_per_minute", 118)

        self.health = EndpointHealth(endpoint_name=name)

    def extract_response(self, data: dict) -> str:
        """Extract response text using configured path"""
        result = data
        try:
            for key in self.response_path:
                if isinstance(result, list) and isinstance(key, int):
                    result = result[key]
                elif isinstance(result, dict):
                    result = result.get(key)
                else:
                    result = result.get(key) if hasattr(result, "get") else result
            return str(result) if result is not None else ""
        except Exception:
            return ""


class EndpointHealth:
    """Track health status of an endpoint"""

    def __init__(self, endpoint_name: str | None = None):
        self.endpoint_name = endpoint_name
        self.status = EndpointStatus.HEALTHY
        self.last_error = None
        self.error_count = 0
        self.last_success = datetime.now()
        self.unavailable_until = None
        self.consecutive_failures = 0

        if endpoint_name:
            self._load_from_db()

    def _load_from_db(self):
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT status, error_count, consecutive_failures,
                           last_success, unavailable_until
                    FROM endpoint_health
                    WHERE endpoint_name = ?
                    """,
                    (self.endpoint_name,),
                )
                row = cursor.fetchone()
                if row:
                    self.status = EndpointStatus(row[0])
                    self.error_count = row[1]
                    self.consecutive_failures = row[2]
                    if row[3]:
                        self.last_success = datetime.fromisoformat(row[3])
                    if row[4]:
                        self.unavailable_until = datetime.fromisoformat(row[4])
        except Exception as e:
            logger.warning(f"Failed to load endpoint health from DB: {e}")

    def _save_to_db(self):
        if not self.endpoint_name:
            return
        try:
            with get_db_connection() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO endpoint_health
                    (endpoint_name, status, error_count, consecutive_failures,
                     last_success, unavailable_until, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        self.endpoint_name,
                        self.status.value,
                        self.error_count,
                        self.consecutive_failures,
                        self.last_success.isoformat() if self.last_success else None,
                        self.unavailable_until.isoformat() if self.unavailable_until else None,
                        datetime.now().isoformat(),
                    ),
                )
        except Exception as e:
            logger.warning(f"Failed to save endpoint health to DB: {e}")

    def is_available(self) -> bool:
        if self.unavailable_until is None:
            return True
        return datetime.now() >= self.unavailable_until

    def time_until_available(self) -> int:
        if self.unavailable_until is None:
            return 0
        remaining = (self.unavailable_until - datetime.now()).total_seconds()
        return max(0, int(remaining))

    def mark_success(self):
        self.status = EndpointStatus.HEALTHY
        self.error_count = 0
        self.consecutive_failures = 0
        self.last_success = datetime.now()
        self.unavailable_until = None
        self._save_to_db()

    def mark_failure(self, status: EndpointStatus, cooldown_minutes: int | None = None):
        self.status = status
        self.last_error = datetime.now()
        self.error_count += 1
        self.consecutive_failures += 1

        if cooldown_minutes is None:
            if status == EndpointStatus.TOKEN_EXHAUSTED:
                cooldown_minutes = 15
            elif status == EndpointStatus.KEY_LOCKED:
                cooldown_minutes = 30
            elif status == EndpointStatus.RATE_LIMITED:
                cooldown_minutes = 2
            else:
                cooldown_minutes = 5

        self.unavailable_until = datetime.now() + timedelta(minutes=cooldown_minutes)
        self._save_to_db()


@dataclass
class AgentModelChoice:
    endpoint_name: str | None
    model_name: str | None


class EndpointManager:
    """Manage multiple API endpoints with support for duplicate model names across endpoints"""

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.endpoints: dict[str, EndpointConfig] = {}
        self.models: dict[str, dict] = {}  # "endpoint/model_name" -> {endpoint, config}
        self._model_to_endpoints: dict[str, list[str]] = {}  # model_name -> [endpoint_names]

        # Load endpoints
        for name, endpoint_config in config.get("endpoints", {}).items():
            self.endpoints[name] = EndpointConfig(name, endpoint_config)
            logger.info(f"Loaded endpoint: {name}")

        default_name = config.get("default_endpoint")
        self.default_endpoint = self.endpoints.get(default_name)

        if default_name and not self.default_endpoint:
            logger.warning(f"Default endpoint '{default_name}' not found in config")

        # Load models from nested structure (reference validation uses
        # default_endpoint, so this must come after it is set)
        self._load_models(config)

        # Validate references in other config sections
        self._validate_model_references()

    def _load_models(self, config: dict[str, Any]):
        """Load models defined under endpoints.<name>.models"""
        self.models.clear()
        self._model_to_endpoints.clear()

        for ep_name, ep_data in config.get("endpoints", {}).items():
            endpoint_obj = self.endpoints.get(ep_name)
            if not endpoint_obj:
                continue

            for model_name, model_config in ep_data.get("models", {}).items():
                key = f"{ep_name}/{model_name}"
                self.models[key] = {
                    "endpoint": endpoint_obj,
                    "config": model_config,
                }

                if model_name not in self._model_to_endpoints:
                    self._model_to_endpoints[model_name] = []
                self._model_to_endpoints[model_name].append(ep_name)

    def _validate_model_references(self):
        """Warn about unknown model references in agent preferences and nested downgrades"""
        prefs = self.config.get("agent_model_preferences", {})
        downgrades_section = self.config.get("resource_controller", {}).get("model_downgrades", {})

        def _walk(section_name: str, node):
            if isinstance(node, dict):
                for key, value in node.items():
                    if str(key).startswith("_"):
                        continue
                    _walk(section_name, value)
            elif isinstance(node, str) and node:
                if not self.model_reference_exists(node):
                    logger.warning(f"Unknown model reference '{node}' in {section_name}")

        _walk("agent_model_preferences", prefs)
        _walk("model_downgrades", downgrades_section)

    # =====================================================================
    # Public Model Resolution API
    # =====================================================================

    def _split_endpoint_prefix(self, reference: str) -> tuple[str | None, str]:
        """Split 'endpoint/model' ONLY when the first segment is a known endpoint.

        Model IDs may themselves contain slashes (e.g. 'stealth/ox-alpha'),
        so a reference like 'openrouter/stealth/ox-alpha' must resolve to
        ('openrouter', 'stealth/ox-alpha') — not ('openrouter', 'stealth') +
        leftover. When the first segment is NOT a known endpoint, the whole
        string is treated as a bare model ID.
        """
        if "/" in reference:
            head, rest = reference.split("/", 1)
            if head in self.endpoints:
                return head, rest
        return None, reference

    def _resolve_key(self, reference: str) -> str | None:
        """Resolve any model reference to its full 'endpoint/model' key."""
        if not reference:
            return None

        # Exact full key
        if reference in self.models:
            return reference

        # Known endpoint prefix: 'openrouter/stealth/ox-alpha'
        ep, mid = self._split_endpoint_prefix(reference)
        if ep and f"{ep}/{mid}" in self.models:
            return f"{ep}/{mid}"

        # Bare model ID (possibly containing slashes): prefer default endpoint
        if self.default_endpoint:
            default_key = f"{self.default_endpoint.name}/{reference}"
            if default_key in self.models:
                return default_key

        # Any endpoint hosting this exact model ID
        for key in self.models:
            if key.endswith(f"/{reference}"):
                return key

        return None

    def list_all_model_references(self) -> list[str]:
        """Returns all available models in 'endpoint/model' format."""
        return list(self.models.keys())

    def get_models_for_endpoint(self, endpoint_name: str) -> dict[str, dict]:
        """Returns all models under a specific endpoint."""
        result = {}
        for key, data in self.models.items():
            if key.startswith(f"{endpoint_name}/"):
                model_name = key.split("/", 1)[1]
                result[model_name] = data["config"]
        return result

    def model_reference_exists(self, reference: str) -> bool:
        """Check if a model reference exists (bare ID or 'endpoint/model')."""
        if not reference:
            return False
        return self._resolve_key(reference) is not None

    def get_endpoint_for_model(self, model_name: str | None = None) -> EndpointConfig | None:
        """
        Get endpoint for a model.
        Accepts bare model ID or full 'endpoint/model' reference.
        When a model exists on multiple endpoints, prefers the default_endpoint.
        """
        if not model_name:
            return self.default_endpoint

        key = self._resolve_key(model_name)
        if key:
            return self.models[key]["endpoint"]
        return self.default_endpoint

    def get_model_config(self, model_name: str, endpoint_name: str | None = None) -> dict[str, Any]:
        """Get model configuration. Accepts bare ID or full 'endpoint/model' ref."""
        if not model_name:
            return {}

        key = self._resolve_key(model_name)
        if endpoint_name:
            # Explicit endpoint scope wins over default-endpoint resolution.
            candidate = f"{endpoint_name}/{model_name}"
            if candidate in self.models:
                return self.models[candidate]["config"]
        if key:
            return self.models[key]["config"]
        return {}

    # =====================================================================
    # Agent Model Resolution
    # =====================================================================

    def resolve_agent_model(self, agent_name: str) -> AgentModelChoice:
        """Resolve which endpoint + model an agent should use."""
        prefs = self.config.get("agent_model_preferences", {})
        raw = prefs.get(agent_name)

        if not raw:
            return AgentModelChoice(
                endpoint_name=self.default_endpoint.name if self.default_endpoint else None,
                model_name=None,
            )

        return self.normalize_model_reference(raw)

    def normalize_model_reference(self, reference: str | None) -> AgentModelChoice:
        """
        Normalize any model reference (bare name or 'endpoint/model') into
        an AgentModelChoice. This is the single entry point for all call paths.
        """
        if not reference:
            return AgentModelChoice(
                endpoint_name=self.default_endpoint.name if self.default_endpoint else None,
                model_name=None,
            )

        return self._parse_model_reference(reference)

    def _parse_model_reference(self, reference: str) -> AgentModelChoice:
        """Parse 'endpoint/model' or plain 'model' format.

        The endpoint prefix is only recognized when it matches a known
        endpoint name — model IDs may themselves contain slashes.
        """
        if not reference:
            return AgentModelChoice(None, None)

        ep, mid = self._split_endpoint_prefix(reference)
        if ep and f"{ep}/{mid}" in self.models:
            return AgentModelChoice(ep, mid)

        # Bare model ID (possibly containing slashes) - resolve to an endpoint
        key = self._resolve_key(reference)
        if key and not ep:
            bare_id = key.split("/", 1)[1]
            return AgentModelChoice(self.models[key]["endpoint"].name, bare_id)
        if key and ep:
            return AgentModelChoice(ep, mid)

        return AgentModelChoice(ep, mid if ep else reference)

    # =====================================================================
    # Existing Methods (kept for compatibility)
    # =====================================================================

    def get_api_key(self, endpoint: EndpointConfig) -> str:
        api_key = self._lookup_structured_api_key(endpoint)
        if not api_key or "YOUR_" in str(api_key):
            raise ValueError(f"API key not configured for endpoint: {endpoint.name}")
        return api_key

    def _lookup_structured_api_key(self, endpoint: EndpointConfig) -> str | None:
        """Look up key under keys.<endpoint_name> in the loaded api key data.

        Resolution order within an endpoint entry:
          1. explicit field named by endpoint.api_key_name (if customized)
          2. default "api_key" field
        """
        structured = self.config.get("_api_keys") or {}
        entry = structured.get(endpoint.name)
        if not isinstance(entry, dict):
            return None
        value = None
        if endpoint.api_key_name and endpoint.api_key_name != "api_key":
            value = entry.get(endpoint.api_key_name)
        if not value:
            value = entry.get("api_key")
        return str(value) if value else None

    def build_payload(
        self,
        endpoint: EndpointConfig,
        model_name: str | None,
        messages: list[dict],
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> dict[str, Any]:

        # model_name may be a bare ID containing slashes ('stealth/ox-alpha')
        # or a full 'endpoint/model' ref; strip ONLY a known endpoint prefix.
        ep, mid = self._split_endpoint_prefix(model_name or "")
        if model_name:
            key = self._resolve_key(model_name)
            if key:
                # The registered model ID is everything after "endpoint/".
                bare = key.split("/", 1)[1]
            elif ep:
                bare = mid
            else:
                bare = model_name
        else:
            bare = None
        model_config = self.get_model_config(model_name) if model_name else {}

        payload = {
            "messages": messages,
            "max_tokens": max_tokens or model_config.get("max_output_tokens", 16384),
            "temperature": temperature if temperature is not None else model_config.get("temperature", 0.5),
        }

        if endpoint.include_model_in_payload and bare:
            payload["model"] = bare

        return payload

    def validate_model(self, model_name: str) -> str | None:
        """
        Validate a model reference and return the bare model ID suitable
        for API payloads. Accepts full 'endpoint/model' or bare name —
        model IDs may themselves contain slashes (e.g. 'stealth/ox-alpha').
        """
        if not model_name:
            return None

        key = self._resolve_key(model_name)
        if key:
            return key.split("/", 1)[1]

        available = list(self._model_to_endpoints.keys())
        if available:
            fallback = available[0]
            logger.warning(f"Model '{model_name}' not found. Using '{fallback}'")
            return fallback
        return None

    def get_fallback_model(self, current_endpoint: EndpointConfig) -> tuple[str, EndpointConfig] | None:
        fallback_settings = self.config.get("fallback_settings", {})
        if not fallback_settings.get("enabled", True):
            return None

        available = [ep for ep in self.get_available_endpoints() if ep.name != current_endpoint.name]
        if not available:
            return None

        # Gather every concrete candidate (model, endpoint) across the available
        # endpoints, then let the recency-weighted model-health tracker order
        # them: healthy models first, flaky/demoted ones last.
        candidates: list[tuple[str, EndpointConfig]] = []
        for ep in sorted(available, key=lambda e: e.priority):
            for key in self.models:
                if key.startswith(f"{ep.name}/"):
                    candidates.append((key.split("/", 1)[1], ep))

        if not candidates:
            return None

        try:
            from core.model_health import rank_candidates

            pairs = [(f"{ep.name}/{m}", ep.priority or 0) for m, ep in candidates]
            ranked_refs = {ref: i for i, (ref, _p) in enumerate(rank_candidates(pairs))}
            candidates.sort(key=lambda c: ranked_refs.get(f"{c[1].name}/{c[0]}", len(ranked_refs)))
        except Exception as e:
            logger.debug(f"model-health ranking unavailable ({e}); using static priority")

        model_name, fallback_endpoint = candidates[0]
        return model_name, fallback_endpoint

    def get_available_endpoints(self) -> list[EndpointConfig]:
        available = [ep for ep in self.endpoints.values() if ep.health.is_available()]
        available.sort(key=lambda ep: ep.priority)
        return available

    def get_health_summary(self) -> dict[str, dict]:
        summary = {}
        for name, endpoint in self.endpoints.items():
            summary[name] = {
                "status": endpoint.health.status.value,
                "available": endpoint.health.is_available(),
                "error_count": endpoint.health.error_count,
                "consecutive_failures": endpoint.health.consecutive_failures,
                "last_success": endpoint.health.last_success.isoformat() if endpoint.health.last_success else None,
                "unavailable_until": endpoint.health.unavailable_until.isoformat() if endpoint.health.unavailable_until else None,
                "seconds_until_available": endpoint.health.time_until_available(),
            }
        return summary


# Global singleton
_endpoint_manager = None


def get_endpoint_manager() -> EndpointManager:
    global _endpoint_manager
    if _endpoint_manager is None:
        from core.config import get_config

        config = get_config()
        _endpoint_manager = EndpointManager(config)
    return _endpoint_manager
