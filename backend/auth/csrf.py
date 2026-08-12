"""
CSRF protection and Origin validation.

Provides Origin/Referer validation for cookie-authenticated requests
to prevent CSRF attacks on state-changing operations.
"""

from typing import Optional
from fastapi import Request, HTTPException
from urllib.parse import urlparse

from .config import is_production


def validate_origin(request: Request, allowed_origins: list) -> None:
    """
    Validate Origin or Referer header for state-changing requests.
    
    This prevents CSRF attacks by ensuring the request comes from an
    allowed origin when using cookie authentication.
    
    Args:
        request: FastAPI request
        allowed_origins: List of allowed origin URLs
    
    Raises:
        HTTPException: 403 if Origin/Referer is not allowed
    """
    # Skip validation for safe methods
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    
    # Get Origin header (preferred) or Referer fallback
    origin = request.headers.get("origin")
    if not origin:
        referer = request.headers.get("referer")
        if referer:
            # Extract origin from referer
            parsed = urlparse(referer)
            origin = f"{parsed.scheme}://{parsed.netloc}"
    
    # If no Origin/Referer, block in production
    if not origin:
        if is_production():
            raise HTTPException(
                status_code=403,
                detail="Origin/Referer header required for state-changing requests"
            )
        return
    
    # Check if origin is allowed
    if not _is_origin_allowed(origin, allowed_origins):
        raise HTTPException(
            status_code=403,
            detail=f"Origin '{origin}' not allowed"
        )


def _is_origin_allowed(origin: str, allowed_origins: list) -> bool:
    """
    Check if origin is in allowed list.
    
    Supports exact match and wildcard subdomains.
    
    Args:
        origin: Origin URL to check
        allowed_origins: List of allowed origins
    
    Returns:
        True if allowed, False otherwise
    """
    origin_parsed = urlparse(origin)
    origin_base = f"{origin_parsed.scheme}://{origin_parsed.netloc}"
    
    for allowed in allowed_origins:
        if allowed == "*":
            return True
        
        if allowed == origin_base:
            return True
        
        # Support wildcard subdomains (e.g., *.example.com)
        if allowed.startswith("*."):
            domain = allowed[2:]
            if origin_parsed.netloc.endswith(domain):
                return True
    
    return False


class CSRFProtection:
    """
    CSRF protection middleware for FastAPI.
    
    Validates Origin/Referer headers on unsafe methods when
    cookie authentication is used.
    """
    
    def __init__(self, allowed_origins: list):
        self.allowed_origins = allowed_origins
    
    async def __call__(self, request: Request, call_next):
        """Process request and validate Origin/Referer."""
        # Validate Origin for state-changing requests
        validate_origin(request, self.allowed_origins)
        
        # Continue processing
        response = await call_next(request)
        
        return response


def get_allowed_origins() -> list:
    """
    Get allowed origins from environment.
    
    Reads CORS_ORIGINS environment variable and returns as list.
    
    Returns:
        List of allowed origin URLs
    """
    import os
    
    raw = os.environ.get("CORS_ORIGINS", "http://localhost:3000")
    origins = [o.strip() for o in raw.split(",") if o.strip()]
    
    # Security: Never allow wildcard in production
    if is_production() and "*" in origins:
        return ["http://localhost:3000"]  # Fallback to safe default
    
    return origins
