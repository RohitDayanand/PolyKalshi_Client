#!/usr/bin/env python3
"""
Test suite using real Kalshi message formats to simulate actual orderbook processing.

Tests with actual snapshot and delta messages from Kalshi API to validate
orderbook state management under realistic conditions.
"""

import json
import asyncio
import sys
import os
from datetime import datetime

# Import from the proper module structure
from backend.master_manager.kalshi_client.message_processor import KalshiMessageProcessor
from backend.master_manager.kalshi_client.models import OrderbookState


async def test_real_kalshi_snapshot():
    """Test with actual Kalshi snapshot message format."""
    print("🔵 Testing real Kalshi snapshot message...")
    
    processor = KalshiMessageProcessor()
    
    # Real Kalshi snapshot message from your example
    real_snapshot = {
        "type": "orderbook_snapshot",
        "sid": 1,
        "seq": 5,
        "msg": {
            "market_ticker": "KXMAYORNYCPARTY-25-R",
            "market_id": "37304114-f769-4a90-ad84-684f3f5b19b2",
            "yes": [[1, 95010]],  # [price_cents, size]
            "no": [
                [1, 12001], [2, 3000], [3, 700], [14, 3000], [22, 1],
                [44, 3000], [45, 143], [64, 350], [74, 3000], [75, 75],
                [79, 229], [80, 229], [81, 171], [82, 166], [83, 166],
                [84, 120], [85, 620], [86, 1954], [87, 7115], [88, 1800],
                [89, 1300], [90, 1300], [91, 1869], [92, 8794], [93, 10823],
                [94, 16441], [95, 6722], [96, 33600], [97, 28659], [98, 8285]
            ]
        }
    }
    
    metadata = {"ticker": "KXMAYORNYCPARTY-25-R"}
    
    await processor.handle_message(json.dumps(real_snapshot), metadata)
    
    # Verify orderbook state
    orderbook = processor.get_orderbook(1)
    assert orderbook is not None, "Orderbook should be created"
    assert orderbook.sid == 1
    assert orderbook.market_ticker == "KXMAYORNYCPARTY-25-R"
    assert orderbook.last_seq == 5
    
    # Validate O(1) optimization correctness
    snapshot = orderbook.get_snapshot()
    expected_yes_bid = max(snapshot.yes_contracts.keys()) if snapshot.yes_contracts else None
    expected_no_bid = max(snapshot.no_contracts.keys()) if snapshot.no_contracts else None
    assert snapshot.best_yes_bid == expected_yes_bid, f"Cached YES bid {snapshot.best_yes_bid} != calculated {expected_yes_bid}"
    assert snapshot.best_no_bid == expected_no_bid, f"Cached NO bid {snapshot.best_no_bid} != calculated {expected_no_bid}"
    
    # Check YES contracts
    print(f"📊 YES contracts: {len(orderbook.yes_contracts)} levels")
    assert len(orderbook.yes_contracts) == 1, "Should have 1 YES level"
    assert 1 in orderbook.yes_contracts, "Should have YES at price 1"
    assert orderbook.yes_contracts[1].size == 95010, "YES size should be 95010"
    
    # Check NO contracts  
    print(f"📊 NO contracts: {len(orderbook.no_contracts)} levels")
    assert len(orderbook.no_contracts) == 30, "Should have 30 NO levels"
    assert 98 in orderbook.no_contracts, "Should have NO at price 98"
    assert orderbook.no_contracts[98].size == 8285, "NO size at 98 should be 8285"
    
    # Test bid calculations
    yes_bid = orderbook.get_yes_market_bid()
    no_bid = orderbook.get_no_market_bid()
    
    print(f"📈 YES bid: {yes_bid}")
    print(f"📈 NO bid: {no_bid}")
    
    assert yes_bid == 1, "YES bid should be 1 (highest YES price)"
    assert no_bid == 98, "NO bid should be 98 (highest NO price)"
    
    # Test summary stats
    summary = orderbook.calculate_yes_no_prices()
    print(f"📊 Summary stats: {summary}")
    
    assert summary is not None
    # Note: calculate_yes_no_prices() returns decimal format (0.0-1.0), not cent format
    assert summary["yes"]["bid"] == 0.01  # 1 cent = 0.01 in decimal
    assert summary["no"]["bid"] == 0.98   # 98 cents = 0.98 in decimal
    
    print("✅ Real Kalshi snapshot processing works correctly")
    return processor


async def test_real_kalshi_delta():
    """Test with actual Kalshi delta message format."""
    print("\n🔵 Testing real Kalshi delta message...")
    
    # Use processor from snapshot test
    processor = await test_real_kalshi_snapshot()
    
    # Real Kalshi delta message from your example
    real_delta = {
        "type": "orderbook_delta",
        "sid": 1,
        "seq": 6,   # Sequential from snapshot (was 5)
        "msg": {
            "market_ticker": "KXMAYORNYCPARTY-25-D",
            "market_id": "d6001565-9ce7-4194-81a1-ab96e694491c",
            "price": 73,
            "delta": 26,
            "side": "yes",
            "ts": "2025-06-25T06:42:22.769682Z"  # Timestamp
        }
    }
    
    metadata = {"ticker": "KXMAYORNYCPARTY-25-D"}
    
    # Get initial state
    orderbook = processor.get_orderbook(1)
    initial_yes_count = len(orderbook.yes_contracts)
    
    print(f"📊 Before delta: {initial_yes_count} YES levels")
    print(f"📊 Price 73 exists: {73 in orderbook.yes_contracts}")
    
    await processor.handle_message(json.dumps(real_delta), metadata)
    
    # Verify delta application
    orderbook = processor.get_orderbook(1)
    assert orderbook.last_seq == 6, "Sequence should update to 6"
    
    # Validate O(1) optimization correctness after delta
    snapshot = orderbook.get_snapshot()
    expected_yes_bid = max(snapshot.yes_contracts.keys()) if snapshot.yes_contracts else None
    expected_no_bid = max(snapshot.no_contracts.keys()) if snapshot.no_contracts else None
    assert snapshot.best_yes_bid == expected_yes_bid, f"After delta: Cached YES bid {snapshot.best_yes_bid} != calculated {expected_yes_bid}"
    assert snapshot.best_no_bid == expected_no_bid, f"After delta: Cached NO bid {snapshot.best_no_bid} != calculated {expected_no_bid}"
    
    # Check if price level 73 was added
    assert 73 in orderbook.yes_contracts, "Should have YES at price 73"
    assert orderbook.yes_contracts[73].size == 26, "Size should be 26"
    assert orderbook.yes_contracts[73].side == "Yes", "Side should be Yes"
    
    final_yes_count = len(orderbook.yes_contracts)
    print(f"📊 After delta: {final_yes_count} YES levels")
    print(f"📊 New YES bid: {orderbook.get_yes_market_bid()}")
    
    # YES bid should now be 73 (higher than original 1)
    assert orderbook.get_yes_market_bid() == 73, "YES bid should update to 73"
    
    print("✅ Real Kalshi delta processing works correctly")
    return processor


async def test_delta_update_existing_level():
    """Test delta updating an existing price level."""
    print("\n🔵 Testing delta updating existing level...")
    
    processor = KalshiMessageProcessor()
    
    # Create initial snapshot with some levels
    snapshot = {
        "type": "orderbook_snapshot",
        "sid": 2,
        "seq": 10,
        "msg": {
            "market_ticker": "TEST-MARKET",
            "market_id": "test-id",
            "yes": [[50, 1000], [60, 500]],
            "no": [[40, 800], [30, 200]]
        }
    }
    
    await processor.handle_message(json.dumps(snapshot), {"ticker": "TEST-MARKET"})
    
    orderbook = processor.get_orderbook(2)
    print(f"📊 Initial YES at 50: {orderbook.yes_contracts[50].size}")
    
    # Apply delta to existing level
    delta = {
        "type": "orderbook_delta",
        "sid": 2,
        "seq": 11,
        "msg": {
            "market_ticker": "TEST-MARKET",
            "market_id": "test-id",
            "price": 50,
            "delta": 200,  # Add 200 to existing 1000
            "side": "yes"
        }
    }
    
    await processor.handle_message(json.dumps(delta), {"ticker": "TEST-MARKET"})
    
    # Verify update
    assert orderbook.yes_contracts[50].size == 1200, "Size should be 1000 + 200 = 1200"
    print(f"📊 Updated YES at 50: {orderbook.yes_contracts[50].size}")
    
    print("✅ Delta update of existing level works correctly")


async def test_delta_remove_level():
    """Test delta that removes a price level by setting size to 0."""
    print("\n🔵 Testing delta removing price level...")
    
    processor = KalshiMessageProcessor()
    
    # Create initial snapshot
    snapshot = {
        "type": "orderbook_snapshot",
        "sid": 3,
        "seq": 20,
        "msg": {
            "market_ticker": "REMOVE-TEST",
            "market_id": "remove-id",
            "yes": [[45, 300]],
            "no": [[55, 400]]
        }
    }
    
    await processor.handle_message(json.dumps(snapshot), {"ticker": "REMOVE-TEST"})
    
    orderbook = processor.get_orderbook(3)
    assert 45 in orderbook.yes_contracts, "Initial YES level should exist"
    print(f"📊 Initial YES levels: {list(orderbook.yes_contracts.keys())}")
    
    # Apply delta that reduces size below 0 (should remove level)
    delta = {
        "type": "orderbook_delta",
        "sid": 3,
        "seq": 21,
        "msg": {
            "market_ticker": "REMOVE-TEST",
            "market_id": "remove-id",
            "price": 45,
            "delta": -350,  # Remove more than existing (300)
            "side": "yes"
        }
    }
    
    await processor.handle_message(json.dumps(delta), {"ticker": "REMOVE-TEST"})
    
    # Verify removal
    assert 45 not in orderbook.yes_contracts, "YES level should be removed"
    print(f"📊 After removal YES levels: {list(orderbook.yes_contracts.keys())}")
    
    # YES bid should be None now
    assert orderbook.get_yes_market_bid() is None, "YES bid should be None"
    
    print("✅ Delta removal of price level works correctly")


async def test_sequence_gap_handling():
    """Test handling of sequence gaps."""
    print("\n🔵 Testing sequence gap handling...")
    
    processor = KalshiMessageProcessor()
    
    # Create initial snapshot
    snapshot = {
        "type": "orderbook_snapshot",
        "sid": 4,
        "seq": 100,
        "msg": {
            "market_ticker": "GAP-TEST",
            "market_id": "gap-id",
            "yes": [[50, 1000]],
            "no": [[50, 1000]]
        }
    }
    
    await processor.handle_message(json.dumps(snapshot), {"ticker": "GAP-TEST"})
    
    orderbook = processor.get_orderbook(4)
    initial_seq = orderbook.last_seq
    print(f"📊 Initial sequence: {initial_seq}")
    
    # Try to apply delta with sequence gap (should be rejected)
    gap_delta = {
        "type": "orderbook_delta",
        "sid": 4,
        "seq": 105,  # Gap! Should be 101
        "msg": {
            "market_ticker": "GAP-TEST",
            "market_id": "gap-id",
            "price": 60,
            "delta": 500,
            "side": "yes"
        }
    }
    
    await processor.handle_message(json.dumps(gap_delta), {"ticker": "GAP-TEST"})
    
    # Verify gap was detected and delta rejected
    assert orderbook.last_seq == 100, "Sequence should remain at 100"
    assert 60 not in orderbook.yes_contracts, "Delta should not be applied"
    
    print(f"📊 Sequence after gap attempt: {orderbook.last_seq}")
    print("✅ Sequence gap handling works correctly")


async def test_complex_market_simulation():
    """Simulate a complex market with multiple price changes."""
    print("\n🔵 Testing complex market simulation...")
    
    processor = KalshiMessageProcessor()
    
    # Large realistic snapshot
    complex_snapshot = {
        "type": "orderbook_snapshot",
        "sid": 5,
        "seq": 1000,
        "msg": {
            "market_ticker": "COMPLEX-MARKET",
            "market_id": "complex-id",
            "yes": [
                [45, 5000], [46, 3000], [47, 2000], [48, 1500], [49, 1000]
            ],
            "no": [
                [51, 1200], [52, 1800], [53, 2500], [54, 3200], [55, 4000],
                [56, 2000], [57, 1500], [58, 1000], [59, 500]
            ]
        }
    }
    
    await processor.handle_message(json.dumps(complex_snapshot), {"ticker": "COMPLEX-MARKET"})
    
    orderbook = processor.get_orderbook(5)
    print(f"📊 Initial state: {len(orderbook.yes_contracts)} YES, {len(orderbook.no_contracts)} NO")
    print(f"📊 Initial YES bid: {orderbook.get_yes_market_bid()}")
    print(f"📊 Initial NO bid: {orderbook.get_no_market_bid()}")
    
    # Series of realistic deltas
    deltas = [
        {"seq": 1001, "price": 50, "delta": 2000, "side": "yes"},  # New best YES bid
        {"seq": 1002, "price": 49, "delta": -500, "side": "yes"},  # Reduce existing
        {"seq": 1003, "price": 52, "delta": -1000, "side": "no"},  # Reduce NO level
        {"seq": 1004, "price": 45, "delta": -5000, "side": "yes"}, # Remove YES level
        {"seq": 1005, "price": 60, "delta": 800, "side": "no"},    # New NO level
    ]
    
    for i, delta_data in enumerate(deltas):
        delta_msg = {
            "type": "orderbook_delta",
            "sid": 5,
            "seq": delta_data["seq"],
            "msg": {
                "market_ticker": "COMPLEX-MARKET",
                "market_id": "complex-id",
                "price": delta_data["price"],
                "delta": delta_data["delta"],
                "side": delta_data["side"]
            }
        }
        
        await processor.handle_message(json.dumps(delta_msg), {"ticker": "COMPLEX-MARKET"})
        
        print(f"📊 After delta {i+1}: YES bid={orderbook.get_yes_market_bid()}, NO bid={orderbook.get_no_market_bid()}")
    
    # Final state analysis
    final_summary = orderbook.calculate_yes_no_prices()
    print(f"📊 Final summary: {final_summary}")
    
    # Verify expected final state
    assert orderbook.get_yes_market_bid() == 50, "YES bid should be 50 (new highest)"
    assert 45 not in orderbook.yes_contracts, "Price 45 should be removed"
    assert 50 in orderbook.yes_contracts, "Price 50 should exist"
    assert orderbook.yes_contracts[49].size == 500, "Price 49 should have reduced size"
    
    print("✅ Complex market simulation works correctly")


async def run_all_real_data_tests():
    """Run all realistic data tests."""
    print("🚀 Running Real Kalshi Data Simulation Tests...\n")
    
    try:
        await test_real_kalshi_snapshot()
        await test_real_kalshi_delta()
        await test_delta_update_existing_level()
        await test_delta_remove_level()
        await test_sequence_gap_handling()
        await test_complex_market_simulation()
        
        print("\n✅ All real data simulation tests passed!")
        print("🎯 The orderbook processor correctly handles real Kalshi message formats")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(run_all_real_data_tests())