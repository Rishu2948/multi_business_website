"""
Device Trust Module

Handles device trust management to reduce MFA prompts for trusted devices.
Users can mark devices as "trusted" for a configurable time period.
"""

import secrets
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict


def generate_device_id() -> str:
    """
    Generate a unique device identifier.
    
    Returns:
        Random device ID (16 characters)
    """
    return secrets.token_urlsafe(12)


def create_trusted_device(
    user_id: str,
    user_agent: str,
    ip_address: str,
    trust_duration_days: int = 30
) -> Dict:
    """
    Create a trusted device record.
    
    Args:
        user_id: User ID
        user_agent: User agent string from browser
        ip_address: IP address of the device
        trust_duration_days: How long to trust this device (default: 30 days)
    
    Returns:
        Device trust record dictionary
    """
    now = datetime.now(timezone.utc)
    return {
        "device_id": generate_device_id(),
        "user_id": user_id,
        "user_agent": user_agent,
        "ip_address": ip_address,
        "trusted_at": now,
        "expires_at": now + timedelta(days=trust_duration_days)
    }


def is_device_trusted(device: Dict) -> bool:
    """
    Check if a device is currently trusted (not expired).
    
    Args:
        device: Device trust record
    
    Returns:
        True if device is trusted and not expired, False otherwise
    """
    if not device:
        return False
    
    now = datetime.now(timezone.utc)
    expires_at = device.get("expires_at")
    
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    
    return now < expires_at


def should_trust_device(
    user_id: str,
    user_agent: str,
    ip_address: str,
    trusted_devices: list
) -> Optional[Dict]:
    """
    Check if current device should be trusted based on existing records.
    
    Args:
        user_id: User ID
        user_agent: Current user agent
        ip_address: Current IP address
        trusted_devices: List of user's trusted device records
    
    Returns:
        Device record if trusted, None otherwise
    """
    for device in trusted_devices:
        if device.get("user_id") != user_id:
            continue
        
        # Check if device matches (by user agent and IP)
        # In production, you might use fingerprinting instead
        if (device.get("user_agent") == user_agent and 
            device.get("ip_address") == ip_address):
            
            if is_device_trusted(device):
                return device
    
    return None


def revoke_device_trust(device_id: str, trusted_devices: list) -> list:
    """
    Revoke trust for a specific device.
    
    Args:
        device_id: Device ID to revoke
        trusted_devices: List of trusted device records
    
    Returns:
        Updated list of trusted devices
    """
    return [device for device in trusted_devices if device.get("device_id") != device_id]


def revoke_all_device_trust(user_id: str, trusted_devices: list) -> list:
    """
    Revoke all trusted devices for a user.
    
    Args:
        user_id: User ID
        trusted_devices: List of trusted device records
    
    Returns:
        Empty list (all devices revoked)
    """
    return []


def cleanup_expired_devices(trusted_devices: list) -> list:
    """
    Remove expired device trust records.
    
    Args:
        trusted_devices: List of trusted device records
    
    Returns:
        List of active (non-expired) devices
    """
    return [device for device in trusted_devices if is_device_trusted(device)]


def add_trusted_device(
    user_id: str,
    user_agent: str,
    ip_address: str,
    trust_duration_days: int = 30
) -> Dict:
    """
    Create and add a trusted device record.
    
    Args:
        user_id: User ID
        user_agent: User agent string from browser
        ip_address: IP address of the device
        trust_duration_days: How long to trust this device (default: 30 days)
    
    Returns:
        Device trust record dictionary
    """
    return create_trusted_device(user_id, user_agent, ip_address, trust_duration_days)


def verify_trusted_device(
    user_id: str,
    user_agent: str,
    ip_address: str,
    trusted_devices: list
) -> Optional[Dict]:
    """
    Verify if current device is trusted (can skip MFA).
    
    Args:
        user_id: User ID
        user_agent: Current user agent
        ip_address: Current IP address
        trusted_devices: List of user's trusted device records
    
    Returns:
        Device record if trusted, None otherwise
    """
    return should_trust_device(user_id, user_agent, ip_address, trusted_devices)


def get_device_fingerprint(user_agent: str, ip_address: str) -> str:
    """
    Generate a device fingerprint for comparison.
    
    This is a simple implementation. In production, you might use
    more sophisticated fingerprinting (e.g., FingerprintJS).
    
    Args:
        user_agent: User agent string
        ip_address: IP address
    
    Returns:
        Device fingerprint string
    """
    fingerprint = f"{user_agent}:{ip_address}"
    return hashlib.sha256(fingerprint.encode()).hexdigest()
