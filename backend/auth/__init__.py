"""
Auth_Module - Centralized authentication and authorization package.

This package provides unified authentication, authorization, and security
functionality across the backend and ai-chatbot services.
"""

# Public API exports
from .config import (
    get_jwt_secret,
    get_access_token_ttl,
    get_refresh_token_ttl,
    get_max_sessions_per_user,
    accept_legacy_session,
    skip_webhook_verify,
    enforce_mfa_for_admins,
    get_mfa_encryption_key,
    get_redis_url,
    get_auth_rate_limit,
    get_razorpay_webhook_secret,
    is_production,
)

from .rbac import (
    Role,
    PRIVILEGED_ROLES,
    require_roles,
    check_business_access,
)

from .sessions import (
    SessionRecord,
    create_session,
    find_session,
    revoke_session,
    revoke_all_sessions,
    update_last_seen,
    enforce_concurrent_limit,
)

from .tokens import (
    TokenManager,
    mint_access_token,
    verify_access_token,
    mint_refresh_token,
    verify_refresh_token,
    rotate_refresh_token,
    validate_legacy_session,
)

from .dependencies import (
    get_current_user,
    get_optional_user,
    require_roles as require_roles_dep,
    require_business_access,
)

from .audit import (
    write_audit_event,
    AuditEventType,
)

from .rate_limit import (
    RateLimiter,
    check_rate_limit,
)

from .csrf import (
    validate_origin,
    CSRFProtection,
)

from .headers import (
    SecurityHeadersMiddleware,
)

from .mfa import (
    MFAManager,
    generate_mfa_secret,
    verify_mfa_token,
    encrypt_mfa_secret,
    decrypt_mfa_secret,
)

from .webhooks import (
    WebhookVerifier,
    verify_razorpay_webhook,
    verify_stripe_webhook,
)

__all__ = [
    # Config
    "get_jwt_secret",
    "get_access_token_ttl",
    "get_refresh_token_ttl",
    "get_max_sessions_per_user",
    "accept_legacy_session",
    "skip_webhook_verify",
    "enforce_mfa_for_admins",
    "get_mfa_encryption_key",
    "get_redis_url",
    "get_auth_rate_limit",
    "get_razorpay_webhook_secret",
    "is_production",
    # RBAC
    "Role",
    "PRIVILEGED_ROLES",
    "require_roles",
    "check_business_access",
    # Sessions
    "SessionRecord",
    "create_session",
    "find_session",
    "revoke_session",
    "revoke_all_sessions",
    "update_last_seen",
    "enforce_concurrent_limit",
    # Tokens
    "TokenManager",
    "mint_access_token",
    "verify_access_token",
    "mint_refresh_token",
    "verify_refresh_token",
    "rotate_refresh_token",
    "validate_legacy_session",
    # Dependencies
    "get_current_user",
    "get_optional_user",
    "require_roles_dep",
    "require_business_access",
    # Audit
    "write_audit_event",
    "AuditEventType",
    # Rate limiting
    "RateLimiter",
    "check_rate_limit",
    # CSRF
    "validate_origin",
    "CSRFProtection",
    # Headers
    "SecurityHeadersMiddleware",
    # MFA
    "MFAManager",
    "generate_mfa_secret",
    "verify_mfa_token",
    "encrypt_mfa_secret",
    "decrypt_mfa_secret",
    # Webhooks
    "WebhookVerifier",
    "verify_razorpay_webhook",
    "verify_stripe_webhook",
]
