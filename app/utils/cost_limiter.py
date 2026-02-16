"""
Async cost-based limiting system for tracking and limiting spending on LLM API calls.

Provides per-IP and global cost tracking with configurable time periods,
separate from request-based rate limiting. All methods are async.
Redis client is injected (no module-level globals).
"""
import hashlib

import redis.asyncio as aioredis
from fastapi import WebSocket

from app.config import settings
from app.utils.logging_config import get_service_logger

logger = get_service_logger("api")


def get_ip_identifier(websocket: WebSocket) -> str:
    """Get IP identifier for cost tracking.

    NOTE: This duplicates logic from rate_limiter.get_ip_identifier().
    Story 1-2 will extract a shared identity.py utility.
    """
    real_ip = (
        websocket.headers.get("x-forwarded-for", "").split(",")[0].strip()
        or websocket.headers.get("x-real-ip", "")
        or websocket.headers.get("cf-connecting-ip", "")
        or websocket.headers.get("x-original-forwarded-for", "")
        or (websocket.client.host if websocket.client else "unknown")
    )

    normalized_ip = real_ip[:45] if real_ip else "unknown"
    return hashlib.sha256(normalized_ip.encode()).hexdigest()[:16]


class IPCostLimiter:
    """Per-IP cost tracking with configurable time periods."""

    def __init__(self, redis_client: aioredis.Redis, max_cost: float = 1.0, period_seconds: int = 168):
        self.redis = redis_client
        self.max_cost = max_cost
        self.period_seconds = period_seconds

    def _get_ip_key(self, ip_identifier: str) -> str:
        return f"cost:ip:{ip_identifier}"

    async def is_within_limits(self, ip_identifier: str) -> bool:
        """Check if IP is within their cost limit for current period."""
        key = self._get_ip_key(ip_identifier)

        try:
            current_cost = float(await self.redis.get(key) or 0)
            return current_cost < self.max_cost
        except Exception as e:
            logger.error("Redis error checking IP cost limit", exc_info=True, extra={
                "error_type": type(e).__name__,
                "error_message": str(e),
                "operation": "ip_cost_limit_check",
                "ip_identifier": ip_identifier[:8] + "...",
                "max_cost": self.max_cost,
                "period_seconds": self.period_seconds,
                "redis_key": key,
            })
            # Fail open for cost limits — allow request if Redis fails
            return True

    async def record_cost(self, ip_identifier: str, actual_cost: float) -> None:
        """Record actual cost for IP with TTL management."""
        if actual_cost <= 0:
            return

        key = self._get_ip_key(ip_identifier)

        try:
            current_cost = await self.redis.get(key)

            if current_cost is None:
                await self.redis.set(key, actual_cost, ex=self.period_seconds)
                logger.debug("First cost record for IP %s...: $%.6f (TTL: %ss)", ip_identifier[:8], actual_cost, self.period_seconds)
            else:
                await self.redis.incrbyfloat(key, actual_cost)
                logger.debug("Added cost for IP %s...: $%.6f", ip_identifier[:8], actual_cost)

        except Exception as e:
            logger.error("Error recording IP cost", exc_info=True, extra={
                "error_type": type(e).__name__,
                "error_message": str(e),
                "operation": "ip_cost_record",
                "ip_identifier": ip_identifier[:8] + "...",
                "actual_cost": actual_cost,
                "redis_key": key,
            })

    async def get_current_usage(self, ip_identifier: str) -> float:
        """Get current cost usage for IP in current period."""
        key = self._get_ip_key(ip_identifier)
        try:
            return float(await self.redis.get(key) or 0)
        except Exception as e:
            logger.error("Error getting IP cost usage", exc_info=True, extra={
                "error_type": type(e).__name__,
                "error_message": str(e),
                "operation": "ip_cost_usage_get",
                "ip_identifier": ip_identifier[:8] + "...",
                "redis_key": key,
            })
            return 0.0


class GlobalCostLimiter:
    """Global cost tracking across all users with configurable time periods."""

    def __init__(self, redis_client: aioredis.Redis, max_cost: float = 10.0, period_seconds: int = 8760):
        self.redis = redis_client
        self.max_cost = max_cost
        self.period_seconds = period_seconds

    def _get_global_key(self) -> str:
        return "cost:global"

    async def is_within_limits(self) -> bool:
        """Check if global system is within cost limit for current period."""
        key = self._get_global_key()

        try:
            current_cost = float(await self.redis.get(key) or 0)
            return current_cost < self.max_cost
        except Exception as e:
            logger.error("Redis error checking global cost limit", exc_info=True, extra={
                "error_type": type(e).__name__,
                "error_message": str(e),
                "operation": "global_cost_limit_check",
                "max_cost": self.max_cost,
                "period_seconds": self.period_seconds,
                "redis_key": key,
            })
            # Fail open for cost limits
            return True

    async def record_cost(self, actual_cost: float) -> None:
        """Record actual cost globally with TTL management."""
        if actual_cost <= 0:
            return

        key = self._get_global_key()

        try:
            current_cost = await self.redis.get(key)

            if current_cost is None:
                await self.redis.set(key, actual_cost, ex=self.period_seconds)
                logger.debug("First global cost record: $%.6f (TTL: %ss)", actual_cost, self.period_seconds)
            else:
                await self.redis.incrbyfloat(key, actual_cost)
                logger.debug("Added global cost: $%.6f", actual_cost)

        except Exception as e:
            logger.error("Error recording global cost", exc_info=True, extra={
                "error_type": type(e).__name__,
                "error_message": str(e),
                "operation": "global_cost_record",
                "actual_cost": actual_cost,
                "redis_key": key,
            })

    async def get_current_usage(self) -> float:
        """Get current global cost usage in current period."""
        key = self._get_global_key()
        try:
            return float(await self.redis.get(key) or 0)
        except Exception as e:
            logger.error("Error getting global cost usage", exc_info=True, extra={
                "error_type": type(e).__name__,
                "error_message": str(e),
                "operation": "global_cost_usage_get",
                "redis_key": key,
            })
            return 0.0


class CostLimiter:
    """Main cost limiter combining IP and global cost tracking."""

    def __init__(self, redis_client: aioredis.Redis):
        """Initialize with settings from config."""
        self.ip_limiter = IPCostLimiter(
            redis_client,
            max_cost=settings.per_user_cost_limit,
            period_seconds=settings.per_user_cost_period_seconds,
        )
        self.global_limiter = GlobalCostLimiter(
            redis_client,
            max_cost=settings.global_cost_limit,
            period_seconds=settings.global_cost_period_seconds,
        )

    async def is_allowed(self, websocket: WebSocket) -> bool:
        """Check if request is allowed based on both IP and global cost limits."""
        ip_identifier = get_ip_identifier(websocket)

        if not await self.global_limiter.is_within_limits():
            logger.warning("Global cost limit exceeded: %.6f >= %s",
                           await self.global_limiter.get_current_usage(), self.global_limiter.max_cost)
            return False

        if not await self.ip_limiter.is_within_limits(ip_identifier):
            logger.warning("IP cost limit exceeded for %s...: %.6f >= %s",
                           ip_identifier[:8], await self.ip_limiter.get_current_usage(ip_identifier), self.ip_limiter.max_cost)
            return False

        return True

    async def record_cost(self, websocket: WebSocket, actual_cost: float) -> None:
        """Record actual cost for both IP and global tracking."""
        if actual_cost <= 0:
            return

        ip_identifier = get_ip_identifier(websocket)

        await self.ip_limiter.record_cost(ip_identifier, actual_cost)
        await self.global_limiter.record_cost(actual_cost)

        logger.info("Recorded cost $%.6f for IP %s...", actual_cost, ip_identifier[:8])
