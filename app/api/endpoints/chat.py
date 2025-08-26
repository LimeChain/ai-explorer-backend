"""
Chat endpoint for the AI Explorer backend service.
"""
import logging
import json
import asyncio

from uuid import UUID

from fastapi import APIRouter, Path, WebSocket, WebSocketDisconnect

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
async def websocket_chat(
    websocket: WebSocket, 
    session_id: UUID = Path(..., description="Session identifier for conversation persistence")
):
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

    active_flow_task = None

    async def cancel_active_flow():
        nonlocal active_flow_task
        await llm_orchestrator.cancel_flow(session_id)
        if active_flow_task and not active_flow_task.done():
            active_flow_task.cancel()
            try:
                await active_flow_task
            except asyncio.CancelledError:
                pass
        active_flow_task = None

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
                
                if message_data.get("type") == "close":
                    await cancel_active_flow()
                    await websocket.send_text(json.dumps({
                        "closed": True
                    }))
                    await websocket.close(code=1000, reason="User disconnected")
                    return
                
                # Validate using ChatRequest schema
                try:
                    chat_request = ChatRequest(**message_data)
                except ValueError as e:
                    logger.warning(f"Invalid request format: {e}")
                    await websocket.send_text(json.dumps({
                        "error": f"Invalid request: {str(e)}"
                    }))
                    continue
                
                # Log account context for traceability  
                if chat_request.account_id:
                    logger.info(f"Processing request with account_id={chat_request.account_id}")
                
                if not chat_request.query:
                    logger.warning(f"No user message found in request for session {session_id}")
                    await websocket.send_text(json.dumps({
                        "error": "No user message found in request"
                    }))
                    continue
                
                # If a previous flow is running, cancel it before starting a new one
                if active_flow_task and not active_flow_task.done():
                    await cancel_active_flow()

                async def run_flow_and_stream(local_chat_request: ChatRequest = chat_request):
                    with get_db_session() as db:
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

                    try:
                        async for token in llm_orchestrator.stream_llm_response(
                            query=local_chat_request.query,
                            session_id=session_id,
                            account_id=local_chat_request.account_id,
                            db=db,  # Pass database session for conversation persistence
                            on_complete=on_complete
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
                        
                    except asyncio.CancelledError:
                        logger.info(f"Flow cancelled for session {session_id}")
                        raise
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

                # Start flow in background to allow cancellation on disconnect
                active_flow_task = asyncio.create_task(run_flow_and_stream())
                
            except json.JSONDecodeError as e:
                logger.warning(f"Invalid JSON received for session {session_id}: {e}")
                await websocket.send_text(json.dumps({
                    "error": "Invalid JSON format"
                }))
            except (ValidationError, ChatServiceError) as e:
                logger.error(f"Service error for session {session_id}: {e}")
                await websocket.send_text(json.dumps({
                    "error": f"Service error"
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
        await cancel_active_flow()
    except Exception as e:
        logger.error(f"WebSocket error for session {session_id}: {e}")
        await cancel_active_flow()
        try:
            await websocket.close(code=1011, reason="Internal server error")
        except Exception:
            pass