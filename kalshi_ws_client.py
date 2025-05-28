import asyncio
import websockets
import json
import os
import time

KALSHI_WS_URL = "wss://api.elections.kalshi.com/trade-api/ws/v2"
SUBSCRIBE_CMD = {
    "id": 1,
    "cmd": "subscribe",
    "params": {
        "channels": ["orderbook_delta"],
        "market_ticker": "kxpresromania24"
    }
}
SUBSCRIBE_CONFIRM_TIMEOUT = 10  # seconds
RECONNECT_DELAY = 5  # seconds

async def kalshi_ws_client(api_key, subscribe_cmd):
    

    while True:
        try:
            headers = {"Authorization": f"Bearer {api_key}"}
            async with websockets.connect(
                KALSHI_WS_URL,
                ping_interval=10,
                ping_timeout=10
            ) as ws:
                print("Connected to Kalshi WebSocket API.")
                await ws.send(json.dumps(subscribe_cmd))
                print(f"Sent subscription: {json.dumps(subscribe_cmd)}")

                # Wait for confirmation
                confirmed = False
                confirm_deadline = time.time() + SUBSCRIBE_CONFIRM_TIMEOUT
                sid_set = set()
                while not confirmed and time.time() < confirm_deadline:
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=SUBSCRIBE_CONFIRM_TIMEOUT)
                        data = json.loads(msg)
                        print("Received:", json.dumps(data, indent=2))
                        if data.get("type") == "subscribed":
                            sid_set.add(data["msg"]["sid"])
                            if len(sid_set) == len(subscribe_cmd["params"]["channels"]):
                                confirmed = True
                                print("All channels subscribed.")
                        elif data.get("type") == "error":
                            print("Subscription error, retrying...")
                            break
                    except asyncio.TimeoutError:
                        print("Subscribe confirmation timeout. Reconnecting...")
                        break
                if not confirmed:
                    print("Did not receive all confirmations. Reconnecting...")
                    continue

                # Main message loop
                while True:
                    try:
                        msg = await ws.recv()
                        if msg == "PING":
                            await ws.send("PONG")
                            continue
                        data = json.loads(msg)
                        print("Received:", json.dumps(data, indent=2))
                        # Handle server-forced unsubscription
                        if data.get("type") == "unsubscribed":
                            print("Server forced unsubscription. Resubscribing...")
                            await ws.send(json.dumps(subscribe_cmd))
                        # Handle error
                        if data.get("type") == "error":
                            print("Error received. Attempting to resubscribe...")
                            await ws.send(json.dumps(subscribe_cmd))
                    except websockets.exceptions.ConnectionClosed:
                        print("Connection closed. Reconnecting in a few seconds...")
                        break
                    except Exception as e:
                        print(f"Error: {e}. Reconnecting...")
                        break
        except Exception as e:
            print(f"WebSocket connection error: {e}. Retrying in {RECONNECT_DELAY} seconds...")
        await asyncio.sleep(RECONNECT_DELAY)

if __name__ == "__main__":
    api_key = os.getenv("KALSHI_API_KEY") or input("Enter your Kalshi API key: ")
    asyncio.run(kalshi_ws_client(api_key, SUBSCRIBE_CMD)) 