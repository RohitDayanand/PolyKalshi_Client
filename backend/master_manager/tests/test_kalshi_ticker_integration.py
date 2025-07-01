"""
Test integration of Kalshi message processor with ticker stream publishing
"""

import asyncio
import json
import sys
import os
from unittest.mock import AsyncMock, MagicMock, patch

# Add the parent directory to Python path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'kalshi_client'))

from kalshi_message_processor import KalshiMessageProcessor
from kalshi_ticker_publisher import KalshiTickerPublisher


async def test_ticker_publisher_basic():
    """Test basic ticker publisher functionality."""
    print("🔵 Testing basic ticker publisher...")
    
    processor = KalshiMessageProcessor()
    
    # Mock the publish function to track calls
    published_updates = []
    
    def mock_publish_nowait(market_id, summary_stats):
        published_updates.append({
            'market_id': market_id,
            'summary_stats': summary_stats
        })
        print(f"[MOCK] Published {market_id}: YES ${summary_stats['yes']['bid']:.2f}/${summary_stats['yes']['ask']:.2f}")
    
    async def mock_start():
        pass
    
    async def mock_stop():
        pass
    
    # Create publisher with very short interval for testing
    with patch('kalshi_ticker_publisher.publish_kalshi_update_nowait', mock_publish_nowait):
        with patch('kalshi_ticker_publisher.start_ticker_publisher', mock_start):
            with patch('kalshi_ticker_publisher.stop_ticker_publisher', mock_stop):
                
                publisher = KalshiTickerPublisher(processor, publish_interval=0.1)
                
                # Start publisher
                await publisher.start()
                
                # Add some test orderbook data
                snapshot_message = {
                    "type": "orderbook_snapshot",
                    "sid": 12345,
                    "seq": 100,
                    "bids": [{"price": "0.52", "size": "500"}],
                    "asks": [{"price": "0.54", "size": "400"}]
                }
                
                metadata = {"ticker": "KXPRESPOLAND-NT"}
                await processor.handle_message(json.dumps(snapshot_message), metadata)
                
                # Wait for a few publish cycles
                await asyncio.sleep(0.3)
                
                # Stop publisher
                await publisher.stop()
    
    # Verify publishing occurred
    assert len(published_updates) >= 2, f"Expected multiple publishes, got {len(published_updates)}"
    
    update = published_updates[0]
    assert update['market_id'] == "KXPRESPOLAND-NT"
    assert update['summary_stats']['yes']['bid'] == 0.52
    assert update['summary_stats']['yes']['ask'] == 0.54
    assert abs(update['summary_stats']['no']['bid'] - 0.46) < 0.001  # 1 - 0.54
    assert abs(update['summary_stats']['no']['ask'] - 0.48) < 0.001  # 1 - 0.52
    
    print("✓ Basic ticker publisher works correctly")


async def test_rate_limiting():
    """Test that rate limiting works correctly."""
    print("🔵 Testing rate limiting...")
    
    processor = KalshiMessageProcessor()
    published_updates = []
    
    def mock_publish_nowait(market_id, summary_stats):
        published_updates.append(market_id)
    
    async def mock_start():
        pass
    
    async def mock_stop():
        pass
    
    with patch('kalshi_ticker_publisher.publish_kalshi_update_nowait', mock_publish_nowait):
        with patch('kalshi_ticker_publisher.start_ticker_publisher', mock_start):
            with patch('kalshi_ticker_publisher.stop_ticker_publisher', mock_stop):
                
                publisher = KalshiTickerPublisher(processor, publish_interval=1.0)
                
                # Add orderbook data
                snapshot_message = {
                    "type": "orderbook_snapshot",
                    "sid": 12345,
                    "seq": 100,
                    "bids": [{"price": "0.50", "size": "100"}],
                    "asks": [{"price": "0.55", "size": "100"}]
                }
                
                metadata = {"ticker": "TEST-TICKER"}
                await processor.handle_message(json.dumps(snapshot_message), metadata)
                
                # Start publisher and test rapid calls
                await publisher.start()
                
                # Wait less than publish interval
                await asyncio.sleep(0.1)
                
                # Should have published once
                initial_count = len(published_updates)
                
                # Wait another short time (still within interval)
                await asyncio.sleep(0.1)
                
                # Should not have published again due to rate limiting
                assert len(published_updates) == initial_count, "Rate limiting failed"
                
                await publisher.stop()
    
    print("✓ Rate limiting works correctly")


async def test_multiple_markets():
    """Test publishing multiple markets."""
    print("🔵 Testing multiple markets...")
    
    processor = KalshiMessageProcessor()
    published_updates = {}
    
    def mock_publish_nowait(market_id, summary_stats):
        published_updates[market_id] = summary_stats
    
    async def mock_start():
        pass
    
    async def mock_stop():
        pass
    
    with patch('kalshi_ticker_publisher.publish_kalshi_update_nowait', mock_publish_nowait):
        with patch('kalshi_ticker_publisher.start_ticker_publisher', mock_start):
            with patch('kalshi_ticker_publisher.stop_ticker_publisher', mock_stop):
                
                publisher = KalshiTickerPublisher(processor, publish_interval=0.1)
                
                # Add multiple markets
                markets = [
                    {"sid": 11111, "ticker": "MARKET-A", "bid": "0.45", "ask": "0.47"},
                    {"sid": 22222, "ticker": "MARKET-B", "bid": "0.60", "ask": "0.65"},
                    {"sid": 33333, "ticker": "MARKET-C", "bid": "0.30", "ask": "0.35"}
                ]
                
                for market in markets:
                    snapshot_message = {
                        "type": "orderbook_snapshot",
                        "sid": market["sid"],
                        "seq": 100,
                        "bids": [{"price": market["bid"], "size": "100"}],
                        "asks": [{"price": market["ask"], "size": "100"}]
                    }
                    
                    metadata = {"ticker": market["ticker"]}
                    await processor.handle_message(json.dumps(snapshot_message), metadata)
                
                # Start publisher and let it run
                await publisher.start()
                await asyncio.sleep(0.3)
                await publisher.stop()
    
    # Verify all markets were published
    assert len(published_updates) == 3, f"Expected 3 markets, got {len(published_updates)}"
    
    for market in markets:
        ticker = market["ticker"]
        assert ticker in published_updates, f"Market {ticker} not published"
        
        stats = published_updates[ticker]
        expected_bid = float(market["bid"])
        expected_ask = float(market["ask"])
        
        assert stats["yes"]["bid"] == expected_bid
        assert stats["yes"]["ask"] == expected_ask
    
    print("✓ Multiple markets publishing works correctly")


async def test_data_validation():
    """Test data validation and error handling."""
    print("🔵 Testing data validation...")
    
    processor = KalshiMessageProcessor()
    published_updates = []
    
    def mock_publish_nowait(market_id, summary_stats):
        published_updates.append(market_id)
    
    async def mock_start():
        pass
    
    async def mock_stop():
        pass
    
    with patch('kalshi_ticker_publisher.publish_kalshi_update_nowait', mock_publish_nowait):
        with patch('kalshi_ticker_publisher.start_ticker_publisher', mock_start):
            with patch('kalshi_ticker_publisher.stop_ticker_publisher', mock_stop):
                
                publisher = KalshiTickerPublisher(processor, publish_interval=0.1)
                
                # Create orderbook with missing ticker (should be skipped)
                snapshot_message = {
                    "type": "orderbook_snapshot",
                    "sid": 99999,
                    "seq": 100,
                    "bids": [{"price": "0.50", "size": "100"}],
                    "asks": [{"price": "0.55", "size": "100"}]
                }
                
                # No ticker in metadata
                metadata = {}
                await processor.handle_message(json.dumps(snapshot_message), metadata)
                
                # Start publisher
                await publisher.start()
                await asyncio.sleep(0.2)
                await publisher.stop()
    
    # Should not have published due to missing ticker
    assert len(published_updates) == 0, "Should not publish markets without ticker"
    
    print("✓ Data validation works correctly")


def test_stats():
    """Test publisher statistics."""
    print("🔵 Testing publisher stats...")
    
    processor = KalshiMessageProcessor()
    publisher = KalshiTickerPublisher(processor, publish_interval=1.0)
    
    stats = publisher.get_stats()
    
    assert "total_published" in stats
    assert "rate_limited" in stats
    assert "failed_publishes" in stats
    assert "active_markets" in stats
    assert "is_running" in stats
    assert "publish_interval" in stats
    assert "tracked_markets" in stats
    
    assert stats["publish_interval"] == 1.0
    assert stats["is_running"] == False
    
    print("✓ Publisher stats work correctly")


async def run_all_tests():
    """Run all integration tests."""
    print("🚀 Running Kalshi Ticker Integration Tests...\n")
    
    try:
        # Run tests
        await test_ticker_publisher_basic()
        await test_rate_limiting()
        await test_multiple_markets()
        await test_data_validation()
        test_stats()
        
        print("\n✅ All integration tests passed!")
        
    except Exception as e:
        print(f"\n❌ Integration test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(run_all_tests())