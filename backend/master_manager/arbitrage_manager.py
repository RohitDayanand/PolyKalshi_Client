"""
ArbitrageManager - Lifecycle management for arbitrage detection between Kalshi and Polymarket.

This manager handles market pair registration, coordination, and delegates core arbitrage
detection logic to ArbitrageDetector. It provides a clean interface for managing
arbitrage detection across multiple market pairs.

Key Features:
- Market pair lifecycle management (add/remove pairs)
- Coordination between ArbitrageDetector and market pairs
- Statistics and monitoring
- EventBus integration for notifications
"""

import logging
import asyncio
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime

from .events.event_bus import EventBus, global_event_bus
from .arbitrage_detector import ArbitrageDetector, ArbitrageAlert

logger = logging.getLogger(__name__)

class ArbitrageManager:
    """
    Lifecycle management for arbitrage detection between Kalshi and Polymarket.
    
    Handles market pair registration and coordinates with ArbitrageDetector for
    the actual arbitrage detection logic. Provides a clean interface for managing
    arbitrage detection across multiple market pairs.
    """
    
    def __init__(self, min_spread_threshold: float = 0.02, event_bus: Optional[EventBus] = None):
        """
        Initialize ArbitrageManager.
        
        Args:
            min_spread_threshold: Minimum spread required to trigger arbitrage alert (default: 2%)
            event_bus: EventBus instance (uses global_event_bus if None)
        """
        self.event_bus = event_bus or global_event_bus
        self.market_pairs: Dict[str, Dict[str, Any]] = {}  # market_pair -> {kalshi_sid, polymarket_yes_asset_id, polymarket_no_asset_id}
        self.last_alerts: Dict[str, ArbitrageAlert] = {}  # market_pair -> last_alert (for deduplication)
        
        # Initialize the core arbitrage detector
        self.detector = ArbitrageDetector(self.event_bus, min_spread_threshold)
        
        # Subscribe to detector notifications about price updates
        self._subscribe_to_detector_events()
        
        logger.info(f"ArbitrageManager initialized with min_spread_threshold={min_spread_threshold}")
    
    def _subscribe_to_detector_events(self):
        """Subscribe to ArbitrageDetector update notifications."""
        # Subscribe to notifications from detector about platform updates
        self.event_bus.subscribe('arbitrage.kalshi_updated', self._handle_kalshi_updated)
        self.event_bus.subscribe('arbitrage.polymarket_updated', self._handle_polymarket_updated)
        
        logger.info("ArbitrageManager subscribed to detector update events")
    
    async def _handle_kalshi_updated(self, event_data: Dict[str, Any]):
        """
        Handle notifications from ArbitrageDetector that Kalshi has updated.
        Find relevant market pairs and trigger arbitrage checks.
        """
        try:
            sid = event_data.get('sid')
            ticker_state = event_data.get('ticker_state')
            
            if not sid or not ticker_state:
                logger.warning("Invalid arbitrage.kalshi_updated event data")
                return
            
            # Find all market pairs that involve this Kalshi market
            relevant_pairs = [
                pair_name for pair_name, config in self.market_pairs.items()
                if config.get('kalshi_sid') == sid
            ]
            
            for pair_name in relevant_pairs:
                await self._check_arbitrage_for_pair(pair_name)
            
        except Exception as e:
            logger.error(f"Error handling Kalshi update notification: {e}")
    
    async def _handle_polymarket_updated(self, event_data: Dict[str, Any]):
        """
        Handle notifications from ArbitrageDetector that Polymarket has updated.
        Find relevant market pairs and trigger arbitrage checks.
        """
        try:
            asset_id = event_data.get('asset_id')
            orderbook_state = event_data.get('orderbook_state')
            
            if not asset_id or not orderbook_state:
                logger.warning("Invalid arbitrage.polymarket_updated event data")
                return
            
            # Find all market pairs that involve this Polymarket asset
            relevant_pairs = [
                pair_name for pair_name, config in self.market_pairs.items()
                if config.get('polymarket_yes_asset_id') == asset_id or 
                   config.get('polymarket_no_asset_id') == asset_id
            ]
            
            for pair_name in relevant_pairs:
                await self._check_arbitrage_for_pair(pair_name)
            
        except Exception as e:
            logger.error(f"Error handling Polymarket update notification: {e}")
    
    async def _check_arbitrage_for_pair(self, pair_name: str):
        """
        Check arbitrage for a specific market pair by delegating to ArbitrageDetector.
        """
        if pair_name not in self.market_pairs:
            logger.warning(f"Market pair {pair_name} not registered")
            return
        
        pair_config = self.market_pairs[pair_name]
        kalshi_sid = pair_config['kalshi_sid']
        poly_yes_asset_id = pair_config['polymarket_yes_asset_id']
        poly_no_asset_id = pair_config['polymarket_no_asset_id']
        
        # Delegate to detector for actual arbitrage calculation
        alerts = await self.detector.check_arbitrage_for_pair(
            pair_name, kalshi_sid, poly_yes_asset_id, poly_no_asset_id
        )
        
        # Process and publish alerts
        for alert in alerts:
            await self._process_arbitrage_alert(alert)
    
    async def _process_arbitrage_alert(self, alert: ArbitrageAlert):
        """
        Process an arbitrage alert (deduplication, filtering, etc.) and publish.
        """
        # Simple deduplication based on market pair and recent alerts
        pair_name = alert.market_pair
        
        # Check if we recently alerted for this pair
        if pair_name in self.last_alerts:
            last_alert = self.last_alerts[pair_name]
            # Only alert again if spread has significantly changed (>10% difference)
            if abs(alert.spread - last_alert.spread) < (last_alert.spread * 0.1):
                logger.debug(f"Skipping similar arbitrage alert for {pair_name}")
                return
        
        # Update last alert and publish
        self.last_alerts[pair_name] = alert
        await self.detector.publish_arbitrage_alert(alert)
    
    # === LIFECYCLE MANAGEMENT METHODS ===
    
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
    
    
    def get_stats(self) -> Dict[str, Any]:
        """Get arbitrage manager statistics."""
        return {
            'monitored_pairs': len(self.market_pairs),
            'market_pairs': list(self.market_pairs.keys()),
            'min_spread_threshold': self.min_spread_threshold,
            'last_alerts_count': len(self.last_alerts),
            'detector_stats': self.detector.get_stats(),
            'status': 'active'
        }
    
