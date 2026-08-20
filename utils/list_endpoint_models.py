#!/usr/bin/env python3
"""
utils/list_endpoint_models.py

Diagnostic tool to:
- List configured endpoints from config.json
- Try to discover available models (/v1/models)
- Fall back to testing the actual chat completions endpoint
- Continue on errors and test every endpoint
"""

import json
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

CONFIG_FILE = Path("config.json")
API_KEY_FILE = Path("api_key.json")


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"⚠️  Failed to parse {path}: {e}")
        return {}


def get_api_key(config: dict, api_key_name: str) -> str | None:
    # Prefer api_key.json
    keys = load_json(API_KEY_FILE)
    if api_key_name in keys:
        return keys[api_key_name]

    # Fallback to config.json
    return config.get(api_key_name)


def derive_models_url(base_url: str) -> str:
    """Convert chat completions URL to models URL."""
    parsed = urlparse(base_url)
    # Remove everything after /v1
    if "/v1/" in base_url:
        root = base_url.split("/v1/")[0] + "/v1"
    else:
        root = f"{parsed.scheme}://{parsed.netloc}/v1"
    return f"{root}/models"


def test_models_endpoint(url: str, api_key: str) -> tuple[bool, str]:
    """Try to fetch /v1/models."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            data = json.loads(response.read().decode())
            if "data" in data:
                models = [m.get("id", "unknown") for m in data.get("data", [])]
                return True, f"✅ Found {len(models)} models: {models[:8]}..."
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="ignore")[:300]
        return False, f"HTTP {e.code}: {body}"
    except Exception as e:
        return False, str(e)[:200]
    return False, "No valid model list returned"


def test_chat_endpoint(base_url: str, api_key: str) -> tuple[bool, str]:
    """Send a minimal test message to the chat endpoint."""
    payload = {
        "messages": [{"role": "user", "content": "Reply with exactly: TEST_OK"}],
        "max_tokens": 8,
        "temperature": 0,
    }
    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    req = urllib.request.Request(base_url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            body = response.read().decode()
            if "content" in body.lower() or "message" in body.lower() or "choices" in body.lower():
                return True, "✅ Chat endpoint responded successfully"
            return False, f"Unexpected response: {body[:200]}"
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="ignore")[:300]
        return False, f"HTTP {e.code}: {body}"
    except Exception as e:
        return False, str(e)[:200]


def main():
    config = load_json(CONFIG_FILE)
    endpoints = config.get("endpoints", {})

    if not endpoints:
        print("⚠️  No 'endpoints' section found in config.json")
        return

    print("🔍 PrizmForge Endpoint Discovery & Health Check")
    print("=" * 60)

    for name, ep_config in endpoints.items():
        print(f"\n{'=' * 60}")
        print(f"🔌 Endpoint: {name}")
        print(f"{'=' * 60}")

        base_url = ep_config.get("base_url")
        if not base_url:
            print("   ⚠️  No base_url configured — skipping")
            continue

        print(f"   Base URL : {base_url}")

        api_key_name = ep_config.get("api_key_name", "api_key")
        api_key = get_api_key(config, api_key_name)

        if not api_key or "YOUR_" in api_key or len(api_key) < 10:
            print(f"   ❌ No valid API key found for '{api_key_name}'")
            continue

        print(f"   ✅ API key found for: {api_key_name}")

        # 1. Try models endpoint
        models_url = derive_models_url(base_url)
        print(f"   Testing models: {models_url}")
        success, msg = test_models_endpoint(models_url, api_key)
        print(f"   {msg}")

        if success:
            continue

        # 2. Fallback to testing chat endpoint
        print("   Testing chat endpoint reachability...")
        _chat_ok, chat_msg = test_chat_endpoint(base_url, api_key)
        print(f"   {chat_msg}")

    print("\n" + "=" * 60)
    print("✅ All endpoints processed.")
    print("=" * 60)


if __name__ == "__main__":
    main()
