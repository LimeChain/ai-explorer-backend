"""WebSocket client for communicating with the AI Explorer API."""

import json
import logging
import asyncio
from uuid import uuid4
from typing import Optional, AsyncGenerator, Dict, Any
from contextlib import asynccontextmanager

import websockets
from websockets.client import WebSocketClientProtocol
from websockets.exceptions import ConnectionClosedError, ConnectionClosedOK

from ..config import settings

logger = logging.getLogger(__name__)


class AIExplorerAPIClient:
    """Client for communicating with the AI Explorer API via WebSocket."""
    
    def __init__(self):
        self.websocket: Optional[WebSocketClientProtocol] = None
        self.session_id: str = str(uuid4())
        
    @asynccontextmanager
    async def connect(self):
        """Context manager for WebSocket connection."""
        url = f"{settings.api_base_url}/api/v1/chat/ws/{self.session_id}"
        
        # Convert http/https to ws/wss
        if url.startswith("http://"):
            url = url.replace("http://", "ws://")
        elif url.startswith("https://"):
            url = url.replace("https://", "wss://")
            
        logger.info(f"Connecting to AI Explorer API at {url}")
        
        try:
            async with websockets.connect(
                url,
                ping_interval=30,
                ping_timeout=10
            ) as websocket:
                self.websocket = websocket
                logger.info("Successfully connected to AI Explorer API")
                yield self
        except Exception as e:
            logger.error(f"Failed to connect to AI Explorer API: {e}")
            raise
        finally:
            self.websocket = None
            logger.info("Disconnected from AI Explorer API")
    
    async def ask_explorer(
        self, 
        question: str, 
        network: str = "mainnet",
        account_id: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """
        Send a question to the AI Explorer and stream the response.
        
        Args:
            question: Ask the AI Explorer
            network: The Hedera network (mainnet, testnet)
            account_id: Optional account ID for context
            
        Yields:
            Response tokens from the AI Explorer
            
        Raises:
            RuntimeError: If not connected or connection fails
        """
        if not self.websocket:
            raise RuntimeError("Not connected to API. Use within connect() context manager.")
        
        # Prepare the query message
        message = {
            "type": "query",
            "content": question,
            "network": network
        }
        
        if account_id:
            message["account_id"] = account_id
        
        try:
            # Send the query
            await self.websocket.send(json.dumps(message))
            logger.info(f"Sent query to AI Explorer: {question[:100]}...")
            
            # Stream the response
            full_response = ""
            assistant_msg_id = None
            user_msg_id = None
            
            async for raw_message in self.websocket:
                try:
                    response = json.loads(raw_message)
                    
                    if "error" in response:
                        error_msg = response["error"]
                        logger.error(f"API error: {error_msg}")
                        raise RuntimeError(f"API error: {error_msg}")
                    
                    elif "token" in response:
                        token = response["token"]
                        full_response += token
                        yield token
                    
                    elif "assistant_msg_id" in response:
                        assistant_msg_id = response["assistant_msg_id"]
                        logger.debug(f"Received assistant message ID: {assistant_msg_id}")
                    
                    elif "user_msg_id" in response:
                        user_msg_id = response["user_msg_id"]
                        logger.debug(f"Received user message ID: {user_msg_id}")
                    
                    elif response.get("complete"):
                        logger.info("Query completed successfully")
                        break
                        
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to decode response: {e}")
                    continue
            
            logger.info(f"Received complete response ({len(full_response)} characters)")
            
        except (ConnectionClosedError, ConnectionClosedOK) as e:
            logger.error(f"WebSocket connection closed: {e}")
            raise RuntimeError(f"Connection lost: {e}")
        except asyncio.TimeoutError:
            logger.error("Request timed out")
            raise RuntimeError("Request timed out")
        except Exception as e:
            logger.error(f"Unexpected error during query: {e}")
            raise RuntimeError(f"Query failed: {e}")
    
    async def get_full_response(
        self, 
        question: str, 
        network: str = "mainnet",
        account_id: Optional[str] = None
    ) -> str:
        """
        Get the complete response as a single string.
        
        Args:
            question: Ask the AI Explorer
            network: The Hedera network (mainnet, testnet)
            account_id: Optional account ID for context
            
        Returns:
            Complete response string
        """
        response_parts = []
        async for token in self.ask_explorer(question, network, account_id):
            response_parts.append(token)
        
        return "".join(response_parts)