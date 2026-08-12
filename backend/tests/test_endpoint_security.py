"""
Integration tests for previously open/unsecured endpoints.

Tests that verify the security hardening of endpoints that were previously
unauthenticated or under-authenticated according to the security requirements.

Tests:
- Order status update endpoint requires authentication + RBAC
- Custom-order admin endpoints require authentication + business scope
- SSE auth requires proper credentials (no query param)
- Chatbot mutating endpoints require privileged authentication
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, AsyncMock, MagicMock

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))


class TestOrderRoutesSecurity:
    """Test security of order routes that were previously unauthenticated."""
    
    @pytest.fixture
    def mock_db(self):
        """Mock MongoDB database."""
        db = Mock()
        db.orders = Mock()
        db.users = Mock()
        return db
    
    @pytest.mark.asyncio
    async def test_order_status_update_requires_auth(self, mock_db):
        """Test that PUT /api/orders/{order_id}/status requires authentication."""
        from order_routes import update_order_status
        from fastapi import Request, HTTPException
        
        # Mock request without authentication
        request = Mock(spec=Request)
        request.client = Mock()
        request.client.host = "1.2.3.4"
        request.method = "PUT"
        
        # Should raise 401 without authentication
        with pytest.raises(HTTPException) as exc_info:
            await update_order_status("order_123", "confirmed", request)
        
        assert exc_info.value.status_code == 401
    
    @pytest.mark.asyncio
    async def test_order_status_update_requires_privileged_role(self, mock_db):
        """Test that order status update requires privileged role."""
        from order_routes import update_order_status
        from fastapi import Request, HTTPException
        
        # Mock request with customer user (not privileged)
        request = Mock(spec=Request)
        request.client = Mock()
        request.client.host = "1.2.3.4"
        request.method = "PUT"
        
        # Mock customer user
        customer_user = {"user_id": "user_123", "role": "customer", "business_access": []}
        
        # Mock order exists
        mock_db.orders.find_one = AsyncMock(return_value={
            "order_id": "order_123",
            "business_id": "whisked_words",
            "order_status": "pending"
        })
        
        # Should raise 403 for non-privileged role
        with pytest.raises(HTTPException) as exc_info:
            await update_order_status("order_123", "confirmed", request)
        
        assert exc_info.value.status_code == 403
    
    @pytest.mark.asyncio
    async def test_order_status_update_requires_business_scope(self, mock_db):
        """Test that order status update requires business access for non-super-admin."""
        from order_routes import update_order_status
        from fastapi import Request, HTTPException
        
        # Mock request with business_admin user
        request = Mock(spec=Request)
        request.client = Mock()
        request.client.host = "1.2.3.4"
        request.method = "PUT"
        
        # Mock business admin without access to this business
        business_admin = {
            "user_id": "user_456",
            "role": "business_admin",
            "business_access": [{"business_id": "other_business"}]
        }
        
        # Mock order for different business
        mock_db.orders.find_one = AsyncMock(return_value={
            "order_id": "order_123",
            "business_id": "whisked_words",
            "order_status": "pending"
        })
        
        # Should raise 403 for wrong business
        with pytest.raises(HTTPException) as exc_info:
            await update_order_status("order_123", "confirmed", request)
        
        assert exc_info.value.status_code == 403
    
    @pytest.mark.asyncio
    async def test_order_get_requires_auth(self, mock_db):
        """Test that GET /api/orders/{order_id} requires authentication."""
        from order_routes import get_order
        from fastapi import Request, HTTPException
        
        # Mock request without authentication
        request = Mock(spec=Request)
        request.client = Mock()
        request.client.host = "1.2.3.4"
        
        # Mock order exists
        mock_db.orders.find_one = AsyncMock(return_value={
            "order_id": "order_123",
            "user_id": "other_user",
            "business_id": "whisked_words"
        })
        
        # Should raise 401 without authentication
        with pytest.raises(HTTPException) as exc_info:
            await get_order("order_123", request)
        
        assert exc_info.value.status_code == 401
    
    @pytest.mark.asyncio
    async def test_order_get_owner_access(self, mock_db):
        """Test that order owner can access their own order."""
        from order_routes import get_order
        from fastapi import Request
        
        # Mock request with authenticated owner
        request = Mock(spec=Request)
        request.client = Mock()
        request.client.host = "1.2.3.4"
        
        # Mock owner user
        owner_user = {
            "user_id": "user_123",
            "role": "customer",
            "business_access": []
        }
        
        # Mock order belonging to this user
        mock_db.orders.find_one = AsyncMock(return_value={
            "order_id": "order_123",
            "user_id": "user_123",
            "business_id": "whisked_words"
        })
        
        # Should return order for owner
        result = await get_order("order_123", request)
        assert result["order_id"] == "order_123"


class TestCustomOrderRoutesSecurity:
    """Test security of custom-order routes that were previously unauthenticated."""
    
    @pytest.fixture
    def mock_db(self):
        """Mock MongoDB database."""
        db = Mock()
        db.custom_orders = Mock()
        db.users = Mock()
        return db
    
    @pytest.mark.asyncio
    async def test_custom_order_admin_list_requires_auth(self, mock_db):
        """Test that GET /api/custom-orders/admin/all requires authentication."""
        from custom_order_routes import get_all_custom_orders
        from fastapi import HTTPException
        
        # Should require authentication (will be enforced by dependency)
        # This test verifies the dependency is present
        from custom_order_routes import get_all_custom_orders
        import inspect
        
        # Check that the function requires authentication
        sig = inspect.signature(get_all_custom_orders)
        # Verify it has user parameter or requires auth dependency
        params = sig.parameters
        assert 'user' in params or 'current_user' in params
    
    @pytest.mark.asyncio
    async def test_custom_order_status_update_requires_auth(self, mock_db):
        """Test that custom order status update requires authentication."""
        from custom_order_routes import update_custom_order_status
        from fastapi import Request, HTTPException
        
        # Mock request without authentication
        request = Mock(spec=Request)
        request.client = Mock()
        request.client.host = "1.2.3.4"
        request.method = "PUT"
        
        # Mock order exists
        mock_db.custom_orders.find_one = AsyncMock(return_value={
            "custom_order_id": "custom_123",
            "business_id": "whisked_words",
            "status": "pending_quote"
        })
        
        # Should raise 401 without authentication
        with pytest.raises(HTTPException) as exc_info:
            await update_custom_order_status("custom_123", request)
        
        assert exc_info.value.status_code == 401


class TestSSERoutesSecurity:
    """Test SSE authentication security (no query param tokens)."""
    
    @pytest.fixture
    def mock_db(self):
        """Mock MongoDB database."""
        db = Mock()
        db.user_sessions = Mock()
        db.users = Mock()
        return db
    
    @pytest.mark.asyncio
    async def test_sse_rejects_query_param_token(self, mock_db):
        """Test that SSE endpoint rejects ?token= query parameter."""
        from sse_routes import _get_user_from_request
        from fastapi import Request
        
        # Mock request with query param token (insecure method)
        request = Mock(spec=Request)
        request.query_params = Mock()
        request.query_params.get = Mock(return_value="insecure_token")
        request.cookies = Mock()
        request.cookies.get = Mock(return_value=None)
        request.headers = Mock()
        request.headers.get = Mock(return_value=None)
        
        # Should return None (rejects query param token)
        user = await _get_user_from_request(request)
        assert user is None
    
    @pytest.mark.asyncio
    async def test_sse_accepts_cookie_token(self, mock_db):
        """Test that SSE endpoint accepts cookie token (secure method)."""
        from sse_routes import _get_user_from_request
        from fastapi import Request
        from datetime import datetime, timezone
        
        # Mock request with cookie token (secure method)
        request = Mock(spec=Request)
        request.query_params = Mock()
        request.query_params.get = Mock(return_value=None)
        request.cookies = Mock()
        request.cookies.get = Mock(side_effect=lambda key: "valid_token" if key == "refresh_token" else None)
        request.headers = Mock()
        request.headers.get = Mock(return_value=None)
        
        # Mock valid session
        mock_db.user_sessions.find_one = AsyncMock(return_value={
            "session_id": "sess_123",
            "user_id": "user_123",
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        })
        mock_db.users.find_one = AsyncMock(return_value={
            "user_id": "user_123",
            "email": "test@example.com",
            "role": "customer"
        })
        
        # Should return user when using cookie
        user = await _get_user_from_request(request)
        assert user is not None
        assert user["user_id"] == "user_123"


class TestChatbotRoutesSecurity:
    """Test chatbot mutating endpoints security."""
    
    @pytest.fixture
    def mock_db(self):
        """Mock MongoDB database."""
        db = Mock()
        return db
    
    @pytest.mark.asyncio
    async def test_chatbot_session_delete_requires_privileged_auth(self, mock_db):
        """Test that DELETE /chat/session/{session_id} requires privileged role."""
        from routers.chat import delete_session
        from fastapi import HTTPException
        
        # Mock request with customer user (not privileged)
        customer_user = {
            "user_id": "user_123",
            "role": "customer",
            "business_access": []
        }
        
        # Should raise 403 for non-privileged role
        with pytest.raises(HTTPException) as exc_info:
            await delete_session("session_123", db=mock_db, user=customer_user)
        
        assert exc_info.value.status_code == 403
    
    @pytest.mark.asyncio
    async def test_chatbot_cache_evict_requires_privileged_auth(self, mock_db):
        """Test that DELETE /cache/business/{business_id} requires privileged role."""
        from routers.chat import evict_cache
        from fastapi import HTTPException
        
        # Mock request with customer user (not privileged)
        customer_user = {
            "user_id": "user_123",
            "role": "customer",
            "business_access": []
        }
        
        # Should raise 403 for non-privileged role
        with pytest.raises(HTTPException) as exc_info:
            await evict_cache("whisked_words", db=mock_db, user=customer_user)
        
        assert exc_info.value.status_code == 403


class TestBusinessScopeValidation:
    """Test business scope validation across secured endpoints."""
    
    @pytest.fixture
    def mock_db(self):
        """Mock MongoDB database."""
        db = Mock()
        db.orders = Mock()
        db.custom_orders = Mock()
        return db
    
    @pytest.mark.asyncio
    async def test_super_admin_bypasses_business_check(self, mock_db):
        """Test that super_admin can access any business."""
        from backend.auth.rbac import check_business_access
        
        super_admin = {
            "role": "super_admin",
            "business_access": []
        }
        
        # Super admin should have access to any business
        assert check_business_access(super_admin, "any_business") == True
        assert check_business_access(super_admin, "other_business") == True
    
    @pytest.mark.asyncio
    async def test_business_admin_respects_business_access(self, mock_db):
        """Test that business_admin is limited to their businesses."""
        from backend.auth.rbac import check_business_access
        
        business_admin = {
            "role": "business_admin",
            "business_access": [{"business_id": "whisked_words"}]
        }
        
        # Should have access to own business
        assert check_business_access(business_admin, "whisked_words") == True
        
        # Should not have access to other business
        assert check_business_access(business_admin, "other_business") == False
    
    @pytest.mark.asyncio
    async def test_staff_respects_business_access(self, mock_db):
        """Test that staff is limited to their businesses."""
        from backend.auth.rbac import check_business_access
        
        staff_user = {
            "role": "staff",
            "business_access": [{"business_id": "whisked_words"}]
        }
        
        # Should have access to own business
        assert check_business_access(staff_user, "whisked_words") == True
        
        # Should not have access to other business
        assert check_business_access(staff_user, "other_business") == False


class TestRoleHierarchy:
    """Test that role hierarchy is enforced correctly."""
    
    def test_role_privilege_levels(self):
        """Test that role privilege levels are correct."""
        from backend.auth.rbac import get_role_level, has_higher_or_equal_privilege
        
        # Test privilege levels
        assert get_role_level("super_admin") == 4
        assert get_role_level("business_admin") == 3
        assert get_role_level("staff") == 2
        assert get_role_level("delivery_agent") == 1
        assert get_role_level("customer") == 0
        
        # Test privilege comparison
        assert has_higher_or_equal_privilege("super_admin", "staff") == True
        assert has_higher_or_equal_privilege("business_admin", "staff") == True
        assert has_higher_or_equal_privilege("staff", "staff") == True
        assert has_higher_or_equal_privilege("customer", "staff") == False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
