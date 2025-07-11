"""
Chat endpoint for the AI Explorer backend service.
"""
import logging
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.schemas.chat import ChatRequest
from app.services.llm_orchestrator import LLMOrchestrator


logger = logging.getLogger(__name__)
router = APIRouter()
llm_orchestrator = LLMOrchestrator()


@router.post(
    "/",
    responses={
        200: {
            "description": "Successful streaming response",
            "content": {"text/event-stream": {"example": "data: Hello\n\ndata: world\n\n"}}
        },
        400: {
            "description": "Bad Request - Invalid input",
            "content": {"application/json": {"example": {"detail": "Query cannot be empty or whitespace"}}}
        },
        503: {
            "description": "Service Unavailable - AI service is temporarily unavailable",
            "content": {"application/json": {"example": {"detail": "The AI service is currently unavailable. Please try again in a moment."}}}
        }
    }
)
async def chat(request: ChatRequest) -> StreamingResponse:
    """
    Main chat endpoint for the AI Explorer with streaming LLM responses.
    
    Accepts a user query and returns a streaming response from the LLM
    using Server-Sent Events (SSE) for real-time token-by-token delivery.
    
    Args:
        request: ChatRequest containing the user's query
        
    Returns:
        StreamingResponse with text/event-stream content type
    """
    logger.info(f"Received chat request: {request.query}")
    # await llm_orchestrator.stream_llm_response(request.query) # TODO: left for future testing needs, seeing results better since not streaming response
    async def generate_response():
        """Generate streaming response from LLM."""
        async for token in llm_orchestrator.stream_llm_response(request.query):
            yield f"data: {token}\n\n"
    
    return StreamingResponse(
        generate_response(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
        }
    )