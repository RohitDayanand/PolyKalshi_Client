"""
Channel management system for multiplatform ticker streaming
Provides advanced filtering and routing capabilities
"""
import asyncio
import json
import logging
from typing import Dict, Set, List, Optional, Callable, Any
from dataclasses import dataclass
from enum import Enum
from fastapi import WebSocket

logger = logging.getLogger(__name__)

class SubscriptionType(Enum):
    """Types of subscriptions available"""
    ALL = "all"                    # All ticker updates
    PLATFORM = "platform"         # Platform-specific updates
    MARKET = "market"             # Market-specific updates
    CUSTOM = "custom"             # Custom filter-based updates

@dataclass
class SubscriptionFilter:
    """Filter definition for custom subscriptions"""
    subscription_type: SubscriptionType
    platform: Optional[str] = None
    market_id: Optional[str] = None
    custom_filter: Optional[Callable[[Dict], bool]] = None
    min_volume: Optional[float] = None
    price_range: Optional[Dict[str, float]] = None  # {"min": 0.1, "max": 0.9}

class ChannelManager:
    """
    Advanced channel management for WebSocket ticker streaming
    Supports complex filtering and routing logic
    """
    
    def __init__(self):
        # Core connection tracking
        self.connections: Set[WebSocket] = set()
        self.subscriptions: Dict[WebSocket, List[SubscriptionFilter]] = {}
        
        # Performance optimization caches
        self._platform_cache: Dict[str, Set[WebSocket]] = {}
        self._market_cache: Dict[str, Set[WebSocket]] = {}
        self._all_subscribers_cache: Optional[Set[WebSocket]] = None
        self._cache_dirty = True
        
        # Statistics
        self.stats = {
            "total_connections": 0,
            "messages_sent": 0,
            "failed_sends": 0,
            "active_subscriptions": 0
        }
    
    def add_connection(self, websocket: WebSocket):
        """Add new WebSocket connection"""
        self.connections.add(websocket)
        self.subscriptions[websocket] = []
        self._invalidate_cache()
        self.stats["total_connections"] = len(self.connections)
        logger.info(f"Connection added. Total: {len(self.connections)}")
    
    def remove_connection(self, websocket: WebSocket):
        """Remove WebSocket connection and clean up subscriptions"""
        self.connections.discard(websocket)
        if websocket in self.subscriptions:
            del self.subscriptions[websocket]
        self._invalidate_cache()
        self.stats["total_connections"] = len(self.connections)
        logger.info(f"Connection removed. Total: {len(self.connections)}")
    
    def subscribe(self, websocket: WebSocket, subscription_filter: SubscriptionFilter):
        """Add subscription filter for a WebSocket connection"""
        if websocket not in self.subscriptions:
            self.subscriptions[websocket] = []
        
        self.subscriptions[websocket].append(subscription_filter)
        self._invalidate_cache()
        self.stats["active_subscriptions"] = sum(len(subs) for subs in self.subscriptions.values())
        
        logger.info(f"🔗 CHANNEL MANAGER: Subscription added - Type: {subscription_filter.subscription_type.value}, Platform: {subscription_filter.platform}, Market: {subscription_filter.market_id}")
        logger.info(f"🔗 CHANNEL MANAGER: Total subscriptions for this websocket: {len(self.subscriptions[websocket])}")
        logger.info(f"🔗 CHANNEL MANAGER: Total active subscriptions across all websockets: {self.stats['active_subscriptions']}")
    
    def unsubscribe(self, websocket: WebSocket, subscription_type: SubscriptionType, 
                   platform: str = None, market_id: str = None):
        """Remove specific subscription from WebSocket connection"""
        if websocket not in self.subscriptions:
            return False
        
        # Find and remove matching subscriptions
        original_count = len(self.subscriptions[websocket])
        self.subscriptions[websocket] = [
            sub for sub in self.subscriptions[websocket]
            if not (sub.subscription_type == subscription_type and
                   (platform is None or sub.platform == platform) and
                   (market_id is None or sub.market_id == market_id))
        ]
        
        removed_count = original_count - len(self.subscriptions[websocket])
        if removed_count > 0:
            self._invalidate_cache()
            self.stats["active_subscriptions"] = sum(len(subs) for subs in self.subscriptions.values())
            logger.info(f"Removed {removed_count} subscriptions")
            return True
        
        return False
    
    def _invalidate_cache(self):
        """Mark caches as dirty for rebuilding"""
        self._cache_dirty = True
        self._platform_cache.clear()
        self._market_cache.clear()
        self._all_subscribers_cache = None
    
    def _rebuild_caches(self):
        """Rebuild performance caches"""
        if not self._cache_dirty:
            return
        
        self._platform_cache.clear()
        self._market_cache.clear()
        all_subscribers = set()
        
        for websocket, filters in self.subscriptions.items():
            for sub_filter in filters:
                if sub_filter.subscription_type == SubscriptionType.ALL:
                    all_subscribers.add(websocket)
                
                elif sub_filter.subscription_type == SubscriptionType.PLATFORM:
                    if sub_filter.platform:
                        if sub_filter.platform not in self._platform_cache:
                            self._platform_cache[sub_filter.platform] = set()
                        self._platform_cache[sub_filter.platform].add(websocket)
                
                elif sub_filter.subscription_type == SubscriptionType.MARKET:
                    if sub_filter.market_id:
                        if sub_filter.market_id not in self._market_cache:
                            self._market_cache[sub_filter.market_id] = set()
                        self._market_cache[sub_filter.market_id].add(websocket)
        
        self._all_subscribers_cache = all_subscribers
        self._cache_dirty = False
        logger.debug("Caches rebuilt")
    
    def _matches_filter(self, ticker_data: Dict, sub_filter: SubscriptionFilter) -> bool:
        """Check if ticker data matches subscription filter"""
        
        # Basic filters
        if sub_filter.subscription_type == SubscriptionType.ALL:
            return True
        
        if sub_filter.subscription_type == SubscriptionType.PLATFORM:
            return ticker_data.get('platform') == sub_filter.platform
        
        if sub_filter.subscription_type == SubscriptionType.MARKET:
            return ticker_data.get('market_id') == sub_filter.market_id
        
        if sub_filter.subscription_type == SubscriptionType.CUSTOM:
            # Volume filter
            if sub_filter.min_volume is not None:
                summary_stats = ticker_data.get('summary_stats', {})
                total_volume = 0
                for side_data in summary_stats.values():
                    if isinstance(side_data, dict) and 'volume' in side_data:
                        total_volume += side_data['volume']
                if total_volume < sub_filter.min_volume:
                    return False
            
            # Price range filter
            if sub_filter.price_range is not None:
                summary_stats = ticker_data.get('summary_stats', {})
                yes_data = summary_stats.get('yes', {})
                if 'bid' in yes_data:
                    price = yes_data['bid']
                    min_price = sub_filter.price_range.get('min', 0)
                    max_price = sub_filter.price_range.get('max', 1)
                    if not (min_price <= price <= max_price):
                        return False
            
            # Custom filter function
            if sub_filter.custom_filter is not None:
                return sub_filter.custom_filter(ticker_data)
        
        return True
    
    async def broadcast_ticker_update(self, ticker_data: Dict):
        """Broadcast ticker update to relevant subscribers with advanced filtering"""
        logger.info(f"📻 CHANNEL MANAGER: Starting broadcast for market_id={ticker_data.get('market_id')}, platform={ticker_data.get('platform')}")
        
        self._rebuild_caches()
        
        # Collect subscribers using optimized caches
        subscribers = set()
        
        # Add "all" subscribers
        if self._all_subscribers_cache:
            subscribers.update(self._all_subscribers_cache)
            logger.info(f"📻 CHANNEL MANAGER: Added {len(self._all_subscribers_cache)} 'all' subscribers")
        
        # Add platform-specific subscribers
        platform = ticker_data.get('platform')
        if platform and platform in self._platform_cache:
            platform_subs = self._platform_cache[platform]
            subscribers.update(platform_subs)
            logger.info(f"📻 CHANNEL MANAGER: Added {len(platform_subs)} platform '{platform}' subscribers")
        
        # Add market-specific subscribers
        market_id = ticker_data.get('market_id')
        if market_id and market_id in self._market_cache:
            market_subs = self._market_cache[market_id]
            subscribers.update(market_subs)
            logger.info(f"📻 CHANNEL MANAGER: Added {len(market_subs)} market '{market_id}' subscribers")
        
        # Add custom filter subscribers (these require individual checking)
        custom_count = 0
        for websocket, filters in self.subscriptions.items():
            for sub_filter in filters:
                if sub_filter.subscription_type == SubscriptionType.CUSTOM:
                    if self._matches_filter(ticker_data, sub_filter):
                        subscribers.add(websocket)
                        custom_count += 1
        
        if custom_count > 0:
            logger.info(f"📻 CHANNEL MANAGER: Added {custom_count} custom filter subscribers")
        
        logger.info(f"📻 CHANNEL MANAGER: Total subscribers to broadcast to: {len(subscribers)}")
        
        # Broadcast to all matching subscribers
        if subscribers:
            await self._send_to_subscribers(subscribers, ticker_data)
        else:
            logger.warning(f"📻 CHANNEL MANAGER: No subscribers found for market_id={market_id}, platform={platform}")
            # Debug: show current cache state
            logger.info(f"📻 CHANNEL MANAGER DEBUG: Platform cache keys: {list(self._platform_cache.keys())}")
            logger.info(f"📻 CHANNEL MANAGER DEBUG: Market cache keys: {list(self._market_cache.keys())}")
            logger.info(f"📻 CHANNEL MANAGER DEBUG: All subscribers: {len(self._all_subscribers_cache) if self._all_subscribers_cache else 0}")
            logger.info(f"📻 CHANNEL MANAGER DEBUG: Total connections: {len(self.connections)}")
            logger.info(f"📻 CHANNEL MANAGER DEBUG: Total subscriptions: {len(self.subscriptions)}")
    
    async def _send_to_subscribers(self, subscribers: Set[WebSocket], data: Dict):
        """Send data to set of WebSocket subscribers with error handling"""
        message = json.dumps(data)
        logger.info(f"📤 CHANNEL MANAGER: Sending to {len(subscribers)} subscribers: {message[:200]}...")
        disconnected = set()
        
        send_tasks = []
        for websocket in subscribers:
            send_tasks.append(self._safe_send(websocket, message))
        
        results = await asyncio.gather(*send_tasks, return_exceptions=True)
        
        # Process results and track disconnections
        successful_sends = 0
        for i, result in enumerate(results):
            websocket = list(subscribers)[i]
            if isinstance(result, Exception):
                logger.warning(f"Failed to send to client: {result}")
                disconnected.add(websocket)
                self.stats["failed_sends"] += 1
            else:
                successful_sends += 1
                self.stats["messages_sent"] += 1
        
        logger.info(f"📤 CHANNEL MANAGER: Successfully sent to {successful_sends}/{len(subscribers)} subscribers")
        
        # Clean up disconnected clients
        for websocket in disconnected:
            self.remove_connection(websocket)
    
    async def _safe_send(self, websocket: WebSocket, message: str):
        """Safely send message to WebSocket with timeout"""
        try:
            await asyncio.wait_for(websocket.send_text(message), timeout=5.0)
        except Exception as e:
            raise e
    
    def get_stats(self) -> Dict[str, Any]:
        """Get channel manager statistics"""
        return {
            **self.stats,
            "platform_subscriptions": {platform: len(subs) for platform, subs in self._platform_cache.items()},
            "market_subscriptions": {market: len(subs) for market, subs in self._market_cache.items()},
            "all_subscribers": len(self._all_subscribers_cache) if self._all_subscribers_cache else 0
        }

# Convenience functions for creating subscription filters
def create_all_subscription() -> SubscriptionFilter:
    """Create subscription for all ticker updates"""
    return SubscriptionFilter(subscription_type=SubscriptionType.ALL)

def create_platform_subscription(platform: str) -> SubscriptionFilter:
    """Create subscription for platform-specific updates"""
    return SubscriptionFilter(
        subscription_type=SubscriptionType.PLATFORM,
        platform=platform
    )

def create_market_subscription(market_id: str) -> SubscriptionFilter:
    """Create subscription for market-specific updates"""
    return SubscriptionFilter(
        subscription_type=SubscriptionType.MARKET,
        market_id=market_id
    )

def create_volume_filter_subscription(min_volume: float, platform: str = None) -> SubscriptionFilter:
    """Create subscription with minimum volume filter"""
    return SubscriptionFilter(
        subscription_type=SubscriptionType.CUSTOM,
        platform=platform,
        min_volume=min_volume
    )

def create_price_range_subscription(min_price: float, max_price: float, platform: str = None) -> SubscriptionFilter:
    """Create subscription with price range filter"""
    return SubscriptionFilter(
        subscription_type=SubscriptionType.CUSTOM,
        platform=platform,
        price_range={"min": min_price, "max": max_price}
    )