"""
Chat endpoint for the AI Explorer backend service.
"""
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import json

from app.schemas.chat import ChatRequest, ChatMessage
from app.services.llm_orchestrator import LLMOrchestrator


logger = logging.getLogger(__name__)
router = APIRouter()
llm_orchestrator = LLMOrchestrator()


@router.websocket("/ws/{session_id}")
async def websocket_chat(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for real-time chat with the AI Explorer.
    
    Accepts WebSocket connections and streams LLM responses in real-time.
    Client should send JSON messages with 'query' field.
    
    Message format:
    - Send: {"query": "your question here"}
    - Receive: {"token": "response_token"} or {"error": "error_message"}
    """
    await websocket.accept()
    logger.info("WebSocket connection established")
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            logger.info(f"Received WebSocket message: {data}")
            
            try:
                message_data = json.loads(data)
                
                # Validate using ChatRequest schema
                try:
                    chat_request = ChatRequest(session_id=session_id, **message_data)
                except ValueError as e:
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
                    await websocket.send_text(json.dumps({
                        "error": "No user message found in request"
                    }))
                    continue
                
                # Stream LLM response with account context and session ID
                async for token in llm_orchestrator.stream_llm_response(
                    query, 
                    account_id=chat_request.account_id,
                    conversation_history=chat_request.messages,
                    session_id=chat_request.session_id
                ):
                    await websocket.send_text(json.dumps({
                        "token": token
                    }))
                
                # Send completion signal
                await websocket.send_text(json.dumps({
                    "complete": True
                }))
                
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({
                    "error": "Invalid JSON format"
                }))
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                await websocket.send_text(json.dumps({
                    "error": f"Internal server error: {str(e)}"
                }))
                
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await websocket.close(code=1011, reason="Internal server error")