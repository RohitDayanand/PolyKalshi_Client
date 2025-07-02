"""
CandlestickManager - Manages candlestick state updates for Kalshi markets.

Receives orderbook updates from KalshiMessageProcessor and maintains 
minute-level OHLC candlestick data for each market.
"""

import logging
from typing import Dict, Optional, Callable
from datetime import datetime
import asyncio

from .models.candlestick_state import CandlestickState
from .models.orderbook_state import OrderbookState

logger = logging.getLogger(__name__)

class CandlestickManager:
    """
    Manages candlestick state for multiple markets.
    
    Receives orderbook updates via callback and maintains minute-level
    OHLC data. Emits completed candlesticks when minutes finish.
    """
    
    def __init__(self):
        # Maps (sid, minute_timestamp) -> CandlestickState
        self.candlesticks: Dict[tuple[int, int], CandlestickState] = {}
        
        # Callback for emitting completed candlesticks
        self.candlestick_emit_callback: Optional[Callable[[int, CandlestickState], None]] = None
        
        logger.info("CandlestickManager initialized")
    
    def set_candlestick_emit_callback(self, callback: Callable[[int, CandlestickState], None]) -> None:
        """Set callback for emitting completed candlesticks."""
        self.candlestick_emit_callback = callback
        logger.info("Candlestick emit callback set")
    
    async def handle_orderbook_update(self, sid: int, orderbook: OrderbookState) -> None:
        """
        Handle orderbook updates and update candlestick state.
        
        This is the callback function that gets called by KalshiMessageProcessor
        after each orderbook update.
        
        Args:
            sid: Market subscription ID
            orderbook: Updated orderbook state
        """
        try:
            current_time = datetime.now()
            minute_timestamp = CandlestickState.floor_timestamp_to_minute(current_time)
            
            # Create key for this market's current minute
            candle_key = (sid, minute_timestamp)
            
            # Check if we have an existing candlestick for this minute
            if candle_key in self.candlesticks:
                # Update existing candlestick
                candlestick = self.candlesticks[candle_key]
                candlestick.update(orderbook, current_time)
                
                logger.debug(f"🕯️ CANDLESTICK: Updated sid={sid}, minute={minute_timestamp}, "
                           f"updates={candlestick.update_count}")
            else:
                # Check if we need to emit previous minute's candlestick
                await self._check_and_emit_previous_candlesticks(sid, minute_timestamp)
                
                # Create new candlestick for this minute
                candlestick = CandlestickState()
                candlestick.create(orderbook, current_time)
                self.candlesticks[candle_key] = candlestick
                
                logger.info(f"🕯️ CANDLESTICK: Created new candlestick sid={sid}, minute={minute_timestamp}")
                
        except Exception as e:
            logger.error(f"Error handling candlestick update for sid={sid}: {e}")
    
    async def _check_and_emit_previous_candlesticks(self, sid: int, current_minute: int) -> None:
        """
        Check for and emit any completed candlesticks for this market.
        
        Args:
            sid: Market subscription ID  
            current_minute: Current minute timestamp
        """
        try:
            # Find all candlesticks for this market from previous minutes
            completed_candles = []
            
            for (candle_sid, minute_ts), candlestick in list(self.candlesticks.items()):
                if candle_sid == sid and minute_ts < current_minute:
                    completed_candles.append((candle_sid, minute_ts, candlestick))
            
            # Emit completed candlesticks
            for candle_sid, minute_ts, candlestick in completed_candles:
                await self._emit_candlestick(candle_sid, candlestick)
                
                # Remove from active candlesticks
                candle_key = (candle_sid, minute_ts)
                del self.candlesticks[candle_key]
                
                logger.info(f"🕯️ CANDLESTICK: Emitted completed candlestick sid={candle_sid}, "
                           f"minute={minute_ts}, updates={candlestick.update_count}")
                
        except Exception as e:
            logger.error(f"Error checking/emitting previous candlesticks for sid={sid}: {e}")
    
    async def _emit_candlestick(self, sid: int, candlestick: CandlestickState) -> None:
        """
        Emit a completed candlestick via callback.
        
        Args:
            sid: Market subscription ID
            candlestick: Completed candlestick to emit
        """
        if self.candlestick_emit_callback:
            try:
                if asyncio.iscoroutinefunction(self.candlestick_emit_callback):
                    await self.candlestick_emit_callback(sid, candlestick)
                else:
                    self.candlestick_emit_callback(sid, candlestick)
            except Exception as e:
                logger.error(f"Error in candlestick emit callback: {e}")
    
    def get_current_candlestick(self, sid: int) -> Optional[CandlestickState]:
        """
        Get the current (incomplete) candlestick for a market.
        
        Args:
            sid: Market subscription ID
            
        Returns:
            Current candlestick or None if no active candlestick
        """
        current_time = datetime.now()
        minute_timestamp = CandlestickState.floor_timestamp_to_minute(current_time)
        candle_key = (sid, minute_timestamp)
        
        return self.candlesticks.get(candle_key)
    
    def get_all_current_candlesticks(self) -> Dict[int, CandlestickState]:
        """
        Get all current candlesticks by market sid.
        
        Returns:
            Dict mapping sid -> current candlestick
        """
        current_time = datetime.now()
        minute_timestamp = CandlestickState.floor_timestamp_to_minute(current_time)
        
        result = {}
        for (sid, candle_minute), candlestick in self.candlesticks.items():
            if candle_minute == minute_timestamp:
                result[sid] = candlestick
                
        return result
    
    def cleanup(self) -> None:
        """Clean up resources."""
        self.candlesticks.clear()
        logger.info("CandlestickManager cleaned up")
    
    def get_stats(self) -> Dict[str, any]:
        """Get manager statistics."""
        active_candlesticks = len(self.candlesticks)
        unique_markets = len(set(sid for sid, _ in self.candlesticks.keys()))
        
        return {
            'active_candlesticks': active_candlesticks,
            'unique_markets': unique_markets,
            'candlestick_keys': list(self.candlesticks.keys())
        }