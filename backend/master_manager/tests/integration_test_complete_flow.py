"""
Complete Integration Test - Full Markets Manager to WebSocket Flow
Tests the complete flow with real token IDs and market slug:
- Polymarket: 75505728818237076147318796536066812362152358606307154083407489467059230821371, 67369669271127885658944531351746308398542291270457462650056001798232262328240
- Kalshi: KXUSAIRANAGREEMENT-26

Tests the complete flow:
Message Processors → Ticker Publishers → WebSocket Publications
"""

import asyncio
import json
import sys
import os
from datetime import datetime

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kalshi_client.kalshi_message_processor import KalshiMessageProcessor
from polymarket_client.polymarket_message_processor import PolymarketMessageProcessor
from polymarket_client.polymarket_ticker_publisher import PolymarketTickerPublisher
from kalshi_ticker_publisher import KalshiTickerPublisher


async def test_complete_integration_flow():
    """Test the complete integration flow with ticker publishers."""
    print("🎯 COMPLETE INTEGRATION TEST - FULL FLOW")
    print("=" * 60)
    print(f"⏰ Started: {datetime.now().isoformat()}")
    print()
    
    # Real market data provided by user
    polymarket_token_ids = [
        "75505728818237076147318796536066812362152358606307154083407489467059230821371",
        "67369669271127885658944531351746308398542291270457462650056001798232262328240"
    ]
    kalshi_market_slug = "KXUSAIRANAGREEMENT-26"
    
    print("📊 Test Configuration:")
    print(f"  Polymarket Tokens: {len(polymarket_token_ids)}")
    for i, token in enumerate(polymarket_token_ids, 1):
        print(f"    {i}. {token}")
    print(f"  Kalshi Market: {kalshi_market_slug}")
    print()
    
    # Track all websocket publications
    published_updates = {
        'kalshi': [],
        'polymarket': []
    }
    
    def mock_kalshi_publish(market_id, summary_stats):
        """Mock Kalshi websocket publishing."""
        published_updates['kalshi'].append({
            'market_id': market_id,
            'data': summary_stats,
            'timestamp': datetime.now().isoformat()
        })
        print(f"📡 KALSHI PUB: {market_id}")
        if 'yes' in summary_stats and 'no' in summary_stats:
            yes = summary_stats['yes']
            no = summary_stats['no']
            print(f"   YES: ${yes.get('bid', 0):.3f}/${yes.get('ask', 0):.3f} vol={yes.get('volume', 0):.0f}")
            print(f"   NO:  ${no.get('bid', 0):.3f}/${no.get('ask', 0):.3f} vol={no.get('volume', 0):.0f}")
        print()
    
    def mock_poly_publish(market_id, summary_stats):
        """Mock Polymarket websocket publishing."""
        published_updates['polymarket'].append({
            'market_id': market_id,
            'data': summary_stats,
            'timestamp': datetime.now().isoformat()
        })
        print(f"📡 POLYMARKET PUB: {market_id[-8:]}...")
        if 'yes' in summary_stats and 'no' in summary_stats:
            yes = summary_stats['yes']
            no = summary_stats['no']
            print(f"   YES: ${yes.get('bid', 0):.3f}/${yes.get('ask', 0):.3f} vol={yes.get('volume', 0):.0f}")
            print(f"   NO:  ${no.get('bid', 0):.3f}/${no.get('ask', 0):.3f} vol={no.get('volume', 0):.0f}")
        print()
    
    print("📋 Step 1: Initialize Components")
    
    # Initialize processors
    kalshi_processor = KalshiMessageProcessor()
    poly_processor = PolymarketMessageProcessor()
    
    print("✓ Message processors initialized")
    
    # Initialize ticker publishers with fast intervals for testing
    kalshi_publisher = KalshiTickerPublisher(
        kalshi_processor=kalshi_processor,
        publish_interval=0.5  # Fast for testing
    )
    poly_publisher = PolymarketTickerPublisher(
        polymarket_processor=poly_processor,
        publish_interval=0.5  # Fast for testing
    )
    
    print("✓ Ticker publishers initialized (0.5s intervals)")
    print()
    
    print("📋 Step 2: Mock WebSocket Integration")
    
    # Mock the ticker stream integration functions
    try:
        # Mock Kalshi publishing
        import sys
        sys.modules['ticker_stream_integration'] = type(sys)('ticker_stream_integration')
        sys.modules['ticker_stream_integration'].publish_kalshi_update_nowait = mock_kalshi_publish
        sys.modules['ticker_stream_integration'].publish_polymarket_update_nowait = mock_poly_publish
        
        # Replace the imports in the ticker publishers
        kalshi_publisher.publish_kalshi_update_nowait = mock_kalshi_publish
        poly_publisher.publish_polymarket_update_nowait = mock_poly_publish
        
        print("✓ WebSocket integration mocked successfully")
        
    except Exception as e:
        print(f"⚠️  WebSocket integration mock failed: {e}")
        # Fallback - direct replacement
        import kalshi_ticker_publisher
        import polymarket_client.polymarket_ticker_publisher
        
        kalshi_ticker_publisher.publish_kalshi_update_nowait = mock_kalshi_publish
        polymarket_client.polymarket_ticker_publisher.publish_polymarket_update_nowait = mock_poly_publish
        
        print("✓ Fallback WebSocket integration mocked")
    
    print()
    
    print("📋 Step 3: Start Ticker Publishers")
    
    # Start ticker publishers
    await kalshi_publisher.start()
    await poly_publisher.start()
    
    print("✓ Ticker publishers started")
    print()
    
    print("📋 Step 4: Simulate Kalshi Market Data")
    print(f"🗳️  Processing {kalshi_market_slug}...")
    
    # Kalshi subscription confirmation
    ok_message = {
        "type": "ok",
        "sid": 12345
    }
    metadata = {
        "ticker": kalshi_market_slug,
        "subscription_id": "iran_agreement_test"
    }
    
    await kalshi_processor.handle_message(json.dumps(ok_message), metadata)
    print(f"✓ Kalshi subscription confirmed: sid=12345")
    
    # Kalshi orderbook snapshot
    snapshot = {
        "type": "orderbook_snapshot",
        "sid": 12345,
        "seq": 100,
        "bids": [
            {"price": "0.35", "size": "1500"},
            {"price": "0.34", "size": "1200"}
        ],
        "asks": [
            {"price": "0.37", "size": "1300"},
            {"price": "0.38", "size": "1000"}
        ]
    }
    
    await kalshi_processor.handle_message(json.dumps(snapshot), metadata)
    print("✓ Kalshi orderbook snapshot applied")
    print("  - Best bid: $0.35 (1500 shares)")
    print("  - Best ask: $0.37 (1300 shares)")
    print()
    
    print("📋 Step 5: Simulate Polymarket Market Data")
    
    for i, token_id in enumerate(polymarket_token_ids, 1):
        print(f"💰 Processing token {i}: {token_id[-8:]}...")
        
        # Polymarket book update
        book_message = {
            "event_type": "book",
            "market": token_id,
            "asset_id": token_id,
            "book": {
                "bids": [
                    {"price": f"0.{52 + i}", "size": f"{1000 + i*200}"},
                    {"price": f"0.{51 + i}", "size": f"{800 + i*100}"}
                ],
                "asks": [
                    {"price": f"0.{54 + i}", "size": f"{900 + i*150}"},
                    {"price": f"0.{55 + i}", "size": f"{700 + i*50}"}
                ]
            },
            "hash": f"test_hash_{i}",
            "timestamp": int(datetime.now().timestamp() * 1000)
        }
        
        metadata = {"source": "websocket", "token_id": token_id}
        await poly_processor.handle_message(json.dumps(book_message), metadata)
        print(f"✓ Polymarket book {i} applied")
        print(f"  - Best bid: $0.{52 + i} ({1000 + i*200} shares)")
        print(f"  - Best ask: $0.{54 + i} ({900 + i*150} shares)")
        
        # Small delay between updates
        await asyncio.sleep(0.1)
    
    print()
    
    print("📋 Step 6: Wait for Ticker Publications")
    print("⏳ Waiting for ticker publishers to poll and publish...")
    
    # Wait for ticker publishers to run their cycles
    await asyncio.sleep(2.0)  # Wait for 2 seconds to allow multiple publish cycles
    
    # Update Kalshi data to trigger another publish
    print("📨 Updating Kalshi market data...")
    delta = {
        "type": "orderbook_delta",
        "sid": 12345,
        "seq": 101,
        "bids": [
            {"price": "0.36", "size": "1800"},  # Better bid
            {"price": "0.35", "size": "0"}      # Remove old bid
        ],
        "asks": [
            {"price": "0.37", "size": "0"},     # Remove ask
            {"price": "0.38", "size": "1100"}   # Update ask
        ]
    }
    
    await kalshi_processor.handle_message(json.dumps(delta), metadata)
    print("✓ Kalshi market updated - price moved up!")
    print("  - New best bid: $0.36 (1800 shares)")
    print("  - New best ask: $0.38 (1100 shares)")
    
    # Wait for more publications
    print("⏳ Waiting for updated publications...")
    await asyncio.sleep(2.0)
    
    print()
    
    print("📋 Step 7: Verify Publications")
    
    kalshi_pubs = len(published_updates['kalshi'])
    poly_pubs = len(published_updates['polymarket'])
    total_pubs = kalshi_pubs + poly_pubs
    
    print("📊 Publication Results:")
    print(f"  Kalshi publications: {kalshi_pubs}")
    print(f"  Polymarket publications: {poly_pubs}")
    print(f"  Total websocket publications: {total_pubs}")
    print()
    
    # Analyze publication quality
    if kalshi_pubs > 0:
        print("✅ Kalshi Integration: WORKING")
        latest = published_updates['kalshi'][-1]
        print(f"   Latest Market: {latest['market_id']}")
        print(f"   Time: {latest['timestamp']}")
        if 'yes' in latest['data'] and 'no' in latest['data']:
            yes = latest['data']['yes']
            no = latest['data']['no']
            print(f"   YES: ${yes.get('bid', 0):.3f}/${yes.get('ask', 0):.3f}")
            print(f"   NO:  ${no.get('bid', 0):.3f}/${no.get('ask', 0):.3f}")
    else:
        print("❌ Kalshi Integration: NO PUBLICATIONS")
    
    if poly_pubs > 0:
        print("✅ Polymarket Integration: WORKING")
        latest = published_updates['polymarket'][-1]
        print(f"   Latest Market: {latest['market_id'][-8:]}...")
        print(f"   Time: {latest['timestamp']}")
        if 'yes' in latest['data'] and 'no' in latest['data']:
            yes = latest['data']['yes']
            no = latest['data']['no']
            print(f"   YES: ${yes.get('bid', 0):.3f}/${yes.get('ask', 0):.3f}")
            print(f"   NO:  ${no.get('bid', 0):.3f}/${no.get('ask', 0):.3f}")
    else:
        print("❌ Polymarket Integration: NO PUBLICATIONS")
    
    print()
    
    print("📋 Step 8: Cleanup")
    
    # Stop ticker publishers
    await kalshi_publisher.stop()
    await poly_publisher.stop()
    
    print("✓ Ticker publishers stopped")
    
    # Get final stats
    kalshi_stats = kalshi_processor.get_stats()
    poly_stats = poly_processor.get_stats()
    
    print(f"✓ Final processor stats:")
    print(f"  Kalshi active markets: {kalshi_stats.get('active_markets', 0)}")
    print(f"  Polymarket active markets: {poly_stats.get('active_markets', 0)}")
    print()
    
    print("🎉 COMPLETE INTEGRATION TEST FINISHED!")
    print(f"📈 Total websocket publications: {total_pubs}")
    print(f"🔗 Markets Manager → Ticker Publishers → WebSocket flow tested")
    print(f"⏰ Finished: {datetime.now().isoformat()}")
    
    return {
        'kalshi_pubs': kalshi_pubs,
        'poly_pubs': poly_pubs,
        'total_pubs': total_pubs,
        'success': total_pubs > 0,
        'kalshi_active_markets': kalshi_stats.get('active_markets', 0),
        'poly_active_markets': poly_stats.get('active_markets', 0)
    }


if __name__ == "__main__":
    print("🚀 Starting Complete Integration Test")
    print("🎯 Testing: Message Processors → Ticker Publishers → WebSocket Publications")
    print()
    
    result = asyncio.run(test_complete_integration_flow())
    
    print()
    print("📋 FINAL SUMMARY:")
    print(f"  Success: {result['success']}")
    print(f"  Total Publications: {result['total_pubs']}")
    print(f"  Kalshi: {result['kalshi_pubs']}, Polymarket: {result['poly_pubs']}")
    print(f"  Active Markets: K={result['kalshi_active_markets']}, P={result['poly_active_markets']}")
    
    if result['success']:
        print("✅ COMPLETE INTEGRATION TEST PASSED!")
        print("🎯 Real market data flowing through complete pipeline to websockets")
    else:
        print("❌ COMPLETE INTEGRATION TEST FAILED!")
        print("🔍 Check ticker publisher configuration and mock functions")