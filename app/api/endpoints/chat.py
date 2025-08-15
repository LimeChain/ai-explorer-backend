"""
Chat endpoint for the AI Explorer backend service.
"""
import logging
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.schemas.chat import ChatRequest
from app.services.llm_orchestrator import LLMOrchestrator
from app.db.session import get_db_session
from app.exceptions import ChatServiceError, ValidationError, LLMServiceError, RateLimitError
from app.utils.rate_limiter import IPRateLimiter, GlobalRateLimiter, redis_client
from app.utils.cost_limiter import CostLimiter
from app.config import settings


logger = logging.getLogger(__name__)
router = APIRouter()
llm_orchestrator = LLMOrchestrator()

# Create global rate limiter instance
global_rate_limiter = GlobalRateLimiter(
    redis_client,
    max_requests=settings.global_rate_limit_max_requests,
    window_seconds=settings.global_rate_limit_window_seconds
)

# Create cost limiter (separate from rate limiter)
cost_limiter = CostLimiter(redis_client)

# Create message-level rate limiter instance with global limiter
ip_rate_limiter = IPRateLimiter(
    redis_client, 
    max_requests=settings.rate_limit_max_requests,
    window_seconds=settings.rate_limit_window_seconds,
    global_limiter=global_rate_limiter
)


@router.websocket("/chat/ws/{session_id}")
async def websocket_chat(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for real-time chat with the AI Explorer.
    
    Accepts WebSocket connections and streams LLM responses in real-time with
    automatic conversation persistence using dependency injection patterns.
    
    Message format:
    - Send: {"query": "your question here", "account_id": "optional_account"}
    - Receive: {"token": "response_token"} or {"error": "error_message"} or {"complete": true}
    
    Args:
        websocket: WebSocket connection
        session_id: Session identifier for conversation persistence
    """
    await websocket.accept()
    logger.info(f"WebSocket connection established for session: {session_id}")
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            logger.info(f"Received WebSocket message for session {session_id}: {data}")

            try:
                # Check rate limit for each message before processing
                if not ip_rate_limiter.is_allowed(websocket):
                    logger.warning(f"Rate limit exceeded for message in session {session_id}")
                    await websocket.send_text(json.dumps({
                        "error": f"Rate limit exceeded. Limits: {settings.rate_limit_max_requests} per IP per {settings.rate_limit_window_seconds}s, {settings.global_rate_limit_max_requests} global per {settings.global_rate_limit_window_seconds}s."
                    }))
                    continue  # Skip processing this message but keep connection alive
                
                # Check cost limits separately
                if not cost_limiter.is_allowed(websocket):
                    logger.warning(f"Cost limit exceeded for message in session {session_id}")
                    await websocket.send_text(json.dumps({
                        "error": (
                            f"Cost limit exceeded. Limits: "
                            f"${settings.per_user_cost_limit} per user per {settings.per_user_cost_period_seconds}s, "
                            f"${settings.global_cost_limit} global per {settings.global_cost_period_seconds}s."
                        )
                    }))
                    continue  # Skip processing this message but keep connection alive
                
                message_data = json.loads(data)
                
                # Validate using ChatRequest schema
                try:
                    chat_request = ChatRequest(session_id=session_id, **message_data)
                except ValueError as e:
                    logger.warning(f"Invalid request format: {e}")
                    await websocket.send_text(json.dumps({
                        "error": f"Invalid request: {str(e)}"
                    }))
                    continue
                
                # Log account context for traceability  
                if chat_request.account_id:
                    logger.info(f"Processing request with account_id={chat_request.account_id}")
                
                # Extract query from messages (last user message)
                query = None
                if chat_request.messages:
                    for msg in reversed(chat_request.messages):
                        if msg.role == "user":
                            query = msg.content
                            break
                
                if not query:
                    logger.warning(f"No user message found in request for session {session_id}")
                    await websocket.send_text(json.dumps({
                        "error": "No user message found in request"
                    }))
                    continue
                
                # Use context manager for safe database session handling
                with get_db_session() as db:
                    # Stream LLM response with account context, session ID, and database session
                    assistant_msg_id = None
                    def on_complete(msg_id):
                        nonlocal assistant_msg_id
                        assistant_msg_id = msg_id

                    def on_cost_calculated(final_state):
                        """Record actual costs after LLM completion."""
                        actual_cost = final_state.get("total_cost", 0.0)
                        if actual_cost > 0:
                            # Record cost using separate cost limiter
                            cost_limiter.record_cost(websocket, actual_cost)
                            logger.info(f"Recorded actual cost for session {session_id}: ${actual_cost:.6f}")

                    async for token in llm_orchestrator.stream_llm_response(
                        query=query,
                        account_id=chat_request.account_id,
                        conversation_history=chat_request.messages,
                        session_id=chat_request.session_id,
                        db=db,  # Pass database session for conversation persistence
                        on_complete=on_complete,
                        on_cost_calculated=on_cost_calculated
                    ):
                        await websocket.send_text(json.dumps({
                            "token": token
                        }))
                    
                    # Send assistant message ID to client if available
                    if assistant_msg_id:
                        await websocket.send_text(json.dumps({
                            "assistant_msg_id": str(assistant_msg_id)
                        }))

                    # Send completion signal
                    await websocket.send_text(json.dumps({
                        "complete": True
                    }))

                    logger.info(f"Successfully processed query for session {session_id}")
                    # Explicit commit for any remaining uncommitted changes
                    db.commit()
                
            except json.JSONDecodeError as e:
                logger.warning(f"Invalid JSON received for session {session_id}: {e}")
                await websocket.send_text(json.dumps({
                    "error": "Invalid JSON format"
                }))
            except (ValidationError, ChatServiceError) as e:
                logger.error(f"Service error for session {session_id}: {e}")
                await websocket.send_text(json.dumps({
                    "error": f"Service error: {str(e)}"
                }))
            except LLMServiceError as e:
                logger.error(f"LLM service error for session {session_id}: {e}")
                await websocket.send_text(json.dumps({
                    "error": "AI service temporarily unavailable. Please try again."
                }))
            except Exception as e:
                logger.error(f"Unexpected error processing message for session {session_id}: {e}")
                await websocket.send_text(json.dumps({
                    "error": "Internal server error"
                }))
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected for session {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error for session {session_id}: {e}")
        await websocket.close(code=1011, reason="Internal server error")