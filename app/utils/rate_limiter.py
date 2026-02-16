"""
Async rate limiting using Redis sorted sets with Lua scripts for atomicity.

All methods are async. Redis client is injected (no module-level globals).
"""
import time
import hashlib

import redis.asyncio as aioredis
from fastapi import WebSocket
from typing import Optional

from app.utils.logging_config import get_service_logger

logger = get_service_logger("rate_limiter")

# Lua script shared by both global and per-IP limiters.
# Atomic: clean expired → check count → add if allowed → set TTL.
_RATE_LIMIT_LUA = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window_start = tonumber(ARGV[2])
local max_requests = tonumber(ARGV[3])
local window_seconds = tonumber(ARGV[4])

redis.call('ZREMRANGEBYSCORE', key, 0, window_start)

local current_count = redis.call('ZCARD', key)

if current_count >= max_requests then
    return 0
end

redis.call('ZADD', key, now, tostring(now))
redis.call('EXPIRE', key, window_seconds)

return 1
"""


class GlobalRateLimiter:
    """Global rate limiter to protect system resources and costs."""

    def __init__(
        self,
        redis_client: aioredis.Redis,
        max_requests: int = 50,
        window_seconds: int = 60,
    ):
        self.redis = redis_client
        self.max_requests = max_requests
        self.window_seconds = window_seconds

    async def is_allowed(self) -> bool:
        """Check if the global rate limit allows this request."""
        now = time.time()
        window_start = now - self.window_seconds
        key = "rate:global"

        try:
            result = await self.redis.eval(
                _RATE_LIMIT_LUA,
                1,
                key,
                str(now),
                str(window_start),
                str(self.max_requests),
                str(self.window_seconds),
            )

            if result == 0:
                logger.warning(
                    "Global rate limit exceeded: %s requests per %ss",
                    self.max_requests,
                    self.window_seconds,
                )
                return False

            return True

        except Exception as e:
            logger.error("Redis error in global rate limiting", exc_info=True, extra={
                "error_type": type(e).__name__,
                "error_message": str(e),
                "operation": "global_rate_limit_check",
                "max_requests": self.max_requests,
                "window_seconds": self.window_seconds,
                "redis_key": key,
            })
            # Fail closed — deny request if Redis is down
            return False


class IPRateLimiter:
    """Per-IP rate limiter with optional global limiter check."""

    def __init__(
        self,
        redis_client: aioredis.Redis,
        max_requests: int = 5,
        window_seconds: int = 60,
        global_limiter: Optional[GlobalRateLimiter] = None,
    ):
        self.redis = redis_client
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.global_limiter = global_limiter

    def get_ip_identifier(self, websocket: WebSocket) -> str:
        """Get IP-based identifier for rate limiting."""
        real_ip = (
            websocket.headers.get("x-forwarded-for", "").split(",")[0].strip()
            or websocket.headers.get("x-real-ip", "")
            or websocket.headers.get("cf-connecting-ip", "")
            or websocket.headers.get("x-original-forwarded-for", "")
            or (websocket.client.host if websocket.client else "unknown")
        )

        normalized_ip = real_ip[:45] if real_ip else "unknown"
        logger.info("Rate limiting based on IP: %s", normalized_ip)

        return hashlib.sha256(normalized_ip.encode()).hexdigest()[:16]

    async def is_allowed(self, websocket: WebSocket) -> bool:
        """Check if the request is allowed (global first, then per-IP)."""
        # Check global rate limit first
        if self.global_limiter and not await self.global_limiter.is_allowed():
            logger.warning("Request denied due to global rate limit")
            return False

        identifier = self.get_ip_identifier(websocket)
        now = time.time()
        window_start = now - self.window_seconds
        key = f"rate:ip:{identifier}"

        try:
            result = await self.redis.eval(
                _RATE_LIMIT_LUA,
                1,
                key,
                str(now),
                str(window_start),
                str(self.max_requests),
                str(self.window_seconds),
            )

            if result == 0:
                logger.warning("Per-IP rate limit exceeded for %s...", identifier[:8])
                return False

            return True

        except Exception as e:
            logger.error("Redis error in IP rate limiting", exc_info=True, extra={
                "error_type": type(e).__name__,
                "error_message": str(e),
                "operation": "ip_rate_limit_check",
                "ip_identifier": identifier[:8] + "...",
                "max_requests": self.max_requests,
                "window_seconds": self.window_seconds,
                "redis_key": key,
            })
            # Fail closed — deny request if Redis is down
            return False
