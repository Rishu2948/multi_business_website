"""
Multi-Factor Authentication (MFA) using TOTP.

Provides TOTP secret generation, verification, and encryption for
privileged users (super_admin, business_admin).
"""

import pyotp
import base64
import os
from typing import Optional, Tuple
from cryptography.fernet import Fernet
from fastapi import HTTPException

from .config import get_mfa_encryption_key, enforce_mfa_for_admins
from .rbac import is_privileged_role


class MFAManager:
    """Manages MFA enrollment and verification."""
    
    def __init__(self):
        self.encryption_key = get_mfa_encryption_key()
        self.cipher = None
        
        if self.encryption_key:
            # Ensure key is proper length for Fernet
            if len(self.encryption_key) < 32:
                # Pad or hash to get proper length
                import hashlib
                self.encryption_key = hashlib.sha256(
                    self.encryption_key.encode()
                ).digest()
            
            # Base64 encode for Fernet
            if len(self.encryption_key) != 32:
                # Generate a new key if still not right length
                self.encryption_key = Fernet.generate_key()
            
            self.cipher = Fernet(self.encryption_key)
    
    def generate_secret(self) -> str:
        """
        Generate a new TOTP secret.
        
        Returns:
            Base32-encoded TOTP secret
        """
        return pyotp.random_base32()
    
    def encrypt_secret(self, secret: str) -> str:
        """
        Encrypt TOTP secret for storage.
        
        Args:
            secret: TOTP secret to encrypt
        
        Returns:
            Encrypted secret (base64)
        
        Raises:
            ValueError: If encryption key not configured
        """
        if not self.cipher:
            raise ValueError("MFA encryption key not configured")
        
        encrypted = self.cipher.encrypt(secret.encode())
        return base64.b64encode(encrypted).decode()
    
    def decrypt_secret(self, encrypted_secret: str) -> str:
        """
        Decrypt TOTP secret from storage.
        
        Args:
            encrypted_secret: Encrypted secret (base64)
        
        Returns:
            Decrypted TOTP secret
        
        Raises:
            ValueError: If decryption fails
        """
        if not self.cipher:
            raise ValueError("MFA encryption key not configured")
        
        try:
            encrypted = base64.b64decode(encrypted_secret.encode())
            decrypted = self.cipher.decrypt(encrypted)
            return decrypted.decode()
        except Exception as e:
            raise ValueError(f"Failed to decrypt MFA secret: {str(e)}")
    
    def verify_token(self, secret: str, token: str) -> bool:
        """
        Verify TOTP token against secret.
        
        Args:
            secret: TOTP secret (decrypted)
            token: 6-digit TOTP token from user
        
        Returns:
            True if token is valid, False otherwise
        """
        totp = pyotp.TOTP(secret)
        return totp.verify(token, valid_window=1)  # Allow 1 step variance
    
    def generate_provisioning_uri(
        self,
        secret: str,
        user_email: str,
        issuer_name: str = "Bakery Platform"
    ) -> str:
        """
        Generate QR code provisioning URI for authenticator apps.
        
        Args:
            secret: TOTP secret
            user_email: User email for label
            issuer_name: Issuer name for authenticator app
        
        Returns:
            URI for QR code generation
        """
        totp = pyotp.TOTP(secret)
        return totp.provisioning_uri(
            name=user_email,
            issuer_name=issuer_name
        )


def generate_mfa_secret() -> str:
    """Generate a new TOTP secret."""
    manager = MFAManager()
    return manager.generate_secret()


def encrypt_mfa_secret(secret: str) -> str:
    """Encrypt TOTP secret for storage."""
    manager = MFAManager()
    return manager.encrypt_secret(secret)


def decrypt_mfa_secret(encrypted_secret: str) -> str:
    """Decrypt TOTP secret from storage."""
    manager = MFAManager()
    return manager.decrypt_secret(encrypted_secret)


def verify_mfa_token(secret: str, token: str) -> bool:
    """Verify TOTP token against secret."""
    manager = MFAManager()
    return manager.verify_token(secret, token)


def should_enforce_mfa(user_role: str) -> bool:
    """
    Check if MFA should be enforced for a user.
    
    Args:
        user_role: User's role
    
    Returns:
        True if MFA should be enforced
    """
    return enforce_mfa_for_admins() and is_privileged_role(user_role)


def is_user_mfa_enrolled(user: dict) -> bool:
    """
    Check if user has MFA enrolled.
    
    Args:
        user: User document from database
    
    Returns:
        True if user has MFA secret configured
    """
    return bool(user.get("mfa_secret"))
