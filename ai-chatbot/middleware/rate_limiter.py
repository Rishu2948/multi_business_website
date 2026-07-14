"""
ai-chatbot/middleware/rate_limiter.py
Sliding-window per-IP rate limiter for the AI Catalog Chatbot service.

Provides:
  - check_rate_limit(ip: str) -> bool   standalone function (importable for tests)
  - RateLimiterMiddleware               Starlette middleware applied to ALL routes

Rate limit: 30 requests per 60-second sliding window per source IP.
No Redis dependency — state is kept in-process using a dict of deques.

Requirements: 9.4
"""

from __future__ import annotations

import threading
import time
from collections import deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_WINDOW_SECONDS: float = 60.0
_MAX_REQUESTS: int = 30

# ---------------------------------------------------------------------------
# In-process state
# ---------------------------------------------------------------------------

# Maps IP address -> deque of monotonic timestamps for requests in the window
_ip_timestamps: dict[str, deque[float]] = {}

# Single lock protecting all reads/writes to _ip_timestamps
_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _purge_old(dq: deque[float], now: float) -> None:
    """Remove timestamps older than the sliding window from the left of *dq*."""
    cutoff = now - _WINDOW_SECONDS
    while dq and dq[0] <= cutoff:
        dq.popleft()


def _evict_empty() -> None:
    """Remove entries whose deque is empty to prevent unbounded dict growth."""
    empty_keys = [ip for ip, dq in _ip_timestamps.items() if not dq]
    for key in empty_keys:
        del _ip_timestamps[key]


# ---------------------------------------------------------------------------
# Public standalone function (also used internally by the middleware)
# ---------------------------------------------------------------------------


def check_rate_limit(ip: str) -> bool:
    """
    Record a request attempt for *ip* and decide whether it is allowed.

    Returns:
        ``True``  — the request is within the rate limit (allowed).
        ``False`` — the request exceeds the rate limit (should be rejected).

    Side-effects:
        - Appends the current monotonic timestamp to the deque for *ip*.
        - Purges timestamps outside the 60-second window.
        - Evicts empty deques periodically to limit memory use.
    """
    now = time.monotonic()

    with _lock:
        dq = _ip_timestamps.get(ip)
        if dq is None:
            dq = deque()
            _ip_timestamps[ip] = dq

        # Purge timestamps outside the window
        _purge_old(dq, now)

        if len(dq) >= _MAX_REQUESTS:
            # Over limit — do NOT record this attempt
            return False

        # Within limit — record the timestamp and allow
        dq.append(now)

        # Opportunistic cleanup: evict empty entries on every 100th call
        # (cheap amortised cost; no separate background thread required)
        if len(_ip_timestamps) > 0 and len(dq) == 1:
            # Only bother evicting when a new deque was just created (low
            # frequency) to keep the hot path fast.
            _evict_empty()

        return True


# ---------------------------------------------------------------------------
# IP resolution helper
# ---------------------------------------------------------------------------


def _resolve_ip(request: Request) -> str:
    """
    Return the source IP for *request*.

    Priority:
    1. ``request.client.host`` (set by the ASGI server).
    2. First value of the ``X-Forwarded-For`` header (reverse-proxy scenario).
    3. Fallback string ``"unknown"`` if neither is available.
    """
    if request.client and request.client.host:
        return request.client.host

    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # X-Forwarded-For may contain a comma-separated list; take the first
        return forwarded_for.split(",")[0].strip()

    return "unknown"


# ---------------------------------------------------------------------------
# Starlette middleware
# ---------------------------------------------------------------------------


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """
    Sliding 60-second window per-IP rate limiter applied to ALL routes.

    Behaviour:
    - Resolves the source IP from ``request.client.host``, falling back to
      the ``X-Forwarded-For`` header.
    - Calls ``check_rate_limit(ip)``; if it returns ``False``, responds
      immediately with HTTP 429 and a JSON error body.
    - Otherwise forwards the request to the next handler unchanged.
    """

    async def dispatch(self, request: Request, call_next):
        ip = _resolve_ip(request)

        if not check_rate_limit(ip):
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded. Please wait before sending more messages."
                },
            )

        return await call_next(request)
