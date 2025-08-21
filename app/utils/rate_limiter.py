import redis
import time
import hashlib
import logging
from fastapi import WebSocket
from typing import Optional
from app.config import settings

logger = logging.getLogger(__name__)

# Redis client with connection pooling
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
    logger.error(f"Failed to connect to Redis at {settings.redis_url}: {e}")
    raise


class GlobalRateLimiter:
    """Global rate limiter to protect system resources and costs."""
    
    def __init__(self, redis_client: redis.Redis, max_requests: int = 50, window_seconds: int = 60):
        self.redis = redis_client
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        
        # Atomic Lua script for global rate limiting
        self.global_rate_limit_script = self.redis.register_script("""
            local key = KEYS[1]
            local now = tonumber(ARGV[1])
            local window_start = tonumber(ARGV[2])
            local max_requests = tonumber(ARGV[3])
            local window_seconds = tonumber(ARGV[4])
            
            -- remove expired entries
            redis.call('ZREMRANGEBYSCORE', key, 0, window_start)
            
            -- get current count
            local current_count = redis.call('ZCARD', key)
            
            -- check if global rate limit is exceeded
            if current_count >= max_requests then
                return 0
            end
            
            -- add the current request and set expiration
            redis.call('ZADD', key, now, tostring(now))
            redis.call('EXPIRE', key, window_seconds)
            
            return 1
        """)
    
    def is_allowed(self) -> bool:
        """Check if the global rate limit allows this request."""
        now = time.time()
        window_start = now - self.window_seconds
        key = "rate_limit:global"
        
        try:
            # Execute atomic Lua script
            result = self.global_rate_limit_script(
                keys=[key],
                args=[now, window_start, self.max_requests, self.window_seconds]
            )
            
            if result == 0:
                logger.warning(f"Global rate limit exceeded: {self.max_requests} requests per {self.window_seconds}s")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Redis error in global rate limiting: {e}")
            # Fail closed for better security - deny request if Redis is down
            logger.warning("Global rate limiting unavailable, denying request for safety")
            return False


class IPRateLimiter:
    def __init__(self, redis_client: redis.Redis, max_requests: int = 5, window_seconds: int = 60, global_limiter: Optional[GlobalRateLimiter] = None):
        self.redis = redis_client
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.global_limiter = global_limiter
        
        # Atomic Lua script for race-condition-free rate limiting
        self.rate_limit_script = self.redis.register_script("""
            local key = KEYS[1]
            local now = tonumber(ARGV[1])
            local window_start = tonumber(ARGV[2])
            local max_requests = tonumber(ARGV[3])
            local window_seconds = tonumber(ARGV[4])
            
            -- remove expired entries
            redis.call('ZREMRANGEBYSCORE', key, 0, window_start)
            
            -- get current count
            local current_count = redis.call('ZCARD', key)
            
            -- check if rate limit is exceeded
            if current_count >= max_requests then
                return 0
            end
            
            -- add the current request and set expiration
            redis.call('ZADD', key, now, tostring(now))
            redis.call('EXPIRE', key, window_seconds)
            
            return 1
        """)
    
    def get_ip_identifier(self, websocket: WebSocket) -> str:
        """Get IP-based identifier for rate limiting"""
        # Get real IP, handling proxies and load balancers
        real_ip = (
            websocket.headers.get("x-forwarded-for", "").split(",")[0].strip() or
            websocket.headers.get("x-real-ip", "") or
            websocket.headers.get("cf-connecting-ip", "") or  # Cloudflare
            websocket.headers.get("x-original-forwarded-for", "") or  # Additional proxy header
            (websocket.client.host if websocket.client else "unknown")
        )
        
        # Normalize IP address (handle IPv4 and IPv6)
        normalized_ip = real_ip[:45] if real_ip else "unknown"
        
        logger.info(f"Rate limiting based on IP: {normalized_ip[:8]}...")
        
        # Create secure IP-only hash
        return hashlib.sha256(normalized_ip.encode()).hexdigest()[:32]
    
    def is_allowed(self, websocket: WebSocket) -> bool:
        """Check if the request is allowed (checks global limit first, then per-IP limit)"""
        
        # Check global rate limit first (most restrictive)
        if self.global_limiter and not self.global_limiter.is_allowed():
            logger.warning("Request denied due to global rate limit")
            return False
        
        # Check per-IP rate limit
        identifier = self.get_ip_identifier(websocket)
        now = time.time()
        window_start = now - self.window_seconds
        key = f"rate_limit:ip:{identifier}"
        
        try:
            # execute atomic Lua script
            result = self.rate_limit_script(
                keys=[key],
                args=[now, window_start, self.max_requests, self.window_seconds]
            )
            
            if result == 0:
                logger.warning(f"Per-IP rate limit exceeded for {identifier[:8]}...")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Redis error in rate limiting: {e}")
            # Fail closed for better security - deny request if Redis is down
            logger.warning("Rate limiting unavailable, denying request for safety")
            return False


