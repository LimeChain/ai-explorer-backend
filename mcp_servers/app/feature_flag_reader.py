"""
MCP-side feature-flag reader.

Resolution order: Redis cache → raw SQL against feature_flags → hardcoded
default.  This module intentionally avoids importing anything from the API
container (app.db.models, app.config, etc.) – it only needs the shared
defaults module and a plain psycopg2 / asyncpg connection for the fallback
SQL query.

The Redis client mirrors the pattern used by app/utils/rate_limiter.py.
"""
import redis
import psycopg2  # type: ignore[import-untyped]
from typing import Optional

from app.services.feature_flag_defaults import FLAG_DEFAULTS
from .settings import settings
from .logging_config import get_logger

logger = get_logger(__name__, service_name="mcp")

# ---------------------------------------------------------------------------
# Redis client
# ---------------------------------------------------------------------------
_redis = redis.Redis.from_url(
    settings.redis_url,
    max_connections=settings.redis_max_connections,
    socket_timeout=settings.redis_socket_timeout,
)

CACHE_TTL_SECONDS = 300


def _cache_key(flag_key: str, account_id: Optional[str]) -> str:
    if account_id is None:
        return f"ff:{flag_key}:global"
    return f"ff:{flag_key}:account:{account_id}"


# ---------------------------------------------------------------------------
# Raw-SQL fallback
# ---------------------------------------------------------------------------
_SQL_ACCOUNT = """
SELECT value FROM feature_flags
WHERE key = %s AND account_id = %s
LIMIT 1
"""

_SQL_GLOBAL = """
SELECT value FROM feature_flags
WHERE key = %s AND account_id IS NULL
LIMIT 1
"""


def _query_db(flag_key: str, account_id: Optional[str]) -> Optional[bool]:
    """
    Execute a two-column SELECT against feature_flags.  Returns the boolean
    value if a row is found, else None.  On any DB error the exception is
    logged and None is returned so that resolution falls through to the
    hardcoded default rather than crashing the tool.
    """
    try:
        conn = psycopg2.connect(settings.database_url)
        conn.autocommit = True
        cur = conn.cursor()
        try:
            if account_id is not None:
                cur.execute(_SQL_ACCOUNT, (flag_key, account_id))
            else:
                cur.execute(_SQL_GLOBAL, (flag_key,))
            row = cur.fetchone()
            return bool(row[0]) if row else None
        finally:
            cur.close()
            conn.close()
    except Exception:
        logger.warning("DB fallback failed for flag %s (account=%s)", flag_key, account_id, exc_info=True)
        return None


# ---------------------------------------------------------------------------
# Public resolve
# ---------------------------------------------------------------------------
def resolve_flag(flag_key: str, account_id: Optional[str] = None) -> bool:
    """
    Resolve a single flag: per-account cache/DB → global cache/DB → default.

    This is the hot-path called by @require_flag on every guarded tool
    invocation, so it is kept intentionally simple and fast.
    """
    if flag_key not in FLAG_DEFAULTS:
        logger.warning("Unknown flag key requested: %s – returning False", flag_key)
        return False

    # --- per-account scope --------------------------------------------------
    if account_id is not None:
        try:
            raw = _redis.get(_cache_key(flag_key, account_id))
            if raw is not None:
                return raw == b"true"
        except redis.RedisError:
            logger.warning("Redis read failed for %s (account=%s)", flag_key, account_id)

        db_val = _query_db(flag_key, account_id)
        if db_val is not None:
            try:
                _redis.setex(_cache_key(flag_key, account_id), CACHE_TTL_SECONDS, "true" if db_val else "false")
            except redis.RedisError:
                pass
            return db_val

    # --- global scope -------------------------------------------------------
    try:
        raw = _redis.get(_cache_key(flag_key, None))
        if raw is not None:
            return raw == b"true"
    except redis.RedisError:
        logger.warning("Redis read failed for %s (global)", flag_key)

    db_val = _query_db(flag_key, None)
    if db_val is not None:
        try:
            _redis.setex(_cache_key(flag_key, None), CACHE_TTL_SECONDS, "true" if db_val else "false")
        except redis.RedisError:
            pass
        return db_val

    # --- hardcoded default --------------------------------------------------
    return FLAG_DEFAULTS[flag_key]
