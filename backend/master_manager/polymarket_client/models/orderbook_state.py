"""
Polymarket orderbook state model.

Maintains the current state of an orderbook for a Polymarket asset.

Usage 
1. async apply_book_snapshot(Data) 
    applies book snapshot and does an atomic swap of orderbook state 
2. async 

@TODO - check for remaining sync logic and remove it 
"""

import logging
import asyncio
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime

from .orderbook_level import PolymarketOrderbookLevel
from backend.master_manager.events.event_bus import global_event_bus

logger = logging.getLogger()


@dataclass(frozen=True)
class PolymarketOrderbookSnapshot:
    """Immutable snapshot of Polymarket orderbook state at a point in time."""
    asset_id: Optional[str] = None
    market: Optional[str] = None  # Market address
    bids: Dict[str, PolymarketOrderbookLevel] = field(default_factory=dict)
    asks: Dict[str, PolymarketOrderbookLevel] = field(default_factory=dict)
    last_update_time: Optional[datetime] = None
    last_hash: Optional[str] = None
    last_timestamp: Optional[str] = None
    # Cached best prices for O(1) access
    best_bid_price: Optional[str] = None
    best_ask_price: Optional[str] = None
    
    def get_best_bid(self) -> Optional[PolymarketOrderbookLevel]:
        """Get the highest bid (best bid price) - O(1) using cached value."""
        if self.best_bid_price and self.best_bid_price in self.bids:
            return self.bids[self.best_bid_price]
        return None
    
    def get_best_ask(self) -> Optional[PolymarketOrderbookLevel]:
        """Get the lowest ask (best ask price) - O(1) using cached value."""
        if self.best_ask_price and self.best_ask_price in self.asks:
            return self.asks[self.best_ask_price]
        return None
    
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
                "volume": float,
                "last_timestamp": str (timestamp from last message)
            }
        """
        best_bid = self.get_best_bid()
        best_ask = self.get_best_ask()
        
        return {
            "bid": best_bid.price_float if best_bid else None,
            "ask": best_ask.price_float if best_ask else None,
            "volume": self.get_total_bid_volume() + self.get_total_ask_volume(),
            "last_timestamp": self.last_timestamp
        }

class AtomicPolymarketOrderbookState:
    """Thread-safe Polymarket orderbook state using atomic reference swaps with copy-on-write."""
    
    def __init__(self, asset_id: Optional[str] = None, market: Optional[str] = None):
        """Initialize with empty orderbook state."""
        self._current_snapshot = PolymarketOrderbookSnapshot(
            asset_id=asset_id,
            market=market,
            bids={},
            asks={},
            last_update_time=None,
            last_hash=None,
            last_timestamp=None,
            best_bid_price=None,
            best_ask_price=None
        )
        self._update_lock = asyncio.Lock()
    
    def get_snapshot(self) -> PolymarketOrderbookSnapshot:
        """Get current immutable snapshot - lock-free read."""
        return self._current_snapshot
    
    async def get_snapshot_async(self) -> PolymarketOrderbookSnapshot:
        """Async version for consistency with other async methods."""
        return self._current_snapshot
    
    @staticmethod
    def _calculate_best_prices(bids: Dict[str, PolymarketOrderbookLevel], 
                              asks: Dict[str, PolymarketOrderbookLevel]) -> tuple[Optional[str], Optional[str]]:
        """
        Calculate best bid and ask prices from orderbook dictionaries.
        
        Args:
            bids: Dictionary of bid price levels
            asks: Dictionary of ask price levels
            
        Returns:
            Tuple of (best_bid_price, best_ask_price)
        """
        best_bid_price = max(bids.keys(), key=lambda x: float(x)) if bids else None
        best_ask_price = min(asks.keys(), key=lambda x: float(x)) if asks else None
        return best_bid_price, best_ask_price
    
    # Pass-through properties for backward compatibility
    @property
    def asset_id(self) -> Optional[str]:
        """Get the asset_id from current snapshot."""
        return self._current_snapshot.asset_id
    
    @property 
    def market(self) -> Optional[str]:
        """Get the market from current snapshot."""
        return self._current_snapshot.market
    
    @property
    def last_update_time(self) -> Optional[datetime]:
        """Get the last update time from current snapshot."""
        return self._current_snapshot.last_update_time
    
    @property
    def last_hash(self) -> Optional[str]:
        """Get the last hash from current snapshot."""
        return self._current_snapshot.last_hash
    
    @property
    def last_timestamp(self) -> Optional[str]:
        """Get the last timestamp from current snapshot."""
        return self._current_snapshot.last_timestamp
    
    @property
    def bids(self) -> Dict[str, PolymarketOrderbookLevel]:
        """Get the bids from current snapshot."""
        return self._current_snapshot.bids
    
    @property
    def asks(self) -> Dict[str, PolymarketOrderbookLevel]:
        """Get the asks from current snapshot."""
        return self._current_snapshot.asks
    
    def get_best_bid(self) -> Optional[PolymarketOrderbookLevel]:
        """Get the highest bid (best bid price) - O(1) using cached value."""
        return self._current_snapshot.get_best_bid()
    
    def get_best_ask(self) -> Optional[PolymarketOrderbookLevel]:
        """Get the lowest ask (best ask price) - O(1) using cached value."""
        return self._current_snapshot.get_best_ask()
    
    def get_total_bid_volume(self) -> float:
        """Calculate total volume on bid side."""
        return self._current_snapshot.get_total_bid_volume()
    
    def get_total_ask_volume(self) -> float:
        """Calculate total volume on ask side."""
        return self._current_snapshot.get_total_ask_volume()
    
    def calculate_market_prices(self) -> Dict[str, Optional[float]]:
        """Calculate bid/ask prices for this market - delegates to current snapshot."""
        return self._current_snapshot.calculate_market_prices()
    
    async def apply_book_snapshot(self, message_data: Dict[str, Any], timestamp: datetime) -> None:
        """Apply a full orderbook snapshot, replacing current state."""
        async with self._update_lock:
            new_bids = {}
            new_asks = {}
            
            # Process bids - use .get() for safety
            for bid in message_data.get('bids', []):
                price = str(bid.get('price', '0'))
                size = str(bid.get('size', '0'))
                if price != '0' and size != '0':
                    new_bids[price] = PolymarketOrderbookLevel(price=price, size=size)
            
            # Process asks - use .get() for safety
            for ask in message_data.get('asks', []):
                price = str(ask.get('price', '0'))
                size = str(ask.get('size', '0'))
                if price != '0' and size != '0':
                    new_asks[price] = PolymarketOrderbookLevel(price=price, size=size)
            
            # Calculate best prices for O(1) access
            best_bid_price, best_ask_price = self._calculate_best_prices(new_bids, new_asks)
            
            # Atomic swap - create new immutable snapshot
            self._current_snapshot = PolymarketOrderbookSnapshot(
                asset_id=self._current_snapshot.asset_id,
                market=self._current_snapshot.market,
                bids=new_bids,
                asks=new_asks,
                last_update_time=timestamp,
                last_hash=message_data.get('hash'),
                last_timestamp=message_data.get('timestamp'),
                best_bid_price=best_bid_price,
                best_ask_price=best_ask_price
            )
            
            logger.info(f"[BOOK_SNAPSHOT] Applied book snapshot for asset_id={self._current_snapshot.asset_id}, processed {len(new_bids)} bids, {len(new_asks)} asks, timestamp={self._current_snapshot.last_timestamp}")
    
    async def apply_price_changes(self, changes: List[Dict[str, Any]], timestamp: datetime) -> None:
        """Apply price changes - full override of specific price levels."""
        async with self._update_lock:
            current = self._current_snapshot
            
            # Copy current state for modification
            #is this efficient
            new_bids = dict(current.bids)
            new_asks = dict(current.asks)
            
            changes_applied = []
            
            for change in changes:
                price_str = str(change.get('price', '0'))
                side = change.get('side', '').upper()
                size_str = str(change.get('size', '0'))
                bid_ask_popped = False
                
                if price_str == '0' or float(price_str) == 0:
                    continue
                    
                if side == 'BUY':
                    # Update bid side
                    if size_str == '0' or float(size_str) == 0:
                        # Remove level
                        if price_str in new_bids:
                            new_bids.pop(price_str, None)
                            changes_applied.append(f"REMOVED BID@{price_str}")

                    else:
                        # Update/add level (full override)
                        if price_str in new_bids:
                            new_bids[price_str] = PolymarketOrderbookLevel(price=price_str, size=size_str)
                            changes_applied.append(f"UPDATED BID@{price_str}={size_str}")
                        else:
                            new_bids[price_str] = PolymarketOrderbookLevel(price=price_str, size=size_str)
                            changes_applied.append(f"ADDED BID@{price_str}={size_str}")
                        
                elif side == 'SELL':
                    # Update ask side
                    if size_str == '0' or float(size_str) == 0:
                        # Remove level
                        if price_str in new_asks:
                            new_asks.pop(price_str, None)
                            changes_applied.append(f"REMOVED ASK@{price_str}")
                    else:
                        # Update/add level (full override)
                        new_asks[price_str] = PolymarketOrderbookLevel(price=price_str, size=size_str)
                        changes_applied.append(f"UPDATED ASK@{price_str}={size_str}")
            
            # Calculate best prices for O(1) access
            best_bid_price, best_ask_price = self._calculate_best_prices(new_bids, new_asks)
            
            # Capture old values before updating snapshot to avoid memory leak
            old_best_bid = current.best_bid_price
            old_best_ask = current.best_ask_price

            # Atomic swap - create new immutable snapshot
            self._current_snapshot = PolymarketOrderbookSnapshot(
                asset_id=current.asset_id,
                market=current.market,
                bids=new_bids,
                asks=new_asks,
                last_update_time=timestamp,
                last_hash=current.last_hash,
                last_timestamp=current.last_timestamp,
                best_bid_price=best_bid_price,
                best_ask_price=best_ask_price
            )
            
            await self.bid_ask_helper(best_bid_price, best_ask_price, old_best_bid, old_best_ask)

            logger.info(f"[PRICE_CHANGES] Applied {len(changes_applied)} changes for asset_id={current.asset_id}: {', '.join(changes_applied)}")
    
    async def apply_tick_size_change(self, old_tick_size: str, new_tick_size: str, timestamp: datetime) -> None:
        """Apply tick size change - create temporary levels with size=1."""
        async with self._update_lock:
            current = self._current_snapshot
            
            # Copy current state for modification
            new_bids = dict(current.bids)
            new_asks = dict(current.asks)
            
            # Create a temporary level at the new tick size with size=1
            # This will be overwritten by subsequent price_change messages
            temp_price = new_tick_size
            temp_level = PolymarketOrderbookLevel(price=temp_price, size="1")
            
            # Add to both sides as temporary placeholder
            new_bids[temp_price] = temp_level
            new_asks[temp_price] = temp_level
            
            # Calculate best prices for O(1) access
            best_bid_price, best_ask_price = self._calculate_best_prices(new_bids, new_asks)
            
            # Capture old values before updating snapshot to avoid memory leak
            old_best_bid = current.best_bid_price
            old_best_ask = current.best_ask_price
            
            # Atomic swap - create new immutable snapshot
            self._current_snapshot = PolymarketOrderbookSnapshot(
                asset_id=current.asset_id,
                market=current.market,
                bids=new_bids,
                asks=new_asks,
                last_update_time=timestamp,
                last_hash=current.last_hash,
                last_timestamp=current.last_timestamp,
                best_bid_price=best_bid_price,
                best_ask_price=best_ask_price
            )
            
            await self.bid_ask_helper(best_bid_price, best_ask_price, old_best_bid, old_best_ask)

            logger.debug(f"Applied tick size change for asset_id={current.asset_id}, old={old_tick_size}, new={new_tick_size}")


    async def bid_ask_helper(self, best_bid_price, best_ask_price, old_best_bid, old_best_ask):
        try:
            # Try explicit int conversion and comparison
            if best_bid_price is not None and old_best_bid is not None and \
                best_ask_price is not None and old_best_ask is not None:
                if float(best_bid_price) != float(old_best_bid) or float(best_ask_price) != float(old_best_ask):
                    payload = {
                        'asset_id': self._current_snapshot.asset_id,           # Polymarket asset ID
                        'market': self._current_snapshot.market,             # Market name/address (optional)
                        'price_changed': True,     # True if best bid/ask changed
                        'timestamp': datetime.now().isoformat()           # ISO timestamp of the update
                    }
                    await global_event_bus.publish("polymarket.bid_ask_updated", event_data=payload)
            else:
                logger.error("[ORDERBOOK_STATE] Best bid/ask comparison failed: Null value(s) in orderbook snapshot.")
        except ValueError as ve:
            logger.error(f"[ORDERBOOK_STATE] Best bid/ask comparison failed: ValueError during int conversion: {ve}")
        except TypeError as te:
            logger.error(f"[ORDERBOOK_STATE] Best bid/ask comparison failed: TypeError during comparison: {te}")
        except Exception as e:
            logger.error(f"[ORDERBOOK_STATE] Best bid/ask comparison failed: Unexpected error: {e}")

# Backward compatibility aliases
PolymarketOrderbookState = AtomicPolymarketOrderbookState