"""
Shared FastAPI dependencies — created during lifespan, consumed via DI.

Keeps dependency state out of main.py to avoid circular imports
(main.py imports routers, routers import dependencies).
"""
import redis.asyncio as aioredis

_redis_client: aioredis.Redis | None = None


def get_redis_client() -> aioredis.Redis:
    """FastAPI dependency — returns the shared async Redis client.

    Overridable in tests via ``app.dependency_overrides[get_redis_client]``.
    """
    if _redis_client is None:
        raise RuntimeError("Redis client not initialized. Is the app lifespan running?")
    return _redis_client


def set_redis_client(client: aioredis.Redis | None) -> None:
    """Called by lifespan to set/clear the shared Redis client."""
    global _redis_client
    _redis_client = client
