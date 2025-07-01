"""
Example usage of Kalshi message processor with bid/ask calculation
"""

import asyncio
import json
import sys
import os

# Add the parent directory to Python path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'kalshi_client'))

from kalshi_message_processor import KalshiMessageProcessor


async def demo_kalshi_bid_ask():
    """Demonstrate bid/ask calculation for Kalshi markets."""
    print("🎯 Kalshi Bid/Ask Calculation Demo\n")
    
    processor = KalshiMessageProcessor()
    
    # Simulate receiving an orderbook snapshot
    snapshot_message = {
        "type": "orderbook_snapshot",
        "sid": 12345,
        "seq": 100,
        "bids": [
            {"price": "0.52", "size": "500"},   # Best bid at 52 cents
            {"price": "0.51", "size": "300"},
            {"price": "0.50", "size": "200"}
        ],
        "asks": [
            {"price": "0.54", "size": "400"},   # Best ask at 54 cents  
            {"price": "0.55", "size": "250"},
            {"price": "0.56", "size": "150"}
        ]
    }
    
    metadata = {"ticker": "KXPRESPOLAND-NT", "subscription_id": "poland_election"}
    
    print("📊 Processing orderbook snapshot...")
    await processor.handle_message(json.dumps(snapshot_message), metadata)
    
    # Get summary stats for this market
    summary_stats = processor.get_summary_stats(12345)
    
    if summary_stats:
        print(f"✅ Market sid=12345 Summary Stats:")
        print(f"   YES side:")
        print(f"     Bid: ${summary_stats['yes']['bid']:.2f}")
        print(f"     Ask: ${summary_stats['yes']['ask']:.2f}")
        print(f"     Volume: {summary_stats['yes']['volume']:.0f}")
        
        print(f"   NO side:")
        print(f"     Bid: ${summary_stats['no']['bid']:.2f}")
        print(f"     Ask: ${summary_stats['no']['ask']:.2f}")
        print(f"     Volume: {summary_stats['no']['volume']:.0f}")
        
        print(f"\n💡 Explanation:")
        print(f"   YES prices = direct orderbook prices")
        print(f"   NO prices = inverse (1 - YES prices)")
        print(f"   This is because YES + NO = $1.00 in prediction markets")
        
        # Show the math
        yes_bid = summary_stats['yes']['bid']
        yes_ask = summary_stats['yes']['ask']
        print(f"\n🧮 Price calculation:")
        print(f"   YES bid = {yes_bid:.2f} → NO ask = 1 - {yes_bid:.2f} = {1-yes_bid:.2f}")
        print(f"   YES ask = {yes_ask:.2f} → NO bid = 1 - {yes_ask:.2f} = {1-yes_ask:.2f}")
    
    # Simulate a delta update
    print(f"\n📈 Applying orderbook delta...")
    delta_message = {
        "type": "orderbook_delta", 
        "sid": 12345,
        "seq": 101,
        "bids": [
            {"price": "0.53", "size": "600"}   # New best bid at 53 cents
        ],
        "asks": [
            {"price": "0.54", "size": "0"}     # Remove the 54 cent ask
        ]
    }
    
    await processor.handle_message(json.dumps(delta_message), metadata)
    
    # Get updated stats
    updated_stats = processor.get_summary_stats(12345)
    if updated_stats:
        print(f"✅ Updated Market Stats:")
        print(f"   YES bid: ${updated_stats['yes']['bid']:.2f} (was ${summary_stats['yes']['bid']:.2f})")
        print(f"   YES ask: ${updated_stats['yes']['ask']:.2f} (was ${summary_stats['yes']['ask']:.2f})")
        print(f"   NO bid: ${updated_stats['no']['bid']:.2f} (was ${summary_stats['no']['bid']:.2f})")
        print(f"   NO ask: ${updated_stats['no']['ask']:.2f} (was ${summary_stats['no']['ask']:.2f})")
    
    # Show how to get all markets
    print(f"\n📊 All active markets:")
    all_stats = processor.get_all_summary_stats()
    for sid, stats in all_stats.items():
        print(f"   Market {sid}: YES ${stats['yes']['bid']:.2f}/${stats['yes']['ask']:.2f}, "
              f"NO ${stats['no']['bid']:.2f}/${stats['no']['ask']:.2f}")


if __name__ == "__main__":
    asyncio.run(demo_kalshi_bid_ask())