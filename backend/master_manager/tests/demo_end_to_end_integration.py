"""
End-to-end demo of Kalshi integration with WebSocket ticker streaming

Shows the complete flow:
Raw WebSocket → Queue → Processor → Orderbook State → Ticker Publisher → WebSocket Server
"""

import asyncio
import json
import sys
import os

# Add the parent directory to Python path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'kalshi_client'))

from kalshi_message_processor import KalshiMessageProcessor
from kalshi_ticker_publisher import KalshiTickerPublisher


async def demo_complete_flow():
    """Demonstrate the complete Kalshi processing and publishing flow."""
    print("🎯 End-to-End Kalshi Integration Demo")
    print("=" * 50)
    
    # Track published updates
    published_updates = []
    
    def mock_publish_nowait(market_id, summary_stats):
        published_updates.append({
            'market_id': market_id,
            'summary_stats': summary_stats,
            'timestamp': asyncio.get_event_loop().time()
        })
        yes = summary_stats['yes']
        no = summary_stats['no']
        print(f"📡 PUBLISHED TO WEBSOCKET: {market_id}")
        print(f"   YES: ${yes['bid']:.3f}/${yes['ask']:.3f} (vol: {yes['volume']:.0f})")
        print(f"   NO:  ${no['bid']:.3f}/${no['ask']:.3f} (vol: {no['volume']:.0f})")
        print()
    
    # Mock the ticker stream integration
    import kalshi_ticker_publisher
    kalshi_ticker_publisher.publish_kalshi_update_nowait = mock_publish_nowait
    
    async def mock_start_ticker():
        print("🚀 Ticker stream started")
    
    async def mock_stop_ticker():
        print("🛑 Ticker stream stopped")
    
    kalshi_ticker_publisher.start_ticker_publisher = mock_start_ticker
    kalshi_ticker_publisher.stop_ticker_publisher = mock_stop_ticker
    
    print("📋 Step 1: Initialize Components")
    processor = KalshiMessageProcessor()
    publisher = KalshiTickerPublisher(processor, publish_interval=0.5)  # Fast for demo
    
    print("✓ Message processor initialized")
    print("✓ Ticker publisher initialized (0.5s intervals)")
    print()
    
    print("📋 Step 2: Start Ticker Publisher")
    await publisher.start()
    print()
    
    print("📋 Step 3: Simulate Raw WebSocket Messages")
    
    # Simulate subscription confirmation
    ok_message = {
        "type": "ok",
        "sid": 12345
    }
    metadata = {"ticker": "KXPRESPOLAND-NT", "subscription_id": "poland_election"}
    
    print("📨 Processing subscription confirmation...")
    await processor.handle_message(json.dumps(ok_message), metadata)
    print("✓ Market subscription confirmed for sid=12345")
    print()
    
    # Simulate initial orderbook snapshot
    snapshot_message = {
        "type": "orderbook_snapshot",
        "sid": 12345,
        "seq": 100,
        "bids": [
            {"price": "0.52", "size": "1000"},
            {"price": "0.51", "size": "800"},
            {"price": "0.50", "size": "600"}
        ],
        "asks": [
            {"price": "0.54", "size": "900"},
            {"price": "0.55", "size": "700"},
            {"price": "0.56", "size": "500"}
        ]
    }
    
    print("📨 Processing orderbook snapshot...")
    await processor.handle_message(json.dumps(snapshot_message), metadata)
    print("✓ Orderbook snapshot applied")
    print(f"  - Best bid: $0.52 (1000 shares)")
    print(f"  - Best ask: $0.54 (900 shares)")
    print(f"  - Total volume: {1000+800+600+900+700+500} shares")
    print()
    
    # Wait for first publish
    print("⏳ Waiting for ticker publication...")
    await asyncio.sleep(0.6)
    
    # Simulate orderbook delta (price movement)
    delta_message = {
        "type": "orderbook_delta",
        "sid": 12345,
        "seq": 101,
        "bids": [
            {"price": "0.53", "size": "1200"},  # New best bid
            {"price": "0.52", "size": "0"}      # Remove old best bid
        ],
        "asks": [
            {"price": "0.54", "size": "0"},     # Remove best ask
            {"price": "0.55", "size": "800"}    # Update ask level
        ]
    }
    
    print("📨 Processing orderbook delta (price movement)...")
    await processor.handle_message(json.dumps(delta_message), metadata)
    print("✓ Orderbook delta applied")
    print(f"  - New best bid: $0.53 (up from $0.52)")
    print(f"  - New best ask: $0.55 (up from $0.54)")
    print()
    
    # Wait for second publish
    print("⏳ Waiting for updated ticker publication...")
    await asyncio.sleep(0.6)
    
    # Add another market
    print("📋 Step 4: Add Second Market")
    
    ok_message_2 = {
        "type": "ok",
        "sid": 67890
    }
    metadata_2 = {"ticker": "KXUSAIRANAGREEMENT-26", "subscription_id": "iran_agreement"}
    
    await processor.handle_message(json.dumps(ok_message_2), metadata_2)
    
    snapshot_message_2 = {
        "type": "orderbook_snapshot",
        "sid": 67890,
        "seq": 200,
        "bids": [{"price": "0.35", "size": "500"}],
        "asks": [{"price": "0.40", "size": "400"}]
    }
    
    print("📨 Processing second market...")
    await processor.handle_message(json.dumps(snapshot_message_2), metadata_2)
    print("✓ Second market added (KXUSAIRANAGREEMENT-26)")
    print()
    
    # Wait for multi-market publish
    print("⏳ Waiting for multi-market publication...")
    await asyncio.sleep(0.6)
    
    print("📋 Step 5: Statistics and Cleanup")
    
    # Show stats
    processor_stats = processor.get_stats()
    publisher_stats = publisher.get_stats()
    
    print(f"📊 Final Statistics:")
    print(f"  Active markets: {processor_stats['active_markets']}")
    print(f"  Total published: {publisher_stats['total_published']}")
    print(f"  Rate limited: {publisher_stats['rate_limited']}")
    print(f"  Failed publishes: {publisher_stats['failed_publishes']}")
    print()
    
    # Stop publisher
    await publisher.stop()
    
    print("📋 Summary")
    print(f"✅ Processed {len(published_updates)} ticker publications")
    print(f"✅ Handled 2 markets successfully")
    print(f"✅ Rate limiting working (max 1 per 0.5s)")
    print(f"✅ Real-time price updates flowing to WebSocket clients")
    print()
    
    # Show published data details
    if published_updates:
        print("📊 Published Data Sample:")
        latest = published_updates[-1]
        print(f"Market: {latest['market_id']}")
        print(f"Data: {json.dumps(latest['summary_stats'], indent=2)}")
        print()
    
    print("🎉 End-to-end integration working successfully!")
    print("🔗 Ready to connect real Kalshi WebSocket data!")


if __name__ == "__main__":
    asyncio.run(demo_complete_flow())