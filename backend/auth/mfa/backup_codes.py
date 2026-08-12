"""
Backup Codes Module

Handles generation, hashing, and validation of backup codes for account recovery.
Backup codes are one-time use and serve as a recovery mechanism if user loses authenticator device.
"""

import secrets
import hashlib
from typing import List


def generate_backup_codes(count: int = 10) -> List[str]:
    """
    Generate random backup codes for account recovery.
    
    Args:
        count: Number of backup codes to generate (default: 10)
    
    Returns:
        List of 8-character alphanumeric backup codes (uppercase)
    """
    codes = []
    for _ in range(count):
        # Generate 8-character alphanumeric code
        code = secrets.token_urlsafe(6).upper()[:8]
        # Ensure it's exactly 8 characters
        while len(code) < 8:
            code += secrets.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')
        codes.append(code[:8])
    return codes


def hash_backup_code(code: str) -> str:
    """
    Hash backup code for secure storage in database.
    
    Args:
        code: Plain text backup code
    
    Returns:
        SHA-256 hash of the code (uppercase for case-insensitivity)
    """
    return hashlib.sha256(code.upper().encode()).hexdigest()


def verify_backup_code(code: str, hashed: str) -> bool:
    """
    Verify backup code against stored hash.
    
    Args:
        code: Plain text backup code provided by user
        hashed: Stored hash of the backup code
    
    Returns:
        True if code matches hash, False otherwise
    """
    return hash_backup_code(code) == hashed


def backup_code_format_valid(code: str) -> bool:
    """
    Validate backup code format.
    
    Args:
        code: Backup code to validate
    
    Returns:
        True if code is valid format, False otherwise
    """
    # Must be 8 characters, alphanumeric, uppercase
    if len(code) != 8:
        return False
    if not code.isalnum():
        return False
    if not code.isupper():
        return False
    return True


def mark_backup_code_used(used_codes: List[str], code: str) -> List[str]:
    """
    Mark a backup code as used by adding it to the used codes list.
    
    Args:
        used_codes: List of already used backup code hashes
        code: Backup code that was just used
    
    Returns:
        Updated list of used backup code hashes
    """
    hashed = hash_backup_code(code)
    if hashed not in used_codes:
        used_codes.append(hashed)
    return used_codes


def is_backup_code_available(backup_codes: List[str], used_codes: List[str]) -> bool:
    """
    Check if user has any unused backup codes remaining.
    
    Args:
        backup_codes: List of all backup code hashes
        used_codes: List of used backup code hashes
    
    Returns:
        True if at least one backup code is available, False otherwise
    """
    available = [code for code in backup_codes if code not in used_codes]
    return len(available) > 0


def get_remaining_backup_codes(backup_codes: List[str], used_codes: List[str]) -> int:
    """
    Get count of remaining unused backup codes.
    
    Args:
        backup_codes: List of all backup code hashes
        used_codes: List of used backup code hashes
    
    Returns:
        Number of unused backup codes remaining
    """
    available = [code for code in backup_codes if code not in used_codes]
    return len(available)
