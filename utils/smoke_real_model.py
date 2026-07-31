"""
Optional real-model smoke (Phase 6).

Skips cleanly when no API credentials are configured.
Never run this as a required CI gate on air-gapped Advana hosts.

Usage:
    python -m utils.smoke_real_model

Env / config:
    Uses the project's normal config.json + api_key.json resolution.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _has_usable_key() -> bool:
    try:
        from core.config import get_config
        cfg = get_config()
    except Exception as e:
        print(f"SKIP: cannot load config ({e})")
        return False

    endpoints = cfg.get("endpoints") or {}
    if not endpoints:
        # legacy single key
        key = cfg.get("api_key") or ""
        if not key or "YOUR_" in key.upper():
            print("SKIP: no usable api_key in config")
            return False
        return True

    for name, ep in endpoints.items():
        key_name = ep.get("api_key_name", "api_key")
        val = cfg.get(key_name) or ""
        if val and "YOUR_" not in val.upper():
            return True
    print("SKIP: no non-placeholder API keys found for configured endpoints")
    return False


def main() -> int:
    print("PrizmForge real-model smoke")
    if not _has_usable_key():
        return 0  # skip is success for optional smoke

    try:
        from agents.base import call_agent
        result = call_agent(
            agent_name="orchestrator",
            prompt='Reply with a minimal JSON object: {"next_agent": "complete", "instructions": "smoke", "reasoning": "smoke test"}',
            task_id="smoke_real_model",
        )
    except Exception as e:
        print(f"FAIL: call_agent raised: {e}")
        return 1

    if not result:
        print("SKIP: empty response (network/API unavailable in this environment)")
        return 0

    print("OK: received response")
    print(result[:500])
    return 0


if __name__ == "__main__":
    sys.exit(main())
