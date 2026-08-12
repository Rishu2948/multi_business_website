"""
Rate limiting middleware and utilities.

Provides per-IP and per-user rate limiting using Redis when available,
with in-memory fallback for single-instance deployments.
"""

import time
import asyncio
from typing import Optional, Dict, Any
from collections import defaultdict
from fastapi import Request, HTTPException

from .config import get_redis_url, get_auth_rate_limit


class RateLimiter:
    """Rate limiter with Redis backend and in-memory fallback."""
    
    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or get_redis_url()
        self.redis_client = None
        self.in_memory_store: Dict[str, list] = defaultdict(list)
        self._init_redis()
    
    def _init_redis(self):
        """Initialize Redis client if URL is provided."""
        if self.redis_url:
            try:
                import redis.asyncio as redis
                self.redis_client = redis.from_url(self.redis_url, decode_responses=True)
            except ImportError:
                # redis package not available, fall back to in-memory
                self.redis_client = None
    
    async def is_allowed(
        self,
        key: str,
        limit: int,
        window_seconds: int = 60
    ) -> bool:
        """
        Check if request is allowed under rate limit.
        
        Args:
            key: Unique key for rate limit (e.g., "ip:1.2.3.4" or "user:123")
            limit: Maximum requests in window
            window_seconds: Time window in seconds
        
        Returns:
            True if allowed, False if rate limit exceeded
        """
        if self.redis_client:
            return await self._is_allowed_redis(key, limit, window_seconds)
        else:
            return self._is_allowed_memory(key, limit, window_seconds)
    
    async def _is_allowed_redis(
        self,
        key: str,
        limit: int,
        window_seconds: int
    ) -> bool:
        """Check rate limit using Redis with sliding window."""
        try:
            current_time = time.time()
            window_start = current_time - window_seconds
            
            # Use Redis pipeline for atomic operations
            pipe = self.redis_client.pipeline()
            
            # Remove old entries
            pipe.zremrangebyscore(key, 0, window_start)
            
            # Count current entries
            pipe.zcard(key)
            
            # Add current request
            pipe.zadd(key, {str(current_time): current_time})
            
            # Set expiry
            pipe.expire(key, window_seconds)
            
            results = await pipe.execute()
            current_count = results[1]
            
            return current_count < limit
        
        except Exception:
            # Fallback to in-memory on Redis error
            return self._is_allowed_memory(key, limit, window_seconds)
    
    def _is_allowed_memory(
        self,
        key: str,
        limit: int,
        window_seconds: int
    ) -> bool:
        """Check rate limit using in-memory store."""
        current_time = time.time()
        window_start = current_time - window_seconds
        
        # Clean old entries
        self.in_memory_store[key] = [
            ts for ts in self.in_memory_store[key]
            if ts > window_start
        ]
        
        # Check if under limit
        if len(self.in_memory_store[key]) >= limit:
            return False
        
        # Add current request
        self.in_memory_store[key].append(current_time)
        return True
    
    async def get_remaining(
        self,
        key: str,
        limit: int,
        window_seconds: int = 60
    ) -> int:
        """
        Get remaining requests before rate limit.
        
        Args:
            key: Unique key for rate limit
            limit: Maximum requests in window
            window_seconds: Time window in seconds
        
        Returns:
            Number of remaining requests
        """
        if self.redis_client:
            try:
                current_time = time.time()
                window_start = current_time - window_seconds
                
                # Remove old entries and count
                pipe = self.redis_client.pipeline()
                pipe.zremrangebyscore(key, 0, window_start)
                pipe.zcard(key)
                results = await pipe.execute()
                
                current_count = results[1]
                return max(0, limit - current_count)
            except Exception:
                pass
        
        # Fallback to in-memory
        current_time = time.time()
        window_start = current_time - window_seconds
        self.in_memory_store[key] = [
            ts for ts in self.in_memory_store[key]
            if ts > window_start
        ]
        return max(0, limit - len(self.in_memory_store[key]))
    
    async def reset(self, key: str) -> None:
        """Reset rate limit for a key."""
        if self.redis_client:
            try:
                await self.redis_client.delete(key)
            except Exception:
                pass
        
        if key in self.in_memory_store:
            del self.in_memory_store[key]


async def check_rate_limit(
    request: Request,
    limiter: RateLimiter,
    limit: int,
    window_seconds: int = 60,
    key_prefix: str = "rate_limit"
) -> None:
    """
    FastAPI dependency to check rate limit.
    
    Args:
        request: FastAPI request
        limiter: RateLimiter instance
        limit: Maximum requests
        window_seconds: Time window
        key_prefix: Prefix for rate limit key
    
    Raises:
        HTTPException: 429 if rate limit exceeded
    """
    # Get client IP
    ip_address = request.client.host if request.client else "unknown"
    
    # Create rate limit key
    key = f"{key_prefix}:{ip_address}"
    
    # Check if allowed
    allowed = await limiter.is_allowed(key, limit, window_seconds)
    
    if not allowed:
        # Get remaining for Retry-After header
        remaining = await limiter.get_remaining(key, limit, window_seconds)
        retry_after = window_seconds  # Simplified, could calculate exact
        
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={
                "Retry-After": str(retry_after),
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": str(remaining),
            }
        )
