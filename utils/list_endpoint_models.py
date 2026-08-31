#!/usr/bin/env python3
"""
utils/list_endpoint_models.py

Exploratory model discovery tool for GenAI.mil endpoints.
Reads endpoints from config.json and models to test from list_models_to_test.json.
"""

import json
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import get_config
from core.http_client import post_json

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
RETRYABLE_STATUS_CODES = {429, 503, 504}
MAX_RETRIES = 3
BASE_DELAY = 1.0  # seconds


def load_test_models() -> list[str]:
    """Load the exploratory list of models to test."""
    path = Path("utils/list_models_to_test.json")
    if not path.exists():
        print(f"⚠️  {path} not found. Using minimal fallback list.")
        return ["gemini-2.5-pro", "gemini-3.7-flash"]

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        models = data.get("models", [])
        # Deduplicate while preserving order
        seen = set()
        unique_models = []
        for m in models:
            if m not in seen:
                seen.add(m)
                unique_models.append(m)
        print(f"Loaded {len(unique_models)} unique models from {path.name}")
        return unique_models
    except Exception as e:
        print(f"⚠️  Failed to load {path}: {e}")
        return ["gemini-2.5-pro", "gemini-3.7-flash"]


def _post_with_retry(
    url: str,
    *,
    headers: dict[str, str],
    json_body: dict[str, Any] | None,
    proxies: dict[str, str] | None,
    timeout: float = 25,
) -> Any:
    """POST with simple exponential backoff for retryable errors."""
    last_exception = None

    for attempt in range(MAX_RETRIES):
        try:
            resp = post_json(
                url=url,
                headers=headers,
                json_body=json_body,
                timeout=timeout,
                proxies=proxies,
                prefer_requests=True,
            )
            if resp.status_code in RETRYABLE_STATUS_CODES and attempt < MAX_RETRIES - 1:
                delay = BASE_DELAY * (2**attempt)
                print(f"     (Retryable {resp.status_code}, waiting {delay:.1f}s...)")
                time.sleep(delay)
                continue
            return resp
        except Exception as e:
            last_exception = e
            if attempt < MAX_RETRIES - 1:
                delay = BASE_DELAY * (2**attempt)
                print(f"     (Transient error, retrying in {delay:.1f}s...)")
                time.sleep(delay)
            else:
                raise  # <-- was: raise last_exception   (this was the B904 violation)

    raise last_exception  # type: ignore


def test_models_endpoint(base_url: str, api_key: str, proxies: dict, endpoint_name: str) -> None:
    """Test the standard OpenAI-compatible /v1/models endpoint."""
    models_url = base_url.replace("/chat/completions", "/models")
    print(f"\n📋 [{endpoint_name}] Testing /v1/models")
    print(f"   URL: {models_url}")

    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}

    try:
        resp = _post_with_retry(
            url=models_url,
            headers=headers,
            json_body=None,
            proxies=proxies,
            timeout=20,
        )
        print(f"   Status: {resp.status_code}")

        if resp.status_code == 200:
            data = resp.json()
            models = [str(m.get("id")) for m in data.get("data", []) if isinstance(m, dict) and m.get("id")]
            print(f"   ✅ SUCCESS — Found {len(models)} models")
            for m in sorted(models)[:30]:
                print(f"      • {m}")
            if len(models) > 30:
                print(f"      ... and {len(models) - 30} more")
        else:
            body = resp.text[:300] if resp.text else "(empty body)"
            print(f"   Body: {body}")
    except Exception as e:
        print(f"   Exception: {type(e).__name__}: {e}")


def test_model(base_url: str, api_key: str, model: str, proxies: dict, endpoint_name: str) -> bool:
    """Test a single model via the chat completions endpoint."""
    print(f"   Testing: {model:<30}", end=" ")

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Reply with exactly: OK"}],
        "max_tokens": 20,
        "temperature": 0.0,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        resp = _post_with_retry(
            url=base_url,
            headers=headers,
            json_body=payload,
            proxies=proxies,
            timeout=25,
        )

        if resp.status_code != 200:
            print(f"❌ {resp.status_code}")
            return False

        # Try to extract the model's reply
        try:
            data = resp.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        except Exception:
            content = resp.text[:80] if resp.text else ""

        # Accept "OK" anywhere in the response (case-insensitive)
        if content and "ok" in content.lower():
            print("✅ WORKING")
            return True
        else:
            print(f'⚠️  REPLIED → "{content[:60]}"')
            return True  # Still counts as the model worked

    except Exception as e:
        print(f"❌ {type(e).__name__}")
        return False


def main() -> None:
    config = get_config()
    proxy: dict = config.get("proxy") or {}
    endpoints = config.get("endpoints", {})

    test_models = load_test_models()

    print("\n🔍 GenAI.mil Exploratory Model Discovery")
    print("=" * 100)
    print(f"Proxy configured : {bool(proxy)}")
    print(f"Endpoints        : {list(endpoints.keys())}")
    print(f"Models to test   : {len(test_models)}")
    print("=" * 100)

    results: dict[str, list[str]] = {}

    for ep_name, ep_config in endpoints.items():
        base_url = ep_config.get("base_url")
        api_key = config.get(ep_config.get("api_key_name"))

        if not base_url or not api_key:
            print(f"\n⚠️  Skipping {ep_name} — missing base_url or API key")
            continue

        print(f"\n{'█' * 100}")
        print(f"🔌 ENDPOINT: {ep_name.upper()} | {base_url}")
        print(f"{'█' * 100}")

        test_models_endpoint(base_url, api_key, proxy, ep_name)

        print("\n🧪 Testing individual models:")
        working_models: list[str] = []
        for model in test_models:
            if test_model(base_url, api_key, model, proxy, ep_name):
                working_models.append(model)

        results[ep_name] = working_models

        if working_models:
            print(f"\n✅ WORKING MODELS on {ep_name} ({len(working_models)}):")
            for m in sorted(set(working_models)):
                print(f"     • {m}")
        else:
            print("   No working models found on this endpoint.")

    # -------------------------------------------------------------------------
    # Final Summary
    # -------------------------------------------------------------------------
    print("\n" + "=" * 100)
    print("SUMMARY")
    print("=" * 100)
    for ep_name, models in results.items():
        print(f"{ep_name:15} → {len(models)} working model(s)")
        if models:
            print(f"                 {', '.join(sorted(set(models)))}")
    print("=" * 100)
    print("Exploratory discovery complete.\n")


if __name__ == "__main__":
    main()
