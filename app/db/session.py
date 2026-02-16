"""
Async database session management and configuration.

Provides AsyncSession via FastAPI dependency injection.
All database access should use get_async_db() or get_async_db_session().

DEPRECATED: get_db_session() provides sync Session for backward compat.
It will be removed once chat.py and evals are migrated (Task 5 / Story 1-2).
"""
import warnings
from contextlib import asynccontextmanager, contextmanager
from collections.abc import AsyncGenerator, Generator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings


def _make_async_url(url: str) -> str:
    """Convert a postgresql:// URL to postgresql+asyncpg:// for async driver."""
    if url.startswith("postgresql+asyncpg://"):
        return url
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    return url


def _make_sync_url(url: str) -> str:
    """Convert a database URL to use the psycopg (v3) sync driver."""
    for prefix in ("postgresql+asyncpg://", "postgresql+psycopg2://", "postgresql://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


# Module-level engine and session factory — created once at import time.
# Lifecycle (open/dispose) managed by app lifespan in main.py.
_async_engine: AsyncEngine = create_async_engine(
    _make_async_url(settings.database_url),
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    pool_timeout=settings.database_pool_timeout,
    pool_recycle=settings.database_pool_recycle,
    pool_pre_ping=settings.database_pool_pre_ping,
    echo=settings.database_echo,
)

_async_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=_async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


def get_async_engine() -> AsyncEngine:
    """Return the async engine for lifespan management (dispose on shutdown)."""
    return _async_engine


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields an AsyncSession.

    Usage:
        @router.get("/items")
        async def list_items(db: AsyncSession = Depends(get_async_db)):
            result = await db.execute(select(Item))
            return result.scalars().all()
    """
    async with _async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def get_async_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager for code that needs a session outside FastAPI DI.

    Usage:
        async with get_async_db_session() as db:
            result = await db.execute(select(Item))
            items = result.scalars().all()
            await db.commit()
    """
    async with _async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


# ---------------------------------------------------------------------------
# DEPRECATED sync session — used by chat.py and evals/main.py.
# Will be removed in Task 5 (Story 1-1) / Story 1-2.
# ---------------------------------------------------------------------------

_sync_engine = create_engine(
    _make_sync_url(settings.database_url),
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    pool_timeout=settings.database_pool_timeout,
    pool_recycle=settings.database_pool_recycle,
    pool_pre_ping=settings.database_pool_pre_ping,
    echo=settings.database_echo,
)

_sync_session_factory = sessionmaker(
    bind=_sync_engine,
    autocommit=False,
    autoflush=False,
)


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """DEPRECATED: Use get_async_db_session() instead. Removed in Task 5."""
    warnings.warn(
        "get_db_session() is deprecated. Use get_async_db_session().",
        DeprecationWarning,
        stacklevel=2,
    )
    session = _sync_session_factory()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
