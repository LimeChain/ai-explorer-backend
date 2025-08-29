"""
Main FastAPI application for the AI Explorer backend service.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.api.endpoints import chat, message, suggestions
from app.config import settings
from app.exception_handlers import register_exception_handlers
from app.utils.logging_config import setup_logging, get_logger, set_correlation_id
from app.middleware import correlation_id_middleware
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

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
    logger.warning("⚠️ Fallback logging configuration is active")

if settings.langsmith_tracing:
    logger.info("✅ LangSmith tracing enabled")
else:
    logger.info("🚫 LangSmith tracing disabled")

# Global checkpointer instance
checkpointer = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager - runs once at startup and shutdown."""
    global checkpointer
    
    # Startup: Initialize checkpointer
    try:
        # Create the checkpointer using the context manager
        async with AsyncPostgresSaver.from_conn_string(settings.database_url) as checkpointer:
            await checkpointer.setup()
            logger.info("✅ Checkpointer initialized successfully")
            
            yield  # Application runs here
            
    except Exception as e:
        logger.error(f"❌ Failed to initialize checkpointer: {e}")
        raise


# Create FastAPI app with lifespan
app = FastAPI(
    title="AI Explorer Backend",
    description="Backend service for the THF AI Explorer - a next-generation block explorer for the Hedera network",
    version="0.1.0",
    lifespan=lifespan,  # Add this line
)

# Add middleware (order matters - correlation ID middleware should be first)
app.middleware("http")(correlation_id_middleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,  # Allows all origins. Change to a list of allowed origins in production!
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allows all headers
)

# Register exception handlers
register_exception_handlers(app)

# Include routers
app.include_router(message.router, prefix="/api/v1", tags=["message"])
app.include_router(chat.router, prefix="/api/v1", tags=["chat"])
app.include_router(suggestions.router, prefix="/api/v1", tags=["suggestions"])

logger.info("🚀 AI Explorer Backend service started")


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint for load balancer."""
    return {"status": "healthy", "message": "AI Explorer Backend is running"}