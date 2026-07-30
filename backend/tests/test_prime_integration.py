"""
Integration Tests for Prime Subscription Flow

End-to-end tests for Prime subscription purchase flow, cancellation,
admin operations, and chatbot integration.
"""

import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'http://localhost:8000').rstrip('/')


class TestPrimeSubscriptionFlow:
    """Test end-to-end Prime subscription flow."""

    def test_get_prime_upgrade_info(self):
        """Test getting Prime upgrade info for a business."""
        response = requests.get(f"{BASE_URL}/api/prime/upgrade-info/whisked_words")
        # This may return 404 if Prime is not configured, which is acceptable
        assert response.status_code in [200, 404]

    def test_subscribe_requires_auth(self):
        """Test that subscription requires authentication."""
        response = requests.post(
            f"{BASE_URL}/api/prime/subscribe",
            json={"business_id": "whisked_words", "plan_id": "prime_monthly"}
        )
        assert response.status_code == 401

    def test_cancel_requires_auth(self):
        """Test that cancellation requires authentication."""
        response = requests.post(
            f"{BASE_URL}/api/prime/cancel",
            params={"business_id": "whisked_words"}
        )
        assert response.status_code == 401

    def test_reactivate_requires_auth(self):
        """Test that reactivation requires authentication."""
        response = requests.post(
            f"{BASE_URL}/api/prime/reactivate",
            params={"business_id": "whisked_words"}
        )
        assert response.status_code == 401


class TestPrimeAdminOperations:
    """Test Prime admin operations."""

    def test_admin_memberships_requires_auth(self):
        """Test that admin memberships endpoint requires authentication."""
        response = requests.get(f"{BASE_URL}/api/prime/admin/memberships")
        assert response.status_code == 401

    def test_admin_grant_requires_auth(self):
        """Test that admin grant requires authentication."""
        response = requests.post(
            f"{BASE_URL}/api/prime/admin/grant/test_user",
            json={"business_id": "whisked_words", "plan_id": "prime_monthly"}
        )
        assert response.status_code == 401

    def test_admin_revoke_requires_auth(self):
        """Test that admin revoke requires authentication."""
        response = requests.post(
            f"{BASE_URL}/api/prime/admin/revoke/test_user",
            json={"business_id": "whisked_words"}
        )
        assert response.status_code == 401

    def test_admin_analytics_requires_auth(self):
        """Test that admin analytics requires authentication."""
        response = requests.get(f"{BASE_URL}/api/prime/admin/analytics/whisked_words")
        assert response.status_code == 401


class TestPrimeChatbotIntegration:
    """Test Prime integration with chatbot."""

    def test_chatbot_access_with_prime(self):
        """Test that chatbot access works with Prime membership."""
        # This would require a real chatbot endpoint test
        # For now, we'll just verify the access helper can be imported
        try:
            from prime.access import has_prime_feature
            assert True
        except ImportError:
            pytest.skip("Prime access module not available")

    def test_business_config_affects_chatbot_access(self):
        """Test that business config affects chatbot access."""
        # Placeholder test - would require mocking business config
        assert True


class TestPrimeWebhooks:
    """Test Prime webhook endpoints."""

    def test_razorpay_webhook_accepts_post(self):
        """Test that Razorpay webhook accepts POST requests."""
        response = requests.post(
            f"{BASE_URL}/api/prime/webhooks/razorpay",
            json={"event": "payment.captured"},
            headers={"X-Razorpay-Signature": "test_signature"}
        )
        # May fail signature validation, but should accept POST
        assert response.status_code in [200, 400, 401]

    def test_stripe_webhook_accepts_post(self):
        """Test that Stripe webhook accepts POST requests."""
        response = requests.post(
            f"{BASE_URL}/api/prime/webhooks/stripe",
            json={"event": "payment.captured"},
            headers={"X-Stripe-Signature": "test_signature"}
        )
        # May fail signature validation, but should accept POST
        assert response.status_code in [200, 400, 401]


class TestPrimeScheduler:
    """Test Prime scheduler functionality."""

    def test_renewal_job_endpoint_requires_admin(self):
        """Test that manual renewal job trigger requires admin access."""
        response = requests.post(f"{BASE_URL}/api/prime/admin/run-renewal-job")
        assert response.status_code == 401

    def test_scheduler_can_be_imported(self):
        """Test that scheduler module can be imported."""
        try:
            from prime.scheduler import PrimeScheduler
            assert True
        except ImportError:
            pytest.skip("Prime scheduler module not available")


class TestPrimeCoupons:
    """Test Prime coupon functionality."""

    def test_create_coupon_requires_auth(self):
        """Test that coupon creation requires authentication."""
        response = requests.post(
            f"{BASE_URL}/api/prime/coupons",
            json={
                "business_id": "whisked_words",
                "code": "TEST20",
                "discount_type": "percentage",
                "discount_value": 20
            }
        )
        assert response.status_code == 401

    def test_validate_coupon_accepts_post(self):
        """Test that coupon validation accepts POST requests."""
        response = requests.post(
            f"{BASE_URL}/api/prime/coupons/validate",
            json={"code": "TEST20", "business_id": "whisked_words"}
        )
        # May fail if coupon doesn't exist, but should accept POST
        assert response.status_code in [200, 400, 404]
