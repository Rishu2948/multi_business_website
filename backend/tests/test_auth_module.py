"""
Unit tests for Auth_Module components.

Tests for:
- RBAC helpers (role checking, business access)
- Session management (creation, validation, revocation, concurrent limits)
- Token lifecycle (JWT minting, verification, refresh rotation)
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock, MagicMock
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from auth.rbac import (
    Role,
    PRIVILEGED_ROLES,
    require_roles,
    check_business_access,
    require_business_access,
    is_privileged_role,
    get_role_level,
    has_higher_or_equal_privilege
)
from auth.sessions import (
    SessionRecord,
    hash_refresh_token,
    generate_session_id,
    generate_refresh_token,
    create_session,
    find_session,
    find_session_by_refresh_token,
    revoke_session,
    revoke_all_sessions,
    update_last_seen,
    enforce_concurrent_limit,
)
from auth.tokens import TokenManager


@pytest.fixture
def mock_db():
    """Mock MongoDB database."""
    db = Mock()
    db.user_sessions = Mock()
    db.users = Mock()
    return db


@pytest.fixture
def sample_user():
    """Sample user document."""
    return {
        "user_id": "user_123",
        "email": "test@example.com",
        "role": "business_admin",
        "business_access": [
            {"business_id": "whisked_words", "role": "business_admin", "assigned_at": datetime.now(timezone.utc)}
        ]
    }


@pytest.fixture
def sample_session():
    """Sample session record."""
    return SessionRecord(
        session_id="sess_abc123",
        user_id="user_123",
        refresh_token_hash=hash_refresh_token("rt_secret123"),
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        device_info={"ip_address": "1.2.3.4", "user_agent": "test"},
    )


# ============= RBAC Tests =============

class TestRBAC:
    """Test RBAC helpers."""
    
    def test_role_hierarchy(self):
        """Test role hierarchy levels."""
        assert get_role_level("customer") == 0
        assert get_role_level("delivery_agent") == 1
        assert get_role_level("staff") == 2
        assert get_role_level("business_admin") == 3
        assert get_role_level("super_admin") == 4
    
    def test_privileged_roles(self):
        """Test privileged role identification."""
        assert is_privileged_role("super_admin") == True
        assert is_privileged_role("business_admin") == True
        assert is_privileged_role("staff") == False
        assert is_privileged_role("customer") == False
    
    def test_check_business_access_super_admin(self):
        """Test super admin has access to all businesses."""
        user = {"role": "super_admin", "business_access": []}
        assert check_business_access(user, "any_business") == True
    
    def test_check_business_access_with_access(self):
        """Test user with business access."""
        user = {
            "role": "business_admin",
            "business_access": [{"business_id": "whisked_words"}]
        }
        assert check_business_access(user, "whisked_words") == True
        assert check_business_access(user, "other_business") == False
    
    def test_check_business_access_without_access(self):
        """Test user without business access."""
        user = {"role": "business_admin", "business_access": []}
        assert check_business_access(user, "whisked_words") == False
    
    def test_has_higher_or_equal_privilege(self):
        """Test privilege comparison."""
        assert has_higher_or_equal_privilege("super_admin", "staff") == True
        assert has_higher_or_equal_privilege("business_admin", "staff") == True
        assert has_higher_or_equal_privilege("staff", "staff") == True
        assert has_higher_or_equal_privilege("customer", "staff") == False
    
    @pytest.mark.asyncio
    async def test_require_roles_dependency(self):
        """Test require_roles FastAPI dependency."""
        require_roles_dep = require_roles(["business_admin", "super_admin"])
        
        # Should pass for allowed role
        user_admin = {"role": "business_admin"}
        role_checker = require_roles_dep()
        result = await role_checker(user_admin)
        assert result == user_admin
        
        # Should fail for disallowed role
        user_customer = {"role": "customer"}
        role_checker = require_roles_dep()
        with pytest.raises(Exception):  # HTTPException
            await role_checker(user_customer)


# ============= Session Tests =============

class TestSessions:
    """Test session management."""
    
    def test_hash_refresh_token(self):
        """Test refresh token hashing."""
        token = "rt_secret123"
        hash1 = hash_refresh_token(token)
        hash2 = hash_refresh_token(token)
        assert hash1 == hash2
        assert hash1 != token
        assert len(hash1) == 64  # SHA-256 hex length
    
    def test_generate_session_id(self):
        """Test session ID generation."""
        session_id = generate_session_id()
        assert session_id.startswith("sess_")
        assert len(session_id) > 10
        
        # Should be unique
        session_id2 = generate_session_id()
        assert session_id != session_id2
    
    def test_generate_refresh_token(self):
        """Test refresh token generation."""
        token = generate_refresh_token()
        assert token.startswith("rt_")
        assert len(token) > 40
        
        # Should be unique
        token2 = generate_refresh_token()
        assert token != token2
    
    def test_session_record_creation(self):
        """Test SessionRecord creation."""
        session = SessionRecord(
            session_id="sess_123",
            user_id="user_123",
            refresh_token_hash="hash123",
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        
        assert session.session_id == "sess_123"
        assert session.user_id == "user_123"
        assert session.mfa_verified == False
    
    def test_session_record_to_dict(self):
        """Test SessionRecord serialization."""
        session = SessionRecord(
            session_id="sess_123",
            user_id="user_123",
            refresh_token_hash="hash123",
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        
        data = session.to_dict()
        assert data["session_id"] == "sess_123"
        assert data["user_id"] == "user_123"
        assert "refresh_token_hash" in data
    
    def test_session_record_from_dict(self):
        """Test SessionRecord deserialization."""
        data = {
            "session_id": "sess_123",
            "user_id": "user_123",
            "refresh_token_hash": "hash123",
            "expires_at": datetime.now(timezone.utc) + timedelta(days=7),
            "device_info": {},
            "mfa_verified": False,
            "created_at": datetime.now(timezone.utc),
            "last_seen_at": datetime.now(timezone.utc),
        }
        
        session = SessionRecord.from_dict(data)
        assert session.session_id == "sess_123"
        assert session.user_id == "user_123"
    
    @pytest.mark.asyncio
    async def test_create_session(self, mock_db):
        """Test session creation."""
        mock_db.user_sessions.insert_one = AsyncMock()
        mock_db.user_sessions.find_one = AsyncMock(return_value=None)
        
        session_id, refresh_token = await create_session(
            mock_db,
            "user_123",
            604800,  # 7 days
            {"ip_address": "1.2.3.4"},
            max_sessions=5
        )
        
        assert session_id.startswith("sess_")
        assert refresh_token.startswith("rt_")
        mock_db.user_sessions.insert_one.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_enforce_concurrent_limit(self, mock_db):
        """Test concurrent session limit enforcement."""
        # Mock existing sessions
        mock_db.user_sessions.count_documents = AsyncMock(return_value=5)
        mock_db.user_sessions.find = MagicMock()
        mock_db.user_sessions.find.return_value.sort.return_value.to_list = AsyncMock(
            return_value=[{"session_id": f"sess_{i}"} for i in range(5)]
        )
        mock_db.user_sessions.delete_one = AsyncMock()
        
        await enforce_concurrent_limit(mock_db, "user_123", max_sessions=5)
        
        # Should delete oldest session
        mock_db.user_sessions.delete_one.assert_called()
    
    @pytest.mark.asyncio
    async def test_revoke_all_sessions(self, mock_db):
        """Test revoking all user sessions."""
        mock_db.user_sessions.delete_many = AsyncMock(return_value=MagicMock(deleted_count=3))
        
        count = await revoke_all_sessions(mock_db, "user_123")
        
        assert count == 3
        mock_db.user_sessions.delete_many.assert_called_once_with({"user_id": "user_123"})


# ============= Token Tests =============

class TestTokens:
    """Test token management."""
    
    @pytest.fixture
    def token_manager(self, mock_db):
        """Create TokenManager with mock DB."""
        # Set required env var
        import os
        os.environ["JWT_SECRET"] = "test_secret_key_32_characters_long"
        return TokenManager(mock_db)
    
    def test_mint_access_token(self, token_manager):
        """Test JWT access token minting."""
        token = token_manager.mint_access_token("user_123", "sess_456")
        
        assert isinstance(token, str)
        assert len(token) > 50  # JWT is substantial length
    
    def test_verify_access_token(self, token_manager):
        """Test JWT access token verification."""
        token = token_manager.mint_access_token("user_123", "sess_456")
        payload = token_manager.verify_access_token(token)
        
        assert payload["sub"] == "user_123"
        assert payload["sid"] == "sess_456"
        assert payload["type"] == "access"
        assert "exp" in payload
    
    def test_verify_invalid_token(self, token_manager):
        """Test verification of invalid token."""
        with pytest.raises(Exception):  # HTTPException
            token_manager.verify_access_token("invalid_token_string")
    
    def test_refresh_token_rotation(self, token_manager, mock_db):
        """Test refresh token rotation."""
        # Mock session lookup
        mock_session = SessionRecord(
            session_id="sess_old",
            user_id="user_123",
            refresh_token_hash=hash_refresh_token("rt_old"),
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        
        mock_db.user_sessions.find_one = AsyncMock(return_value=mock_session.to_dict())
        mock_db.user_sessions.delete_one = AsyncMock()
        mock_db.user_sessions.insert_one = AsyncMock()
        mock_db.users.find_one = AsyncMock(return_value={"user_id": "user_123", "role": "customer"})
        
        session_id, new_refresh, access_token = token_manager.rotate_refresh_token(
            "rt_old",
            {"ip_address": "1.2.3.4"}
        )
        
        assert session_id.startswith("sess_")
        assert new_refresh.startswith("rt_")
        assert access_token is not None
        assert session_id != "sess_old"  # New session created
        assert new_refresh != "rt_old"  # New token issued


# ============= Integration Tests =============

class TestAuthIntegration:
    """Integration tests for auth workflows."""
    
    @pytest.mark.asyncio
    async def test_login_session_revocation_on_role_change(self, mock_db):
        """Test that sessions are revoked when role changes."""
        mock_db.users.update_one = AsyncMock()
        mock_db.user_sessions.delete_many = AsyncMock(return_value=MagicMock(deleted_count=2))
        
        # Simulate role change
        from auth.sessions import revoke_all_sessions
        revoked_count = await revoke_all_sessions(mock_db, "user_123")
        
        assert revoked_count == 2
        mock_db.user_sessions.delete_many.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_business_access_denial_for_non_super_admin(self):
        """Test business access denial for non-super-admin."""
        user = {
            "role": "business_admin",
            "business_access": [{"business_id": "whisked_words"}]
        }
        
        # Should have access to own business
        assert check_business_access(user, "whisked_words") == True
        
        # Should not have access to other business
        assert check_business_access(user, "other_business") == False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
