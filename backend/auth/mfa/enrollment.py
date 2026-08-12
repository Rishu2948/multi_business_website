"""
MFA Enrollment Module

Handles the MFA enrollment flow - from initial secret generation to verification and completion.
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, Optional
from .totp import generate_totp_secret, generate_qr_code_url, validate_totp_code
from .encryption import encrypt_mfa_secret
from .backup_codes import generate_backup_codes, hash_backup_code


async def start_enrollment(db, user_id: str, email: str, issuer: str = "Multi-Business Bakery") -> Dict:
    """
    Start MFA enrollment by generating TOTP secret and QR code.
    
    Args:
        db: MongoDB database instance
        user_id: User ID
        email: User's email address
        issuer: Issuer name for authenticator app
    
    Returns:
        Dictionary with QR code URL and manual secret (for devices without cameras)
    
    Raises:
        ValueError: If MFA is already enabled for user
    """
    # Check if user already has MFA enabled
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0, "mfa": 1})
    if user and user.get("mfa", {}).get("enabled", False):
        raise ValueError("MFA is already enabled for this user")
    
    # Generate TOTP secret
    secret = generate_totp_secret()
    encrypted_secret = encrypt_mfa_secret(secret)
    
    # Generate QR code URL
    qr_code_url = generate_qr_code_url(secret, email, issuer)
    
    # Store pending enrollment (expires in 10 minutes)
    await db.mfa_pending_enrollments.insert_one({
        "user_id": user_id,
        "secret_encrypted": encrypted_secret,
        "email": email,
        "issuer": issuer,
        "created_at": datetime.now(timezone.utc),
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=10)
    })
    
    return {
        "qr_code_url": qr_code_url,
        "manual_secret": secret,  # Only for manual entry
        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
    }


async def verify_enrollment(db, user_id: str, code: str) -> bool:
    """
    Verify TOTP code during enrollment flow.
    
    Args:
        db: MongoDB database instance
        user_id: User ID
        code: 6-digit TOTP code from authenticator app
    
    Returns:
        True if code is valid, False otherwise
    
    Raises:
        ValueError: If no pending enrollment found or enrollment expired
    """
    # Get pending enrollment
    pending = await db.mfa_pending_enrollments.find_one({
        "user_id": user_id
    })
    
    if not pending:
        raise ValueError("No pending MFA enrollment found")
    
    # Check if enrollment expired
    expires_at = pending.get("expires_at")
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    
    if datetime.now(timezone.utc) > expires_at:
        await db.mfa_pending_enrollments.delete_one({"user_id": user_id})
        raise ValueError("MFA enrollment expired. Please start over.")
    
    # Decrypt secret and verify code
    from .encryption import decrypt_mfa_secret
    secret = decrypt_mfa_secret(pending["secret_encrypted"])
    
    return validate_totp_code(code, secret)


async def complete_enrollment(db, user_id: str, code: str, trust_device: bool = False, device_info: Optional[Dict] = None) -> Dict:
    """
    Complete MFA enrollment by saving encrypted secret and generating backup codes.
    
    Args:
        db: MongoDB database instance
        user_id: User ID
        code: 6-digit TOTP code for verification
        trust_device: Whether to mark current device as trusted
        device_info: Device information (user_agent, ip_address) if trusting device
    
    Returns:
        Dictionary with success status and backup codes
    
    Raises:
        ValueError: If verification fails or no pending enrollment
    """
    # Verify the code first
    if not await verify_enrollment(db, user_id, code):
        raise ValueError("Invalid MFA code")
    
    # Get pending enrollment
    pending = await db.mfa_pending_enrollments.find_one({"user_id": user_id})
    
    # Generate backup codes
    backup_codes = generate_backup_codes()
    backup_codes_hashed = [hash_backup_code(code) for code in backup_codes]
    
    # Prepare MFA data
    mfa_data = {
        "enabled": True,
        "method": "totp",
        "enrolled_at": datetime.now(timezone.utc),
        "last_verified_at": datetime.now(timezone.utc),
        "secret_encrypted": pending["secret_encrypted"],
        "backup_codes_hashed": backup_codes_hashed,
        "used_backup_codes": []
    }
    
    # Add device trust if requested
    if trust_device and device_info:
        from .device_trust import create_trusted_device
        device_record = create_trusted_device(
            user_id,
            device_info.get("user_agent", ""),
            device_info.get("ip_address", "")
        )
        mfa_data["devices_trusted"] = [device_record]
    
    # Update user with MFA data
    await db.users.update_one(
        {"user_id": user_id},
        {"$set": {"mfa": mfa_data}}
    )
    
    # Delete pending enrollment
    await db.mfa_pending_enrollments.delete_one({"user_id": user_id})
    
    # Emit audit event
    from ..audit import write_audit_event, AuditEventType
    await write_audit_event(
        db,
        event_type=AuditEventType.MFA_ENROLLMENT,
        user_id=user_id,
        details={"method": "totp", "trust_device": trust_device},
        success=True
    )
    
    return {
        "success": True,
        "backup_codes": backup_codes,
        "trust_device": trust_device
    }


async def cancel_enrollment(db, user_id: str) -> bool:
    """
    Cancel pending MFA enrollment.
    
    Args:
        db: MongoDB database instance
        user_id: User ID
    
    Returns:
        True if enrollment was cancelled, False if no pending enrollment
    """
    result = await db.mfa_pending_enrollments.delete_one({"user_id": user_id})
    return result.deleted_count > 0


async def get_pending_enrollment(db, user_id: str) -> Optional[Dict]:
    """
    Get pending MFA enrollment status.
    
    Args:
        db: MongoDB database instance
        user_id: User ID
    
    Returns:
        Pending enrollment data or None if no pending enrollment
    """
    pending = await db.mfa_pending_enrollments.find_one(
        {"user_id": user_id},
        {"_id": 0, "expires_at": 1}
    )
    
    if not pending:
        return None
    
    # Check if expired
    expires_at = pending.get("expires_at")
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    
    if datetime.now(timezone.utc) > expires_at:
        await db.mfa_pending_enrollments.delete_one({"user_id": user_id})
        return None
    
    return pending
