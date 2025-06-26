"""
Example usage of the simplified Kalshi Client

This demonstrates how to use the abstracted client for basic connection,
message handling, and disconnection with Kalshi's WebSocket API.
"""

import time
from backend.master_manager.tests.kalshi_client import create_kalshi_client, KalshiClientConfig, KalshiClient, Environment


def on_message_received(message):
    """Handle incoming messages from Kalshi WebSocket."""
    msg_type = message.get('type', 'unknown')
    print(f"Received Kalshi message: {msg_type}")
    
    # Show different message types
    if msg_type == 'orderbook_snapshot':
        print(f"  📊 Orderbook snapshot for market: {message.get('market_ticker', 'unknown')}")
    elif msg_type == 'orderbook_delta':
        print(f"  📈 Orderbook delta for market: {message.get('market_ticker', 'unknown')}")
    elif msg_type == 'trade':
        print(f"  💰 Trade: {message.get('trade_size', 'unknown')} @ {message.get('trade_price', 'unknown')}")
    elif msg_type == 'ticker_v2':
        print(f"  📊 Ticker update: {message}")
    else:
        print(f"  🔗 Other message: {message}")


def on_connection_status(connected):
    """Handle connection status changes."""
    status = "Connected" if connected else "Disconnected"
    print(f"Kalshi connection status: {status}")


def on_error(error):
    """Handle errors."""
    print(f"Kalshi error occurred: {error}")


def main():
    """Example usage of the Kalshi client."""
    
    print("Kalshi Client Example")
    print("=" * 30)
    
    try:
        # Create client using convenience function
        client = create_kalshi_client(
            ticker="PRESWIN24",  # Example ticker - replace with actual
            channel="orderbook_delta",
            environment=Environment.DEMO,  # Use DEMO for testing
            ping_interval=30,
            log_level="INFO"
        )
        
        # Set up callbacks
        client.set_message_callback(on_message_received)
        client.set_connection_callback(on_connection_status)
        client.set_error_callback(on_error)
        
        # Connect to Kalshi
        print("Attempting to connect to Kalshi...")
        if client.connect():
            print("✅ Client started successfully")
            
            # Keep running for 60 seconds
            for i in range(60):
                print(f"Running... {i+1}/60 seconds")
                status = client.get_status()
                print(f"Status: Connected={status['connected']}, Ticker={status['ticker']}")
                time.sleep(1)
                
                if not client.is_running():
                    print("Client stopped running")
                    break
        else:
            print("❌ Failed to start client")
            print("This might be due to:")
            print("  - Missing Kalshi API credentials")
            print("  - Invalid private key file")
            print("  - Network connectivity issues")
            print("  - Invalid ticker symbol")
            
    except FileNotFoundError as e:
        print(f"❌ File not found: {e}")
        print("Make sure the Kalshi private key file exists")
    except Exception as e:
        print(f"❌ Error: {e}")
    except KeyboardInterrupt:
        print("Interrupted by user")
    finally:
        # Always disconnect when done
        if 'client' in locals():
            client.disconnect()
            print("Client disconnected")


def test_configuration():
    """Test different client configurations."""
    print("\nTesting different configurations...")
    
    configs = [
        {
            "ticker": "PRESWIN24",
            "channel": "orderbook_delta", 
            "environment": Environment.DEMO,
            "description": "Demo environment, orderbook deltas"
        },
        {
            "ticker": "RAIN-NYC",
            "channel": "trade",
            "environment": Environment.DEMO,
            "description": "Demo environment, trade events"
        }
    ]
    
    for i, config in enumerate(configs, 1):
        print(f"\nConfiguration {i}: {config['description']}")
        try:
            client_config = KalshiClientConfig(
                ticker=config["ticker"],
                channel=config["channel"],
                environment=config["environment"],
                log_level="WARNING"  # Reduce logging for testing
            )
            
            client = KalshiClient(client_config)
            status = client.get_status()
            print(f"  ✅ Config valid - Ticker: {status['ticker']}, Channel: {status['channel']}")
            
        except Exception as e:
            print(f"  ❌ Config error: {e}")


if __name__ == "__main__":
    # Test configurations first
    test_configuration()
    
    # Then run main example
    main()
