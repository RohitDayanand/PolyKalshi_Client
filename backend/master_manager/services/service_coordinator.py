"""
ServiceCoordinator - Manages cross-cutting services through event-driven architecture

Coordinates services that span multiple platforms like arbitrage detection,
ticker publishing coordination, and alert management.
"""
import logging
from typing import Dict, Any, Optional

from ..events.event_bus import EventBus
from ..arbitrage_manager import ArbitrageManager

logger = logging.getLogger(__name__)

class ServiceCoordinator:
    """
    Coordinates cross-cutting services that operate across multiple platforms.
    
    Features:
    - Event-driven service integration
    - Arbitrage detection across platforms
    - Alert management and forwarding
    - Service lifecycle management
    """
    
    def __init__(self, event_bus: EventBus, arbitrage_service: Optional[ArbitrageManager] = None):
        """
        Initialize the service coordinator.
        
        Args:
            event_bus: Event bus for cross-component communication
            arbitrage_service: Optional arbitrage manager (will create if None)
        """
        self.event_bus = event_bus
        
        # Initialize arbitrage service
        if arbitrage_service:
            self.arbitrage_service = arbitrage_service
        else:
            self.arbitrage_service = ArbitrageManager(min_spread_threshold=0.02)
        
        # Service state tracking
        self.services_started = False
        
        # Statistics
        self.stats = {
            "arbitrage_alerts": 0,
            "kalshi_orderbook_updates": 0,
            "polymarket_orderbook_updates": 0,
            "service_errors": 0
        }
        
        # Set up event subscriptions
        self._setup_event_subscriptions()
        
        logger.info("ServiceCoordinator initialized")
    
    def _setup_event_subscriptions(self):
        """Set up event subscriptions for cross-cutting services."""
        
        # Arbitrage monitoring - subscribe to orderbook updates from both platforms
        self.event_bus.subscribe('kalshi.orderbook_update', self._handle_kalshi_orderbook_update)
        self.event_bus.subscribe('polymarket.orderbook_update', self._handle_polymarket_orderbook_update)
        
        # Error handling
        self.event_bus.subscribe('kalshi.error', self._handle_platform_error)
        self.event_bus.subscribe('polymarket.error', self._handle_platform_error)
        
        # Set up arbitrage alert callback
        self.arbitrage_service.set_arbitrage_alert_callback(self._handle_arbitrage_alert)
        
        logger.info("ServiceCoordinator event subscriptions set up")
    
    async def start_services(self, kalshi_processor=None, polymarket_processor=None):
        """
        Start cross-cutting services.
        
        Args:
            kalshi_processor: Kalshi message processor for arbitrage
            polymarket_processor: Polymarket message processor for arbitrage
        """
        if self.services_started:
            logger.info("ServiceCoordinator services already started")
            return
        
        try:
            # Set up arbitrage service with processors if provided
            if kalshi_processor and polymarket_processor:
                self.arbitrage_service.set_processors(kalshi_processor, polymarket_processor)
                logger.info("Arbitrage service configured with processors")
            else:
                logger.warning("No processors provided to ServiceCoordinator - arbitrage may not function")
            
            self.services_started = True
            logger.info("✅ ServiceCoordinator services started successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to start ServiceCoordinator services: {e}")
            raise
    
    async def stop_services(self):
        """Stop all cross-cutting services."""
        try:
            # Note: ArbitrageManager doesn't have explicit stop method
            # but we can reset its state if needed
            
            self.services_started = False
            logger.info("ServiceCoordinator services stopped")
            
        except Exception as e:
            logger.error(f"Error stopping ServiceCoordinator services: {e}")
    
    async def _handle_kalshi_orderbook_update(self, event_data: Dict[str, Any]):
        """Handle Kalshi orderbook updates for arbitrage detection."""
        try:
            sid = event_data.get('sid')
            orderbook_state = event_data.get('orderbook_state')
            
            if sid is not None and orderbook_state:
                await self.arbitrage_service.handle_kalshi_orderbook_update(sid, orderbook_state)
                self.stats["kalshi_orderbook_updates"] += 1
                logger.debug(f"Processed Kalshi orderbook update for sid={sid}")
            else:
                logger.warning(f"Invalid Kalshi orderbook update event: {event_data}")
                
        except Exception as e:
            self.stats["service_errors"] += 1
            logger.error(f"Error handling Kalshi orderbook update: {e}")
    
    async def _handle_polymarket_orderbook_update(self, event_data: Dict[str, Any]):
        """Handle Polymarket orderbook updates for arbitrage detection."""
        try:
            asset_id = event_data.get('asset_id')
            orderbook_state = event_data.get('orderbook_state')
            
            if asset_id and orderbook_state:
                await self.arbitrage_service.handle_polymarket_orderbook_update(asset_id, orderbook_state)
                self.stats["polymarket_orderbook_updates"] += 1
                logger.debug(f"Processed Polymarket orderbook update for asset_id={asset_id}")
            else:
                logger.warning(f"Invalid Polymarket orderbook update event: {event_data}")
                
        except Exception as e:
            self.stats["service_errors"] += 1
            logger.error(f"Error handling Polymarket orderbook update: {e}")
    
    async def _handle_platform_error(self, event_data: Dict[str, Any]):
        """Handle platform errors for logging and monitoring."""
        platform = event_data.get('platform', 'unknown')
        error_info = event_data.get('error_info', {})
        
        logger.error(f"Platform error from {platform}: {error_info}")
        self.stats["service_errors"] += 1
        
        # Could publish error events to external monitoring systems here
        await self.event_bus.publish('service.platform_error', {
            'platform': platform,
            'error_info': error_info,
            'coordinator': 'ServiceCoordinator'
        })
    
    async def _handle_arbitrage_alert(self, alert_data: Dict[str, Any]):
        """Handle arbitrage alerts and forward them to WebSocket clients."""
        try:
            logger.info(f"Arbitrage alert: {alert_data}")
            self.stats["arbitrage_alerts"] += 1
            
            # Publish arbitrage alert through event bus
            await self.event_bus.publish('arbitrage.alert', {
                'type': 'arbitrage_alert',
                **alert_data
            })
            
            # Also publish to WebSocket clients directly (for compatibility)
            # This will be handled by the coordinator that subscribes to arbitrage.alert
            
        except Exception as e:
            self.stats["service_errors"] += 1
            logger.error(f"Error handling arbitrage alert: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get service coordinator statistics."""
        arbitrage_stats = self.arbitrage_service.get_stats() if self.arbitrage_service else {}
        
        return {
            "services_started": self.services_started,
            "coordinator_stats": self.stats,
            "arbitrage_stats": arbitrage_stats,
            "event_bus_stats": self.event_bus.get_stats()
        }
    
    # Arbitrage service delegation methods (for backward compatibility)
    def add_arbitrage_market_pair(self, market_pair: str, kalshi_sid: int, polymarket_yes_asset_id: str, polymarket_no_asset_id: str):
        """Add a market pair for arbitrage monitoring."""
        return self.arbitrage_service.add_market_pair(market_pair, kalshi_sid, polymarket_yes_asset_id, polymarket_no_asset_id)
    
    def remove_arbitrage_market_pair(self, market_pair: str):
        """Remove a market pair from arbitrage monitoring."""
        return self.arbitrage_service.remove_market_pair(market_pair)
    
    async def check_arbitrage_for_pair(self, market_pair: str):
        """Check arbitrage opportunities for a specific market pair."""
        return await self.arbitrage_service.check_arbitrage_for_pair(market_pair)
    
    async def check_all_arbitrage_opportunities(self):
        """Check arbitrage opportunities for all registered market pairs."""
        return await self.arbitrage_service.check_all_arbitrage_opportunities()
    
    def get_arbitrage_stats(self):
        """Get arbitrage manager statistics."""
        return self.arbitrage_service.get_stats()