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
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

@dataclass
class PolymarketOrderbookLevel:
    """Represents a single price level in the Polymarket orderbook."""
    price: str
    size: str
    
    @property
    def price_float(self) -> float:
        """Get price as float."""
        return float(self.price)
    
    @property 
    def size_float(self) -> float:
        """Get size as float."""
        return float(self.size)

@dataclass 
class PolymarketOrderbookState:
    """Maintains the current state of an orderbook for a Polymarket asset."""
    asset_id: Optional[str] = None
    market: Optional[str] = None  # Market address
    bids: Dict[str, PolymarketOrderbookLevel] = field(default_factory=dict)
    asks: Dict[str, PolymarketOrderbookLevel] = field(default_factory=dict)
    last_update_time: Optional[datetime] = None
    last_hash: Optional[str] = None
    last_timestamp: Optional[str] = None
    
    def apply_book_snapshot(self, message_data: Dict[str, Any], timestamp: datetime) -> None:
        """Apply a full orderbook snapshot, replacing current state."""
        self.bids.clear()
        self.asks.clear()
        
        # Process bids - use .get() for safety
        for bid in message_data.get('bids', []):
            price = str(bid.get('price', '0'))
            size = str(bid.get('size', '0'))
            if price != '0' and size != '0':
                self.bids[price] = PolymarketOrderbookLevel(price=price, size=size)
        
        # Process asks - use .get() for safety
        for ask in message_data.get('asks', []):
            price = str(ask.get('price', '0'))
            size = str(ask.get('size', '0'))
            if price != '0' and size != '0':
                self.asks[price] = PolymarketOrderbookLevel(price=price, size=size)
                
        # Update metadata
        self.last_update_time = timestamp
        self.last_hash = message_data.get('hash')
        self.last_timestamp = message_data.get('timestamp')
        
        logger.debug(f"Applied book snapshot for asset_id={self.asset_id}, bids={len(self.bids)}, asks={len(self.asks)}")
    
    def apply_price_changes(self, changes: List[Dict[str, Any]], timestamp: datetime) -> None:
        """Apply price changes - full override of specific price levels."""
        for change in changes:
            price = str(change.get('price', '0'))
            side = change.get('side', '').upper()
            size = str(change.get('size', '0'))
            
            if price == '0':
                continue
                
            if side == 'BUY':
                # Update bid side
                if size == '0' or float(size) == 0:
                    # Remove level
                    self.bids.pop(price, None)
                else:
                    # Update/add level (full override)
                    self.bids[price] = PolymarketOrderbookLevel(price=price, size=size)
                    
            elif side == 'SELL':
                # Update ask side
                if size == '0' or float(size) == 0:
                    # Remove level
                    self.asks.pop(price, None)
                else:
                    # Update/add level (full override)
                    self.asks[price] = PolymarketOrderbookLevel(price=price, size=size)
        
        self.last_update_time = timestamp
        logger.debug(f"Applied price changes for asset_id={self.asset_id}, bids={len(self.bids)}, asks={len(self.asks)}")
    
    def apply_tick_size_change(self, old_tick_size: str, new_tick_size: str, timestamp: datetime) -> None:
        """Apply tick size change - create temporary levels with size=1."""
        # Create a temporary level at the new tick size with size=1
        # This will be overwritten by subsequent price_change messages
        temp_price = new_tick_size
        temp_level = PolymarketOrderbookLevel(price=temp_price, size="1")
        
        # Add to both sides as temporary placeholder
        self.bids[temp_price] = temp_level
        self.asks[temp_price] = temp_level
        
        self.last_update_time = timestamp
        logger.debug(f"Applied tick size change for asset_id={self.asset_id}, old={old_tick_size}, new={new_tick_size}")
    
    def get_best_bid(self) -> Optional[PolymarketOrderbookLevel]:
        """Get the highest bid (best bid price)."""
        if not self.bids:
            return None
        best_price = max(self.bids.keys(), key=lambda x: float(x))
        return self.bids[best_price]
    
    def get_best_ask(self) -> Optional[PolymarketOrderbookLevel]:
        """Get the lowest ask (best ask price)."""
        if not self.asks:
            return None
        best_price = min(self.asks.keys(), key=lambda x: float(x))
        return self.asks[best_price]
    
    def get_total_bid_volume(self) -> float:
        """Calculate total volume on bid side."""
        return sum(level.size_float for level in self.bids.values())
    
    def get_total_ask_volume(self) -> float:
        """Calculate total volume on ask side."""
        return sum(level.size_float for level in self.asks.values())
    
    def calculate_market_prices(self) -> Dict[str, Optional[float]]:
        """
        Calculate bid/ask prices for this market.
        
        Returns:
            Dict with format: {
                "bid": float,
                "ask": float,
                "volume": float
            }
        """
        best_bid = self.get_best_bid()
        best_ask = self.get_best_ask()
        
        return {
            "bid": best_bid.price_float if best_bid else None,
            "ask": best_ask.price_float if best_ask else None,
            "volume": self.get_total_bid_volume() + self.get_total_ask_volume()
        }

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
            
            # Extract event type - use .get() for safety
            event_type = message_data.get('event_type')
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
            else:
                logger.info(f"Unknown Polymarket event_type: {event_type}")
                logger.debug(f"Message data: {message_data}")
                
        except Exception as e:
            logger.error(f"Error processing Polymarket message: {e}")
            logger.debug(f"Raw message: {raw_message}")
            logger.debug(f"Metadata: {metadata}")
    
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
            logger.info(f"Applied book snapshot for asset_id={asset_id}")
            
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
            orderbook.apply_price_changes(changes, current_time)
            logger.debug(f"Applied price changes for asset_id={asset_id}")
            
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
        """
        result = {}
        for asset_id, orderbook in self.orderbooks.items():
            market_summary = orderbook.calculate_market_prices()
            result[asset_id] = market_summary
        
        return result
    
    def get_stats(self) -> Dict[str, Any]:
        """Get processor statistics."""
        return {
            'active_assets': len(self.orderbooks),
            'asset_ids': list(self.orderbooks.keys()),
            'processor_status': 'running'
        }