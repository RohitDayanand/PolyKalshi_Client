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
    Publisher class that receives cleaned ticker updates and publishes them
    to WebSocket clients via the stream manager
    """
    
    def __init__(self):
        self.loop = None
        self.running = False
    
    def start(self):
        """Start the publisher (sets up event loop if needed)"""
        if not self.running:
            self.running = True
            if self.loop is None:
                try:
                    self.loop = asyncio.get_event_loop()
                except RuntimeError:
                    self.loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(self.loop)
            logger.info("TickerStreamPublisher started")
    
    def stop(self):
        """Stop the publisher"""
        self.running = False
        logger.info("TickerStreamPublisher stopped")
    
    def publish_update(self, market_id: str, platform: str, summary_stats: Dict[str, Any]):
        """
        Publish a ticker update to WebSocket clients
        
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
            "market_id": market_id,
            "platform": platform,
            "summary_stats": summary_stats,
            "timestamp": time.time()
        }
        
        # Schedule the async publish call
        if self.loop and self.loop.is_running():
            asyncio.create_task(publish_ticker_update(ticker_data))
        else:
            asyncio.run(publish_ticker_update(ticker_data))
        
        logger.debug(f"Published ticker update for {platform} market {market_id}")

# Global publisher instance
ticker_publisher = TickerStreamPublisher()

# Convenience functions for direct use by orderbook processors
def publish_polymarket_update(market_id: str, summary_stats: Dict[str, Any]):
    """Publish Polymarket ticker update"""
    ticker_publisher.publish_update(market_id, 'polymarket', summary_stats)

def publish_kalshi_update(market_id: str, summary_stats: Dict[str, Any]):
    """Publish Kalshi ticker update"""
    ticker_publisher.publish_update(market_id, 'kalshi', summary_stats)

def start_ticker_publisher():
    """Start the global ticker publisher"""
    ticker_publisher.start()

def stop_ticker_publisher():
    """Stop the global ticker publisher"""
    ticker_publisher.stop()

# Example usage for orderbook processors:
"""
# In your orderbook processor code:
from backend.ticker_stream_integration import publish_polymarket_update, publish_kalshi_update

# When you have cleaned ticker data:
summary_stats = {
    "yes": {"bid": 0.45, "ask": 0.47, "volume": 1000.0},
    "no": {"bid": 0.53, "ask": 0.55, "volume": 800.0}
}

# Publish to WebSocket clients
publish_polymarket_update("some_market_id", summary_stats)
# or
publish_kalshi_update("some_market_id", summary_stats)
"""