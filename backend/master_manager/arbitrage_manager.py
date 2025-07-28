"""
ArbitrageManager - Lifecycle management for arbitrage detection between Kalshi and Polymarket.

This manager handles market pair registration, coordination, and delegates core arbitrage
detection logic to ArbitrageDetector. It provides a clean interface for managing
arbitrage detection across multiple market pairs.

Key Features:
- Market pair lifecycle management (add/remove pairs)
- Coordination between ArbitrageDetector and market pairs
- Statistics and monitoring
- EventBus integration for notification
"""

import logging
import asyncio
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, asdict
from datetime import datetime

from .events.event_bus import EventBus, global_event_bus
from .arbitrage_detector import ArbitrageDetector, ArbitrageAlert

logger = logging.getLogger(__name__)

DEDUPLICATION_THRESHOLD = 0.1  # Only alert again if spread changes by more than 10%

@dataclass
class ArbitrageSettings:
    """
    Modular arbitrage settings that can be updated dynamically via EventBus.
    
    This dataclass contains all configurable parameters for arbitrage detection.
    New settings can be easily added without breaking existing functionality.
    
    Current settings:
        min_spread_threshold (float): Minimum spread required to trigger arbitrage alert
        min_trade_size (float): Minimum trade size threshold for execution
        
    Future extensible settings examples:
        max_trade_size (float): Maximum trade size limit
        max_alerts_per_minute (int): Rate limiting for alerts
        enabled_platforms (List[str]): Which platforms to monitor
        confidence_threshold (float): Minimum confidence level required
        max_spread_age_seconds (int): How long spreads are valid
        enable_notifications (bool): Whether to send notifications
        blacklisted_markets (List[str]): Markets to exclude from monitoring
    """
    min_spread_threshold: float = 0.05
    min_trade_size: float = 10.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert settings to dictionary for serialization."""
        return asdict(self)
    
    @classmethod 
    def from_dict(cls, data: Dict[str, Any]) -> 'ArbitrageSettings':
        """Create ArbitrageSettings from dictionary."""
        # Filter only valid fields to handle partial updates
        valid_fields = {k: v for k, v in data.items() if hasattr(cls, k)}
        return cls(**valid_fields)
    
    def update_from_dict(self, data: Dict[str, Any]) -> 'ArbitrageSettings':
        """Update current settings with new values, returning new instance."""
        current_dict = self.to_dict()
        # Only update fields that exist in the dataclass
        valid_updates = {k: v for k, v in data.items() if hasattr(self, k)}
        current_dict.update(valid_updates)
        return ArbitrageSettings.from_dict(current_dict)
    
    def validate(self) -> List[str]:
        """Validate settings and return list of error messages."""
        errors = []
        
        if self.min_spread_threshold < 0:
            errors.append("min_spread_threshold must be non-negative")
        if self.min_spread_threshold > 1:
            errors.append("min_spread_threshold must be <= 1.0 (100%)")
            
        if self.min_trade_size < 0:
            errors.append("min_trade_size must be non-negative")
            
        return errors

class ArbitrageManager:
    """
    Lifecycle management for arbitrage detection between Kalshi and Polymarket.
    
    Handles market pair registration and coordinates with ArbitrageDetector for
    the actual arbitrage detection logic. Provides a clean interface for managing
    arbitrage detection across multiple market pairs.
    """
    
    def __init__(self, min_spread_threshold: float = 0.05, min_trade_size: float = 10.0, 
                 event_bus: Optional[EventBus] = None, kalshi_processor=None, polymarket_processor=None):
        """
        Initialize ArbitrageManager with modular settings system.
        
        Args:
            min_spread_threshold: Minimum spread required to trigger arbitrage alert (default: 5%)
            min_trade_size: Minimum trade size threshold for execution (default: 10.0)
            event_bus: EventBus instance (uses global_event_bus if None)
            kalshi_processor: Kalshi processor with get_orderbook() method (optional)
            polymarket_processor: Polymarket processor with get_orderbook() method (optional)
        """
        self.event_bus = event_bus or global_event_bus
        
        # Initialize arbitrage settings with validation
        self.settings = ArbitrageSettings(
            min_spread_threshold=min_spread_threshold,
            min_trade_size=min_trade_size
        )
        
        # Validate initial settings
        validation_errors = self.settings.validate()
        if validation_errors:
            logger.error(f"Invalid initial arbitrage settings: {validation_errors}")
            raise ValueError(f"Invalid arbitrage settings: {', '.join(validation_errors)}")
        
        self.market_pairs: Dict[str, Dict[str, Any]] = {}  # market_pair -> {kalshi_ticker, polymarket_yes_asset_id, polymarket_no_asset_id}
        
        # Processor references for accessing OrderbookState objects
        self.kalshi_processor = kalshi_processor
        self.polymarket_processor = polymarket_processor
        
        # Initialize the core arbitrage detector
        self.detector = ArbitrageDetector(self.event_bus, self.settings.min_spread_threshold, self.settings.min_trade_size)
        
        # Subscribe to detector notifications about price updates
        self._subscribe_to_detector_events()
        
        logger.info(f"ArbitrageManager initialized with settings: {self.settings.to_dict()}")
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
        """Subscribe to ArbitrageDetector update notifications and settings changes."""
        # Subscribe to notifications from detector about platform updates
        self.event_bus.subscribe('arbitrage.kalshi_updated', self._handle_kalshi_updated)
        self.event_bus.subscribe('arbitrage.polymarket_updated', self._handle_polymarket_updated)
        
        # Subscribe to arbitrage settings changes from frontend
        self.event_bus.subscribe('arbitrage.settings_changed', self._handle_settings_changed)
        
        logger.info("ArbitrageManager subscribed to detector update events and settings changes")
    
    async def _handle_kalshi_updated(self, event_data: Dict[str, Any]):
        """
        Handle notifications from ArbitrageDetector that Kalshi has updated.
        Find relevant market pairs and trigger arbitrage checks.
        """
        try:
            ticker = event_data.get('ticker')
            
            if not ticker:
                logger.warning("Invalid arbitrage.kalshi_updated event data - missing ticker")
                return
            
            # Find all market pairs that involve this Kalshi market
            relevant_pairs = [
                pair_name for pair_name, config in self.market_pairs.items()
                if config.get('kalshi_ticker') == ticker
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
    
    async def _handle_settings_changed(self, event_data: Dict[str, Any]):
        """
        Handle arbitrage settings changes from frontend via EventBus.
        
        Event data format:
        {
            'settings': {
                'min_spread_threshold': 0.03,
                'min_trade_size': 25.0,
                # ... future settings
            },
            'source': 'frontend_user' | 'admin' | 'api',
            'timestamp': '2025-01-15T10:30:00Z',
            'user_id': 'optional_user_id'
        }
        
        Args:
            event_data: Event data containing new settings and metadata
        """
        try:
            new_settings_data = event_data.get('settings', {})
            source = event_data.get('source', 'unknown')
            correlation_id = event_data.get('correlation_id')  # Extract correlation ID for response tracking
            
            if not new_settings_data:
                logger.warning("Invalid arbitrage.settings_changed event data - missing 'settings'")
                return
            
            # Create new settings instance from current settings + updates
            updated_settings = self.settings.update_from_dict(new_settings_data)
            
            # Validate new settings
            validation_errors = updated_settings.validate()
            if validation_errors:
                logger.error(f"Invalid arbitrage settings update from {source}: {validation_errors}")
                # Publish validation error event for frontend notification
                await self.event_bus.publish('arbitrage.settings_error', {
                    'errors': validation_errors,
                    'rejected_settings': new_settings_data,
                    'current_settings': self.settings.to_dict(),
                    'correlation_id': correlation_id,  # Pass through correlation ID
                    'source': source,
                    'timestamp': event_data.get('timestamp')
                })
                return
            
            # Store old settings for logging
            old_settings = self.settings.to_dict()
            
            # Atomic settings update: Update detector first, then swap settings reference
            # This ensures detector and settings are always consistent
            if old_settings['min_spread_threshold'] != updated_settings.min_spread_threshold:
                # Update detector before settings swap to maintain consistency
                self.detector.calculator.min_spread_threshold = updated_settings.min_spread_threshold
                logger.info(f"🎯 Updated ArbitrageDetector min_spread_threshold: {old_settings['min_spread_threshold']:.3f} → {updated_settings.min_spread_threshold:.3f}")
            
            if old_settings['min_trade_size'] != updated_settings.min_trade_size:
                # Update detector min_trade_size for filtering
                self.detector.calculator.min_trade_size = updated_settings.min_trade_size
                logger.info(f"💰 Updated ArbitrageDetector min_trade_size: {old_settings['min_trade_size']:.1f} → {updated_settings.min_trade_size:.1f}")
            
            # Atomic settings swap (single reference assignment is atomic in Python)
            self.settings = updated_settings
            
            logger.info(f"✅ Arbitrage settings updated from {source}")
            logger.info(f"   Old: {old_settings}")
            logger.info(f"   New: {self.settings.to_dict()}")
            
            # Publish success confirmation for frontend
            await self.event_bus.publish('arbitrage.settings_updated', {
                'old_settings': old_settings,
                'new_settings': self.settings.to_dict(),
                'changed_fields': [k for k in new_settings_data.keys() if k in self.settings.to_dict()],
                'correlation_id': correlation_id,  # Pass through correlation ID
                'source': source,
                'timestamp': event_data.get('timestamp')
            })
            
        except Exception as e:
            logger.error(f"Error handling arbitrage settings change: {e}")
            # Publish error event for frontend notification
            await self.event_bus.publish('arbitrage.settings_error', {
                'errors': [f"Internal error: {str(e)}"],
                'rejected_settings': event_data.get('settings', {}),
                'current_settings': self.settings.to_dict(),
                'correlation_id': correlation_id,  # Pass through correlation ID
                'source': event_data.get('source', 'unknown'),
                'timestamp': event_data.get('timestamp')
            })
    
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
        kalshi_ticker = pair_config['kalshi_ticker']
        poly_yes_asset_id = pair_config['polymarket_yes_asset_id']
        poly_no_asset_id = pair_config['polymarket_no_asset_id']
        
        # Get fresh OrderbookState objects from processors
        kalshi_orderbook_state = self.kalshi_processor.get_orderbook(kalshi_ticker)
        poly_yes_orderbook_state = self.polymarket_processor.get_orderbook(poly_yes_asset_id)
        poly_no_orderbook_state = self.polymarket_processor.get_orderbook(poly_no_asset_id)
        
        # Validate we have orderbook states
        if not kalshi_orderbook_state:
            logger.debug(f"No Kalshi orderbook state for ticker={kalshi_ticker} in pair {pair_name}")
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
    
    def add_market_pair(self, market_pair: str, kalshi_ticker: str, polymarket_yes_asset_id: str, polymarket_no_asset_id: str):
        """
        Add a market pair for arbitrage monitoring (atomic operation).
        
        Args:
            market_pair: Human-readable market pair identifier
            kalshi_ticker: Kalshi market ticker
            polymarket_yes_asset_id: Polymarket YES asset ID
            polymarket_no_asset_id: Polymarket NO asset ID
        """
        try:
            # Create atomic copy of current market pairs
            new_market_pairs = self.market_pairs.copy()
            
            # Check if already exists
            was_update = market_pair in new_market_pairs
            
            # Add to copy (not original state)
            new_market_pairs[market_pair] = {
                'kalshi_ticker': kalshi_ticker,
                'polymarket_yes_asset_id': polymarket_yes_asset_id,
                'polymarket_no_asset_id': polymarket_no_asset_id
            }
            
            # Atomic swap: replace entire dictionary in one operation
            self.market_pairs = new_market_pairs
            
            action = "Updated" if was_update else "Added"
            logger.info(f"🔗 ARBITRAGE MANAGER: {action} market pair: {market_pair} -> Kalshi:{kalshi_ticker}, Poly:{polymarket_yes_asset_id}/{polymarket_no_asset_id}")
            logger.info(f"🔗 ARBITRAGE MANAGER: Total market pairs: {len(self.market_pairs)}")
            logger.debug(f"🔗 ARBITRAGE MANAGER: Active pairs: {list(self.market_pairs.keys())}")
            
        except Exception as e:
            logger.error(f"🔗 ARBITRAGE MANAGER: Error adding market pair {market_pair}: {e}")
            # State remains unchanged due to atomic operation failure
    
    def remove_market_pair(self, market_pair: str):
        """
        Remove a market pair from monitoring (atomic operation).
        
        Uses atomic copy-swap pattern to prevent race conditions during concurrent access.
        
        Args:
            market_pair: Market pair identifier to remove
            
        Returns:
            bool: True if pair was found and removed, False if not found
        """
        try:
            # Create atomic copy of current market pairs
            new_market_pairs = self.market_pairs.copy()
            
            # Check if exists and remove from copy (not original state)
            if market_pair in new_market_pairs:
                removed_config = new_market_pairs.pop(market_pair)
                
                # Atomic swap: replace entire dictionary in one operation
                self.market_pairs = new_market_pairs
                
                logger.info(f"🔗 ARBITRAGE MANAGER: Removed market pair: {market_pair}")
                logger.info(f"🔗 ARBITRAGE MANAGER: Removed config: Kalshi:{removed_config['kalshi_ticker']}, Poly:{removed_config['polymarket_yes_asset_id']}/{removed_config['polymarket_no_asset_id']}")
                logger.info(f"🔗 ARBITRAGE MANAGER: Remaining market pairs: {len(self.market_pairs)}")
                logger.debug(f"🔗 ARBITRAGE MANAGER: Active pairs: {list(self.market_pairs.keys())}")
                return True
            else:
                logger.warning(f"🔗 ARBITRAGE MANAGER: Market pair {market_pair} not found for removal")
                return False
                
        except Exception as e:
            logger.error(f"🔗 ARBITRAGE MANAGER: Error removing market pair {market_pair}: {e}")
            # State remains unchanged due to atomic operation failure
            return False
    
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
        kalshi_ticker = pair_config['kalshi_ticker']
        poly_yes_asset_id = pair_config['polymarket_yes_asset_id']
        poly_no_asset_id = pair_config['polymarket_no_asset_id']
        
        # Get fresh OrderbookState objects
        kalshi_orderbook_state = self.kalshi_processor.get_orderbook(kalshi_ticker)
        poly_yes_orderbook_state = self.polymarket_processor.get_orderbook(poly_yes_asset_id)
        poly_no_orderbook_state = self.polymarket_processor.get_orderbook(poly_no_asset_id)
        
        # Skip if any orderbook is missing
        if not kalshi_orderbook_state:
            logger.debug(f"No Kalshi orderbook state for ticker={kalshi_ticker}")
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
        logger.debug(f"🔗 ARBITRAGE MANAGER: Checking arbitrage for {len(self.market_pairs)} pairs: {list(self.market_pairs.keys())}")
        
        all_alerts = []
        
        for market_pair in self.market_pairs.keys():
            try:
                alerts = await self.check_arbitrage_for_pair(market_pair)
                all_alerts.extend(alerts)
                if alerts:
                    logger.debug(f"🔗 ARBITRAGE MANAGER: Found {len(alerts)} alerts for pair {market_pair}")
            except Exception as e:
                logger.error(f"🔗 ARBITRAGE MANAGER: Error checking arbitrage for pair {market_pair}: {e}")
        
        logger.debug(f"🔗 ARBITRAGE MANAGER: Total alerts found: {len(all_alerts)}")
        return all_alerts
    
    def get_settings(self) -> Dict[str, Any]:
        """Get current arbitrage settings."""
        return self.settings.to_dict()
    
    async def update_settings(self, new_settings: Dict[str, Any], source: str = 'api') -> bool:
        """
        Public method to update arbitrage settings programmatically.
        
        Args:
            new_settings: Dictionary with setting updates
            source: Source of the update (for logging)
            
        Returns:
            bool: True if settings were updated successfully, False otherwise
        """
        try:
            # Trigger settings change event (will be handled by our event handler)
            await self.event_bus.publish('arbitrage.settings_changed', {
                'settings': new_settings,
                'source': source,
                'timestamp': datetime.now().isoformat()
            })
            return True
        except Exception as e:
            logger.error(f"Error updating settings programmatically: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get arbitrage manager statistics including current settings."""
        return {
            'monitored_pairs': len(self.market_pairs),
            'market_pairs': list(self.market_pairs.keys()),
            'settings': self.settings.to_dict(),
            'detector_stats': self.detector.get_stats(),
            'status': 'active'
        }
    
    
