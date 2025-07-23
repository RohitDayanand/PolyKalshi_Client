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
from .models.ticker_state import TickerState
from ..events.event_bus import EventBus, global_event_bus

logger = logging.getLogger(__name__)

# Add custom logging level for orderbook snapshots
ORDERBOOK_SNAPSHOT_LEVEL = 25
logging.addLevelName(ORDERBOOK_SNAPSHOT_LEVEL, "ORDERBOOK_SNAPSHOT")

def orderbook_snapshot_log(message):
    """Log orderbook snapshot updates at custom level for easy filtering."""
    logger.log(ORDERBOOK_SNAPSHOT_LEVEL, message)

class KalshiMessageProcessor:
    """
    Processes raw Kalshi WebSocket messages to maintain orderbook state.
    
    Designed to work as the message_handler for KalshiQueue.
    Maintains separate orderbook state per market using ticker.
    """
    
    def __init__(self, start_logging: bool = False, event_bus: Optional[EventBus] = None):
        self.orderbooks: Dict[str, OrderbookState] = {}  # ticker -> OrderbookState
        self.ticker_states: Dict[str, TickerState] = {}  # ticker -> TickerState
        self.error_callback: Optional[Callable[[Dict[str, Any]], None]] = None
        self.orderbook_update_callback: Optional[Callable[[str, OrderbookState], None]] = None
        self.ticker_update_callback: Optional[Callable[[str, TickerState], None]] = None
        
        # EventBus integration for publishing events
        self.event_bus = event_bus or global_event_bus
        
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
    
    def set_orderbook_update_callback(self, callback: Callable[[str, OrderbookState], None]) -> None:
        """Set callback for orderbook update notifications."""
        self.orderbook_update_callback = callback
        logger.info("Kalshi orderbook update callback set")
    
    def set_ticker_update_callback(self, callback: Callable[[str, TickerState], None]) -> None:
        """Set callback for ticker update notifications."""
        self.ticker_update_callback = callback
        logger.info("Kalshi ticker update callback set")
    
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
        """Log current orderbook and ticker state for debugging bid/ask calculations."""
        try:
            total_markets = len(set(self.orderbooks.keys()) | set(self.ticker_states.keys()))
            
            if total_markets == 0:
                logger.info("🔍 KALSHI DEBUG: No active Kalshi markets")
                return
            
            logger.info(f"🔍 KALSHI DEBUG: {len(self.orderbooks)} orderbook markets, "
                       f"{len(self.ticker_states)} ticker markets, {total_markets} total")
            
            # Log orderbook markets
            for ticker, orderbook in self.orderbooks.items():
                # Get current snapshot for consistent read
                snapshot = orderbook.get_snapshot()
                
                # Log basic orderbook info
                bid_count = len(snapshot.yes_contracts)
                ask_count = len(snapshot.no_contracts)
                best_bid = snapshot.get_yes_market_bid()
                best_ask = snapshot.get_no_market_bid()
                
                logger.info(f"🔍 ORDERBOOK DEBUG: sid={ticker}, ticker={snapshot.market_ticker}")
                logger.info(f"  - Bids: {bid_count} levels, Best bid: {best_bid}")
                logger.info(f"  - Asks: {ask_count} levels, Best ask: {best_ask}")
                logger.info(f"  - Last seq: {snapshot.last_seq}, Last update: {snapshot.last_update_time}")
                
                # Log bid/ask calculation results
                summary_stats = snapshot.calculate_yes_no_prices()
                logger.info(f"  - Summary stats: {summary_stats}")
                
                # Log top 3 bid/ask levels for detailed debugging
                if snapshot.yes_contracts:
                    sorted_bids = sorted(snapshot.yes_contracts.items(), key=lambda x: float(x[0]), reverse=True)[:3]
                    logger.info(f"  - Top 3 bids: {[(price, level.size) for price, level in sorted_bids]}")
                
                if snapshot.no_contracts:
                    sorted_asks = sorted(snapshot.no_contracts.items(), key=lambda x: float(x[0]))[:3]
                    logger.info(f"  - Top 3 asks: {[(price, level.size) for price, level in sorted_asks]}")
            
            # Log ticker markets (only those without orderbook data)
            ticker_only_markets = set(self.ticker_states.keys()) - set(self.orderbooks.keys())
            for ticker in ticker_only_markets:
                ticker_state = self.ticker_states[ticker]
                
                logger.info(f"🔍 TICKER DEBUG: ticker={ticker}, sid={ticker_state.sid}")
                logger.info(f"  - Price: {ticker_state.price} ({ticker_state.price_float})")
                logger.info(f"  - Yes bid/ask: {ticker_state.yes_bid}/{ticker_state.yes_ask} "
                           f"({ticker_state.yes_bid_float}/{ticker_state.yes_ask_float})")
                logger.info(f"  - Volume: {ticker_state.volume}, Open interest: {ticker_state.open_interest}")
                logger.info(f"  - Updates: {ticker_state.update_count}, Last: {ticker_state.last_update_time}")
                
                # Log ticker summary stats
                ticker_summary = ticker_state.get_summary_stats()
                logger.info(f"  - Ticker summary: {ticker_summary}")
        
        except Exception as e:
            logger.error(f"Error logging market state: {e}")
    
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
            logger.info(f"🔍 KALSHI MESSAGE RECEIVED: {raw_message[:200]}{'...' if len(raw_message) > 200 else ''}")
            logger.info(f"🔍 KALSHI METADATA: {metadata}")
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
            elif message_type == 'ticker_v2':
                await self._handle_ticker_update(message_data, metadata)
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
        ticker = metadata.get('ticker')
        logger.info(f"Kalshi subscription successful - sid: {sid}, ticker: {ticker}")
        
        # Initialize orderbook state for this market if we have ticker
        if ticker is not None:
            if ticker not in self.orderbooks:
                self.orderbooks[ticker] = OrderbookState(
                    sid=sid, 
                    market_ticker=ticker
                )
                logger.info(f"Initialized orderbook state for market ticker={ticker}, sid={sid}")
    
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
        ticker = metadata.get('ticker')
        if ticker not in self.orderbooks:
            self.orderbooks[ticker] = OrderbookState(
                sid=sid,
                market_ticker=ticker
            )
            logger.info(f"Created new orderbook state for ticker={ticker}")
        
        orderbook = self.orderbooks[ticker]
        current_time = datetime.now()
        
        # Check if this snapshot is newer than our last update
        current_snapshot = orderbook.get_snapshot()
        if current_snapshot.last_seq is not None and seq <= current_snapshot.last_seq:
            logger.warning(f"Received old snapshot for sid={sid}: seq={seq} <= last_seq={current_snapshot.last_seq}")
            return
        
        # Apply the snapshot
        try:
            await orderbook.apply_snapshot(message_data, seq, current_time)
            
            # Notify callback if set
            if self.orderbook_update_callback:
                try:
                    if asyncio.iscoroutinefunction(self.orderbook_update_callback):
                        await self.orderbook_update_callback(ticker, orderbook)
                    else:
                        self.orderbook_update_callback(ticker, orderbook)
                except Exception as e:
                    logger.error(f"Error in orderbook update callback: {e}")
                    
        except Exception as e:
            logger.error(f"Error applying orderbook_snapshot for sid={sid}: {e}")
    
    async def _handle_orderbook_delta(self, message_data: Dict[str, Any], metadata: Dict[str, Any]) -> None:
        """Handle incremental orderbook updates."""
        sid = message_data.get('sid')
        seq = message_data.get('seq')
        ticker = metadata.get('ticker')
        
        if sid is None:
            logger.warning("No sid in orderbook_delta message")
            return
            
        if ticker is None:
            logger.warning(f"No ticker in orderbook_delta metadata for sid={sid}")
            return
            
        if seq is None:
            logger.warning(f"No seq in orderbook_delta message for ticker={ticker}")
            return
        
        # Ensure we have orderbook state for this market
        if ticker not in self.orderbooks:
            logger.warning(f"No orderbook state for ticker={ticker}, cannot apply delta. Need snapshot first.")
            return
        
        orderbook = self.orderbooks[ticker]
        
        # Check sequence ordering
        current_snapshot = orderbook.get_snapshot()
        if current_snapshot.last_seq is not None:
            expected_seq = current_snapshot.last_seq + 1
            if seq != expected_seq:
                logger.error(f"Missing sequence for sid={sid}: expected {expected_seq}, got {seq}. "
                           f"Gap in orderbook updates detected!")
                # Could request snapshot here or implement gap handling
                return
        
        # Apply the delta
        try:
            current_time = datetime.now()
            await orderbook.apply_delta(message_data, seq, current_time)
            
            
            # Notify callback if set
            if self.orderbook_update_callback:
                try:
                    if asyncio.iscoroutinefunction(self.orderbook_update_callback):
                        await self.orderbook_update_callback(ticker, orderbook)
                    else:
                        self.orderbook_update_callback(ticker, orderbook)
                except Exception as e:
                    logger.error(f"Error in orderbook update callback: {e}")
                    
        except Exception as e:
            logger.error(f"Error applying orderbook_delta for sid={sid}: {e}")
    
    async def _handle_ticker_update(self, message_data: Dict[str, Any], metadata: Dict[str, Any]) -> None:
        """Handle ticker_v2 updates."""
        sid = message_data.get('sid')
        msg = message_data.get('msg', {})
        market_ticker = msg.get('market_ticker')
        
        if sid is None:
            logger.warning("No sid in ticker_v2 message")
            return
            
        if not market_ticker:
            logger.warning(f"No market_ticker in ticker_v2 message for sid={sid}")
            return
        
        # Ensure we have ticker state for this market
        if market_ticker not in self.ticker_states:
            # Create ticker state with async API initialization to get current market data
            try:
                self.ticker_states[market_ticker] = await TickerState.create_with_api_init(
                    sid=sid,
                    market_ticker=market_ticker
                )
                logger.info(f"Created new ticker state with API init for ticker={market_ticker}, sid={sid}")
            except Exception as e:
                # Fallback to creation without API if initialization fails
                logger.warning(f"API initialization failed for {market_ticker}, using defaults: {e}")
                self.ticker_states[market_ticker] = TickerState.create_without_api_init(
                    sid=sid,
                    market_ticker=market_ticker
                )
                logger.info(f"Created new ticker state without API init for ticker={market_ticker}, sid={sid}")
        
        ticker_state = self.ticker_states[market_ticker]
        
        # Apply the ticker update and check for bid/ask changes
        try:
            # Store previous bid/ask for change detection
            prev_yes_bid = ticker_state.yes_bid_float
            prev_yes_ask = ticker_state.yes_ask_float
            prev_no_bid = 1.0 - ticker_state.yes_ask_float if ticker_state.yes_ask_float is not None else None
            prev_no_ask = 1.0 - ticker_state.yes_bid_float if ticker_state.yes_bid_float is not None else None
            
            ticker_state.apply_ticker_update(message_data)
            logger.debug(f"Applied ticker_v2 update for sid={sid}, ticker={market_ticker}")
            
            # Check if bid/ask prices have changed
            curr_yes_bid = ticker_state.yes_bid_float
            curr_yes_ask = ticker_state.yes_ask_float
            curr_no_bid = 1.0 - ticker_state.yes_ask_float if ticker_state.yes_ask_float is not None else None
            curr_no_ask = 1.0 - ticker_state.yes_bid_float if ticker_state.yes_bid_float is not None else None
            
            bid_ask_changed = (
                prev_yes_bid != curr_yes_bid or
                prev_yes_ask != curr_yes_ask or
                prev_no_bid != curr_no_bid or
                prev_no_ask != curr_no_ask
            )
            
            # Publish ticker update event via EventBus
            try:
                await self.event_bus.publish('kalshi.ticker_update', {
                    'sid': sid,
                    'ticker_state': ticker_state,
                    'market_ticker': market_ticker,
                    'bid_ask_changed': bid_ask_changed,
                    'timestamp': datetime.now().isoformat()
                })
                logger.debug(f"Published kalshi.ticker_update event for sid={sid}, bid_ask_changed={bid_ask_changed}")
            except Exception as e:
                logger.error(f"Error publishing ticker update event: {e}")
            
            # Notify callback if set (legacy support)
            if self.ticker_update_callback:
                try:
                    if asyncio.iscoroutinefunction(self.ticker_update_callback):
                        await self.ticker_update_callback(market_ticker, ticker_state)
                    else:
                        self.ticker_update_callback(market_ticker, ticker_state)
                except Exception as e:
                    logger.error(f"Error in ticker update callback: {e}")
                    
        except Exception as e:
            logger.error(f"Error applying ticker_v2 update for sid={sid}: {e}")
    
    def get_orderbook(self, ticker: str) -> Optional[OrderbookState]:
        """Get current orderbook state for a market."""
        return self.orderbooks.get(ticker)
    
    def get_all_orderbooks(self) -> Dict[str, OrderbookState]:
        """Get all current orderbook states."""
        return self.orderbooks.copy()
    
    def get_ticker_state(self, ticker: str) -> Optional[TickerState]:
        """Get current ticker state for a market."""
        return self.ticker_states.get(ticker)
    
    def get_all_ticker_states(self) -> Dict[str, TickerState]:
        """Get all current ticker states."""
        return self.ticker_states.copy()
    
    def get_summary_stats(self, ticker: str) -> Optional[Dict[str, Dict[str, Optional[float]]]]:
        """
        Get yes/no bid/ask/volume summary stats for a specific market.
        
        Args:
            ticker: Market ticker
            
        Returns:
            Dict in format expected by ticker stream integration:
            {
                "yes": {"bid": float, "ask": float, "volume": float},
                "no": {"bid": float, "ask": float, "volume": float}
            }
            Returns None if ticker not found or no orderbook data.
        """
        orderbook = self.get_orderbook(ticker)
        if not orderbook:
            return None
        
        return orderbook.get_snapshot().calculate_yes_no_prices()
    
    def get_all_summary_stats(self) -> Dict[str, Dict[str, Dict[str, Optional[float]]]]:
        """
        Get summary stats for all active markets (prioritizes orderbook data over ticker data).
        
        Returns:
            Dict mapping ticker -> summary_stats for all markets
        """
        result = {}
        
        # First, use orderbook data (more detailed)
        for ticker, orderbook in self.orderbooks.items():
            summary_stats = orderbook.get_snapshot().calculate_yes_no_prices()
            result[ticker] = summary_stats
        
        # Then, add ticker data for markets that don't have orderbook data
        for ticker, ticker_state in self.ticker_states.items():
            if ticker not in result:
                summary_stats = ticker_state.get_summary_stats()
                result[ticker] = summary_stats
        
        return result
    
    def get_ticker_summary_stats(self, ticker: str) -> Optional[Dict[str, Dict[str, Optional[float]]]]:
        """
        Get yes/no bid/ask/volume summary stats from ticker data for a specific market.
        
        Args:
            ticker: Market ticker
            
        Returns:
            Dict in format compatible with orderbook summary stats or None if not found
        """
        ticker_state = self.get_ticker_state(ticker)
        if not ticker_state:
            return None
        
        return ticker_state.get_summary_stats()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get processor statistics."""
        return {
            'active_orderbook_markets': len(self.orderbooks),
            'active_ticker_markets': len(self.ticker_states),
            'total_active_markets': len(set(self.orderbooks.keys()) | set(self.ticker_states.keys())),
            'orderbook_tickers': list(self.orderbooks.keys()),
            'ticker_tickers': list(self.ticker_states.keys()),
            'processor_status': 'running' 
            }