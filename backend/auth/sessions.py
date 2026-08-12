"""
Session management for refresh tokens and legacy sessions.

Handles session creation, validation, revocation, and concurrent session limits.
Session records are stored in MongoDB with TTL for automatic expiration.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
import hashlib
import secrets
import uuid


class SessionRecord:
    """Session record data structure."""
    
    def __init__(
        self,
        session_id: str,
        user_id: str,
        refresh_token_hash: str,
        expires_at: datetime,
        device_info: Optional[Dict[str, Any]] = None,
        mfa_verified: bool = False,
        created_at: Optional[datetime] = None,
        last_seen_at: Optional[datetime] = None,
    ):
        self.session_id = session_id
        self.user_id = user_id
        self.refresh_token_hash = refresh_token_hash
        self.expires_at = expires_at
        self.device_info = device_info or {}
        self.mfa_verified = mfa_verified
        self.created_at = created_at or datetime.now(timezone.utc)
        self.last_seen_at = last_seen_at or datetime.now(timezone.utc)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for MongoDB storage."""
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "refresh_token_hash": self.refresh_token_hash,
            "expires_at": self.expires_at,
            "device_info": self.device_info,
            "mfa_verified": self.mfa_verified,
            "created_at": self.created_at,
            "last_seen_at": self.last_seen_at,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionRecord":
        """Create from MongoDB document."""
        return cls(
            session_id=data["session_id"],
            user_id=data["user_id"],
            refresh_token_hash=data["refresh_token_hash"],
            expires_at=data["expires_at"],
            device_info=data.get("device_info", {}),
            mfa_verified=data.get("mfa_verified", False),
            created_at=data.get("created_at"),
            last_seen_at=data.get("last_seen_at"),
        )


def hash_refresh_token(token: str) -> str:
    """Hash refresh token for storage (SHA-256)."""
    return hashlib.sha256(token.encode()).hexdigest()


def generate_session_id() -> str:
    """Generate unique session ID."""
    return f"sess_{uuid.uuid4().hex}"


def generate_refresh_token() -> str:
    """Generate cryptographically secure refresh token."""
    return f"rt_{secrets.token_urlsafe(32)}"


async def create_session(
    db,
    user_id: str,
    ttl_seconds: int,
    device_info: Optional[Dict[str, Any]] = None,
    max_sessions: int = 5,
) -> tuple[str, str]:
    """
    Create a new session for a user.
    
    Args:
        db: MongoDB database instance
        user_id: User ID to create session for
        ttl_seconds: Time-to-live for session in seconds
        device_info: Optional device/browser information
        max_sessions: Maximum concurrent sessions (enforced by evicting oldest)
    
    Returns:
        Tuple of (session_id, refresh_token)
    """
    # Generate session and token
    session_id = generate_session_id()
    refresh_token = generate_refresh_token()
    refresh_token_hash = hash_refresh_token(refresh_token)
    
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
    
    # Create session record
    session = SessionRecord(
        session_id=session_id,
        user_id=user_id,
        refresh_token_hash=refresh_token_hash,
        expires_at=expires_at,
        device_info=device_info,
    )
    
    # Enforce concurrent session limit
    await enforce_concurrent_limit(db, user_id, max_sessions)
    
    # Insert session
    await db.user_sessions.insert_one(session.to_dict())
    
    return session_id, refresh_token


async def find_session(db, session_id: str) -> Optional[SessionRecord]:
    """
    Find session by ID.
    
    Args:
        db: MongoDB database instance
        session_id: Session ID to find
    
    Returns:
        SessionRecord if found and not expired, None otherwise
    """
    session_data = await db.user_sessions.find_one({"session_id": session_id})
    
    if not session_data:
        return None
    
    # Check expiry
    expires_at = session_data.get("expires_at")
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    
    if expires_at < datetime.now(timezone.utc):
        # Clean up expired session
        await db.user_sessions.delete_one({"session_id": session_id})
        return None
    
    return SessionRecord.from_dict(session_data)


async def find_session_by_refresh_token(db, refresh_token: str) -> Optional[SessionRecord]:
    """
    Find session by refresh token (using hash lookup).
    
    Args:
        db: MongoDB database instance
        refresh_token: Refresh token to look up
    
    Returns:
        SessionRecord if found and not expired, None otherwise
    """
    refresh_token_hash = hash_refresh_token(refresh_token)
    session_data = await db.user_sessions.find_one({"refresh_token_hash": refresh_token_hash})
    
    if not session_data:
        return None
    
    # Check expiry
    expires_at = session_data.get("expires_at")
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    
    if expires_at < datetime.now(timezone.utc):
        # Clean up expired session
        await db.user_sessions.delete_one({"session_id": session_data["session_id"]})
        return None
    
    return SessionRecord.from_dict(session_data)


async def revoke_session(db, session_id: str) -> bool:
    """
    Revoke a specific session.
    
    Args:
        db: MongoDB database instance
        session_id: Session ID to revoke
    
    Returns:
        True if session was revoked, False if not found
    """
    # Get session info before deletion for audit
    session = await db.user_sessions.find_one({"session_id": session_id})
    user_id = session.get("user_id") if session else None
    
    result = await db.user_sessions.delete_one({"session_id": session_id})
    
    # Emit audit event if session was revoked
    if result.deleted_count > 0 and user_id:
        from .audit import write_audit_event, AuditEventType
        await write_audit_event(
            db,
            event_type=AuditEventType.SESSION_REVOKED,
            user_id=user_id,
            details={"session_id": session_id},
            success=True
        )
    
    return result.deleted_count > 0


async def revoke_all_sessions(db, user_id: str) -> int:
    """
    Revoke all sessions for a user.
    
    This should be called when:
    - User role changes
    - Business access changes
    - Security incident
    - User requests logout from all devices
    
    Args:
        db: MongoDB database instance
        user_id: User ID to revoke all sessions for
    
    Returns:
        Number of sessions revoked
    """
    result = await db.user_sessions.delete_many({"user_id": user_id})
    return result.deleted_count


async def update_last_seen(db, session_id: str) -> bool:
    """
    Update last_seen_at timestamp for a session.
    
    Args:
        db: MongoDB database instance
        session_id: Session ID to update
    
    Returns:
        True if updated, False if session not found
    """
    result = await db.user_sessions.update_one(
        {"session_id": session_id},
        {"$set": {"last_seen_at": datetime.now(timezone.utc)}}
    )
    return result.modified_count > 0


async def enforce_concurrent_limit(db, user_id: str, max_sessions: int) -> None:
    """
    Enforce maximum concurrent sessions by evicting oldest sessions.
    
    Args:
        db: MongoDB database instance
        user_id: User ID to check
        max_sessions: Maximum allowed sessions
    """
    # Count current active sessions
    count = await db.user_sessions.count_documents({"user_id": user_id})
    
    if count >= max_sessions:
        # Find and delete oldest session(s)
        oldest_sessions = await db.user_sessions.find(
            {"user_id": user_id}
        ).sort("created_at", 1).to_list(count - max_sessions + 1)
        
        for session in oldest_sessions:
            await db.user_sessions.delete_one({"session_id": session["session_id"]})


async def ensure_session_indexes(db) -> None:
    """
    Create necessary indexes for sessions collection.
    
    Should be called on application startup.
    """
    # TTL index on expires_at for automatic cleanup
    await db.user_sessions.create_index(
        [("expires_at", 1)],
        expireAfterSeconds=0,
        background=True,
        name="user_sessions_ttl_expires_at"
    )
    
    # Index for user lookups
    await db.user_sessions.create_index(
        [("user_id", 1)],
        background=True,
        name="user_sessions_user_id"
    )
    
    # Index for refresh token hash lookups
    await db.user_sessions.create_index(
        [("refresh_token_hash", 1)],
        background=True,
        name="user_sessions_refresh_token_hash"
    )
