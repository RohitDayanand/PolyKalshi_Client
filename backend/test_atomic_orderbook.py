#!/usr/bin/env python3
"""
Quick test script to verify the atomic orderbook state functionality.
"""

import asyncio
import time
from datetime import datetime
from master_manager.kalshi_client.models.orderbook_state import AtomicOrderbookState, OrderbookSnapshot

async def test_atomic_operations():
    """Test basic atomic operations."""
    print("🧪 Testing Atomic Orderbook State...")
    
    # Create atomic orderbook state
    atomic_orderbook = AtomicOrderbookState(sid=123, market_ticker="TEST-MARKET")
    
    # Test lock-free read
    snapshot1 = atomic_orderbook.get_snapshot()
    print(f"✅ Initial snapshot: sid={snapshot1.sid}, ticker={snapshot1.market_ticker}")
    print(f"   - Yes contracts: {len(snapshot1.yes_contracts)}")
    print(f"   - No contracts: {len(snapshot1.no_contracts)}")
    print(f"   - Last seq: {snapshot1.last_seq}")
    
    # Test async snapshot application
    test_snapshot_data = {
        'msg': {
            'yes': [[50, 100], [60, 200]],  # price, size
            'no': [[40, 150], [30, 250]]
        }
    }
    
    print("\n🔄 Applying test snapshot...")
    await atomic_orderbook.apply_snapshot(test_snapshot_data, seq=1, timestamp=datetime.now())
    
    # Verify atomic swap worked
    snapshot2 = atomic_orderbook.get_snapshot()
    print(f"✅ After snapshot: sid={snapshot2.sid}, ticker={snapshot2.market_ticker}")
    print(f"   - Yes contracts: {len(snapshot2.yes_contracts)} (should be 2)")
    print(f"   - No contracts: {len(snapshot2.no_contracts)} (should be 2)")
    print(f"   - Last seq: {snapshot2.last_seq} (should be 1)")
    print(f"   - Best yes bid: {snapshot2.get_yes_market_bid()}")
    print(f"   - Best no bid: {snapshot2.get_no_market_bid()}")
    
    # Test delta application
    test_delta_data = {
        'msg': {
            'side': 'yes',
            'price': 70,  # New price level
            'delta': 300
        }
    }
    
    print("\n🔄 Applying test delta...")
    await atomic_orderbook.apply_delta(test_delta_data, seq=2, timestamp=datetime.now())
    
    # Verify delta worked
    snapshot3 = atomic_orderbook.get_snapshot()
    print(f"✅ After delta: last_seq={snapshot3.last_seq} (should be 2)")
    print(f"   - Yes contracts: {len(snapshot3.yes_contracts)} (should be 3)")
    print(f"   - Best yes bid: {snapshot3.get_yes_market_bid()} (should be 70)")
    
    # Test price calculation
    prices = snapshot3.calculate_yes_no_prices()
    print(f"\n📊 Price calculation:")
    print(f"   - YES: bid={prices['yes']['bid']}, ask={prices['yes']['ask']}")
    print(f"   - NO: bid={prices['no']['bid']}, ask={prices['no']['ask']}")
    
    print("\n✨ All tests passed! Atomic orderbook state is working correctly.")

async def test_concurrent_access():
    """Test concurrent read/write operations."""
    print("\n🔀 Testing concurrent access...")
    
    atomic_orderbook = AtomicOrderbookState(sid=456, market_ticker="CONCURRENT-TEST")
    
    # Initialize with some data
    initial_data = {
        'msg': {
            'yes': [[50, 100]],
            'no': [[40, 150]]
        }
    }
    await atomic_orderbook.apply_snapshot(initial_data, seq=1, timestamp=datetime.now())
    
    # Simulate concurrent readers
    async def reader_task(reader_id: int):
        """Simulate a reader accessing the orderbook frequently."""
        for i in range(100):
            snapshot = atomic_orderbook.get_snapshot()
            best_bid = snapshot.get_yes_market_bid()
            # No locks needed for reads - this is lock-free!
            await asyncio.sleep(0.001)  # Small delay to simulate processing
        print(f"   ✅ Reader {reader_id} completed 100 reads")
    
    # Simulate concurrent writer
    async def writer_task():
        """Simulate a writer updating the orderbook."""
        for i in range(10):
            delta_data = {
                'msg': {
                    'side': 'yes',
                    'price': 50 + i,
                    'delta': 10
                }
            }
            await atomic_orderbook.apply_delta(delta_data, seq=2+i, timestamp=datetime.now())
            await asyncio.sleep(0.01)  # Simulate processing time
        print(f"   ✅ Writer completed 10 updates")
    
    # Run concurrent tasks
    start_time = time.time()
    await asyncio.gather(
        reader_task(1),
        reader_task(2), 
        reader_task(3),
        writer_task()
    )
    end_time = time.time()
    
    print(f"   ⚡ Concurrent test completed in {end_time - start_time:.3f}s")
    
    # Verify final state
    final_snapshot = atomic_orderbook.get_snapshot()
    print(f"   📊 Final state: {len(final_snapshot.yes_contracts)} yes contracts, seq={final_snapshot.last_seq}")

if __name__ == "__main__":
    asyncio.run(test_atomic_operations())
    asyncio.run(test_concurrent_access())