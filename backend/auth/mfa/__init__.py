"""
MFA (Multi-Factor Authentication) Module

Provides TOTP-based multi-factor authentication for privileged users.

Modules:
- totp: TOTP secret generation and validation
- encryption: Secret encryption/decryption for secure storage
- backup_codes: Backup code generation and validation for account recovery
- device_trust: Device trust management for reduced MFA prompts
- enrollment: MFA enrollment flow management
- verification: MFA verification flow management
- recovery: Account recovery using backup codes
"""

from .totp import generate_totp_secret, generate_qr_code_url, validate_totp_code
from .encryption import encrypt_mfa_secret, decrypt_mfa_secret
from .backup_codes import generate_backup_codes, hash_backup_code, verify_backup_code
from .device_trust import add_trusted_device, verify_trusted_device, revoke_trusted_device
from .enrollment import start_enrollment, verify_enrollment, complete_enrollment
from .verification import verify_mfa_code, verify_mfa_for_operation
from .recovery import recover_with_backup_code, regenerate_backup_codes

# Helper functions for MFA enforcement
from backend.auth.config import enforce_mfa_for_admins


def should_enforce_mfa(role: str) -> bool:
    """
    Check if MFA should be enforced for a given role.
    
    Args:
        role: User role
    
    Returns:
        True if MFA should be enforced, False otherwise
    """
    if not enforce_mfa_for_admins():
        return False
    
    from backend.auth.rbac import is_privileged_role
    return is_privileged_role(role)


def is_user_mfa_enrolled(user: dict) -> bool:
    """
    Check if a user has MFA enabled.
    
    Args:
        user: User document from database
    
    Returns:
        True if MFA is enabled, False otherwise
    """
    return user.get("mfa", {}).get("enabled", False)


__all__ = [
    # TOTP
    'generate_totp_secret',
    'generate_qr_code_url',
    'validate_totp_code',
    # Encryption
    'encrypt_mfa_secret',
    'decrypt_mfa_secret',
    # Backup Codes
    'generate_backup_codes',
    'hash_backup_code',
    'verify_backup_code',
    # Device Trust
    'add_trusted_device',
    'verify_trusted_device',
    'revoke_trusted_device',
    # Enrollment
    'start_enrollment',
    'verify_enrollment',
    'complete_enrollment',
    # Verification
    'verify_mfa_code',
    'verify_mfa_for_operation',
    # Recovery
    'recover_with_backup_code',
    'regenerate_backup_codes',
    # Helpers
    'should_enforce_mfa',
    'is_user_mfa_enrolled',
]
