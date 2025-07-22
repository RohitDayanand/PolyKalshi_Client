#!/usr/bin/env python3
"""
Test level removal (popping) with simple arithmetic validation.

Uses known initial state and predictable deltas to verify exact expected results
without circular dependency on the same data structure being tested.
"""

import asyncio
import sys
import os
from datetime import datetime

# Import from the proper module structure  
from backend.master_manager.kalshi_client.models.orderbook_state import AtomicOrderbookState


async def test_sequential_level_removal():
    """Test removing levels sequentially with known arithmetic results."""
    print("🧪 Testing sequential level removal with known arithmetic...")
    
    orderbook = AtomicOrderbookState(sid=1, market_ticker="ARITHMETIC-TEST")
    
    # Initial state: 4 YES levels, 3 NO levels
    initial_snapshot = {
        "msg": {
            "yes": [
                [95, 100],  # 95¢ → 100 shares (BEST)
                [90, 200],  # 90¢ → 200 shares
                [85, 150],  # 85¢ → 150 shares  
                [80, 300],  # 80¢ → 300 shares
            ],
            "no": [
                [20, 400],  # 20¢ → 400 shares (BEST)
                [15, 250],  # 15¢ → 250 shares
                [10, 180],  # 10¢ → 180 shares
            ]
        }
    }
    
    await orderbook.apply_snapshot(initial_snapshot, seq=1, timestamp=datetime.now())
    
    # ===== STEP 1: Verify initial state =====
    print("📊 STEP 1: Initial state")
    assert orderbook.get_yes_market_bid() == 95, "Initial YES best should be 95¢"
    assert orderbook.get_no_market_bid() == 20, "Initial NO best should be 20¢"
    assert len(orderbook.yes_contracts) == 4, "Should have 4 YES levels"
    assert len(orderbook.no_contracts) == 3, "Should have 3 NO levels"
    assert 95 in orderbook.yes_contracts, "95¢ level should exist"
    assert orderbook.yes_contracts[95].size == 100, "95¢ level should have 100 shares"
    print(f"✅ YES bid: {orderbook.get_yes_market_bid()}¢, NO bid: {orderbook.get_no_market_bid()}¢")
    
    # ===== STEP 2: Remove best YES level (95¢) =====
    print("📊 STEP 2: Remove best YES level (95¢)")
    delta_remove_95 = {
        "msg": {
            "side": "yes",
            "price": 95,
            "delta": -100  # Remove all 100 shares
        }
    }
    
    await orderbook.apply_delta(delta_remove_95, seq=2, timestamp=datetime.now())
    
    # Expected: best_yes_bid should fall back to 90¢
    assert orderbook.get_yes_market_bid() == 90, "After removing 95¢, best should be 90¢"
    assert orderbook.get_no_market_bid() == 20, "NO side should be unchanged"
    assert len(orderbook.yes_contracts) == 3, "Should have 3 YES levels remaining"
    assert 95 not in orderbook.yes_contracts, "95¢ level should be removed"
    assert 90 in orderbook.yes_contracts, "90¢ level should still exist"
    print(f"✅ YES bid: {orderbook.get_yes_market_bid()}¢, NO bid: {orderbook.get_no_market_bid()}¢")
    
    # ===== STEP 3: Remove new best YES level (90¢) =====
    print("📊 STEP 3: Remove new best YES level (90¢)")
    delta_remove_90 = {
        "msg": {
            "side": "yes",
            "price": 90,
            "delta": -200  # Remove all 200 shares
        }
    }
    
    await orderbook.apply_delta(delta_remove_90, seq=3, timestamp=datetime.now())
    
    # Expected: best_yes_bid should fall back to 85¢
    assert orderbook.get_yes_market_bid() == 85, "After removing 90¢, best should be 85¢"
    assert orderbook.get_no_market_bid() == 20, "NO side should be unchanged"
    assert len(orderbook.yes_contracts) == 2, "Should have 2 YES levels remaining"
    assert 90 not in orderbook.yes_contracts, "90¢ level should be removed"
    assert 85 in orderbook.yes_contracts, "85¢ level should still exist"
    assert 80 in orderbook.yes_contracts, "80¢ level should still exist"
    print(f"✅ YES bid: {orderbook.get_yes_market_bid()}¢, NO bid: {orderbook.get_no_market_bid()}¢")
    
    # ===== STEP 4: Add new better YES level (88¢) =====
    print("📊 STEP 4: Add new better YES level (88¢)")
    delta_add_88 = {
        "msg": {
            "side": "yes",
            "price": 88,
            "delta": 250  # Add 250 shares at 88¢
        }
    }
    
    await orderbook.apply_delta(delta_add_88, seq=4, timestamp=datetime.now())
    
    # Expected: best_yes_bid should update to 88¢ (better than 85¢)
    assert orderbook.get_yes_market_bid() == 88, "After adding 88¢, best should be 88¢"
    assert orderbook.get_no_market_bid() == 20, "NO side should be unchanged"
    assert len(orderbook.yes_contracts) == 3, "Should have 3 YES levels now"
    assert 88 in orderbook.yes_contracts, "88¢ level should exist"
    assert orderbook.yes_contracts[88].size == 250, "88¢ level should have 250 shares"
    assert 85 in orderbook.yes_contracts, "85¢ level should still exist"
    assert 80 in orderbook.yes_contracts, "80¢ level should still exist"
    print(f"✅ YES bid: {orderbook.get_yes_market_bid()}¢, NO bid: {orderbook.get_no_market_bid()}¢")
    
    # ===== STEP 5: Remove middle level (85¢) - should NOT affect best =====
    print("📊 STEP 5: Remove middle level (85¢)")
    delta_remove_85 = {
        "msg": {
            "side": "yes",
            "price": 85,
            "delta": -150  # Remove all 150 shares
        }
    }
    
    await orderbook.apply_delta(delta_remove_85, seq=5, timestamp=datetime.now())
    
    # Expected: best_yes_bid should remain 88¢ (removing middle level doesn't affect best)
    assert orderbook.get_yes_market_bid() == 88, "After removing 85¢, best should remain 88¢"
    assert orderbook.get_no_market_bid() == 20, "NO side should be unchanged"
    assert len(orderbook.yes_contracts) == 2, "Should have 2 YES levels remaining"
    assert 85 not in orderbook.yes_contracts, "85¢ level should be removed"
    assert 88 in orderbook.yes_contracts, "88¢ level should still exist"
    assert 80 in orderbook.yes_contracts, "80¢ level should still exist"
    print(f"✅ YES bid: {orderbook.get_yes_market_bid()}¢, NO bid: {orderbook.get_no_market_bid()}¢")
    
    # ===== STEP 6: Remove best NO level (20¢) =====
    print("📊 STEP 6: Remove best NO level (20¢)")
    delta_remove_20 = {
        "msg": {
            "side": "no",
            "price": 20,
            "delta": -400  # Remove all 400 shares
        }
    }
    
    await orderbook.apply_delta(delta_remove_20, seq=6, timestamp=datetime.now())
    
    # Expected: best_no_bid should fall back to 15¢
    assert orderbook.get_yes_market_bid() == 88, "YES side should be unchanged"
    assert orderbook.get_no_market_bid() == 15, "After removing 20¢, NO best should be 15¢"
    assert len(orderbook.no_contracts) == 2, "Should have 2 NO levels remaining"
    assert 20 not in orderbook.no_contracts, "20¢ level should be removed"
    assert 15 in orderbook.no_contracts, "15¢ level should still exist"
    assert 10 in orderbook.no_contracts, "10¢ level should still exist"
    print(f"✅ YES bid: {orderbook.get_yes_market_bid()}¢, NO bid: {orderbook.get_no_market_bid()}¢")
    
    # ===== STEP 7: Remove current best YES (88¢) - should fall back to 80¢ =====
    print("📊 STEP 7: Remove current best YES (88¢)")
    delta_remove_88 = {
        "msg": {
            "side": "yes",
            "price": 88,
            "delta": -250  # Remove all 250 shares
        }
    }
    
    await orderbook.apply_delta(delta_remove_88, seq=7, timestamp=datetime.now())
    
    # Expected: best_yes_bid should fall back to 80¢ (only remaining level)
    assert orderbook.get_yes_market_bid() == 80, "After removing 88¢, best should be 80¢"
    assert orderbook.get_no_market_bid() == 15, "NO side should be unchanged"
    assert len(orderbook.yes_contracts) == 1, "Should have 1 YES level remaining"
    assert 88 not in orderbook.yes_contracts, "88¢ level should be removed"
    assert 80 in orderbook.yes_contracts, "80¢ level should still exist"
    assert orderbook.yes_contracts[80].size == 300, "80¢ level should have 300 shares"
    print(f"✅ YES bid: {orderbook.get_yes_market_bid()}¢, NO bid: {orderbook.get_no_market_bid()}¢")
    
    print("🎉 Sequential level removal test PASSED!")
    print("✅ All level removals (popping) worked correctly")
    print("✅ Best bid recalculation always correct")
    print("✅ Middle level removal doesn't affect best bid")


async def test_complete_level_clearing():
    """Test removing all levels and verifying empty state."""
    print("🧪 Testing complete level clearing...")
    
    orderbook = AtomicOrderbookState(sid=2, market_ticker="CLEAR-TEST")
    
    # Start with 2 YES levels
    initial_snapshot = {
        "msg": {
            "yes": [[75, 100], [70, 200]],
            "no": [[25, 300]]
        }
    }
    
    await orderbook.apply_snapshot(initial_snapshot, seq=1, timestamp=datetime.now())
    
    # Verify initial state
    assert orderbook.get_yes_market_bid() == 75, "Initial YES best should be 75¢"
    assert orderbook.get_no_market_bid() == 25, "Initial NO best should be 25¢"
    print(f"📊 Initial: YES={orderbook.get_yes_market_bid()}¢, NO={orderbook.get_no_market_bid()}¢")
    
    # Remove first level
    delta_1 = {"msg": {"side": "yes", "price": 75, "delta": -100}}
    await orderbook.apply_delta(delta_1, seq=2, timestamp=datetime.now())
    
    assert orderbook.get_yes_market_bid() == 70, "Should fall back to 70¢"
    assert len(orderbook.yes_contracts) == 1, "Should have 1 YES level"
    print(f"📊 After removing 75¢: YES={orderbook.get_yes_market_bid()}¢")
    
    # Remove last level - should become None
    delta_2 = {"msg": {"side": "yes", "price": 70, "delta": -200}}
    await orderbook.apply_delta(delta_2, seq=3, timestamp=datetime.now())
    
    assert orderbook.get_yes_market_bid() is None, "Should be None when empty"
    assert orderbook.get_no_market_bid() == 25, "NO should be unchanged"
    assert len(orderbook.yes_contracts) == 0, "Should have 0 YES levels"
    print(f"📊 After clearing YES: YES={orderbook.get_yes_market_bid()}, NO={orderbook.get_no_market_bid()}¢")
    
    # Add level back - should become best
    delta_3 = {"msg": {"side": "yes", "price": 60, "delta": 150}}
    await orderbook.apply_delta(delta_3, seq=4, timestamp=datetime.now())
    
    assert orderbook.get_yes_market_bid() == 60, "Should be 60¢ after re-adding"
    assert len(orderbook.yes_contracts) == 1, "Should have 1 YES level"
    print(f"📊 After re-adding: YES={orderbook.get_yes_market_bid()}¢")
    
    print("✅ Complete level clearing test PASSED!")


async def run_arithmetic_tests():
    """Run all arithmetic-based tests."""
    print("🚀 Running Level Removal Arithmetic Tests...")
    print("=" * 60)
    
    try:
        await test_sequential_level_removal()
        print()
        
        await test_complete_level_clearing()
        print()
        
        print("=" * 60)
        print("🎉 ALL ARITHMETIC TESTS PASSED!")
        print("✅ Level removal (popping) works correctly")
        print("✅ Best bid recalculation is accurate")
        print("✅ No circular dependency in validation")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(run_arithmetic_tests())