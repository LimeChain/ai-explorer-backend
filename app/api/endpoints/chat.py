"""
Chat endpoint for the AI Explorer backend service.
"""
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import json

from app.schemas.chat import ChatRequest
from app.services.llm_orchestrator import LLMOrchestrator


logger = logging.getLogger(__name__)
router = APIRouter()
llm_orchestrator = LLMOrchestrator()


@router.websocket("/ws")
async def websocket_chat(websocket: WebSocket):
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
                message = json.loads(data)
                query = message.get("query")
                
                if not query or not query.strip():
                    await websocket.send_text(json.dumps({
                        "error": "Query cannot be empty or whitespace"
                    }))
                    continue
                
                # Stream LLM response
                async for token in llm_orchestrator.stream_llm_response(query):
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