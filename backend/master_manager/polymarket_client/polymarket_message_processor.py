"""
Polymarket Message Processor - Processes raw JSON polymarket websocket messages.

Handles four message types:
- book: Full orderbook snapshot that overwrites current state
- price_change: Price level updates (full override of specific levels)
- tick_size_change: Minimum tick size changes with temporary size=1 levels
- last_trade_price: Trade price updates (stub implementation)

Maintains in-memory orderbook state per market using asset_id.
Polymarket YES and NO markets are separate asset_ids.
"""

import json
import logging
import asyncio
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime

from .models import PolymarketOrderbookLevel, PolymarketOrderbookState

logger = logging.getLogger(__name__)

class PolymarketMessageProcessor:
    """
    Processes raw Polymarket WebSocket messages to maintain orderbook state.
    
    Designed to work as the message_handler for PolymarketQueue.
    Maintains separate orderbook state per market using asset_id.
    """
    
    def __init__(self):
        self.orderbooks: Dict[str, PolymarketOrderbookState] = {}  # asset_id -> OrderbookState
        self.error_callback: Optional[Callable[[Dict[str, Any]], None]] = None
        self.orderbook_update_callback: Optional[Callable[[str, PolymarketOrderbookState], None]] = None
        self.token_map: Dict[str, Any] = {}
        
        logger.info("PolymarketMessageProcessor initialized")
    
    def set_error_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Set callback for error message handling."""
        self.error_callback = callback
        logger.info("Polymarket error callback set")
    
    def set_orderbook_update_callback(self, callback: Callable[[str, PolymarketOrderbookState], None]) -> None:
        """Set callback for orderbook update notifications."""
        self.orderbook_update_callback = callback
        logger.info("Polymarket orderbook update callback set")
    
    async def handle_message(self, raw_message: str, metadata: Dict[str, Any]) -> None:
        """
        Main message handler for PolymarketQueue.
        
        Args:
            raw_message: Raw JSON string from WebSocket
            metadata: Message metadata including platform, subscription_id, etc.
        """
        try:
            # Decode JSON
            try:
                message_data = json.loads(raw_message)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to decode Polymarket message JSON: {e}")
                logger.debug(f"Raw message: {raw_message}")
                return
            
            # Handle both arrays and single objects
            if isinstance(message_data, list):
                # Array of messages - process each individually
                logger.debug(f"Processing Polymarket array with {len(message_data)} messages")
                for individual_message in message_data:
                    await self._process_individual_message(individual_message, metadata)
            else:
                # Single message object
                await self._process_individual_message(message_data, metadata)
                
        except Exception as e:
            logger.error(f"Error processing Polymarket message: {e}")
            logger.debug(f"Raw message: {raw_message}")
            logger.debug(f"Metadata: {metadata}")
    
    async def _process_individual_message(self, message_data: Dict[str, Any], metadata: Dict[str, Any]) -> None:
        """Process a single Polymarket message object."""
        # Extract event type - use .get() for safety
        event_type = message_data.get('event_type') or metadata.get("event_type") #in case of token map
        if not event_type:
            logger.warning(f"No event_type found in Polymarket message: {message_data}")
            return
        
        logger.debug(f"Processing Polymarket message event_type: {event_type}")
        
        # Route to appropriate handler
        if event_type == 'book':
            await self._handle_book_message(message_data, metadata)
        elif event_type == 'price_change':
            await self._handle_price_change_message(message_data, metadata)
        elif event_type == 'tick_size_change':
            await self._handle_tick_size_change_message(message_data, metadata)
        elif event_type == 'last_trade_price':
            await self._handle_last_trade_price_message(message_data, metadata)
        elif metadata.get("event_type") == "token_map":
            #merge our token maps (in case multiple subscriptions)
            self.token_map = self.token_map | message_data
        else:
            logger.info(f"Unknown Polymarket event_type: {event_type}")
            logger.debug(f"Message data: {message_data}")
    
    async def _handle_book_message(self, message_data: Dict[str, Any], metadata: Dict[str, Any]) -> None:
        """Handle full orderbook snapshots - overwrites current state."""
        asset_id = message_data.get('asset_id')
        market = message_data.get('market')
        
        if not asset_id:
            logger.warning("No asset_id in book message")
            return
        
        # Ensure we have orderbook state for this asset
        if asset_id not in self.orderbooks:
            self.orderbooks[asset_id] = PolymarketOrderbookState(
                asset_id=asset_id,
                market=market
            )
            logger.info(f"Created new orderbook state for asset_id={asset_id}")
        
        orderbook = self.orderbooks[asset_id]
        current_time = datetime.now()
        
        # Apply the book snapshot (complete overwrite)
        try:
            orderbook.apply_book_snapshot(message_data, current_time)
            logger.info(f"[BOOK_SNAPSHOT] Applied book snapshot for asset_id={asset_id}, bids={len(orderbook.bids)}, asks={len(orderbook.asks)}")
            
            # Notify callback if set
            if self.orderbook_update_callback:
                try:
                    if asyncio.iscoroutinefunction(self.orderbook_update_callback):
                        await self.orderbook_update_callback(asset_id, orderbook)
                    else:
                        self.orderbook_update_callback(asset_id, orderbook)
                except Exception as e:
                    logger.error(f"Error in orderbook update callback: {e}")
                    
        except Exception as e:
            logger.error(f"Error applying book snapshot for asset_id={asset_id}: {e}")
            logger.error(f"Message data: {message_data}")
    
    async def _handle_price_change_message(self, message_data: Dict[str, Any], metadata: Dict[str, Any]) -> None:
        """Handle price changes - full override of specific price levels."""
        asset_id = message_data.get('asset_id')
        changes = message_data.get('changes', [])
        
        if not asset_id:
            logger.warning("No asset_id in price_change message")
            return
        
        if not changes:
            logger.debug(f"No changes in price_change message for asset_id={asset_id}")
            return
        
        # Ensure we have orderbook state for this asset
        if asset_id not in self.orderbooks:
            logger.warning(f"No orderbook state for asset_id={asset_id}, cannot apply price changes. Need book message first.")
            return
        
        orderbook = self.orderbooks[asset_id]
        
        # Apply the price changes
        try:
            current_time = datetime.now()
            logger.info(f"[PRICE_CHANGE] Applying {len(changes)} price changes for asset_id={asset_id}")
            orderbook.apply_price_changes(changes, current_time)
            logger.info(f"[PRICE_CHANGE] Successfully applied price changes for asset_id={asset_id}, bids={len(orderbook.bids)}, asks={len(orderbook.asks)}")
            
            # Notify callback if set
            if self.orderbook_update_callback:
                try:
                    if asyncio.iscoroutinefunction(self.orderbook_update_callback):
                        await self.orderbook_update_callback(asset_id, orderbook)
                    else:
                        self.orderbook_update_callback(asset_id, orderbook)
                except Exception as e:
                    logger.error(f"Error in orderbook update callback: {e}")
                    
        except Exception as e:
            logger.error(f"Error applying price changes for asset_id={asset_id}: {e}")
            logger.error(f"Changes data: {changes}")
    
    async def _handle_tick_size_change_message(self, message_data: Dict[str, Any], metadata: Dict[str, Any]) -> None:
        """Handle tick size changes - create temporary levels with size=1."""
        asset_id = message_data.get('asset_id')
        old_tick_size = message_data.get('old_tick_size', '0')
        new_tick_size = message_data.get('new_tick_size', '0')
        
        if not asset_id:
            logger.warning("No asset_id in tick_size_change message")
            return
        
        # Ensure we have orderbook state for this asset
        if asset_id not in self.orderbooks:
            logger.warning(f"No orderbook state for asset_id={asset_id}, cannot apply tick size change. Need book message first.")
            return
        
        orderbook = self.orderbooks[asset_id]
        
        # Apply the tick size change
        try:
            current_time = datetime.now()
            orderbook.apply_tick_size_change(old_tick_size, new_tick_size, current_time)
            logger.info(f"Applied tick size change for asset_id={asset_id}: {old_tick_size} -> {new_tick_size}")
            
            # Notify callback if set
            if self.orderbook_update_callback:
                try:
                    if asyncio.iscoroutinefunction(self.orderbook_update_callback):
                        await self.orderbook_update_callback(asset_id, orderbook)
                    else:
                        self.orderbook_update_callback(asset_id, orderbook)
                except Exception as e:
                    logger.error(f"Error in orderbook update callback: {e}")
                    
        except Exception as e:
            logger.error(f"Error applying tick size change for asset_id={asset_id}: {e}")
    
    async def _handle_last_trade_price_message(self, message_data: Dict[str, Any], metadata: Dict[str, Any]) -> None:
        """Handle last trade price updates - stub implementation for future use."""
        asset_id = message_data.get('asset_id')
        trade_price = message_data.get('price')
        
        # Stub implementation - log for now
        logger.debug(f"Last trade price for asset_id={asset_id}: {trade_price}")
        
        # Future implementation could:
        # - Store last trade prices
        # - Calculate trade volume metrics
        # - Emit trade events
    
    def get_orderbook(self, asset_id: str) -> Optional[PolymarketOrderbookState]:
        """Get current orderbook state for an asset."""
        return self.orderbooks.get(asset_id)
    
    def get_all_orderbooks(self) -> Dict[str, PolymarketOrderbookState]:
        """Get all current orderbook states."""
        return self.orderbooks.copy()
    
    def get_market_summary(self, asset_id: str) -> Optional[Dict[str, Optional[float]]]:
        """
        Get bid/ask/volume summary for a specific asset.
        
        Args:
            asset_id: Asset ID for the market
            
        Returns:
            Dict in format:
            {
                "bid": float,
                "ask": float,
                "volume": float
            }
            Returns None if asset_id not found or no orderbook data.
        """
        orderbook = self.get_orderbook(asset_id)
        if not orderbook:
            return None
        
        return orderbook.calculate_market_prices()
    
    def get_all_market_summaries(self) -> Dict[str, Dict[str, Optional[float]]]:
        """
        Get market summaries for all active assets.
        
        Returns:
            Dict mapping asset_id -> market_summary for all assets

            so 
            "yes": {"bid": ,"ask": ,"volume": },
            "no": {"bid": ,"ask": ,"volume": }
        
        Limitations: 
            can only deal with one polymarket subscription at a time - multiplexed subscriptions will need to be added later
        """
        result = {}
        condition_ids = []
        for asset_id, orderbook in self.orderbooks.items():
            market_summary = orderbook.calculate_market_prices()
            #translate orderbook id into yes/no

            if asset_id not in self.token_map:
                raise KeyError(f"Major error: token_map key not in value. Current keys are {self.token_map.keys()} with type {type(self.token_map.keys())} while our asset_id is {asset_id} with type {type(asset_id)}")
            
            #gives us "YES": market_summary
            result[(self.token_map[asset_id]).lower()] = market_summary

            #CAN ONLY DEAL WITH ONE POLYMARKET SUBSCRIPTION AT A TIME:
            condition_ids.append(asset_id)
        
        #now map the token_id to our result - this will be used to create the right channel
        result["token_id"] = f"polymarket_{",".join(condition_ids)}"
        
        return result
    
    def get_stats(self) -> Dict[str, Any]:
        """Get processor statistics."""
        return {
            'active_assets': len(self.orderbooks),
            'asset_ids': list(self.orderbooks.keys()),
            'processor_status': 'running'
        }