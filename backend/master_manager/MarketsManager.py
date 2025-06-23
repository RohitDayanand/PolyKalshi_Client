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

from polymarket_client import PolymarketClient, PolymarketClientConfig
from kalshi_client.kalshi_client import KalshiClient
from kalshi_client.kalshi_client_config import KalshiClientConfig
from kalshi_client.kalshi_environment import Environment
from ticker_processor import KalshiJsonFormatter, PolyJsonFormatter
from message_processor import MessageProcessor

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
        
        # Initialize processor (composition pattern)
        self.processor = MessageProcessor(self)
        
        # Threading for async message processing
        self._message_queue = queue.Queue()
        self._processor_thread: Optional[threading.Thread] = None
        self._should_process = True
        
        logger.info("MarketsManager initialized")

        self.KALSHI_CHANNEL = "orderbook_delta"
        #no polymarket channel, markets channel by default

    
    def connect(self, subscription_id: str, platform: str = "polymarket") -> bool:
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
                return self._connect_polymarket(subscription_id)
            elif platform.lower() == "kalshi":
                return self._connect_kalshi(subscription_id)
            else:
                logger.error(f"Unsupported platform: {platform}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to connect {platform}:{subscription_id} - {e}")
            return False
    
    def _connect_polymarket(self, subscription_id: str) -> bool:
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
                return client.connect()

        # For Polymarket, subscription_id should be token IDs (comma-separated or list)
        # Parse the subscription_id to get token IDs
        if isinstance(subscription_id, str):
            if ',' in subscription_id:
                token_ids = subscription_id.split(',')
            else:
                token_ids = [subscription_id]
        else:
            token_ids = subscription_id

        # Generate subscription message using PolyJsonFormatter
        subscription_message = PolyJsonFormatter([token_ids])
        
        # Create client config with a default slug (can be customized later)
        config = PolymarketClientConfig(
            slug="default-polymarket-subscription",
            ping_interval=30,
            log_level="INFO"
        )
        
        client = PolymarketClient(config)
        
        # Set up message forwarding with platform tagging
        message_count = 0
        last_reset_time = time.time()
        rate_limit = 10  # Default rate limit
        
        def message_forwarder(message):
            nonlocal message_count, last_reset_time
            
            # Simple rate limiting check
            current_time = time.time()
            if current_time - last_reset_time >= 1.0:  # Reset every second
                message_count = 0
                last_reset_time = current_time
            
            if message_count >= rate_limit:
                logger.warning(f"Rate limit exceeded for Polymarket {subscription_id}")
                return
            
            # Efficient in-place message tagging (O(1) operation)
            message["_platform"] = "polymarket"
            message["_subscription_id"] = subscription_id
            message["_timestamp"] = datetime.now().isoformat()
            message["_rate_limit"] = rate_limit
            message["_channels"] = ["price", "orderbook"]
            
            # Forward to processor queue
            self._message_queue.put(message)
            message_count += 1
        
        def connection_handler(connected):
            logger.info(f"Polymarket {subscription_id} connection: {connected}")
            
        def error_handler(error):
            logger.error(f"Polymarket {subscription_id} error: {error}")
        
        # Set callbacks
        client.set_message_callback(message_forwarder)
        client.set_connection_callback(connection_handler)
        client.set_error_callback(error_handler)
        
        # Connect to websocket first
        if client.connect():
            # After connection, send subscription message
            if hasattr(client, 'ws') and client.ws and client.is_connected:
                try:
                    client.ws.send(json.dumps(subscription_message))
                    logger.info(f"Sent Polymarket subscription for tokens: {token_ids}")
                except Exception as e:
                    logger.error(f"Failed to send Polymarket subscription: {e}")
            
            self.polymarket_clients[subscription_id] = client
            logger.info(f"Successfully connected Polymarket {subscription_id}")
            
            # Start processor if not running
            self._ensure_processor_running()
            return True
        else:
            logger.error(f"Failed to connect Polymarket {subscription_id}")
            return False
    
    def _connect_kalshi(self, subscription_id: str) -> bool:
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
                return client.connect()

        # For Kalshi, subscription_id should be the ticker (e.g., "KXPRESPOLAND-NT")
        ticker = subscription_id
        
        # Generate subscription message using KalshiJsonFormatter
        subscription_message = KalshiJsonFormatter([ticker], self.KALSHI_CHANNEL)
        
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
            
            def message_forwarder(message):
                nonlocal message_count, last_reset_time
                
                # Simple rate limiting check
                current_time = time.time()
                if current_time - last_reset_time >= 1.0:  # Reset every second
                    message_count = 0
                    last_reset_time = current_time
                
                if message_count >= rate_limit:
                    logger.warning(f"Rate limit exceeded for Kalshi {subscription_id}")
                    return
                
                # Efficient in-place message tagging (O(1) operation)
                message["_platform"] = "kalshi"
                message["_subscription_id"] = subscription_id
                message["_timestamp"] = datetime.now().isoformat()
                message["_rate_limit"] = rate_limit
                message["_channels"] = self.KALSHI_CHANNEL
                
                # Forward to processor queue
                self._message_queue.put(message)
                message_count += 1
            
            def connection_handler(connected):
                logger.info(f"Kalshi {subscription_id} connection: {connected}")
                
            def error_handler(error):
                logger.error(f"Kalshi {subscription_id} error: {error}")
            
            # Set callbacks
            client.set_message_callback(message_forwarder)
            client.set_connection_callback(connection_handler)
            client.set_error_callback(error_handler)
            
            # Connect to websocket
            if client.connect():
                # Note: Kalshi client handles subscription internally via _subscribe_to_channel
                # The subscription message is automatically sent when connection is established
                
                self.kalshi_clients[subscription_id] = client
                logger.info(f"Successfully connected Kalshi {subscription_id}")
                
                # Start processor if not running
                self._ensure_processor_running()
                return True
            else:
                logger.error(f"Failed to connect Kalshi {subscription_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error setting up Kalshi client {subscription_id}: {e}")
            return False
    
    def disconnect(self, subscription_id: str, platform: str = "polymarket") -> bool:
        """Disconnect from a specific market."""
        try:
            if platform.lower() == "polymarket":
                if subscription_id in self.polymarket_clients:
                    self.polymarket_clients[subscription_id].disconnect()
                    del self.polymarket_clients[subscription_id]
                    logger.info(f"Disconnected Polymarket {subscription_id}")
                    return True
            elif platform.lower() == "kalshi":
                if subscription_id in self.kalshi_clients:
                    self.kalshi_clients[subscription_id].disconnect()
                    del self.kalshi_clients[subscription_id]
                    logger.info(f"Disconnected Kalshi {subscription_id}")
                    return True
            
            logger.warning(f"No active connection found for {platform}:{subscription_id}")
            return False
            
        except Exception as e:
            logger.error(f"Error disconnecting {platform}:{subscription_id} - {e}")
            return False
    
    def disconnect_all(self) -> None:
        """Disconnect all clients and stop processing."""
        logger.info("Disconnecting all clients...")
        
        # Stop processor
        self._should_process = False
        if self._processor_thread and self._processor_thread.is_alive():
            self._processor_thread.join(timeout=5.0)
        
        # Disconnect all Polymarket clients
        for subscription_id, client in self.polymarket_clients.items():
            try:
                client.disconnect()
                logger.info(f"Disconnected Polymarket {subscription_id}")
            except Exception as e:
                logger.error(f"Error disconnecting Polymarket {subscription_id}: {e}")
        
        # Disconnect all Kalshi clients
        for subscription_id, client in self.kalshi_clients.items():
            try:
                client.disconnect()
                logger.info(f"Disconnected Kalshi {subscription_id}")
            except Exception as e:
                logger.error(f"Error disconnecting Kalshi {subscription_id}: {e}")
        
        self.polymarket_clients.clear()
        self.kalshi_clients.clear()
        logger.info("All clients disconnected")
    
    def _ensure_processor_running(self) -> None:
        """Ensure the message processor thread is running."""
        if not self._processor_thread or not self._processor_thread.is_alive():
            self._should_process = True
            self._processor_thread = threading.Thread(
                target=self._process_messages, 
                daemon=True
            )
            self._processor_thread.start()
            logger.info("Message processor thread started")
    
    def _process_messages(self) -> None:
        """Process messages from the queue in a separate thread."""
        while self._should_process:
            try:
                # Get message with timeout to allow thread shutdown
                message = self._message_queue.get(timeout=1.0)
                self.processor.process_message(message)
                self._message_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error processing message: {e}")
    
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
            "processor_running": self._processor_thread and self._processor_thread.is_alive(),
            "queue_size": self._message_queue.qsize(),
            "polymarket_details": poly_status,
            "kalshi_details": kalshi_status
        }
    
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