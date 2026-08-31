"""Format HTTP error responses for soak / operator diagnostics."""

from __future__ import annotations

import json
from typing import Any

# Headers we never print (secrets).
_REDACT_HEADERS = {
    "authorization",
    "proxy-authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
    "api-key",
}

# Always include these if present; everything else is still printed except secrets.
_PRIORITY_HEADER_SUBSTR = (
    "retry-after",
    "ratelimit",
    "rate-limit",
    "x-request-id",
    "request-id",
    "cf-ray",
    "openai-",
    "x-kong",
    "x-opencode",
    "www-authenticate",
)

_DEFAULT_BODY_CHARS = 2000


def _header_items(headers: Any) -> list[tuple[str, str]]:
    if headers is None:
        return []
    if hasattr(headers, "items"):
        return [(str(k), str(v)) for k, v in headers.items()]
    try:
        return [(str(k), str(v)) for k, v in dict(headers).items()]
    except Exception:
        return []


def _safe_headers(headers: Any) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in _header_items(headers):
        if key.lower() in _REDACT_HEADERS:
            out[key] = "<redacted>"
        else:
            out[key] = value
    return out


def _priority_headers(headers: dict[str, str]) -> dict[str, str]:
    picked: dict[str, str] = {}
    for key, value in headers.items():
        lower = key.lower()
        if any(token in lower for token in _PRIORITY_HEADER_SUBSTR):
            picked[key] = value
    return picked


def extract_error_payload(body_text: str) -> dict[str, Any]:
    """Best-effort parse of provider error JSON (OpenAI / OpenRouter / OpenCode)."""
    text = (body_text or "").strip()
    if not text:
        return {}
    try:
        data = json.loads(text)
    except Exception:
        return {"raw": text[:_DEFAULT_BODY_CHARS]}
    if not isinstance(data, dict):
        return {"raw": text[:_DEFAULT_BODY_CHARS]}
    err = data.get("error", data)
    if isinstance(err, str):
        return {"message": err, "keys": sorted(data.keys())}
    if isinstance(err, dict):
        slim = dict(err)
        slim.setdefault("_top_keys", sorted(data.keys()))
        return slim
    return {"body": data}


def format_http_error_dump(
    resp: Any,
    *,
    url: str = "",
    model: str = "",
    endpoint: str = "",
    max_body: int = _DEFAULT_BODY_CHARS,
) -> str:
    """Multi-line dump: status, URL, model, headers, parsed error, raw body."""
    status = getattr(resp, "status_code", "?")
    headers = _safe_headers(getattr(resp, "headers", None))
    body = getattr(resp, "text", None)
    if body is None:
        raw = getattr(resp, "content", b"") or getattr(resp, "_body", b"")
        if isinstance(raw, bytes):
            body = raw.decode("utf-8", errors="replace")
        else:
            body = str(raw or "")

    lines = [f"HTTP {status}"]
    if endpoint:
        lines.append(f"endpoint: {endpoint}")
    if url:
        lines.append(f"url: {url}")
    if model:
        lines.append(f"model: {model}")

    priority = _priority_headers(headers)
    if priority:
        lines.append(f"rate/id headers: {priority}")
    if headers:
        lines.append(f"headers: {headers}")
    else:
        lines.append("headers: (none)")

    parsed = extract_error_payload(body)
    if parsed:
        try:
            rendered = json.dumps(parsed, ensure_ascii=False, default=str)
        except Exception:
            rendered = str(parsed)
        if len(rendered) > max_body:
            rendered = rendered[:max_body] + f"... <truncated {len(rendered) - max_body} chars>"
        lines.append(f"parsed error: {rendered}")

    clipped = body if len(body) <= max_body else body[:max_body] + f"... <truncated {len(body) - max_body} chars>"
    lines.append(f"body ({len(body)} chars): {clipped or '(empty)'}")
    return "\n".join(f"   {line}" for line in lines)


def print_http_error_dump(resp: Any, **kwargs: Any) -> str:
    """Print the dump and return it so callers can stash it on health state."""
    dump = format_http_error_dump(resp, **kwargs)
    print(dump)
    return dump
