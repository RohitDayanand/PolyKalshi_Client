"""
Test suite for KalshiMessageProcessor
"""

import json
import asyncio
import sys
import os
from datetime import datetime

# Add the parent directory to Python path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import directly from the module files
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'kalshi_client'))

from kalshi_message_processor import KalshiMessageProcessor, OrderbookState


async def test_handle_error_message():
    """Test error message handling."""
    print("🔵 Testing error message handling...")
    
    processor = KalshiMessageProcessor()
    test_errors = []
    
    def error_callback(error_info):
        test_errors.append(error_info)
    
    processor.set_error_callback(error_callback)
    
    error_message = {
        "type": "error",
        "msg": "Invalid subscription",
        "code": "INVALID_SUB"
    }
    
    metadata = {"ticker": "TEST-TICKER"}
    
    await processor.handle_message(json.dumps(error_message), metadata)
    
    assert len(test_errors) == 1
    error = test_errors[0]
    assert error["type"] == "error"
    assert error["message"] == "Invalid subscription"
    assert error["code"] == "INVALID_SUB"
    
    print("✓ Error message handling works correctly")


async def test_handle_ok_message():
    """Test successful subscription message."""
    print("🔵 Testing OK message handling...")
    
    processor = KalshiMessageProcessor()
    
    ok_message = {
        "type": "ok",
        "sid": 12345
    }
    
    metadata = {"ticker": "TEST-TICKER"}
    
    await processor.handle_message(json.dumps(ok_message), metadata)
    
    # Should create orderbook state
    assert 12345 in processor.orderbooks
    orderbook = processor.orderbooks[12345]
    assert orderbook.sid == 12345
    assert orderbook.market_ticker == "TEST-TICKER"
    
    print("✓ OK message handling works correctly")


async def test_handle_orderbook_snapshot():
    """Test orderbook snapshot processing."""
    print("🔵 Testing orderbook snapshot handling...")
    
    processor = KalshiMessageProcessor()
    test_updates = []
    
    def update_callback(sid, orderbook):
        test_updates.append((sid, orderbook))
    
    processor.set_orderbook_update_callback(update_callback)
    
    snapshot_message = {
        "type": "orderbook_snapshot",
        "sid": 12345,
        "seq": 100,
        "bids": [
            {"price": "0.52", "size": "100"},
            {"price": "0.51", "size": "200"}
        ],
        "asks": [
            {"price": "0.53", "size": "150"},
            {"price": "0.54", "size": "75"}
        ]
    }
    
    metadata = {"ticker": "TEST-TICKER"}
    
    await processor.handle_message(json.dumps(snapshot_message), metadata)
    
    # Should create orderbook and apply snapshot
    assert 12345 in processor.orderbooks
    orderbook = processor.orderbooks[12345]
    
    assert orderbook.last_seq == 100
    assert len(orderbook.bids) == 2
    assert len(orderbook.asks) == 2
    assert orderbook.bids["0.52"].size == "100"
    assert orderbook.asks["0.53"].size == "150"
    
    # Should trigger update callback
    assert len(test_updates) == 1
    assert test_updates[0][0] == 12345
    
    print("✓ Orderbook snapshot handling works correctly")


async def test_handle_orderbook_delta():
    """Test orderbook delta processing."""
    print("🔵 Testing orderbook delta handling...")
    
    processor = KalshiMessageProcessor()
    test_updates = []
    
    def update_callback(sid, orderbook):
        test_updates.append((sid, orderbook))
    
    processor.set_orderbook_update_callback(update_callback)
    
    # First set up with snapshot
    snapshot_message = {
        "type": "orderbook_snapshot",
        "sid": 12345,
        "seq": 100,
        "bids": [{"price": "0.52", "size": "100"}],
        "asks": [{"price": "0.53", "size": "150"}]
    }
    
    metadata = {"ticker": "TEST-TICKER"}
    await processor.handle_message(json.dumps(snapshot_message), metadata)
    test_updates.clear()  # Clear snapshot update
    
    # Apply delta
    delta_message = {
        "type": "orderbook_delta",
        "sid": 12345,
        "seq": 101,
        "bids": [
            {"price": "0.52", "size": "0"},  # Remove this level
            {"price": "0.50", "size": "300"}  # Add new level
        ],
        "asks": [
            {"price": "0.53", "size": "200"}  # Update existing level
        ]
    }
    
    await processor.handle_message(json.dumps(delta_message), metadata)
    
    orderbook = processor.orderbooks[12345]
    
    assert orderbook.last_seq == 101
    assert "0.52" not in orderbook.bids  # Should be removed
    assert orderbook.bids["0.50"].size == "300"  # Should be added
    assert orderbook.asks["0.53"].size == "200"  # Should be updated
    
    # Should trigger update callback
    assert len(test_updates) == 1
    
    print("✓ Orderbook delta handling works correctly")


async def test_sequence_validation():
    """Test sequence number validation."""
    print("🔵 Testing sequence validation...")
    
    processor = KalshiMessageProcessor()
    
    # Set up orderbook with snapshot
    snapshot_message = {
        "type": "orderbook_snapshot",
        "sid": 12345,
        "seq": 100,
        "bids": [{"price": "0.52", "size": "100"}],
        "asks": [{"price": "0.53", "size": "150"}]
    }
    
    metadata = {"ticker": "TEST-TICKER"}
    await processor.handle_message(json.dumps(snapshot_message), metadata)
    
    # Try to apply delta with wrong sequence
    delta_message = {
        "type": "orderbook_delta",
        "sid": 12345,
        "seq": 103,  # Should be 101, not 103
        "bids": [{"price": "0.50", "size": "100"}]
    }
    
    await processor.handle_message(json.dumps(delta_message), metadata)
    
    # Should not apply delta due to sequence gap
    orderbook = processor.orderbooks[12345]
    assert orderbook.last_seq == 100  # Should remain unchanged
    assert "0.50" not in orderbook.bids  # Delta should not be applied
    
    print("✓ Sequence validation works correctly")


async def test_invalid_json():
    """Test handling of invalid JSON messages."""
    print("🔵 Testing invalid JSON handling...")
    
    processor = KalshiMessageProcessor()
    invalid_message = "{ invalid json"
    metadata = {"ticker": "TEST-TICKER"}
    
    # Should not crash
    await processor.handle_message(invalid_message, metadata)
    
    # Should not have processed anything
    assert len(processor.orderbooks) == 0
    
    print("✓ Invalid JSON handling works correctly")


def test_get_orderbook_methods():
    """Test orderbook retrieval methods."""
    print("🔵 Testing orderbook retrieval methods...")
    
    processor = KalshiMessageProcessor()
    
    # Create mock orderbook
    orderbook = OrderbookState(sid=12345, market_ticker="TEST")
    processor.orderbooks[12345] = orderbook
    
    # Test get_orderbook
    retrieved = processor.get_orderbook(12345)
    assert retrieved is orderbook
    
    # Test get_all_orderbooks
    all_orderbooks = processor.get_all_orderbooks()
    assert 12345 in all_orderbooks
    assert all_orderbooks[12345] is orderbook
    
    # Test non-existent orderbook
    assert processor.get_orderbook(99999) is None
    
    print("✓ Orderbook retrieval methods work correctly")


def test_get_stats():
    """Test processor statistics."""
    print("🔵 Testing stats method...")
    
    processor = KalshiMessageProcessor()
    
    # Create mock orderbooks
    processor.orderbooks[12345] = OrderbookState(sid=12345)
    processor.orderbooks[67890] = OrderbookState(sid=67890)
    
    stats = processor.get_stats()
    
    assert stats["active_markets"] == 2
    assert 12345 in stats["market_sids"]
    assert 67890 in stats["market_sids"]
    assert stats["processor_status"] == "running"
    
    print("✓ Stats method works correctly")


async def test_bid_ask_calculation():
    """Test bid/ask calculation for yes/no sides."""
    print("🔵 Testing bid/ask calculation...")
    
    processor = KalshiMessageProcessor()
    
    # Set up orderbook with snapshot
    snapshot_message = {
        "type": "orderbook_snapshot",
        "sid": 12345,
        "seq": 100,
        "bids": [
            {"price": "0.45", "size": "100"},  # Best bid
            {"price": "0.44", "size": "200"},
            {"price": "0.43", "size": "150"}
        ],
        "asks": [
            {"price": "0.47", "size": "80"},   # Best ask
            {"price": "0.48", "size": "120"},
            {"price": "0.49", "size": "90"}
        ]
    }
    
    metadata = {"ticker": "TEST-TICKER"}
    await processor.handle_message(json.dumps(snapshot_message), metadata)
    
    # Test summary stats calculation
    summary_stats = processor.get_summary_stats(12345)
    
    assert summary_stats is not None
    
    # Check YES side (direct prices)
    yes_data = summary_stats["yes"]
    assert yes_data["bid"] == 0.45  # Best bid
    assert yes_data["ask"] == 0.47  # Best ask
    assert yes_data["volume"] == 100 + 200 + 150 + 80 + 120 + 90  # Total volume
    
    # Check NO side (inverse prices)
    no_data = summary_stats["no"]
    assert abs(no_data["bid"] - (1.0 - 0.47)) < 0.001  # 1 - best ask = 0.53
    assert abs(no_data["ask"] - (1.0 - 0.45)) < 0.001  # 1 - best bid = 0.55
    assert no_data["volume"] == yes_data["volume"]  # Same volume
    
    print("✓ Bid/ask calculation works correctly")
    print(f"  YES: bid={yes_data['bid']}, ask={yes_data['ask']}")
    print(f"  NO:  bid={no_data['bid']:.3f}, ask={no_data['ask']:.3f}")


def test_summary_stats_empty_orderbook():
    """Test summary stats with empty orderbook."""
    print("🔵 Testing summary stats with empty orderbook...")
    
    processor = KalshiMessageProcessor()
    
    # Test non-existent sid
    summary_stats = processor.get_summary_stats(99999)
    assert summary_stats is None
    
    # Test sid with empty orderbook
    processor.orderbooks[12345] = OrderbookState(sid=12345)
    summary_stats = processor.get_summary_stats(12345)
    
    assert summary_stats is not None
    assert summary_stats["yes"]["bid"] is None
    assert summary_stats["yes"]["ask"] is None
    assert summary_stats["yes"]["volume"] == 0.0
    assert summary_stats["no"]["bid"] is None
    assert summary_stats["no"]["ask"] is None
    assert summary_stats["no"]["volume"] == 0.0
    
    print("✓ Empty orderbook handling works correctly")


async def run_all_tests():
    """Run all tests."""
    print("🚀 Running KalshiMessageProcessor tests...\n")
    
    try:
        # Test basic functionality
        test_get_stats()
        test_get_orderbook_methods()
        test_summary_stats_empty_orderbook()
        
        # Test async message handling
        await test_handle_error_message()
        await test_handle_ok_message()
        await test_handle_orderbook_snapshot()
        await test_handle_orderbook_delta()
        await test_sequence_validation()
        await test_invalid_json()
        await test_bid_ask_calculation()
        
        print("\n✅ All tests passed!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # Run the tests
    asyncio.run(run_all_tests())