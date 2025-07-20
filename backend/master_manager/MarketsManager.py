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

from .polymarket_client.polymarket_client import PolymarketClient, PolymarketClientConfig
from .kalshi_client.kalshi_client import KalshiClient
from .kalshi_client.kalshi_client_config import KalshiClientConfig
from .kalshi_client.kalshi_environment import Environment
from .deprecated.message_processor import MessageProcessor
from .kalshi_client.kalshi_queue import KalshiQueue
from .kalshi_client.message_processor import KalshiMessageProcessor
from .polymarket_client.polymarket_queue import PolymarketQueue
from .polymarket_client.polymarket_message_processor import PolymarketMessageProcessor
from .polymarket_client.polymarket_ticker_publisher import PolymarketTickerPublisher
from .kalshi_client.kalshi_ticker_publisher import KalshiTickerPublisher
from .utils.tglobal_config import PUBLISH_INTERVAL_SECONDS
from .arbitrage_manager import ArbitrageManager
from .events.event_bus import EventBus, global_event_bus

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
        
        # Initialize Kalshi message processor with EventBus
        self.kalshi_processor = KalshiMessageProcessor(event_bus=self.event_bus)
        
        # Initialize Polymarket message processor
        self.polymarket_processor = PolymarketMessageProcessor()
        
        # Initialize Kalshi candlestick manager
        from .kalshi_client.candlestick_manager import CandlestickManager
        self.kalshi_candlestick_manager = CandlestickManager()
        
        # Initialize Kalshi ticker publisher (1-second intervals)
        self.kalshi_ticker_publisher = KalshiTickerPublisher(
            kalshi_processor=self.kalshi_processor,
            candlestick_manager=self.kalshi_candlestick_manager,
            publish_interval=PUBLISH_INTERVAL_SECONDS
        )
        
        # Set up candlestick emission callback to force publish completed candles
        async def emit_completed_candlestick(sid: int, candlestick):
            """Emit completed candlestick immediately via ticker publisher"""
            self.kalshi_ticker_publisher.force_publish_market(sid)
        
        self.kalshi_candlestick_manager.set_candlestick_emit_callback(emit_completed_candlestick)
        
        # Initialize Polymarket ticker publisher (1-second intervals)
        self.polymarket_ticker_publisher = PolymarketTickerPublisher(
            polymarket_processor=self.polymarket_processor,
            publish_interval=PUBLISH_INTERVAL_SECONDS
        )
        
        # Initialize EventBus for component communication
        self.event_bus = global_event_bus
        
        # Initialize ArbitrageManager with EventBus pattern
        self.arbitrage_manager = ArbitrageManager(min_spread_threshold=0.02, event_bus=self.event_bus)
        
        # Set up processor callbacks
        self.kalshi_processor.set_error_callback(self._handle_kalshi_error)
        self.kalshi_processor.set_orderbook_update_callback(self._handle_kalshi_orderbook_update)
        
        self.polymarket_processor.set_error_callback(self._handle_polymarket_error)
        self.polymarket_processor.set_orderbook_update_callback(self._handle_polymarket_orderbook_update)
        
        # Connect processors to queues
        self.kalshi_queue.set_message_handler(self.kalshi_processor.handle_message)
        self.polymarket_queue.set_message_handler(self.polymarket_processor.handle_message)

        #single market - initialize token ids 
        self.kalshi_sid = -1 #number is not usable yet
        self.polymarket_yes_id = ""
        self.polymarket_no_id = ""
        
        # Track if async components are started
        self._async_started = False
        
        logger.info("MarketsManager initialized with async queues, Kalshi/Polymarket message processors, and ticker publishers")

        self.KALSHI_CHANNEL = "orderbook_delta"
        #no polymarket channel, markets channel by default

    async def start_async_components(self):
        """Start async components that require a running event loop"""
        if self._async_started:
            logger.info("MarketsManager async components already started")
            return
        
        try:
            # Start queue processors and ticker publishers
            await self.kalshi_queue.start()
            await self.polymarket_queue.start()
            await self.kalshi_ticker_publisher.start()
            await self.polymarket_ticker_publisher.start()
            
            self._async_started = True
            logger.info("✅ MarketsManager async components started successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to start MarketsManager async components: {e}")
            raise
    
    async def connect(self, subscription_id: str, platform: str = "polymarket") -> bool:
        """
        Connect to a specific market using subscription ID and platform.
        
        Args:
            subscription_id: ID from subscriptions config
            platform: "polymarket" or "kalshi"
            
        Returns:
            bool: True if connection successful
        """
        # Ensure async components are started
        if not self._async_started:
            await self.start_async_components()
            
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
                #also remove the polymarket tag
                token_ids[0] = token_ids[0].removeprefix('polymarket_')
            else:
                token_ids = [subscription_id]
        else:
            token_ids = subscription_id
        
        if len(token_ids) > 1:
            self.polymarket_yes_id = token_ids[0]
            self.polymarket_no_id = token_ids[1]

        # Create client config with token_ids
        # Check for debug logging environment variable
        import os
        debug_logging = os.getenv('POLYMARKET_DEBUG_LOGGING', 'false').lower() == 'true'
        
        config = PolymarketClientConfig(
            slug="default-polymarket-subscription",
            ping_interval=30,
            log_level="INFO",
            token_ids=token_ids,
            debug_websocket_logging=debug_logging,
            debug_log_file=None
        )
        
        client = PolymarketClient(config)
        
        # Set up message forwarding with platform tagging
        message_count = 0
        last_reset_time = time.time()
        rate_limit = 1_000_000 #1 million messages/sec rate limit
        
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
        ticker = subscription_id.removeprefix("kalshi_") #shhould parse
        
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
            rate_limit = 1_000_000  # 1,000,000 rate limit - should never be hit, and is likely way 
            #above what our system can handle (we will crash before this)
            
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
        
        # Stop ticker publishers first
        await self.kalshi_ticker_publisher.stop()
        await self.polymarket_ticker_publisher.stop()
        
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
            "polymarket_processor_stats": self.polymarket_processor.get_stats(),
            "kalshi_ticker_publisher_stats": self.kalshi_ticker_publisher.get_stats(),
            "polymarket_ticker_publisher_stats": self.polymarket_ticker_publisher.get_stats(),
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
        # Note: Arbitrage detection now handled via EventBus subscriptions in ArbitrageManager
    
    async def _handle_polymarket_error(self, error_info: Dict[str, Any]) -> None:
        """Handle errors from Polymarket message processor."""
        logger.error(f"Polymarket processor error: {error_info.get('message')}")
        # Could emit events here for external error handling
    
    async def _handle_polymarket_orderbook_update(self, asset_id: str, orderbook_state) -> None:
        """Handle orderbook updates from Polymarket message processor."""
        logger.debug(f"Orderbook updated for asset_id={asset_id}, market={orderbook_state.market}")
        # Note: Arbitrage detection now handled via EventBus subscriptions in ArbitrageManager
    
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
    
    def force_publish_kalshi_market(self, sid: int) -> bool:
        """Force immediate publication of a Kalshi market (bypasses rate limiting)."""
        return self.kalshi_ticker_publisher.force_publish_market(sid)
    
    async def restart_kalshi_ticker_publisher(self):
        """Restart the Kalshi ticker publisher."""
        await self.kalshi_ticker_publisher.stop()
        await self.kalshi_ticker_publisher.start()
        logger.info("Kalshi ticker publisher restarted")
    
    def get_polymarket_orderbook(self, asset_id: str):
        """Get current Polymarket orderbook state for an asset."""
        return self.polymarket_processor.get_orderbook(asset_id)
    
    def get_all_polymarket_orderbooks(self):
        """Get all current Polymarket orderbook states."""
        return self.polymarket_processor.get_all_orderbooks()
    
    def get_polymarket_market_summary(self, asset_id: str):
        """Get bid/ask/volume summary for a Polymarket asset."""
        return self.polymarket_processor.get_market_summary(asset_id)
    
    def get_all_polymarket_market_summaries(self):
        """Get market summaries for all active Polymarket assets."""
        return self.polymarket_processor.get_all_market_summaries()
    
    def force_publish_polymarket_asset(self, asset_id: str) -> bool:
        """Force immediate publication of a Polymarket asset (bypasses rate limiting)."""
        return self.polymarket_ticker_publisher.force_publish_asset(asset_id)
    
    async def restart_polymarket_ticker_publisher(self):
        """Restart the Polymarket ticker publisher."""
        await self.polymarket_ticker_publisher.stop()
        await self.polymarket_ticker_publisher.start()
        logger.info("Polymarket ticker publisher restarted")
    
    # Arbitrage Management Methods
    def add_arbitrage_market_pair(self, market_pair: str, kalshi_sid: int, polymarket_yes_asset_id: str, polymarket_no_asset_id: str):
        """Add a market pair for arbitrage monitoring."""
        return self.arbitrage_manager.add_market_pair(market_pair, kalshi_sid, polymarket_yes_asset_id, polymarket_no_asset_id)
    
    def remove_arbitrage_market_pair(self, market_pair: str):
        """Remove a market pair from arbitrage monitoring."""
        return self.arbitrage_manager.remove_market_pair(market_pair)
    
    def subscribe_to_arbitrage_alerts(self, callback):
        """Subscribe to arbitrage alert events via EventBus."""
        return self.event_bus.subscribe('arbitrage.alert', callback)
    
    async def check_arbitrage_for_pair(self, market_pair: str):
        """Check arbitrage opportunities for a specific market pair."""
        return await self.arbitrage_manager.check_arbitrage_for_pair(market_pair)
    
    async def check_all_arbitrage_opportunities(self):
        """Check arbitrage opportunities for all registered market pairs."""
        return await self.arbitrage_manager.check_all_arbitrage_opportunities()
    
    def get_arbitrage_stats(self):
        """Get arbitrage manager statistics."""
        return self.arbitrage_manager.get_stats()
    
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