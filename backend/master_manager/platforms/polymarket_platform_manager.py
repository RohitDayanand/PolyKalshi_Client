"""
PolymarketPlatformManager - Self-contained Polymarket platform stack

Manages all Polymarket-specific components including YES/NO market pairing logic,
queue, processor, ticker publisher, and client connections.
"""
import json
import logging
import os
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
import asyncio

from ..events.event_bus import EventBus
from ..messaging.message_forwarder import MessageForwarder
from ..connection.connection_manager import ConnectionManager
from ..polymarket_client.polymarket_queue import PolymarketQueue
from ..polymarket_client.polymarket_message_processor import PolymarketMessageProcessor
from ..polymarket_client.polymarket_ticker_publisher import PolymarketTickerPublisher
from ..polymarket_client.polymarket_client import PolymarketClient, PolymarketClientConfig
from ..utils.tglobal_config import PUBLISH_INTERVAL_SECONDS

logger = logging.getLogger(__name__)

class PolymarketPlatformManager:
    """
    Self-contained manager for all Polymarket platform components.
    
    Features:
    - Complete Polymarket messaging stack (Queue → Processor → Ticker Publisher)
    - YES/NO market pairing logic for prediction markets
    - Token ID array handling
    - Event-driven architecture integration
    - Client lifecycle management
    - Asset ID-based market tracking
    """
    
    def __init__(self, event_bus: EventBus):
        """
        Initialize the Polymarket platform manager.
        
        Args:
            event_bus: Event bus for cross-component communication
        """
        self.event_bus = event_bus
        self.platform = "polymarket"
        
        # Client tracking
        self.clients: Dict[str, PolymarketClient] = {}
        
        # Initialize Polymarket-specific stack
        self.queue = PolymarketQueue(max_queue_size=1000)
        self.processor = PolymarketMessageProcessor()
        
        # Initialize ticker publisher (no candlestick manager for Polymarket)
        self.ticker_publisher = PolymarketTickerPublisher(
            polymarket_processor=self.processor,
            publish_interval=PUBLISH_INTERVAL_SECONDS
        )
        
        # Initialize messaging components
        self.message_forwarder = MessageForwarder(self.platform, self.queue)
        self.connection_manager = ConnectionManager(self.platform, self.event_bus)
        
        # Track if async components are started
        self._async_started = False
        
        # Single market tracking (maintaining legacy interface)
        self.polymarket_yes_id = ""
        self.polymarket_no_id = ""
        
        # Wire up Polymarket-specific event handling
        self._wire_polymarket_specific_callbacks()
        
        logger.info("PolymarketPlatformManager initialized with YES/NO pairing logic")
    
    def _wire_polymarket_specific_callbacks(self):
        """Wire up Polymarket-specific callback patterns."""
        
        # Set up processor callbacks to publish events
        self.processor.set_error_callback(self._handle_polymarket_error)
        self.processor.set_orderbook_update_callback(self._handle_polymarket_orderbook_update)
        
        # Connect processor to queue
        self.queue.set_message_handler(self.processor.handle_message)
        
        logger.info("Polymarket-specific callbacks wired up")
    
    async def _handle_polymarket_error(self, error_info: Dict[str, Any]) -> None:
        """Handle errors from Polymarket message processor."""
        logger.error(f"Polymarket processor error: {error_info.get('message')}")
        
        # Publish error event
        await self.event_bus.publish('polymarket.error', {
            'platform': self.platform,
            'error_info': error_info,
            'timestamp': datetime.now().isoformat()
        })
    
    async def _handle_polymarket_orderbook_update(self, asset_id: str, orderbook_state) -> None:
        """Handle orderbook updates from Polymarket message processor."""
        logger.debug(f"Polymarket orderbook updated for asset_id={asset_id}, market={orderbook_state.market}")
        
        # Publish generic orderbook update event
        await self.event_bus.publish('polymarket.orderbook_update', {
            'platform': self.platform,
            'asset_id': asset_id,
            'orderbook_state': orderbook_state,
            'market': orderbook_state.market,
            'timestamp': datetime.now().isoformat()
        })
    
    def _parse_token_ids(self, market_identifier: str) -> List[str]:
        """
        Parse token IDs from market identifier.
        
        Supports both JSON arrays and comma-separated strings.
        
        Args:
            market_identifier: Token IDs as JSON array or comma-separated string
            
        Returns:
            List[str]: Parsed token IDs
        """
        try:
            # Try parsing as JSON first
            if market_identifier.startswith('[') and market_identifier.endswith(']'):
                token_ids = json.loads(market_identifier)
                logger.info(f"Parsed JSON token IDs: {token_ids}")
                return token_ids
        except (json.JSONDecodeError, TypeError):
            pass
        
        # Fall back to comma-separated parsing
        if ',' in market_identifier:
            token_ids = [token.strip() for token in market_identifier.split(',')]
            # Remove polymarket prefix from first token if present
            if token_ids and token_ids[0].startswith('polymarket_'):
                token_ids[0] = token_ids[0].removeprefix('polymarket_')
            logger.info(f"Parsed comma-separated token IDs: {token_ids}")
            return token_ids
        
        # Single token ID
        single_token = market_identifier.removeprefix('polymarket_')
        logger.info(f"Single token ID: {single_token}")
        return [single_token]
    
    def _setup_yes_no_tracking(self, token_ids: List[str]) -> None:
        """
        Set up YES/NO token tracking for prediction markets.
        
        Args:
            token_ids: List of token IDs (expects [YES_token, NO_token] for pairs)
        """
        if len(token_ids) >= 2:
            self.polymarket_yes_id = token_ids[0]
            self.polymarket_no_id = token_ids[1]
            logger.info(f"YES/NO pairing: YES={self.polymarket_yes_id}, NO={self.polymarket_no_id}")
        elif len(token_ids) == 1:
            self.polymarket_yes_id = token_ids[0]
            self.polymarket_no_id = ""
            logger.info(f"Single token tracking: {self.polymarket_yes_id}")
    
    async def start_async_components(self):
        """Start async components that require a running event loop."""
        if self._async_started:
            logger.info("PolymarketPlatformManager async components already started")
            return
        
        try:
            # Start queue processor and ticker publisher
            await self.queue.start()
            await self.ticker_publisher.start()
            
            self._async_started = True
            logger.info("✅ PolymarketPlatformManager async components started successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to start PolymarketPlatformManager async components: {e}")
            raise
    
    async def connect_market(self, market_id: str) -> bool:
        """
        Connect to a Polymarket market.
        
        Args:
            market_id: Market identifier (token IDs as JSON array or comma-separated)
            
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
                logger.info(f"Polymarket {market_id} already connected")
                return True
            else:
                # Reconnect existing client
                logger.info(f"Reconnecting Polymarket {market_id}")
                return await client.connect()
        
        # Parse token IDs and set up YES/NO tracking
        token_ids = self._parse_token_ids(market_id)
        self._setup_yes_no_tracking(token_ids)
        
        try:
            # Check for debug logging environment variable
            debug_logging = os.getenv('POLYMARKET_DEBUG_LOGGING', 'false').lower() == 'true'
            
            # Create client config with token_ids (URL can be overridden via POLYMARKET_WS_URL env var)
            config = PolymarketClientConfig(
                slug="default-polymarket-subscription",
                ws_url=None,  # Will use env var or default
                ping_interval=30,
                log_level="INFO",
                token_ids=token_ids,
                debug_websocket_logging=debug_logging,
                debug_log_file=None
            )
            
            client = PolymarketClient(config)
            
            # Create standardized callbacks using connection manager
            message_callback, connection_callback, error_callback = self.connection_manager.create_client_callbacks(
                market_id, self.message_forwarder
            )
            
            # Set callbacks
            client.set_message_callback(message_callback)
            client.set_connection_callback(connection_callback)
            client.set_error_callback(error_callback)
            
            # Connect to websocket
            connection_result = await client.connect()
            
            if connection_result and client.is_connected:
                self.clients[market_id] = client
                logger.info(f"Successfully connected Polymarket {market_id}")
                return True
            else:
                logger.error(f"Failed to connect Polymarket {market_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error connecting Polymarket {market_id}: {e}")
            return False
    
    async def disconnect_market(self, market_id: str) -> bool:
        """
        Disconnect from a Polymarket market.
        
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

                #next step is to tell our message_processor to ignore messages with this market_id
                #if the disconnect fails, we want to maintain orderbook state hence this comes after the self.clients disconnect

                if self.processor:

                    token_ids: List[str] = self._parse_token_ids(market_id)

                    success = await self.processor.handle_tokens_removed_event(token_ids, market_id)
                else:
                    logger.error("Remove markets called and processor is not online")
                
                if not success:
                    logger.error("MessageProcessor is still maintaining old orderbook state, memory leakage possible")
                    return False

                logger.info(f"Disconnected Polymarket {market_id} and successfuly removed orderbook state")
                return True
            except Exception as e:
                logger.error(f"Error disconnecting Polymarket {market_id}: {e}")
                return False
        else:
            logger.warning(f"No active Polymarket connection found for {market_id}")
            return False
    
    async def disconnect_all(self) -> None:
        """Disconnect all Polymarket clients and stop async components."""
        logger.info("Disconnecting all Polymarket clients...")
        
        # Stop ticker publisher
        await self.ticker_publisher.stop()
        
        # Stop queue processor
        await self.queue.stop()
        
        # Disconnect all clients
        for market_id, client in self.clients.items():
            try:
                await client.disconnect()
                logger.info(f"Disconnected Polymarket {market_id}")
            except Exception as e:
                logger.error(f"Error disconnecting Polymarket {market_id}: {e}")
        
        self.clients.clear()
        self.connection_manager.clear_all_connections()
        self._async_started = False
        logger.info("All Polymarket clients disconnected")
    
    async def add_tokens_to_market(self, market_id: str) -> Dict[str, Any]:
        """Add tokens to market subscription with fail-fast validation."""
        add_tokens = self._parse_token_ids(market_id)
        return await self._execute_token_operation(market_id, "add", add_tokens)
    
    async def remove_tokens_from_market(self, market_id: str, remove_tokens: List[str]) -> Dict[str, Any]:
        """Remove tokens from market subscription with fail-fast validation.""" 
        return await self._execute_token_operation(market_id, "remove", remove_tokens)
    
    async def _execute_token_operation(self, market_id: str, operation: str, tokens: List[str]) -> Dict[str, Any]:
        """Execute token operation with fail-fast and simple rollback."""
        # Fail-fast validation
        if error := self._validate_operation(market_id, operation, tokens):
            await self._handle_operation_result(market_id, operation, False, error=error)
            return {"success": False, "error": error}
        
        # Store original state and execute
        client = self.clients[market_id]
        original_tokens = client.token_id.copy() if client.token_id else []
        
        try:
            # Execute the risky WebSocket operation first
            if operation == "add":
                success = await client.add_ticker(tokens)
            else:  # remove
                success = await client.remove_ticker(tokens)
            
            if not success:
                await self._handle_operation_result(market_id, operation, False, error="Client operation failed")
                return {"success": False, "error": "client_operation_failed"}
            
            # Update tracking and notify success
            self._update_tracking(client.token_id or [])
            result_data = {"tokens": tokens, "total": len(client.token_id or [])}
            await self._handle_operation_result(market_id, operation, True, data=result_data)
            
            return {"success": True, **result_data}
            
        except Exception as e:
            # Simple rollback
            await self._rollback_client(client, original_tokens, market_id)
            await self._handle_operation_result(market_id, operation, False, error=str(e))
            return {"success": False, "error": str(e)}
    
    def _validate_operation(self, market_id: str, operation: str, tokens: List[str]) -> Optional[str]: #
        """Validate operation - return error message or None if valid."""
        if not tokens:
            return f"{operation}_tokens list cannot be empty"
        if market_id not in self.clients:
            return f"No client found for market {market_id}"
        if not self.clients[market_id].is_connected:
            return f"Client for market {market_id} is not connected"
        return None
    
    def _update_tracking(self, current_tokens: List[str]):
        """Update YES/NO tracking from current tokens."""
        # Handle empty string quirk
        if current_tokens == [""]:
            current_tokens = []
        
        self.polymarket_yes_id = current_tokens[0] if len(current_tokens) > 0 else ""
        self.polymarket_no_id = current_tokens[1] if len(current_tokens) > 1 else ""
    
    async def _rollback_client(self, client, original_tokens: List[str], market_id: str):
        """Simple rollback - restore original subscription."""
        try:
            client.token_id = original_tokens
            await client.subscribe()
            self._update_tracking(original_tokens)
            logger.info(f"Rollback successful for market {market_id}")
        except Exception as e:
            logger.error(f"Rollback failed for market {market_id}: {e}")
            await self.event_bus.publish('polymarket.client_inconsistent', {
                'market_id': market_id, 'error': str(e)
            })
    
    async def _handle_operation_result(self, market_id: str, operation: str, success: bool, 
                                     data: Dict[str, Any] = None, error: str = None):
        """Unified handler for operation success/failure."""
        # Update components asynchronously (fire-and-forget)
        if success:
            asyncio.create_task(self._notify_components(market_id, operation, data))
        
        # Notify frontend
        await self.event_bus.publish(f'frontend.notify.{market_id}', {
            'type': f'polymarket_{operation}_{"success" if success else "error"}',
            'market_id': market_id,
            'data' if success else 'error': data if success else error,
            'timestamp': datetime.now().isoformat()
        })
    
    async def _notify_components(self, market_id: str, operation: str, data: Dict[str, Any]):
        """Notify other components of token changes."""
        try:
            await self.event_bus.publish(f'polymarket.tokens_{operation}d', {
                'market_id': market_id,
                'platform': self.platform,
                **data,
                'timestamp': datetime.now().isoformat()
            })
        except Exception as e:
            logger.error(f"Failed to notify components for {market_id}: {e}")
    
    def get_market_token_info(self, market_id: str) -> Dict[str, Any]:
        """Get current token info for a market."""
        if market_id not in self.clients:
            return {"error": "Market not found"}
        
        client = self.clients[market_id]
        tokens = client.token_id or []
        if tokens == [""]:
            tokens = []
        
        return {
            "market_id": market_id,
            "tokens": tokens,
            "count": len(tokens),
            "connected": client.is_connected,
            "yes_id": self.polymarket_yes_id,
            "no_id": self.polymarket_no_id
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive Polymarket platform statistics."""
        return {
            "platform": self.platform,
            "total_connections": len(self.clients),
            "async_started": self._async_started,
            "polymarket_yes_id": self.polymarket_yes_id,
            "polymarket_no_id": self.polymarket_no_id,
            "queue_stats": self.queue.get_stats(),
            "processor_stats": self.processor.get_stats(),
            "ticker_publisher_stats": self.ticker_publisher.get_stats(),
            "message_forwarder_stats": self.message_forwarder.get_stats(),
            "connection_manager_stats": self.connection_manager.get_connection_stats(),
            "client_details": {market_id: client.get_status() for market_id, client in self.clients.items()}
        }
    
    # Legacy interface methods for compatibility
    def get_orderbook(self, asset_id: str):
        """Get current Polymarket orderbook state for an asset."""
        return self.processor.get_orderbook(asset_id)
    
    def get_all_orderbooks(self):
        """Get all current Polymarket orderbook states."""
        return self.processor.get_all_orderbooks()
    
    def get_market_summary(self, asset_id: str):
        """Get bid/ask/volume summary for a Polymarket asset."""
        return self.processor.get_market_summary(asset_id)
    
    def get_all_market_summaries(self):
        """Get market summaries for all active Polymarket assets."""
        return self.processor.get_all_market_summaries()
    
    def force_publish_asset(self, asset_id: str) -> bool:
        """Force immediate publication of a Polymarket asset (bypasses rate limiting)."""
        return self.ticker_publisher.force_publish_asset(asset_id)
    
    async def restart_ticker_publisher(self):
        """Restart the Polymarket ticker publisher."""
        await self.ticker_publisher.stop()
        await self.ticker_publisher.start()
        logger.info("Polymarket ticker publisher restarted")