"""
ai-chatbot/middleware/auth.py
RBAC access-control dependency for the AI Catalog Chatbot service.

Provides:
  - get_db()                 async generator that yields a Motor database object
  - check_chatbot_access()   FastAPI dependency; validates session token and enforces
                             role/prime access rules against the shared MongoDB

Access matrix:
  super_admin, business_admin, staff  →  always permitted
  customer with active Prime membership for business →  permitted
  customer without Prime membership →  HTTP 403
  missing/invalid/expired token       →  HTTP 401

Business-scoped access:
  - Checks business_config.prime.features.ai_chatbot.enabled first
  - Then checks prime_memberships for active record
  - Falls back to users.is_prime for migration (whisked_words only)

No caching of access decisions — every request reads live from MongoDB so that
subscription changes (e.g. prime expiry) are reflected immediately.

Aligned with Auth_Module semantics:
  - First tries JWT access token validation
  - Falls back to legacy session tokens if AUTH_ACCEPT_LEGACY_SESSION=true
  - Uses centralized token extraction logic

Requirements: 3.4, 3.5, 12.3, 15.1
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import AsyncGenerator

from fastapi import Depends, HTTPException, Request
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

# Add backend to path for Auth_Module import
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

try:
    from backend.auth.dependencies import extract_token
    from backend.auth.tokens import TokenManager
    AUTH_MODULE_AVAILABLE = True
except ImportError:
    AUTH_MODULE_AVAILABLE = False


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

    Business-scoped access check:
    1. Extract business_id from request body
    2. Check business_config.prime.features.ai_chatbot.enabled
    3. Check prime_memberships for active record
    4. Fall back to users.is_prime for migration (whisked_words only)

    Raises:
        HTTPException(401) — token missing, session not found, session expired,
                             or user not found in ``users`` collection.
        HTTPException(403) — authenticated as a non-prime customer.
        HTTPException(404) — business_config not found for business_id.

    Returns:
        A dict with at least ``role`` and ``is_prime`` fields from the
        ``users`` collection (``_id`` excluded by projection).

    No caching: membership status is read from MongoDB on every request so that
    subscription changes take effect immediately.
    """
    # ------------------------------------------------------------------
    # Step 1: Extract token using Auth_Module (if available) or legacy method
    # ------------------------------------------------------------------
    if AUTH_MODULE_AVAILABLE:
        # Use centralized token extraction from Auth_Module
        token = await extract_token(request)
    else:
        # Legacy fallback
        token: str | None = request.cookies.get("session_token") or request.cookies.get("refresh_token")
        if not token:
            auth_header = request.headers.get("authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header.split(" ", 1)[1].strip() or None

    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")

    # ------------------------------------------------------------------
    # Step 2: Validate token using Auth_Module (if available) or legacy method
    # ------------------------------------------------------------------
    user_id = None
    
    if AUTH_MODULE_AVAILABLE:
        # Try JWT access token validation first
        try:
            token_manager = TokenManager(db)
            payload = token_manager.verify_access_token(token)
            user_id = payload["sub"]
            
            # Load user from DB
            user = await db.users.find_one(
                {"user_id": user_id},
                {"_id": 0, "role": 1, "is_prime": 1, "business_access": 1}
            )
            
            if not user:
                raise HTTPException(status_code=401, detail="User not found")
            
            # Skip to RBAC check (Step 4)
            role = user.get("role", "")
            if role in _ALLOWED_ROLES:
                return user
            
            # Continue to business-scoped check (Step 5)
            
        except HTTPException:
            # If JWT fails, try legacy session if enabled
            if os.environ.get("AUTH_ACCEPT_LEGACY_SESSION", "false").lower() == "true":
                # Fall through to legacy validation below
                pass
            else:
                raise
    
    # Legacy session validation (for AUTH_ACCEPT_LEGACY_SESSION=true or when Auth_Module unavailable)
    if user_id is None:
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
            {"_id": 0, "role": 1, "is_prime": 1, "business_access": 1},
        )

        if not user:
            raise HTTPException(status_code=401, detail="Authentication required")
    
    # ------------------------------------------------------------------
    # Step 4: RBAC check (admin bypass)
    # ------------------------------------------------------------------
    role: str = user.get("role", "")

    # super_admin, business_admin, staff — always permitted
    if role in _ALLOWED_ROLES:
        return user

    # ------------------------------------------------------------------
    # Step 4: RBAC check (admin bypass)
    # ------------------------------------------------------------------
    role: str = user.get("role", "")

    # super_admin, business_admin, staff — always permitted
    if role in _ALLOWED_ROLES:
        return user

    # ------------------------------------------------------------------
    # Step 5: Business-scoped Prime access check for customers
    # ------------------------------------------------------------------
    if role == "customer":
        # Extract business_id from request body
        try:
            request_body = await request.json()
            business_id = request_body.get("business_id")
        except:
            # If request body is not JSON or missing, try query params
            business_id = request.query_params.get("business_id")

        if not business_id:
            raise HTTPException(
                status_code=400,
                detail="business_id required in request body or query params"
            )

        # Check business_config.prime.features.ai_chatbot.enabled
        try:
            business_config = await db.business_config.find_one(
                {"business_id": business_id},
                {"_id": 0, "prime.enabled": 1, "prime.features": 1}
            )

            if not business_config:
                raise HTTPException(
                    status_code=404,
                    detail=f"Prime not configured for business: {business_id}"
                )

            prime_config = business_config.get("prime", {})
            if not prime_config.get("enabled", False):
                raise HTTPException(
                    status_code=403,
                    detail={
                        "error": "Prime subscription required",
                        "feature": "ai_chatbot",
                        "upgrade_url": f"/prime?business_id={business_id}"
                    }
                )

            features = prime_config.get("features", {})
            ai_chatbot_config = features.get("ai_chatbot", {})
            if not ai_chatbot_config.get("enabled", False):
                raise HTTPException(
                    status_code=403,
                    detail={
                        "error": "Prime subscription required",
                        "feature": "ai_chatbot",
                        "upgrade_url": f"/prime?business_id={business_id}"
                    }
                )
        except HTTPException:
            raise
        except Exception as e:
            # Log error but deny access on config errors
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "Prime subscription required",
                    "feature": "ai_chatbot",
                    "upgrade_url": f"/prime?business_id={business_id}"
                }
            )

        # Check prime_memberships for active record
        try:
            membership = await db.prime_memberships.find_one({
                "user_id": user_id,
                "business_id": business_id,
                "status": "active",
                "expires_at": {"$gt": datetime.now(timezone.utc)}
            })

            if membership:
                return user
        except Exception:
            pass

        # Migration fallback: check users.is_prime for whisked_words
        if business_id == "whisked_words" and user.get("is_prime") is True:
            return user

        # No active membership
        raise HTTPException(
            status_code=403,
            detail={
                "error": "Prime subscription required",
                "feature": "ai_chatbot",
                "upgrade_url": f"/prime?business_id={business_id}"
            }
        )

    # ------------------------------------------------------------------
    # Step 6: Any unrecognised role — denied
    # ------------------------------------------------------------------
    raise HTTPException(
        status_code=403,
        detail={"error": "Prime subscription required", "upgrade_url": "/prime"},
    )
