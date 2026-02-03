"""
Feature-flag service – CRUD operations, Redis cache management, and flag
resolution with per-account → global → default fall-through.
"""
from typing import Optional

import redis
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import FeatureFlag
from app.services.feature_flag_defaults import FLAG_DEFAULTS
from app.utils.logging_config import get_service_logger

logger = get_service_logger("feature_flag_service")

# ---------------------------------------------------------------------------
# Redis client (mirrors the pattern used by rate_limiter.py)
# ---------------------------------------------------------------------------
_redis = redis.Redis.from_url(
    settings.redis_url,
    max_connections=settings.redis_max_connections,
    retry_on_timeout=settings.redis_retry_on_timeout,
    socket_timeout=settings.redis_socket_timeout,
)

CACHE_TTL_SECONDS = 300  # 5 minutes


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _cache_key(flag_key: str, account_id: Optional[str]) -> str:
    """Return the Redis key for a given flag + scope."""
    if account_id is None:
        return f"ff:{flag_key}:global"
    return f"ff:{flag_key}:account:{account_id}"


def _invalidate(flag_key: str, account_id: Optional[str]) -> None:
    """Delete the cached value so the next read re-populates it."""
    try:
        _redis.delete(_cache_key(flag_key, account_id))
    except redis.RedisError:
        logger.warning("Redis cache invalidation failed for %s", _cache_key(flag_key, account_id))


def _read_cache(flag_key: str, account_id: Optional[str]) -> Optional[bool]:
    """Return the cached boolean or None on miss / error."""
    try:
        raw = _redis.get(_cache_key(flag_key, account_id))
        if raw is None:
            return None
        return raw == b"true"
    except redis.RedisError:
        logger.warning("Redis cache read failed for %s", _cache_key(flag_key, account_id))
        return None


def _write_cache(flag_key: str, account_id: Optional[str], value: bool) -> None:
    """Write a boolean into Redis with the standard TTL."""
    try:
        _redis.setex(_cache_key(flag_key, account_id), CACHE_TTL_SECONDS, "true" if value else "false")
    except redis.RedisError:
        logger.warning("Redis cache write failed for %s", _cache_key(flag_key, account_id))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def resolve_flag(db: Session, flag_key: str, account_id: Optional[str] = None) -> bool:
    """
    Resolve a single flag following the priority chain:
      1. Per-account cache / DB
      2. Global cache / DB
      3. Hardcoded default

    The result at each level is cached on a DB hit so subsequent reads within
    the TTL window skip the database entirely.
    """
    if flag_key not in FLAG_DEFAULTS:
        raise ValueError(f"Unknown flag key: {flag_key}")

    # --- per-account scope --------------------------------------------------
    if account_id is not None:
        cached = _read_cache(flag_key, account_id)
        if cached is not None:
            return cached
        row = (
            db.query(FeatureFlag)
            .filter(FeatureFlag.key == flag_key, FeatureFlag.account_id == account_id)
            .first()
        )
        if row is not None:
            _write_cache(flag_key, account_id, row.value)
            return row.value

    # --- global scope -------------------------------------------------------
    cached = _read_cache(flag_key, None)
    if cached is not None:
        return cached
    row = (
        db.query(FeatureFlag)
        .filter(FeatureFlag.key == flag_key, FeatureFlag.account_id.is_(None))
        .first()
    )
    if row is not None:
        _write_cache(flag_key, None, row.value)
        return row.value

    # --- hardcoded default --------------------------------------------------
    return FLAG_DEFAULTS[flag_key]


def list_flags(db: Session) -> list[dict]:
    """Return every persisted flag row as a list of dicts."""
    rows = db.query(FeatureFlag).order_by(FeatureFlag.key, FeatureFlag.account_id).all()
    return [
        {
            "id": str(row.id),
            "key": row.key,
            "value": row.value,
            "account_id": row.account_id,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }
        for row in rows
    ]


def upsert_flag(db: Session, flag_key: str, value: bool, account_id: Optional[str] = None) -> dict:
    """
    Insert or update a flag row.  Invalidates the Redis cache so the new
    value is visible to all services on the next read.
    """
    if flag_key not in FLAG_DEFAULTS:
        raise ValueError(f"Unknown flag key: {flag_key}")

    row = (
        db.query(FeatureFlag)
        .filter(
            FeatureFlag.key == flag_key,
            FeatureFlag.account_id == account_id if account_id is not None else FeatureFlag.account_id.is_(None),
        )
        .first()
    )

    if row is None:
        row = FeatureFlag(key=flag_key, value=value, account_id=account_id)
        db.add(row)
    else:
        row.value = value

    db.commit()
    db.refresh(row)
    _invalidate(flag_key, account_id)

    logger.info(
        "Flag upserted: key=%s value=%s account_id=%s",
        flag_key, value, account_id,
    )

    return {
        "id": str(row.id),
        "key": row.key,
        "value": row.value,
        "account_id": row.account_id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def delete_flag(db: Session, flag_key: str, account_id: Optional[str] = None) -> bool:
    """
    Delete a persisted flag row (falls back to hardcoded default on next
    resolve).  Returns True if a row was deleted, False if nothing matched.
    """
    row = (
        db.query(FeatureFlag)
        .filter(
            FeatureFlag.key == flag_key,
            FeatureFlag.account_id == account_id if account_id is not None else FeatureFlag.account_id.is_(None),
        )
        .first()
    )
    if row is None:
        return False

    db.delete(row)
    db.commit()
    _invalidate(flag_key, account_id)

    logger.info("Flag deleted: key=%s account_id=%s", flag_key, account_id)
    return True
