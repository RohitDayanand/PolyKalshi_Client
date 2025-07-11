"""
KalshiMessageProcessor - Processes raw JSON messages from KalshiQueue to maintain orderbook state.

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
from typing import Dict, Any, Optional, Callable
from datetime import datetime

from .models.orderbook_state import OrderbookState

logger = logging.getLogger(__name__)

class KalshiMessageProcessor:
    """
    Processes raw Kalshi WebSocket messages to maintain orderbook state.
    
    Designed to work as the message_handler for KalshiQueue.
    Maintains separate orderbook state per market using sid.
    """
    
    def __init__(self, start_logging: bool = False):
        self.orderbooks: Dict[int, OrderbookState] = {}  # sid -> OrderbookState
        self.error_callback: Optional[Callable[[Dict[str, Any]], None]] = None
        self.orderbook_update_callback: Optional[Callable[[int, OrderbookState], None]] = None
        
        # Start periodic logging task only if requested and event loop is running
        self.logging_task: Optional[asyncio.Task] = None
        if start_logging:
            try:
                self.start_periodic_logging()
            except RuntimeError:
                # No event loop running, skip periodic logging
                logger.debug("No event loop running, skipping periodic logging")
        
        logger.info("KalshiMessageProcessor initialized")
    
    def set_error_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Set callback for error message handling."""
        self.error_callback = callback
        logger.info("Kalshi error callback set")
    
    def set_orderbook_update_callback(self, callback: Callable[[int, OrderbookState], None]) -> None:
        """Set callback for orderbook update notifications."""
        self.orderbook_update_callback = callback
        logger.info("Kalshi orderbook update callback set")
    
    def start_periodic_logging(self):
        """Start background task for periodic orderbook state logging."""
        if self.logging_task is None or self.logging_task.done():
            self.logging_task = asyncio.create_task(self._periodic_logging_loop())
            logger.info("Started periodic orderbook logging (every 10 seconds)")
    
    def stop_periodic_logging(self):
        """Stop the periodic logging task."""
        if self.logging_task and not self.logging_task.done():
            self.logging_task.cancel()
            logger.info("Stopped periodic orderbook logging")
    
    async def _periodic_logging_loop(self):
        """Background loop that logs orderbook state every 10 seconds."""
        while True:
            try:
                await asyncio.sleep(10)  # Log every 10 seconds
                await self._log_orderbook_state()
            except asyncio.CancelledError:
                logger.info("Periodic logging loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in periodic logging loop: {e}")
    
    async def _log_orderbook_state(self):
        """Log current orderbook state for debugging bid/ask calculations."""
        try:
            if not self.orderbooks:
                logger.info("🔍 ORDERBOOK DEBUG: No active Kalshi markets")
                return
            
            logger.info(f"🔍 ORDERBOOK DEBUG: {len(self.orderbooks)} active Kalshi markets")
            
            for sid, orderbook in self.orderbooks.items():
                # Log basic orderbook info
                bid_count = len(orderbook.yes_contracts)
                ask_count = len(orderbook.no_contracts)
                best_bid = orderbook.get_yes_market_bid()
                best_ask = orderbook.get_no_market_bid()
                
                logger.info(f"🔍 ORDERBOOK DEBUG: sid={sid}, ticker={orderbook.market_ticker}")
                logger.info(f"  - Bids: {bid_count} levels, Best bid: {best_bid}")
                logger.info(f"  - Asks: {ask_count} levels, Best ask: {best_ask}")
                logger.info(f"  - Last seq: {orderbook.last_seq}, Last update: {orderbook.last_update_time}")
                
                # Log bid/ask calculation results
                summary_stats = orderbook.calculate_yes_no_prices()
                logger.info(f"  - Summary stats: {summary_stats}")
                
                # Log top 3 bid/ask levels for detailed debugging
                if orderbook.yes_contracts:
                    sorted_bids = sorted(orderbook.yes_contracts.items(), key=lambda x: float(x[0]), reverse=True)[:3]
                    logger.info(f"  - Top 3 bids: {[(price, level.size) for price, level in sorted_bids]}")
                
                if orderbook.no_contracts:
                    sorted_asks = sorted(orderbook.no_contracts.items(), key=lambda x: float(x[0]))[:3]
                    logger.info(f"  - Top 3 asks: {[(price, level.size) for price, level in sorted_asks]}")
        
        except Exception as e:
            logger.error(f"Error logging orderbook state: {e}")
    
    def cleanup(self):
        """Clean up resources, stop background tasks."""
        self.stop_periodic_logging()
        logger.info("KalshiMessageProcessor cleaned up")

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
                logger.error(f"❌ KALSHI MSG: Failed to decode JSON: {e}")
                return
            
            # Extract message type
            message_type = message_data.get('type')
            if not message_type:
                logger.warning(f"⚠️ KALSHI MSG: No message type found")
                return
            
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
                logger.info(f"❓ KALSHI MSG: Unknown message type: {message_type}")
                
        except Exception as e:
            logger.error(f"💥 KALSHI MSG: Error processing message: {e}")
    
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