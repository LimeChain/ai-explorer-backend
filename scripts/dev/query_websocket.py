import asyncio
import json
import ssl
import websockets

SESSION_ID = "123456789"
API_HOST = "34.8.191.177"
URI = f"wss://{API_HOST}/api/v1/chat/ws/{SESSION_ID}"

async def send_query(query: str):
    try:
        # Create SSL context that doesn't verify certificates (for self-signed cert)
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        async with websockets.connect(URI, ssl=ssl_context) as websocket:
            query = {"query": query}
            await websocket.send(json.dumps(query))
            print(f"Sent: {query}")
            
            async for message in websocket:
                try:
                    response = json.loads(message)
                    print(f"Response: {response}")
                    
                    # Handle different response formats
                    if "token" in response:
                        print(response["token"] + " ", end="", flush=True)
                    elif "content" in response:
                        print(response["content"] + " ", end="", flush=True)
                    else:
                        print(f"Raw response: {response}")
                        
                except json.JSONDecodeError:
                    print(f"Non-JSON response: {message}")
                
    except websockets.exceptions.ConnectionClosed:
        print("Connection closed")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(
        send_query("Tell me the last 10 tokens of 0.0.6105114"),
    )