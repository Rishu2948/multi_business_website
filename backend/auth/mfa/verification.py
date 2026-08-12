"""
MFA Verification Module

Handles MFA code verification for login and sensitive operations.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, Dict
from .totp import validate_totp_code
from .encryption import decrypt_mfa_secret
from .backup_codes import verify_backup_code, mark_backup_code_used
from .device_trust import should_trust_device, create_trusted_device, is_device_trusted


async def verify_mfa_code(
    db,
    user_id: str,
    code: str,
    ip_address: str,
    user_agent: str,
    trust_device: bool = False
) -> Dict:
    """
    Verify MFA code for user login.
    
    Args:
        db: MongoDB database instance
        user_id: User ID
        code: 6-digit TOTP code or backup code
        ip_address: IP address of the request
        user_agent: User agent string
        trust_device: Whether to mark current device as trusted
    
    Returns:
        Dictionary with verification status and trust info
    
    Raises:
        ValueError: If MFA is not enabled or code is invalid
    """
    # Get user's MFA data
    user = await db.users.find_one(
        {"user_id": user_id},
        {"_id": 0, "mfa": 1}
    )
    
    if not user or not user.get("mfa", {}).get("enabled", False):
        raise ValueError("MFA is not enabled for this user")
    
    mfa_data = user["mfa"]
    secret_encrypted = mfa_data.get("secret_encrypted")
    backup_codes_hashed = mfa_data.get("backup_codes_hashed", [])
    used_backup_codes = mfa_data.get("used_backup_codes", [])
    
    # Try TOTP validation first
    secret = decrypt_mfa_secret(secret_encrypted)
    totp_valid = validate_totp_code(code, secret)
    
    if totp_valid:
        # Update last verified timestamp
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": {"mfa.last_verified_at": datetime.now(timezone.utc)}}
        )
        
        # Handle device trust
        device_trusted = False
        if trust_device:
            device_record = create_trusted_device(user_id, user_agent, ip_address)
            await db.users.update_one(
                {"user_id": user_id},
                {"$push": {"mfa.devices_trusted": device_record}}
            )
            device_trusted = True
        
        # Emit audit event
        from ..audit import write_audit_event, AuditEventType
        await write_audit_event(
            db,
            event_type=AuditEventType.MFA_VERIFICATION,
            user_id=user_id,
            ip_address=ip_address,
            details={"method": "totp", "trust_device": trust_device},
            success=True
        )
        
        return {
            "success": True,
            "method": "totp",
            "device_trusted": device_trusted
        }
    
    # Try backup code validation
    for backup_hash in backup_codes_hashed:
        if backup_hash not in used_backup_codes:
            if verify_backup_code(code, backup_hash):
                # Mark backup code as used
                updated_used = mark_backup_code_used(used_backup_codes, code)
                await db.users.update_one(
                    {"user_id": user_id},
                    {"$set": {"mfa.used_backup_codes": updated_used}}
                )
                
                # Emit audit event
                from ..audit import write_audit_event, AuditEventType
                await write_audit_event(
                    db,
                    event_type=AuditEventType.MFA_VERIFICATION,
                    user_id=user_id,
                    ip_address=ip_address,
                    details={"method": "backup_code"},
                    success=True
                )
                
                return {
                    "success": True,
                    "method": "backup_code",
                    "device_trusted": False
                }
    
    # Code is invalid
    # Emit audit event for failed verification
    from ..audit import write_audit_event, AuditEventType
    await write_audit_event(
        db,
        event_type=AuditEventType.MFA_VERIFICATION_FAILED,
        user_id=user_id,
        ip_address=ip_address,
        details={"reason": "invalid_code"},
        success=False
    )
    
    raise ValueError("Invalid MFA code")


async def check_device_trust(
    db,
    user_id: str,
    ip_address: str,
    user_agent: str
) -> bool:
    """
    Check if current device is trusted (can skip MFA).
    
    Args:
        db: MongoDB database instance
        user_id: User ID
        ip_address: IP address
        user_agent: User agent string
    
    Returns:
        True if device is trusted, False otherwise
    """
    user = await db.users.find_one(
        {"user_id": user_id},
        {"_id": 0, "mfa.devices_trusted": 1}
    )
    
    if not user:
        return False
    
    trusted_devices = user.get("mfa", {}).get("devices_trusted", [])
    
    return should_trust_device(user_id, user_agent, ip_address, trusted_devices) is not None


async def verify_mfa_for_operation(
    db,
    user_id: str,
    code: str,
    operation: str,
    ip_address: str
) -> bool:
    """
    Verify MFA code for sensitive operation (e.g., role change, bulk delete).
    
    Args:
        db: MongoDB database instance
        user_id: User ID
        code: 6-digit TOTP code
        operation: Description of the operation being performed
        ip_address: IP address
    
    Returns:
        True if code is valid, False otherwise
    """
    # Get user's MFA data
    user = await db.users.find_one(
        {"user_id": user_id},
        {"_id": 0, "mfa": 1}
    )
    
    if not user or not user.get("mfa", {}).get("enabled", False):
        # If MFA is not enabled, skip verification (backward compatibility)
        return True
    
    mfa_data = user["mfa"]
    secret_encrypted = mfa_data.get("secret_encrypted")
    
    # Validate TOTP code
    secret = decrypt_mfa_secret(secret_encrypted)
    totp_valid = validate_totp_code(code, secret)
    
    if totp_valid:
        # Update last verified timestamp
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": {"mfa.last_verified_at": datetime.now(timezone.utc)}}
        )
        
        # Emit audit event
        from ..audit import write_audit_event, AuditEventType
        await write_audit_event(
            db,
            event_type=AuditEventType.PRIVILEGED_ACTION,
            user_id=user_id,
            ip_address=ip_address,
            details={
                "action": operation,
                "mfa_verified": True
            },
            success=True
        )
        
        return True
    
    # Emit audit event for failed verification
    from ..audit import write_audit_event, AuditEventType
    await write_audit_event(
        db,
        event_type=AuditEventType.PRIVILEGED_ACTION,
        user_id=user_id,
        ip_address=ip_address,
        details={
            "action": operation,
            "mfa_verified": False,
            "reason": "invalid_mfa_code"
        },
        success=False
    )
    
    return False


async def get_mfa_status(db, user_id: str) -> Dict:
    """
    Get MFA enrollment status for a user.
    
    Args:
        db: MongoDB database instance
        user_id: User ID
    
    Returns:
        Dictionary with MFA status information
    """
    user = await db.users.find_one(
        {"user_id": user_id},
        {"_id": 0, "mfa": 1}
    )
    
    if not user:
        return {"enabled": False}
    
    mfa_data = user.get("mfa", {})
    
    # Count remaining backup codes
    backup_codes_hashed = mfa_data.get("backup_codes_hashed", [])
    used_backup_codes = mfa_data.get("used_backup_codes", [])
    remaining_backup_codes = len([c for c in backup_codes_hashed if c not in used_backup_codes])
    
    # Count trusted devices
    trusted_devices = mfa_data.get("devices_trusted", [])
    from .device_trust import cleanup_expired_devices
    active_devices = cleanup_expired_devices(trusted_devices)
    
    return {
        "enabled": mfa_data.get("enabled", False),
        "method": mfa_data.get("method"),
        "enrolled_at": mfa_data.get("enrolled_at"),
        "last_verified_at": mfa_data.get("last_verified_at"),
        "remaining_backup_codes": remaining_backup_codes,
        "total_backup_codes": len(backup_codes_hashed),
        "trusted_devices_count": len(active_devices)
    }
