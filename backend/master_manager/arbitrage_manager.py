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

from .events.event_bus import EventBus, global_event_bus
from .arbitrage_detector import ArbitrageDetector, ArbitrageAlert

logger = logging.getLogger(__name__)

DEDUPLICATION_THRESHOLD = 0.1  # Only alert again if spread changes by more than 10%

class ArbitrageManager:
    """
    Lifecycle management for arbitrage detection between Kalshi and Polymarket.
    
    Handles market pair registration and coordinates with ArbitrageDetector for
    the actual arbitrage detection logic. Provides a clean interface for managing
    arbitrage detection across multiple market pairs.
    """
    
    def __init__(self, min_spread_threshold: float = 0.02, event_bus: Optional[EventBus] = None, 
                 kalshi_processor=None, polymarket_processor=None):
        """
        Initialize ArbitrageManager.
        
        Args:
            min_spread_threshold: Minimum spread required to trigger arbitrage alert (default: 2%)
            event_bus: EventBus instance (uses global_event_bus if None)
            kalshi_processor: Kalshi processor with get_orderbook() method (optional)
            polymarket_processor: Polymarket processor with get_orderbook() method (optional)
        """
        self.event_bus = event_bus or global_event_bus
        self.market_pairs: Dict[str, Dict[str, Any]] = {}  # market_pair -> {kalshi_sid, polymarket_yes_asset_id, polymarket_no_asset_id}
        # No deduplication state; stateless except for market_pairs
        
        # Processor references for accessing OrderbookState objects
        self.kalshi_processor = kalshi_processor
        self.polymarket_processor = polymarket_processor
        
        # Initialize the core arbitrage detector
        self.detector = ArbitrageDetector(self.event_bus, min_spread_threshold)
        
        # Subscribe to detector notifications about price updates
        self._subscribe_to_detector_events()
        
        logger.info(f"ArbitrageManager initialized with min_spread_threshold={min_spread_threshold}")
        if kalshi_processor and polymarket_processor:
            logger.info("ArbitrageManager has processor references for direct orderbook access")
    
    def set_processors(self, kalshi_processor, polymarket_processor):
        """
        Set processor references for accessing orderbook data.
        
        Args:
            kalshi_processor: Kalshi processor with get_orderbook() method
            polymarket_processor: Polymarket processor with get_orderbook() method
        """
        self.kalshi_processor = kalshi_processor
        self.polymarket_processor = polymarket_processor
        
        if kalshi_processor and polymarket_processor:
            logger.info("✅ ArbitrageManager processors set - arbitrage detection enabled")
        else:
            logger.warning("⚠️ ArbitrageManager processors partially set - some may be None")
    
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
            
            if not sid:
                logger.warning("Invalid arbitrage.kalshi_updated event data - missing sid")
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
            
            if not asset_id:
                logger.warning("Invalid arbitrage.polymarket_updated event data - missing asset_id")
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
        Gets fresh OrderbookState objects and passes them to detector for snapshot-based calculation.
        """
        if pair_name not in self.market_pairs:
            logger.warning(f"Market pair {pair_name} not registered")
            return
        
        if not self.kalshi_processor or not self.polymarket_processor:
            logger.warning(f"Cannot check arbitrage for {pair_name} - processors not available")
            return
        
        pair_config = self.market_pairs[pair_name]
        kalshi_sid = pair_config['kalshi_sid']
        poly_yes_asset_id = pair_config['polymarket_yes_asset_id']
        poly_no_asset_id = pair_config['polymarket_no_asset_id']
        
        # Get fresh OrderbookState objects from processors
        kalshi_orderbook_state = self.kalshi_processor.get_orderbook(kalshi_sid)
        poly_yes_orderbook_state = self.polymarket_processor.get_orderbook(poly_yes_asset_id)
        poly_no_orderbook_state = self.polymarket_processor.get_orderbook(poly_no_asset_id)
        
        # Validate we have orderbook states
        if not kalshi_orderbook_state:
            logger.debug(f"No Kalshi orderbook state for sid={kalshi_sid} in pair {pair_name}")
            return
        if not poly_yes_orderbook_state:
            logger.debug(f"No Polymarket YES orderbook state for asset_id={poly_yes_asset_id} in pair {pair_name}")
            return
        if not poly_no_orderbook_state:
            logger.debug(f"No Polymarket NO orderbook state for asset_id={poly_no_asset_id} in pair {pair_name}")
            return
        
        # Delegate to detector for actual arbitrage calculation using OrderbookState objects
        alerts = await self.detector.check_arbitrage_for_pair(
            pair_name, kalshi_orderbook_state, poly_yes_orderbook_state, poly_no_orderbook_state
        )
        
        # Process and publish alerts
        for alert in alerts:
            await self._process_arbitrage_alert(alert)
    
    async def _process_arbitrage_alert(self, alert: ArbitrageAlert):
        """
        Process an arbitrage alert and publish (no deduplication or state).
        """
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
            logger.info(f"Removed market pair: {market_pair}")
    
    async def check_arbitrage_for_pair(self, market_pair: str) -> List[ArbitrageAlert]:
        """
        Check for arbitrage opportunities for a specific market pair using snapshot-based detection.
        
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
        
        # Get fresh OrderbookState objects
        kalshi_orderbook_state = self.kalshi_processor.get_orderbook(kalshi_sid)
        poly_yes_orderbook_state = self.polymarket_processor.get_orderbook(poly_yes_asset_id)
        poly_no_orderbook_state = self.polymarket_processor.get_orderbook(poly_no_asset_id)
        
        # Skip if any orderbook is missing
        if not kalshi_orderbook_state:
            logger.debug(f"No Kalshi orderbook state for sid={kalshi_sid}")
            return []
        if not poly_yes_orderbook_state:
            logger.debug(f"No Polymarket YES orderbook state for asset_id={poly_yes_asset_id}")
            return []
        if not poly_no_orderbook_state:
            logger.debug(f"No Polymarket NO orderbook state for asset_id={poly_no_asset_id}")
            return []
        
        # Delegate to detector for snapshot-based arbitrage calculation
        return await self.detector.check_arbitrage_for_pair(
            market_pair, kalshi_orderbook_state, poly_yes_orderbook_state, poly_no_orderbook_state
        )
    
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
            'min_spread_threshold': 0, #not available - post refactor arb detector deals with economic logic for arb calculation
            'detector_stats': self.detector.get_stats(),
            'status': 'active'
        }
    
