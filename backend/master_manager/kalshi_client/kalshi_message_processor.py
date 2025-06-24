"""
Kalshi Message Processor - Processes raw JSON messages from KalshiQueue to maintain orderbook state.

Handles four message types:
- error: Propagated upward and logged
- ok: Successful subscription confirmation  
- orderbook_snapshot: Full orderbook state at timestamp
- orderbook_delta: Incremental orderbook updates

Maintains in-memory orderbook state per market using sid (subscription ID).
Tracks sequence numbers and validates message ordering.
"""

import json
import logging
import asyncio
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

@dataclass
class OrderbookLevel:
    """Represents a single price level in the orderbook."""
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
class OrderbookState:
    """Maintains the current state of an orderbook for a market."""
    sid: Optional[int] = None
    market_ticker: Optional[str] = None
    bids: Dict[str, OrderbookLevel] = field(default_factory=dict)
    asks: Dict[str, OrderbookLevel] = field(default_factory=dict)
    last_seq: Optional[int] = None
    last_update_time: Optional[datetime] = None
    
    def apply_snapshot(self, snapshot_data: Dict[str, Any], seq: int, timestamp: datetime) -> None:
        """Apply a full orderbook snapshot, replacing current state."""
        self.bids.clear()
        self.asks.clear()
        
        # Process bids
        for bid in snapshot_data.get('bids', []):
            price = str(bid['price'])
            self.bids[price] = OrderbookLevel(price=price, size=str(bid['size']))
        
        # Process asks  
        for ask in snapshot_data.get('asks', []):
            price = str(ask['price'])
            self.asks[price] = OrderbookLevel(price=price, size=str(ask['size']))
            
        self.last_seq = seq
        self.last_update_time = timestamp
        logger.debug(f"Applied snapshot for sid={self.sid}, seq={seq}, bids={len(self.bids)}, asks={len(self.asks)}")
    
    def apply_delta(self, delta_data: Dict[str, Any], seq: int, timestamp: datetime) -> None:
        """Apply incremental orderbook changes."""
        # Process bid changes
        for bid in delta_data.get('bids', []):
            price = str(bid['price'])
            size = str(bid['size'])
            
            if size == '0' or float(size) == 0:
                # Remove level
                self.bids.pop(price, None)
            else:
                # Update/add level
                self.bids[price] = OrderbookLevel(price=price, size=size)
        
        # Process ask changes
        for ask in delta_data.get('asks', []):
            price = str(ask['price'])
            size = str(ask['size'])
            
            if size == '0' or float(size) == 0:
                # Remove level
                self.asks.pop(price, None)
            else:
                # Update/add level
                self.asks[price] = OrderbookLevel(price=price, size=size)
                
        self.last_seq = seq
        self.last_update_time = timestamp
        logger.debug(f"Applied delta for sid={self.sid}, seq={seq}, bids={len(self.bids)}, asks={len(self.asks)}")
    
    def get_best_bid(self) -> Optional[OrderbookLevel]:
        """Get the highest bid (best bid price)."""
        if not self.bids:
            return None
        best_price = max(self.bids.keys(), key=lambda x: float(x))
        return self.bids[best_price]
    
    def get_best_ask(self) -> Optional[OrderbookLevel]:
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
    
    def calculate_yes_no_prices(self) -> Dict[str, Dict[str, Optional[float]]]:
        """
        Calculate bid/ask prices for YES/NO sides.
        
        In prediction markets:
        - YES bid = best bid price
        - YES ask = best ask price  
        - NO bid = 1 - best ask price (inverse of YES ask)
        - NO ask = 1 - best bid price (inverse of YES bid)
        
        Returns:
            Dict with format: {
                "yes": {"bid": float, "ask": float, "volume": float},
                "no": {"bid": float, "ask": float, "volume": float}
            }
        """
        best_bid = self.get_best_bid()
        best_ask = self.get_best_ask()
        
        yes_data = {
            "bid": best_bid.price_float if best_bid else None,
            "ask": best_ask.price_float if best_ask else None,
            "volume": self.get_total_bid_volume() + self.get_total_ask_volume()
        }
        
        # Calculate NO prices as inverse of YES prices
        no_data = {
            "bid": (1.0 - best_ask.price_float) if best_ask else None,
            "ask": (1.0 - best_bid.price_float) if best_bid else None, 
            "volume": self.get_total_bid_volume() + self.get_total_ask_volume()
        }
        
        return {
            "yes": yes_data,
            "no": no_data
        }

class KalshiMessageProcessor:
    """
    Processes raw Kalshi WebSocket messages to maintain orderbook state.
    
    Designed to work as the message_handler for KalshiQueue.
    Maintains separate orderbook state per market using sid.
    """
    
    def __init__(self):
        self.orderbooks: Dict[int, OrderbookState] = {}  # sid -> OrderbookState
        self.error_callback: Optional[Callable[[Dict[str, Any]], None]] = None
        self.orderbook_update_callback: Optional[Callable[[int, OrderbookState], None]] = None
        
        logger.info("KalshiMessageProcessor initialized")
    
    def set_error_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Set callback for error message handling."""
        self.error_callback = callback
        logger.info("Kalshi error callback set")
    
    def set_orderbook_update_callback(self, callback: Callable[[int, OrderbookState], None]) -> None:
        """Set callback for orderbook update notifications."""
        self.orderbook_update_callback = callback
        logger.info("Kalshi orderbook update callback set")
    
    async def handle_message(self, raw_message: str, metadata: Dict[str, Any]) -> None:
        """
        Main message handler for KalshiQueue.
        
        Args:
            raw_message: Raw JSON string from WebSocket
            metadata: Message metadata including ticker, channel, etc.
        """
        try:
            # Decode JSON
            try:
                message_data = json.loads(raw_message)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to decode Kalshi message JSON: {e}")
                logger.debug(f"Raw message: {raw_message}")
                return
            
            # Extract message type
            message_type = message_data.get('type')
            if not message_type:
                logger.warning(f"No message type found in Kalshi message: {message_data}")
                return
            
            logger.debug(f"Processing Kalshi message type: {message_type}")
            
            # Route to appropriate handler
            if message_type == 'error':
                await self._handle_error_message(message_data, metadata)
            elif message_type == 'ok':
                await self._handle_ok_message(message_data, metadata)
            elif message_type == 'orderbook_snapshot':
                await self._handle_orderbook_snapshot(message_data, metadata)
            elif message_type == 'orderbook_delta':
                await self._handle_orderbook_delta(message_data, metadata)
            else:
                logger.info(f"Unknown Kalshi message type: {message_type}")
                logger.debug(f"Message data: {message_data}")
                
        except Exception as e:
            logger.error(f"Error processing Kalshi message: {e}")
            logger.debug(f"Raw message: {raw_message}")
            logger.debug(f"Metadata: {metadata}")
    
    async def _handle_error_message(self, message_data: Dict[str, Any], metadata: Dict[str, Any]) -> None:
        """Handle error messages - log and propagate upward."""
        error_info = {
            'type': 'error',
            'message': message_data.get('msg', 'Unknown error'),
            'code': message_data.get('code'),
            'timestamp': datetime.now().isoformat(),
            'metadata': metadata
        }
        
        logger.error(f"Kalshi error received: {error_info['message']} (code: {error_info['code']})")
        
        # Propagate error upward if callback is set
        if self.error_callback:
            try:
                if asyncio.iscoroutinefunction(self.error_callback):
                    await self.error_callback(error_info)
                else:
                    self.error_callback(error_info)
            except Exception as e:
                logger.error(f"Error in error callback: {e}")
    
    async def _handle_ok_message(self, message_data: Dict[str, Any], metadata: Dict[str, Any]) -> None:
        """Handle successful subscription confirmations."""
        sid = message_data.get('sid')
        logger.info(f"Kalshi subscription successful - sid: {sid}, ticker: {metadata.get('ticker')}")
        
        # Initialize orderbook state for this market if we have sid
        if sid is not None:
            if sid not in self.orderbooks:
                self.orderbooks[sid] = OrderbookState(
                    sid=sid, 
                    market_ticker=metadata.get('ticker')
                )
                logger.info(f"Initialized orderbook state for market sid={sid}, ticker={metadata.get('ticker')}")
    
    async def _handle_orderbook_snapshot(self, message_data: Dict[str, Any], metadata: Dict[str, Any]) -> None:
        """Handle full orderbook snapshots."""
        sid = message_data.get('sid')
        seq = message_data.get('seq')
        
        if sid is None:
            logger.warning("No sid in orderbook_snapshot message")
            return
            
        if seq is None:
            logger.warning(f"No seq in orderbook_snapshot message for sid={sid}")
            return
        
        # Ensure we have orderbook state for this market
        if sid not in self.orderbooks:
            self.orderbooks[sid] = OrderbookState(
                sid=sid,
                market_ticker=metadata.get('ticker')
            )
            logger.info(f"Created new orderbook state for sid={sid}")
        
        orderbook = self.orderbooks[sid]
        current_time = datetime.now()
        
        # Check if this snapshot is newer than our last update
        if orderbook.last_seq is not None and seq <= orderbook.last_seq:
            logger.warning(f"Received old snapshot for sid={sid}: seq={seq} <= last_seq={orderbook.last_seq}")
            return
        
        # Apply the snapshot
        try:
            orderbook.apply_snapshot(message_data, seq, current_time)
            logger.info(f"Applied orderbook_snapshot for sid={sid}, seq={seq}")
            
            # Notify callback if set
            if self.orderbook_update_callback:
                try:
                    if asyncio.iscoroutinefunction(self.orderbook_update_callback):
                        await self.orderbook_update_callback(sid, orderbook)
                    else:
                        self.orderbook_update_callback(sid, orderbook)
                except Exception as e:
                    logger.error(f"Error in orderbook update callback: {e}")
                    
        except Exception as e:
            logger.error(f"Error applying orderbook_snapshot for sid={sid}: {e}")
    
    async def _handle_orderbook_delta(self, message_data: Dict[str, Any], metadata: Dict[str, Any]) -> None:
        """Handle incremental orderbook updates."""
        sid = message_data.get('sid')
        seq = message_data.get('seq')
        
        if sid is None:
            logger.warning("No sid in orderbook_delta message")
            return
            
        if seq is None:
            logger.warning(f"No seq in orderbook_delta message for sid={sid}")
            return
        
        # Ensure we have orderbook state for this market
        if sid not in self.orderbooks:
            logger.warning(f"No orderbook state for sid={sid}, cannot apply delta. Need snapshot first.")
            return
        
        orderbook = self.orderbooks[sid]
        
        # Check sequence ordering
        if orderbook.last_seq is not None:
            expected_seq = orderbook.last_seq + 1
            if seq != expected_seq:
                logger.error(f"Missing sequence for sid={sid}: expected {expected_seq}, got {seq}. "
                           f"Gap in orderbook updates detected!")
                # Could request snapshot here or implement gap handling
                return
        
        # Apply the delta
        try:
            current_time = datetime.now()
            orderbook.apply_delta(message_data, seq, current_time)
            logger.debug(f"Applied orderbook_delta for sid={sid}, seq={seq}")
            
            # Notify callback if set
            if self.orderbook_update_callback:
                try:
                    if asyncio.iscoroutinefunction(self.orderbook_update_callback):
                        await self.orderbook_update_callback(sid, orderbook)
                    else:
                        self.orderbook_update_callback(sid, orderbook)
                except Exception as e:
                    logger.error(f"Error in orderbook update callback: {e}")
                    
        except Exception as e:
            logger.error(f"Error applying orderbook_delta for sid={sid}: {e}")
    
    def get_orderbook(self, sid: int) -> Optional[OrderbookState]:
        """Get current orderbook state for a market."""
        return self.orderbooks.get(sid)
    
    def get_all_orderbooks(self) -> Dict[int, OrderbookState]:
        """Get all current orderbook states."""
        return self.orderbooks.copy()
    
    def get_summary_stats(self, sid: int) -> Optional[Dict[str, Dict[str, Optional[float]]]]:
        """
        Get yes/no bid/ask/volume summary stats for a specific market.
        
        Args:
            sid: Market subscription ID
            
        Returns:
            Dict in format expected by ticker stream integration:
            {
                "yes": {"bid": float, "ask": float, "volume": float},
                "no": {"bid": float, "ask": float, "volume": float}
            }
            Returns None if sid not found or no orderbook data.
        """
        orderbook = self.get_orderbook(sid)
        if not orderbook:
            return None
        
        return orderbook.calculate_yes_no_prices()
    
    def get_all_summary_stats(self) -> Dict[int, Dict[str, Dict[str, Optional[float]]]]:
        """
        Get summary stats for all active markets.
        
        Returns:
            Dict mapping sid -> summary_stats for all markets
        """
        result = {}
        for sid, orderbook in self.orderbooks.items():
            summary_stats = orderbook.calculate_yes_no_prices()
            result[sid] = summary_stats
        
        return result
    
    def get_stats(self) -> Dict[str, Any]:
        """Get processor statistics."""
        return {
            'active_markets': len(self.orderbooks),
            'market_sids': list(self.orderbooks.keys()),
            'processor_status': 'running'
        }