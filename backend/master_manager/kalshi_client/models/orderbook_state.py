"""
OrderbookState - Maintains the current state of an orderbook for a market.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, field

from .orderbook_level import OrderbookLevel

logger = logging.getLogger(__name__)

@dataclass 
class OrderbookState:
    """Maintains the current state of an orderbook for a market."""
    sid: Optional[int] = None
    market_ticker: Optional[str] = None
    yes_contracts: Dict[int, OrderbookLevel] = field(default_factory=dict)
    no_contracts: Dict[int, OrderbookLevel] = field(default_factory=dict)
    last_seq: Optional[int] = None
    last_update_time: Optional[datetime] = None
    
    def apply_snapshot(self, snapshot_data: Dict[str, Any], seq: int, timestamp: datetime) -> None:
        """Apply a full orderbook snapshot, replacing current state."""
        self.yes_contracts.clear()
        self.no_contracts.clear()
        
        # Process yes - Orderbooks in kalshi/polymarket work different
        for price_level in snapshot_data['msg'].get('yes', []):
            if len(price_level) < 2:
                print("We are processing the wrong order shape - there is some empty price level and kalshi has not updated it. Line 88 in kalshi message processor")
            else:
                price = int(price_level[0])
                size = int(price_level[1])
                self.yes_contracts[price] = OrderbookLevel(price=price, size=size, side="Yes")
        
        # Process Nos
        for price_level in snapshot_data['msg'].get('no', []):
                if len(price_level) < 2:
                    print("Erorr occured here")
                else:
                    price = int(price_level[0])
                    size = int(price_level[1])
                    self.no_contracts[price] = OrderbookLevel(price=price, size=size, side="No")
            
        self.last_seq = seq
        self.last_update_time = timestamp
        logger.debug(f"Applied snapshot for sid={self.sid}, seq={seq}, bids={len(self.yes_contracts)}, asks={len(self.no_contracts)}")
    
    def apply_delta(self, delta_data: Dict[str, Any], seq: int, timestamp: datetime) -> None:
        """Apply incremental orderbook changes."""
        # Process change and decide which side it is, and check if it's a new orderbook level
        if delta_data["msg"].get("side", "") == "yes":
            price_level = int(delta_data["msg"].get("price", 0))
            delta = int(delta_data["msg"].get("delta", 0))
            if price_level in self.yes_contracts:
                new_size = self.yes_contracts[price_level].apply_delta(delta)
                self.yes_contracts.pop(price_level, "") if new_size <= 0 else None
            else:
                self.yes_contracts[price_level] = OrderbookLevel(price = price_level, size = delta, side = "Yes")
        else:
            price_level = int(delta_data["msg"].get("price", 0))
            delta = int(delta_data["msg"].get("delta", 0))

            if price_level in self.no_contracts:
                new_size = self.no_contracts[price_level].apply_delta(delta)
                self.no_contracts.pop(price_level, "") if new_size <= 0 else None
            else:
                self.no_contracts[price_level] = OrderbookLevel(price = price_level, size = delta, side = "No")
                
        self.last_seq = seq
        self.last_update_time = timestamp
        logger.debug(f"Applied delta for sid={self.sid}, seq={seq}, yes={len(self.yes_contracts)}, no={len(self.no_contracts)}")
    
    def get_yes_market_bid(self) -> int:
        """Get the highest bid (best bid price)."""
        if not self.yes_contracts or len(self.yes_contracts) <= 0:
            return None
         
        # This is an O(n) operation - price levels are limited (~50) so it's mostly constant, but need to consider other approaches
        # We assume that if any orderbook level delta goes below 0, we remove that orderbook level otherwise this max calculation 
        # will NOT work
        return max(self.yes_contracts.keys(), key=lambda x: int(x))
    
    def get_no_market_bid(self) -> int:
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