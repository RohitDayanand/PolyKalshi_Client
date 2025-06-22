"""
Markets Manager - Central coordinator for    def __init__(self, config_path: Optional[str] = None):
        # Client storage
        self.polymarket_clients: Dict[str, PolymarketClient] = {}
        self.kalshi_clients: Dict[str, KalshiClient] = {}
        
        # Load subscription configuration
        self.subscriptions = self._load_subscriptions(config_path)
        
        # Initialize processor (composition pattern)
        self.processor = self.MessageProcessor(self)
        
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
from kalshi_client_wrapper import KalshiClient, KalshiClientConfig, Environment

# Configure logging
logger = logging.getLogger(__name__)


# Configuration classes
class KalshiClientConfig:
    """Configuration class for Kalshi client (replaced by imported version)."""
    pass  # Now using the imported KalshiClientConfig


class MarketsManager:
    """
    Central manager for all market data connections and processing.
    
    Uses composition pattern with Processor class for message handling.
    Manages both Polymarket and Kalshi connections.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        # Client storage
        self.polymarket_clients: Dict[str, PolymarketClient] = {}
        self.kalshi_clients: Dict[str, KalshiClient] = {}  # Now implemented
        
        # Load subscription configuration
        self.subscriptions = self._load_subscriptions(config_path)
        
        # Initialize processor (composition pattern)
        self.processor = self.MessageProcessor(self)
        
        # Threading for async message processing
        self._message_queue = queue.Queue()
        self._processor_thread: Optional[threading.Thread] = None
        self._should_process = True
        
        logger.info("MarketsManager initialized")
    
    def _load_subscriptions(self, config_path: Optional[str] = None) -> Dict:
        """Load subscription configuration from JSON file or use dummy data."""
        if config_path:
            try:
                with open(config_path, 'r') as f:
                    return json.load(f)
            except FileNotFoundError:
                logger.warning(f"Config file {config_path} not found, using dummy data")
        
        # Enhanced subscription data structure - will be replaced with React state later
        dummy_subscriptions = {
            "polymarket": {
                "election_2024": {
                    "slug": "poland-presidential-election",
                    "status": "active",
                    "priority": "high",
                    "subscription_config": {
                        "asset_types": ["token"],
                        "channels": ["price", "orderbook"],
                        "rate_limit": 10  # messages per second
                    }
                },
                "sports_event": {
                    "slug": "sports-betting-market",
                    "status": "pending",
                    "priority": "medium",
                    "subscription_config": {
                        "asset_types": ["token"],
                        "channels": ["price"],
                        "rate_limit": 5
                    }
                }
            },
            "kalshi": {
                "pres_election": {
                    "ticker": "PRESWIN24",
                    "status": "active", 
                    "priority": "high",
                    "subscription_config": {
                        "channels": ["orderbook_delta", "trade"],
                        "rate_limit": 15
                    }
                },
                "weather_bet": {
                    "ticker": "RAIN-NYC",
                    "status": "pending",
                    "priority": "low",
                    "subscription_config": {
                        "channels": ["orderbook_delta"],
                        "rate_limit": 3
                    }
                }
            }
        }
        
        logger.info(f"Loaded {len(dummy_subscriptions)} platform subscriptions")
        return dummy_subscriptions
    
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
        poly_subscriptions = self.subscriptions.get("polymarket", {})
        
        if subscription_id not in poly_subscriptions:
            logger.error(f"Polymarket subscription {subscription_id} not found")
            return False
        
        subscription = poly_subscriptions[subscription_id]
        slug = subscription["slug"]
        
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
        
        # Create new client connection
        subscription = poly_subscriptions[subscription_id]
        slug = subscription["slug"]
        config_data = subscription.get("subscription_config", {})
        
        # Extract configuration from JSON subscription data
        rate_limit = config_data.get("rate_limit", 10)  # Default rate limit
        channels = config_data.get("channels", ["price", "orderbook"])
        
        config = PolymarketClientConfig(
            slug=slug,
            ping_interval=30,
            log_level="INFO"
        )
        
        client = PolymarketClient(config)
        
        # Set up message forwarding with efficient platform tagging and rate limiting
        message_count = 0
        last_reset_time = time.time()
        
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
            message["_channels"] = channels
            
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
        
        # Connect and store
        if client.connect():
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
        kalshi_subscriptions = self.subscriptions.get("kalshi", {})
        
        if subscription_id not in kalshi_subscriptions:
            logger.error(f"Kalshi subscription {subscription_id} not found")
            return False
        
        subscription = kalshi_subscriptions[subscription_id]
        ticker = subscription["ticker"]
        
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
        
        # Create new client connection
        subscription = kalshi_subscriptions[subscription_id]
        ticker = subscription["ticker"]
        config_data = subscription.get("subscription_config", {})
        
        # Extract configuration from JSON subscription data
        rate_limit = config_data.get("rate_limit", 15)  # Default rate limit
        channels = config_data.get("channels", ["orderbook_delta"])
        primary_channel = channels[0] if channels else "orderbook_delta"
        
        try:
            config = KalshiClientConfig(
                ticker=ticker,
                channel=primary_channel,
                environment=Environment.PROD,  # Can be made configurable from subscription
                ping_interval=30,
                log_level="INFO"
            )
            
            client = KalshiClient(config)
            
            # Set up message forwarding with efficient platform tagging and rate limiting
            message_count = 0
            last_reset_time = time.time()
            
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
                message["_channels"] = channels
                
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
            
            # Connect and store
            if client.connect():
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
            "total_subscriptions": len(self.subscriptions.get("polymarket", {})) + len(self.subscriptions.get("kalshi", {})),
            "processor_running": self._processor_thread and self._processor_thread.is_alive(),
            "queue_size": self._message_queue.qsize(),
            "polymarket_details": poly_status,
            "kalshi_details": kalshi_status
        }
    
    class MessageProcessor:
        """
        Message processor subclass using composition pattern.
        
        Processes tagged messages from different platforms and emits events
        through pyee event emitter with rate limiting and testing capabilities.
        """
        
        def __init__(self, manager: 'MarketsManager'):
            self.manager = manager
            self.event_emitter = AsyncIOEventEmitter()
            
            # Rate limiting tracking for testing
            self.rate_limit_stats = {
                "total_messages": 0,
                "rate_limited_messages": 0,
                "platform_stats": {},
                "last_reset": datetime.now()
            }
            
            # Message type handlers for different event types
            self.message_handlers = {
                "book": self._handle_orderbook,
                "orderbook_snapshot": self._handle_orderbook,
                "orderbook_delta": self._handle_orderbook,
                "trade": self._handle_trade,
                "ticker": self._handle_ticker,
                "ticker_v2": self._handle_ticker,
                "price": self._handle_price,
                "fill": self._handle_fill
            }
            
            logger.info("MessageProcessor initialized with pyee event emitter")
        
        def process_message(self, message: Dict[str, Any]) -> None:
            """
            Process a tagged message from any platform with rate limiting.
            
            Args:
                message: Message dict with _platform, _subscription_id, _timestamp tags
            """
            try:
                platform = message.get("_platform")
                subscription_id = message.get("_subscription_id")
                event_type = message.get("event_type", message.get("type", "unknown"))
                rate_limit = message.get("_rate_limit", 10)
                
                # Update stats
                self.rate_limit_stats["total_messages"] += 1
                
                # Track per-platform stats
                platform_key = f"{platform}:{subscription_id}"
                if platform_key not in self.rate_limit_stats["platform_stats"]:
                    self.rate_limit_stats["platform_stats"][platform_key] = {
                        "messages": 0,
                        "rate_limited": 0,
                        "last_message": None
                    }
                
                platform_stats = self.rate_limit_stats["platform_stats"][platform_key]
                platform_stats["messages"] += 1
                platform_stats["last_message"] = datetime.now().isoformat()
                
                logger.debug(f"Processing {platform}:{subscription_id} message type: {event_type}")
                
                # Route to appropriate handler based on message type
                if event_type in self.message_handlers:
                    self.message_handlers[event_type](message)
                else:
                    # Default handler - emit raw message
                    self._emit_raw_message(message)
                
                # Emit to pyee event emitter for testing
                self._emit_to_pyee(message)
                
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                logger.debug(f"Failed message: {message}")
        
        def _handle_orderbook(self, message: Dict[str, Any]) -> None:
            """Handle orderbook-related messages."""
            platform = message.get("_platform")
            subscription_id = message.get("_subscription_id")
            
            logger.info(f"📊 ORDERBOOK: {platform}:{subscription_id}")
            self._emit_to_channel("orderbook", message)
        
        def _handle_trade(self, message: Dict[str, Any]) -> None:
            """Handle trade messages."""
            platform = message.get("_platform")
            subscription_id = message.get("_subscription_id")
            
            logger.info(f"💰 TRADE: {platform}:{subscription_id}")
            self._emit_to_channel("trade", message)
        
        def _handle_ticker(self, message: Dict[str, Any]) -> None:
            """Handle ticker/price messages."""
            platform = message.get("_platform")
            subscription_id = message.get("_subscription_id")
            
            logger.info(f"📈 TICKER: {platform}:{subscription_id}")
            self._emit_to_channel("ticker", message)
        
        def _handle_price(self, message: Dict[str, Any]) -> None:
            """Handle price update messages."""
            platform = message.get("_platform")
            subscription_id = message.get("_subscription_id")
            
            logger.info(f"💲 PRICE: {platform}:{subscription_id}")
            self._emit_to_channel("price", message)
        
        def _handle_fill(self, message: Dict[str, Any]) -> None:
            """Handle fill messages."""
            platform = message.get("_platform")
            subscription_id = message.get("_subscription_id")
            
            logger.info(f"✅ FILL: {platform}:{subscription_id}")
            self._emit_to_channel("fill", message)
        
        def _emit_raw_message(self, message: Dict[str, Any]) -> None:
            """Emit raw message for unknown types."""
            platform = message.get("_platform", "unknown")
            subscription_id = message.get("_subscription_id", "unknown")
            event_type = message.get("event_type", message.get("type", "raw"))
            
            logger.info(f"🔗 RAW: {platform}:{subscription_id} - {event_type}")
            self._emit_to_channel("raw", message)
        
        def _emit_to_channel(self, event_type: str, message: Dict[str, Any]) -> None:
            """Emit message to a specific channel."""
            platform = message.get("_platform", "unknown")
            subscription_id = message.get("_subscription_id", "unknown")
            
            # Create channel name
            channel = f"{platform}.{subscription_id}.{event_type}"
            
            logger.debug(f"Emitting to channel '{channel}'")
            
            # For now, just log the emission - later we'll connect to WebSocket broadcasters
            # When we add WebSocket broadcasting, this is where we'd emit to connected clients
        
        def _emit_to_pyee(self, message: Dict[str, Any]) -> None:
            """Emit events to pyee for testing and rate limiting validation."""
            try:
                platform = message.get("_platform")
                subscription_id = message.get("_subscription_id")
                event_type = message.get("event_type", message.get("type", "unknown"))
                
                # Create event name for pyee
                event_name = f"{platform}_{subscription_id}_{event_type}"
                
                # Emit the event
                self.event_emitter.emit(event_name, message)
                
                # Also emit a general event for testing
                self.event_emitter.emit("message_processed", {
                    "platform": platform,
                    "subscription_id": subscription_id,
                    "event_type": event_type,
                    "timestamp": message.get("_timestamp"),
                    "rate_limit": message.get("_rate_limit")
                })
                
            except Exception as e:
                logger.error(f"Error emitting to pyee: {e}")
        
        def add_message_handler(self, message_type: str, handler_func: callable) -> None:
            """Add a custom message handler for specific message types."""
            self.message_handlers[message_type] = handler_func
            logger.info(f"Added handler for message type: {message_type}")
        
        def get_event_emitter(self) -> AsyncIOEventEmitter:
            """Get the event emitter for external listener registration."""
            return self.event_emitter
        
        def get_rate_limit_stats(self) -> Dict[str, Any]:
            """Get current rate limiting statistics for testing."""
            return self.rate_limit_stats.copy()
        
        def reset_rate_limit_stats(self) -> None:
            """Reset rate limiting statistics."""
            self.rate_limit_stats = {
                "total_messages": 0,
                "rate_limited_messages": 0,
                "platform_stats": {},
                "last_reset": datetime.now()
            }
            logger.info("Rate limit statistics reset")


# Convenience function for quick setup
def create_markets_manager(config_path: Optional[str] = None) -> MarketsManager:
    """
    Create a markets manager with optional configuration file.
    
    Args:
        config_path: Path to JSON subscription configuration file
        
    Returns:
        MarketsManager: Configured manager instance
    """
    return MarketsManager(config_path)