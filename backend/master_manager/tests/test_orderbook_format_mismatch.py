#!/usr/bin/env python3
"""
Test script to demonstrate the orderbook format mismatch issue.

The KalshiMessageProcessor expects Kalshi format:
- bids/asks arrays with {price, size} objects

But the data being tested is Polymarket format:
- yes/no arrays with [price, size] tuples
"""

import json
import asyncio
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ..kalshi_client.message_processor import KalshiMessageProcessor

async def test_format_mismatch():
    """Test the format mismatch between expected Kalshi and provided Polymarket data."""
    
    print("🧪 Testing orderbook format mismatch...")
    
    # Initialize processor
    processor = KalshiMessageProcessor()
    
    # The data format you provided (Polymarket style)
    polymarket_style_data = {
        "sid": 123,
        "type": "orderbook_snapshot", 
        "seq": 1,
        "msg": {
            "market_ticker": "TEST_MARKET",
            "yes": [
                [60, 100],  # [price_cents, size]
                [59, 200],
                [58, 150]
            ],
            "no": [
                [41, 120],  # [price_cents, size] 
                [42, 180],
                [43, 90]
            ]
        }
    }
    
    # What the processor actually expects (Kalshi style)
    kalshi_style_data = {
        "sid": 123,
        "type": "orderbook_snapshot",
        "seq": 1,
        "bids": [  # Note: direct bids/asks, not inside 'msg'
            {"price": "0.60", "size": "100"},
            {"price": "0.59", "size": "200"}, 
            {"price": "0.58", "size": "150"}
        ],
        "asks": [
            {"price": "0.61", "size": "120"},
            {"price": "0.62", "size": "180"},
            {"price": "0.63", "size": "90"}
        ]
    }
    
    print("\n1️⃣ Testing with Polymarket-style data (should fail)...")
    print(f"Data: {json.dumps(polymarket_style_data, indent=2)}")
    
    await processor.handle_message(
        json.dumps(polymarket_style_data),
        {"ticker": "TEST_MARKET"}
    )
    
    # Check orderbook state
    orderbook = processor.get_orderbook(123)
    if orderbook:
        print(f"✅ Orderbook created: bids={len(orderbook.yes_contracts)}, asks={len(orderbook.no_contracts)}")
    else:
        print("❌ No orderbook state created")
    
    print("\n2️⃣ Testing with Kalshi-style data (should work)...")
    print(f"Data: {json.dumps(kalshi_style_data, indent=2)}")
    
    await processor.handle_message(
        json.dumps(kalshi_style_data),
        {"ticker": "TEST_MARKET"}
    )
    
    # Check orderbook state again
    orderbook = processor.get_orderbook(123)
    if orderbook:
        print(f"✅ Orderbook updated: bids={len(orderbook.yes_contracts)}, asks={len(orderbook.no_contracts)}")
        
        # Show the actual data
        print(f"📊 Best bid: {orderbook.get_yes_market_bid()}")
        print(f"📊 Best ask: {orderbook.get_no_market_bid()}")
        print(f"📊 Summary stats: {orderbook.calculate_yes_no_prices()}")
    else:
        print("❌ Still no orderbook state")
    
    print("\n🔍 Conclusion:")
    print("- The processor expects Kalshi format with bids/asks arrays containing {price, size} objects")
    print("- Your test data is in Polymarket format with yes/no arrays containing [price, size] tuples")
    print("- The data also needs to be at the root level, not inside a 'msg' object")
    
    processor.cleanup()

if __name__ == "__main__":
    asyncio.run(test_format_mismatch())