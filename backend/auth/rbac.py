"""
Role-Based Access Control (RBAC) helpers.

Defines role hierarchy and provides authorization helpers for checking
user roles and business access permissions.
"""

from enum import Enum
from typing import Optional, List
from fastapi import HTTPException


class Role(str, Enum):
    """User roles in the system."""
    SUPER_ADMIN = "super_admin"
    BUSINESS_ADMIN = "business_admin"
    STAFF = "staff"
    DELIVERY_AGENT = "delivery_agent"
    CUSTOMER = "customer"


# Role hierarchy (higher index = more privilege)
ROLE_HIERARCHY = {
    Role.CUSTOMER: 0,
    Role.DELIVERY_AGENT: 1,
    Role.STAFF: 2,
    Role.BUSINESS_ADMIN: 3,
    Role.SUPER_ADMIN: 4,
}

# Roles that require MFA when enforced
PRIVILEGED_ROLES = {Role.SUPER_ADMIN, Role.BUSINESS_ADMIN}


def require_roles(allowed_roles: List[str]):
    """
    FastAPI dependency to check if user has required role.
    
    Args:
        allowed_roles: List of role strings that are permitted
    
    Returns:
        Dependency function that raises 403 if user lacks required role
    """
    async def role_checker(current_user: dict) -> dict:
        user_role = current_user.get("role")
        
        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=f"Access forbidden. Required role: one of {allowed_roles}"
            )
        
        return current_user
    
    return role_checker


def check_business_access(user: dict, business_id: str) -> bool:
    """
    Check if user has access to a specific business.
    
    Super admins have access to all businesses.
    Other users must have the business_id in their business_access array.
    
    Args:
        user: User document from database
        business_id: Business ID to check access for
    
    Returns:
        True if user has access, False otherwise
    """
    # Super admin has access to all businesses
    if user.get("role") == Role.SUPER_ADMIN:
        return True
    
    # Check business_access array
    business_access_list = user.get("business_access", [])
    if not isinstance(business_access_list, list):
        return False
    
    for access in business_access_list:
        if isinstance(access, dict):
            if access.get("business_id") == business_id:
                return True
        elif isinstance(access, str):
            if access == business_id:
                return True
    
    return False


def require_business_access(business_id: str):
    """
    FastAPI dependency to check if user has access to specific business.
    
    Args:
        business_id: Business ID to check access for
    
    Returns:
        Dependency function that raises 403 if user lacks business access
    """
    async def business_checker(current_user: dict) -> dict:
        if not check_business_access(current_user, business_id):
            raise HTTPException(
                status_code=403,
                detail=f"Access forbidden. User does not have access to business {business_id}"
            )
        
        return current_user
    
    return business_checker


def is_privileged_role(role: str) -> bool:
    """Check if role is considered privileged (requires MFA when enforced)."""
    return role in {r.value for r in PRIVILEGED_ROLES}


def get_role_level(role: str) -> int:
    """Get privilege level for a role (higher = more privilege)."""
    try:
        role_enum = Role(role)
        return ROLE_HIERARCHY.get(role_enum, 0)
    except ValueError:
        return 0


def has_higher_or_equal_privilege(user_role: str, required_role: str) -> bool:
    """
    Check if user has equal or higher privilege than required role.
    
    Args:
        user_role: User's current role
        required_role: Minimum required role
    
    Returns:
        True if user has sufficient privilege
    """
    return get_role_level(user_role) >= get_role_level(required_role)
