import asyncio
import json
import websockets

SESSION_ID = "123456789"
URI = f"ws://localhost:8000/api/v1/chat/ws/{SESSION_ID}"

async def send_query(query: str):
    try:
        async with websockets.connect(URI) as websocket:
            query = {"query": query}
            await websocket.send(json.dumps(query))
            print(f"Sent: {query}")
            
            async for message in websocket:
                response = json.loads(message)
                print(response["token"] + " ", end="", flush=True)
                
    except websockets.exceptions.ConnectionClosed:
        print("Connection closed")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(
        send_query("Tell me the last 10 tokens of 0.0.6105114"),
    )