"""
Integration module for connecting orderbook processors to WebSocket streaming
"""
import asyncio
import time
from typing import Dict, Any
from backend.websocket_server import publish_ticker_update
import logging

logger = logging.getLogger(__name__)

class TickerStreamPublisher:
    """
    Async publisher class that receives cleaned ticker updates and publishes them
    to WebSocket clients via the stream manager
    """
    
    def __init__(self):
        self.running = False
    
    async def start(self):
        """Start the async publisher"""
        if not self.running:
            self.running = True
            logger.info("TickerStreamPublisher started")
    
    async def stop(self):
        """Stop the async publisher"""
        self.running = False
        logger.info("TickerStreamPublisher stopped")
    
    async def publish_update(self, market_id: str, platform: str, summary_stats: Dict[str, Any]):
        """
        Async publish a ticker update to WebSocket clients
        
        Args:
            market_id: The market identifier
            platform: 'polymarket' or 'kalshi'
            summary_stats: Dictionary containing bid/ask/volume data
                Expected format: {
                    "yes": {"bid": float, "ask": float, "volume": float},
                    "no": {"bid": float, "ask": float, "volume": float}
                }
        """
        if not self.running:
            logger.warning("Publisher not running, skipping update")
            return
        
        ticker_data = {
            "type": "ticker_update",  # Add type field for frontend compatibility
            "market_id": market_id,
            "platform": platform,
            "summary_stats": summary_stats,
            "timestamp": time.time()
        }
        
        try:
            # Direct async call - no event loop juggling
            await publish_ticker_update(ticker_data)
            logger.debug(f"Published ticker update for {platform} market {market_id}")
        except Exception as e:
            logger.error(f"Failed to publish ticker update for {platform} market {market_id}: {e}")

# Global publisher instance
ticker_publisher = TickerStreamPublisher()

# Async convenience functions for direct use by orderbook processors
async def publish_polymarket_update(market_id: str, summary_stats: Dict[str, Any]):
    """Async publish Polymarket ticker update"""
    await ticker_publisher.publish_update(market_id, 'polymarket', summary_stats)

async def publish_kalshi_update(market_id: str, summary_stats: Dict[str, Any]):
    """Async publish Kalshi ticker update"""
    await ticker_publisher.publish_update(market_id, 'kalshi', summary_stats)

async def start_ticker_publisher():
    """Start the global ticker publisher"""
    await ticker_publisher.start()

async def stop_ticker_publisher():
    """Stop the global ticker publisher"""
    await ticker_publisher.stop()

# Fire-and-forget versions for non-blocking calls
def publish_polymarket_update_nowait(market_id: str, summary_stats: Dict[str, Any]):
    """Fire-and-forget Polymarket ticker update (non-blocking)"""
    asyncio.create_task(publish_polymarket_update(market_id, summary_stats))

def publish_kalshi_update_nowait(market_id: str, summary_stats: Dict[str, Any]):
    """Fire-and-forget Kalshi ticker update (non-blocking)"""
    asyncio.create_task(publish_kalshi_update(market_id, summary_stats))

# Example usage for orderbook processors:
"""
# In your orderbook processor code:
from backend.ticker_stream_integration import publish_kalshi_update_nowait, publish_polymarket_update_nowait

# When you have cleaned ticker data:
summary_stats = {
    "yes": {"bid": 0.45, "ask": 0.47, "volume": 1000.0},
    "no": {"bid": 0.53, "ask": 0.55, "volume": 800.0}
}

# Fire-and-forget publish to WebSocket clients (NON-BLOCKING)
publish_polymarket_update_nowait("some_market_id", summary_stats)
# or
publish_kalshi_update_nowait("some_market_id", summary_stats)

# If you need to await (blocking):
await publish_polymarket_update("some_market_id", summary_stats)
await publish_kalshi_update("some_market_id", summary_stats)
"""