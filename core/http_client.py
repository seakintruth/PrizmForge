from typing import Dict, Optional

"""
Minimal HTTP JSON POST helper.

Prefer the `requests` package when available (Advana / normal installs).
Fall back to stdlib `urllib.request` on minimal SageMaker images.

No new dependencies.
"""

from __future__ import annotations

import json
import ssl
from typing import Any, Dict, Optional
from urllib import error as urllib_error
from urllib import request as urllib_request


class HttpResponse:
    """Small response object compatible with the bits agents.base uses."""

    def __init__(self, status_code: int, body: bytes, headers: Optional[Dict[str, str]] = None):
        self.status_code = status_code
        self._body = body or b""
        self.headers = headers or {}
        self.text = self._body.decode("utf-8", errors="replace")

    def json(self) -> Any:
        return json.loads(self.text or "null")

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise HttpError(f"HTTP {self.status_code}: {self.text[:200]}")


class HttpError(Exception):
    pass


def _post_with_requests(
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    json_body: Optional[Dict[str, Any]] = None,
    timeout: float = 120,
    proxies: Optional[Dict[str, str]] = None,
) -> HttpResponse:
    import requests

    resp = requests.post(
        url,
        headers=headers or {},
        json=json_body,
        timeout=timeout,
        proxies=proxies,
    )
    return HttpResponse(resp.status_code, resp.content, dict(resp.headers))


def _post_with_urllib(
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    json_body: Optional[Dict[str, Any]] = None,
    timeout: float = 120,
    proxies: Optional[Dict[str, str]] = None,
) -> HttpResponse:
    data = None
    hdrs = dict(headers or {})
    if json_body is not None:
        data = json.dumps(json_body).encode("utf-8")
        hdrs.setdefault("Content-Type", "application/json")

    req = urllib_request.Request(url, data=data, headers=hdrs, method="POST")

    # Basic proxy support (HTTP_PROXY style) if provided
    handlers = []
    if proxies:
        handlers.append(urllib_request.ProxyHandler(proxies))
    # Default SSL context
    handlers.append(urllib_request.HTTPSHandler(context=ssl.create_default_context()))
    opener = urllib_request.build_opener(*handlers)

    try:
        with opener.open(req, timeout=timeout) as resp:
            body = resp.read()
            status = getattr(resp, "status", None) or resp.getcode()
            return HttpResponse(int(status), body, dict(resp.headers.items()))
    except urllib_error.HTTPError as e:
        body = e.read() if hasattr(e, "read") else b""
        return HttpResponse(int(e.code), body, dict(getattr(e, "headers", {}) or {}))
    except urllib_error.URLError as e:
        raise HttpError(f"URL error: {e}") from e


def post_json(
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    json_body: Optional[Dict[str, Any]] = None,
    timeout: float = 120,
    proxies: Optional[Dict[str, str]] = None,
    prefer_requests: bool = True,
) -> HttpResponse:
    """
    POST JSON to url.

    Uses `requests` when importable and prefer_requests=True; otherwise urllib.
    """
    if prefer_requests:
        try:
            return _post_with_requests(
                url,
                headers=headers,
                json_body=json_body,
                timeout=timeout,
                proxies=proxies,
            )
        except ImportError:
            pass
    return _post_with_urllib(url, headers=headers, json_body=json_body, timeout=timeout, proxies=proxies)


def has_requests() -> bool:
    try:
        import requests  # noqa: F401

        return True
    except ImportError:
        return False
