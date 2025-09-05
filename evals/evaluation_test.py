#!/usr/bin/env python3
"""
Evaluation Tests for AI Explorer Backend.

Evaluates the AI agent by sending queries over WebSocket to the actual
endpoint, collecting responses, and evaluating them using LangSmith.
"""

import asyncio
import json
import os
import sys
import time
import uuid
import websockets
import websockets.exceptions
from typing import Dict, List, Optional, Any
from urllib.parse import urljoin

# add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langsmith import Client
from app.config import settings
from app.utils.logging_config import setup_logging, get_service_logger, set_correlation_id
from evals.dataset import get_or_create_dataset, DATASET_NAME
from evals.evaluator import correctness_evaluator

WEBSOCKET_ENDPOINT = "http://localhost:8000"
WEBSOCKET_PATH = "/api/v1/chat/ws"
MAX_RESPONSE_TIME = 120 # seconds
PER_MESSAGE_TIMEOUT = 60 # seconds
NETWORK = "mainnet"
EXPERIMENT_PREFIX = "gpt-4.1"

setup_logging(
    level=settings.log_level,
    use_json=False,
    use_colors=True,
    service_name="evals"
)

logger = get_service_logger("evaluation_test", "evals")

# Set up LangSmith client
os.environ["OPENAI_API_KEY"] = settings.llm_api_key.get_secret_value()
client = Client(api_key=settings.langsmith_api_key.get_secret_value())
dataset = get_or_create_dataset(client)


class WebSocketAIClient:
    """WebSocket client for communicating with the AI Explorer backend."""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.websocket = None
        
    async def connect(self, session_id: str) -> None:
        """Connect to the WebSocket endpoint."""
        ws_url = f"{self.base_url.replace('http', 'ws')}{WEBSOCKET_PATH}/{session_id}"
        logger.info("🔗 Connecting to WebSocket", extra={
            "ws_url": ws_url,
            "session_id": session_id,
            "timeout": 10.0
        })
        
        try:
            # Use asyncio.wait_for for timeout instead of websockets timeout parameter
            self.websocket = await asyncio.wait_for(
                websockets.connect(ws_url), 
                timeout=10.0
            )
            logger.info("✅ WebSocket connection established", extra={
                "session_id": session_id
            })
        except Exception as e:
            logger.error("❌ Failed to connect to WebSocket", exc_info=True, extra={
                "session_id": session_id,
                "ws_url": ws_url,
                "error_type": type(e).__name__
            })
            raise
            
    async def disconnect(self) -> None:
        """Disconnect from the WebSocket cleanly."""
        if self.websocket:
            try:
                # Close the websocket without sending close message to avoid API errors
                await self.websocket.close(code=1000, reason="Evaluation completed")
                logger.debug("🔌 WebSocket connection closed cleanly")
            except Exception as e:
                logger.debug("⚠️ Error during WebSocket disconnect", extra={
                    "error": str(e),
                    "error_type": type(e).__name__
                })
            finally:
                self.websocket = None
    
    async def send_query(self, query: str, account_id: Optional[str] = None, network: str = "mainnet") -> str:
        """
        Send a query to the AI and collect the full response.
        
        Args:
            query: The user question
            account_id: Optional account ID for context
            network: Network to use (mainnet, testnet, etc.)
            
        Returns:
            The complete AI response as a string
        """
        if not self.websocket:
            raise RuntimeError("WebSocket not connected")
        
        # Prepare the message
        message = {
            "type": "query",
            "content": query,
            "network": network
        }
        
        if account_id:
            message["account_id"] = account_id
        
        query_preview = query[:100] + "..." if len(query) > 100 else query
        logger.info("📤 Sending query to AI agent", extra={
            "query_preview": query_preview,
            "query_length": len(query),
            "account_id": "***" if account_id else None,
            "network": network
        })
        
        # Send the query
        await self.websocket.send(json.dumps(message))
        
        # Wait for the complete response from the API
        response_parts = []
        start_time = time.time()
        last_progress_log = start_time
        
        try:
            while True:
                # Use shorter timeout per message but track total time
                try:
                    response = await asyncio.wait_for(
                        self.websocket.recv(), 
                        timeout=PER_MESSAGE_TIMEOUT
                    )
                except asyncio.TimeoutError:
                    # Check if total time exceeded
                    total_time = time.time() - start_time
                    if total_time > MAX_RESPONSE_TIME:
                        logger.error("⏰ Total response timeout exceeded", extra={
                            "total_timeout_seconds": MAX_RESPONSE_TIME,
                            "actual_time_seconds": round(total_time, 1),
                            "response_parts_collected": len(response_parts),
                            "partial_response_length": len("".join(response_parts))
                        })
                        # Return partial response if we have something
                        if response_parts:
                            partial_response = "".join(response_parts).strip()
                            logger.info("📥 Returning partial response due to timeout", extra={
                                "partial_response_length": len(partial_response)
                            })
                            return f"{partial_response}\n\n[Response incomplete - timeout after {round(total_time, 1)}s]"
                        return f"Error: Response timeout after {round(total_time, 1)} seconds"
                    else:
                        # Still within total timeout, log progress and continue
                        logger.info("⏳ Still waiting for response...", extra={
                            "elapsed_seconds": round(total_time, 1),
                            "max_seconds": MAX_RESPONSE_TIME,
                            "tokens_received": len(response_parts)
                        })
                        continue
                
                data = json.loads(response)
                
                if "token" in data:
                    # Collect response tokens
                    response_parts.append(data["token"])
                    
                    # Log progress for long responses
                    current_time = time.time()
                    if current_time - last_progress_log > 10:  # Log every 10 seconds
                        logger.info("📊 Response in progress...", extra={
                            "elapsed_seconds": round(current_time - start_time, 1),
                            "tokens_received": len(response_parts),
                            "response_length": len("".join(response_parts))
                        })
                        last_progress_log = current_time
                        
                elif "error" in data:
                    # API returned an error
                    logger.error("🚨 API error received", extra={
                        "error": data['error'],
                        "elapsed_seconds": round(time.time() - start_time, 1)
                    })
                    return f"Error: {data['error']}"
                elif data.get("complete"):
                    # Response is complete, we can return
                    total_time = time.time() - start_time
                    logger.debug("✅ Response completed", extra={
                        "total_time_seconds": round(total_time, 1),
                        "tokens_received": len(response_parts)
                    })
                    break
                elif "assistant_msg_id" in data or "user_msg_id" in data:
                    # Message IDs - just log and continue
                    logger.debug("📨 Message ID received")
                    continue
                else:
                    # Other message types - continue waiting
                    continue
                    
        except websockets.exceptions.ConnectionClosedError as e:
            total_time = time.time() - start_time
            logger.warning("🔌 WebSocket connection closed during response", extra={
                "close_code": e.code,
                "close_reason": e.reason,
                "response_parts_collected": len(response_parts),
                "elapsed_seconds": round(total_time, 1),
                "partial_response_available": len(response_parts) > 0
            })
            
            # Handle service restart (1012) or other connection closes
            if response_parts:
                partial_response = "".join(response_parts).strip()
                logger.info("📥 Returning partial response due to connection close", extra={
                    "partial_response_length": len(partial_response),
                    "close_code": e.code
                })
                return f"{partial_response}\n\n[Response incomplete - connection closed (code: {e.code})]"
            else:
                return f"Error: Connection closed by server (code: {e.code}, reason: {e.reason})"
                
        except Exception as e:
            total_time = time.time() - start_time
            logger.error("❌ Error receiving response", exc_info=True, extra={
                "error_type": type(e).__name__,
                "response_parts_collected": len(response_parts),
                "elapsed_seconds": round(total_time, 1)
            })
            return f"Error: {str(e)}"
        
        # Combine all response parts
        full_response = "".join(response_parts).strip()
        logger.debug("📥 Response collected successfully", extra={
            "response_length": len(full_response),
            "response_parts_count": len(response_parts)
        })
        return full_response


async def run_evaluation_test(inputs: Dict[str, Any], max_retries: int = 1) -> Dict[str, str]:
    """
    Run a single evaluation test following the simple flow:
    1. Open websocket and send query to API
    2. Wait to receive the full response from the API
    3. Return the response for evaluation
    
    Args:
        inputs: Test case inputs containing 'question' and optional 'account_id'
        max_retries: Number of retries for connection issues (1012 service restart)
        
    Returns:
        Dictionary with 'answer' key containing the AI response
    """
    question = inputs["question"]
    account_id = inputs.get("account_id")  # Support both direct and regex extraction
    
    # If no direct account_id, try regex extraction (backward compatibility)
    if not account_id:
        import re
        wallet_pattern = r'0\.0\.\d+'
        match = re.search(wallet_pattern, question)
        account_id = match.group(0) if match else None
    
    last_error = None
    
    for attempt in range(max_retries + 1):
        # Generate unique session ID for each attempt
        session_id = str(uuid.uuid4())
        client = WebSocketAIClient(WEBSOCKET_ENDPOINT)
        
        try:
            if attempt > 0:
                logger.info("🔄 Retrying evaluation due to connection issue", extra={
                    "attempt": attempt + 1,
                    "max_attempts": max_retries + 1,
                    "question": question[:50] + "..." if len(question) > 50 else question,
                    "last_error": str(last_error)
                })
                # Wait a bit before retry to allow server to recover
                await asyncio.sleep(3)
            
            # Step 1: Open websocket and connect to API
            await client.connect(session_id)
            
            # Step 2: Send query and wait for full response from API
            response = await client.send_query(
                query=question,
                account_id=account_id,
                network=NETWORK
            )
            
            # Step 3: Return response for evaluation
            return {"answer": response}
            
        except websockets.exceptions.ConnectionClosedError as e:
            last_error = e
            if e.code == 1012:  # Service restart - retry this
                logger.warning("🔄 Service restart detected, will retry", extra={
                    "attempt": attempt + 1,
                    "max_attempts": max_retries + 1,
                    "close_code": e.code,
                    "close_reason": e.reason
                })
                if attempt < max_retries:
                    continue  # Retry
            
            # Other connection close codes or no retries left
            logger.error("❌ Connection closed, no more retries", extra={
                "session_id": session_id,
                "question": question[:100] + "..." if len(question) > 100 else question,
                "close_code": e.code,
                "close_reason": e.reason,
                "attempt": attempt + 1
            })
            return {"answer": f"Error: Connection closed by server (code: {e.code}, reason: {e.reason})"}
            
        except Exception as e:
            # Non-connection errors - don't retry
            logger.error("❌ Evaluation test failed", exc_info=True, extra={
                "session_id": session_id,
                "question": question[:100] + "..." if len(question) > 100 else question,
                "error_type": type(e).__name__
            })
            return {"answer": f"Error: {str(e)}"}
        
        finally:
            # Always disconnect cleanly
            await client.disconnect()
            # Small delay to allow API cleanup before next test
            await asyncio.sleep(0.5)
    
    # If we get here, all retries failed
    logger.error("❌ All retry attempts failed", extra={
        "question": question[:100] + "..." if len(question) > 100 else question,
        "max_retries": max_retries,
        "final_error": str(last_error)
    })
    return {"answer": f"Connection failed after {max_retries + 1} attempts: {str(last_error)}"}


def target(inputs: Dict[str, Any]) -> Dict[str, str]:
    """
    Target function for LangSmith evaluation.
    Wraps the async integration test for synchronous evaluation.
    """
    try:
        result = asyncio.run(run_evaluation_test(inputs))
        
        # Add small delay between tests to avoid overwhelming the system
        delay_seconds = 1.5
        logger.debug("⏳ Adding delay between tests", extra={
            "delay_seconds": delay_seconds
        })
        time.sleep(delay_seconds)
        
        return result
    except Exception as e:
        logger.error("❌ Target function error", exc_info=True, extra={
            "error_type": type(e).__name__,
            "inputs": str(inputs)[:200] + "..." if len(str(inputs)) > 200 else str(inputs)
        })
        return {"answer": f"Target function error: {str(e)}"}


def main():
    """
    Main evaluation function.
    
    Evaluation Flow:
    For each example in the dataset:
    1. Open websocket and send query to API
    2. Wait to receive the full response from the API  
    3. Evaluate if the response matches expected answer
    4. Continue with next example
    """
    # Set correlation ID for evaluation session tracing
    correlation_id = set_correlation_id()
    
    logger.info("🚀 Starting AI Agent Accuracy Evaluation", extra={
        "dataset": DATASET_NAME,
        "websocket_endpoint": WEBSOCKET_ENDPOINT,
        "network": NETWORK,
        "max_response_time": MAX_RESPONSE_TIME,
        "per_message_timeout": PER_MESSAGE_TIMEOUT,
        "experiment_prefix": EXPERIMENT_PREFIX,
        "evaluation_flow": "1. Open websocket → 2. Send query → 3. Wait for response → 4. Evaluate accuracy"
    })
    
    print("🧪 AI Agent Accuracy Evaluation")
    print(f"📊 Dataset: {DATASET_NAME}")
    print(f"🎯 Flow: Open WebSocket → Send Query → Wait for Response → Evaluate Accuracy")
    print(f"🔗 Endpoint: {WEBSOCKET_ENDPOINT}")
    print(f"🌐 Network: {NETWORK}")
    print(f"⏰ Timeout: {MAX_RESPONSE_TIME}s total, {PER_MESSAGE_TIMEOUT}s per message\n")
    
    try:
        # Run the evaluation with simple flow
        print("🚀 Starting evaluation...")
        logger.info("Starting LangSmith evaluation", extra={
            "correlation_id": correlation_id,
            "max_concurrency": 1,
            "test_flow": "sequential"
        })
        
        experiment_results = client.evaluate(
            target,
            data=DATASET_NAME,
            evaluators=[
                correctness_evaluator(),
            ],
            experiment_prefix=EXPERIMENT_PREFIX,
            max_concurrency=1,
            num_repetitions=1,
        )
        
        logger.info("✅ Evaluation completed successfully", extra={
            "experiment_results": str(experiment_results)
        })
        
        print(f"\n✅ Evaluation completed!")
        print(f"📊 Results: {experiment_results}")
        
    except Exception as e:
        logger.error("❌ Evaluation failed", exc_info=True, extra={
            "websocket_endpoint": WEBSOCKET_ENDPOINT,
            "error_type": type(e).__name__
        })
        
        if "Connection" in str(e) or "WebSocket" in str(e):
            print(f"❌ Cannot connect to AI agent at {WEBSOCKET_ENDPOINT}")
            print("💡 Make sure your backend is running:")
            print("   docker compose up  # or start manually")
        else:
            print(f"❌ Evaluation failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
