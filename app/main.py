"""
Main FastAPI application for the AI Explorer backend service.
"""
import logging
from fastapi import FastAPI

from app.api.endpoints import chat
from app.exception_handlers import register_exception_handlers


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

# Register exception handlers
register_exception_handlers(app)

# Include routers
app.include_router(chat.router, prefix="/api/v1/chat", tags=["chat"])

logger.info("AI Explorer Backend service started")


@app.get("/")
async def root():
    """Root endpoint for health check."""
    return {"message": "AI Explorer Backend is running"}