"""Tests for Order Management, Delivery, Notifications and Tracking (Phase 3)"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://multi-vendor-suite.preview.emergentagent.com").rstrip("/")
ADMIN_TOKEN = "test_session_admin_001"
CUSTOMER_TOKEN = "test_session_customer_001"
CUSTOMER_USER_ID = "test_customer_001"

H_ADMIN = {"Authorization": f"Bearer {ADMIN_TOKEN}", "Content-Type": "application/json"}
H_CUSTOMER = {"Authorization": f"Bearer {CUSTOMER_TOKEN}", "Content-Type": "application/json"}


# ------- Admin Orders Dashboard -------
class TestAdminOrders:
    def test_list_orders(self):
        r = requests.get(f"{BASE_URL}/api/order-management/orders", headers=H_ADMIN)
        assert r.status_code == 200
        data = r.json()
        assert "orders" in data and "total" in data
        assert isinstance(data["orders"], list)

    def test_list_orders_no_auth(self):
        r = requests.get(f"{BASE_URL}/api/order-management/orders")
        assert r.status_code == 401

    def test_list_orders_customer_forbidden(self):
        r = requests.get(f"{BASE_URL}/api/order-management/orders", headers=H_CUSTOMER)
        assert r.status_code == 403

    def test_list_orders_status_filter(self):
        r = requests.get(f"{BASE_URL}/api/order-management/orders?status=pending", headers=H_ADMIN)
        assert r.status_code == 200
        for o in r.json()["orders"]:
            assert o["order_status"] == "pending"

    def test_order_stats(self):
        r = requests.get(f"{BASE_URL}/api/order-management/orders/stats", headers=H_ADMIN)
        assert r.status_code == 200
        d = r.json()
        assert "total_orders" in d and "by_status" in d and "total_revenue" in d


# ------- Admin Status Updates -------
class TestStatusUpdates:
    @pytest.fixture(scope="class")
    def pending_order_id(self):
        r = requests.get(f"{BASE_URL}/api/order-management/orders?status=pending", headers=H_ADMIN)
        orders = r.json().get("orders", [])
        if not orders:
            pytest.skip("No pending orders available")
        return orders[0]["order_id"]

    def test_confirm_pending_order(self, pending_order_id):
        r = requests.put(
            f"{BASE_URL}/api/order-management/orders/{pending_order_id}/status",
            headers=H_ADMIN, json={"status": "confirmed"}
        )
        assert r.status_code == 200
        # Verify
        v = requests.get(f"{BASE_URL}/api/order-management/track/{pending_order_id}", headers=H_ADMIN)
        assert v.status_code == 200
        assert v.json()["order"]["order_status"] == "confirmed"

    def test_mark_preparing(self, pending_order_id):
        r = requests.put(
            f"{BASE_URL}/api/order-management/orders/{pending_order_id}/status",
            headers=H_ADMIN, json={"status": "preparing"}
        )
        assert r.status_code == 200
        v = requests.get(f"{BASE_URL}/api/order-management/track/{pending_order_id}", headers=H_ADMIN)
        assert v.json()["order"]["order_status"] == "preparing"

    def test_invalid_status_for_admin(self, pending_order_id):
        # Admin cannot set delivery statuses
        r = requests.put(
            f"{BASE_URL}/api/order-management/orders/{pending_order_id}/status",
            headers=H_ADMIN, json={"status": "delivered"}
        )
        assert r.status_code == 400

    def test_cancel_order(self):
        # Find a different pending order to cancel
        r = requests.get(f"{BASE_URL}/api/order-management/orders?status=pending", headers=H_ADMIN)
        orders = r.json().get("orders", [])
        if not orders:
            pytest.skip("No pending orders to cancel")
        oid = orders[0]["order_id"]
        rr = requests.put(
            f"{BASE_URL}/api/order-management/orders/{oid}/status",
            headers=H_ADMIN, json={"status": "cancelled"}
        )
        assert rr.status_code == 200


# ------- Delivery Agent Management -------
class TestDeliveryAgent:
    def test_list_delivery_agents(self):
        r = requests.get(f"{BASE_URL}/api/order-management/delivery-agents", headers=H_ADMIN)
        assert r.status_code == 200
        assert "agents" in r.json()

    def test_user_search_endpoint(self):
        r = requests.get(
            f"{BASE_URL}/api/users/search?email=testcustomer@whiskedwords.com",
            headers=H_ADMIN
        )
        # May be 200 with user or 404
        assert r.status_code in [200, 404]

    def test_make_delivery_agent_and_assign(self):
        # Use an existing user (not the test customer - we'll use fb1a35e23da7)
        target_user = "user_fb1a35e23da7"
        # Promote
        r = requests.put(
            f"{BASE_URL}/api/order-management/users/{target_user}/make-delivery-agent",
            headers=H_ADMIN, json={"phone": "+919999988888"}
        )
        if r.status_code == 404:
            pytest.skip("Target user not found in DB")
        assert r.status_code == 200

        # Verify in list
        agents_r = requests.get(f"{BASE_URL}/api/order-management/delivery-agents", headers=H_ADMIN)
        agent_ids = [a["user_id"] for a in agents_r.json()["agents"]]
        assert target_user in agent_ids

        # Assign to an order
        orders_r = requests.get(f"{BASE_URL}/api/order-management/orders", headers=H_ADMIN)
        order = next((o for o in orders_r.json()["orders"] if o["order_status"] in ["confirmed", "preparing"]), None)
        if not order:
            pytest.skip("No confirmed/preparing order to assign")

        a = requests.put(
            f"{BASE_URL}/api/order-management/orders/{order['order_id']}/assign",
            headers=H_ADMIN, json={"delivery_agent_id": target_user}
        )
        assert a.status_code == 200


# ------- Notifications -------
class TestNotifications:
    def test_get_notifications(self):
        r = requests.get(f"{BASE_URL}/api/order-management/notifications", headers=H_CUSTOMER)
        assert r.status_code == 200
        d = r.json()
        assert "notifications" in d and "unread_count" in d

    def test_get_notifications_unread_only(self):
        r = requests.get(f"{BASE_URL}/api/order-management/notifications?unread_only=true", headers=H_CUSTOMER)
        assert r.status_code == 200
        for n in r.json()["notifications"]:
            assert n["read"] is False

    def test_mark_all_read(self):
        r = requests.put(f"{BASE_URL}/api/order-management/notifications/read-all", headers=H_CUSTOMER)
        assert r.status_code == 200
        # Verify
        v = requests.get(f"{BASE_URL}/api/order-management/notifications", headers=H_CUSTOMER)
        assert v.json()["unread_count"] == 0


# ------- Order Tracking -------
class TestOrderTracking:
    def test_track_own_order(self):
        # Customer's own order
        r = requests.get(f"{BASE_URL}/api/order-management/track/ord_d6b06a5a6b26", headers=H_CUSTOMER)
        assert r.status_code == 200
        d = r.json()
        assert "order" in d and "timeline" in d and "current_status" in d
        assert isinstance(d["timeline"], list)
        # Timeline contains pending step
        statuses = [t["status"] for t in d["timeline"]]
        assert "pending" in statuses

    def test_track_other_user_order_forbidden(self):
        # Order belonging to another user
        r = requests.get(f"{BASE_URL}/api/order-management/track/ord_f0e03c3227c7", headers=H_CUSTOMER)
        assert r.status_code in [403, 404]

    def test_track_nonexistent_order(self):
        r = requests.get(f"{BASE_URL}/api/order-management/track/ord_nonexistent", headers=H_CUSTOMER)
        assert r.status_code == 404


# ------- Customer My Orders -------
class TestMyOrders:
    def test_my_orders_endpoint(self):
        r = requests.get(f"{BASE_URL}/api/orders/my-orders", headers=H_CUSTOMER)
        assert r.status_code == 200
        d = r.json()
        # Could be list or {orders: []}
        if isinstance(d, dict):
            orders = d.get("orders", [])
        else:
            orders = d
        assert isinstance(orders, list)


# ------- Not Delivered Reasons -------
class TestNotDeliveredReasons:
    def test_get_reasons(self):
        r = requests.get(f"{BASE_URL}/api/order-management/not-delivered-reasons")
        assert r.status_code == 200
        d = r.json()
        assert "reasons" in d and len(d["reasons"]) > 0
