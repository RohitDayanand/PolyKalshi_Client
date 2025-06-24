"""
Markets Manager - Central coordinator for    def __init__(self, config_path: Optional[str] = None):
        # Client storage
        self.polymarket_clients: Dict[str, PolymarketClient] = {}
        self.kalshi_clients: Dict[str, KalshiClient] = {}
        
        # Load subscription configuration
        self.subscriptions = self._load_subscriptions(config_path)
        
        # Initialize processor (composition pattern)
        self.processor = MessageProcessor(self)
        
        # Threading for async message processing
        self._message_queue = queue.Queue()
        self._processor_thread: Optional[threading.Thread] = None
        self._should_process = True
        
        logger.info("MarketsManager initialized")connections

This module manages multiple market data connections (Polymarket, Kalshi) and
processes incoming messages through a centralized processor with event emission.

Key Features:
- Manages multiple client connections
- Centralized message processing with platform tagging
- Event-driven architecture using pyee
- Subscription management from JSON configuration
- Composition pattern with Processor subclass
"""

import json
import logging
import asyncio
import queue
import threading
import time
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from pyee.asyncio import AsyncIOEventEmitter

from polymarket_client.polymarket_client import PolymarketClient, PolymarketClientConfig
from kalshi_client.kalshi_client import KalshiClient
from kalshi_client.kalshi_client_config import KalshiClientConfig
from kalshi_client.kalshi_environment import Environment
from ticker_processor import KalshiJsonFormatter, PolyJsonFormatter
from deprecated.message_processor import MessageProcessor
from kalshi_client.kalshi_queue import KalshiQueue
from kalshi_client.kalshi_message_processor import KalshiMessageProcessor
from polymarket_client.polymarket_queue import PolymarketQueue

# Configure logging
logger = logging.getLogger(__name__)


# Configuration classes
class MarketsManager:
    """
    Central manager for all market data connections and processing.
    
    Uses composition pattern with Processor class for message handling.
    Manages both Polymarket and Kalshi connections.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        # Client storage
        self.polymarket_clients: Dict[str, PolymarketClient] = {}
        self.kalshi_clients: Dict[str, KalshiClient] = {}
        
        # Initialize new async queue system (replaces legacy processor)
        self.kalshi_queue = KalshiQueue(max_queue_size=1000)
        self.polymarket_queue = PolymarketQueue(max_queue_size=1000)
        
        # Initialize Kalshi message processor
        self.kalshi_processor = KalshiMessageProcessor()
        
        # Set up processor callbacks
        self.kalshi_processor.set_error_callback(self._handle_kalshi_error)
        self.kalshi_processor.set_orderbook_update_callback(self._handle_kalshi_orderbook_update)
        
        # Connect processor to queue
        self.kalshi_queue.set_message_handler(self.kalshi_processor.handle_message)
        
        # Start queue processors
        asyncio.create_task(self.kalshi_queue.start())
        asyncio.create_task(self.polymarket_queue.start())
        
        logger.info("MarketsManager initialized with async queues and Kalshi message processor")

        self.KALSHI_CHANNEL = "orderbook_delta"
        #no polymarket channel, markets channel by default

    
    async def connect(self, subscription_id: str, platform: str = "polymarket") -> bool:
        """
        Connect to a specific market using subscription ID and platform.
        
        Args:
            subscription_id: ID from subscriptions config
            platform: "polymarket" or "kalshi"
            
        Returns:
            bool: True if connection successful
        """
        try:
            if platform.lower() == "polymarket":
                return await self._connect_polymarket(subscription_id)
            elif platform.lower() == "kalshi":
                return await self._connect_kalshi(subscription_id)
            else:
                logger.error(f"Unsupported platform: {platform}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to connect {platform}:{subscription_id} - {e}")
            return False
    async def _connect_polymarket(self, subscription_id: str) -> bool:
        """Connect to Polymarket using subscription configuration."""
        # Check if already connected
        if subscription_id in self.polymarket_clients:
            client = self.polymarket_clients[subscription_id]
            if client.is_running():
                logger.info(f"Polymarket {subscription_id} already connected")
                return True
            else:
                # Reconnect existing client
                logger.info(f"Reconnecting Polymarket {subscription_id}")
                return await client.connect()

        # For Polymarket, subscription_id should be token IDs (comma-separated or list)
        # Parse the subscription_id to get token IDs
        if isinstance(subscription_id, str):
            if ',' in subscription_id:
                token_ids = subscription_id.split(',')
            else:
                token_ids = [subscription_id]
        else:
            token_ids = subscription_id

        # Create client config with token_ids
        config = PolymarketClientConfig(
            slug="default-polymarket-subscription",
            ping_interval=30,
            log_level="INFO",
            token_id=token_ids
        )
        
        client = PolymarketClient(config)
        
        # Set up message forwarding with platform tagging
        message_count = 0
        last_reset_time = time.time()
        rate_limit = 10  # Default rate limit
        
        async def message_forwarder(raw_message, metadata):
            nonlocal message_count, last_reset_time
            
            # Simple rate limiting check
            current_time = time.time()
            if current_time - last_reset_time >= 1.0:  # Reset every second
                message_count = 0
                last_reset_time = current_time
            
            if message_count >= rate_limit:
                logger.warning(f"Rate limit exceeded for Polymarket {subscription_id}")
                return
            
            # Create enhanced metadata for queue processing
            enhanced_metadata = {
                **metadata,
                "platform": "polymarket",
                "subscription_id": subscription_id,
                "timestamp": datetime.now().isoformat(),
                "rate_limit": rate_limit,
                "channels": ["price", "orderbook"]
            }
            
            # Forward raw message to Polymarket queue
            await self.polymarket_queue.put_message(raw_message, enhanced_metadata)
            message_count += 1
        
        def connection_handler(connected):
            logger.info(f"Polymarket {subscription_id} connection: {connected}")
            
        def error_handler(error):
            logger.error(f"Polymarket {subscription_id} error: {error}")
        
        # Set callbacks
        client.set_message_callback(message_forwarder)
        client.set_connection_callback(connection_handler)
        client.set_error_callback(error_handler)
        
        # Connect to websocket (now properly awaited)
        try:
            # Use the updated connect method that returns properly
            connection_result = await client.connect()
            
            if connection_result and client.is_connected:
                self.polymarket_clients[subscription_id] = client
                logger.info(f"Successfully connected Polymarket {subscription_id}")
                
                # Queue processors started in __init__
                return True
            else:
                logger.error(f"Failed to connect Polymarket {subscription_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error connecting Polymarket {subscription_id}: {e}")
            return False
    
    async def _connect_kalshi(self, subscription_id: str) -> bool:
        """Connect to Kalshi using subscription configuration."""
        # Check if already connected
        if subscription_id in self.kalshi_clients:
            client = self.kalshi_clients[subscription_id]
            if client.is_running():
                logger.info(f"Kalshi {subscription_id} already connected")
                return True
            else:
                # Reconnect existing client
                logger.info(f"Reconnecting Kalshi {subscription_id}")
                return await client.connect()

        # For Kalshi, subscription_id should be the ticker (e.g., "KXPRESPOLAND-NT")
        ticker = subscription_id
        
        try:
            # @TODO pass credentials for auth instead of using the defaults 
            config = KalshiClientConfig(
                ticker=ticker,
                channel=self.KALSHI_CHANNEL,  # Primary channel
                environment=Environment.PROD,
                ping_interval=30,
                log_level="INFO"
            )
            
            client = KalshiClient(config)
            
            # Set up message forwarding with platform tagging
            message_count = 0
            last_reset_time = time.time()
            rate_limit = 15  # Default rate limit
            
            async def message_forwarder(raw_message, metadata):
                nonlocal message_count, last_reset_time
                
                # Simple rate limiting check
                current_time = time.time()
                if current_time - last_reset_time >= 1.0:  # Reset every second
                    message_count = 0
                    last_reset_time = current_time
                
                if message_count >= rate_limit:
                    logger.warning(f"Rate limit exceeded for Kalshi {subscription_id}")
                    return
                
                # Create enhanced metadata for queue processing
                enhanced_metadata = {
                    **metadata,
                    "platform": "kalshi",
                    "subscription_id": subscription_id,
                    "timestamp": datetime.now().isoformat(),
                    "rate_limit": rate_limit,
                    "channels": self.KALSHI_CHANNEL
                }
                
                # Forward raw message to Kalshi queue
                await self.kalshi_queue.put_message(raw_message, enhanced_metadata)
                message_count += 1
            
            def connection_handler(connected):
                logger.info(f"Kalshi {subscription_id} connection: {connected}")
                
            def error_handler(error):
                logger.error(f"Kalshi {subscription_id} error: {error}")
            
            # Set callbacks
            client.set_message_callback(message_forwarder)
            client.set_connection_callback(connection_handler)
            client.set_error_callback(error_handler)
            
            # Connect to websocket (now properly awaited)
            try:
                # Use the updated connect method that returns properly
                connection_result = await client.connect()
                
                if connection_result and client.is_connected:
                    self.kalshi_clients[subscription_id] = client
                    logger.info(f"Successfully connected Kalshi {subscription_id}")
                    
                    # Queue processors started in __init__
                    return True
                else:
                    logger.error(f"Failed to connect Kalshi {subscription_id}")
                    return False
                    
            except Exception as e:
                logger.error(f"Error connecting Kalshi {subscription_id}: {e}")
                return False
                
        except Exception as e:
            logger.error(f"Error setting up Kalshi client {subscription_id}: {e}")
            return False
    
    async def disconnect(self, subscription_id: str, platform: str = "polymarket") -> bool:
        """Disconnect from a specific market."""
        try:
            if platform.lower() == "polymarket":
                if subscription_id in self.polymarket_clients:
                    await self.polymarket_clients[subscription_id].disconnect()
                    del self.polymarket_clients[subscription_id]
                    logger.info(f"Disconnected Polymarket {subscription_id}")
                    return True
            elif platform.lower() == "kalshi":
                if subscription_id in self.kalshi_clients:
                    await self.kalshi_clients[subscription_id].disconnect()  # Now async
                    del self.kalshi_clients[subscription_id]
                    logger.info(f"Disconnected Kalshi {subscription_id}")
                    return True
            
            logger.warning(f"No active connection found for {platform}:{subscription_id}")
            return False
            
        except Exception as e:
            logger.error(f"Error disconnecting {platform}:{subscription_id} - {e}")
            return False
    
    async def disconnect_all(self) -> None:
        """Disconnect all clients and stop processing."""
        logger.info("Disconnecting all clients...")
        
        # Stop queue processors
        await self.kalshi_queue.stop()
        await self.polymarket_queue.stop()
        
        # Disconnect all Polymarket clients (async)
        for subscription_id, client in self.polymarket_clients.items():
            try:
                await client.disconnect()
                logger.info(f"Disconnected Polymarket {subscription_id}")
            except Exception as e:
                logger.error(f"Error disconnecting Polymarket {subscription_id}: {e}")
        
        # Disconnect all Kalshi clients (now async)
        for subscription_id, client in self.kalshi_clients.items():
            try:
                await client.disconnect()
                logger.info(f"Disconnected Kalshi {subscription_id}")
            except Exception as e:
                logger.error(f"Error disconnecting Kalshi {subscription_id}: {e}")
        
        self.polymarket_clients.clear()
        self.kalshi_clients.clear()
        logger.info("All clients disconnected")
    
    
    def get_status(self) -> Dict[str, Any]:
        """Get status of all connections and the manager."""
        poly_status = {}
        for sub_id, client in self.polymarket_clients.items():
            poly_status[sub_id] = client.get_status()
        
        kalshi_status = {}
        for sub_id, client in self.kalshi_clients.items():
            kalshi_status[sub_id] = client.get_status()
        
        return {
            "polymarket_connections": len(self.polymarket_clients),
            "kalshi_connections": len(self.kalshi_clients),
            "total_connections": len(self.polymarket_clients) + len(self.kalshi_clients),
            "kalshi_queue_stats": self.kalshi_queue.get_stats(),
            "polymarket_queue_stats": self.polymarket_queue.get_stats(),
            "kalshi_processor_stats": self.kalshi_processor.get_stats(),
            "polymarket_details": poly_status,
            "kalshi_details": kalshi_status
        }
    
    async def _handle_kalshi_error(self, error_info: Dict[str, Any]) -> None:
        """Handle errors from Kalshi message processor."""
        logger.error(f"Kalshi processor error: {error_info.get('message')} (code: {error_info.get('code')})")
        # Could emit events here for external error handling
    
    async def _handle_kalshi_orderbook_update(self, sid: int, orderbook_state) -> None:
        """Handle orderbook updates from Kalshi message processor."""
        logger.debug(f"Orderbook updated for sid={sid}, ticker={orderbook_state.market_ticker}")
        # Could emit events here for external orderbook consumers
    
    def get_kalshi_orderbook(self, sid: int):
        """Get current Kalshi orderbook state for a market."""
        return self.kalshi_processor.get_orderbook(sid)
    
    def get_all_kalshi_orderbooks(self):
        """Get all current Kalshi orderbook states."""
        return self.kalshi_processor.get_all_orderbooks()
    
    def get_kalshi_summary_stats(self, sid: int):
        """Get yes/no bid/ask/volume summary for a Kalshi market.""" 
        return self.kalshi_processor.get_summary_stats(sid)
    
    def get_all_kalshi_summary_stats(self):
        """Get summary stats for all active Kalshi markets."""
        return self.kalshi_processor.get_all_summary_stats()
    
# Convenience function for quick setup
def create_markets_manager(config_path: Optional[str] = None) -> MarketsManager:
    """
    Create a markets manager with optional configuration file.
    
    Args:
        config_path: Path to JSON subscription configuration file
        
    Returns:
        MarketsManager: Configured manager instance
    """
    #config path represents some illusory json subscription

    return MarketsManager(config_path)