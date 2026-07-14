"""
ai-chatbot/services/session_manager.py

Session CRUD for the ``chat_sessions`` MongoDB collection and a lightweight
``user_preferences`` look-up for personalisation.

Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SESSION_TIMEOUT_MINUTES: int = 30
MAX_TURNS: int = 20
KEEP_RECENT_TURNS: int = 10


# ---------------------------------------------------------------------------
# Index creation (call once at startup from main.py)
# ---------------------------------------------------------------------------


async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    """Create required indexes on ``chat_sessions`` idempotently.

    Indexes created:
    - ``{session_id: 1}`` — unique, for fast session lookups.
    - ``{last_active: 1}`` — TTL index; MongoDB auto-expires documents whose
      ``last_active`` is more than 1800 seconds (30 min) old.

    Using ``background=True`` (motor / pymongo ≤ 4 alias) ensures the
    operation is non-blocking on existing collections.
    """
    collection = db["chat_sessions"]
    await collection.create_index(
        [("session_id", 1)],
        unique=True,
        name="session_id_unique",
        background=True,
    )
    await collection.create_index(
        [("last_active", 1)],
        expireAfterSeconds=SESSION_TIMEOUT_MINUTES * 60,  # 1800
        name="last_active_ttl",
        background=True,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utcnow() -> datetime:
    """Return the current UTC time as a timezone-aware datetime."""
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    """Serialise a datetime to ISO 8601 UTC string (e.g. ``2024-01-01T12:00:00+00:00``)."""
    return dt.isoformat()


def _truncate_turns(turns: list) -> list:
    """Enforce the 20-turn truncation rule (Requirement 5.2).

    Keeps ``turns[0]`` (the system message) plus the 10 most recent turns
    whenever the list exceeds MAX_TURNS (20).
    """
    if len(turns) > MAX_TURNS:
        return [turns[0]] + turns[-KEEP_RECENT_TURNS:]
    return turns


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def create_session(
    db: AsyncIOMotorDatabase,
    business_id: str,
    user_id: Optional[str] = None,
) -> dict:
    """Create a new chat session document and persist it to MongoDB.

    The session is initialised with an empty ``turns`` list (the first
    element will be the system prompt, inserted by the caller after
    generating the business-specific prompt).

    Args:
        db:          Motor async database object.
        business_id: Business context for the session.
        user_id:     Optional authenticated user ID; ``None`` for anonymous.

    Returns:
        The newly created session document (Python dict, without ``_id``).
    """
    now = _utcnow()
    session: dict = {
        "session_id": str(uuid.uuid4()),
        "business_id": business_id,
        "user_id": user_id,
        "turns": [],                      # Caller appends system-prompt turn
        "active_filters": {},
        "recommendation_rationales": {},
        "created_at": _iso(now),
        "last_active": _iso(now),
    }
    await db["chat_sessions"].insert_one({**session})  # insert a copy so _id stays in DB only
    return session


async def load_session(
    db: AsyncIOMotorDatabase,
    session_id: str,
) -> Optional[dict]:
    """Load a session by ``session_id`` if it is still active.

    A session is considered expired when its ``last_active`` timestamp is
    more than 30 minutes ago (Requirement 5.6).  In that case — or when the
    document does not exist — ``None`` is returned so the caller can create
    a fresh session.

    Args:
        db:         Motor async database object.
        session_id: UUID string of the session to load.

    Returns:
        The session document (without ``_id``) or ``None``.
    """
    doc = await db["chat_sessions"].find_one(
        {"session_id": session_id},
        {"_id": 0},  # Requirement 9.5: never expose _id
    )
    if doc is None:
        return None

    # Parse last_active — stored as ISO 8601 string
    last_active_raw = doc.get("last_active")
    if last_active_raw is None:
        return None

    last_active: datetime = datetime.fromisoformat(str(last_active_raw))
    # Ensure timezone-aware for comparison
    if last_active.tzinfo is None:
        last_active = last_active.replace(tzinfo=timezone.utc)

    expiry_threshold = _utcnow() - timedelta(minutes=SESSION_TIMEOUT_MINUTES)
    if last_active < expiry_threshold:
        # Expired — caller must create a new session (Req 5.6)
        return None

    return doc


async def save_session(
    db: AsyncIOMotorDatabase,
    session: dict,
) -> None:
    """Upsert the session document, applying the truncation rule first.

    Updated fields on upsert:
    - ``turns``                     (after truncation if needed)
    - ``active_filters``
    - ``recommendation_rationales``
    - ``last_active``               (refreshed to now)

    Truncation rule (Requirement 5.2): when ``len(turns) > 20``, keep
    ``turns[0]`` (system message) + ``turns[-10:]`` (10 most recent).

    Args:
        db:      Motor async database object.
        session: The in-memory session dict (must contain ``session_id``).
    """
    turns = _truncate_turns(list(session.get("turns", [])))

    await db["chat_sessions"].update_one(
        {"session_id": session["session_id"]},
        {
            "$set": {
                "turns": turns,
                "active_filters": session.get("active_filters", {}),
                "recommendation_rationales": session.get("recommendation_rationales", {}),
                "last_active": _iso(_utcnow()),
            }
        },
        upsert=True,
    )
    # Keep the in-memory copy consistent with the persisted state
    session["turns"] = turns


async def clear_session(
    db: AsyncIOMotorDatabase,
    session_id: str,
) -> None:
    """Delete a session by ``session_id``.

    Raises:
        HTTPException(400): if no document with the given ``session_id``
            exists in the collection (Requirement 5.5 / API spec).
    """
    result = await db["chat_sessions"].delete_one({"session_id": session_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=400, detail="Session not found")


async def get_user_preferences(
    db: AsyncIOMotorDatabase,
    user_id: str,
) -> Optional[dict]:
    """Return the ``user_preferences`` document for a user if it has not expired.

    The document is valid when ``expires_at > now(UTC)``.  The ``_id``
    field is excluded from the result (Requirement 9.5).

    Args:
        db:      Motor async database object.
        user_id: The authenticated user's ID.

    Returns:
        The preference document or ``None`` if absent or expired.
    """
    now_iso = _iso(_utcnow())
    doc = await db["user_preferences"].find_one(
        {
            "user_id": user_id,
            "expires_at": {"$gt": now_iso},
        },
        {"_id": 0},
    )
    return doc
