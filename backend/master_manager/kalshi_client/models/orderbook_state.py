"""
OrderbookState - Maintains the current state of an orderbook for a market.

Module Overview:
----------------
This module provides a thread-safe, atomic state model for a prediction market orderbook. It exposes:
  - `OrderbookSnapshot`: An immutable snapshot of the orderbook at a point in time.
  - `AtomicOrderbookState`: A state manager supporting atomic swaps and async/sync access.

Snapshot Shape (`OrderbookSnapshot`):
-------------------------------------
Each snapshot is a frozen dataclass with:
    sid: Optional[int]                # Market/session ID
    market_ticker: Optional[str]      # Market ticker symbol
    yes_contracts: Dict[int, OrderbookLevel]  # YES side price levels (price → OrderbookLevel)
    no_contracts: Dict[int, OrderbookLevel]   # NO side price levels (price → OrderbookLevel)
    last_seq: Optional[int]           # Last sequence number applied
    last_update_time: Optional[datetime] # Timestamp of last update
    best_yes_bid: Optional[int]       # Cached best YES bid price (cent integer)
    best_no_bid: Optional[int]        # Cached best NO bid price (cent integer)

Delta Format (for `apply_delta`):
---------------------------------
Delta messages are expected as dicts with the following shape:
    {
        "msg": {
            "side": "yes" | "no",      # Which side to update
            "price": int,               # Price level (cent integer)
            "delta": int                # Change in size (positive or negative)
        }
    }
    seq: int                          # Sequence number for ordering
    timestamp: datetime               # Timestamp of the update

Snapshot Format (for `apply_snapshot`):
---------------------------------------
Snapshot messages are expected as dicts with the following shape:
    {
        "msg": {
            "yes": [[price, size], ...],   # List of YES price levels
            "no": [[price, size], ...]     # List of NO price levels
        }
    }
    seq: int                          # Sequence number for ordering
    timestamp: datetime               # Timestamp of the update

Critical Helper Arguments:
-------------------------
- All price levels are cent integers (0-100).
- All sizes are integer quantities (can be converted to float via OrderbookLevel.size_float).
- `OrderbookLevel` is a helper class representing a single price level (see orderbook_level.py).
- All state updates are atomic: reads are lock-free, writes use asyncio.Lock for consistency.

Usage:
------
- Use `get_snapshot()` or `get_snapshot_async()` for lock-free reads.
- Use `apply_snapshot()` to replace the entire orderbook state.
- Use `apply_delta()` to incrementally update a single price level.
"""

import logging
import socket
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, field
from backend.master_manager.events.event_bus import global_event_bus

from .orderbook_level import OrderbookLevel

logger = logging.getLogger()

@dataclass(frozen=True)
class OrderbookSnapshot:
    """Immutable snapshot of orderbook state at a point in time."""
    sid: Optional[int] = None
    market_ticker: Optional[str] = None
    yes_contracts: Dict[int, OrderbookLevel] = field(default_factory=dict)
    no_contracts: Dict[int, OrderbookLevel] = field(default_factory=dict)
    last_seq: Optional[int] = None
    last_update_time: Optional[datetime] = None
    # Cached best prices for O(1) access
    best_yes_bid: Optional[int] = None
    best_no_bid: Optional[int] = None
    
    def get_yes_market_bid(self) -> Optional[int]:
        """Get the highest bid (best bid price) - O(1) using cached value."""
        return self.best_yes_bid
    
    def get_no_market_bid(self) -> Optional[int]:
        """Get the highest bid (best bid price) - O(1) using cached value."""
        return self.best_no_bid
    
    def get_total_bid_volume(self) -> float:
        """Calculate total volume on bid side."""
        return sum(level.size_float for level in self.yes_contracts.values())
    
    def get_total_ask_volume(self) -> float:
        """Calculate total volume on ask side."""
        return sum(level.size_float for level in self.no_contracts.values())
    
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
                "yes": {"bid": float, "ask": float, "volume": float, "candlestick": {open: float, high: float, low: flow, close: float}},
                "no": {"bid": float, "ask": float, "volume": float}
            }
        """
        # Represents market bid for buying yes contract (selling no contract)
        market_yes = self.get_yes_market_bid()

        # Represents market bid for buying no contract (selling yes contract)
        market_no = self.get_no_market_bid()
        
        # Debug logging for bid/ask calculation
        logger.debug(f"🧮 BID/ASK CALC: sid={self.sid}, ticker={self.market_ticker}")
        
        # Volume needs to be computed correctly
        bid_volume = self.get_total_bid_volume()
        ask_volume = self.get_total_ask_volume()
        total_volume = bid_volume + ask_volume
        
        logger.debug(f"  - Bid volume: {bid_volume}, Ask volume: {ask_volume}, Total: {total_volume}")
        
        # Convert cent prices to decimal probabilities (0.0-1.0 format)
        # This ensures compatibility with ticker publisher validation and downstream systems
        yes_bid_decimal = market_yes / 100.0 if market_yes is not None else None
        yes_ask_decimal = (100 - market_no) / 100.0 if market_no is not None else None
        no_bid_decimal = market_no / 100.0 if market_no is not None else None 
        no_ask_decimal = (100 - market_yes) / 100.0 if market_yes is not None else None
        
        yes_data = {
            "bid": yes_bid_decimal,
            "ask": yes_ask_decimal,
            "volume": total_volume
        }
        
        # Calculate NO prices as inverse of YES prices (in decimal format)
        no_data = {
            "bid": no_bid_decimal,
            "ask": no_ask_decimal, 
            "volume": total_volume
        }
        
        # Log the conversion for debugging
        logger.debug(f"  - Price conversion: YES {market_yes}¢→{yes_bid_decimal:.3f}, NO {market_no}¢→{no_bid_decimal:.3f}")
        logger.debug(f"  - Complement check: YES ask={yes_ask_decimal:.3f}, NO ask={no_ask_decimal:.3f}")
        
        # Economic validation (should sum to 1.0 in decimal format)
        if yes_bid_decimal is not None and no_ask_decimal is not None:
            complement_sum = yes_bid_decimal + no_ask_decimal
            logger.debug(f"  - Economic check: {yes_bid_decimal:.3f} + {no_ask_decimal:.3f} = {complement_sum:.3f}")
            if complement_sum > 1.01:  # Allow small floating point tolerance
                logger.warning(f"⚠️ ECONOMIC WARNING: YES bid + NO ask = {complement_sum:.3f} > 1.0 (potential arbitrage)")
        
        if yes_ask_decimal is not None and no_bid_decimal is not None:
            spread_sum = yes_ask_decimal + no_bid_decimal  
            logger.debug(f"  - Spread check: {yes_ask_decimal:.3f} + {no_bid_decimal:.3f} = {spread_sum:.3f}")
            if spread_sum < 0.99:  # Should be close to 1.0
                logger.warning(f"⚠️ SPREAD WARNING: YES ask + NO bid = {spread_sum:.3f} < 1.0 (unusual spread)")
        
        result = {
            "yes": yes_data,
            "no": no_data
        }
        
        logger.debug(f"  - Calculated result: {result}")
        
        return result

class AtomicOrderbookState:
    """Thread-safe orderbook state using atomic reference swaps with copy-on-write."""
    
    def __init__(self, sid: Optional[int] = None, market_ticker: Optional[str] = None):
        """Initialize with empty orderbook state."""
        self._current_snapshot = OrderbookSnapshot(
            sid=sid,
            market_ticker=market_ticker,
            yes_contracts={},
            no_contracts={},
            last_seq=None,
            last_update_time=None,
            best_yes_bid=None,
            best_no_bid=None
        )
        self._update_lock = asyncio.Lock()
    
    def get_snapshot(self) -> OrderbookSnapshot:
        """Get current immutable snapshot - lock-free read."""
        return self._current_snapshot
    
    async def get_snapshot_async(self) -> OrderbookSnapshot:
        """Async version for consistency with other async methods."""
        return self._current_snapshot
    
    @staticmethod
    def _calculate_best_prices(yes_contracts: Dict[int, OrderbookLevel], 
                              no_contracts: Dict[int, OrderbookLevel]) -> tuple[Optional[int], Optional[int]]:
        """
        Calculate best bid prices from contract dictionaries.
        
        Args:
            yes_contracts: Dictionary of YES contract price levels
            no_contracts: Dictionary of NO contract price levels
            
        Returns:
            Tuple of (best_yes_bid, best_no_bid)
        """
        best_yes_bid = max(yes_contracts.keys()) if yes_contracts else None
        best_no_bid = max(no_contracts.keys()) if no_contracts else None
        return best_yes_bid, best_no_bid
    
    @property
    def market_ticker(self) -> Optional[str]:
        """Get the market ticker from current snapshot."""
        return self._current_snapshot.market_ticker
    
    @property 
    def sid(self) -> Optional[int]:
        """Get the sid from current snapshot."""
        return self._current_snapshot.sid
    
    @property
    def last_seq(self) -> Optional[int]:
        """Get the last sequence number from current snapshot."""
        return self._current_snapshot.last_seq
    
    @property
    def last_update_time(self) -> Optional[datetime]:
        """Get the last update time from current snapshot."""
        return self._current_snapshot.last_update_time
    
    @property
    def yes_contracts(self) -> Dict[int, 'OrderbookLevel']:
        """Get the yes_contracts from current snapshot."""
        return self._current_snapshot.yes_contracts
    
    @property
    def no_contracts(self) -> Dict[int, 'OrderbookLevel']:
        """Get the no_contracts from current snapshot."""
        return self._current_snapshot.no_contracts
    
    def get_yes_market_bid(self) -> Optional[int]:
        """Get the highest bid (best bid price) - O(1) using cached value."""
        return self._current_snapshot.get_yes_market_bid()
    
    def get_no_market_bid(self) -> Optional[int]:
        """Get the highest bid (best bid price) - O(1) using cached value."""
        return self._current_snapshot.get_no_market_bid()
    
    def get_total_bid_volume(self) -> float:
        """Calculate total volume on bid side."""
        return self._current_snapshot.get_total_bid_volume()
    
    def get_total_ask_volume(self) -> float:
        """Calculate total volume on ask side."""
        return self._current_snapshot.get_total_ask_volume()
    
    def calculate_yes_no_prices(self) -> Dict[str, Dict[str, Optional[float]]]:
        """Calculate bid/ask prices for YES/NO sides - delegates to current snapshot."""
        return self._current_snapshot.calculate_yes_no_prices()
    
    async def apply_snapshot(self, snapshot_data: Dict[str, Any], seq: int, timestamp: datetime) -> None:
        """Apply a full orderbook snapshot, replacing current state."""
        async with self._update_lock:
            new_yes_contracts = {}
            new_no_contracts = {}
            
            # Process yes contracts
            for price_level in snapshot_data['msg'].get('yes', []):
                if len(price_level) < 2:
                    logger.warning("Empty price level in Kalshi orderbook snapshot")
                else:
                    price = int(price_level[0])
                    size = int(price_level[1])
                    new_yes_contracts[price] = OrderbookLevel(price=price, size=size, side="Yes")
            
            # Process no contracts
            for price_level in snapshot_data['msg'].get('no', []):
                if len(price_level) < 2:
                    logger.warning("Empty price level in Kalshi orderbook snapshot")
                else:
                    price = int(price_level[0])
                    size = int(price_level[1])
                    new_no_contracts[price] = OrderbookLevel(price=price, size=size, side="No")
            
            # Calculate best prices for O(1) access
            best_yes_bid, best_no_bid = self._calculate_best_prices(new_yes_contracts, new_no_contracts)
            
            # Capture old values before updating snapshot to avoid memory leak
            old_best_yes_bid = self._current_snapshot.best_yes_bid
            old_best_no_bid = self._current_snapshot.best_no_bid
            
            # Atomic swap - create new immutable snapshot
            self._current_snapshot = OrderbookSnapshot(
                sid=self._current_snapshot.sid,
                market_ticker=self._current_snapshot.market_ticker,
                yes_contracts=new_yes_contracts,
                no_contracts=new_no_contracts,
                last_seq=seq,
                last_update_time=timestamp,
                best_yes_bid=best_yes_bid,
                best_no_bid=best_no_bid
            )

            #determine whether to publish a bid_ask_updated event (for downstream consumers)
            #no return or callback soup - uses event bus coordination
            await self.bid_ask_change_helper(best_yes_bid, best_no_bid, old_best_yes_bid, old_best_no_bid)
            
            logger.debug(f"Applied snapshot for sid={self._current_snapshot.sid}, seq={seq}, bids={len(new_yes_contracts)}, asks={len(new_no_contracts)}")
    
    async def apply_delta(self, delta_data: Dict[str, Any], seq: int, timestamp: datetime) -> None:
        """Apply incremental orderbook changes."""
        async with self._update_lock:
            current = self._current_snapshot
            
            # Copy current state for modification
            new_yes_contracts = dict(current.yes_contracts)
            new_no_contracts = dict(current.no_contracts)
            
            # Process delta change
            if delta_data["msg"].get("side", "") == "yes":
                price_level = int(delta_data["msg"].get("price", 0))
                delta = int(delta_data["msg"].get("delta", 0))
                
                if price_level in new_yes_contracts:
                    new_size = new_yes_contracts[price_level].apply_delta(delta)
                    if new_size <= 0:
                        new_yes_contracts.pop(price_level, None)
                    else:
                        # Create new OrderbookLevel with updated size
                        new_yes_contracts[price_level] = OrderbookLevel(
                            price=price_level, 
                            size=new_size, 
                            side="Yes"
                        )
                else:
                    new_yes_contracts[price_level] = OrderbookLevel(
                        price=price_level, 
                        size=delta, 
                        side="Yes"
                    )
            else:
                price_level = int(delta_data["msg"].get("price", 0))
                delta = int(delta_data["msg"].get("delta", 0))

                if price_level in new_no_contracts:
                    new_size = new_no_contracts[price_level].apply_delta(delta)
                    if new_size <= 0:
                        new_no_contracts.pop(price_level, None)
                    else:
                        # Create new OrderbookLevel with updated size
                        new_no_contracts[price_level] = OrderbookLevel(
                            price=price_level, 
                            size=new_size, 
                            side="No"
                        )
                else:
                    new_no_contracts[price_level] = OrderbookLevel(
                        price=price_level, 
                        size=delta, 
                        side="No"
                    )
            
            # Incrementally update best prices
            new_best_yes_bid = current.best_yes_bid
            new_best_no_bid = current.best_no_bid

            #hasUpdate?
            hasBidAskUpdated = False
            
            # Check if we need to update best prices based on the delta
            if delta_data["msg"].get("side", "") == "yes":
                price_level = int(delta_data["msg"].get("price", 0))
                
                # If this price level was removed and it was the best bid, recalculate
                if price_level not in new_yes_contracts and price_level == current.best_yes_bid:
                    new_best_yes_bid = max(new_yes_contracts.keys()) if new_yes_contracts else None
                    hasBidAskUpdated = True
                # If this is a new/updated price level that's better than current best
                elif price_level in new_yes_contracts and (current.best_yes_bid is None or price_level > current.best_yes_bid):
                    new_best_yes_bid = price_level
                    hasBidAskUpdated = True
            else:
                price_level = int(delta_data["msg"].get("price", 0))
                
                # If this price level was removed and it was the best bid, recalculate
                if price_level not in new_no_contracts and price_level == current.best_no_bid:
                    new_best_no_bid = max(new_no_contracts.keys()) if new_no_contracts else None
                    hasBidAskUpdated = True
                # If this is a new/updated price level that's better than current best
                elif price_level in new_no_contracts and (current.best_no_bid is None or price_level > current.best_no_bid):
                    new_best_no_bid = price_level
                    hasBidAskUpdated = True
            
            # Atomic swap - create new immutable snapshot
            self._current_snapshot = OrderbookSnapshot(
                sid=current.sid,
                market_ticker=current.market_ticker,
                yes_contracts=new_yes_contracts,
                no_contracts=new_no_contracts,
                last_seq=seq,
                last_update_time=timestamp,
                best_yes_bid=new_best_yes_bid,
                best_no_bid=new_best_no_bid
            )

            if hasBidAskUpdated: 
                await self.bid_ask_change_helper(new_best_yes_bid, new_best_no_bid, current.best_yes_bid, current.best_no_bid) #use old values from current 
            #! Check scope - want to let Python GC efficiently remove snapshots when out of memory

            logger.debug(f"Applied delta for sid={current.sid}, seq={seq}, yes={len(new_yes_contracts)}, no={len(new_no_contracts)}")


    async def bid_ask_change_helper(self, new_best_yes_bid, new_best_no_bid, old_best_yes_bid, old_best_no_bid) -> None:
        # Publish event if best bid/ask changed
            try:
                if new_best_yes_bid is not None and old_best_yes_bid is not None and \
                   new_best_no_bid is not None and old_best_no_bid is not None:
                    # Check if values actually changed
                    if new_best_yes_bid != old_best_yes_bid or new_best_no_bid != old_best_no_bid:
                        payload = {
                                'sid': self._current_snapshot.sid,                # Kalshi market/session ID
                                'market_ticker': self._current_snapshot.market_ticker,      # Market ticker (optional, for logging)
                                'bid_ask_changed': True,   # True if best bid/ask changed
                                'timestamp': datetime.now().isoformat()           # ISO timestamp of the update
                        }
                        logger.log(logging.DEBUG, "Bid cask change helped")

                        await global_event_bus.publish("kalshi.bid_ask_updated", payload)
                else:
                    logger.error("[ORDERBOOK_STATE] Kalshi best bid/ask comparison failed: Null value(s) in orderbook snapshot.")
            except ValueError as ve:
                logger.error(f"[ORDERBOOK_STATE] Kalshi best bid/ask comparison failed: ValueError during int conversion: {ve}")
            except TypeError as te:
                logger.error(f"[ORDERBOOK_STATE] Kalshi best bid/ask comparison failed: TypeError during comparison: {te}")
            except Exception as e:
                logger.error(f"[ORDERBOOK_STATE] Kalshi best bid/ask comparison failed: Unexpected error: {e}")

# Backward compatibility alias
OrderbookState = AtomicOrderbookState