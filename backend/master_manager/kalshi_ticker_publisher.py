"""
Kalshi Ticker Publisher - Connects Kalshi orderbook state to WebSocket streaming

Periodically publishes bid/ask/volume updates for all active Kalshi markets
to the upstream WebSocket server at controlled intervals (max 1/second).
"""

import asyncio
import time
import logging
from typing import Dict, Any, Optional
import sys
import os

# Add backend path for imports
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(__file__))))

try:
    from backend.ticker_stream_integration import publish_kalshi_update_nowait, start_ticker_publisher, stop_ticker_publisher
except ImportError:
    # Fallback for development/testing - mock the functions
    def publish_kalshi_update_nowait(market_id: str, summary_stats: Dict[str, Any]):
        print(f"[MOCK] Publishing Kalshi update for {market_id}: {summary_stats}")
    
    async def start_ticker_publisher():
        print("[MOCK] Starting ticker publisher")
    
    async def stop_ticker_publisher():
        print("[MOCK] Stopping ticker publisher")

logger = logging.getLogger(__name__)

class KalshiTickerPublisher:
    """
    Periodic publisher for Kalshi market data to WebSocket clients.
    
    Features:
    - Rate-limited publishing (max 1/second per market)
    - Automatic discovery of active markets from processor
    - Graceful handling of missing or invalid data
    - Configurable publishing intervals
    """
    
    def __init__(self, kalshi_processor, publish_interval: float = 1.0):
        """
        Initialize the ticker publisher.
        
        Args:
            kalshi_processor: KalshiMessageProcessor instance
            publish_interval: Minimum seconds between publications (default 1.0)
        """
        self.kalshi_processor = kalshi_processor
        self.publish_interval = publish_interval
        self.is_running = False
        self.publisher_task: Optional[asyncio.Task] = None
        
        # Track last publish times per market to enforce rate limiting
        self.last_publish_times: Dict[int, float] = {}
        
        # Statistics
        self.stats = {
            "total_published": 0,
            "rate_limited": 0,
            "failed_publishes": 0,
            "active_markets": 0
        }
        
        logger.info(f"KalshiTickerPublisher initialized with {publish_interval}s interval")
    
    async def start(self):
        """Start the periodic ticker publisher."""
        if self.is_running:
            logger.warning("Kalshi ticker publisher already running")
            return
        
        self.is_running = True
        
        # Start the upstream ticker publisher
        await start_ticker_publisher()
        
        # Start our periodic publishing task
        self.publisher_task = asyncio.create_task(self._publish_loop())
        logger.info("Kalshi ticker publisher started")
    
    async def stop(self):
        """Stop the periodic ticker publisher."""
        if not self.is_running:
            return
        
        logger.info("Stopping Kalshi ticker publisher...")
        self.is_running = False
        
        if self.publisher_task:
            self.publisher_task.cancel()
            try:
                await self.publisher_task
            except asyncio.CancelledError:
                pass
        
        # Stop the upstream ticker publisher
        await stop_ticker_publisher()
        
        logger.info("Kalshi ticker publisher stopped")
    
    async def _publish_loop(self):
        """Main publishing loop that runs periodically."""
        logger.info("Kalshi ticker publishing loop started")
        
        while self.is_running:
            try:
                await self._publish_all_markets()
                await asyncio.sleep(self.publish_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in Kalshi ticker publish loop: {e}")
                # Continue running even if there's an error
                await asyncio.sleep(self.publish_interval)
        
        logger.info("Kalshi ticker publishing loop stopped")
    
    async def _publish_all_markets(self):
        """Publish ticker updates for all active Kalshi markets."""
        try:
            # Get all current summary stats from the processor
            all_stats = self.kalshi_processor.get_all_summary_stats()
            current_time = time.time()
            
            self.stats["active_markets"] = len(all_stats)
            
            if not all_stats:
                logger.debug("No active Kalshi markets to publish")
                return
            
            published_count = 0
            
            for sid, summary_stats in all_stats.items():
                try:
                    # Check rate limiting per market
                    last_publish = self.last_publish_times.get(sid, 0)
                    time_since_last = current_time - last_publish
                    
                    if time_since_last < self.publish_interval:
                        self.stats["rate_limited"] += 1
                        continue
                    
                    # Get market info
                    orderbook = self.kalshi_processor.get_orderbook(sid)
                    if not orderbook or not orderbook.market_ticker:
                        logger.debug(f"No market ticker for sid={sid}, skipping")
                        continue
                    
                    # Validate data quality
                    if not self._is_valid_summary_stats(summary_stats):
                        logger.debug(f"Invalid summary stats for sid={sid}, skipping")
                        continue
                    
                    # Create market_id from ticker or use sid
                    market_id = orderbook.market_ticker or f"kalshi_sid_{sid}"
                    
                    # Publish the update
                    await self._safe_publish(market_id, summary_stats)
                    
                    # Update tracking
                    self.last_publish_times[sid] = current_time
                    published_count += 1
                    self.stats["total_published"] += 1
                    
                except Exception as e:
                    logger.error(f"Error publishing market sid={sid}: {e}")
                    self.stats["failed_publishes"] += 1
            
            if published_count > 0:
                logger.debug(f"Published {published_count} Kalshi market updates")
                
        except Exception as e:
            logger.error(f"Error in _publish_all_markets: {e}")
    
    async def _safe_publish(self, market_id: str, summary_stats: Dict[str, Any]):
        """Safely publish ticker update with fire-and-forget approach (non-blocking)."""
        try:
            # Fire-and-forget: don't await, don't block orderbook processing
            publish_kalshi_update_nowait(market_id, summary_stats)
            logger.debug(f"Scheduled ticker update for {market_id}")
            
        except Exception as e:
            logger.error(f"Failed to schedule ticker update for {market_id}: {e}")
            self.stats["failed_publishes"] += 1
    
    def _is_valid_summary_stats(self, summary_stats: Dict[str, Any]) -> bool:
        """Validate summary stats data quality."""
        try:
            # Check structure
            if not isinstance(summary_stats, dict):
                return False
            
            for side in ["yes", "no"]:
                if side not in summary_stats:
                    return False
                
                side_data = summary_stats[side]
                if not isinstance(side_data, dict):
                    return False
                
                # Check for required fields and valid values
                for field in ["bid", "ask", "volume"]:
                    if field not in side_data:
                        return False
                    
                    value = side_data[field]
                    if value is not None:
                        # Must be a number
                        if not isinstance(value, (int, float)):
                            return False
                        
                        # Prices should be between 0 and 1
                        if field in ["bid", "ask"] and not (0 <= value <= 1):
                            return False
                        
                        # Volume should be non-negative
                        if field == "volume" and value < 0:
                            return False
            
            return True
            
        except Exception:
            return False
    
    def force_publish_market(self, sid: int) -> bool:
        """
        Force immediate publication of a specific market (bypasses rate limiting).
        Uses fire-and-forget approach for non-blocking behavior.
        
        Args:
            sid: Market subscription ID
            
        Returns:
            bool: True if scheduled successfully
        """
        try:
            summary_stats = self.kalshi_processor.get_summary_stats(sid)
            if not summary_stats:
                return False
            
            orderbook = self.kalshi_processor.get_orderbook(sid)
            if not orderbook or not orderbook.market_ticker:
                return False
            
            market_id = orderbook.market_ticker
            
            # Fire-and-forget publish (non-blocking)
            publish_kalshi_update_nowait(market_id, summary_stats)
            
            self.last_publish_times[sid] = time.time()
            self.stats["total_published"] += 1
            return True
            
        except Exception as e:
            logger.error(f"Failed to force publish market sid={sid}: {e}")
            self.stats["failed_publishes"] += 1
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get publisher statistics."""
        return {
            **self.stats,
            "is_running": self.is_running,
            "publish_interval": self.publish_interval,
            "tracked_markets": len(self.last_publish_times)
        }