import logging
import re

# Feedback #552: Allow configuring custom fallback rules explicitly
_CUSTOM_FALLBACKS = {}
_SCHEMAS = {}


def register_schema(name, schema):
    """
    Registers a schema for a specific agent name.
    """
    _SCHEMAS[name] = schema


def configure_fallbacks(mapping):
    """
    Explicitly map agent names to their schema keys.
    Reference: Feedback #552
    """
    _CUSTOM_FALLBACKS.update(mapping)


def get_schema(agent_name):
    """
    Retrieves the schema for a given agent name.

    Includes expanded fallback logic to handle naming variations and edge cases
    where custom prefix/suffixes are used.

    Reference: Feedback #552
    """
    if not agent_name:
        return None

    # 1. Direct match
    if agent_name in _SCHEMAS:
        return _SCHEMAS[agent_name]

    # 2. Check explicit custom fallbacks (Feedback #552)
    if agent_name in _CUSTOM_FALLBACKS:
        target = _CUSTOM_FALLBACKS[agent_name]
        if target in _SCHEMAS:
            return _SCHEMAS[target]

    # 3. Expanded fallback logic (Feedback #552)
    # Normalize: lowercase and remove non-alphanumeric characters
    def normalize(s):
        return re.sub(r"[^a-z0-9]", "", s.lower())

    norm_name = normalize(agent_name)

    # Define common prefixes and suffixes to check for naming variations
    prefixes = ["agent", "bot", "assistant"]
    suffixes = ["agent", "bot", "assistant", "schema", "service", "handler"]

    # Check all registered schemas using normalized keys
    for key, schema in _SCHEMAS.items():
        norm_key = normalize(key)

        # Check exact normalized match
        if norm_name == norm_key:
            return schema

        # Check variations by stripping common prefixes
        for p in prefixes:
            if norm_name.removeprefix(p) == norm_key:
                return schema

        # Check variations by stripping common suffixes
        for s in suffixes:
            if norm_name.removesuffix(s) == norm_key:
                return schema

    logging.warning(f"Schema for agent '{agent_name}' not found after applying fallback logic.")
    return None
