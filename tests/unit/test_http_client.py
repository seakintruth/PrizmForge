"""
Phase 4 — HTTP client + endpoint resilience (mocked, no network).

Uses stdlib unittest.mock only (pytest-mock also fine on Advana).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestHttpClient:
    def test_has_requests(self):
        from core.http_client import has_requests

        # In this environment requests is installed
        assert isinstance(has_requests(), bool)

    def test_post_json_uses_requests_when_available(self):
        from core.http_client import post_json

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = json.dumps({"choices": [{"message": {"content": "hello"}}]}).encode()
        mock_resp.headers = {"Content-Type": "application/json"}

        with patch("requests.post", return_value=mock_resp) as mocked:
            r = post_json(
                "http://example.invalid/v1/chat/completions",
                json_body={"model": "x", "messages": []},
                prefer_requests=True,
            )
            assert mocked.called
            assert r.status_code == 200
            assert r.json()["choices"][0]["message"]["content"] == "hello"

    def test_post_json_urllib_path(self):
        from core.http_client import post_json

        class FakeResp:
            def __init__(self):
                self.status = 200
                self.headers = {"Content-Type": "application/json"}

            def read(self):
                return b'{"ok": true}'

            def getcode(self):
                return 200

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        class FakeOpener:
            def open(self, req, timeout=None):
                return FakeResp()

        with patch("core.http_client.urllib_request.build_opener", return_value=FakeOpener()):
            r = post_json(
                "http://example.invalid/v1",
                json_body={"a": 1},
                prefer_requests=False,
            )
            assert r.status_code == 200
            assert r.json()["ok"] is True

    def test_http_error_raise_for_status(self):
        from core.http_client import HttpError, HttpResponse

        r = HttpResponse(500, b"fail")
        with pytest.raises(HttpError):
            r.raise_for_status()


class TestEndpointResilienceMocks:
    def test_401_response_shape(self):
        """Simulate key-locked style body the call_endpoint path inspects."""
        from core.http_client import HttpResponse

        body = {
            "error": {
                "type": "unauthorized",
                "message": "API KEY LOCKED",
                "unlock_url": "https://example.invalid/unlock",
            }
        }
        r = HttpResponse(401, json.dumps(body).encode())
        data = r.json()["error"]
        assert data["type"] == "unauthorized"
        assert "unlock_url" in data

    def test_rate_limit_429_body(self):
        from core.http_client import HttpResponse

        r = HttpResponse(429, b'{"error": {"message": "rate limited"}}')
        assert r.status_code == 429
        assert "rate" in r.json()["error"]["message"]

    def test_mock_openai_chat_still_patches_requests(self, mock_openai_chat):
        """Existing fixture continues to work for HTTP-layer tests."""
        mock_openai_chat(response_text="RESILIENCE_OK")

        # base still imports requests; fixture patches agents.base.requests.post
        # and top-level requests.post — post_json goes through requests.post
        with patch("requests.post") as mocked:
            mocked.return_value = MagicMock(
                status_code=200,
                content=json.dumps({"choices": [{"message": {"content": "RESILIENCE_OK"}}]}).encode(),
                headers={},
            )
            from core.http_client import post_json

            r = post_json("http://localhost/v1", json_body={})
            assert r.status_code == 200


class TestRateLimiter:
    def test_rate_limiter_basic(self):
        from core.rate_limiter import RateLimiter

        rl = RateLimiter(60)
        # wait_if_needed should return without sleeping when under limit
        rl.wait_if_needed()
        assert len(rl.calls) == 1
        rl.set_max_calls(30)
        assert rl.max_calls == 30
