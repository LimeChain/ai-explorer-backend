"""
Chat endpoint for the AI Explorer backend service.
"""
import logging
from fastapi import APIRouter

from app.schemas.chat import ChatRequest, ChatResponse


logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """
    Main chat endpoint for the AI Explorer.
    
    Accepts a user query and returns a hardcoded response while the AI systems
    are being implemented.
    
    Args:
        request: ChatRequest containing the user's query
        
    Returns:
        ChatResponse with a hardcoded message
    """
    logger.info(f"Received chat request: {request.query}")
    
    return ChatResponse(
        response="Hello, I am the AI Explorer. My systems are not fully online yet."
    )