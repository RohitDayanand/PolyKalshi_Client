"""
CandlestickState - Tracks OHLC candlestick data for a specific minute timestamp.
"""

import logging
import asyncio
from typing import Dict, Any, Optional, TYPE_CHECKING
from datetime import datetime
from dataclasses import dataclass, field

if TYPE_CHECKING:
    from .orderbook_state import OrderbookState

logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class CandlestickSnapshot:
    """Immutable snapshot of candlestick state at a point in time."""
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

class AtomicCandlestickState:
    """Thread-safe candlestick state using atomic reference swaps with copy-on-write."""
    
    def __init__(self, timestamp_minute: int):
        """Initialize with empty candlestick state."""
        self._current_snapshot = CandlestickSnapshot(
            timestamp_minute=timestamp_minute
        )
        self._update_lock = asyncio.Lock()
    
    def get_snapshot(self) -> CandlestickSnapshot:
        """Get current immutable snapshot - lock-free read."""
        return self._current_snapshot
    
    async def get_snapshot_async(self) -> CandlestickSnapshot:
        """Async version for consistency with other async methods."""
        return self._current_snapshot
    
    async def create(self, orderbook: 'OrderbookState', current_time: datetime) -> None:
        """
        Initialize the candlestick with the first price data from orderbook.
        Sets all OHLC values to the current price (open = high = low = close).
        
        Args:
            orderbook: OrderbookState to get pricing from
            current_time: Current datetime for the update
        """
        async with self._update_lock:
            timestamp_minute = CandlestickSnapshot.floor_timestamp_to_minute(current_time)
            
            # Get current prices from orderbook
            prices = orderbook.calculate_yes_no_prices()
            
            # Initialize OHLC with current bid prices (all fields set to current price)
            yes_price = prices.get("yes", {}).get("bid", 0.0)
            no_price = prices.get("no", {}).get("bid", 0.0)
            volume = prices.get("yes", {}).get("volume", 0.0)
            
            # Atomic swap - create new immutable snapshot
            self._current_snapshot = CandlestickSnapshot(
                timestamp_minute=timestamp_minute,
                market_ticker=orderbook.market_ticker,
                yes_open=yes_price,
                yes_high=yes_price,
                yes_low=yes_price,
                yes_close=yes_price,
                no_open=no_price,
                no_high=no_price,
                no_low=no_price,
                no_close=no_price,
                volume=volume,
                first_update_time=current_time,
                last_update_time=current_time,
                update_count=1
            )
            
            logger.debug(f"🕯️ CANDLESTICK CREATE: minute={timestamp_minute}, "
                        f"yes_price={yes_price}, no_price={no_price}, volume={volume}")
    
    async def update(self, orderbook: 'OrderbookState', current_time: datetime) -> None:
        """
        Update the candlestick with new price data from orderbook.
        Only updates high/low/close values - open remains unchanged.
        
        Args:
            orderbook: OrderbookState to get pricing from
            current_time: Current datetime for the update
        """
        async with self._update_lock:
            current = self._current_snapshot
            
            # Verify this update belongs to the same minute
            update_minute = CandlestickSnapshot.floor_timestamp_to_minute(current_time)
            if update_minute != current.timestamp_minute:
                logger.warning(f"⚠️ CANDLESTICK UPDATE: Timestamp mismatch. "
                              f"Expected minute {current.timestamp_minute}, got {update_minute}")
                return
            
            # Get current prices from orderbook
            prices = orderbook.calculate_yes_no_prices()
            
            # Update YES side: only high/low/close (open stays the same)
            yes_price = prices.get("yes", {}).get("bid", 0.0)
            new_yes_high = max(current.yes_high, yes_price)
            new_yes_low = min(current.yes_low, yes_price)
            
            # Update NO side: only high/low/close (open stays the same)
            no_price = prices.get("no", {}).get("bid", 0.0)
            new_no_high = max(current.no_high, no_price)
            new_no_low = min(current.no_low, no_price)
            
            # Update volume (use current total volume)
            volume = prices.get("yes", {}).get("volume", 0.0)
            
            # Atomic swap - create new immutable snapshot
            self._current_snapshot = CandlestickSnapshot(
                timestamp_minute=current.timestamp_minute,
                market_ticker=current.market_ticker,
                yes_open=current.yes_open,  # Keep original open
                yes_high=new_yes_high,
                yes_low=new_yes_low,
                yes_close=yes_price,
                no_open=current.no_open,    # Keep original open
                no_high=new_no_high,
                no_low=new_no_low,
                no_close=no_price,
                volume=volume,
                first_update_time=current.first_update_time,
                last_update_time=current_time,
                update_count=current.update_count + 1
            )
            
            logger.debug(f"🕯️ CANDLESTICK UPDATE: minute={current.timestamp_minute}, "
                        f"yes_price={yes_price}, no_price={no_price}, "
                        f"update_count={current.update_count + 1}")
    
    # Properties for backward compatibility
    @property
    def timestamp_minute(self) -> int:
        """Get timestamp_minute from current snapshot."""
        return self._current_snapshot.timestamp_minute
    
    @property
    def market_ticker(self) -> Optional[str]:
        """Get market_ticker from current snapshot."""
        return self._current_snapshot.market_ticker
    
    @property
    def yes_open(self) -> float:
        """Get yes_open from current snapshot."""
        return self._current_snapshot.yes_open
    
    @property
    def yes_high(self) -> float:
        """Get yes_high from current snapshot."""
        return self._current_snapshot.yes_high
    
    @property
    def yes_low(self) -> float:
        """Get yes_low from current snapshot."""
        return self._current_snapshot.yes_low
    
    @property
    def yes_close(self) -> float:
        """Get yes_close from current snapshot."""
        return self._current_snapshot.yes_close
    
    @property
    def no_open(self) -> float:
        """Get no_open from current snapshot."""
        return self._current_snapshot.no_open
    
    @property
    def no_high(self) -> float:
        """Get no_high from current snapshot."""
        return self._current_snapshot.no_high
    
    @property
    def no_low(self) -> float:
        """Get no_low from current snapshot."""
        return self._current_snapshot.no_low
    
    @property
    def no_close(self) -> float:
        """Get no_close from current snapshot."""
        return self._current_snapshot.no_close
    
    @property
    def volume(self) -> float:
        """Get volume from current snapshot."""
        return self._current_snapshot.volume
    
    @property
    def first_update_time(self) -> Optional[datetime]:
        """Get first_update_time from current snapshot."""
        return self._current_snapshot.first_update_time
    
    @property
    def last_update_time(self) -> Optional[datetime]:
        """Get last_update_time from current snapshot."""
        return self._current_snapshot.last_update_time
    
    @property
    def update_count(self) -> int:
        """Get update_count from current snapshot."""
        return self._current_snapshot.update_count
    
    @staticmethod
    def floor_timestamp_to_minute(timestamp: datetime) -> int:
        """Floor a datetime timestamp to the minute (seconds = 0)."""
        return CandlestickSnapshot.floor_timestamp_to_minute(timestamp)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert candlestick to dictionary format for API responses."""
        return self._current_snapshot.to_dict()

# Backward compatibility alias
CandlestickState = AtomicCandlestickState