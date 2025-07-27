"""
KalshiPlatformManager - Self-contained Kalshi platform stack

Manages all Kalshi-specific components including the candlestick manager,
queue, processor, ticker publisher, and client connections.
"""
import logging
import os
from typing import Dict, Any, Optional
from datetime import datetime

from ..events.event_bus import EventBus
from ..messaging.message_forwarder import MessageForwarder
from ..connection.connection_manager import ConnectionManager
from ..kalshi_client.kalshi_queue import KalshiQueue
from ..kalshi_client.message_processor import KalshiMessageProcessor
from ..kalshi_client.candlestick_manager import CandlestickManager
from ..kalshi_client.kalshi_ticker_publisher import KalshiTickerPublisher
from ..kalshi_client.kalshi_client import KalshiClient
from ..kalshi_client.kalshi_client_config import KalshiClientConfig
from ..kalshi_client.kalshi_environment import Environment
from ..utils.tglobal_config import PUBLISH_INTERVAL_SECONDS

logger = logging.getLogger(__name__)

class KalshiPlatformManager:
    """
    Self-contained manager for all Kalshi platform components.
    
    Features:
    - Complete Kalshi messaging stack (Queue → Processor → Ticker Publisher)
    - Kalshi-specific candlestick manager integration
    - Event-driven architecture integration
    - Client lifecycle management
    - SID-based market tracking
    """
    
    def __init__(self, event_bus: EventBus, channel: str = "orderbook_delta"):
        """
        Initialize the Kalshi platform manager.
        
        Args:
            event_bus: Event bus for cross-component communication
            channel: Kalshi channel to subscribe to (default: orderbook_delta)
        """
        self.event_bus = event_bus
        self.channel = channel
        self.platform = "kalshi"
        
        # Client tracking
        self.clients: Dict[str, KalshiClient] = {}
        
        # Initialize Kalshi-specific stack
        self.queue = KalshiQueue(max_queue_size=1000)
        self.processor = KalshiMessageProcessor(event_bus=event_bus)
        self.candlestick_manager = CandlestickManager()  # Kalshi-only component
        
        # Initialize ticker publisher with candlestick integration
        self.ticker_publisher = KalshiTickerPublisher(
            kalshi_processor=self.processor,
            candlestick_manager=self.candlestick_manager,
            publish_interval=PUBLISH_INTERVAL_SECONDS
        )
        
        # Initialize messaging components
        self.message_forwarder = MessageForwarder(self.platform, self.queue)
        self.connection_manager = ConnectionManager(self.platform, self.event_bus)
        
        # Track if async components are started
        self._async_started = False
        
        # Single market tracking (maintaining legacy interface)
        self.kalshi_sid = -1 #this means no sid has actually been set yet - it's a default value for debugging
        
        # Wire up Kalshi-specific event handling
        self._wire_kalshi_specific_callbacks()
        
        logger.info("KalshiPlatformManager initialized with candlestick integration")
    
    def _wire_kalshi_specific_callbacks(self):
        """Wire up Kalshi-specific callback patterns."""
        
        # Kalshi-specific: candlestick completion forces ticker publishing
        async def emit_completed_candlestick(sid: int, candlestick):
            """Emit completed candlestick immediately via ticker publisher"""
            logger.info(f"Kalshi candlestick completed for sid={sid}, forcing ticker publish")
            self.ticker_publisher.force_publish_market(sid)
        
        self.candlestick_manager.set_candlestick_emit_callback(emit_completed_candlestick)
        
        # Set up processor callbacks to publish events
        self.processor.set_error_callback(self._handle_kalshi_error)
        self.processor.set_orderbook_update_callback(self._handle_kalshi_orderbook_update)
        
        # Connect processor to queue
        self.queue.set_message_handler(self.processor.handle_message)
        
        logger.info("Kalshi-specific callbacks wired up")
    
    async def _handle_kalshi_error(self, error_info: Dict[str, Any]) -> None:
        """Handle errors from Kalshi message processor."""
        logger.error(f"Kalshi processor error: {error_info.get('message')} (code: {error_info.get('code')})")
        
        # Publish error event
        await self.event_bus.publish('kalshi.error', {
            'platform': self.platform,
            'error_info': error_info,
            'timestamp': datetime.now().isoformat()
        })
    
    async def _handle_kalshi_orderbook_update(self, sid: str, orderbook_state) -> None:
        """Handle orderbook updates from Kalshi message processor."""
        logger.debug(f"Kalshi orderbook updated for sid={sid}, ticker={orderbook_state.market_ticker}")
        
        # Kalshi-specific: update candlestick manager
        try:
            await self.candlestick_manager.handle_orderbook_update(sid, orderbook_state)
        except Exception as e:
            logger.error(f"Error updating candlestick manager for sid={sid}: {e}")
        
        # Publish generic orderbook update event
        await self.event_bus.publish('kalshi.orderbook_update', {
            'platform': self.platform,
            'sid': sid,
            'orderbook_state': orderbook_state,
            'market_ticker': orderbook_state.market_ticker,
            'timestamp': datetime.now().isoformat()
        })
    
    async def start_async_components(self):
        """Start async components that require a running event loop."""
        if self._async_started:
            logger.info("KalshiPlatformManager async components already started")
            return
        
        try:
            # Start queue processor and ticker publisher
            await self.queue.start()
            await self.ticker_publisher.start()
            
            self._async_started = True
            logger.info("✅ KalshiPlatformManager async components started successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to start KalshiPlatformManager async components: {e}")
            raise
    
    async def connect_market(self, market_id: str) -> bool:
        """
        Connect to a Kalshi market.
        
        Args:
            market_id: Market identifier (will remove 'kalshi_' prefix if present)
            
        Returns:
            bool: True if connection successful
        """
        # Ensure async components are started
        if not self._async_started:
            await self.start_async_components()
        
        # Check if already connected
        if market_id in self.clients:
            client = self.clients[market_id]
            if client.is_running():
                logger.info(f"Kalshi {market_id} already connected")
                return True
            else:
                # Reconnect existing client
                logger.info(f"Reconnecting Kalshi {market_id}")
                return await client.connect()
        
        # Parse ticker from market_id
        ticker = market_id.removeprefix("kalshi_")
        self.kalshi_sid = hash(ticker) % 1000000  # Simple hash for SID
        
        try:
            # Create client config (URL can be overridden via KALSHI_WS_URL env var)
            config = KalshiClientConfig(
                ticker=ticker,
                channel=self.channel,
                environment=Environment.PROD,
                ping_interval=30,
                log_level="INFO",
                custom_ws_url=None  # Will use env var or default
            )
            
            client = KalshiClient(config)
            
            # Create standardized callbacks using connection manager
            message_callback, connection_callback, error_callback = self.connection_manager.create_client_callbacks(
                market_id, self.message_forwarder
            )
            
            # Set callbacks
            client.set_message_callback(message_callback)
            client.set_connection_callback(connection_callback)
            client.set_error_callback(error_callback)

            # Notify processor to expect messages from this thread (resolves TODO)
            if not self.processor:
                logger.error("Fatal error - kalshi processor not initialized at market creation time. Ensure processor reference is not being overwritten or corrupted")
                return False
            
            # Proactively initialize orderbook state in processor before messages arrive
            processor_notified = await self.processor.add_ticker(ticker, self.kalshi_sid)
            if processor_notified:
                logger.info(f"Notified processor to expect messages for ticker={ticker}, sid={self.kalshi_sid}")
            else:
                logger.warning(f"Processor already has state for ticker={ticker}, continuing with connection")
            
            # Connect to websocket
            connection_result = await client.connect()
            
            if connection_result and client.is_connected:
                self.clients[market_id] = client
                logger.info(f"Successfully connected Kalshi {market_id}")
                return True
            else:
                logger.error(f"Failed to connect Kalshi {market_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error connecting Kalshi {market_id}: {e}")
            return False
    
    async def disconnect_market(self, market_id: str) -> bool:
        """
        Disconnect from a Kalshi market.
        
        Args:
            market_id: Market identifier to disconnect
            
        Returns:
            bool: True if disconnection successful
        """
        if market_id in self.clients:
            try:
                await self.clients[market_id].disconnect()
                del self.clients[market_id]
                self.connection_manager.remove_connection(market_id)

                # Next step is to tell our message_processor to clean up state for this market_id
                # If the disconnect fails, we want to maintain orderbook state hence this comes after the client disconnect
                
                if self.processor:
                    # Parse ticker from market_id (remove "kalshi_" prefix if present)
                    ticker = market_id.removeprefix("kalshi_")
                    
                    success = await self.processor.handle_market_removed_event(ticker, market_id)
                else:
                    logger.error("Remove market called and processor is not online")
                    return False
                
                if not success:
                    logger.error("MessageProcessor failed to clean up orderbook state, memory leakage possible")
                    return False

                logger.info(f"Disconnected Kalshi {market_id} and successfully removed orderbook state")
                return True
            except Exception as e:
                logger.error(f"Error disconnecting Kalshi {market_id}: {e}")
                return False
        else:
            logger.warning(f"No active Kalshi connection found for {market_id}")
            return False
    
    async def disconnect_all(self) -> None:
        """Disconnect all Kalshi clients and stop async components."""
        logger.info("Disconnecting all Kalshi clients...")
        
        # Stop ticker publisher
        await self.ticker_publisher.stop()
        
        # Stop queue processor
        await self.queue.stop()
        
        # Disconnect all clients
        for market_id, client in self.clients.items():
            try:
                await client.disconnect()
                logger.info(f"Disconnected Kalshi {market_id}")
            except Exception as e:
                logger.error(f"Error disconnecting Kalshi {market_id}: {e}")
        
        self.clients.clear()
        self.connection_manager.clear_all_connections()
        self._async_started = False
        logger.info("All Kalshi clients disconnected")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive Kalshi platform statistics."""
        return {
            "platform": self.platform,
            "total_connections": len(self.clients),
            "async_started": self._async_started,
            "kalshi_sid": self.kalshi_sid,
            "queue_stats": self.queue.get_stats(),
            "processor_stats": self.processor.get_stats(),
            "ticker_publisher_stats": self.ticker_publisher.get_stats(),
            "message_forwarder_stats": self.message_forwarder.get_stats(),
            "connection_manager_stats": self.connection_manager.get_connection_stats(),
            "candlestick_manager_stats": self.candlestick_manager.get_stats() if hasattr(self.candlestick_manager, 'get_stats') else {},
            "client_details": {market_id: client.get_status() for market_id, client in self.clients.items()}
        }
    
    # Legacy interface methods for compatibility
    def get_orderbook(self, sid: int):
        """Get current Kalshi orderbook state for a market."""
        return self.processor.get_orderbook(sid)
    
    def get_all_orderbooks(self):
        """Get all current Kalshi orderbook states."""
        return self.processor.get_all_orderbooks()
    
    def get_summary_stats(self, sid: int):
        """Get yes/no bid/ask/volume summary for a Kalshi market.""" 
        return self.processor.get_summary_stats(sid)
    
    def get_all_summary_stats(self):
        """Get summary stats for all active Kalshi markets."""
        return self.processor.get_all_summary_stats()
    
    def force_publish_market(self, sid: int) -> bool:
        """Force immediate publication of a Kalshi market (bypasses rate limiting)."""
        return self.ticker_publisher.force_publish_market(sid)
    
    async def restart_ticker_publisher(self):
        """Restart the Kalshi ticker publisher."""
        await self.ticker_publisher.stop()
        await self.ticker_publisher.start()
        logger.info("Kalshi ticker publisher restarted")