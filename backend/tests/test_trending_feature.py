"""
Tests for Trending/Bestsellers Feature
Tests: GET /api/products/trending/{business_id} endpoint
"""
import pytest
import requests
import os

# Base URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'http://localhost:8000').rstrip('/')

# Test tokens
CUSTOMER_TOKEN = "test_session_customer_001"

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


# ============= TRENDING ENDPOINT TESTS =============
class TestTrendingEndpoint:
    """Test GET /api/products/trending/{business_id} endpoint"""
    
    def test_trending_returns_products_with_required_fields(self, api_client):
        """GET /api/products/trending/whisked_words returns trending products with all required fields"""
        response = api_client.get(f"{BASE_URL}/api/products/trending/whisked_words")
        assert response.status_code == 200
        
        data = response.json()
        assert "trending" in data
        assert "total" in data
        
        # Should have at least 1 trending product
        assert len(data["trending"]) >= 1
        
        # Verify each product has required fields
        for product in data["trending"]:
            assert "product_id" in product
            assert "product_name" in product
            assert "trending_score" in product
            assert "total_ordered" in product
            assert "review_count" in product
            assert "avg_rating" in product
            assert "base_price" in product
            assert "currency" in product
            
            # Verify types
            assert isinstance(product["trending_score"], (int, float))
            assert isinstance(product["total_ordered"], int)
            assert isinstance(product["review_count"], int)
            assert isinstance(product["avg_rating"], (int, float))
    
    def test_trending_limit_parameter(self, api_client):
        """GET /api/products/trending/whisked_words?limit=1 returns only 1 product"""
        response = api_client.get(f"{BASE_URL}/api/products/trending/whisked_words?limit=1")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["trending"]) == 1
        assert data["total"] == 1
    
    def test_trending_sorted_by_score_descending(self, api_client):
        """Trending products are sorted by trending_score descending"""
        response = api_client.get(f"{BASE_URL}/api/products/trending/whisked_words")
        assert response.status_code == 200
        
        data = response.json()
        trending = data["trending"]
        
        if len(trending) >= 2:
            # Verify descending order
            for i in range(len(trending) - 1):
                assert trending[i]["trending_score"] >= trending[i + 1]["trending_score"], \
                    f"Products not sorted by trending_score: {trending[i]['trending_score']} < {trending[i+1]['trending_score']}"
    
    def test_chocolate_truffle_cake_ranks_first(self, api_client):
        """Chocolate Truffle Cake should rank #1 (has 1 order, 5-star review)"""
        response = api_client.get(f"{BASE_URL}/api/products/trending/whisked_words")
        assert response.status_code == 200
        
        data = response.json()
        trending = data["trending"]
        
        # Find Chocolate Truffle Cake
        chocolate_cake = next((p for p in trending if "Chocolate" in p["product_name"]), None)
        
        if chocolate_cake:
            # Should be first in the list
            assert trending[0]["product_name"] == chocolate_cake["product_name"], \
                f"Expected Chocolate Truffle Cake to be #1, but got {trending[0]['product_name']}"
            
            # Verify expected stats
            assert chocolate_cake["total_ordered"] >= 1, "Chocolate Truffle Cake should have at least 1 order"
            assert chocolate_cake["avg_rating"] == 5.0, "Chocolate Truffle Cake should have 5-star rating"
            
            # Verify trending score formula: (total_ordered * 10) + (avg_rating * 5) + (review_count * 2)
            # Expected: (1*10) + (5*5) + (1*2) = 37
            expected_score = (chocolate_cake["total_ordered"] * 10) + (chocolate_cake["avg_rating"] * 5) + (chocolate_cake["review_count"] * 2)
            assert chocolate_cake["trending_score"] == expected_score, \
                f"Trending score mismatch: expected {expected_score}, got {chocolate_cake['trending_score']}"
    
    def test_trending_default_limit_is_6(self, api_client):
        """Default limit should be 6 products"""
        response = api_client.get(f"{BASE_URL}/api/products/trending/whisked_words")
        assert response.status_code == 200
        
        data = response.json()
        # Should return at most 6 products (or fewer if less exist)
        assert len(data["trending"]) <= 6
    
    def test_trending_nonexistent_business(self, api_client):
        """GET /api/products/trending/nonexistent_business returns empty list"""
        response = api_client.get(f"{BASE_URL}/api/products/trending/nonexistent_business")
        assert response.status_code == 200
        
        data = response.json()
        assert data["trending"] == []
        assert data["total"] == 0


# ============= ORDER CREATION WITH VARIANT_ID=NULL TEST =============
class TestOrderCreationFix:
    """Test that order creation works with variant_id=null"""
    
    def test_create_order_with_null_variant_id(self, customer_client):
        """POST /api/orders/create works with variant_id=null"""
        # Get a product first
        products_response = customer_client.get(f"{BASE_URL}/api/products?business_id=whisked_words")
        products = products_response.json()["products"]
        
        if len(products) == 0:
            pytest.skip("No products available for order test")
        
        product = products[0]
        
        order_data = {
            "items": [{
                "product_id": product["product_id"],
                "variant_id": None,  # Explicitly null
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
            "tax": round(product["base_price"] * 0.18, 2),
            "delivery_charge": 50,
            "total": round(product["base_price"] * 1.18 + 50, 2)
        }
        
        response = customer_client.post(f"{BASE_URL}/api/orders/create", json=order_data)
        
        # Should succeed (200) - not fail with "Insufficient stock"
        assert response.status_code == 200, f"Order creation failed: {response.json()}"
        
        data = response.json()
        assert "order_id" in data
        assert data["message"] == "Order created successfully"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
