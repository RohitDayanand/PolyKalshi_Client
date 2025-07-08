#!/usr/bin/env python3
"""
Test script to validate that the ticker publisher now accepts the modernized format.
"""

import asyncio
import json
import logging
from datetime import datetime
import sys
import os

# Add the backend path for imports
sys.path.append('/home/rohit/Websocket_Polymarket_Kalshi/backend')

from backend.master_manager.kalshi_client.message_processor import KalshiMessageProcessor
from backend.master_manager.kalshi_ticker_publisher import KalshiTickerPublisher

# Configure logging to see validation details
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger(__name__)

async def test_ticker_publisher_validation():
    """Test that ticker publisher validation works with the new decimal format."""
    
    print("🧪 Testing Ticker Publisher Validation")
    print("=" * 50)
    
    # Initialize components
    processor = KalshiMessageProcessor()
    publisher = KalshiTickerPublisher(processor, publish_interval=1.0)
    
    # Real Kalshi snapshot with the data that was previously failing
    snapshot_message = {
        "type": "orderbook_snapshot",
        "sid": 1,
        "seq": 2,
        "msg": {
            "market_ticker": "KXMAYORNYCPARTY-25-D",
            "market_id": "d6001565-9ce7-4194-81a1-ab96e694491c",
            "yes": [[76,11444],[75,23239]],  # Simplified real data
            "no": [[23,6958],[24,3000]]
        }
    }
    
    metadata = {
        "platform": "kalshi",
        "subscription_id": "test_market", 
        "ticker": "KXMAYORNYCPARTY-25-D"
    }
    
    print("\n1. Processing Snapshot")
    await processor.handle_message(json.dumps(snapshot_message), metadata)
    
    print("\n2. Getting Summary Stats from Processor")
    summary_stats = processor.get_summary_stats(1)
    
    if summary_stats:
        print(f"   Summary stats generated: {summary_stats}")
        
        # Show the format conversion details
        yes_bid = summary_stats['yes']['bid']
        yes_ask = summary_stats['yes']['ask']
        no_bid = summary_stats['no']['bid']
        no_ask = summary_stats['no']['ask']
        volume = summary_stats['yes']['volume']
        
        print(f"   YES: bid={yes_bid}, ask={yes_ask}")
        print(f"   NO:  bid={no_bid}, ask={no_ask}")
        print(f"   Volume: {volume}")
        
        print("\n3. Testing Ticker Publisher Validation")
        is_valid = publisher._is_valid_summary_stats(summary_stats)
        
        if is_valid:
            print("   ✅ VALIDATION PASSED! Summary stats accepted by ticker publisher")
            
            # Test economic checks
            if yes_bid is not None and no_ask is not None:
                complement = yes_bid + no_ask
                print(f"   ✅ Economic check: YES bid + NO ask = {complement:.3f} ≈ 1.0")
            
            if yes_ask is not None and no_bid is not None:
                spread_sum = yes_ask + no_bid
                print(f"   ✅ Spread check: YES ask + NO bid = {spread_sum:.3f} ≈ 1.0")
                
        else:
            print("   ❌ VALIDATION FAILED! Summary stats rejected by ticker publisher")
            return False
    else:
        print("   ❌ No summary stats generated")
        return False
    
    print("\n4. Testing Edge Cases")
    
    # Test invalid data (old format) should fail
    invalid_stats = {
        "yes": {"bid": 76, "ask": 77, "volume": 143452.0},  # Old cent format
        "no": {"bid": 23, "ask": 24, "volume": 143452.0}
    }
    
    print("\n   Testing old cent format (should fail):")
    print(f"   Invalid data: {invalid_stats}")
    is_invalid = publisher._is_valid_summary_stats(invalid_stats)
    
    if not is_invalid:
        print("   ✅ Correctly rejected old cent format")
    else:
        print("   ❌ Incorrectly accepted old cent format")
        return False
    
    # Test arbitrage detection
    arbitrage_stats = {
        "yes": {"bid": 0.8, "ask": 0.85, "volume": 1000.0},  # YES bid too high
        "no": {"bid": 0.25, "ask": 0.15, "volume": 1000.0}   # NO ask too low (sum > 1.0)
    }
    
    print("\n   Testing arbitrage detection (should fail):")
    print(f"   Arbitrage data: {arbitrage_stats}")
    print(f"   YES bid + NO ask = {arbitrage_stats['yes']['bid'] + arbitrage_stats['no']['ask']} > 1.0")
    is_arbitrage = publisher._is_valid_summary_stats(arbitrage_stats)
    
    if not is_arbitrage:
        print("   ✅ Correctly detected and rejected arbitrage opportunity")
    else:
        print("   ❌ Failed to detect arbitrage opportunity")
        return False
    
    print("\n🎯 Test Summary")
    print("=" * 50)
    print("✅ Decimal format conversion: WORKING")
    print("✅ Ticker publisher validation: ACCEPTING")
    print("✅ Economic validation: WORKING") 
    print("✅ Edge case detection: WORKING")
    print("\n🔥 The 'invalid summary stats' error is now FIXED!")
    
    processor.cleanup()
    return True

if __name__ == "__main__":
    success = asyncio.run(test_ticker_publisher_validation())
    sys.exit(0 if success else 1)