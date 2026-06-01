"""
Iteration 6 tests:
- SSE endpoint auth & connected event
- Email service graceful skip (no provider configured)
- Auto-assignment of delivery agent on order confirm
- Delivery agents endpoint includes base_pincode & active_orders
- make-delivery-agent accepts base_pincode
"""
import os
import json
import time
import uuid
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://multi-vendor-suite.preview.emergentagent.com").rstrip("/")
ADMIN_TOKEN = "test_session_admin_001"
CUSTOMER_TOKEN = "test_session_customer_001"
DELIVERY_TOKEN = "test_session_delivery_001"
DELIVERY_USER_ID = "user_fb1a35e23da7"
CUSTOMER_USER_ID = "test_customer_001"

def H(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# ============= AUTH/HEALTH SANITY =============
class TestSanity:
    def test_admin_auth(self):
        r = requests.get(f"{BASE_URL}/api/auth/me", headers=H(ADMIN_TOKEN), timeout=15)
        assert r.status_code == 200, r.text
        assert r.json().get("role") == "business_admin"

    def test_customer_auth(self):
        r = requests.get(f"{BASE_URL}/api/auth/me", headers=H(CUSTOMER_TOKEN), timeout=15)
        assert r.status_code == 200, r.text


# ============= SSE TESTS =============
class TestSSE:
    def test_sse_no_auth_returns_401(self):
        r = requests.get(f"{BASE_URL}/api/sse/events", timeout=10, stream=True)
        # SSE without token must reject
        assert r.status_code == 401, f"Expected 401, got {r.status_code}: {r.text[:200]}"

    def test_sse_invalid_token_returns_401(self):
        r = requests.get(f"{BASE_URL}/api/sse/events?token=invalid_token_xyz", timeout=10, stream=True)
        assert r.status_code == 401

    def test_sse_connected_event_via_query_token(self):
        """Connect via ?token= and read first SSE event line."""
        with requests.get(
            f"{BASE_URL}/api/sse/events?token={CUSTOMER_TOKEN}",
            stream=True, timeout=15
        ) as r:
            assert r.status_code == 200, f"Status {r.status_code}: {r.text[:200]}"
            assert "text/event-stream" in r.headers.get("content-type", "")
            # Read first data line
            got_connected = False
            start = time.time()
            for raw in r.iter_lines(decode_unicode=True):
                if raw and raw.startswith("data: "):
                    payload = json.loads(raw[6:])
                    assert payload.get("type") == "connected"
                    assert payload.get("data", {}).get("user_id") == CUSTOMER_USER_ID
                    got_connected = True
                    break
                if time.time() - start > 10:
                    break
            assert got_connected, "Did not receive 'connected' SSE event"

    def test_sse_connected_event_via_bearer(self):
        with requests.get(
            f"{BASE_URL}/api/sse/events",
            headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
            stream=True, timeout=15
        ) as r:
            assert r.status_code == 200
            start = time.time()
            for raw in r.iter_lines(decode_unicode=True):
                if raw and raw.startswith("data: "):
                    payload = json.loads(raw[6:])
                    assert payload.get("type") == "connected"
                    return
                if time.time() - start > 10:
                    break
            pytest.fail("No connected event received")


# ============= EMAIL SERVICE TESTS =============
class TestEmailService:
    def test_email_provider_not_configured(self):
        """EMAIL_PROVIDER env var should be empty."""
        # Test via the module directly using subprocess-safe import
        import sys
        sys.path.insert(0, "/app/backend")
        from email_service import get_email_provider
        provider = get_email_provider()
        assert provider is None, "Expected no provider when EMAIL_PROVIDER is empty"

    def test_send_email_skips_gracefully(self):
        """send_email returns False & logs 'no provider configured' message."""
        import sys, asyncio
        sys.path.insert(0, "/app/backend")
        from email_service import send_email
        result = asyncio.run(send_email("test@example.com", "Test", "<p>hi</p>"))
        assert result is False


# ============= DELIVERY AGENTS LIST =============
class TestDeliveryAgentsList:
    def test_agents_list_has_base_pincode_and_active_orders(self):
        r = requests.get(
            f"{BASE_URL}/api/order-management/delivery-agents",
            headers=H(ADMIN_TOKEN), timeout=15
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert "agents" in data
        assert len(data["agents"]) >= 1, "No delivery agents present"
        for agent in data["agents"]:
            assert "base_pincode" in agent, f"Missing base_pincode on agent {agent.get('user_id')}"
            assert "active_orders" in agent, f"Missing active_orders on agent {agent.get('user_id')}"
            assert isinstance(agent["active_orders"], int)

    def test_make_delivery_agent_accepts_base_pincode(self):
        """Re-promote existing delivery agent with a base_pincode value."""
        payload = {"phone": "9999999999", "base_pincode": "400001"}
        r = requests.put(
            f"{BASE_URL}/api/order-management/users/{DELIVERY_USER_ID}/make-delivery-agent",
            headers=H(ADMIN_TOKEN), json=payload, timeout=15
        )
        assert r.status_code == 200, r.text

        # Verify base_pincode persisted by listing agents again
        r2 = requests.get(
            f"{BASE_URL}/api/order-management/delivery-agents",
            headers=H(ADMIN_TOKEN), timeout=15
        )
        agents = r2.json().get("agents", [])
        match = next((a for a in agents if a.get("user_id") == DELIVERY_USER_ID), None)
        assert match is not None, "Test delivery agent not found in list"
        assert match.get("base_pincode") == "400001", f"base_pincode not persisted: {match}"


# ============= AUTO-ASSIGNMENT =============
class TestAutoAssign:
    @pytest.fixture(scope="class")
    def pending_order_id(self):
        """Find a pending order owned by test customer, or create one."""
        # List customer's orders
        r = requests.get(
            f"{BASE_URL}/api/order-management/orders?status=pending",
            headers=H(ADMIN_TOKEN), timeout=15
        )
        if r.status_code == 200:
            for o in r.json().get("orders", []):
                if not o.get("delivery_agent_id") and o.get("delivery_info", {}).get("pincode"):
                    return o["order_id"]
        pytest.skip("No suitable pending order with delivery pincode available")

    def test_auto_assign_on_confirm(self, pending_order_id):
        # Confirm the pending order
        r = requests.put(
            f"{BASE_URL}/api/order-management/orders/{pending_order_id}/status",
            headers=H(ADMIN_TOKEN), json={"status": "confirmed"}, timeout=15
        )
        assert r.status_code == 200, r.text

        # Wait briefly for asyncio.create_task auto_assign
        time.sleep(3)

        # Verify order now has delivery_agent_id
        r2 = requests.get(
            f"{BASE_URL}/api/order-management/track/{pending_order_id}",
            headers=H(ADMIN_TOKEN), timeout=15
        )
        assert r2.status_code == 200, r2.text
        data = r2.json()
        order = data.get("order", {})
        assert order.get("delivery_agent_id"), (
            f"Order {pending_order_id} not auto-assigned after confirm. Order: {order}"
        )

    def test_auto_assign_notification_created(self):
        """Delivery agent should have a recent delivery_assignment notification."""
        r = requests.get(
            f"{BASE_URL}/api/order-management/notifications",
            headers=H(DELIVERY_TOKEN), timeout=15
        )
        assert r.status_code == 200, r.text
        notifs = r.json().get("notifications", [])
        assignment_notifs = [n for n in notifs if n.get("type") == "delivery_assignment"]
        assert len(assignment_notifs) >= 1, "No delivery_assignment notification found for delivery agent"


# ============= AWS DEPLOYMENT README =============
class TestAWSReadme:
    def test_readme_exists_and_has_sections(self):
        path = "/app/AWS_DEPLOYMENT_README.md"
        assert os.path.exists(path), f"{path} missing"
        content = open(path).read()
        for keyword in ["S3", "CloudFront", "ECS", "MongoDB Atlas", "EMAIL_PROVIDER"]:
            assert keyword in content, f"Missing {keyword} in AWS_DEPLOYMENT_README.md"
