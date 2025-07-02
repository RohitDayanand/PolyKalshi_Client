"""
Kalshi Message Processor - Processes raw JSON messages from KalshiQueue to maintain orderbook state.

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
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

@dataclass
class OrderbookLevel:
    """Represents a single price level in the orderbook."""
    price: int
    size: int
    side: str 
    
    @property
    def price_float(self) -> float:
        """Get price as float."""
        return float(self.price)
    
    @property 
    def size_float(self) -> float:
        """Get size as float."""
        return float(self.size)
    
    def get_size(self) -> int:
        """Get the current size of this orderbook level."""
        return self.size
    
    def apply_delta(self, delta: int) -> None:
        """Apply a size delta to this orderbook level with logging."""
        old_size = self.size
        self.size += delta
        
        # Conditional logging for debugging
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"📊 LEVEL DELTA: price={self.price}, side={self.side}, "
                        f"old_size={old_size}, delta={delta}, new_size={self.size}")
        
        # Log warning if size goes negative (shouldn't happen in normal operation)
        if self.size <= 0:
            logger.warning(f"⚠️ NEGATIVE SIZE OR MINIMUM SIZE: price={self.price}, side={self.side}, "
                          f"size={self.size} (delta={delta} applied to {old_size})")
        
        #return size to remove bad keys
        return self.get_size()

            #remove the key itself from the dictionary - can we do this? 




@dataclass 
class OrderbookState:
    #need to add in the yes/no stub
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
                #print an error 
                print("We are processing the wrong order shape - there is some empty price level and kalshi has not updated it. Line 88 in kalshi message processor")
            else:
                price = int(price_level[0])
                size = int(price_level[1])
                self.yes_contracts[price] = OrderbookLevel(price=price, size=size, side="Yes")
        
        # Process Nos -Orderbooks in 
        
        for price_level in snapshot_data['msg'].get('no', []):
                if len(price_level) < 2:
                    #print an error 
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
            #if price level already exists, the
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
            #update the orderbook
                
        self.last_seq = seq
        self.last_update_time = timestamp
        logger.debug(f"Applied delta for sid={self.sid}, seq={seq}, yes={len(self.yes_contracts)}, no={len(self.no_contracts)}")
    
    #Get the current market price of buying 
    def get_yes_market_bid(self) -> int:
        """Get the highest bid (best bid price)."""
        if not self.yes_contracts or len(self.yes_contracts) <= 0:
            return None
         
        #this is an O(n) operation - price levels are limited (~50) so it's mostly constant, but need to consider other approaches
        #We assume that if any orderbook level delta goes below 0, we remove that orderbook level otherwise this max calculation 
        #will NOT work

        return max(self.yes_contracts.keys(), key=lambda x: int(x))
        
    
    def get_no_market_bid(self) -> int:
        """Get the highest bid (best bid price)."""
        if not self.no_contracts or len(self.no_contracts) <= 0:
            #that means there is no market here - it's aalready resovled
            return None
        
        #this is an O(n) operation - price levels are limited (~50) so it's mostly constant, but need to consider other approaches
        #We assume that if any orderbook level delta goes below 0, we remove that orderbook level otherwise this max calculation 
        #will NOT work

        return max(self.no_contracts.keys(), key=lambda x: int(x))
    
    def get_total_bid_volume(self) -> float:
        """Calculate total volume on bid side."""
        #@TODO - implement actual volume logic
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
                "yes": {"bid": float, "ask": float, "volume": float},
                "no": {"bid": float, "ask": float, "volume": float}
            }
        """
        #represents market bid for buying yes contract (selling no contract)
        market_yes = self.get_yes_market_bid()

        #represents market bid for buying no contract (selling yes contract)
        market_no = self.get_no_market_bid()
        
        # Debug logging for bid/ask calculation
        logger.debug(f"🧮 BID/ASK CALC: sid={self.sid}, ticker={self.market_ticker}")
        #redo the logger debugging
        
        # @TODO volume needs to be computed correctly
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

class KalshiMessageProcessor:
    """
    Processes raw Kalshi WebSocket messages to maintain orderbook state.
    
    Designed to work as the message_handler for KalshiQueue.
    Maintains separate orderbook state per market using sid.
    """
    
    def __init__(self):
        self.orderbooks: Dict[int, OrderbookState] = {}  # sid -> OrderbookState
        self.error_callback: Optional[Callable[[Dict[str, Any]], None]] = None
        self.orderbook_update_callback: Optional[Callable[[int, OrderbookState], None]] = None
        
        # Start periodic logging task
        self.logging_task: Optional[asyncio.Task] = None
        self.start_periodic_logging()
        
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
                best_bid = orderbook.get_best_bid()
                best_ask = orderbook.get_best_ask()
                
                logger.info(f"🔍 ORDERBOOK DEBUG: sid={sid}, ticker={orderbook.market_ticker}")
                logger.info(f"  - Bids: {bid_count} levels, Best bid: {best_bid.price if best_bid else 'None'}")
                logger.info(f"  - Asks: {ask_count} levels, Best ask: {best_ask.price if best_ask else 'None'}")
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
        with open("/tmp/kalshi_raw_messages.log", "a") as f:
                f.write(f"{datetime.now().isoformat()} {raw_message}\n")
        try:
            # Log raw message receipt
            logger.debug(f"📨 KALSHI MSG: Received raw message (length: {len(raw_message)})")
            logger.debug(f"📨 KALSHI MSG: Metadata: {metadata}")
            
            # Decode JSON
            try:
                message_data = json.loads(raw_message)
            except json.JSONDecodeError as e:
                logger.error(f"❌ KALSHI MSG: Failed to decode JSON: {e}")
                logger.debug(f"Raw message: {raw_message}")
                return
            
            # Extract message type
            message_type = message_data.get('type')
            if not message_type:
                logger.warning(f"⚠️ KALSHI MSG: No message type found: {message_data}")
                return
            
            logger.info(f"🔄 KALSHI MSG: Processing type '{message_type}' (sid: {message_data.get('sid', 'unknown')})")
            
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
                logger.debug(f"Message data: {message_data}")
                
        except Exception as e:
            logger.error(f"💥 KALSHI MSG: Error processing message: {e}")
            logger.debug(f"Raw message: {raw_message}")
            logger.debug(f"Metadata: {metadata}")
    
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
            logger.debug(f"Applied orderbook_delta for sid={sid}, seq={seq}")
            
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