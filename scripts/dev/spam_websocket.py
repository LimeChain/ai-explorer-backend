#!/usr/bin/env python3
"""
Script to spam the WebSocket endpoint and test rate limiting.
This script will send multiple requests rapidly to trigger rate limiting.
"""
import asyncio
import os
import websockets
import json
import time
import sys
from typing import List, Dict, Any

# Configuration  
BASE_URL = os.getenv("API_BASE_URL", "ws://localhost:8000")
MAX_REQUESTS = 10  # Number of requests to send
DELAY_BETWEEN_REQUESTS = 0.1  # Delay in seconds between requests
TEST_MESSAGE = {
    "messages": [
        {
            "role": "user",
            "content": "What is Hedera?"
        }
    ],
    "account_id": "test-account"
}


async def send_single_request(session_id: str, request_num: int) -> Dict[str, Any]:
    """Send a single WebSocket request and return the result."""
    url = f"{BASE_URL}/api/v1/chat/ws/{session_id}"
    
    try:
        async with websockets.connect(url) as websocket:
            # Send the test message
            await websocket.send(json.dumps(TEST_MESSAGE))
            
            # Collect all responses
            responses = []
            start_time = time.time()
            
            try:
                # Read the first response to check for rate limiting
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                response_data = json.loads(response)
                responses.append(response_data)
                
                # Check if we got an error (rate limit or other)
                if "error" in response_data:
                    return {
                        "request_num": request_num,
                        "success": False,
                        "error": response_data["error"],
                        "time_taken": time.time() - start_time,
                        "responses": responses
                    }
                
                # If no immediate error, continue reading until completion or timeout
                while True:
                    try:
                        response = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                        response_data = json.loads(response)
                        responses.append(response_data)
                        
                        # Check if we got completion
                        if response_data.get("complete"):
                            return {
                                "request_num": request_num,
                                "success": True,
                                "time_taken": time.time() - start_time,
                                "responses": responses
                            }
                    except asyncio.TimeoutError:
                        # Assume success if we got some responses and no errors
                        return {
                            "request_num": request_num,
                            "success": True,
                            "time_taken": time.time() - start_time,
                            "responses": responses
                        }
                        
            except asyncio.TimeoutError:
                return {
                    "request_num": request_num,
                    "success": False,
                    "error": "Timeout waiting for initial response",
                    "time_taken": time.time() - start_time,
                    "responses": responses
                }
                
    except Exception as e:
        return {
            "request_num": request_num,
            "success": False,
            "error": f"Connection error: {str(e)}",
            "time_taken": 0,
            "responses": []
        }


async def spam_websocket_sequential():
    """Send requests sequentially to test rate limiting."""
    print(f"🚀 Starting sequential WebSocket spam test...")
    print(f"📊 Sending {MAX_REQUESTS} requests with {DELAY_BETWEEN_REQUESTS}s delay")
    print(f"🎯 Target: {BASE_URL}/api/v1/chat/ws/")
    print("-" * 60)
    
    results = []
    session_id = f"spam-test-{int(time.time())}"
    
    for i in range(MAX_REQUESTS):
        print(f"📤 Sending request {i+1}/{MAX_REQUESTS}...")
        
        result = await send_single_request(session_id, i+1)
        results.append(result)
        
        # Print immediate result
        if result["success"]:
            print(f"✅ Request {i+1}: SUCCESS ({result['time_taken']:.2f}s)")
        else:
            print(f"❌ Request {i+1}: FAILED - {result['error']}")
            if "rate limit" in result["error"].lower():
                print(f"🎯 RATE LIMIT HIT on request {i+1}!")
        
        # Delay before next request
        if i < MAX_REQUESTS - 1:
            await asyncio.sleep(DELAY_BETWEEN_REQUESTS)
    
    return results


async def spam_websocket_concurrent():
    """Send requests concurrently to test rate limiting."""
    print(f"🚀 Starting concurrent WebSocket spam test...")
    print(f"📊 Sending {MAX_REQUESTS} requests concurrently")
    print(f"🎯 Target: {BASE_URL}/api/v1/chat/ws/")
    print("-" * 60)
    
    # Create tasks for concurrent execution
    tasks = []
    base_session_id = f"spam-concurrent-{int(time.time())}"
    
    for i in range(MAX_REQUESTS):
        # Use different session IDs to test IP-based rate limiting
        session_id = f"{base_session_id}-{i}"
        task = send_single_request(session_id, i+1)
        tasks.append(task)
    
    # Execute all requests concurrently
    results = await asyncio.gather(*tasks)
    
    # Print results
    for result in results:
        if result["success"]:
            print(f"✅ Request {result['request_num']}: SUCCESS ({result['time_taken']:.2f}s)")
        else:
            print(f"❌ Request {result['request_num']}: FAILED - {result['error']}")
            if "rate limit" in result["error"].lower():
                print(f"🎯 RATE LIMIT HIT on request {result['request_num']}!")
    
    return results


def print_summary(results: List[Dict[str, Any]]):
    """Print a summary of the test results."""
    print("\n" + "=" * 60)
    print("📈 TEST SUMMARY")
    print("=" * 60)
    
    successful = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]
    rate_limited = [r for r in failed if "rate limit" in r.get("error", "").lower()]
    
    print(f"Total requests: {len(results)}")
    print(f"✅ Successful: {len(successful)}")
    print(f"❌ Failed: {len(failed)}")
    print(f"🚫 Rate limited: {len(rate_limited)}")
    
    if successful:
        avg_time = sum(r["time_taken"] for r in successful) / len(successful)
        print(f"⏱️  Average response time: {avg_time:.2f}s")
    
    if rate_limited:
        print(f"\n🎯 Rate limit was triggered after {len(successful)} successful requests")
        print("Rate limited requests:")
        for r in rate_limited:
            print(f"  - Request {r['request_num']}: {r['error']}")


async def main():
    """Main function to run the spam test."""
    if len(sys.argv) > 1 and sys.argv[1] == "concurrent":
        results = await spam_websocket_concurrent()
    else:
        results = await spam_websocket_sequential()
    
    print_summary(results)
    
    print(f"\n💡 To check Redis counters, run: python scripts/check_redis_counters.py")


if __name__ == "__main__":
    print("🔥 WebSocket Rate Limit Spam Test")
    print("Usage:")
    print("  python scripts/spam_websocket.py          # Sequential requests")
    print("  python scripts/spam_websocket.py concurrent # Concurrent requests")
    print()
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⛔ Test interrupted by user")
    except Exception as e:
        print(f"\n💥 Error: {e}")
