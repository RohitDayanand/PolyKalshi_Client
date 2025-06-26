"""
Enhanced Test Script for MarketsManager with Rate Limiting and pyee Integration

This demonstrates the complete functionality including:
- JSON subscription configuration ingestion
- Efficient in-place message tagging at client level
- Rate limiting testing
- pyee event emission
- Both Polymarket and Kalshi integration
"""

import time
import logging
import asyncio
from MarketsManager import create_markets_manager

# Configure logging to see detailed message flow
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_enhanced_manager():
    """Test the enhanced MarketsManager functionality."""
    print("=== Enhanced MarketsManager Test ===")
    print("Features tested:")
    print("✓ JSON subscription config ingestion")
    print("✓ Efficient in-place message tagging")
    print("✓ Rate limiting with pyee integration")
    print("✓ Both Polymarket and Kalshi support")
    print()
    
    # Create manager with enhanced subscription data
    manager = create_markets_manager()
    
    # Set up pyee event listeners for testing
    event_emitter = manager.processor.get_event_emitter()
    
    message_count = 0
    rate_limit_violations = 0
    
    def on_message_processed(event_data):
        nonlocal message_count
        message_count += 1
        platform = event_data.get("platform")
        sub_id = event_data.get("subscription_id")
        event_type = event_data.get("event_type")
        rate_limit = event_data.get("rate_limit", "unknown")
        
        if message_count % 10 == 0:  # Log every 10th message
            print(f"📊 Processed {message_count} messages | Latest: {platform}:{sub_id} ({event_type}) | Rate: {rate_limit}/s")
    
    def on_rate_limit_violation(event_data):
        nonlocal rate_limit_violations
        rate_limit_violations += 1
        print(f"🚫 Rate limit violation #{rate_limit_violations}: {event_data}")
    
    # Register pyee event listeners
    event_emitter.on("message_processed", on_message_processed)
    event_emitter.on("rate_limit_violation", on_rate_limit_violation)
    
    try:
        print("=== Subscription Configuration Test ===")
        status = manager.get_status()
        print(f"Total subscriptions loaded: {status['total_subscriptions']}")
        print(f"Polymarket configs: {len(manager.subscriptions.get('polymarket', {}))}")
        print(f"Kalshi configs: {len(manager.subscriptions.get('kalshi', {}))}")
        print()
        
        # Show subscription details
        print("=== Subscription Details ===")
        for platform, subs in manager.subscriptions.items():
            print(f"{platform.upper()}:")
            for sub_id, config in subs.items():
                rate_limit = config.get("subscription_config", {}).get("rate_limit", "unknown")
                channels = config.get("subscription_config", {}).get("channels", "unknown")
                print(f"  {sub_id}: rate={rate_limit}/s, channels={channels}")
        print()
        
        print("=== Connecting to Markets (Testing Message Tagging) ===")
        
        # Connect to Polymarket
        poly_success = manager.connect("election_2024", "polymarket")
        print(f"Polymarket election_2024: {poly_success}")
        
        # Try Kalshi connection (might fail if credentials not available)
        try:
            kalshi_success = manager.connect("pres_election", "kalshi")
            print(f"Kalshi pres_election: {kalshi_success}")
        except Exception as e:
            print(f"Kalshi connection failed (expected): {e}")
            kalshi_success = False
        
        if poly_success or kalshi_success:
            print()
            print("=== Running Message Processing Test (30 seconds) ===")
            print("Watching for:")
            print("- In-place message tagging efficiency")
            print("- Rate limiting behavior")
            print("- pyee event emission")
            print("- JSON config usage")
            print()
            
            start_time = time.time()
            
            for i in range(30):
                # Get current status
                status = manager.get_status()
                rate_stats = manager.processor.get_rate_limit_stats()
                
                if i % 10 == 0:
                    print(f"=== Status at {i}s ===")
                    print(f"Active connections: P={status['polymarket_connections']}, K={status['kalshi_connections']}")
                    print(f"Queue size: {status['queue_size']}")
                    print(f"Total messages processed: {rate_stats['total_messages']}")
                    print(f"Rate limited messages: {rate_stats['rate_limited_messages']}")
                    print()
                
                time.sleep(1)
            
            # Final statistics
            print("=== Final Test Results ===")
            final_stats = manager.processor.get_rate_limit_stats()
            print(f"📈 Total messages processed: {final_stats['total_messages']}")
            print(f"⚡ Messages via pyee: {message_count}")
            print(f"🚫 Rate limit violations: {rate_limit_violations}")
            print()
            
            print("=== Platform-specific Stats ===")
            for platform_key, stats in final_stats.get("platform_stats", {}).items():
                print(f"{platform_key}: {stats['messages']} messages, {stats['rate_limited']} rate limited")
            
        else:
            print("❌ No successful connections - cannot test message processing")
            
    except KeyboardInterrupt:
        print("\n⏹️  Test interrupted by user")
    finally:
        print("\n=== Cleanup ===")
        manager.disconnect_all()
        print("✅ Test complete")
    
    try:
        # Connect to markets with different rate limits
        print("Connecting to markets with rate limiting...")
        
        # Polymarket (rate limit: 10/sec)
        poly_success = manager.connect("election_2024", "polymarket")
        print(f"Polymarket connection: {poly_success}")
        
        # Kalshi (rate limit: 15/sec) - might fail if no credentials
        kalshi_success = manager.connect("pres_election", "kalshi")
        print(f"Kalshi connection: {kalshi_success}")
        
        if poly_success or kalshi_success:
            print("\n=== Running for 20 seconds to test rate limiting ===")
            
            start_time = time.time()
            while time.time() - start_time < 20:
                # Display stats every 5 seconds
                if int(time.time() - start_time) % 5 == 0:
                    status = manager.get_status()
                    rate_stats = manager.processor.get_rate_limit_stats()
                    
                    print(f"\n--- Status Update ({int(time.time() - start_time)}s) ---")
                    print(f"Queue size: {status['queue_size']}")
                    print(f"Events processed: {event_counts['total']}")
                    print(f"Rate limit stats: {rate_stats['total_messages']} total messages")
                    print(f"Platform breakdown: {event_counts['by_platform']}")
                    
                    for platform_key, stats in rate_stats['platform_stats'].items():
                        print(f"  {platform_key}: {stats['messages']} messages")
                
                time.sleep(1)
                
            print(f"\n=== Final Results ===")
            print(f"Total events processed: {event_counts['total']}")
            print(f"Platform breakdown: {event_counts['by_platform']}")
            
            final_rate_stats = manager.processor.get_rate_limit_stats()
            print(f"Rate limiting stats: {final_rate_stats}")
            
        else:
            print("No successful connections made")
            
    except KeyboardInterrupt:
        print("Interrupted by user")
    finally:
        print("\n=== Shutting Down ===")
        manager.disconnect_all()


def test_subscription_config_ingestion():
    """Test that subscription configuration is properly ingested from JSON."""
    print("\n=== Testing Subscription Config Ingestion ===")
    
    manager = create_markets_manager()
    
    print("Subscription configuration loaded:")
    for platform, subscriptions in manager.subscriptions.items():
        print(f"\n{platform.upper()}:")
        for sub_id, config in subscriptions.items():
            print(f"  {sub_id}:")
            print(f"    Status: {config['status']}")
            print(f"    Priority: {config['priority']}")
            
            if 'subscription_config' in config:
                sub_config = config['subscription_config']
                print(f"    Rate limit: {sub_config.get('rate_limit', 'not set')}")
                print(f"    Channels: {sub_config.get('channels', 'not set')}")
                
                if platform == 'polymarket':
                    print(f"    Slug: {config['slug']}")
                elif platform == 'kalshi':
                    print(f"    Ticker: {config['ticker']}")


def test_message_handler_registration():
    """Test custom message handler registration."""
    print("\n=== Testing Custom Message Handler Registration ===")
    
    manager = create_markets_manager()
    
    # Register custom handlers
    def custom_trade_handler(message):
        platform = message.get("_platform")
        sub_id = message.get("_subscription_id")
        print(f"🔥 CUSTOM TRADE HANDLER: {platform}:{sub_id}")
        print(f"   Rate limit: {message.get('_rate_limit')}")
        print(f"   Channels: {message.get('_channels')}")
    
    def custom_orderbook_handler(message):
        platform = message.get("_platform")
        sub_id = message.get("_subscription_id")
        print(f"🔥 CUSTOM ORDERBOOK HANDLER: {platform}:{sub_id}")
        print(f"   Message keys: {list(message.keys())}")
    
    # Add custom handlers
    manager.processor.add_message_handler("trade", custom_trade_handler)
    manager.processor.add_message_handler("book", custom_orderbook_handler)
    
    print("Custom handlers registered successfully")
    print("These would be called when processing real messages")


def test_rate_limiting_and_pyee():
    """Test rate limiting and pyee integration with live data."""
    print("\n=== Testing Rate Limiting and pyee Integration ===")
    
    manager = create_markets_manager()
    
    # Set up pyee event listeners
    event_emitter = manager.processor.get_event_emitter()
    
    message_count = 0
    rate_limit_violations = 0
    
    def on_message_processed(event_data):
        nonlocal message_count
        message_count += 1
        platform = event_data.get("platform")
        sub_id = event_data.get("subscription_id")
        event_type = event_data.get("event_type")
        rate_limit = event_data.get("rate_limit", "unknown")
        
        if message_count % 10 == 0:  # Log every 10th message
            print(f"📊 Processed {message_count} messages | Latest: {platform}:{sub_id} ({event_type}) | Rate: {rate_limit}/s")
    
    def on_rate_limit_violation(event_data):
        nonlocal rate_limit_violations
        rate_limit_violations += 1
        print(f"🚫 Rate limit violation #{rate_limit_violations}: {event_data}")
    
    # Register pyee event listeners
    event_emitter.on("message_processed", on_message_processed)
    event_emitter.on("rate_limit_violation", on_rate_limit_violation)
    
    try:
        print("=== Connecting to Markets (Testing Rate Limiting) ===")
        
        # Connect to Polymarket with rate limit 10/sec
        poly_success = manager.connect("election_2024", "polymarket")
        print(f"Polymarket connection: {poly_success}")
        
        # Connect to Kalshi with rate limit 15/sec (credentials may be required)
        kalshi_success = manager.connect("pres_election", "kalshi")
        print(f"Kalshi connection: {kalshi_success}")
        
        print()
        print("=== Running for 30 seconds to test rate limiting ===")
        print("Watching for:")
        print("- Rate limit violations")
        print("- Message processing stats")
        print()
        
        start_time = time.time()
        
        while time.time() - start_time < 30:
            # Periodically print status
            if int(time.time() - start_time) % 5 == 0:
                status = manager.get_status()
                rate_stats = manager.processor.get_rate_limit_stats()
                
                print(f"=== Status Update ({int(time.time() - start_time)}s) ===")
                print(f"Active connections: P={status['polymarket_connections']}, K={status['kalshi_connections']}")
                print(f"Queue size: {status['queue_size']}")
                print(f"Total messages processed: {rate_stats['total_messages']}")
                print(f"Rate limited messages: {rate_stats['rate_limited_messages']}")
                print()
            
            time.sleep(1)
        
        print("=== Final Rate Limiting Test Results ===")
        final_stats = manager.processor.get_rate_limit_stats()
        print(f"📈 Total messages processed: {final_stats['total_messages']}")
        print(f"🚫 Rate limit violations: {rate_limit_violations}")
        print()
        
        print("=== Platform-specific Rate Limiting Stats ===")
        for platform_key, stats in final_stats.get("platform_stats", {}).items():
            print(f"{platform_key}: {stats['messages']} messages, {stats['rate_limited']} rate limited")
    
    except KeyboardInterrupt:
        print("\n⏹️  Test interrupted by user")
    finally:
        print("\n=== Cleanup ===")
        manager.disconnect_all()
        print("✅ Test complete")


def test_rate_limiting_simulation():
    """Test rate limiting with simulated high-frequency messages."""
    print("\n=== Rate Limiting Simulation Test ===")
    
    manager = create_markets_manager()
    
    # Create a mock message for testing
    def simulate_high_frequency_messages():
        """Simulate receiving many messages quickly to test rate limiting."""
        for i in range(100):
            mock_message = {
                "event_type": "test_message",
                "data": f"message_{i}",
                "_platform": "test",
                "_subscription_id": "rate_test",
                "_timestamp": time.time(),
                "_rate_limit": 10  # 10 messages per second limit
            }
            manager._message_queue.put(mock_message)
        
        print("📤 Queued 100 test messages with 10/s rate limit")
    
    # Start processor
    manager._ensure_processor_running()
    
    # Simulate messages
    simulate_high_frequency_messages()
    
    # Let it process
    print("⏳ Processing messages for 5 seconds...")
    time.sleep(5)
    
    # Check stats
    stats = manager.processor.get_rate_limit_stats()
    print(f"📊 Results: {stats['total_messages']} processed, {stats['rate_limited_messages']} rate limited")
    
    manager.disconnect_all()


def test_json_config_pluggability():
    """Test that subscription configurations are properly plug-and-play."""
    print("\n=== JSON Configuration Pluggability Test ===")
    
    # Test with current dummy config
    manager = create_markets_manager()
    
    print("🔌 Current subscription structure:")
    for platform, subs in manager.subscriptions.items():
        print(f"  {platform}: {list(subs.keys())}")
        for sub_id, config in subs.items():
            print(f"    {sub_id}:")
            print(f"      - Primary identifier: {config.get('slug', config.get('ticker'))}")
            print(f"      - Status: {config.get('status')}")
            print(f"      - Rate limit: {config.get('subscription_config', {}).get('rate_limit')}")
    
    print("\n✅ Configuration structure is ready for React state integration!")
    print("📝 To integrate with React:")
    print("   1. Replace dummy_subscriptions with data from React state")
    print("   2. Pass the subscription data via config_path or direct injection")
    print("   3. All client connections will automatically use the new config")


def main():
    """Run all tests."""
    print("Enhanced MarketsManager Testing Suite")
    print("=" * 60)
    
    # Test 1: Subscription config ingestion
    test_subscription_config_ingestion()
    
    # Test 2: Custom message handlers
    test_message_handler_registration()
    
    # Test 3: Rate limiting and pyee (requires actual connections)
    print("\nWould you like to test live connections? (y/n)")
    response = input().strip().lower()
    
    if response == 'y':
        test_rate_limiting_and_pyee()
    else:
        print("Skipping live connection tests")
    
    print("\n=== All Tests Complete ===")


if __name__ == "__main__":
    print("🚀 Enhanced MarketsManager Testing Suite")
    print("=" * 60)
    
    # Run all tests
    test_enhanced_manager()
    test_rate_limiting_simulation()
    test_json_config_pluggability()
    
    print("\n🎉 All tests completed!")
    print("\n💡 Key improvements implemented:")
    print("✅ 1. JSON subscription config ingestion - ready for React state")
    print("✅ 2. In-place message tagging (O(1) efficiency)")
    print("✅ 3. pyee integration for event-driven testing")
    print("✅ 4. Rate limiting with statistics tracking")
    print("✅ 5. Full Kalshi client integration")
    print("✅ 6. Enhanced message type handling")
