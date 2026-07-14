"""
ai-chatbot/tests/test_rate_limiter.py
Unit tests for middleware/rate_limiter.py

Tests cover:
- check_rate_limit() allows requests within the cap
- check_rate_limit() blocks the 31st request from the same IP
- Requests from different IPs are tracked independently
- Old timestamps outside the 60-second window are purged and the window resets
- The middleware returns HTTP 429 with the correct JSON body when over limit
- The middleware passes allowed requests through to the next handler
- IP resolution prefers client.host and falls back to X-Forwarded-For
"""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Reset module-level state between tests by patching the shared dict
from middleware import rate_limiter as rl


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _reset_state() -> None:
    """Clear the in-process IP tracking dict between tests."""
    with rl._lock:
        rl._ip_timestamps.clear()


# ---------------------------------------------------------------------------
# check_rate_limit() unit tests
# ---------------------------------------------------------------------------


class TestCheckRateLimit:
    def setup_method(self):
        _reset_state()

    def test_first_request_is_allowed(self):
        assert rl.check_rate_limit("10.0.0.1") is True

    def test_requests_up_to_cap_are_allowed(self):
        ip = "10.0.0.2"
        for _ in range(rl._MAX_REQUESTS):
            assert rl.check_rate_limit(ip) is True

    def test_request_beyond_cap_is_blocked(self):
        ip = "10.0.0.3"
        for _ in range(rl._MAX_REQUESTS):
            rl.check_rate_limit(ip)
        # 31st request
        assert rl.check_rate_limit(ip) is False

    def test_different_ips_are_independent(self):
        ip_a = "192.168.1.1"
        ip_b = "192.168.1.2"
        # Exhaust ip_a
        for _ in range(rl._MAX_REQUESTS):
            rl.check_rate_limit(ip_a)
        assert rl.check_rate_limit(ip_a) is False
        # ip_b should still be fresh
        assert rl.check_rate_limit(ip_b) is True

    def test_window_resets_after_60_seconds(self):
        ip = "10.0.0.4"
        # Exhaust the window
        for _ in range(rl._MAX_REQUESTS):
            rl.check_rate_limit(ip)
        assert rl.check_rate_limit(ip) is False

        # Simulate all timestamps being > 60 s old
        old_time = time.monotonic() - 61.0
        with rl._lock:
            dq = rl._ip_timestamps[ip]
            for i in range(len(dq)):
                dq[i] = old_time

        # Next request should be allowed again
        assert rl.check_rate_limit(ip) is True

    def test_blocked_request_does_not_consume_a_slot(self):
        """Timestamps must not be appended when the request is rejected."""
        ip = "10.0.0.5"
        for _ in range(rl._MAX_REQUESTS):
            rl.check_rate_limit(ip)

        # Make several blocked calls
        for _ in range(5):
            rl.check_rate_limit(ip)

        with rl._lock:
            count = len(rl._ip_timestamps[ip])

        assert count == rl._MAX_REQUESTS

    def test_unknown_ip_fallback(self):
        """'unknown' IP should still be tracked normally."""
        assert rl.check_rate_limit("unknown") is True


# ---------------------------------------------------------------------------
# _resolve_ip() unit tests
# ---------------------------------------------------------------------------


class TestResolveIp:
    def _make_request(self, host=None, forwarded_for=None):
        req = MagicMock()
        if host:
            req.client = MagicMock()
            req.client.host = host
        else:
            req.client = None
        headers = {}
        if forwarded_for:
            headers["X-Forwarded-For"] = forwarded_for
        req.headers = headers
        return req

    def test_prefers_client_host(self):
        req = self._make_request(host="1.2.3.4", forwarded_for="9.9.9.9")
        assert rl._resolve_ip(req) == "1.2.3.4"

    def test_falls_back_to_x_forwarded_for(self):
        req = self._make_request(forwarded_for="5.6.7.8, 10.0.0.1")
        assert rl._resolve_ip(req) == "5.6.7.8"

    def test_falls_back_to_unknown(self):
        req = self._make_request()
        assert rl._resolve_ip(req) == "unknown"


# ---------------------------------------------------------------------------
# RateLimiterMiddleware integration tests (using TestClient)
# ---------------------------------------------------------------------------


class TestRateLimiterMiddleware:
    """Tests the middleware dispatch method via a lightweight ASGI app."""

    def setup_method(self):
        _reset_state()

    @pytest.mark.asyncio
    async def test_allowed_request_calls_next(self):
        from starlette.requests import Request
        from starlette.responses import JSONResponse

        middleware = rl.RateLimiterMiddleware(app=MagicMock())
        mock_next = AsyncMock(return_value=JSONResponse({"ok": True}))

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/chat/health",
            "headers": [],
            "query_string": b"",
        }

        # Patch _resolve_ip so it returns a stable IP
        with patch.object(rl, "_resolve_ip", return_value="10.1.1.1"):
            request = Request(scope)
            response = await middleware.dispatch(request, mock_next)

        assert response.status_code == 200
        mock_next.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_blocked_request_returns_429(self):
        from starlette.requests import Request

        middleware = rl.RateLimiterMiddleware(app=MagicMock())
        mock_next = AsyncMock()

        ip = "10.2.2.2"
        # Pre-fill the rate limit
        for _ in range(rl._MAX_REQUESTS):
            rl.check_rate_limit(ip)

        scope = {
            "type": "http",
            "method": "POST",
            "path": "/chat/message",
            "headers": [],
            "query_string": b"",
        }

        with patch.object(rl, "_resolve_ip", return_value=ip):
            request = Request(scope)
            response = await middleware.dispatch(request, mock_next)

        assert response.status_code == 429
        import json
        body = json.loads(response.body)
        assert body["error"] == "Rate limit exceeded. Please wait before sending more messages."
        mock_next.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_middleware_applies_to_all_routes(self):
        """The middleware should block any route, not only /chat/message."""
        from starlette.requests import Request

        middleware = rl.RateLimiterMiddleware(app=MagicMock())
        mock_next = AsyncMock()

        ip = "10.3.3.3"
        for _ in range(rl._MAX_REQUESTS):
            rl.check_rate_limit(ip)

        for path in ["/chat/health", "/chat/session/abc123", "/some/other/route"]:
            scope = {
                "type": "http",
                "method": "GET",
                "path": path,
                "headers": [],
                "query_string": b"",
            }
            with patch.object(rl, "_resolve_ip", return_value=ip):
                request = Request(scope)
                response = await middleware.dispatch(request, mock_next)
            assert response.status_code == 429, f"Expected 429 for path {path}"
