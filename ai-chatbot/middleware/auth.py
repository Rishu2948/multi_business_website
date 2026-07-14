"""
ai-chatbot/middleware/auth.py
RBAC access-control dependency for the AI Catalog Chatbot service.

Provides:
  - get_db()                 async generator that yields a Motor database object
  - check_chatbot_access()   FastAPI dependency; validates session token and enforces
                             role/prime access rules against the shared MongoDB

Access matrix:
  super_admin, business_admin, staff  →  always permitted
  customer with is_prime: True        →  permitted
  customer with is_prime: False/absent →  HTTP 403
  missing/invalid/expired token       →  HTTP 401

No caching of access decisions — every request reads live from MongoDB so that
subscription changes (e.g. prime expiry) are reflected immediately.

Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.9, 10.10
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import AsyncGenerator

from fastapi import Depends, HTTPException, Request
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase


# ---------------------------------------------------------------------------
# MongoDB connection dependency
# ---------------------------------------------------------------------------

# Module-level Motor client — created once per process on first use.
# Using a module-level client (rather than per-request) lets Motor's
# built-in connection pool be shared across requests.
_motor_client: AsyncIOMotorClient | None = None


def _get_motor_client() -> AsyncIOMotorClient:
    """Return (or lazily create) the module-level Motor client."""
    global _motor_client
    if _motor_client is None:
        mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
        _motor_client = AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=5000)
    return _motor_client


async def get_db() -> AsyncGenerator[AsyncIOMotorDatabase, None]:
    """
    FastAPI dependency: yields a Motor database object.

    Reads ``MONGO_URL`` and ``DB_NAME`` from environment variables.
    Falls back to ``mongodb://localhost:27017`` / ``multi_business_db`` if
    the variables are absent (useful for local development without a .env).

    Usage::

        @router.post("/chat/message")
        async def chat(db=Depends(get_db)):
            ...
    """
    db_name = os.environ.get("DB_NAME", "multi_business_db")
    client = _get_motor_client()
    yield client[db_name]


# ---------------------------------------------------------------------------
# RBAC dependency
# ---------------------------------------------------------------------------

#: Roles that are always granted access regardless of is_prime.
_ALLOWED_ROLES: frozenset[str] = frozenset({"super_admin", "business_admin", "staff"})


async def check_chatbot_access(
    request: Request,
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict:
    """
    FastAPI dependency: authenticate the caller and enforce chatbot access rules.

    Token extraction order:
    1. ``session_token`` cookie
    2. ``Authorization: Bearer <token>`` header

    Raises:
        HTTPException(401) — token missing, session not found, session expired,
                             or user not found in ``users`` collection.
        HTTPException(403) — authenticated as a non-prime customer.

    Returns:
        A dict with at least ``role`` and ``is_prime`` fields from the
        ``users`` collection (``_id`` excluded by projection).

    No caching: ``is_prime`` is read from MongoDB on every request so that
    subscription changes take effect immediately.
    """
    # ------------------------------------------------------------------
    # Step 1: Extract token from cookie or Authorization header
    # ------------------------------------------------------------------
    token: str | None = request.cookies.get("session_token")

    if not token:
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1].strip() or None

    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")

    # ------------------------------------------------------------------
    # Step 2: Validate session in user_sessions collection
    # ------------------------------------------------------------------
    session = await db.user_sessions.find_one(
        {"session_token": token},
        {"_id": 0, "user_id": 1, "expires_at": 1},
    )

    if not session:
        raise HTTPException(status_code=401, detail="Authentication required")

    # Normalise expires_at to an aware datetime before comparison
    expires_at: datetime | None = session.get("expires_at")
    if expires_at is not None:
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at)
        # If stored as naive UTC (no tzinfo), attach UTC timezone
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < datetime.now(timezone.utc):
            raise HTTPException(status_code=401, detail="Authentication required")

    # ------------------------------------------------------------------
    # Step 3: Load user role and is_prime from users collection
    # ------------------------------------------------------------------
    user_id = session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    user = await db.users.find_one(
        {"user_id": user_id},
        {"_id": 0, "role": 1, "is_prime": 1},
    )

    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    # ------------------------------------------------------------------
    # Step 4: RBAC check
    # ------------------------------------------------------------------
    role: str = user.get("role", "")

    # super_admin, business_admin, staff — always permitted
    if role in _ALLOWED_ROLES:
        return user

    # prime customers — permitted
    if role == "customer" and user.get("is_prime") is True:
        return user

    # non-prime customers and any unrecognised role — denied
    raise HTTPException(
        status_code=403,
        detail={"error": "Prime subscription required", "upgrade_url": "/prime"},
    )
