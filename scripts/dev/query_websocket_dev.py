import asyncio
import json
import websockets

SESSION_ID = "86d7f295-2ec9-41cb-9d56-18c456cd268b"
URI = f"ws://localhost:8000/api/v1/chat/ws/{SESSION_ID}"

async def send_query(query: str):
    try:
        async with websockets.connect(URI) as websocket:
            message = {
                "type": "query",
                "content": query,
                "network": "testnet"
            }
            await websocket.send(json.dumps(message))
            print(f"Sent: {message}")
            
            async for message in websocket:
                try:
                    response = json.loads(message)
                    if "token" in response:
                        print(response["token"] + " ", end="", flush=True)
                    elif "complete" in response and response["complete"]:
                        print("\n[Complete]")
                        break
                    else:
                        print(f"\n[Response: {response}]")
                except json.JSONDecodeError:
                    print(f"\n[Non-JSON: {message}]")
                
    except websockets.exceptions.ConnectionClosed:
        print("Connection closed")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(
        send_query("Tell me the last 10 tokens of 0.0.6105114"),
    )