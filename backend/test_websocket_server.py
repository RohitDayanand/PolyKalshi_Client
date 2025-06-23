"""
Test script for WebSocket ticker streaming server
"""
import asyncio
import json
import websockets
import time
from typing import Dict, Any
from backend.ticker_stream_integration import publish_polymarket_update, publish_kalshi_update, start_ticker_publisher

async def test_websocket_client():
    """Test WebSocket client that connects and subscribes to ticker updates"""
    uri = "ws://localhost:8000/ws/ticker"
    
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected to WebSocket server")
            
            # Test 1: Subscribe to all Polymarket updates
            subscribe_msg = {
                "type": "subscribe_platform",
                "platform": "polymarket"
            }
            await websocket.send(json.dumps(subscribe_msg))
            
            # Wait for confirmation
            response = await websocket.recv()
            print(f"Subscription response: {response}")
            
            # Test 2: Subscribe to specific market
            subscribe_market_msg = {
                "type": "subscribe_market",
                "market_id": "test_market_123"
            }
            await websocket.send(json.dumps(subscribe_market_msg))
            
            # Wait for confirmation
            response = await websocket.recv()
            print(f"Market subscription response: {response}")
            
            # Listen for ticker updates for 30 seconds
            print("Listening for ticker updates...")
            timeout = time.time() + 30
            
            while time.time() < timeout:
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                    data = json.loads(message)
                    print(f"Received ticker update: {data}")
                except asyncio.TimeoutError:
                    continue
                except json.JSONDecodeError as e:
                    print(f"Failed to decode message: {e}")
    
    except ConnectionRefusedError:
        print("Could not connect to WebSocket server. Make sure it's running on localhost:8000")
    except Exception as e:
        print(f"WebSocket client error: {e}")

async def simulate_ticker_data():
    """Simulate ticker data being published"""
    print("Starting ticker data simulation...")
    
    # Start the ticker publisher
    start_ticker_publisher()
    
    await asyncio.sleep(2)  # Give time for client to connect
    
    # Simulate Polymarket ticker updates
    for i in range(10):
        polymarket_data = {
            "yes": {"bid": 0.45 + i * 0.01, "ask": 0.47 + i * 0.01, "volume": 1000 + i * 100},
            "no": {"bid": 0.53 - i * 0.01, "ask": 0.55 - i * 0.01, "volume": 800 + i * 50}
        }
        
        publish_polymarket_update(f"polymarket_test_{i}", polymarket_data)
        print(f"Published Polymarket update {i}")
        
        await asyncio.sleep(2)
    
    # Simulate Kalshi ticker updates
    for i in range(5):
        kalshi_data = {
            "yes": {"bid": 0.35 + i * 0.02, "ask": 0.37 + i * 0.02, "volume": 500 + i * 75},
            "no": {"bid": 0.63 - i * 0.02, "ask": 0.65 - i * 0.02, "volume": 400 + i * 25}
        }
        
        publish_kalshi_update(f"kalshi_test_{i}", kalshi_data)
        print(f"Published Kalshi update {i}")
        
        await asyncio.sleep(2)
    
    # Test specific market that client subscribed to
    special_market_data = {
        "yes": {"bid": 0.75, "ask": 0.77, "volume": 5000},
        "no": {"bid": 0.23, "ask": 0.25, "volume": 3000}
    }
    
    publish_polymarket_update("test_market_123", special_market_data)
    print("Published update for test_market_123")

async def test_health_endpoint():
    """Test the health check endpoint"""
    import aiohttp
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get('http://localhost:8000/health') as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"Health check passed: {data}")
                else:
                    print(f"Health check failed with status: {response.status}")
    except Exception as e:
        print(f"Health check error: {e}")

async def run_full_test():
    """Run complete test suite"""
    print("=== WebSocket Ticker Server Test ===")
    
    # Start the data simulation in background
    simulation_task = asyncio.create_task(simulate_ticker_data())
    
    # Wait a moment for server to be ready
    await asyncio.sleep(1)
    
    # Test health endpoint
    await test_health_endpoint()
    
    # Run client test
    client_task = asyncio.create_task(test_websocket_client())
    
    # Wait for both tasks
    await asyncio.gather(simulation_task, client_task, return_exceptions=True)
    
    print("Test completed")

if __name__ == "__main__":
    print("Starting WebSocket server test...")
    print("Make sure to run 'python backend/websocket_server.py' in another terminal first!")
    asyncio.run(run_full_test())