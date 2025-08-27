"""
Main FastAPI application for the AI Explorer backend service.
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.api.endpoints import chat, message, suggestions
from app.config import settings
from app.exception_handlers import register_exception_handlers
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

if settings.langsmith_tracing:
    logging.info("LangSmith tracing enabled")
else:
    logging.info("LangSmith tracing disabled")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
    ]
)

logger = logging.getLogger(__name__)

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
            logging.info("Checkpointer initialized successfully")
            
            yield  # Application runs here
            
    except Exception as e:
        logging.error(f"Failed to initialize checkpointer: {e}")
        raise


# Create FastAPI app with lifespan
app = FastAPI(
    title="AI Explorer Backend",
    description="Backend service for the THF AI Explorer - a next-generation block explorer for the Hedera network",
    version="0.1.0",
    lifespan=lifespan,  # Add this line
)

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

logger.info("AI Explorer Backend service started")


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint for load balancer."""
    return {"status": "healthy", "message": "AI Explorer Backend is running"}