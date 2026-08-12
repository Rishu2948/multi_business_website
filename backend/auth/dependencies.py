"""
FastAPI dependencies for authentication and authorization.

Provides the canonical auth entry points for route handlers:
- get_current_user: Require authenticated user
- get_optional_user: Get user if authenticated, None otherwise
- require_roles: Require specific roles
- require_business_access: Require access to specific business
"""

from typing import Optional
from fastapi import HTTPException, Request, Depends

from .tokens import TokenManager
from .rbac import require_roles as rbac_require_roles, check_business_access, require_business_access as rbac_require_business_access
from .sessions import update_last_seen


async def extract_token(request: Request) -> Optional[str]:
    """
    Extract token from request, trying cookie first, then Authorization header.
    
    Order of precedence:
    1. HttpOnly cookie (refresh_token or access_token)
    2. Authorization: Bearer <token> header
    
    Args:
        request: FastAPI request
    
    Returns:
        Token string if found, None otherwise
    """
    # Try cookie first
    token = request.cookies.get("refresh_token") or request.cookies.get("access_token")
    
    # Fallback to Authorization header
    if not token:
        auth_header = request.headers.get("authorization")
        if auth_header:
            # Validate Bearer scheme
            if not auth_header.startswith("Bearer "):
                raise HTTPException(
                    status_code=401,
                    detail="Invalid authorization header format. Use 'Bearer <token>'"
                )
            token = auth_header[7:]  # Remove "Bearer " prefix
    
    return token


async def get_current_user(request: Request, db = Depends(lambda: None)) -> dict:
    """
    FastAPI dependency to get authenticated user.
    
    This is the canonical auth entry point for routes that require authentication.
    It validates tokens via Auth_Module and always enforces expiry.
    
    Args:
        request: FastAPI request
        db: MongoDB database instance (injected via app dependency)
    
    Returns:
        User document from database
    
    Raises:
        HTTPException: 401 if not authenticated or token invalid/expired
    """
    token = await extract_token(request)
    
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Try as JWT access token first
    try:
        token_manager = TokenManager(db)
        payload = token_manager.verify_access_token(token)
        
        # Load user from DB for authorization (not from JWT claims)
        user = await db.users.find_one(
            {"user_id": payload["sub"]},
            {"_id": 0}
        )
        
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        
        # Update last seen
        await update_last_seen(db, payload["sid"])
        
        return user
    
    except HTTPException:
        # If JWT fails, try legacy session if enabled
        from .tokens import validate_legacy_session
        user = await validate_legacy_session(db, token)
        
        if user:
            return user
        
        raise HTTPException(status_code=401, detail="Invalid or expired credentials")


async def get_optional_user(request: Request, db = Depends(lambda: None)) -> Optional[dict]:
    """
    FastAPI dependency to get user if authenticated, None otherwise.
    
    Useful for routes that work for both authenticated and anonymous users.
    
    Args:
        request: FastAPI request
        db: MongoDB database instance
    
    Returns:
        User document if authenticated, None otherwise
    """
    try:
        return await get_current_user(request, db)
    except HTTPException:
        return None


def require_roles(allowed_roles: list):
    """
    FastAPI dependency to require specific roles.
    
    Wraps the RBAC helper for use as a FastAPI dependency.
    
    Args:
        allowed_roles: List of role strings that are permitted
    
    Returns:
        Dependency function
    """
    return rbac_require_roles(allowed_roles)


def require_business_access(business_id: str):
    """
    FastAPI dependency to require access to specific business.
    
    Wraps the RBAC helper for use as a FastAPI dependency.
    
    Args:
        business_id: Business ID to check access for
    
    Returns:
        Dependency function
    """
    return rbac_require_business_access(business_id)
