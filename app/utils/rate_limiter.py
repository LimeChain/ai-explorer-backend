import redis
import time
import hashlib
import json
import logging
from functools import wraps
from fastapi import WebSocket
from typing import Callable, Optional
from app.exceptions import RateLimitError
from app.config import settings

logger = logging.getLogger(__name__)

# Global Redis client with connection pooling
redis_client = redis.Redis.from_url(
    settings.redis_url,
    max_connections=settings.redis_max_connections,
    retry_on_timeout=settings.redis_retry_on_timeout,
    socket_timeout=settings.redis_socket_timeout
)

try:
    redis_client.ping()
    logger.info("Redis connection established successfully")
except redis.ConnectionError as e:
    logger.error(f"Failed to connect to Redis: {e}")
    raise


class FingerprintRateLimiter:
    def __init__(self, redis_client: redis.Redis, max_requests: int = 5, window_seconds: int = 60):
        self.redis = redis_client
        self.max_requests = max_requests
        self.window_seconds = window_seconds
    
    def create_fingerprint(self, websocket: WebSocket) -> str:
        """Create a unique fingerprint from available WebSocket data"""
        def get_header(key: str, max_length: int = 200) -> str:
            """Get header value with length limit and normalization"""
            value = websocket.headers.get(key, "")
            return value[:max_length].strip().lower()
        
        # Get real IP, handling proxies
        real_ip = (
            websocket.headers.get("x-forwarded-for", "").split(",")[0].strip() or
            websocket.headers.get("x-real-ip", "") or
            (websocket.client.host if websocket.client else "unknown")
        )
        
        fingerprint_data = {
            "ip": real_ip[:45],  # Handles both IPv4 and IPv6
            "user_agent": get_header("user-agent", 500),
            "accept_language": get_header("accept-language", 100),
            "accept_encoding": get_header("accept-encoding", 100),
            "sec_websocket_protocol": get_header("sec-websocket-protocol", 100),
            "sec_websocket_extensions": get_header("sec-websocket-extensions", 200),
            "origin": get_header("origin", 200),  # More unique than other headers
        }
        
        # Remove empty values to improve uniqueness
        fingerprint_data = {k: v for k, v in fingerprint_data.items() if v}
        
        # Create a hash of the fingerprint data using SHA-256
        fingerprint_str = json.dumps(fingerprint_data, sort_keys=True)
        return hashlib.sha256(fingerprint_str.encode()).hexdigest()[:16]
    
    def is_allowed(self, websocket: WebSocket) -> bool:
        """Check if the request is allowed based on fingerprint"""
        identifier = self.create_fingerprint(websocket)
        now = time.time()
        window_start = now - self.window_seconds
        key = f"rate_limit:fingerprint:{identifier}"
        
        try:
            # Use pipeline for better performance
            pipe = self.redis.pipeline()
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zcard(key)
            pipe.zadd(key, {str(now): now})
            pipe.expire(key, self.window_seconds)
            
            results = pipe.execute()
            current_requests = results[1]
            
            if current_requests >= self.max_requests:
                # Remove the request we just added since it's not allowed
                self.redis.zrem(key, str(now))
                logger.warning(f"Rate limit exceeded for {identifier[:8]}...")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Redis error in rate limiting: {e}")
            # Fail closed for better security - deny request if Redis is down
            logger.warning("Rate limiting unavailable, denying request for safety")
            return False


def rate_limit_websocket(max_requests: Optional[int] = None, window_seconds: Optional[int] = None):
    """Decorator to rate limit WebSocket connections"""
    # Use config defaults if not specified
    _max_requests = max_requests or settings.rate_limit_max_requests
    _window_seconds = window_seconds or settings.rate_limit_window_seconds
    
    # Create rate limiter for this specific endpoint
    rate_limiter = FingerprintRateLimiter(
        redis_client, 
        max_requests=_max_requests, 
        window_seconds=_window_seconds
    )
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(websocket: WebSocket, *args, **kwargs):
            
            # Check rate limit before processing
            if not rate_limiter.is_allowed(websocket):
                error_msg = f"Rate limit exceeded. Max {_max_requests} requests per {_window_seconds} seconds."
                raise RateLimitError(error_msg)
            
            # Call the original function
            return await func(websocket, *args, **kwargs)
        
        return wrapper
    return decorator