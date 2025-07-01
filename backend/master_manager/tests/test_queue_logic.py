"""
Simple test to verify queue processing logic works correctly.
Tests both Kalshi and Polymarket queues independently.
"""

import asyncio
import json
import sys
import os

# Add the current directory to Python path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.master_manager.kalshi_client.kalshi_queue import KalshiQueue
from backend.master_manager.polymarket_client.polymarket_queue import PolymarketQueue

async def test_kalshi_queue():
    """Test Kalshi queue processing"""
    print("🔵 Testing Kalshi Queue...")
    
    # Track processed messages
    processed_messages = []
    
    def kalshi_handler(raw_message, metadata):
        try:
            decoded = json.loads(raw_message)
            processed_messages.append({
                "type": decoded.get("type"),
                "ticker": metadata.get("ticker"),
                "platform": metadata.get("platform"),
                "raw_length": len(raw_message)
            })
            print(f"  ✅ Kalshi processed: {decoded.get('type')} from {metadata.get('ticker')}")
        except Exception as e:
            print(f"  ❌ Kalshi handler error: {e}")
    
    # Create and start queue
    queue = KalshiQueue(max_queue_size=10)
    queue.set_message_handler(kalshi_handler)
    await queue.start()
    
    # Send test messages mimicking real Kalshi data
    test_messages = [
        ('{"type":"subscribed","id":1,"msg":{"channel":"orderbook_delta","sid":1}}', 
         {"ticker": "KXUSAIRANAGREEMENT-26", "platform": "kalshi", "channel": "orderbook_delta"}),
        ('{"type":"orderbook_snapshot","sid":1,"seq":1,"msg":{"market_ticker":"KXUSAIRANAGREEMENT-26","yes":[[1,1000]],"no":[[2,500]]}}', 
         {"ticker": "KXUSAIRANAGREEMENT-26", "platform": "kalshi", "channel": "orderbook_delta"}),
        ('{"type":"orderbook_delta","sid":1,"seq":2,"msg":{"market_ticker":"KXUSAIRANAGREEMENT-26","delta":{"yes":[[1,1100]],"no":[]}}}', 
         {"ticker": "KXUSAIRANAGREEMENT-26", "platform": "kalshi", "channel": "orderbook_delta"})
    ]
    
    print("  📤 Sending Kalshi test messages...")
    for i, (raw_msg, metadata) in enumerate(test_messages, 1):
        print(f"    Sending message {i}/{len(test_messages)}")
        await queue.put_message(raw_msg, metadata)
        await asyncio.sleep(0.2)  # Small delay to see processing
    
    # Wait for processing
    await asyncio.sleep(1)
    
    # Results
    stats = queue.get_stats()
    print(f"  📊 Kalshi Results:")
    print(f"    Messages sent: {len(test_messages)}")
    print(f"    Messages processed: {len(processed_messages)}")
    print(f"    Queue size: {stats['queue_size']}")
    print(f"    Queue running: {stats['is_running']}")
    
    await queue.stop()
    return len(processed_messages) == len(test_messages)

async def test_polymarket_queue():
    """Test Polymarket queue processing"""
    print("\n🟠 Testing Polymarket Queue...")
    
    # Track processed messages
    processed_messages = []
    
    def polymarket_handler(raw_message, metadata):
        try:
            decoded = json.loads(raw_message)
            # Handle both single messages and arrays
            messages = decoded if isinstance(decoded, list) else [decoded]
            for msg in messages:
                processed_messages.append({
                    "type": msg.get("type"),
                    "slug": metadata.get("slug"),
                    "platform": metadata.get("platform"),
                    "raw_length": len(raw_message)
                })
                print(f"  ✅ Polymarket processed: {msg.get('type')} from {metadata.get('slug')}")
        except Exception as e:
            print(f"  ❌ Polymarket handler error: {e}")
    
    # Create and start queue
    queue = PolymarketQueue(max_queue_size=10)
    queue.set_message_handler(polymarket_handler)
    await queue.start()
    
    # Send test messages mimicking real Polymarket data
    test_messages = [
        ('[{"type":"book","data":{"asset_id":"1234","bids":[["0.45","100"]],"asks":[["0.55","200"]]}}]', 
         {"slug": "test-market", "platform": "polymarket", "token_id": ["1234"]}),
        ('{"type":"price_change","data":{"asset_id":"1234","price":"0.46"}}', 
         {"slug": "test-market", "platform": "polymarket", "token_id": ["1234"]}),
        ('[{"type":"book","data":{"asset_id":"1234","bids":[["0.46","150"]],"asks":[["0.54","180"]]}},{"type":"trade","data":{"price":"0.46","size":"50"}}]', 
         {"slug": "test-market", "platform": "polymarket", "token_id": ["1234"]})
    ]
    
    print("  📤 Sending Polymarket test messages...")
    for i, (raw_msg, metadata) in enumerate(test_messages, 1):
        print(f"    Sending message {i}/{len(test_messages)}")
        await queue.put_message(raw_msg, metadata)
        await asyncio.sleep(0.2)  # Small delay to see processing
    
    # Wait for processing
    await asyncio.sleep(1)
    
    # Results
    stats = queue.get_stats()
    print(f"  📊 Polymarket Results:")
    print(f"    Messages sent: {len(test_messages)}")
    print(f"    Individual messages processed: {len(processed_messages)}")
    print(f"    Queue size: {stats['queue_size']}")
    print(f"    Queue running: {stats['is_running']}")
    
    await queue.stop()
    return len(processed_messages) > 0  # At least some messages processed

async def main():
    """Run all queue tests"""
    print("🧪 Starting Queue Logic Tests\n")
    
    try:
        # Test both queues
        kalshi_success = await test_kalshi_queue()
        polymarket_success = await test_polymarket_queue()
        
        # Overall results
        print(f"\n📋 Final Results:")
        print(f"  Kalshi Queue: {'✅ PASS' if kalshi_success else '❌ FAIL'}")
        print(f"  Polymarket Queue: {'✅ PASS' if polymarket_success else '❌ FAIL'}")
        
        overall_success = kalshi_success and polymarket_success
        print(f"\n🎯 Overall: {'✅ ALL TESTS PASSED' if overall_success else '❌ SOME TESTS FAILED'}")
        
        return overall_success
        
    except Exception as e:
        print(f"❌ Test error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)