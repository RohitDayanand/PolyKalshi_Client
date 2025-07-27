"""
Test atomic disconnect operations to verify race condition prevention.

Tests the atomic swap implementations in both Kalshi and Polymarket message processors.
"""
import asyncio
import sys
import os
from unittest.mock import MagicMock, patch

# Add the parent directory to the path to allow imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

def test_kalshi_atomic_disconnect():
    """Test Kalshi processor atomic disconnect prevents race conditions."""
    from backend.master_manager.kalshi_client.message_processor import KalshiMessageProcessor
    
    # Create processor with mock event bus
    processor = KalshiMessageProcessor(event_bus=MagicMock())
    
    # Add initial state
    ticker = "TEST-MARKET"
    market_id = f"kalshi_{ticker}"
    
    processor.orderbooks[ticker] = {"test": "orderbook_data"}
    processor.ticker_states[ticker] = {"test": "ticker_data"}
    
    # Verify initial state
    assert ticker in processor.orderbooks
    assert ticker in processor.ticker_states
    
    # Test atomic removal
    result = asyncio.run(processor.handle_market_removed_event(ticker, market_id))
    
    # Verify successful removal
    assert result is True
    assert ticker not in processor.orderbooks
    assert ticker not in processor.ticker_states

def test_polymarket_atomic_disconnect():
    """Test Polymarket processor atomic disconnect prevents race conditions."""
    from backend.master_manager.polymarket_client.polymarket_message_processor import PolymarketMessageProcessor
    
    # Create processor
    processor = PolymarketMessageProcessor()
    
    # Add initial state
    token_ids = ["123456789", "987654321"]
    market_id = f"polymarket_{','.join(token_ids)}"
    
    for token_id in token_ids:
        processor.orderbooks[token_id] = {"test": f"orderbook_data_{token_id}"}
        processor.token_map[token_id] = {"test": f"token_data_{token_id}"}
    
    # Verify initial state
    for token_id in token_ids:
        assert token_id in processor.orderbooks
        assert token_id in processor.token_map
    
    # Test atomic removal
    result = asyncio.run(processor.handle_tokens_removed_event(token_ids, market_id))
    
    # Verify successful removal
    assert result is True
    for token_id in token_ids:
        assert token_id not in processor.orderbooks
        assert token_id not in processor.token_map

def test_atomic_operation_failure_rollback():
    """Test that atomic operations don't partially update state on failure."""
    from backend.master_manager.polymarket_client.polymarket_message_processor import PolymarketMessageProcessor
    
    processor = PolymarketMessageProcessor()
    
    # Add initial state
    token_ids = ["valid_token", "invalid_token"]
    processor.orderbooks["valid_token"] = {"test": "data"}
    
    # Mock deepcopy to fail and test rollback
    with patch('backend.master_manager.polymarket_client.polymarket_message_processor.copy.deepcopy', side_effect=Exception("Mock failure")):
        result = processor.remove_tokens(token_ids)
        
        # Operation should fail gracefully
        assert result is False
        # Original state should remain unchanged
        assert "valid_token" in processor.orderbooks

def test_concurrent_disconnect_safety():
    """Test that concurrent disconnects don't cause race conditions."""
    from backend.master_manager.kalshi_client.message_processor import KalshiMessageProcessor
    
    processor = KalshiMessageProcessor(event_bus=MagicMock())
    
    # Add state for multiple markets
    tickers = ["MARKET-1", "MARKET-2", "MARKET-3"]
    for ticker in tickers:
        processor.orderbooks[ticker] = {"test": f"data_{ticker}"}
        processor.ticker_states[ticker] = {"test": f"state_{ticker}"}
    
    async def concurrent_removal():
        """Simulate concurrent removal attempts."""
        tasks = []
        for ticker in tickers:
            task = processor.handle_market_removed_event(ticker, f"kalshi_{ticker}")
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return results
    
    # Execute concurrent removals
    results = asyncio.run(concurrent_removal())
    
    # All operations should succeed
    assert all(r is True for r in results)
    
    # All state should be cleaned up
    for ticker in tickers:
        assert ticker not in processor.orderbooks
        assert ticker not in processor.ticker_states

if __name__ == "__main__":
    # Run tests individually for debugging
    test_kalshi_atomic_disconnect()
    test_polymarket_atomic_disconnect()
    test_atomic_operation_failure_rollback()
    test_concurrent_disconnect_safety()
    print("All atomic disconnect tests passed!")