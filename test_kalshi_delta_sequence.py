#!/usr/bin/env python3
"""
Test script for Kalshi orderbook delta processing with correct sequence numbers.
"""

import asyncio
import json
import logging
from datetime import datetime
import sys
import os

# Add the backend path for imports
sys.path.append('/home/rohit/Websocket_Polymarket_Kalshi/backend')

from backend.master_manager.kalshi_client.kalshi_message_processor import KalshiMessageProcessor

# Configure logging 
logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger(__name__)

async def test_sequential_delta_processing():
    """Test delta processing with correct sequence numbers."""
    
    print("🧪 Testing Sequential Delta Processing")
    print("=" * 50)
    
    processor = KalshiMessageProcessor()
    
    # Snapshot with seq=2
    snapshot_message = {
        "type": "orderbook_snapshot",
        "sid": 1,
        "seq": 2,
        "msg": {
            "market_ticker": "KXMAYORNYCPARTY-25-D",
            "market_id": "d6001565-9ce7-4194-81a1-ab96e694491c",
            "yes": [[75,1000],[76,2000]],  # Simplified for testing
            "no": [[23,5000],[24,3000]]
        }
    }
    
    # Delta with seq=3 (next sequence)
    delta_message = {
        "type": "orderbook_delta",
        "sid": 1,
        "seq": 3,
        "msg": {
            "market_ticker": "KXMAYORNYCPARTY-25-D",
            "market_id": "d6001565-9ce7-4194-81a1-ab96e694491c",
            "price": 77,
            "delta": 1500,
            "side": "yes",
            "ts": "2025-06-25T06:40:36.059857Z"
        }
    }
    
    metadata = {"platform": "kalshi", "subscription_id": "test_market", "ticker": "KXMAYORNYCPARTY-25-D"}
    
    print("\n1. Processing Snapshot (seq=2)")
    await processor.handle_message(json.dumps(snapshot_message), metadata)
    
    orderbook = processor.get_orderbook(1)
    print(f"   Initial state: {len(orderbook.yes_contracts)} YES, {len(orderbook.no_contracts)} NO")
    print(f"   Highest YES: {orderbook.get_yes_market_bid()}")
    print(f"   Highest NO: {orderbook.get_no_market_bid()}")
    
    initial_stats = orderbook.calculate_yes_no_prices()
    print(f"   Initial: YES bid={initial_stats['yes']['bid']}, NO ask={initial_stats['no']['ask']}")
    
    print("\n2. Processing Delta (seq=3) - Adding YES level at 77")
    await processor.handle_message(json.dumps(delta_message), metadata)
    
    print(f"   Sequence updated: {orderbook.last_seq}")
    print(f"   New highest YES: {orderbook.get_yes_market_bid()}")
    
    # Check if price 77 was added
    level_77 = orderbook.yes_contracts.get(77)
    if level_77:
        print(f"   ✅ Price 77 (YES) created: size={level_77.size}")
    else:
        print(f"   ❌ Price 77 (YES) not found!")
    
    updated_stats = orderbook.calculate_yes_no_prices()
    print(f"   Updated: YES bid={updated_stats['yes']['bid']}, NO ask={updated_stats['no']['ask']}")
    
    # Validate that YES bid increased from 0.76 to 0.77 (decimal format)
    if updated_stats['yes']['bid'] == 0.77:
        print("   ✅ YES bid correctly updated to 0.77")
        # NO ask should be (100-77)/100=0.23
        if updated_stats['no']['ask'] == 0.23:
            print("   ✅ NO ask correctly updated to 0.23 (decimal format)")
        else:
            print(f"   ❌ NO ask should be 0.23, got {updated_stats['no']['ask']}")
    else:
        print(f"   ❌ YES bid should be 0.77, got {updated_stats['yes']['bid']}")
    
    print("\n3. Testing Price Level Removal")
    # Delta that removes a level (size goes to 0)
    removal_delta = {
        "type": "orderbook_delta",
        "sid": 1,
        "seq": 4,
        "msg": {
            "market_ticker": "KXMAYORNYCPARTY-25-D",
            "market_id": "d6001565-9ce7-4194-81a1-ab96e694491c",
            "price": 77,
            "delta": -1500,  # Remove all size
            "side": "yes",
            "ts": "2025-06-25T06:40:36.059857Z"
        }
    }
    
    await processor.handle_message(json.dumps(removal_delta), metadata)
    
    # Check if price 77 was removed
    level_77_after = orderbook.yes_contracts.get(77)
    if level_77_after is None:
        print("   ✅ Price 77 (YES) correctly removed")
        new_highest = orderbook.get_yes_market_bid()
        print(f"   New highest YES: {new_highest} (should be 76)")
        
        final_stats = orderbook.calculate_yes_no_prices()
        print(f"   Final: YES bid={final_stats['yes']['bid']}, NO ask={final_stats['no']['ask']}")
    else:
        print(f"   ❌ Price 77 (YES) still exists: size={level_77_after.size}")
    
    processor.cleanup()
    print("\n✅ Sequential delta processing test completed!")
    return True

if __name__ == "__main__":
    asyncio.run(test_sequential_delta_processing())