#!/usr/bin/env python3
"""
MarketsManager with TickerProcessor Integration Example

This example demonstrates how the enhanced MarketsManager can now handle
simple tickers like "kxprespoland" and automatically expand them into
full market subscriptions.
"""

import sys
import asyncio
import logging
from pathlib import Path

# Add the backend directory to the path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import our enhanced MarketsManager
try:
    from MarketsManager import MarketsManager, create_markets_manager
    from ticker_processor import TickerProcessor
except ImportError as e:
    logger.error(f"Import error: {e}")
    logger.error("Make sure you're running this from the correct directory")
    sys.exit(1)


def demonstrate_ticker_processor():
    """Demonstrate standalone TickerProcessor functionality."""
    print("🔧 Demonstrating TickerProcessor")
    print("=" * 50)
    
    # Create a ticker processor
    processor = TickerProcessor(min_volume=10)
    
    # Example 1: Process a simple event ticker
    print("\n📊 Example 1: Simple event ticker")
    ticker = "kxprespoland"
    print(f"Input ticker: '{ticker}'")
    
    template = processor.process_ticker(ticker)
    print(f"  Platform: {template.platform}")
    print(f"  Event ticker: {template.event_ticker}")
    print(f"  Market tickers: {template.market_tickers[:3]}{'...' if len(template.market_tickers) > 3 else ''}")
    print(f"  Channels: {template.channels}")
    print(f"  Total markets found: {len(template.market_tickers)}")
    
    # Generate WebSocket subscription
    ws_subscription = processor.generate_websocket_subscription(template)
    print(f"  WebSocket subscription ready: {len(str(ws_subscription))} chars")
    
    # Example 2: Specific market ticker
    print("\n📊 Example 2: Specific market ticker")
    specific_ticker = "KXPRESPOLAND-SM"
    print(f"Input ticker: '{specific_ticker}'")
    
    template2 = processor.process_ticker(specific_ticker)
    print(f"  Platform: {template2.platform}")
    print(f"  Market tickers: {template2.market_tickers}")
    print(f"  Channels: {template2.channels}")


def demonstrate_enhanced_markets_manager():
    """Demonstrate the enhanced MarketsManager with TickerProcessor."""
    print("\n\n🎛️ Demonstrating Enhanced MarketsManager")
    print("=" * 50)
    
    # Create markets manager (includes TickerProcessor)
    manager = create_markets_manager()
    
    # Example 1: Connect using simple ticker
    print("\n🔗 Example 1: Connect with simple ticker")
    ticker = "kxprespoland"
    print(f"Connecting to: '{ticker}'")
    
    # This would normally connect, but we'll just show the process
    print("  1. TickerProcessor detects this as Kalshi event ticker")
    print("  2. Auto-discovers all Poland Presidential markets")
    print("  3. Creates dynamic subscription with multiple market tickers")
    print("  4. Connects to WebSocket with full subscription")
    
    # Simulate the discovery without actual connection
    markets = manager.discover_markets(ticker, "kalshi")
    print(f"  Would connect to {len(markets)} markets:")
    for market in markets[:3]:
        print(f"    • {market['ticker']}: Volume {market['volume']}")
    
    # Example 2: Get ticker processor statistics
    print("\n📈 Example 2: Ticker processor statistics")
    stats = manager.get_ticker_processor_stats()
    print(f"  Cache entries: {stats['total_entries']}")
    print(f"  Fresh entries: {stats['fresh_entries']}")
    print(f"  Min volume threshold: {stats['min_volume_threshold']}")
    
    # Example 3: Show dynamic subscription structure
    print("\n⚙️ Example 3: Dynamic subscription structure")
    print("  Traditional subscription (old way):")
    print("    {")
    print("      'ticker': 'PRESWIN24',")
    print("      'channels': ['orderbook_delta']")
    print("    }")
    print()
    print("  Enhanced subscription (new way):")
    print("    {")
    print("      'tickers': ['KXPRESPOLAND-SM', 'KXPRESPOLAND-MJ', ...],")
    print("      'event_ticker': 'POLAND-PRES',")
    print("      'channels': ['orderbook_delta', 'trade', 'ticker_v2'],")
    print("      'is_dynamic': true,")
    print("      'discovered_markets': 15")
    print("    }")


def show_usage_examples():
    """Show practical usage examples."""
    print("\n\n💡 Practical Usage Examples")
    print("=" * 50)
    
    print("""
# Example 1: Simple connection with auto-discovery
manager = create_markets_manager()
success = manager.connect_with_ticker("kxprespoland")
if success:
    print("Connected to all Poland Presidential markets")

# Example 2: Discover markets before connecting
markets = manager.discover_markets("kxprespoland")
high_volume_markets = [m for m in markets if m['volume'] > 50]
print(f"Found {len(high_volume_markets)} high-volume markets")

# Example 3: Connect to specific market
manager.connect_with_ticker("KXPRESPOLAND-SM", subscription_id="poland_sm_only")

# Example 4: Refresh dynamic subscriptions (re-discover markets)
manager.refresh_dynamic_subscription("kalshi_kxprespoland_123", "kalshi")

# Example 5: Monitor multiple events
events = ["kxprespoland", "kxusair", "kxelection"]
for event in events:
    manager.connect_with_ticker(event)

# Example 6: Get comprehensive status
status = manager.get_status()
print(f"Connected to {status['kalshi_connections']} Kalshi markets")
print(f"Ticker processor cache: {status['ticker_processor_stats']}")
""")


def show_websocket_message_format():
    """Show what the actual WebSocket messages look like."""
    print("\n\n📡 WebSocket Message Format")
    print("=" * 50)
    
    processor = TickerProcessor()
    
    print("Input: 'kxprespoland'")
    print("Generated WebSocket subscription:")
    
    try:
        template = processor.process_ticker("kxprespoland", "kalshi")
        ws_message = processor.generate_websocket_subscription(template)
        
        # Pretty print the message
        import json
        print(json.dumps(ws_message, indent=2))
        
    except Exception as e:
        print(f"Error generating message: {e}")
        # Show example format
        print("""
{
  "id": 1624123456,
  "cmd": "subscribe",
  "params": {
    "channels": ["orderbook_delta", "trade", "ticker_v2"],
    "market_tickers": [
      "KXPRESPOLAND-SM",
      "KXPRESPOLAND-MJ", 
      "KXPRESPOLAND-SH",
      "KXPRESPOLAND-RT",
      "KXPRESPOLAND-KN"
    ]
  },
  "_metadata": {
    "event_ticker": "POLAND-PRES",
    "discovered_markets": 5,
    "subscription_params": {
      "rate_limit": 20,
      "discovered_markets": 5,
      "high_volume_markets": 5
    }
  }
}
""")


def main():
    """Run all demonstrations."""
    print("🚀 MarketsManager + TickerProcessor Integration Demo")
    print("=" * 60)
    
    try:
        demonstrate_ticker_processor()
        demonstrate_enhanced_markets_manager()
        show_usage_examples()
        show_websocket_message_format()
        
        print("\n\n✅ Demo completed!")
        print("\nKey benefits of the TickerProcessor integration:")
        print("• 🎯 Simple ticker input: 'kxprespoland' → full event subscription")
        print("• 🔍 Auto-discovery: Finds all related markets automatically") 
        print("• 📈 Volume filtering: Only subscribes to active markets")
        print("• 💾 Caching: Efficient market discovery with caching")
        print("• 🔄 Dynamic updates: Refresh subscriptions as markets change")
        print("• 🎛️ Flexible: Supports both event-level and specific market tickers")
        
    except KeyboardInterrupt:
        print("\n\n⏹️  Demo interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
