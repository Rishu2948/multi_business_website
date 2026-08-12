"""
Webhook signature verification.

Provides signature verification for payment webhooks (Razorpay, Stripe)
to prevent fraudulent webhook events.
"""

import hmac
import hashlib
from typing import Optional, Dict, Any
from fastapi import HTTPException, Request

from .config import get_razorpay_webhook_secret, skip_webhook_verify


class WebhookVerifier:
    """Verifies webhook signatures from payment providers."""
    
    def __init__(self):
        self.razorpay_secret = get_razorpay_webhook_secret()
    
    def verify_razorpay_webhook(
        self,
        payload: bytes,
        signature: str,
        webhook_secret: Optional[str] = None
    ) -> bool:
        """
        Verify Razorpay webhook signature.
        
        Razorpay uses HMAC SHA256 with the webhook secret.
        
        Args:
            payload: Raw webhook payload (bytes)
            signature: X-Razorpay-Signature header value
            webhook_secret: Optional override of webhook secret
        
        Returns:
            True if signature is valid, False otherwise
        """
        secret = webhook_secret or self.razorpay_secret
        
        if not secret:
            if skip_webhook_verify():
                return True  # Skip verification if configured
            raise ValueError("Razorpay webhook secret not configured")
        
        # Compute HMAC SHA256
        expected_signature = hmac.new(
            secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        # Compare signatures
        return hmac.compare_digest(expected_signature, signature)
    
    def verify_stripe_webhook(
        self,
        payload: bytes,
        signature: str,
        webhook_secret: Optional[str] = None
    ) -> bool:
        """
        Verify Stripe webhook signature.
        
        Stripe uses a more complex signature scheme with timestamp.
        This is a placeholder for future Stripe integration.
        
        Args:
            payload: Raw webhook payload (bytes)
            signature: Stripe-Signature header value
            webhook_secret: Optional override of webhook secret
        
        Returns:
            True if signature is valid, False otherwise
        """
        # Stripe webhooks are not currently implemented
        # This is a placeholder for future implementation
        if skip_webhook_verify():
            return True
        
        raise NotImplementedError("Stripe webhook verification not implemented")


async def verify_razorpay_webhook_request(
    request: Request,
    verifier: WebhookVerifier,
    webhook_secret: Optional[str] = None
) -> bytes:
    """
    Verify Razorpay webhook from FastAPI request.
    
    Args:
        request: FastAPI request
        verifier: WebhookVerifier instance
        webhook_secret: Optional webhook secret override
    
    Returns:
        Raw payload bytes if verification succeeds
    
    Raises:
        HTTPException: 403 if signature verification fails
    """
    # Get signature from header
    signature = request.headers.get("X-Razorpay-Signature")
    if not signature:
        raise HTTPException(
            status_code=403,
            detail="Missing X-Razorpay-Signature header"
        )
    
    # Read raw payload
    payload = await request.body()
    
    # Verify signature
    if not verifier.verify_razorpay_webhook(payload, signature, webhook_secret):
        raise HTTPException(
            status_code=403,
            detail="Invalid webhook signature"
        )
    
    return payload


async def verify_stripe_webhook_request(
    request: Request,
    verifier: WebhookVerifier,
    webhook_secret: Optional[str] = None
) -> bytes:
    """
    Verify Stripe webhook from FastAPI request.
    
    Args:
        request: FastAPI request
        verifier: WebhookVerifier instance
        webhook_secret: Optional webhook secret override
    
    Returns:
        Raw payload bytes if verification succeeds
    
    Raises:
        HTTPException: 403 if signature verification fails
    """
    # Get signature from header
    signature = request.headers.get("Stripe-Signature")
    if not signature:
        raise HTTPException(
            status_code=403,
            detail="Missing Stripe-Signature header"
        )
    
    # Read raw payload
    payload = await request.body()
    
    # Verify signature
    if not verifier.verify_stripe_webhook(payload, signature, webhook_secret):
        raise HTTPException(
            status_code=403,
            detail="Invalid webhook signature"
        )
    
    return payload


def verify_razorpay_webhook(
    payload: bytes,
    signature: str,
    webhook_secret: Optional[str] = None
) -> bool:
    """
    Verify Razorpay webhook signature (convenience function).
    
    Args:
        payload: Raw webhook payload
        signature: X-Razorpay-Signature header value
        webhook_secret: Optional webhook secret override
    
    Returns:
        True if valid, False otherwise
    """
    verifier = WebhookVerifier()
    return verifier.verify_razorpay_webhook(payload, signature, webhook_secret)


def verify_stripe_webhook(
    payload: bytes,
    signature: str,
    webhook_secret: Optional[str] = None
) -> bool:
    """
    Verify Stripe webhook signature (convenience function).
    
    Args:
        payload: Raw webhook payload
        signature: Stripe-Signature header value
        webhook_secret: Optional webhook secret override
    
    Returns:
        True if valid, False otherwise
    """
    verifier = WebhookVerifier()
    return verifier.verify_stripe_webhook(payload, signature, webhook_secret)
