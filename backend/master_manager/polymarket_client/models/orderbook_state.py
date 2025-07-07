"""
Polymarket orderbook state model.

Maintains the current state of an orderbook for a Polymarket asset.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime

from .orderbook_level import PolymarketOrderbookLevel

logger = logging.getLogger(__name__)


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
            price = float(change.get('price', '0'))
            side = change.get('side', '').upper()
            size = float(change.get('size', '0'))
            
            if price == '0':
                continue
                
            if side == 'BUY':
                # Update bid side
                if size == '0' or float(size) == 0:
                    # Remove level
                    self.bids.pop(price, None)
                else:
                    # Update/add level (full override)
                    self.bids[price].set_size(size)
                    
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