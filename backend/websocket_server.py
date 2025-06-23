"""
FastAPI WebSocket server for streaming cleaned ticker updates
"""
import asyncio
import json
import logging
from typing import Dict, List, Set
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pyee.asyncio import AsyncIOEventEmitter
import uvicorn
from backend.channel_manager import (
    ChannelManager, 
    create_all_subscription, 
    create_platform_subscription, 
    create_market_subscription,
    SubscriptionType
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TickerStreamManager:
    """Manages WebSocket connections and ticker update streaming using advanced channel manager"""
    
    def __init__(self):
        self.channel_manager = ChannelManager()
        self.event_emitter = AsyncIOEventEmitter()
        
        # Set up event listeners
        self.event_emitter.on('ticker_update', self._broadcast_ticker_update)
    
    async def connect(self, websocket: WebSocket):
        """Accept new WebSocket connection"""
        await websocket.accept()
        self.channel_manager.add_connection(websocket)
    
    def disconnect(self, websocket: WebSocket):
        """Handle WebSocket disconnection"""
        self.channel_manager.remove_connection(websocket)
    
    def subscribe_to_market(self, websocket: WebSocket, market_id: str):
        """Subscribe WebSocket to specific market updates"""
        subscription = create_market_subscription(market_id)
        self.channel_manager.subscribe(websocket, subscription)
    
    def subscribe_to_platform(self, websocket: WebSocket, platform: str):
        """Subscribe WebSocket to specific platform updates"""
        subscription = create_platform_subscription(platform)
        self.channel_manager.subscribe(websocket, subscription)
    
    def unsubscribe_from_market(self, websocket: WebSocket, market_id: str):
        """Unsubscribe WebSocket from market updates"""
        self.channel_manager.unsubscribe(websocket, SubscriptionType.MARKET, market_id=market_id)
    
    def unsubscribe_from_platform(self, websocket: WebSocket, platform: str):
        """Unsubscribe WebSocket from platform updates"""
        self.channel_manager.unsubscribe(websocket, SubscriptionType.PLATFORM, platform=platform)
    
    async def _broadcast_ticker_update(self, ticker_data: dict):
        """Broadcast ticker update using advanced channel manager"""
        await self.channel_manager.broadcast_ticker_update(ticker_data)
    
    async def emit_ticker_update(self, ticker_data: dict):
        """Emit ticker update event (called by orderbook processors)"""
        await self.event_emitter.emit('ticker_update', ticker_data)

# Global stream manager instance
stream_manager = TickerStreamManager()

# FastAPI app
app = FastAPI(title="Ticker Stream API", version="1.0.0")

@app.websocket("/ws/ticker")
async def websocket_ticker_endpoint(websocket: WebSocket):
    """Main WebSocket endpoint for ticker streaming"""
    await stream_manager.connect(websocket)
    
    try:
        while True:
            # Listen for subscription messages
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                message_type = message.get('type')
                
                if message_type == 'subscribe_market':
                    market_id = message.get('market_id')
                    if market_id:
                        stream_manager.subscribe_to_market(websocket, market_id)
                        await websocket.send_text(json.dumps({
                            'type': 'subscription_confirmed',
                            'subscription': 'market',
                            'market_id': market_id
                        }))
                
                elif message_type == 'subscribe_platform':
                    platform = message.get('platform')
                    if platform in ['polymarket', 'kalshi']:
                        stream_manager.subscribe_to_platform(websocket, platform)
                        await websocket.send_text(json.dumps({
                            'type': 'subscription_confirmed',
                            'subscription': 'platform',
                            'platform': platform
                        }))
                
                elif message_type == 'unsubscribe_market':
                    market_id = message.get('market_id')
                    if market_id:
                        stream_manager.unsubscribe_from_market(websocket, market_id)
                        await websocket.send_text(json.dumps({
                            'type': 'unsubscription_confirmed',
                            'subscription': 'market',
                            'market_id': market_id
                        }))
                
                elif message_type == 'unsubscribe_platform':
                    platform = message.get('platform')
                    if platform:
                        stream_manager.unsubscribe_from_platform(websocket, platform)
                        await websocket.send_text(json.dumps({
                            'type': 'unsubscription_confirmed',
                            'subscription': 'platform',
                            'platform': platform
                        }))
                
                else:
                    await websocket.send_text(json.dumps({
                        'type': 'error',
                        'message': f'Unknown message type: {message_type}'
                    }))
                    
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({
                    'type': 'error',
                    'message': 'Invalid JSON format'
                }))
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                await websocket.send_text(json.dumps({
                    'type': 'error',
                    'message': 'Internal server error'
                }))
                
    except WebSocketDisconnect:
        pass
    finally:
        stream_manager.disconnect(websocket)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    stats = stream_manager.channel_manager.get_stats()
    return {
        "status": "healthy",
        **stats
    }

# Function to be called by orderbook processors
async def publish_ticker_update(ticker_data: dict):
    """
    Publish ticker update to WebSocket clients
    
    Expected format:
    {
        "market_id": "some_market_id",
        "platform": "polymarket" or "kalshi", 
        "summary_stats": {
            "yes": {"bid": float, "ask": float, "volume": float},
            "no": {"bid": float, "ask": float, "volume": float}
        },
        "timestamp": unix_timestamp
    }
    """
    await stream_manager.emit_ticker_update(ticker_data)

if __name__ == "__main__":
    uvicorn.run(
        "websocket_server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )