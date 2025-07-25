"""
Real integration test for Polymarket WebSocket unsubscribing functionality.

This test actually connects to Polymarket's WebSocket server to verify
that unsubscribing works by calling subscribe() with fewer token_ids.
"""

import asyncio
import json
import logging
import sys
import os
from datetime import datetime

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from polymarket_client import create_polymarket_client, PolymarketClient, PolymarketClientConfig


class MessageCapture:
    """Helper class to capture and analyze WebSocket messages."""
    
    def __init__(self):
        self.messages = []
        self.token_maps = []
        
    async def message_callback(self, message, metadata):
        """Capture messages for analysis."""
        timestamp = datetime.now().isoformat()
        
        if metadata.get("event_type") == "token_map":
            self.token_maps.append({
                "timestamp": timestamp,
                "token_map": json.loads(message),
                "metadata": metadata
            })
            print(f"[{timestamp}] Token map received: {message}")
        else:
            # This is a market data message
            self.messages.append({
                "timestamp": timestamp,
                "message": message,
                "metadata": metadata
            })
            # Only print first few chars to avoid spam
            print(f"[{timestamp}] Market data: {message[:100]}...")


async def test_real_unsubscribe():
    """
    Test unsubscribing from Polymarket WebSocket with real server connection.
    """
    print("=== Real Polymarket Unsubscribe Test ===")
    
    # Test token IDs for Israel x Hamas Ceasefire market
    initial_token_ids = [
        "36983600554365577850917051019051094208107094324057250177743040919797354737778",
        "27328614281599691408249679475598101144024812037645322360848849289647283526760"
    ]
    
    # Create message capture
    message_capture = MessageCapture()
    
    # Create client with initial token IDs
    poly_client = create_polymarket_client(
        slug="israel-x-hamas-ceasefire-by-july-15", 
        token_ids=initial_token_ids
    )
    
    # Set up message callback
    poly_client.set_message_callback(message_capture.message_callback)
    
    try:
        print(f"Connecting to Polymarket WebSocket...")
        # Connect to real Polymarket WebSocket
        success = await poly_client.connect()
        if not success:
            print("❌ Failed to connect to Polymarket WebSocket")
            return False
            
        print(f"✅ Connected! Subscribed to {len(initial_token_ids)} tokens")
        print("Waiting 5 seconds to receive initial data...")
        await asyncio.sleep(5)
        
        initial_message_count = len(message_capture.messages)
        print(f"Received {initial_message_count} market data messages")
        print(f"Received {len(message_capture.token_maps)} token maps")
        
        # Test partial unsubscribe
        print("\n=== Testing Partial Unsubscribe ===")
        reduced_token_ids = [initial_token_ids[0]]  # Keep only first token
        poly_client.token_id = reduced_token_ids
        
        # Call subscribe again with fewer tokens (this is the unsubscribe)
        await poly_client.subscribe()
        print(f"Unsubscribed! Now only subscribed to {len(reduced_token_ids)} token")
        
        # Wait and check if we're getting fewer messages
        print("Waiting 5 seconds to verify reduced message flow...")
        message_capture.messages.clear()  # Clear to count new messages
        await asyncio.sleep(5)
        
        partial_message_count = len(message_capture.messages)
        print(f"After partial unsubscribe: {partial_message_count} messages")
        
        # Test complete unsubscribe
        print("\n=== Testing Complete Unsubscribe ===")
        poly_client.token_id = [""]  # Empty string for complete unsubscribe
        
        await poly_client.subscribe()
        print("Complete unsubscribe sent!")
        
        # Wait and check if messages stop
        print("Waiting 5 seconds to verify message flow stopped...")
        message_capture.messages.clear()
        await asyncio.sleep(5)
        
        complete_message_count = len(message_capture.messages)
        print(f"After complete unsubscribe: {complete_message_count} messages")
        
        # Disconnect
        await poly_client.disconnect()
        print("✅ Disconnected from Polymarket WebSocket")
        
        # Analysis
        print("\n=== Test Results ===")
        print(f"Initial messages (5sec): {initial_message_count}")
        print(f"Partial unsubscribe messages (5sec): {partial_message_count}")
        print(f"Complete unsubscribe messages (5sec): {complete_message_count}")
        
        # The message count should decrease with each unsubscribe
        if partial_message_count <= initial_message_count:
            print("✅ Partial unsubscribe appears to work (message flow reduced or similar)")
        else:
            print("⚠️  Partial unsubscribe: message flow increased (unexpected)")
            
        if complete_message_count <= partial_message_count:
            print("✅ Complete unsubscribe appears to work (message flow reduced or stopped)")
        else:
            print("⚠️  Complete unsubscribe: message flow increased (unexpected)")
            
        return True
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        if poly_client.is_running():
            await poly_client.disconnect()
        raise


async def test_resubscribe():
    """
    Test that we can resubscribe after unsubscribing.
    """
    print("\n=== Testing Resubscribe After Unsubscribe ===")
    
    token_ids = [
        "36983600554365577850917051019051094208107094324057250177743040919797354737778"
    ]
    
    message_capture = MessageCapture()
    poly_client = create_polymarket_client(
        slug="israel-x-hamas-ceasefire-by-july-15",
        token_ids=token_ids
    )
    poly_client.set_message_callback(message_capture.message_callback)
    
    try:
        # Connect and subscribe
        await poly_client.connect()
        print("Connected and subscribed to 1 token")
        await asyncio.sleep(3)
        
        # Unsubscribe completely
        poly_client.token_id = [""]
        await poly_client.subscribe()
        print("Unsubscribed completely")
        await asyncio.sleep(2)
        
        # Resubscribe
        poly_client.token_id = token_ids
        await poly_client.subscribe()
        print("Resubscribed to 1 token")
        await asyncio.sleep(3)
        
        await poly_client.disconnect()
        print("✅ Resubscribe test completed")
        return True
        
    except Exception as e:
        print(f"❌ Resubscribe test failed: {e}")
        if poly_client.is_running():
            await poly_client.disconnect()
        raise


async def main():
    """
    Run all real unsubscribe tests.
    """
    print("Starting REAL Polymarket unsubscribe tests...\n")
    print("⚠️  This will connect to Polymarket's actual WebSocket server")
    
    try:
        # Test unsubscribe functionality
        await test_real_unsubscribe()
        
        # Test resubscribe functionality
        await test_resubscribe()
        
        print("\n🎉 All real tests completed successfully!")
        
    except Exception as e:
        print(f"❌ Real test failed with error: {e}")
        raise


if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    
    # Run the real tests
    asyncio.run(main())