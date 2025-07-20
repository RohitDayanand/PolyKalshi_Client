"""
ArbitrageDetector - Core arbitrage detection logic separated from lifecycle management.

This module contains the pure arbitrage calculation logic, event handling, and alert generation.
The ArbitrageManager handles pair registration, state management, and coordination.
"""

import logging
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass

from .events.event_bus import EventBus
from .kalshi_client.models.orderbook_state import OrderbookState as KalshiOrderbookState
from .kalshi_client.models.ticker_state import TickerState as KalshiTickerState
from .polymarket_client.models.orderbook_state import PolymarketOrderbookState

logger = logging.getLogger(__name__)

@dataclass
class ArbitrageAlert:
    """Data class representing an arbitrage opportunity."""
    market_pair: str
    timestamp: str
    spread: float
    direction: str  # "kalshi_to_polymarket" or "polymarket_to_kalshi"
    side: str  # "yes" or "no"
    kalshi_price: Optional[float]
    polymarket_price: Optional[float]
    kalshi_market_id: Optional[int]
    polymarket_asset_id: Optional[str]
    confidence: float = 1.0  # Future: confidence score for the arbitrage opportunity

class ArbitrageDetector:
    """
    Core arbitrage detection logic separated from lifecycle management.
    
    Handles:
    - Event subscriptions and processing
    - Fresh state retrieval for depth analysis
    - Arbitrage calculation and alert generation
    - EventBus publishing
    """
    
    def __init__(self, event_bus: EventBus, min_spread_threshold: float = 0.02):
        """
        Initialize the arbitrage detector.
        
        Args:
            event_bus: EventBus instance for communication
            min_spread_threshold: Minimum spread required to trigger arbitrage alert
        """
        self.event_bus = event_bus
        self.min_spread_threshold = min_spread_threshold
        
        # State caches (populated by events)
        self.kalshi_states: Dict[int, KalshiTickerState] = {}  # sid -> TickerState
        self.polymarket_states: Dict[str, PolymarketOrderbookState] = {}  # asset_id -> OrderbookState
        
        # Subscribe to price change events
        self._subscribe_to_events()
        
        logger.info(f"ArbitrageDetector initialized with min_spread_threshold={min_spread_threshold}")
    
    def _subscribe_to_events(self):
        """Subscribe to price change events from both platforms."""
        # Subscribe to Kalshi ticker updates (when bid/ask changes)
        self.event_bus.subscribe('kalshi.ticker_update', self._handle_kalshi_ticker_update)
        
        # Subscribe to Polymarket price changes (when real price changes occur)
        self.event_bus.subscribe('polymarket.price_change', self._handle_polymarket_price_change)
        
        logger.info("ArbitrageDetector subscribed to price change events")
    
    async def _handle_kalshi_ticker_update(self, event_data: Dict[str, Any]):
        """
        Handle Kalshi ticker update events.
        
        Event data format:
        {
            'sid': int,
            'ticker_state': TickerState,
            'bid_ask_changed': bool,
            'market_ticker': str
        }
        """
        try:
            sid = event_data.get('sid')
            ticker_state = event_data.get('ticker_state')
            bid_ask_changed = event_data.get('bid_ask_changed', False)
            
            if not sid or not ticker_state:
                logger.warning("Invalid kalshi.ticker_update event data")
                return
            
            # Update cached state
            self.kalshi_states[sid] = ticker_state
            
            # Only check arbitrage if bid/ask actually changed
            if bid_ask_changed:
                logger.debug(f"🔄 ARBITRAGE: Kalshi ticker update for sid={sid}, checking arbitrage")
                await self._notify_kalshi_update(sid, ticker_state)
            
        except Exception as e:
            logger.error(f"Error handling Kalshi ticker update: {e}")
    
    async def _handle_polymarket_price_change(self, event_data: Dict[str, Any]):
        """
        Handle Polymarket price change events.
        
        Event data format:
        {
            'asset_id': str,
            'orderbook_state': PolymarketOrderbookState,
            'price_changed': bool,
            'market': str
        }
        """
        try:
            asset_id = event_data.get('asset_id')
            orderbook_state = event_data.get('orderbook_state')
            price_changed = event_data.get('price_changed', False)
            
            if not asset_id or not orderbook_state:
                logger.warning("Invalid polymarket.price_change event data")
                return
            
            # Update cached state
            self.polymarket_states[asset_id] = orderbook_state
            
            # Only check arbitrage if price actually changed
            if price_changed:
                logger.debug(f"🔄 ARBITRAGE: Polymarket price change for asset_id={asset_id}, checking arbitrage")
                await self._notify_polymarket_update(asset_id, orderbook_state)
            
        except Exception as e:
            logger.error(f"Error handling Polymarket price change: {e}")
    
    async def _notify_kalshi_update(self, sid: int, ticker_state: KalshiTickerState):
        """Notify that Kalshi has updated - ArbitrageManager will handle pair matching."""
        await self.event_bus.publish('arbitrage.kalshi_updated', {
            'sid': sid,
            'ticker_state': ticker_state,
            'timestamp': datetime.now().isoformat()
        })
    
    async def _notify_polymarket_update(self, asset_id: str, orderbook_state: PolymarketOrderbookState):
        """Notify that Polymarket has updated - ArbitrageManager will handle pair matching."""
        await self.event_bus.publish('arbitrage.polymarket_updated', {
            'asset_id': asset_id,
            'orderbook_state': orderbook_state,
            'timestamp': datetime.now().isoformat()
        })
    
    async def check_arbitrage_for_pair(self, pair_name: str, kalshi_sid: int, 
                                     poly_yes_asset_id: str, poly_no_asset_id: str) -> List[ArbitrageAlert]:
        """
        Check arbitrage for a specific pair using fresh orderbook states.
        This ensures we have current depth information for sizing the arbitrage.
        
        Args:
            pair_name: Market pair identifier
            kalshi_sid: Kalshi subscription ID
            poly_yes_asset_id: Polymarket YES asset ID
            poly_no_asset_id: Polymarket NO asset ID
            
        Returns:
            List of arbitrage alerts (empty if no opportunities found)
        """
        # Get FRESH states from both platforms - critical for depth/liquidity analysis
        kalshi_ticker = self.kalshi_states.get(kalshi_sid)
        poly_yes_orderbook = self.polymarket_states.get(poly_yes_asset_id)
        poly_no_orderbook = self.polymarket_states.get(poly_no_asset_id)
        
        # Validate we have fresh data from both sides
        if not kalshi_ticker:
            logger.debug(f"No current Kalshi ticker state for sid={kalshi_sid} in pair {pair_name}")
            return []
        if not poly_yes_orderbook:
            logger.debug(f"No current Polymarket YES orderbook for asset_id={poly_yes_asset_id} in pair {pair_name}")
            return []
        if not poly_no_orderbook:
            logger.debug(f"No current Polymarket NO orderbook for asset_id={poly_no_asset_id} in pair {pair_name}")
            return []
        
        logger.debug(f"🔄 ARBITRAGE: Checking {pair_name} - using fresh orderbook states")
        
        # Extract current pricing and depth information
        kalshi_prices = kalshi_ticker.get_summary_stats()
        poly_yes_prices = poly_yes_orderbook.calculate_current_prices()
        poly_no_prices = poly_no_orderbook.calculate_current_prices()
        
        # TODO: Add depth analysis here
        # kalshi_depth = self._analyze_kalshi_depth(kalshi_ticker)
        # poly_depth = self._analyze_polymarket_depth(poly_yes_orderbook, poly_no_orderbook)
        
        # Calculate arbitrage opportunities with current market state
        return await self._calculate_arbitrage_alerts(
            pair_name, kalshi_prices, poly_yes_prices, poly_no_prices,
            kalshi_sid, poly_yes_asset_id
        )
    
    async def _calculate_arbitrage_alerts(self, pair_name: str, kalshi_prices: Dict, 
                                        poly_yes_prices: Dict, poly_no_prices: Dict,
                                        kalshi_sid: int, poly_yes_asset_id: str) -> List[ArbitrageAlert]:
        """
        Calculate arbitrage opportunities between Kalshi and Polymarket prices.
        
        Returns:
            List of arbitrage alerts
        """
        alerts = []
        
        # Extract prices (with validation)
        kalshi_yes_bid = kalshi_prices.get("yes", {}).get("bid")
        kalshi_yes_ask = kalshi_prices.get("yes", {}).get("ask") 
        kalshi_no_bid = kalshi_prices.get("no", {}).get("bid")
        kalshi_no_ask = kalshi_prices.get("no", {}).get("ask")
        
        poly_yes_bid = poly_yes_prices.get("bid")
        poly_yes_ask = poly_yes_prices.get("ask")
        poly_no_bid = poly_no_prices.get("bid") 
        poly_no_ask = poly_no_prices.get("ask")
        
        # Check for valid prices before calculating spreads
        if None in [kalshi_yes_bid, kalshi_yes_ask, poly_yes_bid, poly_yes_ask]:
            logger.debug(f"Missing YES prices for {pair_name}, skipping arbitrage check")
            return alerts
        
        if None in [kalshi_no_bid, kalshi_no_ask, poly_no_bid, poly_no_ask]:
            logger.debug(f"Missing NO prices for {pair_name}, skipping arbitrage check") 
            return alerts
        
        # Check YES side arbitrage opportunities
        # Kalshi YES bid > Polymarket YES ask (sell Kalshi, buy Polymarket)
        if kalshi_yes_bid > poly_yes_ask:
            spread = kalshi_yes_bid - poly_yes_ask
            if spread >= self.min_spread_threshold:
                alert = ArbitrageAlert(
                    market_pair=pair_name,
                    timestamp=datetime.now().isoformat(),
                    spread=spread,
                    direction="kalshi_to_polymarket",
                    side="yes",
                    kalshi_price=kalshi_yes_bid,
                    polymarket_price=poly_yes_ask,
                    kalshi_market_id=kalshi_sid,
                    polymarket_asset_id=poly_yes_asset_id
                )
                alerts.append(alert)
        
        # Polymarket YES bid > Kalshi YES ask (sell Polymarket, buy Kalshi)
        if poly_yes_bid > kalshi_yes_ask:
            spread = poly_yes_bid - kalshi_yes_ask
            if spread >= self.min_spread_threshold:
                alert = ArbitrageAlert(
                    market_pair=pair_name,
                    timestamp=datetime.now().isoformat(),
                    spread=spread,
                    direction="polymarket_to_kalshi", 
                    side="yes",
                    kalshi_price=kalshi_yes_ask,
                    polymarket_price=poly_yes_bid,
                    kalshi_market_id=kalshi_sid,
                    polymarket_asset_id=poly_yes_asset_id
                )
                alerts.append(alert)
        
        # Check NO side arbitrage opportunities
        # Kalshi NO bid > Polymarket NO ask (sell Kalshi, buy Polymarket)
        if kalshi_no_bid > poly_no_ask:
            spread = kalshi_no_bid - poly_no_ask
            if spread >= self.min_spread_threshold:
                alert = ArbitrageAlert(
                    market_pair=pair_name,
                    timestamp=datetime.now().isoformat(),
                    spread=spread,
                    direction="kalshi_to_polymarket",
                    side="no", 
                    kalshi_price=kalshi_no_bid,
                    polymarket_price=poly_no_ask,
                    kalshi_market_id=kalshi_sid,
                    polymarket_asset_id=poly_yes_asset_id  # Using YES asset_id as primary
                )
                alerts.append(alert)
        
        # Polymarket NO bid > Kalshi NO ask (sell Polymarket, buy Kalshi)
        if poly_no_bid > kalshi_no_ask:
            spread = poly_no_bid - kalshi_no_ask
            if spread >= self.min_spread_threshold:
                alert = ArbitrageAlert(
                    market_pair=pair_name,
                    timestamp=datetime.now().isoformat(),
                    spread=spread,
                    direction="polymarket_to_kalshi",
                    side="no",
                    kalshi_price=kalshi_no_ask,
                    polymarket_price=poly_no_bid,
                    kalshi_market_id=kalshi_sid,
                    polymarket_asset_id=poly_yes_asset_id  # Using YES asset_id as primary
                )
                alerts.append(alert)
        
        return alerts
    
    async def publish_arbitrage_alert(self, alert: ArbitrageAlert):
        """Publish arbitrage alert via EventBus."""
        try:
            # Publish to EventBus for other components to consume
            await self.event_bus.publish('arbitrage.alert', {
                'alert': alert,
                'market_pair': alert.market_pair,
                'spread': alert.spread,
                'direction': alert.direction,
                'timestamp': alert.timestamp
            })
            
            logger.info(f"🚨 ARBITRAGE ALERT: {alert.market_pair} - {alert.direction} - spread: {alert.spread:.3f}")
            
        except Exception as e:
            logger.error(f"Error publishing arbitrage alert: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get detector statistics."""
        return {
            'kalshi_states_count': len(self.kalshi_states),
            'polymarket_states_count': len(self.polymarket_states),
            'kalshi_sids': list(self.kalshi_states.keys()),
            'polymarket_asset_ids': list(self.polymarket_states.keys()),
            'min_spread_threshold': self.min_spread_threshold
        }