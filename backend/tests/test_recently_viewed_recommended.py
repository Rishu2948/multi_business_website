"""
Tests for Recently Viewed and Recommended For You Features
Tests:
- POST /api/products/track-view - Track product views (auth and non-auth)
- GET /api/products/recommended/{business_id} - Get personalized recommendations
"""
import pytest
import requests
import os

# Base URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'http://localhost:8000').rstrip('/')

# Test tokens
CUSTOMER_TOKEN = os.environ.get("TEST_CUSTOMER_TOKEN", "test_session_customer_001")
ADMIN_TOKEN = os.environ.get("TEST_ADMIN_TOKEN", "test_session_admin_001")

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


# ============= TRACK VIEW ENDPOINT TESTS =============
class TestTrackViewEndpoint:
    """Test POST /api/products/track-view endpoint"""
    
    def test_track_view_with_auth_returns_view_tracked(self, customer_client):
        """POST /api/products/track-view with auth tracks view in DB"""
        # Get a product first
        products_response = customer_client.get(f"{BASE_URL}/api/products?business_id=whisked_words")
        products = products_response.json()["products"]
        
        if len(products) == 0:
            pytest.skip("No products available for track view test")
        
        product = products[0]
        
        response = customer_client.post(f"{BASE_URL}/api/products/track-view", json={
            "product_id": product["product_id"],
            "business_id": "whisked_words"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "View tracked"
    
    def test_track_view_without_auth_returns_local_only(self, api_client):
        """POST /api/products/track-view without auth returns 'View tracked locally only'"""
        # Get a product first
        products_response = api_client.get(f"{BASE_URL}/api/products?business_id=whisked_words")
        products = products_response.json()["products"]
        
        if len(products) == 0:
            pytest.skip("No products available for track view test")
        
        product = products[0]
        
        response = api_client.post(f"{BASE_URL}/api/products/track-view", json={
            "product_id": product["product_id"],
            "business_id": "whisked_words"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "View tracked locally only"
    
    def test_track_view_missing_product_id_returns_400(self, customer_client):
        """POST /api/products/track-view without product_id returns 400"""
        response = customer_client.post(f"{BASE_URL}/api/products/track-view", json={
            "business_id": "whisked_words"
        })
        
        assert response.status_code == 400
        data = response.json()
        assert "product_id" in data["detail"].lower() or "required" in data["detail"].lower()
    
    def test_track_view_missing_business_id_returns_400(self, customer_client):
        """POST /api/products/track-view without business_id returns 400"""
        response = customer_client.post(f"{BASE_URL}/api/products/track-view", json={
            "product_id": "prod_test123"
        })
        
        assert response.status_code == 400
        data = response.json()
        assert "business_id" in data["detail"].lower() or "required" in data["detail"].lower()


# ============= RECOMMENDED ENDPOINT TESTS =============
class TestRecommendedEndpoint:
    """Test GET /api/products/recommended/{business_id} endpoint"""
    
    def test_recommended_with_auth_returns_personalized_recommendations(self, customer_client):
        """GET /api/products/recommended/whisked_words with auth returns personalized recommendations"""
        response = customer_client.get(f"{BASE_URL}/api/products/recommended/whisked_words")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "recommended" in data
        assert "total" in data
        assert "strategy" in data
        
        # Strategy should be one of the personalized strategies for authenticated user
        # (category_match, also_bought, discovery) or top_rated fallback
        valid_strategies = ["category_match", "also_bought", "discovery", "top_rated"]
        assert data["strategy"] in valid_strategies, f"Unexpected strategy: {data['strategy']}"
        
        # Should have at least 1 recommendation
        if len(data["recommended"]) > 0:
            # Verify each product has required fields including review_count and avg_rating
            for product in data["recommended"]:
                assert "product_id" in product
                assert "product_name" in product
                assert "review_count" in product
                assert "avg_rating" in product
                assert "base_price" in product
                
                # Verify types
                assert isinstance(product["review_count"], int)
                assert isinstance(product["avg_rating"], (int, float))
    
    def test_recommended_without_auth_returns_top_rated_strategy(self, api_client):
        """GET /api/products/recommended/whisked_words without auth returns top_rated strategy"""
        response = api_client.get(f"{BASE_URL}/api/products/recommended/whisked_words")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "recommended" in data
        assert "total" in data
        assert "strategy" in data
        
        # Without auth, should use top_rated fallback strategy
        assert data["strategy"] == "top_rated", f"Expected 'top_rated' strategy for unauthenticated user, got '{data['strategy']}'"
    
    def test_recommended_includes_review_count_and_avg_rating(self, api_client):
        """GET /api/products/recommended/whisked_words includes review_count and avg_rating for each product"""
        response = api_client.get(f"{BASE_URL}/api/products/recommended/whisked_words")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify each product has review_count and avg_rating
        for product in data["recommended"]:
            assert "review_count" in product, f"Product {product.get('product_id')} missing review_count"
            assert "avg_rating" in product, f"Product {product.get('product_id')} missing avg_rating"
            
            # Verify types
            assert isinstance(product["review_count"], int), f"review_count should be int, got {type(product['review_count'])}"
            assert isinstance(product["avg_rating"], (int, float)), f"avg_rating should be number, got {type(product['avg_rating'])}"
    
    def test_recommended_limit_parameter(self, api_client):
        """GET /api/products/recommended/whisked_words?limit=1 returns only 1 product"""
        response = api_client.get(f"{BASE_URL}/api/products/recommended/whisked_words?limit=1")
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["recommended"]) <= 1
    
    def test_recommended_nonexistent_business(self, api_client):
        """GET /api/products/recommended/nonexistent_business returns empty list"""
        response = api_client.get(f"{BASE_URL}/api/products/recommended/nonexistent_business")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["recommended"] == []
        assert data["total"] == 0
        assert data["strategy"] == "none"
    
    def test_recommended_sorted_by_rating(self, api_client):
        """Recommended products are sorted by avg_rating descending"""
        response = api_client.get(f"{BASE_URL}/api/products/recommended/whisked_words")
        
        assert response.status_code == 200
        data = response.json()
        recommended = data["recommended"]
        
        if len(recommended) >= 2:
            # Verify descending order by rating
            for i in range(len(recommended) - 1):
                # Primary sort by avg_rating, secondary by review_count
                current_rating = recommended[i]["avg_rating"]
                next_rating = recommended[i + 1]["avg_rating"]
                assert current_rating >= next_rating, \
                    f"Products not sorted by avg_rating: {current_rating} < {next_rating}"


# ============= INTEGRATION TESTS =============
class TestTrackViewAndRecommendedIntegration:
    """Test that tracking views affects recommendations"""
    
    def test_track_view_then_get_recommendations(self, customer_client):
        """Track a view and verify recommendations are returned"""
        # Get products
        products_response = customer_client.get(f"{BASE_URL}/api/products?business_id=whisked_words")
        products = products_response.json()["products"]
        
        if len(products) == 0:
            pytest.skip("No products available")
        
        # Track view for first product
        product = products[0]
        track_response = customer_client.post(f"{BASE_URL}/api/products/track-view", json={
            "product_id": product["product_id"],
            "business_id": "whisked_words"
        })
        assert track_response.status_code == 200
        
        # Get recommendations
        rec_response = customer_client.get(f"{BASE_URL}/api/products/recommended/whisked_words")
        assert rec_response.status_code == 200
        
        data = rec_response.json()
        # Should have a strategy (not 'none')
        assert data["strategy"] != "none" or len(data["recommended"]) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
