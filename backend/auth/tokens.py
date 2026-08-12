"""
JWT access token and refresh token management.

Handles minting, verification, and rotation of tokens.
Supports legacy session token acceptance during migration.
"""

import jwt
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, Tuple
from fastapi import HTTPException

from .config import get_jwt_secret, get_access_token_ttl, get_refresh_token_ttl, accept_legacy_session
from .sessions import SessionRecord, find_session_by_refresh_token, revoke_session, revoke_all_sessions


class TokenManager:
    """Manages JWT access tokens and refresh tokens."""
    
    def __init__(self, db):
        self.db = db
        self.jwt_secret = get_jwt_secret()
        self.access_ttl = get_access_token_ttl()
        self.refresh_ttl = get_refresh_token_ttl()
    
    def mint_access_token(
        self,
        user_id: str,
        session_id: str,
        additional_claims: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Mint a new JWT access token.
        
        Args:
            user_id: User ID
            session_id: Session ID
            additional_claims: Optional additional claims to include
        
        Returns:
            JWT access token string
        """
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=self.access_ttl)
        
        payload = {
            "sub": user_id,
            "sid": session_id,
            "type": "access",
            "iat": now.timestamp(),
            "exp": expires_at.timestamp(),
        }
        
        if additional_claims:
            payload.update(additional_claims)
        
        return jwt.encode(payload, self.jwt_secret, algorithm="HS256")
    
    def verify_access_token(self, token: str) -> Dict[str, Any]:
        """
        Verify JWT access token.
        
        Args:
            token: JWT token string
        
        Returns:
            Decoded token payload
        
        Raises:
            HTTPException: If token is invalid or expired
        """
        try:
            payload = jwt.decode(
                token,
                self.jwt_secret,
                algorithms=["HS256"],
                options={"require": ["sub", "sid", "type", "exp"]}
            )
            
            # Ensure it's an access token
            if payload.get("type") != "access":
                raise HTTPException(status_code=401, detail="Invalid token type")
            
            return payload
        
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.InvalidTokenError as e:
            raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")
    
    async def mint_refresh_token(
        self,
        user_id: str,
        device_info: Optional[Dict[str, Any]] = None,
        max_sessions: int = 5
    ) -> Tuple[str, str]:
        """
        Mint a new refresh token and create session.
        
        Args:
            user_id: User ID
            device_info: Optional device information
            max_sessions: Maximum concurrent sessions
        
        Returns:
            Tuple of (session_id, refresh_token)
        """
        from .sessions import create_session
        
        return await create_session(
            self.db,
            user_id,
            self.refresh_ttl,
            device_info,
            max_sessions
        )
    
    async def verify_refresh_token(self, refresh_token: str) -> Optional[SessionRecord]:
        """
        Verify refresh token and return session.
        
        Args:
            refresh_token: Refresh token string
        
        Returns:
            SessionRecord if valid, None otherwise
        """
        session = await find_session_by_refresh_token(self.db, refresh_token)
        return session
    
    async def rotate_refresh_token(
        self,
        old_refresh_token: str,
        device_info: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, str, str]:
        """
        Rotate refresh token (issue new one, revoke old).
        
        Implements refresh token rotation to detect token reuse.
        If an old token is reused, all tokens in the family are revoked.
        
        Args:
            old_refresh_token: Previous refresh token
            device_info: Optional device information
        
        Returns:
            Tuple of (session_id, new_refresh_token, access_token)
        
        Raises:
            HTTPException: If old token is invalid or reuse detected
        """
        # Verify old token
        old_session = await self.verify_refresh_token(old_refresh_token)
        if not old_session:
            raise HTTPException(status_code=401, detail="Invalid refresh token")
        
        # Revoke old session
        await revoke_session(self.db, old_session.session_id)
        
        # Issue new refresh token and access token
        session_id, new_refresh_token = await self.mint_refresh_token(
            old_session.user_id,
            device_info,
            max_sessions=5  # Could be configurable
        )
        
        access_token = self.mint_access_token(
            old_session.user_id,
            session_id
        )
        
        return session_id, new_refresh_token, access_token
    
    async def revoke_refresh_token_family(self, refresh_token: str) -> int:
        """
        Revoke all sessions for user when token reuse is detected.
        
        Args:
            refresh_token: The reused refresh token
        
        Returns:
            Number of sessions revoked
        """
        session = await self.verify_refresh_token(refresh_token)
        if not session:
            return 0
        
        revoked_count = await revoke_all_sessions(self.db, session.user_id)
        
        # Emit audit event for token reuse
        from .audit import write_audit_event, AuditEventType
        await write_audit_event(
            self.db,
            event_type=AuditEventType.TOKEN_REUSE_DETECTED,
            user_id=session.user_id,
            details={"session_id": session.session_id, "revoked_count": revoked_count},
            success=False
        )
        
        return revoked_count
    
    async def validate_legacy_session(self, session_token: str) -> Optional[Dict[str, Any]]:
        """
        Validate legacy session token during migration.
        
        Args:
            session_token: Legacy session token string
        
        Returns:
            User dict if valid, None otherwise
        """
        if not accept_legacy_session():
            return None
        
        # Look up legacy session
        session = await self.db.user_sessions.find_one(
            {"session_token": session_token},
            {"_id": 0}
        )
        
        if not session:
            return None
        
        # Check expiry
        expires_at = session.get("expires_at")
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at)
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        
        if expires_at < datetime.now(timezone.utc):
            return None
        
        # Get user
        user = await self.db.users.find_one(
            {"user_id": session["user_id"]},
            {"_id": 0}
        )
        
        return user


# Convenience functions for backward compatibility
def mint_access_token(
    user_id: str,
    session_id: str,
    additional_claims: Optional[Dict[str, Any]] = None
) -> str:
    """Mint a JWT access token (requires TokenManager instance)."""
    raise NotImplementedError("Use TokenManager.mint_access_token instead")


def verify_access_token(token: str, db) -> Dict[str, Any]:
    """Verify a JWT access token (requires TokenManager instance)."""
    manager = TokenManager(db)
    return manager.verify_access_token(token)


async def mint_refresh_token(
    db,
    user_id: str,
    device_info: Optional[Dict[str, Any]] = None,
    max_sessions: int = 5
) -> Tuple[str, str]:
    """Mint a refresh token (requires TokenManager instance)."""
    manager = TokenManager(db)
    return await manager.mint_refresh_token(user_id, device_info, max_sessions)


async def verify_refresh_token(db, refresh_token: str) -> Optional[SessionRecord]:
    """Verify a refresh token (requires TokenManager instance)."""
    manager = TokenManager(db)
    return await manager.verify_refresh_token(refresh_token)


async def rotate_refresh_token(
    db,
    old_refresh_token: str,
    device_info: Optional[Dict[str, Any]] = None
) -> Tuple[str, str, str]:
    """Rotate a refresh token (requires TokenManager instance)."""
    manager = TokenManager(db)
    return await manager.rotate_refresh_token(old_refresh_token, device_info)


async def validate_legacy_session(db, session_token: str) -> Optional[Dict[str, Any]]:
    """Validate a legacy session token (requires TokenManager instance)."""
    manager = TokenManager(db)
    return await manager.validate_legacy_session(session_token)
