"""
MarketsCoordinator - Lightweight coordinator replacing the monolithic MarketsManager

Provides a orchestration layer over platform-specific managers and services
while maintaining backward compatibility with the existing callback interface.

Maintains connection state with the websocket

"""
import logging
from typing import Dict, Any, Optional, List

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

        #check if polymarket or kalshi is connected
        self.isKalshiConnected = False
        self.isPolymarketConnected = False
        
        # Initialize service coordinator
        self.service_coordinator = ServiceCoordinator(self.event_bus)
        
        # Track if async components are started
        self._async_started = False
        
        # Simple tracking of currently connected markets (one per platform)

        self.supported_platforms = {"kalshi", "polymarket"} #toplevel definition of supported platforms 
        
        self.current_markets = {platform: None for platform in self.supported_platforms} #list comprehension for instantiation
       

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
    
    def _wire_processors(self):
        """Wire platform processors to services that need them."""
        try:
            # Get processors from platform managers
            kalshi_processor = getattr(self.kalshi_platform, 'processor', None)
            polymarket_processor = getattr(self.polymarket_platform, 'processor', None)
            
            # Debug logging to check if processors are found
            logger.debug(f"Retrieved processors: kalshi={kalshi_processor is not None}, polymarket={polymarket_processor is not None}")
            
            # Set processors in service coordinator
            self.service_coordinator.set_platform_processors(
                kalshi_processor=kalshi_processor,
                polymarket_processor=polymarket_processor
            )
            
            logger.info("✅ Processors wired to services")
            
        except Exception as e:
            logger.error(f"❌ Failed to wire processors: {e}")
    
    async def _publish_arbitrage_alert(self, alert_data: Dict[str, Any]):
        """
        Publish arbitrage alert to WebSocket clients via websocket_server module.
        
        This method is a bridge between the EventBus and the WebSocket broadcasting system.
        It receives arbitrage alerts from the ArbitrageDetector via the 'arbitrage.alert' event
        and forwards them to all connected frontend clients.
        
        Data flow:
        1. Receives alert_data containing ArbitrageOpportunity and metadata
        2. Calls publish_arbitrage_alert() from websocket_server module  
        3. websocket_server calls global_channel_manager.broadcast_arbitrage_alert()
        4. ChannelManager broadcasts to all WebSocket connections
        5. Frontend receives message with type: 'arbitrage_alert'
        
        Expected alert_data structure:
        {
            'alert': ArbitrageOpportunity,  # dataclass instance with all arbitrage details
            'market_pair': str,             # e.g., "PRES24-DJT"
            'spread': float,                # e.g., 0.035 (3.5% profit)
            'direction': str,               # "kalshi_to_polymarket" or "polymarket_to_kalshi" 
            'timestamp': str                # ISO timestamp
        }
        
        Args:
            alert_data (Dict[str, Any]): Alert data from ArbitrageDetector via EventBus
        """
        try:
            # Import here to avoid circular dependencies
            from ..websocket_server import publish_arbitrage_alert

            await publish_arbitrage_alert(alert_data)
            logger.info(f"Published arbitrage alert to WebSocket clients: {alert_data.get('market_pair')}")

            #@TODO - add in trading engine MP queue here for thread-safe concurrency
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
            
            # Wire processors for arbitrage detection (after platforms are initialized)
            self._wire_processors()
        
            
            self._async_started = True
            logger.info("✅ MarketsCoordinator async components started successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to start MarketsCoordinator async components: {e}")
            raise
    
    async def connect(self, market_id: str, platform: str) -> bool:
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
            success = False
            
            platform = platform.lower()

            if platform not in self.supported_platforms:
                logger.error(f"Unsupported platform: {platform}")
                return False
            
            if platform == "polymarket":
                success = await self.polymarket_platform.connect_market(market_id)
            elif platform == "kalshi":
                success = await self.kalshi_platform.connect_market(market_id)
            else:
                logger.error(f"Unsupported platform: {platform}")
                return False
            
            # If connection successful, track market and check for arbitrage pair
            if success:
                if platform.lower() == "kalshi":
                    # Extract ticker from market_id for Kalshi
                    ticker = market_id.removeprefix("kalshi_")

                    #call local add callback to update 

                    self.current_markets['kalshi'] = ticker
                    logger.info(f"Tracking Kalshi ticker: {ticker} (from market_id: {market_id})")
                    #self.isKalshiConnected = True #Presumptively assume that the kalshi connection exists and is living
                elif platform.lower() == "polymarket":
                    # Parse Polymarket assets from market_id
                    parsed_assets = self._parse_polymarket_assets(market_id)

                    #call local add callback to update

                    self.current_markets['polymarket'] = parsed_assets
                    logger.info(f"Tracking Polymarket assets: {parsed_assets} (from market_id: {market_id})")
                    #self.isPolymarketConnected = True #Presumptively assume that the kalshi connection exists and is living
                
                #checks and adds arbitrage pair in case we need to do that here
                self._check_and_add_arbitrage_pair()
            
            return success
                
        except Exception as e:
            logger.error(f"Failed to connect {platform}:{market_id} - {e}")
            return False
    
    async def disconnect(self, market_id: str, platform: str) -> bool:
        """
        Disconnect from a specific market.
        
        Args:
            market_id: Market identifier to disconnect
            platform: "polymarket" or "kalshi"
            
        Returns:
            bool: True if disconnection successful
        """
        try:
            success = False
            if platform.lower() == "polymarket":
                success = await self.polymarket_platform.disconnect_market(market_id)
            elif platform.lower() == "kalshi":
                success = await self.kalshi_platform.disconnect_market(market_id)
            else:
                logger.error(f"Unsupported platform: {platform}")
                return False
            
            # If disconnection successful, clear tracking and remove arbitrage pair
            if success:
                if platform.lower() == "kalshi":
                    # Log both market_id and ticker for clarity
                    old_ticker = self.current_markets['kalshi']
                    self.current_markets['kalshi'] = None
                    logger.info(f"Stopped tracking Kalshi ticker: {old_ticker} (market_id: {market_id})")
                else:
                    self.current_markets['polymarket'] = None
                    logger.info(f"Stopped tracking Polymarket market: {market_id}")
                
                self._remove_current_arbitrage_pair()
            
            return success
                
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
            
            # Clear market tracking and arbitrage pairs
            self.current_markets = {'kalshi': None, 'polymarket': None}
            self._remove_current_arbitrage_pair()
            
            self._async_started = False
            logger.info("All clients disconnected and market tracking cleared")
            
        except Exception as e:
            logger.error(f"Error during disconnect_all: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get status of all connections and the coordinator."""
        connection_state = self.get_connection_state()
        
        return {
            "async_started": self._async_started,
            "kalshi_platform": self.kalshi_platform.get_stats(),
            "polymarket_platform": self.polymarket_platform.get_stats(),
            "service_coordinator": self.service_coordinator.get_stats(),
            "event_bus": self.event_bus.get_stats(),
            "total_connections": (
                self.kalshi_platform.get_stats().get("total_connections", 0) +
                self.polymarket_platform.get_stats().get("total_connections", 0)
            ),
            "current_markets": self.current_markets,
            "connection_state": connection_state
        }
    
    # Arbitrage Management Methods (delegated to service coordinator because it is a cross market service)
    def add_arbitrage_market_pair(self, market_pair: str, kalshi_ticker: str, polymarket_yes_asset_id: str, polymarket_no_asset_id: str):
        """Add a market pair for arbitrage monitoring."""
        return self.service_coordinator.add_arbitrage_market_pair(market_pair, kalshi_ticker, polymarket_yes_asset_id, polymarket_no_asset_id)
    
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
    
    # Dynamic Arbitrage Pair Management
    def ticker_to_sid(self, ticker: str) -> int:
        """Convert ticker to SID using same logic as platform manager."""
        return hash(ticker) % 1000000
    
    def _parse_polymarket_assets(self, market_identifier: str) -> str:
        """
        Parse Polymarket assets from market identifier, similar to platform manager logic.
        
        Args:
            market_identifier: Market ID in various formats
            
        Returns:
            str: Comma-separated asset IDs
        """
        import json
        
        try:
            # Try parsing as JSON first
            if market_identifier.startswith('[') and market_identifier.endswith(']'):
                token_ids = json.loads(market_identifier)
                return ','.join(token_ids)
        except (json.JSONDecodeError, TypeError):
            pass
        
        # Fall back to comma-separated parsing
        if ',' in market_identifier:
            tokens = [token.strip() for token in market_identifier.split(',')]
            # Remove polymarket prefix from first token if present
            if tokens and tokens[0].startswith('polymarket_'):
                tokens[0] = tokens[0].removeprefix('polymarket_')
            return ','.join(tokens)
        
        # Single token ID - remove prefix
        single_token = market_identifier.removeprefix('polymarket_')
        # For single token, assume it's YES and create a placeholder NO
        # This is a fallback - normally we expect comma-separated pairs
        logger.warning(f"Single Polymarket token provided: {single_token}. Creating placeholder pair.")
        return f"{single_token},placeholder_no"
    
    def _check_and_add_arbitrage_pair(self): #make this into a check and modify arbitrage pair
        """
        Check if both platforms have connected markets and add arbitrage pair if so.
        """
        kalshi_ticker = self.current_markets['kalshi']
        polymarket_market = self.current_markets['polymarket']
        
        if kalshi_ticker and polymarket_market:
            # Parse Polymarket market (format: "yes_asset_id,no_asset_id")
            try:
                poly_parts = polymarket_market.split(',')
                if len(poly_parts) != 2:
                    logger.warning(f"Invalid Polymarket asset format: {polymarket_market}. Expected 'yes_id,no_id' but got {len(poly_parts)} parts")
                    return
                
                yes_asset_id, no_asset_id = poly_parts
                
                
                # Create a simple pair name using ticker and shortened asset ID
                yes_asset_short = yes_asset_id[:12] + "..." if len(yes_asset_id) > 12 else yes_asset_id
                pair_name = f"auto_pair_{kalshi_ticker}_{yes_asset_short}" #create a arbitrage

                self.pair_name = pair_name #currently we can only have one arb pair - this will change as we scale with client to Rust 
                
                logger.info(f"Both platforms connected - adding arbitrage pair: {pair_name} (ticker: {kalshi_ticker})")
                self.add_arbitrage_market_pair(pair_name, kalshi_ticker, yes_asset_id, no_asset_id)
                
            except (ValueError, IndexError) as e:
                logger.error(f"Error parsing market IDs for arbitrage pair: {e}")
        else:
            logger.debug(f"Waiting for both platforms - Kalshi ticker: {kalshi_ticker}, Polymarket: {polymarket_market}")
    
    def _remove_current_arbitrage_pair(self):
        """
        Remove the current arbitrage pair if one exists.
        
        Wrapped in try-catch to prevent crashes during cleanup.
        """
        try:
            # Get all current arbitrage pairs and remove them (should be only one in this simple model)
            if self.service_coordinator.arbitrage_service:
                current_pairs = list(self.service_coordinator.arbitrage_service.market_pairs.keys())

                for pair_name in current_pairs:
                    logger.info(f"Removing arbitrage pair: {pair_name}")
                    self.remove_arbitrage_market_pair(pair_name)
        except Exception as e:
            logger.error(f"Error removing arbitrage pairs during cleanup: {e}")
            # Continue execution - don't let arbitrage cleanup crash the disconnect process 
    
    # Connection State Tracking Methods  
    def get_connection_state(self) -> Dict[str, Any]:
        """
        Get connection state for both platforms.
        
        Returns:
            Dict containing current connection state
        """
        kalshi_ticker = self.current_markets['kalshi']
        polymarket_market = self.current_markets['polymarket']
        both_connected = kalshi_ticker is not None and polymarket_market is not None
        
        # Get active arbitrage pairs
        active_pairs = []
        if self.service_coordinator.arbitrage_service:
            active_pairs = list(self.service_coordinator.arbitrage_service.market_pairs.keys())
        
        # Include SID for debugging/status
        kalshi_sid = self.ticker_to_sid(kalshi_ticker) if kalshi_ticker else None
        
        return {
            'kalshi_ticker': kalshi_ticker,
            'kalshi_sid': kalshi_sid,
            'polymarket_market': polymarket_market,
            'both_connected': both_connected,
            'active_arbitrage_pairs': active_pairs,
            'arbitrage_pair_active': len(active_pairs) > 0
        }
    
    def is_market_connected(self, market_id: str, platform: str) -> bool:
        """
        Check if a specific market is connected on a platform.
        
        Args:
            market_id: Market identifier (for Kalshi, can be ticker or market_id)
            platform: "kalshi" or "polymarket"
            
        Returns:
            bool: True if market is connected and tracked
        """
        if platform.lower() == "kalshi":
            # For Kalshi, accept either ticker or market_id format
            ticker = market_id.removeprefix("kalshi_")  # Handle both formats
            return self.current_markets.get('kalshi') == ticker
        else:
            return self.current_markets.get(platform.lower()) == market_id
    
    def get_current_markets(self) -> Dict[str, str]:
        """
        Get currently tracked markets for both platforms.
        
        Returns:
            Dict with platform names as keys and current identifiers as values (ticker for Kalshi, market_id for Polymarket)
        """
        return self.current_markets.copy()
    
    

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