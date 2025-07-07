"""
CandlestickState - Tracks OHLC candlestick data for a specific minute timestamp.
"""

import logging
from typing import Dict, Any, Optional, TYPE_CHECKING
from datetime import datetime
from dataclasses import dataclass

if TYPE_CHECKING:
    from .orderbook_state import OrderbookState

logger = logging.getLogger(__name__)

@dataclass
class CandlestickState:
    """
    Tracks OHLC candlestick data for a specific minute timestamp.
    
    Uses the orderbook's calculate_yes_no_prices method to get current pricing,
    and maintains open/high/low/close values for both YES and NO sides.
    Always maintains complete OHLC data.
    """
    timestamp_minute: int  # Unix timestamp floored to the minute
    market_ticker: Optional[str] = None
    
    # YES side OHLC (bid prices) - always complete
    yes_open: float = 0.0
    yes_high: float = 0.0  
    yes_low: float = 0.0
    yes_close: float = 0.0
    
    # NO side OHLC (bid prices) - always complete
    no_open: float = 0.0
    no_high: float = 0.0
    no_low: float = 0.0
    no_close: float = 0.0
    
    # Volume tracking
    volume: float = 0.0
    
    # Tracking metadata
    first_update_time: Optional[datetime] = None
    last_update_time: Optional[datetime] = None
    update_count: int = 0
    
    @staticmethod
    def floor_timestamp_to_minute(timestamp: datetime) -> int:
        """Floor a datetime timestamp to the minute (seconds = 0)."""
        floored = timestamp.replace(second=0, microsecond=0)
        return int(floored.timestamp())
    
    def create(self, orderbook: 'OrderbookState', current_time: datetime) -> None:
        """
        Initialize the candlestick with the first price data from orderbook.
        Sets all OHLC values to the current price (open = high = low = close).
        
        Args:
            orderbook: OrderbookState to get pricing from
            current_time: Current datetime for the update
        """
        self.timestamp_minute = self.floor_timestamp_to_minute(current_time)
        self.market_ticker = orderbook.market_ticker
        self.first_update_time = current_time
        self.last_update_time = current_time
        
        # Get current prices from orderbook
        prices = orderbook.calculate_yes_no_prices()
        
        # Initialize OHLC with current bid prices (all fields set to current price)
        yes_price = prices.get("yes", {}).get("bid", 0.0)
        no_price = prices.get("no", {}).get("bid", 0.0)
        
        # Set all OHLC values to current price
        self.yes_open = yes_price
        self.yes_high = yes_price
        self.yes_low = yes_price
        self.yes_close = yes_price
        
        self.no_open = no_price
        self.no_high = no_price
        self.no_low = no_price
        self.no_close = no_price
        
        # Initialize volume
        self.volume = prices.get("yes", {}).get("volume", 0.0)
        self.update_count = 1
        
        logger.debug(f"🕯️ CANDLESTICK CREATE: minute={self.timestamp_minute}, "
                    f"yes_price={yes_price}, no_price={no_price}, volume={self.volume}")
    
    def update(self, orderbook: 'OrderbookState', current_time: datetime) -> None:
        """
        Update the candlestick with new price data from orderbook.
        Only updates high/low/close values - open remains unchanged.
        
        Args:
            orderbook: OrderbookState to get pricing from
            current_time: Current datetime for the update
        """
        # Verify this update belongs to the same minute
        update_minute = self.floor_timestamp_to_minute(current_time)
        if update_minute != self.timestamp_minute:
            logger.warning(f"⚠️ CANDLESTICK UPDATE: Timestamp mismatch. "
                          f"Expected minute {self.timestamp_minute}, got {update_minute}")
            return
        
        self.last_update_time = current_time
        self.update_count += 1
        
        # Get current prices from orderbook
        prices = orderbook.calculate_yes_no_prices()
        
        # Update YES side: only high/low/close (open stays the same)
        yes_price = prices.get("yes", {}).get("bid", 0.0)
        if yes_price > self.yes_high:
            self.yes_high = yes_price
        if yes_price < self.yes_low:
            self.yes_low = yes_price
        self.yes_close = yes_price
        
        # Update NO side: only high/low/close (open stays the same)
        no_price = prices.get("no", {}).get("bid", 0.0)
        if no_price > self.no_high:
            self.no_high = no_price
        if no_price < self.no_low:
            self.no_low = no_price
        self.no_close = no_price
        
        # Update volume (use current total volume)
        self.volume = prices.get("yes", {}).get("volume", 0.0)
        
        logger.debug(f"🕯️ CANDLESTICK UPDATE: minute={self.timestamp_minute}, "
                    f"yes_price={yes_price}, no_price={no_price}, "
                    f"update_count={self.update_count}")
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert candlestick to dictionary format for API responses.
        
        Returns:
            Dict with candlestick data in API format
        """
        return {
            "time": self.timestamp_minute,
            "market_ticker": self.market_ticker,
            "yes_open": self.yes_open,
            "yes_high": self.yes_high,
            "yes_low": self.yes_low,
            "yes_close": self.yes_close,
            "no_open": self.no_open,
            "no_high": self.no_high,
            "no_low": self.no_low,
            "no_close": self.no_close,
            "volume": self.volume,
            "update_count": self.update_count,
            "first_update_time": self.first_update_time.isoformat() if self.first_update_time else None,
            "last_update_time": self.last_update_time.isoformat() if self.last_update_time else None
        }