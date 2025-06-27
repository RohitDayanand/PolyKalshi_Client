"""
Simplified WebSocket server for single connection ticker streaming
"""
import asyncio
import json
import logging
import time
from typing import Set, Optional
from fastapi import WebSocket
from pyee.asyncio import AsyncIOEventEmitter

logger = logging.getLogger(__name__)

class SimpleTickerManager:
    """Simple manager for single WebSocket connection with market subscriptions"""
    
    def __init__(self):
        self.websocket: Optional[WebSocket] = None
        self.subscribed_markets: Set[str] = set()
        self.event_emitter = AsyncIOEventEmitter()
        
        # Set up event listener for ticker updates
        self.event_emitter.on('ticker_update', self._send_ticker_update)
    
    async def connect(self, websocket: WebSocket):
        """Accept WebSocket connection"""
        await websocket.accept()
        self.websocket = websocket
        logger.info(f"✅ SIMPLE MANAGER: WebSocket connected from {websocket.client}")
    
    def disconnect(self):
        """Handle WebSocket disconnection"""
        if self.websocket:
            logger.info(f"🔌 SIMPLE MANAGER: WebSocket disconnected")
            self.websocket = None
            self.subscribed_markets.clear()
    
    def subscribe_to_market(self, market_id: str):
        """Subscribe to market updates"""
        self.subscribed_markets.add(market_id)
        logger.info(f"📡 SIMPLE MANAGER: Subscribed to market: {market_id}")
        logger.info(f"📡 SIMPLE MANAGER: Total subscriptions: {len(self.subscribed_markets)}")
        logger.info(f"📡 SIMPLE MANAGER: Subscribed markets: {list(self.subscribed_markets)}")
    
    def unsubscribe_from_market(self, market_id: str):
        """Unsubscribe from market updates"""
        self.subscribed_markets.discard(market_id)
        logger.info(f"📡 SIMPLE MANAGER: Unsubscribed from market: {market_id}")
    
    async def _send_ticker_update(self, ticker_data: dict):
        """Send ticker update if WebSocket is connected and subscribed to this market"""
        if not self.websocket:
            logger.warning(f"📡 SIMPLE MANAGER: No WebSocket connected - dropping ticker update")
            return
        
        market_id = ticker_data.get('market_id')
        if market_id not in self.subscribed_markets:
            logger.debug(f"📡 SIMPLE MANAGER: Not subscribed to {market_id} - ignoring update")
            return
        
        try:
            message = json.dumps(ticker_data)
            await self.websocket.send_text(message)
            logger.info(f"📤 SIMPLE MANAGER: Sent ticker update for {market_id}")
        except Exception as e:
            logger.error(f"❌ SIMPLE MANAGER: Failed to send ticker update: {e}")
            self.disconnect()
    
    async def emit_ticker_update(self, ticker_data: dict):
        """External method to emit ticker updates"""
        logger.info(f"🚀 SIMPLE MANAGER: Emitting ticker update for market_id={ticker_data.get('market_id')}")
        await self._send_ticker_update(ticker_data)
    
    def get_stats(self):
        """Get connection statistics"""
        return {
            "connected": self.websocket is not None,
            "subscribed_markets": list(self.subscribed_markets),
            "total_subscriptions": len(self.subscribed_markets)
        }

# Global simple manager instance
simple_manager = SimpleTickerManager()