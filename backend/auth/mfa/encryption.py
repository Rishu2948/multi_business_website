"""
MFA Secret Encryption Module

Handles encryption and decryption of MFA secrets using Fernet symmetric encryption.
Uses AES-256-GCM for secure storage of TOTP secrets in the database.
"""

from cryptography.fernet import Fernet, InvalidToken
from backend.auth.config import get_mfa_encryption_key
from typing import Optional


def encrypt_mfa_secret(secret: str) -> str:
    """
    Encrypt MFA secret for secure storage in database.
    
    Args:
        secret: Plain text TOTP secret
    
    Returns:
        Base64-encoded encrypted secret
    
    Raises:
        ValueError: If MFA_ENCRYPTION_KEY is not configured
    """
    key = get_mfa_encryption_key()
    if not key:
        raise ValueError("MFA_ENCRYPTION_KEY is required for MFA encryption")
    
    fernet = Fernet(key.encode())
    encrypted = fernet.encrypt(secret.encode())
    return encrypted.decode()


def decrypt_mfa_secret(encrypted: str) -> str:
    """
    Decrypt MFA secret from database for validation.
    
    Args:
        encrypted: Base64-encoded encrypted secret
    
    Returns:
        Plain text TOTP secret
    
    Raises:
        ValueError: If decryption fails or key is invalid
    """
    key = get_mfa_encryption_key()
    if not key:
        raise ValueError("MFA_ENCRYPTION_KEY is required for MFA decryption")
    
    try:
        fernet = Fernet(key.encode())
        decrypted = fernet.decrypt(encrypted.encode())
        return decrypted.decode()
    except InvalidToken as e:
        raise ValueError(f"Failed to decrypt MFA secret: {e}")


def validate_encryption_key(key: str) -> bool:
    """
    Validate that the encryption key is properly formatted.
    
    Args:
        key: Encryption key string
    
    Returns:
        True if key is valid, False otherwise
    """
    try:
        Fernet(key.encode())
        return True
    except Exception:
        return False


def generate_encryption_key() -> str:
    """
    Generate a new Fernet-compatible encryption key.
    
    This should be used only during initial setup or key rotation.
    The generated key must be stored securely in environment variables.
    
    Returns:
        Base64-encoded encryption key (44 characters)
    """
    return Fernet.generate_key().decode()
