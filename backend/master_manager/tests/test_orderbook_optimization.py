#!/usr/bin/env python3
"""
Test suite specifically for the O(1) orderbook optimization.

Tests edge cases and validates that cached best prices match calculated values.
"""

import asyncio
import sys
import os
from datetime import datetime

# Import from the proper module structure  
from backend.master_manager.kalshi_client.models.orderbook_state import AtomicOrderbookState, OrderbookSnapshot
from backend.master_manager.kalshi_client.models.orderbook_level import OrderbookLevel


def validate_best_prices(orderbook: AtomicOrderbookState) -> bool:
    """
    Validation helper: Compare cached best prices vs recalculated O(n) values.
    
    Returns:
        True if cached values match recalculated values
    """
    snapshot = orderbook.get_snapshot()
    
    # Recalculate best prices using O(n) method
    expected_yes_bid = max(snapshot.yes_contracts.keys()) if snapshot.yes_contracts else None
    expected_no_bid = max(snapshot.no_contracts.keys()) if snapshot.no_contracts else None
    
    # Compare with cached values
    cached_yes_bid = snapshot.best_yes_bid
    cached_no_bid = snapshot.best_no_bid
    
    print(f"🔍 VALIDATION: YES - cached:{cached_yes_bid} vs expected:{expected_yes_bid}")
    print(f"🔍 VALIDATION: NO - cached:{cached_no_bid} vs expected:{expected_no_bid}")
    
    return (cached_yes_bid == expected_yes_bid) and (cached_no_bid == expected_no_bid)


async def test_best_price_improvement():
    """Test that new better bids correctly update cached best prices."""
    print("🧪 Testing best price improvement...")
    
    orderbook = AtomicOrderbookState(sid=1, market_ticker="TEST-IMPROVE")
    
    # Initial snapshot with moderate prices
    snapshot_data = {
        "msg": {
            "yes": [[85, 100], [80, 200]],  # Best YES bid = 85
            "no": [[15, 80], [10, 120]]     # Best NO bid = 15
        }
    }
    
    await orderbook.apply_snapshot(snapshot_data, seq=1, timestamp=datetime.now())
    
    # Validate initial state
    assert validate_best_prices(orderbook), "Initial best prices should match"
    assert orderbook.get_yes_market_bid() == 85, "Initial YES bid should be 85"
    assert orderbook.get_no_market_bid() == 15, "Initial NO bid should be 15"
    
    # Add a better YES bid (95 > 85)
    delta_better_yes = {
        "msg": {
            "side": "yes",
            "price": 95,
            "delta": 50
        }
    }
    
    await orderbook.apply_delta(delta_better_yes, seq=2, timestamp=datetime.now())
    
    # Validate improvement
    assert validate_best_prices(orderbook), "Best prices should match after improvement"
    assert orderbook.get_yes_market_bid() == 95, "YES bid should improve to 95"
    assert orderbook.get_no_market_bid() == 15, "NO bid should remain 15"
    
    # Add a better NO bid (20 > 15)
    delta_better_no = {
        "msg": {
            "side": "no",
            "price": 20,
            "delta": 75
        }
    }
    
    await orderbook.apply_delta(delta_better_no, seq=3, timestamp=datetime.now())
    
    # Validate both improvements
    assert validate_best_prices(orderbook), "Best prices should match after both improvements"
    assert orderbook.get_yes_market_bid() == 95, "YES bid should remain 95"
    assert orderbook.get_no_market_bid() == 20, "NO bid should improve to 20"
    
    print("✅ Best price improvement test passed!")


async def test_best_price_removal():
    """Test that removing the best bid correctly recalculates to next best."""
    print("🧪 Testing best price removal and recalculation...")
    
    orderbook = AtomicOrderbookState(sid=2, market_ticker="TEST-REMOVE")
    
    # Initial snapshot with multiple price levels
    snapshot_data = {
        "msg": {
            "yes": [[98, 100], [95, 200], [90, 150]],  # Best YES bid = 98
            "no": [[22, 80], [20, 120], [18, 90]]      # Best NO bid = 22
        }
    }
    
    await orderbook.apply_snapshot(snapshot_data, seq=1, timestamp=datetime.now())
    
    # Validate initial state
    assert validate_best_prices(orderbook), "Initial best prices should match"
    assert orderbook.get_yes_market_bid() == 98, "Initial YES bid should be 98"
    assert orderbook.get_no_market_bid() == 22, "Initial NO bid should be 22"
    
    # Remove the best YES bid (98)
    delta_remove_yes = {
        "msg": {
            "side": "yes",
            "price": 98,
            "delta": -100  # Remove entire level
        }
    }
    
    await orderbook.apply_delta(delta_remove_yes, seq=2, timestamp=datetime.now())
    
    # Validate recalculation to next best
    assert validate_best_prices(orderbook), "Best prices should match after YES removal"
    assert orderbook.get_yes_market_bid() == 95, "YES bid should fall back to 95"
    assert orderbook.get_no_market_bid() == 22, "NO bid should remain 22"
    
    # Remove the best NO bid (22)
    delta_remove_no = {
        "msg": {
            "side": "no",
            "price": 22,
            "delta": -80  # Remove entire level
        }
    }
    
    await orderbook.apply_delta(delta_remove_no, seq=3, timestamp=datetime.now())
    
    # Validate both recalculations
    assert validate_best_prices(orderbook), "Best prices should match after both removals"
    assert orderbook.get_yes_market_bid() == 95, "YES bid should remain 95"
    assert orderbook.get_no_market_bid() == 20, "NO bid should fall back to 20"
    
    print("✅ Best price removal test passed!")


async def test_empty_orderbook_handling():
    """Test edge case of completely empty orderbook."""
    print("🧪 Testing empty orderbook handling...")
    
    orderbook = AtomicOrderbookState(sid=3, market_ticker="TEST-EMPTY")
    
    # Start with empty snapshot
    snapshot_data = {"msg": {"yes": [], "no": []}}
    
    await orderbook.apply_snapshot(snapshot_data, seq=1, timestamp=datetime.now())
    
    # Validate empty state
    assert validate_best_prices(orderbook), "Empty orderbook should have consistent best prices"
    assert orderbook.get_yes_market_bid() is None, "Empty YES side should return None"
    assert orderbook.get_no_market_bid() is None, "Empty NO side should return None"
    
    # Add first level to empty orderbook
    delta_first_yes = {
        "msg": {
            "side": "yes",
            "price": 50,
            "delta": 100
        }
    }
    
    await orderbook.apply_delta(delta_first_yes, seq=2, timestamp=datetime.now())
    
    # Validate first addition
    assert validate_best_prices(orderbook), "Best prices should match after first addition"
    assert orderbook.get_yes_market_bid() == 50, "YES bid should be 50"
    assert orderbook.get_no_market_bid() is None, "NO side should still be empty"
    
    # Remove the only level, returning to empty
    delta_remove_only = {
        "msg": {
            "side": "yes",
            "price": 50,
            "delta": -100
        }
    }
    
    await orderbook.apply_delta(delta_remove_only, seq=3, timestamp=datetime.now())
    
    # Validate return to empty state
    assert validate_best_prices(orderbook), "Empty orderbook should have consistent best prices"
    assert orderbook.get_yes_market_bid() is None, "YES side should be empty again"
    assert orderbook.get_no_market_bid() is None, "NO side should remain empty"
    
    print("✅ Empty orderbook handling test passed!")


async def test_sequential_delta_updates():
    """Test multiple sequential delta updates maintain correct state."""
    print("🧪 Testing sequential delta updates...")
    
    orderbook = AtomicOrderbookState(sid=4, market_ticker="TEST-SEQUENTIAL")
    
    # Initial snapshot
    snapshot_data = {
        "msg": {
            "yes": [[75, 100]],  # Best YES bid = 75
            "no": [[25, 200]]    # Best NO bid = 25
        }
    }
    
    await orderbook.apply_snapshot(snapshot_data, seq=1, timestamp=datetime.now())
    
    # Sequence of deltas that exercise different cases
    deltas = [
        # 1. Add better YES bid
        {"side": "yes", "price": 80, "delta": 150},  # YES: 80 becomes best
        # 2. Add worse YES bid (should not change best)
        {"side": "yes", "price": 70, "delta": 200},  # YES: best remains 80
        # 3. Add better NO bid
        {"side": "no", "price": 30, "delta": 175},   # NO: 30 becomes best
        # 4. Remove current best YES bid
        {"side": "yes", "price": 80, "delta": -150}, # YES: should fall back to 75
        # 5. Remove current best NO bid
        {"side": "no", "price": 30, "delta": -175},  # NO: should fall back to 25
    ]
    
    expected_yes_bids = [80, 80, 80, 75, 75]
    expected_no_bids = [25, 25, 30, 30, 25]
    
    for i, delta in enumerate(deltas):
        delta_data = {"msg": delta}
        await orderbook.apply_delta(delta_data, seq=i+2, timestamp=datetime.now())
        
        # Validate each step
        assert validate_best_prices(orderbook), f"Step {i+1}: Best prices should match"
        
        actual_yes = orderbook.get_yes_market_bid()
        actual_no = orderbook.get_no_market_bid()
        
        assert actual_yes == expected_yes_bids[i], f"Step {i+1}: YES bid should be {expected_yes_bids[i]}, got {actual_yes}"
        assert actual_no == expected_no_bids[i], f"Step {i+1}: NO bid should be {expected_no_bids[i]}, got {actual_no}"
        
        print(f"📊 Step {i+1}: YES={actual_yes}, NO={actual_no} ✓")
    
    print("✅ Sequential delta updates test passed!")


async def run_optimization_tests():
    """Run all optimization-specific tests."""
    print("🚀 Running Orderbook Optimization Tests...")
    print("=" * 60)
    
    try:
        await test_best_price_improvement()
        print()
        
        await test_best_price_removal()
        print()
        
        await test_empty_orderbook_handling()
        print()
        
        await test_sequential_delta_updates()
        print()
        
        print("=" * 60)
        print("🎉 ALL OPTIMIZATION TESTS PASSED!")
        print("✅ O(1) orderbook optimization is working correctly")
        print("✅ Cached best prices always match recalculated values")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(run_optimization_tests())