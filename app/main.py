"""
Main FastAPI application for the AI Explorer backend service.
"""
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI
from psycopg_pool import AsyncConnectionPool
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.api.endpoints import chat, message, suggestions
from app.config import settings
from app.db.session import get_async_engine
from app.dependencies import set_redis_client
from app.exception_handlers import register_exception_handlers
from app.utils.logging_config import setup_logging, get_logger
from app.middleware import correlation_id_middleware

# Setup centralized logging
logging_success = setup_logging(
    level=settings.log_level,
    use_json=(settings.environment == "production"),
    use_colors=(settings.environment != "production"),
    service_name="api"
)

logger = get_logger(__name__, service_name="api")

if logging_success:
    logger.info("Advanced logging configuration loaded successfully")
else:
    logger.warning("Fallback logging configuration is active")

if settings.langsmith_tracing:
    logger.info("LangSmith tracing enabled")
else:
    logger.info("LangSmith tracing disabled")

# ---------------------------------------------------------------------------
# Checkpointer pool (psycopg3 — used by LangGraph)
# ---------------------------------------------------------------------------
_pool: AsyncConnectionPool | None = None
checkpointer: AsyncPostgresSaver | None = None


def _get_checkpointer_pool() -> AsyncConnectionPool:
    """Lazy-create the checkpointer connection pool."""
    global _pool
    if _pool is None:
        _pool = AsyncConnectionPool(
            settings.database_url,
            min_size=settings.checkpointer_min_pool_size,
            max_size=settings.checkpointer_max_pool_size,
            max_idle=settings.checkpointer_max_idle,
            timeout=settings.checkpointer_pool_timeout,
            open=False,
            kwargs={"autocommit": True},
            check=AsyncConnectionPool.check_connection,
        )
    return _pool


# ---------------------------------------------------------------------------
# Lifespan — manages Redis, async SQLAlchemy engine, and checkpointer pool
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager — runs once at startup and shutdown."""
    global checkpointer, _pool

    # --- Redis ---
    redis_client = aioredis.from_url(
        settings.redis_url,
        max_connections=settings.redis_max_connections,
        retry_on_timeout=settings.redis_retry_on_timeout,
        socket_timeout=settings.redis_socket_timeout,
    )
    try:
        await redis_client.ping()
        logger.info("Redis connection established successfully")
    except Exception as e:
        logger.error("Failed to connect to Redis: %s", e)
        raise

    set_redis_client(redis_client)

    # --- Checkpointer pool (psycopg3) ---
    pool = _get_checkpointer_pool()
    await pool.open()
    await pool.wait(timeout=settings.checkpointer_pool_timeout)

    try:
        checkpointer = AsyncPostgresSaver(pool)
        await checkpointer.setup()
        logger.info("Checkpointer initialized successfully")

        yield  # Application runs here

    except Exception as e:
        logger.error("Failed to initialize checkpointer: %s", e)
        raise
    finally:
        # Shutdown: close Redis, checkpointer pool, async SQLAlchemy engine
        await redis_client.aclose()
        set_redis_client(None)
        logger.info("Redis connection closed")

        await pool.close()
        _pool = None

        engine = get_async_engine()
        await engine.dispose()
        logger.info("Async DB engine disposed")


# Create FastAPI app with lifespan
app = FastAPI(
    title="AI Explorer Backend",
    description="Backend service for the THF AI Explorer - a next-generation block explorer for the Hedera network",
    version="0.1.0",
    lifespan=lifespan,
)

# Add middleware (order matters - correlation ID middleware should be first)
app.middleware("http")(correlation_id_middleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register exception handlers
register_exception_handlers(app)

# Include routers
app.include_router(message.router, prefix="/api/v1", tags=["message"])
app.include_router(chat.router, prefix="/api/v1", tags=["chat"])
app.include_router(suggestions.router, prefix="/api/v1", tags=["suggestions"])

logger.info("AI Explorer Backend service started")


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint for load balancer."""
    return {"status": "healthy", "message": "AI Explorer Backend is running"}
