"""
Audit logging for security-relevant events.

Records authentication, authorization, and security events to the
audit_logs collection for compliance and security monitoring.
"""

from datetime import datetime, timezone
from typing import Optional, Dict, Any
from enum import Enum


class AuditEventType(str, Enum):
    """Types of audit events."""
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    LOGOUT = "logout"
    TOKEN_REFRESH = "token_refresh"
    TOKEN_REUSE_DETECTED = "token_reuse_detected"
    SESSION_REVOKED = "session_revoked"
    ALL_SESSIONS_REVOKED = "all_sessions_revoked"
    ROLE_CHANGED = "role_changed"
    BUSINESS_ACCESS_CHANGED = "business_access_changed"
    MFA_ENROLLMENT = "mfa_enrollment"
    MFA_VERIFICATION = "mfa_verification"
    MFA_VERIFICATION_FAILED = "mfa_verification_failed"
    MFA_RECOVERY = "mfa_recovery"
    MFA_RECOVERY_FAILED = "mfa_recovery_failed"
    MFA_DISABLED = "mfa_disabled"
    MFA_RESET = "mfa_reset"
    MFA_BACKUP_CODES_REGENERATED = "mfa_backup_codes_regenerated"
    WEBHOOK_VERIFICATION_FAILED = "webhook_verification_failed"
    WEBHOOK_PROCESSED = "webhook_processed"
    PRIVILEGED_ACTION = "privileged_action"
    AUTHORIZATION_FAILED = "authorization_failed"


async def write_audit_event(
    db,
    event_type: AuditEventType,
    user_id: Optional[str] = None,
    business_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    resource: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    success: bool = True,
) -> str:
    """
    Write an audit event to the audit_logs collection.
    
    IMPORTANT: Never log secrets, passwords, tokens, or sensitive PII.
    
    Args:
        db: MongoDB database instance
        event_type: Type of audit event
        user_id: User ID if applicable
        business_id: Business ID if applicable
        ip_address: Client IP address
        user_agent: Client user agent
        resource: Resource being accessed (e.g., endpoint, order_id)
        details: Additional event details (sanitized, no secrets)
        success: Whether the operation succeeded
    
    Returns:
        Audit event ID
    """
    import uuid
    
    audit_id = f"audit_{uuid.uuid4().hex}"
    
    # Sanitize details to ensure no secrets are logged
    sanitized_details = _sanitize_details(details) if details else {}
    
    audit_event = {
        "audit_id": audit_id,
        "event_type": event_type.value,
        "user_id": user_id,
        "business_id": business_id,
        "ip_address": ip_address,
        "user_agent": user_agent,
        "resource": resource,
        "details": sanitized_details,
        "success": success,
        "timestamp": datetime.now(timezone.utc),
    }
    
    await db.audit_logs.insert_one(audit_event)
    
    return audit_id


def _sanitize_details(details: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitize details to remove sensitive information.
    
    Removes common secret fields like passwords, tokens, API keys, etc.
    
    Args:
        details: Original details dict
    
    Returns:
        Sanitized details dict
    """
    sensitive_keys = {
        "password", "token", "secret", "api_key", "private_key",
        "session_token", "refresh_token", "access_token", "authorization",
        "credit_card", "ssn", "social_security", "cvv", "cvc"
    }
    
    sanitized = {}
    for key, value in details.items():
        key_lower = key.lower()
        if any(sensitive in key_lower for sensitive in sensitive_keys):
            sanitized[key] = "[REDACTED]"
        else:
            sanitized[key] = value
    
    return sanitized


async def ensure_audit_indexes(db) -> None:
    """
    Create necessary indexes for audit_logs collection.
    
    Should be called on application startup.
    """
    # Index for user lookups
    await db.audit_logs.create_index(
        [("user_id", 1)],
        background=True,
        name="audit_logs_user_id"
    )
    
    # Index for event type lookups
    await db.audit_logs.create_index(
        [("event_type", 1)],
        background=True,
        name="audit_logs_event_type"
    )
    
    # Index for timestamp queries (most recent events)
    await db.audit_logs.create_index(
        [("timestamp", -1)],
        background=True,
        name="audit_logs_timestamp"
    )
    
    # Compound index for user + timestamp
    await db.audit_logs.create_index(
        [("user_id", 1), ("timestamp", -1)],
        background=True,
        name="audit_logs_user_timestamp"
    )
    
    # TTL index: keep audit logs for 90 days by default
    await db.audit_logs.create_index(
        [("timestamp", 1)],
        expireAfterSeconds=90 * 24 * 3600,  # 90 days
        background=True,
        name="audit_logs_ttl"
    )
