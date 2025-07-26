"""
Simple test for add/remove ticker functionality with real Polymarket client
"""

import asyncio
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from polymarket_client import create_polymarket_client


async def test_simple_add_remove():
    """Test add/remove with real client (no platform manager)."""
    print("=== Simple Add/Remove Test ===")
    
    # Test tokens
    initial_token = "36983600554365577850917051019051094208107094324057250177743040919797354737778"
    add_token = "27328614281599691408249679475598101144024812037645322360848849289647283526760"
    
    # Create client with initial token
    client = create_polymarket_client(
        slug="test-market",
        token_ids=[initial_token]
    )
    
    # Mock the connection to avoid real WebSocket
    from unittest.mock import AsyncMock
    client.websocket = AsyncMock()
    client.is_connected = True
    
    sent_messages = []
    async def mock_send(message):
        sent_messages.append(message)
        print(f"Mock sent: {message}")
    
    client.websocket.send = mock_send
    
    async def mock_callback(message, metadata):
        pass
    
    client.set_message_callback(mock_callback)
    
    try:
        print(f"Initial tokens: {client.token_id}")
        
        # Test add_ticker
        print("\n--- Testing add_ticker ---")
        result = await client.add_ticker([add_token])
        print(f"Add result: {result}")
        print(f"New tokens: {client.token_id}")
        assert result is True
        assert len(client.token_id) == 2
        
        # Test remove_ticker  
        print("\n--- Testing remove_ticker ---")
        result = await client.remove_ticker([add_token])
        print(f"Remove result: {result}")
        print(f"Remaining tokens: {client.token_id}")
        assert result is True
        assert len(client.token_id) == 1
        
        # Test complete unsubscribe
        print("\n--- Testing complete unsubscribe ---")
        result = await client.remove_ticker([initial_token])
        print(f"Complete unsubscribe result: {result}")
        print(f"Final tokens: {client.token_id}")
        assert result is True
        assert client.token_id == [""]  # Polymarket quirk
        
        print("✅ All add/remove tests passed!")
        
        # Show messages that would have been sent
        print(f"\nMessages that would be sent to Polymarket:")
        for i, msg in enumerate(sent_messages, 1):
            print(f"  {i}: {msg}")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False


async def test_validation():
    """Test validation and error handling."""
    print("\n=== Validation Test ===")
    
    client = create_polymarket_client("test", token_ids=["token1"])
    
    # Test without connection
    try:
        await client.add_ticker(["token2"])
        assert False, "Should have failed without connection"
    except RuntimeError as e:
        print(f"✅ Correctly caught error: {e}")
    
    # Test with connection but no websocket
    client.is_connected = True
    client.websocket = None
    
    try:
        await client.add_ticker(["token2"])
        assert False, "Should have failed without websocket"
    except RuntimeError as e:
        print(f"✅ Correctly caught error: {e}")
    
    print("✅ Validation tests passed!")


async def main():
    """Run all tests."""
    success1 = await test_simple_add_remove()
    await test_validation()
    
    if success1:
        print("\n🎉 All tests completed successfully!")
        print("\nThe add/remove ticker functionality works correctly!")
        print("Key features tested:")
        print("  ✅ Adding tokens to subscription")
        print("  ✅ Removing tokens from subscription") 
        print("  ✅ Complete unsubscribe (empty string handling)")
        print("  ✅ Error handling and validation")
    else:
        print("\n❌ Some tests failed")


if __name__ == "__main__":
    asyncio.run(main())