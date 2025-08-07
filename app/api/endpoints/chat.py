"""
Chat endpoint for the AI Explorer backend service.
"""
import logging
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.schemas.chat import ChatRequest
from app.services.llm_orchestrator import LLMOrchestrator
from app.db.session import get_session_local
from app.exceptions import ChatServiceError, ValidationError, LLMServiceError


logger = logging.getLogger(__name__)
router = APIRouter()
llm_orchestrator = LLMOrchestrator()


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

            db = None

            try:
                SessionLocal = get_session_local()
                db = SessionLocal()  

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
                
                # Stream LLM response with account context, session ID, and database session
                assistant_msg_id = None
                def on_complete(msg_id):
                    nonlocal assistant_msg_id
                    assistant_msg_id = msg_id

                async for token in llm_orchestrator.stream_llm_response(
                    query=query,
                    account_id=chat_request.account_id,
                    conversation_history=chat_request.messages,
                    session_id=chat_request.session_id,
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
            finally:
                if db is not None:
                    db.close()
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected for session {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error for session {session_id}: {e}")
        await websocket.close(code=1011, reason="Internal server error")