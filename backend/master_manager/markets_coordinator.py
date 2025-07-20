"""
MarketsCoordinator - Lightweight coordinator replacing the monolithic MarketsManager

Provides a thin orchestration layer over platform-specific managers and services
while maintaining backward compatibility with the existing interface.
"""
import logging
from typing import Dict, Any, Optional

from backend.master_manager.events.event_bus import EventBus, global_event_bus
from backend.master_manager.platforms.kalshi_platform_manager import KalshiPlatformManager
from backend.master_manager.platforms.polymarket_platform_manager import PolymarketPlatformManager
from backend.master_manager.services.service_coordinator import ServiceCoordinator

logger = logging.getLogger(__name__)

class MarketsCoordinator:
    """
    Lightweight coordinator for managing multiple market platforms.
    
    Replaces the monolithic MarketsManager with a clean, event-driven architecture.
    
    Features:
    - Platform-agnostic market connection management
    - Event-driven cross-platform coordination
    - Backward-compatible interface
    - Centralized service coordination
    """
    
    def __init__(self, event_bus: Optional[EventBus] = None):
        """
        Initialize the markets coordinator.
        
        Args:
            event_bus: Optional event bus (uses global if not provided)
        """
        self.event_bus = event_bus or global_event_bus
        
        # Initialize platform managers
        self.kalshi_platform = KalshiPlatformManager(self.event_bus)
        self.polymarket_platform = PolymarketPlatformManager(self.event_bus)
        
        # Initialize service coordinator
        self.service_coordinator = ServiceCoordinator(self.event_bus)
        
        # Track if async components are started
        self._async_started = False
        
        # Set up global event handlers for WebSocket publishing
        self._setup_global_event_handlers()
        
        logger.info("MarketsCoordinator initialized with event-driven architecture")
    
    def _setup_global_event_handlers(self):
        """Set up global event handlers for WebSocket publishing and logging."""
        
        # Handle arbitrage alerts by publishing to WebSocket clients
        self.event_bus.subscribe('arbitrage.alert', self._publish_arbitrage_alert)
        
        # Log platform connection events
        self.event_bus.subscribe('kalshi.connection_status', self._log_connection_status)
        self.event_bus.subscribe('polymarket.connection_status', self._log_connection_status)
        
        # Log platform errors
        self.event_bus.subscribe('kalshi.error', self._log_platform_error)
        self.event_bus.subscribe('polymarket.error', self._log_platform_error)
        
        logger.info("Global event handlers set up")
    
    async def _publish_arbitrage_alert(self, alert_data: Dict[str, Any]):
        """Publish arbitrage alert to WebSocket clients."""
        try:
            # Import here to avoid circular dependencies
            from ..websocket_server import publish_arbitrage_alert
            await publish_arbitrage_alert(alert_data)
            logger.info(f"Published arbitrage alert to WebSocket clients: {alert_data.get('market_pair')}")
        except Exception as e:
            logger.error(f"Failed to publish arbitrage alert to WebSocket: {e}")
    
    async def _log_connection_status(self, event_data: Dict[str, Any]):
        """Log connection status changes."""
        platform = event_data.get('platform', 'unknown')
        client_id = event_data.get('client_id', 'unknown')
        connected = event_data.get('connected', False)
        status = "connected" if connected else "disconnected"
        
        logger.info(f"Connection status: {platform} client {client_id} {status}")
    
    async def _log_platform_error(self, event_data: Dict[str, Any]):
        """Log platform errors."""
        platform = event_data.get('platform', 'unknown')
        error_info = event_data.get('error_info', {})
        
        logger.error(f"Platform error from {platform}: {error_info}")
    
    async def start_async_components(self):
        """Start async components that require a running event loop."""
        if self._async_started:
            logger.info("MarketsCoordinator async components already started")
            return
        
        try:
            # Start platform managers
            await self.kalshi_platform.start_async_components()
            await self.polymarket_platform.start_async_components()
            
            # Start service coordinator
            await self.service_coordinator.start_services()
            
            self._async_started = True
            logger.info("✅ MarketsCoordinator async components started successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to start MarketsCoordinator async components: {e}")
            raise
    
    async def connect(self, market_id: str, platform: str = "polymarket") -> bool:
        """
        Connect to a specific market using platform and market ID.
        
        Args:
            market_id: Market identifier (platform-specific format)
            platform: "polymarket" or "kalshi"
            
        Returns:
            bool: True if connection successful
        """
        # Ensure async components are started
        if not self._async_started:
            await self.start_async_components()
        
        try:
            if platform.lower() == "polymarket":
                return await self.polymarket_platform.connect_market(market_id)
            elif platform.lower() == "kalshi":
                return await self.kalshi_platform.connect_market(market_id)
            else:
                logger.error(f"Unsupported platform: {platform}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to connect {platform}:{market_id} - {e}")
            return False
    
    async def disconnect(self, market_id: str, platform: str = "polymarket") -> bool:
        """
        Disconnect from a specific market.
        
        Args:
            market_id: Market identifier to disconnect
            platform: "polymarket" or "kalshi"
            
        Returns:
            bool: True if disconnection successful
        """
        try:
            if platform.lower() == "polymarket":
                return await self.polymarket_platform.disconnect_market(market_id)
            elif platform.lower() == "kalshi":
                return await self.kalshi_platform.disconnect_market(market_id)
            else:
                logger.error(f"Unsupported platform: {platform}")
                return False
                
        except Exception as e:
            logger.error(f"Error disconnecting {platform}:{market_id} - {e}")
            return False
    
    async def disconnect_all(self) -> None:
        """Disconnect all clients and stop processing."""
        logger.info("Disconnecting all clients...")
        
        try:
            # Stop service coordinator
            await self.service_coordinator.stop_services()
            
            # Disconnect all platform clients
            await self.kalshi_platform.disconnect_all()
            await self.polymarket_platform.disconnect_all()
            
            self._async_started = False
            logger.info("All clients disconnected")
            
        except Exception as e:
            logger.error(f"Error during disconnect_all: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get status of all connections and the coordinator."""
        return {
            "async_started": self._async_started,
            "kalshi_platform": self.kalshi_platform.get_stats(),
            "polymarket_platform": self.polymarket_platform.get_stats(),
            "service_coordinator": self.service_coordinator.get_stats(),
            "event_bus": self.event_bus.get_stats(),
            "total_connections": (
                self.kalshi_platform.get_stats().get("total_connections", 0) +
                self.polymarket_platform.get_stats().get("total_connections", 0)
            )
        }
    
    # Legacy interface methods for backward compatibility
    
    # Kalshi-specific methods
    def get_kalshi_orderbook(self, sid: int):
        """Get current Kalshi orderbook state for a market."""
        return self.kalshi_platform.get_orderbook(sid)
    
    def get_all_kalshi_orderbooks(self):
        """Get all current Kalshi orderbook states."""
        return self.kalshi_platform.get_all_orderbooks()
    
    def get_kalshi_summary_stats(self, sid: int):
        """Get yes/no bid/ask/volume summary for a Kalshi market.""" 
        return self.kalshi_platform.get_summary_stats(sid)
    
    def get_all_kalshi_summary_stats(self):
        """Get summary stats for all active Kalshi markets."""
        return self.kalshi_platform.get_all_summary_stats()
    
    def force_publish_kalshi_market(self, sid: int) -> bool:
        """Force immediate publication of a Kalshi market (bypasses rate limiting)."""
        return self.kalshi_platform.force_publish_market(sid)
    
    async def restart_kalshi_ticker_publisher(self):
        """Restart the Kalshi ticker publisher."""
        await self.kalshi_platform.restart_ticker_publisher()
    
    # Polymarket-specific methods
    def get_polymarket_orderbook(self, asset_id: str):
        """Get current Polymarket orderbook state for an asset."""
        return self.polymarket_platform.get_orderbook(asset_id)
    
    def get_all_polymarket_orderbooks(self):
        """Get all current Polymarket orderbook states."""
        return self.polymarket_platform.get_all_orderbooks()
    
    def get_polymarket_market_summary(self, asset_id: str):
        """Get bid/ask/volume summary for a Polymarket asset."""
        return self.polymarket_platform.get_market_summary(asset_id)
    
    def get_all_polymarket_market_summaries(self):
        """Get market summaries for all active Polymarket assets."""
        return self.polymarket_platform.get_all_market_summaries()
    
    def force_publish_polymarket_asset(self, asset_id: str) -> bool:
        """Force immediate publication of a Polymarket asset (bypasses rate limiting)."""
        return self.polymarket_platform.force_publish_asset(asset_id)
    
    async def restart_polymarket_ticker_publisher(self):
        """Restart the Polymarket ticker publisher."""
        await self.polymarket_platform.restart_ticker_publisher()
    
    # Arbitrage Management Methods (delegated to service coordinator)
    def add_arbitrage_market_pair(self, market_pair: str, kalshi_sid: int, polymarket_yes_asset_id: str, polymarket_no_asset_id: str):
        """Add a market pair for arbitrage monitoring."""
        return self.service_coordinator.add_arbitrage_market_pair(market_pair, kalshi_sid, polymarket_yes_asset_id, polymarket_no_asset_id)
    
    def remove_arbitrage_market_pair(self, market_pair: str):
        """Remove a market pair from arbitrage monitoring."""
        return self.service_coordinator.remove_arbitrage_market_pair(market_pair)
    
    def set_arbitrage_alert_callback(self, callback):
        """Set callback for arbitrage alert notifications."""
        # Note: In the new architecture, callbacks are handled via events
        # This method is kept for compatibility but doesn't do anything
        # since alerts are automatically published via events
        _ = callback  # Mark as used to avoid warning
        logger.warning("set_arbitrage_alert_callback is deprecated - alerts are published via events")
        return True
    
    async def check_arbitrage_for_pair(self, market_pair: str):
        """Check arbitrage opportunities for a specific market pair."""
        return await self.service_coordinator.check_arbitrage_for_pair(market_pair)
    
    async def check_all_arbitrage_opportunities(self):
        """Check arbitrage opportunities for all registered market pairs."""
        return await self.service_coordinator.check_all_arbitrage_opportunities()
    
    def get_arbitrage_stats(self):
        """Get arbitrage manager statistics."""
        return self.service_coordinator.get_arbitrage_stats()

# Convenience function for quick setup (backward compatibility)
def create_markets_manager(config_path: Optional[str] = None) -> MarketsCoordinator:
    """
    Create a markets coordinator (replaces MarketsManager).
    
    Args:
        config_path: Path to JSON subscription configuration file (ignored in new architecture)
        
    Returns:
        MarketsCoordinator: Configured coordinator instance
    """
    if config_path:
        logger.warning(f"config_path parameter ({config_path}) is ignored in new architecture")
    
    return MarketsCoordinator()