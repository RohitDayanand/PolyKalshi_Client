"""
Polymarket Ticker Publisher - Connects Polymarket orderbook state to WebSocket streaming

Periodically publishes bid/ask/volume updates for all active Polymarket assets
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
    from backend.ticker_stream_integration import publish_polymarket_update_nowait, start_ticker_publisher, stop_ticker_publisher
except ImportError:
    # Fallback for development/testing - mock the functions
    def publish_polymarket_update_nowait(market_id: str, summary_stats: Dict[str, Any]):
        print(f"[MOCK] Publishing Polymarket update for {market_id}: {summary_stats}")
    
    async def start_ticker_publisher():
        print("[MOCK] Starting ticker publisher")
    
    async def stop_ticker_publisher():
        print("[MOCK] Stopping ticker publisher")

logger = logging.getLogger(__name__)

class PolymarketTickerPublisher:
    """
    Periodic publisher for Polymarket market data to WebSocket clients.
    
    Features:
    - Rate-limited publishing (max 1/second per asset)
    - Automatic discovery of active assets from processor
    - Graceful handling of missing or invalid data
    - Configurable publishing intervals
    - YES/NO market pairing logic for prediction markets
    """
    
    def __init__(self, polymarket_processor, publish_interval: float = 1.0):
        """
        Initialize the ticker publisher.
        
        Args:
            polymarket_processor: PolymarketMessageProcessor instance
            publish_interval: Minimum seconds between publications (default 1.0)
        """
        self.polymarket_processor = polymarket_processor
        self.publish_interval = publish_interval
        self.is_running = False
        self.publisher_task: Optional[asyncio.Task] = None
        
        # Track last publish times per asset to enforce rate limiting
        self.last_publish_times: Dict[str, float] = {}
        
        # Statistics
        self.stats = {
            "total_published": 0,
            "rate_limited": 0,
            "failed_publishes": 0,
            "active_assets": 0
        }
        
        logger.info(f"PolymarketTickerPublisher initialized with {publish_interval}s interval")
    
    async def start(self):
        """Start the periodic ticker publisher."""
        if self.is_running:
            logger.warning("Polymarket ticker publisher already running")
            return
        
        self.is_running = True
        
        # Start the upstream ticker publisher
        await start_ticker_publisher()
        
        # Start our periodic publishing task
        self.publisher_task = asyncio.create_task(self._publish_loop())
        logger.info("Polymarket ticker publisher started")
    
    async def stop(self):
        """Stop the periodic ticker publisher."""
        if not self.is_running:
            return
        
        logger.info("Stopping Polymarket ticker publisher...")
        self.is_running = False
        
        if self.publisher_task:
            self.publisher_task.cancel()
            try:
                await self.publisher_task
            except asyncio.CancelledError:
                pass
        
        # Stop the upstream ticker publisher
        await stop_ticker_publisher()
        
        logger.info("Polymarket ticker publisher stopped")
    
    async def _publish_loop(self):
        """Main publishing loop that runs periodically."""
        logger.info("Polymarket ticker publishing loop started")
        
        while self.is_running:
            try:
                await self._publish_all_assets()
                await asyncio.sleep(self.publish_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in Polymarket ticker publish loop: {e}")
                # Continue running even if there's an error
                await asyncio.sleep(self.publish_interval)
        
        logger.info("Polymarket ticker publishing loop stopped")
    
    async def _publish_all_assets(self):
        """Publish ticker updates for all active Polymarket assets."""
        try:
            # Get all current market summaries from the processor
            all_summaries = self.polymarket_processor.get_all_market_summaries()
            current_time = time.time()
            
            if not all_summaries:
                logger.debug("No active Polymarket assets to publish")
                return
            
            for key in ["yes", "no"]:
                print("Checking market summary validation for polymarket market", self._is_valid_market_summary(all_summaries.get(key)))
            
            
            # Publish the update
            await self._safe_publish(all_summaries["token_id"], {k: v for k, v in all_summaries.items() if k != "token_id"})
        except KeyError as e:
            print("Major exception")
               
    
    def _convert_to_yes_no_format(self, market_summary: Dict[str, Optional[float]]) -> Dict[str, Dict[str, Optional[float]]]:
        """
        Convert individual asset market summary to YES/NO format.
        
        For Polymarket, each asset_id represents either YES or NO side.
        We treat the asset as "yes" and calculate "no" as the inverse.
        """
        bid = market_summary.get('bid')
        ask = market_summary.get('ask')
        volume = market_summary.get('volume', 0.0)
        
        # YES side data (direct from asset)
        yes_data = {
            "bid": bid,
            "ask": ask,
            "volume": volume
        }
        
        # NO side data (inverse of YES prices)
        no_data = {
            "bid": (1.0 - ask) if ask is not None else None,
            "ask": (1.0 - bid) if bid is not None else None,
            "volume": volume  # Same volume for both sides
        }
        
        return {
            "yes": yes_data,
            "no": no_data
        }
    
    async def _safe_publish(self, market_id: str, summary_stats: Dict[str, Any]):
        """Safely publish ticker update with fire-and-forget approach (non-blocking)."""
        try:
            # Fire-and-forget: don't await, don't block orderbook processing
            publish_polymarket_update_nowait(market_id, summary_stats)
            logger.debug(f"Scheduled ticker update for {market_id}")
            
        except Exception as e:
            logger.error(f"Failed to schedule ticker update for {market_id}: {e}")
            self.stats["failed_publishes"] += 1
    
    def _is_valid_market_summary(self, market_summary: Dict[str, Any]) -> bool:
        """Validate market summary data quality."""
        try:
            # Check structure
            if not isinstance(market_summary, dict):
                return False
            
            # Check for required fields
            bid = market_summary.get('bid')
            ask = market_summary.get('ask')
            volume = market_summary.get('volume')
            
            # At least one of bid/ask should be present
            if bid is None and ask is None:
                return False
            
            # Validate bid if present
            if bid is not None:
                if not isinstance(bid, (int, float)):
                    return False
                if not (0 <= bid <= 1):
                    return False
            
            # Validate ask if present
            if ask is not None:
                if not isinstance(ask, (int, float)):
                    return False
                if not (0 <= ask <= 1):
                    return False
            
            # Validate volume if present
            if volume is not None:
                if not isinstance(volume, (int, float)):
                    return False
                if volume < 0:
                    return False
            
            # Bid should be less than ask if both present
            if bid is not None and ask is not None and bid >= ask:
                return False
            
            return True
            
        except Exception:
            return False
    
    def force_publish_asset(self, asset_id: str) -> bool:
        """
        Force immediate publication of a specific asset (bypasses rate limiting).
        Uses fire-and-forget approach for non-blocking behavior.
        
        Args:
            asset_id: Asset ID for the market
            
        Returns:
            bool: True if scheduled successfully
        """
        try:
            market_summary = self.polymarket_processor.get_market_summary(asset_id)
            if not market_summary:
                return False
            
            if not self._is_valid_market_summary(market_summary):
                return False
            
            summary_stats = self._convert_to_yes_no_format(market_summary)
            market_id = f"polymarket_{asset_id}"
            
            # Fire-and-forget publish (non-blocking)
            publish_polymarket_update_nowait(market_id, summary_stats)
            
            self.last_publish_times[asset_id] = time.time()
            self.stats["total_published"] += 1
            return True
            
        except Exception as e:
            logger.error(f"Failed to force publish asset asset_id={asset_id}: {e}")
            self.stats["failed_publishes"] += 1
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get publisher statistics."""
        return {
            **self.stats,
            "is_running": self.is_running,
            "publish_interval": self.publish_interval,
            "tracked_assets": len(self.last_publish_times)
        }