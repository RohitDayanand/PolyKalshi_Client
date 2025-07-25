#!/usr/bin/env python3
"""
Test for Kalshi client ticker add/remove operations to observe auto-disconnect behavior.

This test connects to a ticker, removes it, and re-adds it to see if Kalshi auto-disconnects.
Logging is enabled to observe the behavior.
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import List, Dict, Any

# Set up logging first
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('kalshi_ticker_test.log')
    ]
)

logger = logging.getLogger(__name__)

# Import after logging setup to get debug messages from imports
try:
    from backend.master_manager.kalshi_client.kalshi_client import KalshiClient
    from backend.master_manager.kalshi_client.kalshi_client_config import KalshiClientConfig
    from backend.master_manager.kalshi_client.kalshi_environment import Environment
except ImportError as e:
    logger.error(f"Import error: {e}")
    # Try relative imports
    from kalshi_client import KalshiClient
    from kalshi_client_config import KalshiClientConfig
    from kalshi_environment import Environment


class KalshiTickerOperationsTest:
    """Test class for Kalshi ticker add/remove operations."""
    
    def __init__(self, ticker: str = "KXSPOTIFYARTISTD-25JUL25-THE", channel: str = "orderbook_delta"):
        self.ticker = ticker
        self.channel = channel
        self.client = None
        self.messages_received: List[Dict[str, Any]] = []
        self.connection_events: List[bool] = []
        self.errors: List[Exception] = []
        self.connection_sid = None  # Will be extracted from subscription response
        self.tracker_id = 100  # Starting ID for tracking operations
        
        logger.info(f"Initializing test for ticker: {ticker}, channel: {channel}")
    
    def setup_client(self) -> bool:
        """Set up the Kalshi client with proper configuration."""
        try:
            # Create configuration
            config = KalshiClientConfig(
                ticker=self.ticker,
                channel=self.channel,
                environment=Environment.PROD,  # Using demo environment for testing
                ping_interval=30,
                reconnect_interval=5,
                log_level="DEBUG"
            )
            
            # Create client
            self.client = KalshiClient(config)
            
            # Set up callbacks
            self.client.set_message_callback(self._on_message)
            self.client.set_connection_callback(self._on_connection)
            self.client.set_error_callback(self._on_error)
            
            logger.info("Client setup completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to set up client: {e}")
            self.errors.append(e)
            return False
    
    async def _on_message(self, message: str, metadata: Dict[str, Any]) -> None:
        """Handle incoming messages and extract connection SID."""
        try:
            import json
            
            # Store raw message for analysis
            message_data = {
                'timestamp': datetime.now().isoformat(),
                'message': message,
                'metadata': metadata
            }
            self.messages_received.append(message_data)
            
            # Try to parse JSON and extract SID from subscription response
            try:
                parsed = json.loads(message)
                if 'sid' in parsed:
                    self.connection_sid = parsed['sid']
                    logger.info(f"Extracted connection SID: {self.connection_sid}")
                elif 'sids' in parsed and parsed['sids']:
                    self.connection_sid = parsed['sids'][0]
                    logger.info(f"Extracted connection SID from sids array: {self.connection_sid}")
                
                logger.debug(f"Received message: {parsed}")
            except json.JSONDecodeError:
                logger.debug(f"Received non-JSON message: {message}")
                
        except Exception as e:
            logger.error(f"Error in message callback: {e}")
            self.errors.append(e)
    
    def _on_connection(self, connected: bool) -> None:
        """Handle connection events."""
        self.connection_events.append(connected)
        status = "connected" if connected else "disconnected"
        logger.info(f"Connection status changed: {status}")
    
    def _on_error(self, error: Exception) -> None:
        """Handle errors."""
        self.errors.append(error)
        logger.error(f"Client error: {error}")
    
    async def run_test(self) -> bool:
        """Run the complete test sequence."""
        logger.info("=" * 60)
        logger.info("STARTING KALSHI TICKER OPERATIONS TEST")
        logger.info("=" * 60)
        
        # Setup
        if not self.setup_client():
            return False
        
        try:
            # Step 1: Connect to initial ticker
            logger.info(f"Step 1: Connecting to ticker {self.ticker}")
            success = await self.client.connect()
            if not success:
                logger.error("Failed to connect to Kalshi")
                return False
            
            # Wait for initial connection and subscription
            await asyncio.sleep(5)
            logger.info(f"Messages received after initial connection: {len(self.messages_received)}")
            
            # Check if we got a connection SID
            if self.connection_sid is None:
                logger.warning("No connection SID found in messages, using default value 1")
                self.connection_sid = 1
            
            # Step 2: Remove the ticker
            logger.info(f"Step 2: Removing ticker {self.ticker}")
            try:
                await self.client.removeTicker(
                    oldTicker=self.ticker,
                    connection_sid=self.connection_sid,
                    tracker_id=self.tracker_id
                )
                self.tracker_id += 1
                logger.info("Remove ticker request sent")
            except Exception as e:
                logger.error(f"Failed to remove ticker: {e}")
                self.errors.append(e)
            
            # Wait and observe
            await asyncio.sleep(10)
            logger.info(f"Messages after ticker removal: {len(self.messages_received)}")
            
            # Step 3: Add the ticker back
            logger.info(f"Step 3: Adding ticker {self.ticker} back")
            try:
                await self.client.addTicker(
                    newTicker=self.ticker,
                    connection_sid=self.connection_sid,
                    tracker_id=self.tracker_id
                )
                self.tracker_id += 1
                logger.info("Add ticker request sent")
            except Exception as e:
                logger.error(f"Failed to add ticker back: {e}")
                self.errors.append(e)
            
            # Wait and observe final behavior
            await asyncio.sleep(15)
            logger.info(f"Final message count: {len(self.messages_received)}")
            
            # Step 4: Test with a different ticker
            different_ticker = "PRES24REP" if self.ticker == "PRES24DEM" else "PRES24DEM"
            logger.info(f"Step 4: Testing with different ticker {different_ticker}")
            try:
                await self.client.addTicker(
                    newTicker=different_ticker,
                    connection_sid=self.connection_sid,
                    tracker_id=self.tracker_id
                )
                self.tracker_id += 1
                logger.info(f"Added different ticker: {different_ticker}")
            except Exception as e:
                logger.error(f"Failed to add different ticker: {e}")
                self.errors.append(e)
            
            # Final observation period
            await asyncio.sleep(10)
            
            return True
            
        except Exception as e:
            logger.error(f"Test execution failed: {e}")
            self.errors.append(e)
            return False
        
        finally:
            # Cleanup
            if self.client:
                await self.client.disconnect()
    
    def print_summary(self) -> None:
        """Print a summary of the test results."""
        logger.info("=" * 60)
        logger.info("TEST SUMMARY")
        logger.info("=" * 60)
        
        logger.info(f"Total messages received: {len(self.messages_received)}")
        logger.info(f"Connection events: {self.connection_events}")
        logger.info(f"Errors encountered: {len(self.errors)}")
        
        if self.errors:
            logger.error("Errors during test:")
            for i, error in enumerate(self.errors, 1):
                logger.error(f"  {i}. {error}")
        
        # Show message timeline
        logger.info("\nMessage Timeline:")
        for i, msg_data in enumerate(self.messages_received[:10], 1):  # Show first 10 messages
            timestamp = msg_data['timestamp']
            message = msg_data['message'][:100] + "..." if len(msg_data['message']) > 100 else msg_data['message']
            logger.info(f"  {i}. [{timestamp}] {message}")
        
        if len(self.messages_received) > 10:
            logger.info(f"  ... and {len(self.messages_received) - 10} more messages")
        
        # Analysis
        logger.info("\nAnalysis:")
        if len(self.connection_events) > 1:
            logger.info("✓ Connection state changes detected - possible auto-disconnect behavior")
        else:
            logger.info("→ No connection state changes - connection remained stable")
        
        if len(self.messages_received) == 0:
            logger.warning("⚠ No messages received - possible connection issues")
        else:
            logger.info(f"✓ Received {len(self.messages_received)} messages")


async def main():
    """Main test function."""
    # Test with default ticker
    test = KalshiTickerOperationsTest("KXSPOTIFYARTISTD-25JUL25-THE", "orderbook_delta")
    
    try:
        success = await test.run_test()
        test.print_summary()
        
        if success:
            logger.info("Test completed successfully!")
        else:
            logger.error("Test failed!")
            
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
        if test.client:
            await test.client.disconnect()
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        if test.client:
            await test.client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())