"""
Test the Platform Manager add/remove token functionality
"""

import asyncio
import sys
import os
from unittest.mock import AsyncMock, MagicMock

# Add parent directories to path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, backend_path)

from master_manager.events.event_bus import EventBus
from master_manager.platforms.polymarket_platform_manager import PolymarketPlatformManager
from master_manager.polymarket_client.polymarket_client import PolymarketClient


async def test_add_remove_tokens():
    """Test add and remove tokens with mocked client."""
    print("=== Testing Platform Manager Add/Remove Tokens ===")
    
    # Create event bus and platform manager
    event_bus = EventBus()
    platform = PolymarketPlatformManager(event_bus)
    
    # Create mock client
    mock_client = AsyncMock(spec=PolymarketClient)
    mock_client.token_id = ["token1"]
    mock_client.is_connected = True
    mock_client.add_ticker = AsyncMock(return_value=True)
    mock_client.remove_ticker = AsyncMock(return_value=True)
    mock_client.subscribe = AsyncMock(return_value=True)
    
    # Add mock client to platform
    market_id = "test_market"
    platform.clients[market_id] = mock_client
    
    # Capture events
    captured_events = []
    
    async def event_capture(event_data):
        captured_events.append(event_data)
    
    event_bus.subscribe("frontend.notify.*", event_capture)
    event_bus.subscribe("polymarket.tokens_*", event_capture)
    
    # Test add tokens
    print("\n--- Testing Add Tokens ---")
    result = await platform.add_tokens_to_market(market_id, ["token2", "token3"])
    
    print(f"Add result: {result}")
    assert result["success"] is True
    assert "tokens" in result
    assert result["tokens"] == ["token2", "token3"]
    
    # Verify client method was called
    mock_client.add_ticker.assert_called_once_with(["token2", "token3"])
    
    # Test remove tokens
    print("\n--- Testing Remove Tokens ---")
    mock_client.token_id = ["token1", "token2"]  # Update mock state
    result = await platform.remove_tokens_from_market(market_id, ["token2"])
    
    print(f"Remove result: {result}")
    assert result["success"] is True
    assert result["tokens"] == ["token2"]
    
    # Verify client method was called
    mock_client.remove_ticker.assert_called_once_with(["token2"])
    
    # Test validation failures
    print("\n--- Testing Validation Failures ---")
    
    # Empty tokens
    result = await platform.add_tokens_to_market(market_id, [])
    assert result["success"] is False
    assert "empty" in result["error"]
    
    # Non-existent market
    result = await platform.add_tokens_to_market("fake_market", ["token1"])
    assert result["success"] is False
    assert "not found" in result["error"]
    
    # Disconnected client
    mock_client.is_connected = False
    result = await platform.add_tokens_to_market(market_id, ["token1"])
    assert result["success"] is False
    assert "not connected" in result["error"]
    
    print("\n--- Testing Rollback ---")
    # Reset client state
    mock_client.is_connected = True
    mock_client.token_id = ["original_token"]
    
    # Make add_ticker fail
    mock_client.add_ticker = AsyncMock(side_effect=Exception("WebSocket error"))
    
    result = await platform.add_tokens_to_market(market_id, ["new_token"])
    assert result["success"] is False
    
    # Verify rollback was attempted
    mock_client.subscribe.assert_called()
    
    print("✅ All platform manager tests passed!")
    
    # Print captured events for debugging
    print(f"\nCaptured {len(captured_events)} events:")
    for i, event in enumerate(captured_events):
        print(f"  {i+1}: {event.get('type', 'unknown')} - {event}")


async def test_get_market_info():
    """Test get market info functionality."""
    print("\n=== Testing Get Market Info ===")
    
    event_bus = EventBus()
    platform = PolymarketPlatformManager(event_bus)
    
    # Test non-existent market
    info = platform.get_market_token_info("fake_market")
    assert "error" in info
    
    # Add mock client
    mock_client = AsyncMock(spec=PolymarketClient)
    mock_client.token_id = ["token1", "token2"]
    mock_client.is_connected = True
    
    market_id = "test_market"
    platform.clients[market_id] = mock_client
    platform.polymarket_yes_id = "token1"
    platform.polymarket_no_id = "token2"
    
    # Test existing market
    info = platform.get_market_token_info(market_id)
    print(f"Market info: {info}")
    
    assert info["market_id"] == market_id
    assert info["tokens"] == ["token1", "token2"]
    assert info["count"] == 2
    assert info["connected"] is True
    assert info["yes_id"] == "token1"
    assert info["no_id"] == "token2"
    
    print("✅ Market info test passed!")


async def main():
    """Run all tests."""
    await test_add_remove_tokens()
    await test_get_market_info()
    print("\n🎉 All tests completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())