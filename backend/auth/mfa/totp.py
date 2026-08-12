"""
TOTP (Time-Based One-Time Password) Module

Handles TOTP secret generation, QR code URL generation, and code validation.
Based on RFC 6238 specification.
"""

import secrets
import pyotp
from typing import Optional


def generate_totp_secret() -> str:
    """
    Generate a cryptographically secure random TOTP secret.
    
    Returns:
        Base32-encoded TOTP secret (16 bytes)
    """
    return secrets.token_urlsafe(32)


def generate_qr_code_url(secret: str, email: str, issuer: str) -> str:
    """
    Generate QR code provisioning URL for authenticator apps.
    
    Args:
        secret: TOTP secret (base32-encoded)
        email: User's email address
        issuer: Issuer name (e.g., "Multi-Business Bakery")
    
    Returns:
        URL that can be used to generate QR code
    """
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(
        name=email,
        issuer_name=issuer
    )


def validate_totp_code(code: str, secret: str, window: int = 1) -> bool:
    """
    Validate TOTP code against secret with time window.
    
    Args:
        code: 6-digit TOTP code from authenticator app
        secret: TOTP secret (base32-encoded)
        window: Number of time steps to allow for clock drift (default: 1)
    
    Returns:
        True if code is valid, False otherwise
    """
    try:
        totp = pyotp.TOTP(secret)
        return totp.verify(code, valid_window=window)
    except Exception:
        return False


def get_current_totp_code(secret: str) -> Optional[str]:
    """
    Get current TOTP code for testing purposes only.
    
    WARNING: This should only be used in development/testing environments.
    Never expose this in production or to end users.
    
    Args:
        secret: TOTP secret (base32-encoded)
    
    Returns:
        Current 6-digit TOTP code
    """
    try:
        totp = pyotp.TOTP(secret)
        return totp.now()
    except Exception:
        return None


def get_totp_remaining_time(secret: str) -> int:
    """
    Get remaining time until next TOTP code changes.
    
    Args:
        secret: TOTP secret (base32-encoded)
    
    Returns:
        Remaining seconds in current 30-second window
    """
    try:
        totp = pyotp.TOTP(secret)
        return totp.interval - (int(totp.time) % totp.interval)
    except Exception:
        return 0
