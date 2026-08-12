"""
Security headers middleware.

Adds security-related HTTP headers to all responses to protect against
common web vulnerabilities.
"""

from fastapi import Request, Response
from fastapi.middleware import Middleware
from fastapi.middleware.base import BaseHTTPMiddleware
from typing import Callable

from .config import is_production


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add security headers to all responses.
    
    Headers added:
    - X-Content-Type-Options: nosniff
    - X-Frame-Options: DENY
    - Referrer-Policy: strict-origin-when-cross-origin
    - Permissions-Policy: Restricts browser features
    - Content-Security-Policy: Restricts resource loading
    - Strict-Transport-Security: HSTS (production only)
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and add security headers to response."""
        response = await call_next(request)
        
        # X-Content-Type-Options: Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        
        # X-Frame-Options: Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"
        
        # Referrer-Policy: Control referrer information
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Permissions-Policy: Restrict browser features
        response.headers["Permissions-Policy"] = (
            "geolocation=(), "
            "microphone=(), "
            "camera=(), "
            "payment=(), "
            "usb=(), "
            "magnetometer=(), "
            "gyroscope=()"
        )
        
        # Content-Security-Policy: Restrict resource loading
        # For API endpoints, use a basic policy
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; "
            "script-src 'self'; "
            "connect-src 'self'; "
            "img-src 'self' data: https:; "
            "style-src 'self' 'unsafe-inline'; "
            "font-src 'self';"
        )
        
        # Strict-Transport-Security: HSTS (production only)
        if is_production():
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )
        
        # X-XSS-Protection: Legacy XSS protection (deprecated but still useful)
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        return response


def get_security_headers_middleware() -> Middleware:
    """
    Create security headers middleware instance.
    
    Returns:
        FastAPI middleware instance
    """
    return Middleware(SecurityHeadersMiddleware)
