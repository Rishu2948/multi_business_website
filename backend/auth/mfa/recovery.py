"""
MFA Recovery Module

Handles account recovery using backup codes and backup code regeneration.
"""

from datetime import datetime, timezone
from typing import List, Dict
from .backup_codes import generate_backup_codes, hash_backup_code, verify_backup_code, get_remaining_backup_codes


async def recover_with_backup_code(
    db,
    user_id: str,
    backup_code: str,
    ip_address: str
) -> Dict:
    """
    Recover account using backup code.
    
    Args:
        db: MongoDB database instance
        user_id: User ID
        backup_code: Backup code provided by user
        ip_address: IP address of the request
    
    Returns:
        Dictionary with recovery status and remaining backup codes
    
    Raises:
        ValueError: If backup code is invalid or already used
    """
    # Get user's MFA data
    user = await db.users.find_one(
        {"user_id": user_id},
        {"_id": 0, "mfa": 1}
    )
    
    if not user or not user.get("mfa", {}).get("enabled", False):
        raise ValueError("MFA is not enabled for this user")
    
    mfa_data = user["mfa"]
    backup_codes_hashed = mfa_data.get("backup_codes_hashed", [])
    used_backup_codes = mfa_data.get("used_backup_codes", [])
    
    # Find matching backup code
    matched_hash = None
    for backup_hash in backup_codes_hashed:
        if backup_hash not in used_backup_codes:
            if verify_backup_code(backup_code, backup_hash):
                matched_hash = backup_hash
                break
    
    if not matched_hash:
        # Emit audit event for failed recovery
        from ..audit import write_audit_event, AuditEventType
        await write_audit_event(
            db,
            event_type=AuditEventType.MFA_RECOVERY_FAILED,
            user_id=user_id,
            ip_address=ip_address,
            details={"reason": "invalid_backup_code"},
            success=False
        )
        
        raise ValueError("Invalid or already used backup code")
    
    # Mark backup code as used
    updated_used = used_backup_codes.copy()
    updated_used.append(matched_hash)
    
    # Update user
    await db.users.update_one(
        {"user_id": user_id},
        {"$set": {"mfa.used_backup_codes": updated_used}}
    )
    
    # Emit audit event for successful recovery
    from ..audit import write_audit_event, AuditEventType
    await write_audit_event(
        db,
        event_type=AuditEventType.MFA_RECOVERY,
        user_id=user_id,
        ip_address=ip_address,
        details={"method": "backup_code"},
        success=True
    )
    
    # Calculate remaining backup codes
    remaining = len([c for c in backup_codes_hashed if c not in updated_used])
    
    return {
        "success": True,
        "remaining_backup_codes": remaining,
        "total_backup_codes": len(backup_codes_hashed)
    }


async def regenerate_backup_codes(
    db,
    user_id: str,
    current_code: str,
    ip_address: str
) -> Dict:
    """
    Regenerate backup codes (requires MFA verification first).
    
    Args:
        db: MongoDB database instance
        user_id: User ID
        current_code: Current MFA code for verification
        ip_address: IP address of the request
    
    Returns:
        Dictionary with new backup codes
    
    Raises:
        ValueError: If MFA verification fails
    """
    # Verify current MFA code first
    from .verification import verify_mfa_code as verify_mfa_code_local
    try:
        await verify_mfa_code_local(
            db,
            user_id,
            current_code,
            ip_address,
            "regenerate_backup_codes"
        )
    except ValueError:
        raise ValueError("Invalid MFA code. Cannot regenerate backup codes.")
    
    # Generate new backup codes
    new_backup_codes = generate_backup_codes()
    new_backup_codes_hashed = [hash_backup_code(code) for code in new_backup_codes]
    
    # Update user with new backup codes
    await db.users.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "mfa.backup_codes_hashed": new_backup_codes_hashed,
                "mfa.used_backup_codes": []
            }
        }
    )
    
    # Emit audit event
    from ..audit import write_audit_event, AuditEventType
    await write_audit_event(
        db,
        event_type=AuditEventType.MFA_BACKUP_CODES_REGENERATED,
        user_id=user_id,
        ip_address=ip_address,
        details={"count": len(new_backup_codes)},
        success=True
    )
    
    return {
        "success": True,
        "backup_codes": new_backup_codes
    }


async def disable_mfa(
    db,
    user_id: str,
    admin_user_id: str,
    ip_address: str,
    reason: str = ""
) -> bool:
    """
    Disable MFA for a user (admin operation).
    
    Args:
        db: MongoDB database instance
        user_id: User ID to disable MFA for
        admin_user_id: User ID of admin performing the action
        ip_address: IP address of the request
        reason: Reason for disabling MFA
    
    Returns:
        True if MFA was disabled, False if not enabled
    
    Raises:
        ValueError: If admin lacks required privileges
    """
    # Verify admin has super_admin role
    admin = await db.users.find_one(
        {"user_id": admin_user_id},
        {"_id": 0, "role": 1}
    )
    
    if not admin or admin.get("role") != "super_admin":
        raise ValueError("Only super_admin can disable MFA for other users")
    
    # Disable MFA for user
    result = await db.users.update_one(
        {"user_id": user_id},
        {"$unset": {"mfa": ""}}
    )
    
    if result.modified_count > 0:
        # Emit audit event
        from ..audit import write_audit_event, AuditEventType
        await write_audit_event(
            db,
            event_type=AuditEventType.MFA_DISABLED,
            user_id=user_id,
            ip_address=ip_address,
            details={
                "admin_user_id": admin_user_id,
                "reason": reason
            },
            success=True
        )
        
        return True
    
    return False


async def reset_mfa(
    db,
    user_id: str,
    admin_user_id: str,
    ip_address: str,
    reason: str = ""
) -> Dict:
    """
    Reset MFA for a user (admin operation) - forces re-enrollment.
    
    Args:
        db: MongoDB database instance
        user_id: User ID to reset MFA for
        admin_user_id: User ID of admin performing the action
        ip_address: IP address of the request
        reason: Reason for MFA reset
    
    Returns:
        Dictionary with reset status
    
    Raises:
        ValueError: If admin lacks required privileges
    """
    # Verify admin has super_admin role
    admin = await db.users.find_one(
        {"user_id": admin_user_id},
        {"_id": 0, "role": 1}
    )
    
    if not admin or admin.get("role") != "super_admin":
        raise ValueError("Only super_admin can reset MFA for other users")
    
    # Remove MFA data (user must re-enroll)
    result = await db.users.update_one(
        {"user_id": user_id},
        {"$unset": {"mfa": ""}}
    )
    
    # Revoke all sessions for security
    from backend.auth.sessions import revoke_all_sessions
    revoked_count = await revoke_all_sessions(db, user_id)
    
    # Emit audit event
    from ..audit import write_audit_event, AuditEventType
    await write_audit_event(
        db,
        event_type=AuditEventType.MFA_RESET,
        user_id=user_id,
        ip_address=ip_address,
        details={
            "admin_user_id": admin_user_id,
            "reason": reason,
            "sessions_revoked": revoked_count
        },
        success=True
    )
    
    return {
        "success": True,
        "sessions_revoked": revoked_count,
        "message": "MFA reset. User must re-enroll before accessing admin functions."
    }


async def get_backup_codes_remaining_warning(db, user_id: str) -> Optional[Dict]:
    """
    Check if user is running low on backup codes and return warning if needed.
    
    Args:
        db: MongoDB database instance
        user_id: User ID
    
    Returns:
        Warning dictionary if running low, None otherwise
    """
    user = await db.users.find_one(
        {"user_id": user_id},
        {"_id": 0, "mfa": 1}
    )
    
    if not user or not user.get("mfa", {}).get("enabled", False):
        return None
    
    mfa_data = user["mfa"]
    backup_codes_hashed = mfa_data.get("backup_codes_hashed", [])
    used_backup_codes = mfa_data.get("used_backup_codes", [])
    
    remaining = len([c for c in backup_codes_hashed if c not in used_backup_codes])
    total = len(backup_codes_hashed)
    
    # Warn if less than 3 backup codes remaining
    if remaining < 3:
        return {
            "warning": "Low backup codes",
            "remaining": remaining,
            "total": total,
            "message": f"You have {remaining} backup codes remaining. Consider regenerating them."
        }
    
    return None
