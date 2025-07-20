"""
OrderbookState - Maintains the current state of an orderbook for a market.
"""

import logging
import socket
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, field

from .orderbook_level import OrderbookLevel

logger = logging.getLogger(__name__)

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
        """Get the highest bid (best bid price)."""
        if not self.yes_contracts or len(self.yes_contracts) <= 0:
            return None
         
        # This is an O(n) operation - price levels are limited (~50) so it's mostly constant, but need to consider other approaches
        # We assume that if any orderbook level delta goes below 0, we remove that orderbook level otherwise this max calculation 
        # will NOT work
        return max(self.yes_contracts.keys(), key=lambda x: int(x))
    
    def get_no_market_bid(self) -> Optional[int]:
        """Get the highest bid (best bid price)."""
        if not self.no_contracts or len(self.no_contracts) <= 0:
            # That means there is no market here - it's already resolved
            return None
        
        # This is an O(n) operation - price levels are limited (~50) so it's mostly constant, but need to consider other approaches
        # We assume that if any orderbook level delta goes below 0, we remove that orderbook level otherwise this max calculation 
        # will NOT work
        return max(self.no_contracts.keys(), key=lambda x: int(x))
    
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
            last_update_time=None
        )
        self._update_lock = asyncio.Lock()
    
    def get_snapshot(self) -> OrderbookSnapshot:
        """Get current immutable snapshot - lock-free read."""
        return self._current_snapshot
    
    async def get_snapshot_async(self) -> OrderbookSnapshot:
        """Async version for consistency with other async methods."""
        return self._current_snapshot
    
    @property
    def market_ticker(self) -> Optional[str]:
        """Get the market ticker from current snapshot."""
        return self._current_snapshot.market_ticker
    
    @property 
    def sid(self) -> Optional[int]:
        """Get the sid from current snapshot."""
        return self._current_snapshot.sid
    
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
            
            # Atomic swap - create new immutable snapshot
            self._current_snapshot = OrderbookSnapshot(
                sid=self._current_snapshot.sid,
                market_ticker=self._current_snapshot.market_ticker,
                yes_contracts=new_yes_contracts,
                no_contracts=new_no_contracts,
                last_seq=seq,
                last_update_time=timestamp
            )
            
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
            
            # Atomic swap - create new immutable snapshot
            self._current_snapshot = OrderbookSnapshot(
                sid=current.sid,
                market_ticker=current.market_ticker,
                yes_contracts=new_yes_contracts,
                no_contracts=new_no_contracts,
                last_seq=seq,
                last_update_time=timestamp
            )
            
            logger.debug(f"Applied delta for sid={current.sid}, seq={seq}, yes={len(new_yes_contracts)}, no={len(new_no_contracts)}")

# Backward compatibility alias
OrderbookState = AtomicOrderbookState