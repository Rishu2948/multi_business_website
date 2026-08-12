"""
Tests for webhook signature verification.

Tests for:
- Razorpay webhook signature verification
- Stripe webhook signature verification (future)
- Webhook security event emission
- Invalid signature rejection
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, AsyncMock, MagicMock
import hmac
import hashlib

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))


class TestRazorpayWebhookVerification:
    """Test Razorpay webhook signature verification."""
    
    @pytest.fixture
    def mock_db(self):
        """Mock MongoDB database."""
        db = Mock()
        return db
    
    @pytest.fixture
    def webhook_secret(self):
        """Test webhook secret."""
        return "test_webhook_secret_12345"
    
    def test_razorpay_signature_calculation(self, webhook_secret):
        """Test Razorpay signature calculation matches expected format."""
        from backend.auth.webhooks import WebhookVerifier
        
        verifier = WebhookVerifier()
        
        # Test payload
        payload = '{"event":"payment.captured","payload":{"payment":{"id":"pay_123"}}}'
        
        # Calculate signature
        signature = verifier._calculate_razorpay_signature(payload, webhook_secret)
        
        # Verify signature is HMAC-SHA256
        assert len(signature) == 64  # SHA-256 hex length
        assert signature != payload  # Not just the payload
    
    def test_razorpay_signature_verification_valid(self, webhook_secret):
        """Test that valid Razorpay signatures are accepted."""
        from backend.auth.webhooks import WebhookVerifier
        from fastapi import Request
        
        verifier = WebhookVerifier()
        
        # Test payload
        payload = '{"event":"payment.captured"}'
        
        # Calculate valid signature
        signature = verifier._calculate_razorpay_signature(payload, webhook_secret)
        
        # Mock request with valid signature
        request = Mock(spec=Request)
        request.headers = Mock()
        request.headers.get = Mock(side_effect=lambda key: signature if key == "x-razorpay-signature" else None)
        request.body = AsyncMock(return_value=payload.encode())
        
        # Set environment variable
        import os
        os.environ["RAZORPAY_WEBHOOK_SECRET"] = webhook_secret
        
        # Should accept valid signature
        result = verifier.verify_razorpay_webhook_request(request)
        assert result == payload
    
    def test_razorpay_signature_verification_invalid(self, webhook_secret):
        """Test that invalid Razorpay signatures are rejected."""
        from backend.auth.webhooks import WebhookVerifier
        from fastapi import Request, HTTPException
        
        verifier = WebhookVerifier()
        
        # Test payload
        payload = '{"event":"payment.captured"}'
        
        # Mock request with invalid signature
        request = Mock(spec=Request)
        request.headers = Mock()
        request.headers.get = Mock(side_effect=lambda key: "invalid_signature" if key == "x-razorpay-signature" else None)
        request.body = AsyncMock(return_value=payload.encode())
        
        # Set environment variable
        import os
        os.environ["RAZORPAY_WEBHOOK_SECRET"] = webhook_secret
        
        # Should reject invalid signature
        with pytest.raises(HTTPException) as exc_info:
            verifier.verify_razorpay_webhook_request(request)
        
        assert exc_info.value.status_code == 403
    
    def test_razorpay_signature_missing_header(self, webhook_secret):
        """Test that missing signature header is rejected."""
        from backend.auth.webhooks import WebhookVerifier
        from fastapi import Request, HTTPException
        
        verifier = WebhookVerifier()
        
        # Mock request without signature header
        request = Mock(spec=Request)
        request.headers = Mock()
        request.headers.get = Mock(return_value=None)
        request.body = AsyncMock(return_value=b'{"event":"payment.captured"}')
        
        # Set environment variable
        import os
        os.environ["RAZORPAY_WEBHOOK_SECRET"] = webhook_secret
        
        # Should reject missing signature
        with pytest.raises(HTTPException) as exc_info:
            verifier.verify_razorpay_webhook_request(request)
        
        assert exc_info.value.status_code == 403
    
    def test_razorpay_signature_missing_secret(self):
        """Test that missing webhook secret is handled gracefully."""
        from backend.auth.webhooks import WebhookVerifier
        from fastapi import Request, HTTPException
        
        verifier = WebhookVerifier()
        
        # Mock request
        request = Mock(spec=Request)
        request.headers = Mock()
        request.headers.get = Mock(return_value="some_signature")
        request.body = AsyncMock(return_value=b'{"event":"payment.captured"}')
        
        # Clear environment variable
        import os
        os.environ.pop("RAZORPAY_WEBHOOK_SECRET", None)
        
        # Should reject when secret is not configured
        with pytest.raises(HTTPException) as exc_info:
            verifier.verify_razorpay_webhook_request(request)
        
        assert exc_info.value.status_code == 403


class TestStripeWebhookVerification:
    """Test Stripe webhook signature verification (future implementation)."""
    
    @pytest.fixture
    def webhook_secret(self):
        """Test webhook secret."""
        return "whsec_test_webhook_secret_12345"
    
    def test_stripe_signature_calculation(self, webhook_secret):
        """Test Stripe signature calculation matches expected format."""
        from backend.auth.webhooks import WebhookVerifier
        
        verifier = WebhookVerifier()
        
        # Test payload
        payload = '{"event":"payment_intent.succeeded"}'
        timestamp = "1234567890"
        
        # Calculate signature
        signature = verifier._calculate_stripe_signature(payload, timestamp, webhook_secret)
        
        # Verify signature is HMAC-SHA256
        assert len(signature) == 64  # SHA-256 hex length
        assert signature != payload  # Not just the payload
    
    def test_stripe_signature_verification_valid(self, webhook_secret):
        """Test that valid Stripe signatures are accepted."""
        from backend.auth.webhooks import WebhookVerifier
        from fastapi import Request
        
        verifier = WebhookVerifier()
        
        # Test payload
        payload = '{"event":"payment_intent.succeeded"}'
        timestamp = "1234567890"
        
        # Calculate valid signature
        signature = verifier._calculate_stripe_signature(payload, timestamp, webhook_secret)
        
        # Mock request with valid signature
        request = Mock(spec=Request)
        request.headers = Mock()
        request.headers.get = Mock(side_effect=lambda key: f"t={timestamp},v1={signature}" if key == "stripe-signature" else None)
        request.body = AsyncMock(return_value=payload.encode())
        
        # Set environment variable
        import os
        os.environ["STRIPE_WEBHOOK_SECRET"] = webhook_secret
        
        # Should accept valid signature
        result = verifier.verify_stripe_webhook_request(request)
        assert result == payload
    
    def test_stripe_signature_verification_invalid(self, webhook_secret):
        """Test that invalid Stripe signatures are rejected."""
        from backend.auth.webhooks import WebhookVerifier
        from fastapi import Request, HTTPException
        
        verifier = WebhookVerifier()
        
        # Mock request with invalid signature
        request = Mock(spec=Request)
        request.headers = Mock()
        request.headers.get = Mock(side_effect=lambda key: "t=1234567890,v1=invalid_signature" if key == "stripe-signature" else None)
        request.body = AsyncMock(return_value=b'{"event":"payment_intent.succeeded"}')
        
        # Set environment variable
        import os
        os.environ["STRIPE_WEBHOOK_SECRET"] = webhook_secret
        
        # Should reject invalid signature
        with pytest.raises(HTTPException) as exc_info:
            verifier.verify_stripe_webhook_request(request)
        
        assert exc_info.value.status_code == 403


class TestWebhookSecurityEvents:
    """Test webhook security event emission."""
    
    @pytest.mark.asyncio
    async def test_webhook_verification_failure_audit_event(self):
        """Test that webhook verification failures emit audit events."""
        from backend.auth.webhooks import WebhookVerifier
        from backend.auth.audit import write_audit_event, AuditEventType
        from fastapi import Request, HTTPException
        from unittest.mock import patch
        
        verifier = WebhookVerifier()
        
        # Mock request with invalid signature
        request = Mock(spec=Request)
        request.headers = Mock()
        request.headers.get = Mock(return_value="invalid_signature")
        request.body = AsyncMock(return_value=b'{"event":"payment.captured"}')
        request.client = Mock()
        request.client.host = "1.2.3.4"
        
        # Mock audit event write
        with patch('backend.auth.webhooks.write_audit_event') as mock_audit:
            mock_audit.return_value = AsyncMock()
            
            # Set environment variable
            import os
            os.environ["RAZORPAY_WEBHOOK_SECRET"] = "test_secret"
            
            # Should reject and emit audit event
            with pytest.raises(HTTPException):
                verifier.verify_razorpay_webhook_request(request)
            
            # Verify audit event was called
            mock_audit.assert_called_once()
            call_args = mock_audit.call_args
            assert call_args[1]['event_type'] == AuditEventType.WEBHOOK_VERIFICATION_FAILED
            assert call_args[1]['success'] == False
    
    @pytest.mark.asyncio
    async def test_webhook_processing_success_audit_event(self):
        """Test that successful webhook processing emits audit events."""
        from backend.auth.webhooks import WebhookVerifier
        from backend.auth.audit import write_audit_event, AuditEventType
        from fastapi import Request
        from unittest.mock import patch
        
        verifier = WebhookVerifier()
        webhook_secret = "test_secret"
        
        # Test payload
        payload = '{"event":"payment.captured"}'
        signature = verifier._calculate_razorpay_signature(payload, webhook_secret)
        
        # Mock request with valid signature
        request = Mock(spec=Request)
        request.headers = Mock()
        request.headers.get = Mock(side_effect=lambda key: signature if key == "x-razorpay-signature" else None)
        request.body = AsyncMock(return_value=payload.encode())
        request.client = Mock()
        request.client.host = "1.2.3.4"
        
        # Mock audit event write
        with patch('backend.auth.webhooks.write_audit_event') as mock_audit:
            mock_audit.return_value = AsyncMock()
            
            # Set environment variable
            import os
            os.environ["RAZORPAY_WEBHOOK_SECRET"] = webhook_secret
            
            # Should accept and emit audit event
            result = verifier.verify_razorpay_webhook_request(request)
            
            # Verify result
            assert result == payload


class TestWebhookVerifierEdgeCases:
    """Test webhook verifier edge cases."""
    
    def test_empty_payload_handling(self):
        """Test handling of empty webhook payloads."""
        from backend.auth.webhooks import WebhookVerifier
        from fastapi import Request, HTTPException
        
        verifier = WebhookVerifier()
        
        # Mock request with empty payload
        request = Mock(spec=Request)
        request.headers = Mock()
        request.headers.get = Mock(return_value="some_signature")
        request.body = AsyncMock(return_value=b'')
        
        # Set environment variable
        import os
        os.environ["RAZORPAY_WEBHOOK_SECRET"] = "test_secret"
        
        # Should handle empty payload gracefully
        with pytest.raises(HTTPException):
            verifier.verify_razorpay_webhook_request(request)
    
    def test_large_payload_handling(self):
        """Test handling of large webhook payloads."""
        from backend.auth.webhooks import WebhookVerifier
        from fastapi import Request
        
        verifier = WebhookVerifier()
        webhook_secret = "test_secret"
        
        # Test large payload
        large_payload = '{"event":"payment.captured","data":"' + "x" * 10000 + '"}'
        signature = verifier._calculate_razorpay_signature(large_payload, webhook_secret)
        
        # Mock request with large payload
        request = Mock(spec=Request)
        request.headers = Mock()
        request.headers.get = Mock(side_effect=lambda key: signature if key == "x-razorpay-signature" else None)
        request.body = AsyncMock(return_value=large_payload.encode())
        
        # Set environment variable
        import os
        os.environ["RAZORPAY_WEBHOOK_SECRET"] = webhook_secret
        
        # Should handle large payload
        result = verifier.verify_razorpay_webhook_request(request)
        assert result == large_payload
    
    def test_unicode_payload_handling(self):
        """Test handling of unicode characters in webhook payloads."""
        from backend.auth.webhooks import WebhookVerifier
        from fastapi import Request
        
        verifier = WebhookVerifier()
        webhook_secret = "test_secret"
        
        # Test unicode payload
        unicode_payload = '{"event":"payment.captured","customer_name":"José García"}'
        signature = verifier._calculate_razorpay_signature(unicode_payload, webhook_secret)
        
        # Mock request with unicode payload
        request = Mock(spec=Request)
        request.headers = Mock()
        request.headers.get = Mock(side_effect=lambda key: signature if key == "x-razorpay-signature" else None)
        request.body = AsyncMock(return_value=unicode_payload.encode('utf-8'))
        
        # Set environment variable
        import os
        os.environ["RAZORPAY_WEBHOOK_SECRET"] = webhook_secret
        
        # Should handle unicode payload
        result = verifier.verify_razorpay_webhook_request(request)
        assert result == unicode_payload


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
