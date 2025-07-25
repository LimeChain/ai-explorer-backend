"""
Main FastAPI application for the AI Explorer backend service.
"""
import logging
from fastapi import FastAPI

from app.api.endpoints import chat, suggestions
from app.config import settings
from app.exception_handlers import register_exception_handlers
from fastapi.middleware.cors import CORSMiddleware

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

# Create FastAPI app instance
app = FastAPI(
    title="AI Explorer Backend",
    description="Backend service for the THF AI Explorer - a next-generation block explorer for the Hedera network",
    version="0.1.0",
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
app.include_router(chat.router, prefix="/api/v1", tags=["chat"])
app.include_router(suggestions.router, prefix="/api/v1", tags=["suggestions"])

logger.info("AI Explorer Backend service started")


@app.get("/")
async def root():
    """Root endpoint for health check."""
    return {"message": "AI Explorer Backend is running"}