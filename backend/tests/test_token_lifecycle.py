"""
Integration tests for token lifecycle.

Tests for:
- JWT access token expiration
- Refresh token rotation
- Token reuse detection and family revocation
- Legacy session acceptance (with AUTH_ACCEPT_LEGACY_SESSION flag)
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock, MagicMock
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from auth.tokens import TokenManager
from auth.sessions import SessionRecord, hash_refresh_token


@pytest.fixture
def mock_db():
    """Mock MongoDB database."""
    db = Mock()
    db.user_sessions = Mock()
    db.users = Mock()
    return db


@pytest.fixture
def token_manager(mock_db):
    """Create TokenManager with mock DB."""
    import os
    os.environ["JWT_SECRET"] = "test_secret_key_32_characters_long"
    return TokenManager(mock_db)


class TestTokenLifecycle:
    """Test token lifecycle operations."""
    
    @pytest.mark.asyncio
    async def test_access_token_expiration(self, token_manager):
        """Test that expired access tokens are rejected."""
        # Create a token with very short TTL
        token_manager.access_ttl = 1  # 1 second
        token = token_manager.mint_access_token("user_123", "sess_456")
        
        # Should work immediately
        payload = token_manager.verify_access_token(token)
        assert payload["sub"] == "user_123"
        
        # Wait for expiration
        import asyncio
        await asyncio.sleep(2)
        
        # Should fail after expiration
        with pytest.raises(Exception):  # HTTPException for expired token
            token_manager.verify_access_token(token)
    
    @pytest.mark.asyncio
    async def test_refresh_token_rotation(self, token_manager, mock_db):
        """Test refresh token rotation on successful refresh."""
        # Mock existing session
        old_session = SessionRecord(
            session_id="sess_old",
            user_id="user_123",
            refresh_token_hash=hash_refresh_token("rt_old_token"),
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        
        mock_db.user_sessions.find_one = AsyncMock(return_value=old_session.to_dict())
        mock_db.user_sessions.delete_one = AsyncMock()
        mock_db.user_sessions.insert_one = AsyncMock()
        mock_db.users.find_one = AsyncMock(return_value={"user_id": "user_123", "role": "customer"})
        
        # Rotate token
        session_id, new_refresh, access_token = await token_manager.rotate_refresh_token(
            "rt_old_token",
            {"ip_address": "1.2.3.4"}
        )
        
        # Verify new tokens were issued
        assert session_id != "sess_old"
        assert new_refresh != "rt_old_token"
        assert access_token is not None
        
        # Verify old session was revoked
        mock_db.user_sessions.delete_one.assert_called_once_with({"session_id": "sess_old"})
        
        # Verify new session was created
        mock_db.user_sessions.insert_one.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_token_reuse_detection(self, token_manager, mock_db):
        """Test that token reuse revokes the entire token family."""
        # Mock existing session
        session = SessionRecord(
            session_id="sess_family",
            user_id="user_123",
            refresh_token_hash=hash_refresh_token("rt_original"),
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        
        mock_db.user_sessions.find_one = AsyncMock(return_value=session.to_dict())
        mock_db.user_sessions.delete_many = AsyncMock(return_value=MagicMock(deleted_count=3))
        
        # Simulate token reuse detection
        revoked_count = await token_manager.revoke_refresh_token_family("rt_original")
        
        # Should revoke all sessions for user
        assert revoked_count == 3
        mock_db.user_sessions.delete_many.assert_called_once_with({"user_id": "user_123"})
    
    @pytest.mark.asyncio
    async def test_invalid_refresh_token(self, token_manager, mock_db):
        """Test that invalid refresh tokens are rejected."""
        mock_db.user_sessions.find_one = AsyncMock(return_value=None)
        
        with pytest.raises(Exception):  # HTTPException
            await token_manager.verify_refresh_token("invalid_refresh_token")
    
    @pytest.mark.asyncio
    async def test_legacy_session_acceptance_enabled(self, token_manager, mock_db):
        """Test legacy session acceptance when flag is enabled."""
        import os
        os.environ["AUTH_ACCEPT_LEGACY_SESSION"] = "true"
        
        # Mock legacy session
        mock_db.user_sessions.find_one = AsyncMock(return_value={
            "session_token": "token_legacy",
            "user_id": "user_123",
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
        })
        mock_db.users.find_one = AsyncMock(return_value={
            "user_id": "user_123",
            "email": "test@example.com",
            "role": "customer"
        })
        
        user = await token_manager.validate_legacy_session("token_legacy")
        
        assert user is not None
        assert user["user_id"] == "user_123"
    
    @pytest.mark.asyncio
    async def test_legacy_session_acceptance_disabled(self, token_manager, mock_db):
        """Test legacy session rejection when flag is disabled."""
        import os
        os.environ["AUTH_ACCEPT_LEGACY_SESSION"] = "false"
        
        # Even with valid session, should return None when flag is disabled
        user = await token_manager.validate_legacy_session("token_legacy")
        
        assert user is None
    
    @pytest.mark.asyncio
    async def test_expired_legacy_session(self, token_manager, mock_db):
        """Test that expired legacy sessions are rejected."""
        import os
        os.environ["AUTH_ACCEPT_LEGACY_SESSION"] = "true"
        
        # Mock expired session
        mock_db.user_sessions.find_one = AsyncMock(return_value={
            "session_token": "token_expired",
            "user_id": "user_123",
            "expires_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
        })
        
        user = await token_manager.validate_legacy_session("token_expired")
        
        assert user is None  # Expired sessions should be rejected


class TestTokenSecurity:
    """Test token security features."""
    
    def test_jwt_signature_validation(self, token_manager):
        """Test that JWT signature is validated."""
        # Create valid token
        valid_token = token_manager.mint_access_token("user_123", "sess_456")
        
        # Should verify successfully
        payload = token_manager.verify_access_token(valid_token)
        assert payload["sub"] == "user_123"
        
        # Tamper with token
        tampered_token = valid_token[:-5] + "ABCDE"
        
        # Should fail verification
        with pytest.raises(Exception):
            token_manager.verify_access_token(tampered_token)
    
    def test_access_token_claims(self, token_manager):
        """Test that access token contains required claims."""
        token = token_manager.mint_access_token("user_123", "sess_456")
        payload = token_manager.verify_access_token(token)
        
        # Check required claims
        assert "sub" in payload  # user_id
        assert "sid" in payload  # session_id
        assert "type" in payload
        assert payload["type"] == "access"
        assert "iat" in payload  # issued at
        assert "exp" in payload  # expiration
    
    def test_access_token_ttl(self, token_manager):
        """Test that access token TTL is respected."""
        # Set custom TTL
        token_manager.access_ttl = 300  # 5 minutes
        token = token_manager.mint_access_token("user_123", "sess_456")
        payload = token_manager.verify_access_token(token)
        
        # Check expiration is approximately 5 minutes from now
        exp_time = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        iat_time = datetime.fromtimestamp(payload["iat"], tz=timezone.utc)
        ttl_seconds = (exp_time - iat_time).total_seconds()
        
        assert 290 <= ttl_seconds <= 310  # Allow some tolerance


class TestConcurrentSessionLimit:
    """Test concurrent session limiting."""
    
    @pytest.mark.asyncio
    async def test_max_sessions_enforced(self, mock_db):
        """Test that concurrent session limit is enforced."""
        from auth.sessions import create_session, enforce_concurrent_limit
        
        # Mock existing sessions at limit
        mock_db.user_sessions.count_documents = AsyncMock(return_value=5)
        mock_db.user_sessions.find = MagicMock()
        mock_db.user_sessions.find.return_value.sort.return_value.to_list = AsyncMock(
            return_value [{"session_id": f"sess_{i}"} for i in range(5)]
        )
        mock_db.user_sessions.delete_one = AsyncMock()
        mock_db.user_sessions.insert_one = AsyncMock()
        
        # Create new session when at limit
        session_id, refresh_token = await create_session(
            mock_db,
            "user_123",
            604800,
            {"ip_address": "1.2.3.4"},
            max_sessions=5
        )
        
        # Should have deleted oldest session
        mock_db.user_sessions.delete_one.assert_called()
        
        # Should have created new session
        mock_db.user_sessions.insert_one.assert_called()
    
    @pytest.mark.asyncio
    async def test_oldest_session_evicted_first(self, mock_db):
        """Test that oldest sessions are evicted first."""
        from auth.sessions import enforce_concurrent_limit
        
        # Mock sessions with different timestamps
        sessions = [
            {"session_id": f"sess_{i}", "created_at": datetime.now(timezone.utc) - timedelta(days=i)}
            for i in range(5)
        ]
        
        mock_db.user_sessions.count_documents = AsyncMock(return_value=5)
        mock_db.user_sessions.find = MagicMock()
        mock_db.user_sessions.find.return_value.sort.return_value.to_list = AsyncMock(return_value=sessions)
        mock_db.user_sessions.delete_one = AsyncMock()
        
        await enforce_concurrent_limit(mock_db, "user_123", max_sessions=5)
        
        # Should delete the oldest session (sess_4 with earliest timestamp)
        mock_db.user_sessions.delete_one.assert_called_once_with({"session_id": "sess_4"})


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
