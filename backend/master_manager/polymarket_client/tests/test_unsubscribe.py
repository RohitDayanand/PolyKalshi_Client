"""
Test for Polymarket WebSocket unsubscribing functionality.

This test demonstrates how to unsubscribe from specific token IDs by calling
subscribe() again with a reduced list of token_ids.
"""

import asyncio
import json
import logging
import sys
import os
from unittest.mock import AsyncMock, MagicMock, patch

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from polymarket_client import create_polymarket_client, PolymarketClient, PolymarketClientConfig


async def test_unsubscribe_functionality():
    """
    Test unsubscribing from Polymarket WebSocket by calling subscribe with fewer token_ids.
    """
    # Test token IDs for Israel x Hamas Ceasefire market
    initial_token_ids = [
        "36983600554365577850917051019051094208107094324057250177743040919797354737778",
        "27328614281599691408249679475598101144024812037645322360848849289647283526760"
    ]
    
    # Create client with initial token IDs
    poly_client = create_polymarket_client(
        slug="israel-x-hamas-ceasefire-by-july-15", 
        token_ids=initial_token_ids
    )
    
    # Mock WebSocket connection
    mock_websocket = AsyncMock()
    poly_client.websocket = mock_websocket
    poly_client.is_connected = True
    
    # Mock message callback to capture subscription messages
    sent_messages = []
    
    async def mock_send(message):
        sent_messages.append(json.loads(message))
    
    mock_websocket.send = mock_send
    
    # Mock message callback
    async def mock_callback(message, metadata):
        pass
    
    poly_client.set_message_callback(mock_callback)
    
    print("=== Initial Subscription Test ===")
    # Subscribe to both tokens initially
    result = await poly_client.subscribe()
    assert result is True, "Initial subscription should succeed"
    
    # Verify initial subscription message
    assert len(sent_messages) == 1, "Should have sent one subscription message"
    initial_message = sent_messages[0]
    print(f"Initial subscription message: {initial_message}")
    assert initial_message["type"] == "MARKET"
    assert len(initial_message["assets_ids"]) == 2
    assert set(initial_message["assets_ids"]) == set(initial_token_ids)
    
    print("=== Unsubscribe Test (Partial) ===")
    # Unsubscribe from one token by updating the client's token_id list
    # and calling subscribe again with fewer tokens
    reduced_token_ids = [initial_token_ids[0]]  # Keep only first token
    poly_client.token_id = reduced_token_ids
    
    # Clear sent messages to capture the unsubscribe operation
    sent_messages.clear()
    
    # Call subscribe again with reduced token list (this acts as unsubscribe)
    result = await poly_client.subscribe()
    assert result is True, "Unsubscribe operation should succeed"
    
    # Verify unsubscribe message
    assert len(sent_messages) == 1, "Should have sent one unsubscribe message"
    unsubscribe_message = sent_messages[0]
    print(f"Unsubscribe message: {unsubscribe_message}")
    assert unsubscribe_message["type"] == "MARKET"
    assert len(unsubscribe_message["assets_ids"]) == 1
    assert unsubscribe_message["assets_ids"] == reduced_token_ids
    
    print("=== Complete Unsubscribe Test ===")
    # Unsubscribe from all tokens by using empty string
    poly_client.token_id = [""]
    sent_messages.clear()
    
    result = await poly_client.subscribe()
    assert result is True, "Complete unsubscribe should succeed"
    
    # Verify complete unsubscribe message
    assert len(sent_messages) == 1, "Should have sent one complete unsubscribe message"
    complete_unsubscribe_message = sent_messages[0]
    print(f"Complete unsubscribe message: {complete_unsubscribe_message}")
    assert complete_unsubscribe_message["type"] == "MARKET"
    assert complete_unsubscribe_message["assets_ids"] == [""]
    
    print("✅ All unsubscribe tests passed!")
    return True


async def test_unsubscribe_when_disconnected():
    """
    Test that unsubscribe fails gracefully when not connected.
    """
    print("=== Disconnected Unsubscribe Test ===")
    
    poly_client = create_polymarket_client(
        slug="test-market",
        token_ids=["test_token_1", "test_token_2"]
    )
    
    # Ensure client is not connected
    poly_client.is_connected = False
    poly_client.websocket = None
    
    # Attempt to unsubscribe (by calling subscribe with fewer tokens)
    poly_client.token_id = ["test_token_1"]  # Reduce tokens
    result = await poly_client.subscribe()
    
    assert result is False, "Unsubscribe should fail when disconnected"
    print("✅ Disconnected unsubscribe test passed!")
    return True


async def main():
    """
    Run all unsubscribe tests.
    """
    print("Starting Polymarket unsubscribe tests...\n")
    
    try:
        # Test basic unsubscribe functionality
        await test_unsubscribe_functionality()
        print()
        
        # Test unsubscribe when disconnected
        await test_unsubscribe_when_disconnected()
        print()
        
        print("🎉 All tests completed successfully!")
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        raise


if __name__ == "__main__":
    # Set up logging to see debug messages
    logging.basicConfig(level=logging.INFO)
    
    # Run the tests
    asyncio.run(main())