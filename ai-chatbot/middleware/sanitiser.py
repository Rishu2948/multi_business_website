"""
ai-chatbot/middleware/sanitiser.py
Input sanitisation for the AI Catalog Chatbot service.

Provides:
  - sanitise(text: str) -> str   standalone function (importable for tests)
  - SanitiserMiddleware           Starlette middleware applied to POST /chat/message

Requirements: 9.1
"""

from __future__ import annotations

import json
import re

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


# ---------------------------------------------------------------------------
# Compiled patterns — compiled once at import time for performance
# ---------------------------------------------------------------------------

# Matches any HTML tag, e.g. <div>, </div>, <br />, <!-- comment -->
_HTML_TAG_RE = re.compile(r"<[^>]+>")

# Characters to strip: backtick, $, {, }, [, ], |, backslash, null byte
_SPECIAL_CHARS_RE = re.compile(r"[`$\{\}\[\]|\\\\]|\x00")

# One or more whitespace characters (space, tab, newline, etc.)
_WHITESPACE_RE = re.compile(r"\s+")


# ---------------------------------------------------------------------------
# Public sanitise() function
# ---------------------------------------------------------------------------


def sanitise(text: str) -> str:
    """
    Clean a raw user message string.

    Steps (applied in order):
    1. Strip all HTML tags (content matching ``<[^>]+>``).
    2. Strip special characters: backtick, ``$``, ``{``, ``}``, ``[``, ``]``,
       ``|``, ``\\``, and null bytes (``\\x00``).
    3. Collapse runs of whitespace to a single space and ``.strip()``.

    Returns the cleaned string, which may be empty if the input consisted
    entirely of stripped characters.
    """
    if not isinstance(text, str):
        return ""

    # Step 1 — remove HTML tags
    text = _HTML_TAG_RE.sub("", text)

    # Step 2 — remove special characters and null bytes
    text = _SPECIAL_CHARS_RE.sub("", text)

    # Step 3 — collapse whitespace
    text = _WHITESPACE_RE.sub(" ", text).strip()

    return text


# ---------------------------------------------------------------------------
# Starlette middleware
# ---------------------------------------------------------------------------


class SanitiserMiddleware(BaseHTTPMiddleware):
    """
    Sanitises the ``message`` field in ``POST /chat/message`` request bodies.

    Behaviour:
    - For any path other than ``POST /chat/message``, the request is forwarded
      unchanged.
    - For ``POST /chat/message``:
        1. Parse the JSON body.
        2. Run ``sanitise()`` on the ``message`` field.
        3. If the sanitised result is empty, return HTTP 400 with
           ``{"detail": "message field is empty after sanitisation"}``.
        4. Otherwise, replace the ``message`` field with the sanitised value,
           re-serialise the body, and pass the modified request to the next
           handler.

    Notes:
    - If the body is not valid JSON or the ``message`` field is absent, the
      request is passed through unchanged so that Pydantic validation in the
      route handler can return the appropriate 422/400 error.
    - The ``Content-Length`` header is updated to reflect the new body size.
    """

    _TARGET_PATH = "/chat/message"
    _TARGET_METHOD = "POST"

    async def dispatch(self, request: Request, call_next):
        # Only intercept POST /chat/message
        if request.method != self._TARGET_METHOD or request.url.path != self._TARGET_PATH:
            return await call_next(request)

        # Read the raw body
        raw_body = await request.body()

        # Attempt to parse JSON; pass through on failure (let FastAPI handle it)
        try:
            body_dict: dict = json.loads(raw_body)
        except (json.JSONDecodeError, ValueError):
            return await call_next(request)

        # If there is no ``message`` field, pass through (Pydantic will 422)
        if "message" not in body_dict:
            return await call_next(request)

        # Sanitise the message field
        original_message = body_dict["message"]
        if not isinstance(original_message, str):
            # Non-string value — pass through, let Pydantic handle type error
            return await call_next(request)

        sanitised_message = sanitise(original_message)

        # Empty after sanitisation → 400
        if not sanitised_message:
            return JSONResponse(
                status_code=400,
                content={"detail": "message field is empty after sanitisation"},
            )

        # Replace message with the sanitised version and rebuild the request
        body_dict["message"] = sanitised_message
        new_raw_body = json.dumps(body_dict).encode("utf-8")

        # Patch the request scope so downstream handlers see the modified body
        async def receive():
            return {"type": "http.request", "body": new_raw_body, "more_body": False}

        request._receive = receive  # type: ignore[attr-defined]

        # Update Content-Length to match the new body
        headers = dict(request.headers)
        headers["content-length"] = str(len(new_raw_body))
        # Starlette Request headers are immutable, but the ASGI scope can be mutated
        scope = request.scope
        scope["headers"] = [
            (k.lower().encode(), v.encode()) if isinstance(k, str) else (k, v)
            for k, v in headers.items()
        ]

        return await call_next(request)
