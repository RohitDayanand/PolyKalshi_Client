"""
Example usage of the MarketsManager

This demonstrates how to use the centralized manager for handling
multiple market connections with message processing and event emission.
"""

import time
import logging
from MarketsManager import create_markets_manager

# Configure logging to see the message flow
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def main():
    """Example usage of the MarketsManager."""
    
    # Create markets manager (will use dummy subscription data)
    manager = create_markets_manager()
    
    print("=== Markets Manager Status ===")
    print(manager.get_status())
    print()
    
    try:
        # Connect to Polymarket markets using subscription IDs
        print("=== Connecting to Markets ===")
        
        # Connect to election market
        success1 = manager.connect("election_2024", "polymarket")
        print(f"Election 2024 connection: {success1}")
        
        # Connect to sports market
        success2 = manager.connect("sports_event", "polymarket")
        print(f"Sports event connection: {success2}")
        
        # Try to connect to Kalshi (will show warning since not implemented)
        success3 = manager.connect("pres_election", "kalshi")
        print(f"Kalshi connection: {success3}")
        
        print()
        
        if success1 or success2:
            print("=== Manager Status After Connections ===")
            status = manager.get_status()
            for key, value in status.items():
                print(f"{key}: {value}")
            print()
            
            # Let it run for a while to see message processing
            print("=== Running for 30 seconds to process messages ===")
            print("Watch the logs for message processing...")
            
            for i in range(30):
                if i % 10 == 0:
                    print(f"Running... {i}/30 seconds")
                    status = manager.get_status()
                    print(f"Queue size: {status['queue_size']}, Processor running: {status['processor_running']}")
                time.sleep(1)
        else:
            print("No successful connections made")
            
    except KeyboardInterrupt:
        print("Interrupted by user")
    finally:
        # Always disconnect when done
        print("\n=== Shutting Down ===")
        manager.disconnect_all()
        print("Manager shut down complete")


def test_individual_connections():
    """Test individual connection management."""
    print("\n=== Testing Individual Connection Management ===")
    
    manager = create_markets_manager()
    
    # Connect one at a time
    print("Connecting to election market...")
    if manager.connect("election_2024", "polymarket"):
        print("✓ Connected successfully")
        
        # Let it run briefly
        time.sleep(5)
        
        # Check status
        status = manager.get_status()
        print(f"Active connections: {status['polymarket_connections']}")
        
        # Disconnect specific market
        print("Disconnecting election market...")
        if manager.disconnect("election_2024", "polymarket"):
            print("✓ Disconnected successfully")
        
        # Check status again
        status = manager.get_status()
        print(f"Active connections after disconnect: {status['polymarket_connections']}")
    
    manager.disconnect_all()


def test_custom_message_handler():
    """Test adding custom message handlers to the processor."""
    print("\n=== Testing Custom Message Handlers ===")
    
    manager = create_markets_manager()
    
    # Add a custom handler for 'book' event types
    def custom_orderbook_handler(message):
        platform = message.get("_platform")
        sub_id = message.get("_subscription_id")
        print(f"🔥 CUSTOM HANDLER: {platform}:{sub_id} orderbook update!")
        print(f"   Asset ID: {message.get('asset_id', 'unknown')}")
        print(f"   Market: {message.get('market', 'unknown')}")
    
    # Add the handler
    manager.processor.add_message_handler("book", custom_orderbook_handler)
    
    # Connect and let it process some messages
    if manager.connect("election_2024", "polymarket"):
        print("Connected with custom handler - watching for 15 seconds...")
        time.sleep(15)
    
    manager.disconnect_all()


if __name__ == "__main__":
    print("Markets Manager Example Usage")
    print("=" * 50)
    
    # Run main example
    main()
    
    # Test individual connections
    test_individual_connections()
    
    # Test custom message handlers
    test_custom_message_handler()
    
    print("\nExample complete!")
