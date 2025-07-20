"""
TickerState - Represents cumulative ticker state for a Kalshi market.

Handles ticker_v2 messages which contain incremental updates including:
- Price updates from trades
- Bid/ask changes  
- Volume and open interest deltas
- Dollar volume and open interest deltas
"""

import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any
from datetime import datetime
import asyncio
import aiohttp

logger = logging.getLogger(__name__)

@dataclass
class TickerState:
    """
    Represents cumulative ticker state for a Kalshi market.
    
    Fields store cumulative values, updated by applying deltas from ticker_v2 messages.
    Can optionally fetch initial market state from Kalshi markets API on creation.
    """
    sid: int
    market_ticker: str
    
    # Current price and bid/ask (in cents, 1-99)
    price: Optional[int] = None
    yes_bid: Optional[int] = None
    yes_ask: Optional[int] = None
    
    # Cumulative volumes and open interest
    volume: int = 0
    open_interest: int = 0
    
    # Dollar volumes - NOTE: Cannot accurately recreate dollar volume state from API
    # Starting from 0 and will be updated via ticker_v2 deltas only
    dollar_volume: int = 0
    dollar_open_interest: int = 0
    
    # Tracking
    last_update_time: Optional[datetime] = None
    last_timestamp: Optional[int] = None
    update_count: int = 0
    
    # API configuration
    api_base_url: str = "https://api.elections.kalshi.com/trade-api/v2"
    
    def __post_init__(self):
        """Initialize ticker state - async API fetch will be called separately."""
        # Note: API initialization is now done via async factory method
        # This ensures non-blocking operation in the event loop
        logger.debug(f"TickerState created for {self.market_ticker} - API init will be called separately")
    
    async def _fetch_initial_market_state_async(self) -> None:
        """
        Async fetch current market state from Kalshi markets API.
        
        Populates: price (last_price), yes_bid, yes_ask, volume, open_interest
        Note: Dollar volumes cannot be accurately recreated and start at 0
        """
        try:
            # Construct API request
            url = f"{self.api_base_url}/markets"
            params = {
                "tickers": self.market_ticker, #check carefully - we can't mock this very easy for testing
                "limit": 1, 
                "status": "open"
            }
            headers = {
                "accept": "application/json",
                "User-Agent": "Kalshi-TickerState/1.0"
            }
            
            logger.debug(f"🔍 API: Async fetching market state for {self.market_ticker}")
            
            # Make async API request with timeout
            timeout = aiohttp.ClientTimeout(total=5.0)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, headers=headers, params=params) as response:
                    response.raise_for_status()
                    data = await response.json()
            
            markets = data.get("markets", [])
            
            if not markets:
                logger.warning(f"🔍 API: No market found for ticker {self.market_ticker}")
                return
            
            market_data = markets[0]
            
            # Validate this is the correct market
            api_ticker = market_data.get("ticker", "")
            if api_ticker != self.market_ticker:
                logger.warning(f"🔍 API: Ticker mismatch - requested {self.market_ticker}, got {api_ticker}")
                return
            
            # Extract and validate market data
            self._apply_api_market_data(market_data)
            
            logger.info(f"🔍 API: Successfully initialized {self.market_ticker} - "
                       f"price={self.price}, bid={self.yes_bid}, ask={self.yes_ask}, "
                       f"volume={self.volume}, oi={self.open_interest}")
            
        except asyncio.TimeoutError:
            logger.warning(f"🔍 API: Timeout fetching market state for {self.market_ticker}")
        except aiohttp.ClientError as e:
            logger.warning(f"🔍 API: Request failed for {self.market_ticker}: {e}")
        except ValueError as e:
            logger.warning(f"🔍 API: Invalid JSON response for {self.market_ticker}: {e}")
        except Exception as e:
            logger.error(f"🔍 API: Unexpected error fetching {self.market_ticker}: {e}")
    
    def _apply_api_market_data(self, market_data: Dict[str, Any]) -> None:
        """
        Apply market data from Kalshi API to ticker state.
        
        Args:
            market_data: Market data dict from Kalshi markets API response
        """
        # Extract last_price (can be 0 if no trades yet)
        last_price = market_data.get("last_price")
        if isinstance(last_price, int) and last_price >= 0:
            # Only set price if there have been trades (price > 0)
            if last_price > 0:
                self.price = last_price
                logger.debug(f"🔍 API: Set price={last_price} for {self.market_ticker}")
            else:
                logger.debug(f"🔍 API: No trades yet for {self.market_ticker} (last_price=0)")
        
        # Extract yes_bid (1-99 cents)
        yes_bid = market_data.get("yes_bid")
        if isinstance(yes_bid, int) and 1 <= yes_bid <= 99:
            self.yes_bid = yes_bid
            logger.debug(f"🔍 API: Set yes_bid={yes_bid} for {self.market_ticker}")
        elif yes_bid == 0:
            logger.debug(f"🔍 API: No yes_bid available for {self.market_ticker}")
        else:
            logger.warning(f"🔍 API: Invalid yes_bid={yes_bid} for {self.market_ticker}")
        
        # Extract yes_ask (1-99 cents)
        yes_ask = market_data.get("yes_ask")
        if isinstance(yes_ask, int) and 1 <= yes_ask <= 99:
            self.yes_ask = yes_ask
            logger.debug(f"🔍 API: Set yes_ask={yes_ask} for {self.market_ticker}")
        elif yes_ask == 0:
            logger.debug(f"🔍 API: No yes_ask available for {self.market_ticker}")
        else:
            logger.warning(f"🔍 API: Invalid yes_ask={yes_ask} for {self.market_ticker}")
        
        # Extract volume (can be 0)
        volume = market_data.get("volume")
        if isinstance(volume, int) and volume >= 0:
            self.volume = volume
            logger.debug(f"🔍 API: Set volume={volume} for {self.market_ticker}")
        else:
            logger.warning(f"🔍 API: Invalid volume={volume} for {self.market_ticker}")
        
        # Extract open_interest (can be 0)
        open_interest = market_data.get("open_interest")
        if isinstance(open_interest, int) and open_interest >= 0:
            self.open_interest = open_interest
            logger.debug(f"🔍 API: Set open_interest={open_interest} for {self.market_ticker}")
        else:
            logger.warning(f"🔍 API: Invalid open_interest={open_interest} for {self.market_ticker}")
        
        # Log that dollar volumes start at 0
        logger.debug(f"🔍 API: Dollar volumes start at 0 for {self.market_ticker} "
                    "(cannot recreate from API - will update via ticker_v2 deltas)")
        
        # Update tracking
        self.last_update_time = datetime.now()
        
        # Validate bid/ask spread if both are present
        if self.yes_bid is not None and self.yes_ask is not None:
            if self.yes_bid >= self.yes_ask:
                logger.warning(f"🔍 API: Invalid spread for {self.market_ticker}: "
                             f"bid={self.yes_bid} >= ask={self.yes_ask}")
            else:
                spread = self.yes_ask - self.yes_bid
                logger.debug(f"🔍 API: Valid spread for {self.market_ticker}: "
                           f"bid={self.yes_bid}, ask={self.yes_ask}, spread={spread}")
    
    @classmethod
    async def create_with_api_init(cls, sid: int, market_ticker: str, 
                                  api_base_url: str = "https://api.elections.kalshi.com/trade-api/v2") -> 'TickerState':
        """
        Async factory method to create TickerState with API initialization.
        
        Args:
            sid: Market subscription ID
            market_ticker: Market ticker symbol
            api_base_url: Kalshi API base URL (defaults to production)
            
        Returns:
            TickerState: Initialized with current market data from API
        """
        instance = cls(
            sid=sid,
            market_ticker=market_ticker,
            api_base_url=api_base_url
        )
        
        # Perform async API initialization
        await instance._fetch_initial_market_state_async()
        
        return instance
    
    @classmethod  
    def create_without_api_init(cls, sid: int, market_ticker: str) -> 'TickerState':
        """
        Factory method to create TickerState without API initialization.
        Useful for testing or when API is unavailable.
        
        Args:
            sid: Market subscription ID
            market_ticker: Market ticker symbol
            
        Returns:
            TickerState: With default values (will update via ticker_v2 messages)
        """
        # Create instance but skip __post_init__ API call
        instance = cls.__new__(cls)
        instance.sid = sid
        instance.market_ticker = market_ticker
        instance.price = None
        instance.yes_bid = None
        instance.yes_ask = None
        instance.volume = 0
        instance.open_interest = 0
        instance.dollar_volume = 0
        instance.dollar_open_interest = 0
        instance.last_update_time = None
        instance.last_timestamp = None
        instance.update_count = 0
        instance.api_base_url = "https://api.elections.kalshi.com/trade-api/v2"
        
        logger.info(f"Created TickerState for {market_ticker} without API initialization")
        return instance
    
    def apply_ticker_update(self, message_data: Dict[str, Any]) -> None:
        """
        Apply a ticker_v2 message update to the state.
        
        Expected message structure:
        {
            "type": "ticker_v2",
            "sid": <int>,
            "msg": {
                "market_ticker": <string>,
                "price": <int>,                    # Optional: 1-99, only on trade
                "yes_bid": <int>,                  # Optional: 1-99, only on bid/ask change  
                "yes_ask": <int>,                  # Optional: 1-99, only on bid/ask change
                "volume_delta": <int>,             # Optional: only on trade
                "open_interest_delta": <int>,      # Optional: only on trade
                "dollar_volume_delta": <int>,      # Optional: only on trade
                "dollar_open_interest_delta": <int>, # Optional: only on trade
                "ts": <int>                        # Unix timestamp in seconds
            }
        }
        
        Args:
            message_data: Dict containing the full ticker_v2 message
        """
        # Validate message structure
        if not isinstance(message_data, dict):
            logger.warning(f"Invalid ticker_v2 message: expected dict, got {type(message_data)}")
            return
        
        # Extract message components
        msg_type = message_data.get('type')
        sid = message_data.get('sid')
        msg = message_data.get('msg', {})
        
        # Validate message type
        # @TODO remove - redudnant
        if msg_type != 'ticker_v2':
            logger.warning(f"Unexpected message type for ticker update: {msg_type}")
            return
        
        # Validate sid matches
        # @TODO remove - redundant
        if sid != self.sid:
            logger.warning(f"SID mismatch in ticker update: expected {self.sid}, got {sid}")
            return
        
        # Validate msg is a dict
        if not isinstance(msg, dict):
            logger.warning(f"Invalid msg field in ticker_v2: expected dict, got {type(msg)}")
            return
        
        # Track what fields were updated for logging
        updated_fields = []
        
        # Process market_ticker (should match, but update if needed)
        if 'market_ticker' in msg:
            if msg['market_ticker'] != self.market_ticker:
                logger.warning(f"Market ticker changed for sid={self.sid}: "
                             f"{self.market_ticker} -> {msg['market_ticker']}")
                self.market_ticker = msg['market_ticker']
        
        # Process price update (only present on trades)
        if 'price' in msg:
            price_value = msg['price']
            if isinstance(price_value, int) and 1 <= price_value <= 99:
                self.price = price_value
                updated_fields.append(f"price={price_value}")
            else:
                logger.warning(f"Invalid price value in ticker_v2: {price_value}")
        
        # Process bid/ask updates (only present on orderbook changes)
        # Track if bid/ask changed for arbitrage detection
        bid_ask_changed = False
        
        if 'yes_bid' in msg:
            yes_bid_value = msg['yes_bid']
            if isinstance(yes_bid_value, int) and 1 <= yes_bid_value <= 99:
                old_yes_bid = self.yes_bid
                self.yes_bid = yes_bid_value
                updated_fields.append(f"yes_bid={yes_bid_value}")
                if old_yes_bid != yes_bid_value:
                    bid_ask_changed = True
            else:
                logger.warning(f"Invalid yes_bid value in ticker_v2: {yes_bid_value}")
        
        if 'yes_ask' in msg:
            yes_ask_value = msg['yes_ask']
            if isinstance(yes_ask_value, int) and 1 <= yes_ask_value <= 99:
                old_yes_ask = self.yes_ask
                self.yes_ask = yes_ask_value
                updated_fields.append(f"yes_ask={yes_ask_value}")
                if old_yes_ask != yes_ask_value:
                    bid_ask_changed = True
            else:
                logger.warning(f"Invalid yes_ask value in ticker_v2: {yes_ask_value}")
        
        # Process volume deltas (only present on trades)
        if 'volume_delta' in msg:
            volume_delta = msg['volume_delta']
            if isinstance(volume_delta, int):
                old_volume = self.volume
                self.volume += volume_delta
                # Ensure volume doesn't go negative
                self.volume = max(0, self.volume)
                updated_fields.append(f"volume={old_volume}+{volume_delta}={self.volume}")
            else:
                logger.warning(f"Invalid volume_delta value in ticker_v2: {volume_delta}")
        
        if 'open_interest_delta' in msg:
            oi_delta = msg['open_interest_delta']
            if isinstance(oi_delta, int):
                old_oi = self.open_interest
                self.open_interest += oi_delta
                # Ensure open interest doesn't go negative
                self.open_interest = max(0, self.open_interest)
                updated_fields.append(f"open_interest={old_oi}+{oi_delta}={self.open_interest}")
            else:
                logger.warning(f"Invalid open_interest_delta value in ticker_v2: {oi_delta}")
        
        if 'dollar_volume_delta' in msg:
            dv_delta = msg['dollar_volume_delta']
            if isinstance(dv_delta, int):
                old_dv = self.dollar_volume
                self.dollar_volume += dv_delta
                # Ensure dollar volume doesn't go negative
                self.dollar_volume = max(0, self.dollar_volume)
                updated_fields.append(f"dollar_volume={old_dv}+{dv_delta}={self.dollar_volume}")
            else:
                logger.warning(f"Invalid dollar_volume_delta value in ticker_v2: {dv_delta}")
        
        if 'dollar_open_interest_delta' in msg:
            doi_delta = msg['dollar_open_interest_delta']
            if isinstance(doi_delta, int):
                old_doi = self.dollar_open_interest
                self.dollar_open_interest += doi_delta
                # Ensure dollar open interest doesn't go negative
                self.dollar_open_interest = max(0, self.dollar_open_interest)
                updated_fields.append(f"dollar_open_interest={old_doi}+{doi_delta}={self.dollar_open_interest}")
            else:
                logger.warning(f"Invalid dollar_open_interest_delta value in ticker_v2: {doi_delta}")
        
        # Process timestamp
        if 'ts' in msg:
            ts_value = msg['ts']
            if isinstance(ts_value, int):
                self.last_timestamp = ts_value
                updated_fields.append(f"ts={ts_value}")
            else:
                logger.warning(f"Invalid timestamp value in ticker_v2: {ts_value}")
        
        # Update tracking
        self.last_update_time = datetime.now()
        self.update_count += 1
        
        # Log the update with details of what changed
        if updated_fields:
            logger.debug(f"📊 TICKER UPDATE sid={self.sid} ticker={self.market_ticker}: {', '.join(updated_fields)}")
        else:
            logger.warning(f"📊 TICKER UPDATE sid={self.sid}: No valid fields updated in message: {msg}")
        
        # Validate bid/ask spread if both are present
        if self.yes_bid is not None and self.yes_ask is not None:
            if self.yes_bid >= self.yes_ask:
                logger.warning(f"📊 TICKER WARNING: Invalid spread for {self.market_ticker}: "
                             f"bid={self.yes_bid} >= ask={self.yes_ask}")
        
        # Return whether bid/ask changed for arbitrage detection
        return bid_ask_changed
    
    @property
    def price_float(self) -> Optional[float]:
        """Get price as float (0.0-1.0 probability)."""
        return self.price / 100.0 if self.price is not None else None
    
    @property
    def yes_bid_float(self) -> Optional[float]:
        """Get yes bid as float (0.0-1.0 probability)."""
        return self.yes_bid / 100.0 if self.yes_bid is not None else None
    
    @property
    def yes_ask_float(self) -> Optional[float]:
        """Get yes ask as float (0.0-1.0 probability)."""
        return self.yes_ask / 100.0 if self.yes_ask is not None else None
    
    @property
    def no_bid_float(self) -> Optional[float]:
        """Get implied no bid as float (0.0-1.0 probability)."""
        return (100 - self.yes_ask) / 100.0 if self.yes_ask is not None else None
    
    @property
    def no_ask_float(self) -> Optional[float]:
        """Get implied no ask as float (0.0-1.0 probability)."""
        return (100 - self.yes_bid) / 100.0 if self.yes_bid is not None else None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'sid': self.sid,
            'market_ticker': self.market_ticker,
            'price': self.price,
            'price_float': self.price_float,
            'yes_bid': self.yes_bid,
            'yes_ask': self.yes_ask,
            'yes_bid_float': self.yes_bid_float,
            'yes_ask_float': self.yes_ask_float,
            'no_bid_float': self.no_bid_float,
            'no_ask_float': self.no_ask_float,
            'volume': self.volume,
            'open_interest': self.open_interest,
            'dollar_volume': self.dollar_volume,
            'dollar_open_interest': self.dollar_open_interest,
            'last_update_time': self.last_update_time.isoformat() if self.last_update_time else None,
            'last_timestamp': self.last_timestamp,
            'update_count': self.update_count
        }
    
    def get_summary_stats(self) -> Dict[str, Dict[str, Optional[float]]]:
        """
        Get summary stats in format compatible with orderbook summary stats.
        
        Returns:
            Dict in format:
            {
                "yes": {"bid": float, "ask": float, "volume": float},
                "no": {"bid": float, "ask": float, "volume": float}
            }
        """
        return {
            "yes": {
                "bid": self.yes_bid_float,
                "ask": self.yes_ask_float,
                "volume": float(self.volume) if self.volume is not None else None
            },
            "no": {
                "bid": self.no_bid_float,
                "ask": self.no_ask_float,
                "volume": float(self.volume) if self.volume is not None else None  # Same volume for both sides
            }
        }
