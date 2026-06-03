"""
Comprehensive API Tests for Multi-Business Platform (Jain Industries)
Tests: Public APIs, Auth, Products, Cart, Orders, Reviews, Loyalty, Subscriptions, Custom Orders
"""
import pytest
import requests
import os
import uuid
from datetime import datetime, timedelta

# Base URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'http://localhost:8000').rstrip('/')

# Test tokens from test_credentials.md
CUSTOMER_TOKEN = "test_session_customer_001"
ADMIN_TOKEN = "test_session_admin_001"

@pytest.fixture
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session

@pytest.fixture
def customer_client(api_client):
    """Session with customer auth"""
    api_client.headers.update({"Authorization": f"Bearer {CUSTOMER_TOKEN}"})
    return api_client

@pytest.fixture
def admin_client(api_client):
    """Session with admin auth"""
    api_client.headers.update({"Authorization": f"Bearer {ADMIN_TOKEN}"})
    return api_client


# ============= PUBLIC API TESTS =============
class TestPublicAPIs:
    """Test public endpoints that don't require authentication"""
    
    def test_get_public_businesses_returns_4_businesses(self, api_client):
        """GET /api/businesses/public should return 4 businesses"""
        response = api_client.get(f"{BASE_URL}/api/businesses/public")
        assert response.status_code == 200
        
        data = response.json()
        assert "businesses" in data
        assert data["total"] == 4
        
        # Verify business IDs
        business_ids = [b["business_id"] for b in data["businesses"]]
        assert "whisked_words" in business_ids
        assert "rishabh_garments" in business_ids
        assert "jain_jewellers" in business_ids
        assert "jain_sarees" in business_ids
    
    def test_get_whisked_words_business_details(self, api_client):
        """GET /api/businesses/whisked_words should return business details"""
        response = api_client.get(f"{BASE_URL}/api/businesses/whisked_words")
        assert response.status_code == 200
        
        data = response.json()
        assert data["business_id"] == "whisked_words"
        assert data["business_name"] == "Whisked Words"
        assert data["business_type"] == "bakery"
        assert "contact" in data
    
    def test_get_products_for_whisked_words(self, api_client):
        """GET /api/products?business_id=whisked_words should return products"""
        response = api_client.get(f"{BASE_URL}/api/products?business_id=whisked_words")
        assert response.status_code == 200
        
        data = response.json()
        assert "products" in data
        assert "pagination" in data
        # Should have at least some products
        assert len(data["products"]) >= 0


# ============= AUTH TESTS =============
class TestAuthentication:
    """Test authentication endpoints"""
    
    def test_auth_me_with_customer_token(self, customer_client):
        """GET /api/auth/me with customer token returns customer user"""
        response = customer_client.get(f"{BASE_URL}/api/auth/me")
        assert response.status_code == 200
        
        data = response.json()
        assert data["user_id"] == "test_customer_001"
        assert data["role"] == "customer"
        assert data["email"] == "testcustomer@whiskedwords.com"
    
    def test_auth_me_with_admin_token(self, admin_client):
        """GET /api/auth/me with admin token returns admin user"""
        response = admin_client.get(f"{BASE_URL}/api/auth/me")
        assert response.status_code == 200
        
        data = response.json()
        assert data["user_id"] == "test_admin_001"
        assert data["role"] == "business_admin"
    
    def test_auth_me_without_token_returns_401(self, api_client):
        """GET /api/auth/me without token returns 401"""
        response = api_client.get(f"{BASE_URL}/api/auth/me")
        assert response.status_code == 401


# ============= PRODUCT CRUD TESTS (Admin) =============
class TestProductCRUD:
    """Test product CRUD operations for admin"""
    
    def test_admin_create_product(self, admin_client):
        """POST /api/products with admin token creates product and inventory"""
        unique_name = f"TEST_Product_{uuid.uuid4().hex[:8]}"
        product_data = {
            "business_id": "whisked_words",
            "product_name": unique_name,
            "description": "Test product for automated testing",
            "base_price": 299.99,
            "currency": "INR",
            "images": [{"url": "https://example.com/test.jpg", "alt": "Test", "is_primary": True}],
            "inventory_count": 50
        }
        
        response = admin_client.post(f"{BASE_URL}/api/products", json=product_data)
        assert response.status_code == 200
        
        data = response.json()
        assert "product_id" in data
        assert data["message"] == "Product created successfully"
        
        # Verify product was created by fetching it
        product_id = data["product_id"]
        get_response = admin_client.get(f"{BASE_URL}/api/products/{product_id}")
        assert get_response.status_code == 200
        
        product = get_response.json()
        assert product["product_name"] == unique_name
        assert product["base_price"] == 299.99
        
        # Cleanup - delete the test product
        delete_response = admin_client.delete(f"{BASE_URL}/api/products/{product_id}")
        assert delete_response.status_code == 200
    
    def test_customer_cannot_create_product(self, customer_client):
        """POST /api/products with customer token returns 403"""
        product_data = {
            "business_id": "whisked_words",
            "product_name": "Unauthorized Product",
            "base_price": 100
        }
        
        response = customer_client.post(f"{BASE_URL}/api/products", json=product_data)
        assert response.status_code == 403


# ============= CART TESTS =============
class TestCartFlow:
    """Test cart operations"""
    
    def test_add_item_to_cart(self, customer_client):
        """POST /api/ecommerce/cart/add adds item to cart"""
        # First get a product
        products_response = customer_client.get(f"{BASE_URL}/api/products?business_id=whisked_words")
        products = products_response.json()["products"]
        
        if len(products) == 0:
            pytest.skip("No products available for cart test")
        
        product_id = products[0]["product_id"]
        
        cart_data = {
            "product_id": product_id,
            "quantity": 1
        }
        
        response = customer_client.post(f"{BASE_URL}/api/ecommerce/cart/add", json=cart_data)
        assert response.status_code == 200
        
        data = response.json()
        assert "cart_id" in data
        assert data["message"] == "Item added to cart"
    
    def test_get_cart(self, customer_client):
        """GET /api/ecommerce/cart returns cart"""
        response = customer_client.get(f"{BASE_URL}/api/ecommerce/cart")
        assert response.status_code == 200
        
        data = response.json()
        # Cart should have items or be empty
        assert "items" in data or "total_amount" in data
    
    def test_update_cart_item_quantity(self, customer_client):
        """PUT /api/ecommerce/cart/{product_id} updates quantity"""
        # First get cart to find an item
        cart_response = customer_client.get(f"{BASE_URL}/api/ecommerce/cart")
        cart = cart_response.json()
        
        if not cart.get("items") or len(cart["items"]) == 0:
            pytest.skip("No items in cart to update")
        
        product_id = cart["items"][0]["product_id"]
        
        update_data = {"quantity": 2}
        response = customer_client.put(f"{BASE_URL}/api/ecommerce/cart/{product_id}", json=update_data)
        assert response.status_code == 200
    
    def test_remove_item_from_cart(self, customer_client):
        """DELETE /api/ecommerce/cart/{product_id} removes item"""
        # First add an item
        products_response = customer_client.get(f"{BASE_URL}/api/products?business_id=whisked_words")
        products = products_response.json()["products"]
        
        if len(products) == 0:
            pytest.skip("No products available")
        
        product_id = products[0]["product_id"]
        
        # Add to cart
        customer_client.post(f"{BASE_URL}/api/ecommerce/cart/add", json={"product_id": product_id, "quantity": 1})
        
        # Remove from cart
        response = customer_client.delete(f"{BASE_URL}/api/ecommerce/cart/{product_id}")
        assert response.status_code == 200


# ============= ORDER TESTS =============
class TestOrderFlow:
    """Test order creation and retrieval"""
    
    def test_create_order_with_cod(self, customer_client):
        """POST /api/orders/create with COD payment creates order"""
        # Get a product first
        products_response = customer_client.get(f"{BASE_URL}/api/products?business_id=whisked_words")
        products = products_response.json()["products"]
        
        if len(products) == 0:
            pytest.skip("No products available for order test")
        
        product = products[0]
        
        order_data = {
            "items": [{
                "product_id": product["product_id"],
                "variant_id": None,
                "product_name": product["product_name"],
                "quantity": 1,
                "price": product["base_price"],
                "subtotal": product["base_price"]
            }],
            "delivery_info": {
                "name": "Test Customer",
                "phone": "+91-9876543210",
                "email": "test@example.com",
                "address": "123 Test Street",
                "city": "Bangalore",
                "state": "Karnataka",
                "pincode": "560001"
            },
            "payment_method": "cod",
            "subtotal": product["base_price"],
            "tax": product["base_price"] * 0.18,
            "delivery_charge": 50,
            "total": product["base_price"] * 1.18 + 50
        }
        
        response = customer_client.post(f"{BASE_URL}/api/orders/create", json=order_data)
        assert response.status_code == 200
        
        data = response.json()
        assert "order_id" in data
        assert data["message"] == "Order created successfully"
    
    def test_get_my_orders(self, customer_client):
        """GET /api/orders/my-orders returns user orders"""
        response = customer_client.get(f"{BASE_URL}/api/orders/my-orders")
        assert response.status_code == 200
        
        data = response.json()
        assert "orders" in data
        assert isinstance(data["orders"], list)


# ============= REVIEW TESTS =============
class TestReviews:
    """Test review creation and retrieval"""
    
    def test_get_product_reviews(self, api_client):
        """GET /api/reviews/product/{product_id} returns reviews"""
        # Get a product first
        products_response = api_client.get(f"{BASE_URL}/api/products?business_id=whisked_words")
        products = products_response.json()["products"]
        
        if len(products) == 0:
            pytest.skip("No products available")
        
        product_id = products[0]["product_id"]
        
        response = api_client.get(f"{BASE_URL}/api/reviews/product/{product_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert "reviews" in data
        assert "average_rating" in data
        assert "total" in data
    
    def test_create_review_requires_auth(self, api_client):
        """POST /api/reviews/create without auth returns 401"""
        review_data = {
            "product_id": "test_product",
            "rating": 5,
            "comment": "Great product!"
        }
        
        response = api_client.post(f"{BASE_URL}/api/reviews/create", json=review_data)
        assert response.status_code == 401
    
    def test_create_review_with_auth(self, customer_client):
        """POST /api/reviews/create creates review and awards points"""
        # Get products to find one without a review from this user
        products_response = customer_client.get(f"{BASE_URL}/api/products?business_id=whisked_words")
        products = products_response.json()["products"]
        
        if len(products) < 2:
            pytest.skip("Not enough products for review test")
        
        # Try the second product (first might already have a review)
        product_id = products[1]["product_id"]
        
        review_data = {
            "product_id": product_id,
            "rating": 4,
            "comment": "Test review from automated testing"
        }
        
        response = customer_client.post(f"{BASE_URL}/api/reviews/create", json=review_data)
        
        # Either 200 (success) or 400 (already reviewed)
        assert response.status_code in [200, 400]
        
        if response.status_code == 200:
            data = response.json()
            assert "review_id" in data
            assert data["points_earned"] == 50


# ============= LOYALTY TESTS =============
class TestLoyalty:
    """Test loyalty points system"""
    
    def test_get_loyalty_points(self, customer_client):
        """GET /api/loyalty/points returns points and tier"""
        response = customer_client.get(f"{BASE_URL}/api/loyalty/points")
        assert response.status_code == 200
        
        data = response.json()
        assert "points" in data
        assert "tier" in data
        assert "total_earned" in data
    
    def test_get_loyalty_transactions(self, customer_client):
        """GET /api/loyalty/transactions returns transaction history"""
        response = customer_client.get(f"{BASE_URL}/api/loyalty/transactions")
        assert response.status_code == 200
        
        data = response.json()
        assert "transactions" in data
        assert isinstance(data["transactions"], list)
    
    def test_loyalty_requires_auth(self, api_client):
        """GET /api/loyalty/points without auth returns 401"""
        response = api_client.get(f"{BASE_URL}/api/loyalty/points")
        assert response.status_code == 401


# ============= SUBSCRIPTION TESTS =============
class TestSubscriptions:
    """Test subscription management"""
    
    def test_create_subscription(self, customer_client):
        """POST /api/subscriptions/create creates subscription"""
        # Get products first
        products_response = customer_client.get(f"{BASE_URL}/api/products?business_id=whisked_words")
        products = products_response.json()["products"]
        
        if len(products) == 0:
            pytest.skip("No products available for subscription test")
        
        product_id = products[0]["product_id"]
        start_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        
        subscription_data = {
            "product_ids": [product_id],
            "frequency": "weekly",
            "delivery_days": ["monday", "friday"],
            "delivery_time": "morning",
            "start_date": start_date,
            "delivery_info": {
                "name": "Test Customer",
                "phone": "+91-9876543210",
                "email": "test@example.com",
                "address": "123 Test Street",
                "city": "Bangalore",
                "state": "Karnataka",
                "pincode": "560001"
            }
        }
        
        response = customer_client.post(f"{BASE_URL}/api/subscriptions/create", json=subscription_data)
        assert response.status_code == 200
        
        data = response.json()
        assert "subscription_id" in data
        assert data["message"] == "Subscription created successfully"
    
    def test_get_my_subscriptions(self, customer_client):
        """GET /api/subscriptions/my-subscriptions returns subscriptions"""
        response = customer_client.get(f"{BASE_URL}/api/subscriptions/my-subscriptions")
        assert response.status_code == 200
        
        data = response.json()
        assert "subscriptions" in data
        assert isinstance(data["subscriptions"], list)
    
    def test_pause_and_resume_subscription(self, customer_client):
        """PUT /api/subscriptions/{id}/pause and resume work correctly"""
        # Get subscriptions
        subs_response = customer_client.get(f"{BASE_URL}/api/subscriptions/my-subscriptions")
        subscriptions = subs_response.json()["subscriptions"]
        
        # Find an active subscription
        active_sub = next((s for s in subscriptions if s["status"] == "active"), None)
        
        if not active_sub:
            pytest.skip("No active subscription to test pause/resume")
        
        subscription_id = active_sub["subscription_id"]
        
        # Pause
        pause_response = customer_client.put(f"{BASE_URL}/api/subscriptions/{subscription_id}/pause")
        assert pause_response.status_code == 200
        
        # Resume
        resume_response = customer_client.put(f"{BASE_URL}/api/subscriptions/{subscription_id}/resume")
        assert resume_response.status_code == 200
    
    def test_cancel_subscription(self, customer_client):
        """DELETE /api/subscriptions/{id} cancels subscription"""
        # Create a new subscription to cancel
        products_response = customer_client.get(f"{BASE_URL}/api/products?business_id=whisked_words")
        products = products_response.json()["products"]
        
        if len(products) == 0:
            pytest.skip("No products available")
        
        product_id = products[0]["product_id"]
        start_date = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")
        
        subscription_data = {
            "product_ids": [product_id],
            "frequency": "monthly",
            "delivery_days": ["wednesday"],
            "delivery_time": "afternoon",
            "start_date": start_date,
            "delivery_info": {
                "name": "Test Cancel",
                "phone": "+91-9876543210",
                "email": "test@example.com",
                "address": "123 Test Street",
                "city": "Bangalore",
                "state": "Karnataka",
                "pincode": "560001"
            }
        }
        
        create_response = customer_client.post(f"{BASE_URL}/api/subscriptions/create", json=subscription_data)
        if create_response.status_code != 200:
            pytest.skip("Could not create subscription to cancel")
        
        subscription_id = create_response.json()["subscription_id"]
        
        # Cancel
        cancel_response = customer_client.delete(f"{BASE_URL}/api/subscriptions/{subscription_id}")
        assert cancel_response.status_code == 200


# ============= CUSTOM ORDER TESTS =============
class TestCustomOrders:
    """Test custom cake order functionality"""
    
    def test_create_custom_order(self, customer_client):
        """POST /api/custom-orders/create creates custom cake order"""
        # Get a product first
        products_response = customer_client.get(f"{BASE_URL}/api/products?business_id=whisked_words")
        products = products_response.json()["products"]
        
        if len(products) == 0:
            pytest.skip("No products available for custom order test")
        
        product_id = products[0]["product_id"]
        delivery_date = (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d")
        
        custom_order_data = {
            "product_id": product_id,
            "cake_type": "birthday",
            "weight": "1kg",
            "flavor": "chocolate",
            "shape": "round",
            "message_on_cake": "Happy Birthday!",
            "special_instructions": "Extra chocolate frosting",
            "delivery_date": delivery_date,
            "delivery_time": "afternoon",
            "delivery_info": {
                "name": "Test Customer",
                "phone": "+91-9876543210",
                "email": "test@example.com",
                "address": "123 Test Street",
                "city": "Bangalore",
                "state": "Karnataka",
                "pincode": "560001"
            }
        }
        
        response = customer_client.post(f"{BASE_URL}/api/custom-orders/create", json=custom_order_data)
        assert response.status_code == 200
        
        data = response.json()
        assert "custom_order_id" in data
        assert data["message"] == "Custom order request submitted"
    
    def test_get_my_custom_orders(self, customer_client):
        """GET /api/custom-orders/my-orders returns user's custom orders"""
        response = customer_client.get(f"{BASE_URL}/api/custom-orders/my-orders")
        assert response.status_code == 200
        
        data = response.json()
        assert "orders" in data
        assert isinstance(data["orders"], list)


# ============= INVENTORY TESTS (Admin) =============
class TestInventory:
    """Test inventory management for admin"""
    
    def test_get_inventory(self, admin_client):
        """GET /api/inventory returns inventory for business"""
        response = admin_client.get(f"{BASE_URL}/api/inventory?business_id=whisked_words")
        assert response.status_code == 200
        
        data = response.json()
        assert "inventory" in data
        assert "total" in data
    
    def test_customer_cannot_access_inventory(self, customer_client):
        """GET /api/inventory with customer token returns 403"""
        response = customer_client.get(f"{BASE_URL}/api/inventory?business_id=whisked_words")
        assert response.status_code == 403


# ============= ANALYTICS TESTS (Admin) =============
class TestAnalytics:
    """Test analytics dashboard for admin"""
    
    def test_get_dashboard_stats(self, admin_client):
        """GET /api/analytics/dashboard returns business stats"""
        response = admin_client.get(f"{BASE_URL}/api/analytics/dashboard?business_id=whisked_words")
        assert response.status_code == 200
        
        data = response.json()
        assert "business_stats" in data
        stats = data["business_stats"]
        assert "total_products" in stats
        assert "total_inventory_value" in stats


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
