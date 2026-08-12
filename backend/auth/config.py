"""
Authentication and security configuration.

Environment variables:
- JWT_SECRET: Secret key for JWT signing (required)
- ACCESS_TOKEN_TTL_SECONDS: Access token TTL in seconds (default: 900 = 15min)
- REFRESH_TOKEN_TTL_SECONDS: Refresh token TTL in seconds (default: 604800 = 7d)
- MAX_SESSIONS_PER_USER: Maximum concurrent sessions per user (default: 5)
- AUTH_ACCEPT_LEGACY_SESSION: Accept legacy session tokens during migration (default: true)
- WEBHOOK_SKIP_VERIFY: Skip webhook signature verification (default: false)
- MFA_ENFORCE_FOR_ADMINS: Enforce MFA for privileged roles (default: false)
- MFA_ENCRYPTION_KEY: Encryption key for MFA secrets (required if MFA enabled)
- REDIS_URL: Redis URL for rate limiting (optional, falls back to in-memory)
- AUTH_RATE_LIMIT_PER_MINUTE: Auth endpoint rate limit per IP (default: 10)
- RAZORPAY_WEBHOOK_SECRET: Razorpay webhook secret for signature verification
- ENVIRONMENT: Environment name (development/production)
"""

import os
from typing import Optional


def is_production() -> bool:
    """Check if running in production environment."""
    return os.environ.get("ENVIRONMENT", "development").lower() == "production"


def get_jwt_secret() -> str:
    """Get JWT secret key for token signing."""
    secret = os.environ.get("JWT_SECRET")
    if not secret:
        raise ValueError("JWT_SECRET environment variable is required")
    return secret


def get_access_token_ttl() -> int:
    """Get access token TTL in seconds."""
    return int(os.environ.get("ACCESS_TOKEN_TTL_SECONDS", "900"))  # 15 minutes


def get_refresh_token_ttl() -> int:
    """Get refresh token TTL in seconds."""
    return int(os.environ.get("REFRESH_TOKEN_TTL_SECONDS", "604800"))  # 7 days


def get_max_sessions_per_user() -> int:
    """Get maximum concurrent sessions per user."""
    return int(os.environ.get("MAX_SESSIONS_PER_USER", "5"))


def accept_legacy_session() -> bool:
    """Whether to accept legacy session tokens during migration."""
    return os.environ.get("AUTH_ACCEPT_LEGACY_SESSION", "true").lower() == "true"


def skip_webhook_verify() -> bool:
    """Whether to skip webhook signature verification."""
    skip = os.environ.get("WEBHOOK_SKIP_VERIFY", "false").lower() == "true"
    
    # Security guard: never allow skipping in production
    if skip and is_production():
        raise ValueError(
            "WEBHOOK_SKIP_VERIFY cannot be true in production environment. "
            "This is a security risk."
        )
    
    return skip


def enforce_mfa_for_admins() -> bool:
    """Whether to enforce MFA for privileged roles."""
    return os.environ.get("MFA_ENFORCE_FOR_ADMINS", "false").lower() == "true"


def get_mfa_encryption_key() -> Optional[str]:
    """Get encryption key for MFA secrets."""
    key = os.environ.get("MFA_ENCRYPTION_KEY")
    
    # If MFA is enforced, key is required
    if enforce_mfa_for_admins() and not key:
        raise ValueError(
            "MFA_ENCRYPTION_KEY is required when MFA_ENFORCE_FOR_ADMINS is true"
        )
    
    return key


def get_redis_url() -> Optional[str]:
    """Get Redis URL for rate limiting (optional)."""
    return os.environ.get("REDIS_URL")


def get_auth_rate_limit() -> int:
    """Get auth endpoint rate limit per minute per IP."""
    return int(os.environ.get("AUTH_RATE_LIMIT_PER_MINUTE", "10"))


def get_razorpay_webhook_secret() -> Optional[str]:
    """Get Razorpay webhook secret for signature verification."""
    return os.environ.get("RAZORPAY_WEBHOOK_SECRET")


def validate_production_config() -> list[str]:
    """
    Validate that production configuration is secure.
    Returns list of validation errors (empty if valid).
    """
    errors = []
    
    if is_production():
        # Check that webhook verification is not skipped
        if skip_webhook_verify():
            errors.append("WEBHOOK_SKIP_VERIFY cannot be true in production")
        
        # Check that MFA key exists if MFA is enforced
        if enforce_mfa_for_admins() and not get_mfa_encryption_key():
            errors.append("MFA_ENCRYPTION_KEY required when MFA_ENFORCE_FOR_ADMINS is true")
        
        # Check that JWT secret is set
        if not os.environ.get("JWT_SECRET"):
            errors.append("JWT_SECRET is required in production")
        
        # Check that webhook secret is set for payment processing
        if not get_razorpay_webhook_secret():
            errors.append("RAZORPAY_WEBHOOK_SECRET should be set in production for payment security")
    
    return errors
