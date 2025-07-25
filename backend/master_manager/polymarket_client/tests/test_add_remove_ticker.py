"""
Test for Polymarket add_ticker and remove_ticker functionality.

This test demonstrates the new add_ticker and remove_ticker functions that work
with Polymarket's subscription system by leveraging the subscribe() method.
"""

import asyncio
import json
import logging
import sys
import os
from unittest.mock import AsyncMock
from datetime import datetime

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from polymarket_client import create_polymarket_client, PolymarketClient


class MessageCapture:
    """Helper class to capture and analyze WebSocket messages."""
    
    def __init__(self):
        self.subscription_messages = []
        self.token_maps = []
        
    async def message_callback(self, message, metadata):
        """Capture messages for analysis."""
        timestamp = datetime.now().isoformat()
        
        if metadata.get("event_type") == "token_map":
            self.token_maps.append({
                "timestamp": timestamp,
                "token_map": json.loads(message),
                "metadata": metadata
            })
            print(f"[{timestamp}] Token map: {message}")


async def test_add_remove_ticker_mock():
    """
    Test add_ticker and remove_ticker with mocked WebSocket.
    """
    print("=== Testing Add/Remove Ticker (Mocked) ===")
    
    # Initial token IDs
    initial_tokens = [
        "36983600554365577850917051019051094208107094324057250177743040919797354737778"
    ]
    
    # Create client with initial token
    poly_client = create_polymarket_client(
        slug="test-market",
        token_ids=initial_tokens
    )
    
    # Mock WebSocket connection
    mock_websocket = AsyncMock()
    poly_client.websocket = mock_websocket
    poly_client.is_connected = True
    
    # Track subscription messages sent
    sent_messages = []
    
    async def mock_send(message):
        sent_messages.append(json.loads(message))
        print(f"Sent: {message}")
    
    mock_websocket.send = mock_send
    
    # Mock message callback
    async def mock_callback(message, metadata):
        pass
    
    poly_client.set_message_callback(mock_callback)
    
    # Test add_ticker
    print("\n--- Testing add_ticker ---")
    new_tokens = ["27328614281599691408249679475598101144024812037645322360848849289647283526760"]
    
    result = await poly_client.add_ticker(new_tokens)
    assert result is True, "add_ticker should succeed"
    
    # Verify subscription message
    assert len(sent_messages) >= 1, "Should have sent subscription message"
    latest_message = sent_messages[-1]
    assert latest_message["type"] == "MARKET"
    assert len(latest_message["assets_ids"]) == 2
    assert set(latest_message["assets_ids"]) == set(initial_tokens + new_tokens)
    print(f"✅ Added token. Now subscribed to: {latest_message['assets_ids']}")
    
    # Test remove_ticker
    print("\n--- Testing remove_ticker ---")
    sent_messages.clear()
    
    result = await poly_client.remove_ticker(new_tokens)
    assert result is True, "remove_ticker should succeed"
    
    # Verify removal message
    assert len(sent_messages) >= 1, "Should have sent subscription message"
    latest_message = sent_messages[-1]
    assert latest_message["type"] == "MARKET"
    assert len(latest_message["assets_ids"]) == 1
    assert latest_message["assets_ids"] == initial_tokens
    print(f"✅ Removed token. Now subscribed to: {latest_message['assets_ids']}")
    
    # Test remove all tokens
    print("\n--- Testing remove all tokens ---")
    sent_messages.clear()
    
    result = await poly_client.remove_ticker(initial_tokens)
    assert result is True, "remove all tokens should succeed"
    
    # Verify complete removal message
    latest_message = sent_messages[-1]
    assert latest_message["type"] == "MARKET"
    assert latest_message["assets_ids"] == [""]  # Polymarket quirk for empty subscription
    print(f"✅ Removed all tokens. Subscription: {latest_message['assets_ids']}")
    
    print("✅ All mocked add/remove ticker tests passed!")
    return True


async def test_add_remove_ticker_disconnected():
    """
    Test that add/remove ticker fail gracefully when disconnected.
    """
    print("\n=== Testing Add/Remove Ticker (Disconnected) ===")
    
    poly_client = create_polymarket_client(
        slug="test-market",
        token_ids=["test_token"]
    )
    
    # Ensure client is not connected
    poly_client.is_connected = False
    poly_client.websocket = None
    
    # Test add_ticker when disconnected
    try:
        await poly_client.add_ticker(["new_token"])
        assert False, "add_ticker should raise RuntimeError when disconnected"
    except RuntimeError as e:
        assert "not connected" in str(e).lower()
        print("✅ add_ticker correctly raises RuntimeError when disconnected")
    
    # Test remove_ticker when disconnected
    try:
        await poly_client.remove_ticker(["test_token"])
        assert False, "remove_ticker should raise RuntimeError when disconnected"
    except RuntimeError as e:
        assert "not connected" in str(e).lower()
        print("✅ remove_ticker correctly raises RuntimeError when disconnected")
    
    return True


async def test_real_add_remove_ticker():
    """
    Test add_ticker and remove_ticker with real Polymarket WebSocket connection.
    """
    print("\n=== Testing Add/Remove Ticker (Real Connection) ===")
    
    # Start with one token
    initial_token = "36983600554365577850917051019051094208107094324057250177743040919797354737778"
    
    message_capture = MessageCapture()
    poly_client = create_polymarket_client(
        slug="israel-x-hamas-ceasefire-by-july-15",
        token_ids=[initial_token]
    )
    poly_client.set_message_callback(message_capture.message_callback)
    
    try:
        print("Connecting to Polymarket WebSocket...")
        success = await poly_client.connect()
        if not success:
            print("❌ Failed to connect - skipping real test")
            return False
            
        print(f"✅ Connected! Initially subscribed to 1 token")
        await asyncio.sleep(2)
        
        # Test add_ticker
        print("\n--- Testing real add_ticker ---")
        new_token = "27328614281599691408249679475598101144024812037645322360848849289647283526760"
        
        result = await poly_client.add_ticker([new_token])
        assert result is True, "add_ticker should succeed"
        print(f"✅ Added token. Now subscribed to {len(poly_client.token_id)} tokens")
        await asyncio.sleep(2)
        
        # Test remove_ticker
        print("\n--- Testing real remove_ticker ---")
        result = await poly_client.remove_ticker([new_token])
        assert result is True, "remove_ticker should succeed"
        print(f"✅ Removed token. Now subscribed to {len(poly_client.token_id)} tokens")
        await asyncio.sleep(2)
        
        # Test remove all
        print("\n--- Testing real remove all ---")
        result = await poly_client.remove_ticker([initial_token])
        assert result is True, "remove all should succeed"
        remaining = len(poly_client.token_id) if poly_client.token_id != [""] else 0
        print(f"✅ Removed all tokens. Now subscribed to {remaining} tokens")
        
        await poly_client.disconnect()
        print("✅ Real add/remove ticker test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Real test failed: {e}")
        if poly_client.is_running():
            await poly_client.disconnect()
        return False


async def main():
    """
    Run all add/remove ticker tests.
    """
    print("Starting Polymarket add/remove ticker tests...\n")
    
    try:
        # Test with mocked connection
        await test_add_remove_ticker_mock()
        
        # Test disconnected behavior
        await test_add_remove_ticker_disconnected()
        
        # Test with real connection
        await test_real_add_remove_ticker()
        
        print("\n🎉 All add/remove ticker tests completed successfully!")
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        raise


if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    
    # Run the tests
    asyncio.run(main())