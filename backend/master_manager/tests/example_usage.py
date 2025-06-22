"""
Example usage of the simplified Polymarket Client

This demonstrates how to use the abstracted client for basic connection,
message handling, and disconnection.
"""

import time
from polymarket_client import create_polymarket_client, PolymarketClientConfig, PolymarketClient


def on_message_received(message):
    """Handle incoming messages from Polymarket WebSocket."""
    print(f"Received message: {message.get('event_type', 'unknown')} - {message}")


def on_connection_status(connected):
    """Handle connection status changes."""
    status = "Connected" if connected else "Disconnected"
    print(f"Connection status: {status}")


def on_error(error):
    """Handle errors."""
    print(f"Error occurred: {error}")


def main():
    """Example usage of the Polymarket client."""
    
    # Create client using convenience function
    client = create_polymarket_client(
        slug="poland-presidential-election",  # Your market slug
        ping_interval=30,
        log_level="INFO"
    )
    
    # Set up callbacks
    client.set_message_callback(on_message_received)
    client.set_connection_callback(on_connection_status)
    client.set_error_callback(on_error)
    
    try:
        # Connect to Polymarket
        if client.connect():
            print("Client started successfully")
            
            # Keep running for 60 seconds
            for i in range(60):
                print(f"Running... {i+1}/60 seconds")
                print(f"Status: {client.get_status()}")
                time.sleep(1)
                
                if not client.is_running():
                    print("Client stopped running")
                    break
        else:
            print("Failed to start client")
            
    except KeyboardInterrupt:
        print("Interrupted by user")
    finally:
        # Always disconnect when done
        client.disconnect()
        print("Client disconnected")


if __name__ == "__main__":
    main()
