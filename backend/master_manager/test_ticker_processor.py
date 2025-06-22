#!/usr/bin/env python3
"""
Test script for TickerProcessor functionality

This script demonstrates how to use the TickerProcessor to translate
simple tickers into full subscription messages.
"""

import sys
import json
from pathlib import Path

# Add the backend directory to the path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from ticker_processor import TickerProcessor, process_ticker_to_subscription, discover_markets_for_event


def test_ticker_processing():
    """Test ticker processing functionality."""
    print("🔧 Testing Ticker Processor")
    print("=" * 50)
    
    # Initialize processor
    processor = TickerProcessor(min_volume=5)
    
    # Test cases
    test_tickers = [
        ("kxprespoland", None),           # Event ticker, auto-detect platform
        ("kxprespoland", "kalshi"),       # Event ticker, explicit platform
        ("KXPRESPOLAND-SM", "kalshi"),    # Specific market ticker
        ("poland-presidential-election", "polymarket"),  # Polymarket slug
    ]
    
    for ticker, platform in test_tickers:
        print(f"\n📊 Processing ticker: '{ticker}' (platform: {platform or 'auto-detect'})")
        print("-" * 40)
        
        try:
            # Process ticker to get template
            template = processor.process_ticker(ticker, platform)
            
            print(f"Platform: {template.platform}")
            print(f"Channels: {template.channels}")
            print(f"Market Tickers: {template.market_tickers}")
            print(f"Event Ticker: {template.event_ticker}")
            print(f"Subscription Params: {template.subscription_params}")
            
            # Generate WebSocket subscription message
            ws_message = processor.generate_websocket_subscription(template)
            print(f"WebSocket Message: {json.dumps(ws_message, indent=2)}")
            
        except Exception as e:
            print(f"❌ Error processing ticker '{ticker}': {e}")


def test_market_discovery():
    """Test market discovery functionality."""
    print("\n\n🔍 Testing Market Discovery")
    print("=" * 50)
    
    test_events = [
        "POLAND-PRES",
        "US-AIR",
        "PRESIDENT-2024"
    ]
    
    for event_ticker in test_events:
        print(f"\n🎯 Discovering markets for: '{event_ticker}'")
        print("-" * 40)
        
        try:
            markets = discover_markets_for_event(event_ticker)
            
            if markets:
                print(f"Found {len(markets)} markets:")
                for market in markets[:3]:  # Show first 3
                    print(f"  • {market['ticker']}: {market['title'][:50]}... (Volume: {market['volume']})")
                
                if len(markets) > 3:
                    print(f"  ... and {len(markets) - 3} more markets")
            else:
                print("No markets found")
                
        except Exception as e:
            print(f"❌ Error discovering markets for '{event_ticker}': {e}")


def test_quick_functions():
    """Test the convenience functions."""
    print("\n\n⚡ Testing Quick Functions")
    print("=" * 50)
    
    # Test quick subscription generation
    ticker = "kxprespoland"
    print(f"\n📡 Quick subscription for: '{ticker}'")
    print("-" * 40)
    
    try:
        subscription_msg = process_ticker_to_subscription(ticker)
        print(f"Generated subscription: {json.dumps(subscription_msg, indent=2)}")
    except Exception as e:
        print(f"❌ Error generating quick subscription: {e}")


def test_cache_functionality():
    """Test caching functionality."""
    print("\n\n💾 Testing Cache Functionality")
    print("=" * 50)
    
    processor = TickerProcessor()
    
    # Get initial cache stats
    print("Initial cache stats:")
    stats = processor.get_market_cache_stats()
    print(f"  Total entries: {stats['total_entries']}")
    print(f"  Fresh entries: {stats['fresh_entries']}")
    print(f"  Stale entries: {stats['stale_entries']}")
    
    # Process a ticker (should populate cache)
    print("\nProcessing ticker to populate cache...")
    try:
        template = processor.process_ticker("kxprespoland", "kalshi")
        print(f"Processed successfully, found {len(template.market_tickers)} markets")
    except Exception as e:
        print(f"Error processing: {e}")
    
    # Check cache stats again
    print("\nCache stats after processing:")
    stats = processor.get_market_cache_stats()
    print(f"  Total entries: {stats['total_entries']}")
    print(f"  Fresh entries: {stats['fresh_entries']}")
    print(f"  Stale entries: {stats['stale_entries']}")
    
    # Clear cache
    print("\nClearing cache...")
    processor.clear_cache()
    
    # Final cache stats
    print("Cache stats after clearing:")
    stats = processor.get_market_cache_stats()
    print(f"  Total entries: {stats['total_entries']}")


def main():
    """Run all tests."""
    print("🚀 TickerProcessor Test Suite")
    print("=" * 60)
    
    try:
        test_ticker_processing()
        test_market_discovery()
        test_quick_functions()
        test_cache_functionality()
        
        print("\n\n✅ All tests completed!")
        
    except KeyboardInterrupt:
        print("\n\n⏹️  Tests interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Test suite failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
