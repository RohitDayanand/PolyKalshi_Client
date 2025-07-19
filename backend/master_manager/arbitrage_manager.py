"""
ArbitrageManager - Detects and streams arbitrage opportunities between Kalshi and Polymarket.

This manager monitors orderbook states from both platforms and calculates spreads to identify 
arbitrage opportunities. It emits real-time arbitrage alerts to the frontend.

Key Features:
- Real-time arbitrage detection across platforms
- Configurable minimum spread threshold
- Streaming arbitrage alerts to frontend
- Market pair matching and validation
"""

import logging
import asyncio
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime
from dataclasses import dataclass

# Import streaming function
try:
    from backend.websocket_server import publish_arbitrage_alert
except ImportError:
    # Fallback for development/testing
    async def publish_arbitrage_alert(alert_data: dict):
        pass

from .kalshi_client.models.orderbook_state import OrderbookState as KalshiOrderbookState
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

class ArbitrageManager:
    """
    Manages arbitrage detection between Kalshi and Polymarket orderbooks.
    
    Monitors orderbook updates from both platforms and calculates spreads to identify
    arbitrage opportunities. Emits real-time alerts when opportunities are found.
    """
    
    def __init__(self, min_spread_threshold: float = 0.02):
        """
        Initialize ArbitrageManager.
        
        Args:
            min_spread_threshold: Minimum spread required to trigger arbitrage alert (default: 2%)
        """
        self.min_spread_threshold = min_spread_threshold
        self.market_pairs: Dict[str, Dict[str, Any]] = {}  # market_pair -> {kalshi_sid, polymarket_yes_asset_id, polymarket_no_asset_id}
        self.arbitrage_alert_callback: Optional[Callable[[ArbitrageAlert], None]] = None
        self.last_alerts: Dict[str, ArbitrageAlert] = {}  # market_pair -> last_alert (for deduplication)
        
        # References to market managers (will be injected)
        self.kalshi_processor = None
        self.polymarket_processor = None
        
        logger.info(f"ArbitrageManager initialized with min_spread_threshold={min_spread_threshold}")
    
    def set_processors(self, kalshi_processor, polymarket_processor):
        """Inject processor references from MarketsManager."""
        self.kalshi_processor = kalshi_processor
        self.polymarket_processor = polymarket_processor
        logger.info("ArbitrageManager processors set")
    
    def set_arbitrage_alert_callback(self, callback: Callable[[ArbitrageAlert], None]):
        """Set callback for arbitrage alert notifications."""
        self.arbitrage_alert_callback = callback
        logger.info("ArbitrageManager arbitrage alert callback set")
    
    def add_market_pair(self, market_pair: str, kalshi_sid: int, polymarket_yes_asset_id: str, polymarket_no_asset_id: str):
        """
        Add a market pair for arbitrage monitoring.
        
        Args:
            market_pair: Human-readable market pair identifier
            kalshi_sid: Kalshi market subscription ID
            polymarket_yes_asset_id: Polymarket YES asset ID
            polymarket_no_asset_id: Polymarket NO asset ID
        """
        self.market_pairs[market_pair] = {
            'kalshi_sid': kalshi_sid,
            'polymarket_yes_asset_id': polymarket_yes_asset_id,
            'polymarket_no_asset_id': polymarket_no_asset_id
        }
        logger.info(f"Added market pair: {market_pair} -> Kalshi:{kalshi_sid}, Poly:{polymarket_yes_asset_id}/{polymarket_no_asset_id}")
    
    def remove_market_pair(self, market_pair: str):
        """Remove a market pair from monitoring."""
        if market_pair in self.market_pairs:
            del self.market_pairs[market_pair]
            if market_pair in self.last_alerts:
                del self.last_alerts[market_pair]
            logger.info(f"Removed market pair: {market_pair}")
    
    async def check_arbitrage_for_pair(self, market_pair: str) -> List[ArbitrageAlert]:
        """
        Check for arbitrage opportunities for a specific market pair.
        
        Args:
            market_pair: Market pair identifier
            
        Returns:
            List of arbitrage alerts (empty if no opportunities found)
        """
        if market_pair not in self.market_pairs:
            logger.warning(f"Market pair {market_pair} not registered")
            return []
        
        if not self.kalshi_processor or not self.polymarket_processor:
            logger.warning("Processors not set, cannot check arbitrage")
            return []
        
        pair_config = self.market_pairs[market_pair]
        kalshi_sid = pair_config['kalshi_sid']
        poly_yes_asset_id = pair_config['polymarket_yes_asset_id']
        poly_no_asset_id = pair_config['polymarket_no_asset_id']
        
        # Get orderbook states
        kalshi_orderbook = self.kalshi_processor.get_orderbook(kalshi_sid)
        poly_yes_orderbook = self.polymarket_processor.get_orderbook(poly_yes_asset_id)
        poly_no_orderbook = self.polymarket_processor.get_orderbook(poly_no_asset_id)
        
        # Skip if any orderbook is missing
        if not kalshi_orderbook:
            logger.debug(f"No Kalshi orderbook for sid={kalshi_sid}")
            return []
        if not poly_yes_orderbook:
            logger.debug(f"No Polymarket YES orderbook for asset_id={poly_yes_asset_id}")
            return []
        if not poly_no_orderbook:
            logger.debug(f"No Polymarket NO orderbook for asset_id={poly_no_asset_id}")
            return []
        
        # Calculate market prices
        kalshi_prices = kalshi_orderbook.calculate_yes_no_prices()
        poly_yes_prices = poly_yes_orderbook.calculate_market_prices()
        poly_no_prices = poly_no_orderbook.calculate_market_prices()
        
        alerts = []
        timestamp = datetime.now().isoformat()
        
        # Check arbitrage opportunities
        # Opportunity 1: Kalshi YES bid + Polymarket NO ask < 1.0
        kalshi_yes_bid = kalshi_prices.get('yes', {}).get('bid')
        poly_no_ask = poly_no_prices.get('ask')
        
        if kalshi_yes_bid is not None and poly_no_ask is not None:
            spread = 1.0 - (kalshi_yes_bid + poly_no_ask)
            if spread > self.min_spread_threshold:
                alert = ArbitrageAlert(
                    market_pair=market_pair,
                    timestamp=timestamp,
                    spread=spread,
                    direction="kalshi_to_polymarket",
                    side="yes",
                    kalshi_price=kalshi_yes_bid,
                    polymarket_price=poly_no_ask,
                    kalshi_market_id=kalshi_sid,
                    polymarket_asset_id=poly_no_asset_id
                )
                alerts.append(alert)
                logger.info(f"🚨 ARBITRAGE ALERT: {market_pair} - Buy YES on Kalshi ({kalshi_yes_bid:.3f}), Buy NO on Polymarket ({poly_no_ask:.3f}), Spread: {spread:.3f}")
        
        # Opportunity 2: Kalshi NO bid + Polymarket YES ask < 1.0
        kalshi_no_bid = kalshi_prices.get('no', {}).get('bid')
        poly_yes_ask = poly_yes_prices.get('ask')
        
        if kalshi_no_bid is not None and poly_yes_ask is not None:
            spread = 1.0 - (kalshi_no_bid + poly_yes_ask)
            if spread > self.min_spread_threshold:
                alert = ArbitrageAlert(
                    market_pair=market_pair,
                    timestamp=timestamp,
                    spread=spread,
                    direction="kalshi_to_polymarket",
                    side="no",
                    kalshi_price=kalshi_no_bid,
                    polymarket_price=poly_yes_ask,
                    kalshi_market_id=kalshi_sid,
                    polymarket_asset_id=poly_yes_asset_id
                )
                alerts.append(alert)
                logger.info(f"🚨 ARBITRAGE ALERT: {market_pair} - Buy NO on Kalshi ({kalshi_no_bid:.3f}), Buy YES on Polymarket ({poly_yes_ask:.3f}), Spread: {spread:.3f}")
        
        # Opportunity 3: Polymarket YES bid + Kalshi NO ask < 1.0
        poly_yes_bid = poly_yes_prices.get('bid')
        kalshi_no_ask = kalshi_prices.get('no', {}).get('ask')
        
        if poly_yes_bid is not None and kalshi_no_ask is not None:
            spread = 1.0 - (poly_yes_bid + kalshi_no_ask)
            if spread > self.min_spread_threshold:
                alert = ArbitrageAlert(
                    market_pair=market_pair,
                    timestamp=timestamp,
                    spread=spread,
                    direction="polymarket_to_kalshi",
                    side="yes",
                    kalshi_price=kalshi_no_ask,
                    polymarket_price=poly_yes_bid,
                    kalshi_market_id=kalshi_sid,
                    polymarket_asset_id=poly_yes_asset_id
                )
                alerts.append(alert)
                logger.info(f"🚨 ARBITRAGE ALERT: {market_pair} - Buy YES on Polymarket ({poly_yes_bid:.3f}), Buy NO on Kalshi ({kalshi_no_ask:.3f}), Spread: {spread:.3f}")
        
        # Opportunity 4: Polymarket NO bid + Kalshi YES ask < 1.0
        poly_no_bid = poly_no_prices.get('bid')
        kalshi_yes_ask = kalshi_prices.get('yes', {}).get('ask')
        
        if poly_no_bid is not None and kalshi_yes_ask is not None:
            spread = 1.0 - (poly_no_bid + kalshi_yes_ask)
            if spread > self.min_spread_threshold:
                alert = ArbitrageAlert(
                    market_pair=market_pair,
                    timestamp=timestamp,
                    spread=spread,
                    direction="polymarket_to_kalshi",
                    side="no",
                    kalshi_price=kalshi_yes_ask,
                    polymarket_price=poly_no_bid,
                    kalshi_market_id=kalshi_sid,
                    polymarket_asset_id=poly_no_asset_id
                )
                alerts.append(alert)
                logger.info(f"🚨 ARBITRAGE ALERT: {market_pair} - Buy NO on Polymarket ({poly_no_bid:.3f}), Buy YES on Kalshi ({kalshi_yes_ask:.3f}), Spread: {spread:.3f}")
        
        return alerts
    
    async def check_all_arbitrage_opportunities(self) -> List[ArbitrageAlert]:
        """
        Check arbitrage opportunities for all registered market pairs.
        
        Returns:
            List of all arbitrage alerts found
        """
        all_alerts = []
        
        for market_pair in self.market_pairs.keys():
            try:
                alerts = await self.check_arbitrage_for_pair(market_pair)
                all_alerts.extend(alerts)
            except Exception as e:
                logger.error(f"Error checking arbitrage for {market_pair}: {e}")
        
        return all_alerts
    
    async def handle_kalshi_orderbook_update(self, sid: int, orderbook_state: KalshiOrderbookState):
        """
        Handle Kalshi orderbook updates and check for arbitrage opportunities.
        
        Args:
            sid: Kalshi market subscription ID
            orderbook_state: Updated orderbook state
        """
        # Find market pairs that include this Kalshi market
        relevant_pairs = [pair for pair, config in self.market_pairs.items() 
                         if config['kalshi_sid'] == sid]
        
        for market_pair in relevant_pairs:
            try:
                alerts = await self.check_arbitrage_for_pair(market_pair)
                for alert in alerts:
                    await self._emit_arbitrage_alert(alert)
            except Exception as e:
                logger.error(f"Error checking arbitrage for {market_pair} after Kalshi update: {e}")
    
    async def handle_polymarket_orderbook_update(self, asset_id: str, orderbook_state: PolymarketOrderbookState):
        """
        Handle Polymarket orderbook updates and check for arbitrage opportunities.
        
        Args:
            asset_id: Polymarket asset ID
            orderbook_state: Updated orderbook state
        """
        # Find market pairs that include this Polymarket asset
        relevant_pairs = [pair for pair, config in self.market_pairs.items() 
                         if config['polymarket_yes_asset_id'] == asset_id or 
                            config['polymarket_no_asset_id'] == asset_id]
        
        for market_pair in relevant_pairs:
            try:
                alerts = await self.check_arbitrage_for_pair(market_pair)
                for alert in alerts:
                    await self._emit_arbitrage_alert(alert)
            except Exception as e:
                logger.error(f"Error checking arbitrage for {market_pair} after Polymarket update: {e}")
    
    async def _emit_arbitrage_alert(self, alert: ArbitrageAlert):
        """
        Emit arbitrage alert with deduplication logic.
        
        Args:
            alert: Arbitrage alert to emit
        """
        # Simple deduplication: only emit if spread has changed significantly
        last_alert = self.last_alerts.get(alert.market_pair)
        if last_alert and abs(alert.spread - last_alert.spread) < 0.005:  # 0.5% threshold
            return
        
        self.last_alerts[alert.market_pair] = alert
        
        # Stream to frontend via WebSocket
        try:
            alert_data = self.to_dict(alert)
            await publish_arbitrage_alert(alert_data)
        except Exception as e:
            logger.error(f"Error publishing arbitrage alert to WebSocket: {e}")
        
        # Also call custom callback if set
        if self.arbitrage_alert_callback:
            try:
                if asyncio.iscoroutinefunction(self.arbitrage_alert_callback):
                    await self.arbitrage_alert_callback(alert)
                else:
                    self.arbitrage_alert_callback(alert)
            except Exception as e:
                logger.error(f"Error in arbitrage alert callback: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get arbitrage manager statistics."""
        return {
            'monitored_pairs': len(self.market_pairs),
            'market_pairs': list(self.market_pairs.keys()),
            'min_spread_threshold': self.min_spread_threshold,
            'last_alerts_count': len(self.last_alerts),
            'status': 'active' if self.kalshi_processor and self.polymarket_processor else 'inactive'
        }
    
    def to_dict(self, alert: ArbitrageAlert) -> Dict[str, Any]:
        """Convert ArbitrageAlert to dictionary for JSON serialization."""
        return {
            'market_pair': alert.market_pair,
            'timestamp': alert.timestamp,
            'spread': alert.spread,
            'direction': alert.direction,
            'side': alert.side,
            'kalshi_price': alert.kalshi_price,
            'polymarket_price': alert.polymarket_price,
            'kalshi_market_id': alert.kalshi_market_id,
            'polymarket_asset_id': alert.polymarket_asset_id,
            'confidence': alert.confidence
        }