"""
FastAPI WebSocket server for streaming cleaned ticker updates
"""
import asyncio
import json
import logging
import re
import time
from typing import Dict, List, Set, Optional
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
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

# Pydantic models for API requests/responses
class MarketSubscriptionRequest(BaseModel):
    platform: str = Field(..., description="Platform name: 'polymarket' or 'kalshi'")
    market_identifier: str = Field(..., description="Token ID for Polymarket or market slug for Kalshi")
    client_id: Optional[str] = Field(None, description="Optional client identifier")

class MarketSubscriptionResponse(BaseModel):
    success: bool
    status: str = Field(..., description="Connection status: pending, connecting, connected, failed")
    market_id: str = Field(..., description="Standardized market ID for WebSocket subscription")
    platform: str
    message: str
    websocket_url: str
    estimated_time_seconds: Optional[int] = None
    market_info: Dict[str, str] = Field(default_factory=dict)

class ConnectionState:
    """
    Track connection states for markets
    
    📝 Redis Migration Notes (when scaling to multiple workers):
    - Replace self.states dict with Redis hash operations
    - Use Redis transactions (MULTI/EXEC) for atomic updates
    - Use Redis pub/sub for state change notifications across workers
    """
    def __init__(self):
        # Currently safe with single worker, but not thread-safe for multiple workers
        self.states: Dict[str, Dict] = {}
    
    def set_state(self, market_id: str, status: str, platform: str, identifier: str, message: str = ""):
        # Redis equivalent: HSET market_states:{market_id} status {status} platform {platform}
        self.states[market_id] = {
            "status": status,
            "platform": platform,
            "identifier": identifier,
            "start_time": datetime.now(),
            "message": message
        }
    
    def get_state(self, market_id: str) -> Optional[Dict]:
        # Redis equivalent: HGETALL market_states:{market_id}
        return self.states.get(market_id)
    
    def update_status(self, market_id: str, status: str, message: str = ""):
        # Redis equivalent: Use WATCH + MULTI/EXEC for atomic updates
        if market_id in self.states:
            self.states[market_id]["status"] = status
            self.states[market_id]["message"] = message
            self.states[market_id]["last_updated"] = datetime.now()

# Global state manager (single worker safe)
connection_state_manager = ConnectionState()

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
        logger.info(f"🎯 STREAM MANAGER: Subscribing websocket to market: {market_id}")
        subscription = create_market_subscription(market_id)
        self.channel_manager.subscribe(websocket, subscription)
        logger.info(f"✅ STREAM MANAGER: Market subscription completed for: {market_id}")
    
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
        logger.info(f"📡 STREAM MANAGER: Broadcasting ticker update to channel manager: {ticker_data}")
        await self.channel_manager.broadcast_ticker_update(ticker_data)
        logger.info(f"✅ STREAM MANAGER: Ticker update broadcast completed")
    
    async def emit_ticker_update(self, ticker_data: dict):
        """Emit ticker update event (called by orderbook processors)"""
        logger.info(f"🚀 STREAM MANAGER: Emitting ticker update for market_id={ticker_data.get('market_id')}, platform={ticker_data.get('platform')}")
        # Directly call the broadcast method instead of using event emitter
        # since we're already in an async context
        await self._broadcast_ticker_update(ticker_data)

# Global stream manager instance
stream_manager = TickerStreamManager()

# Utility functions for market subscription API
def validate_market_request(platform: str, market_identifier: str) -> None:
    """Validate market subscription request parameters"""
    if platform not in ["polymarket", "kalshi"]:
        raise ValueError(f"Unsupported platform: {platform}. Must be 'polymarket' or 'kalshi'")
    
    if platform == "polymarket":
        # Validate Polymarket token ID format (long numeric string, typically 77+ digits)
        if not market_identifier.isdigit() or len(market_identifier) < 70:
            raise ValueError("Invalid Polymarket token ID format. Must be a long numeric string (70+ digits)")
    
    elif platform == "kalshi":
        # Validate Kalshi market slug format (uppercase alphanumeric with hyphens)
        if not re.match(r'^[A-Z0-9\-]+$', market_identifier):
            raise ValueError("Invalid Kalshi market slug format. Must be uppercase alphanumeric with hyphens")

def generate_market_id(platform: str, identifier: str) -> str:
    """Generate standardized market_id for WebSocket subscriptions"""
    return f"{platform}_{identifier}"

# Global MarketsManager instance (initialized on app startup)
markets_manager = None

async def initialize_markets_manager():
    """Initialize MarketsManager during app startup when event loop is available"""
    global markets_manager
    try:
        from .master_manager.MarketsManager import MarketsManager
        markets_manager = MarketsManager()
        logger.info("MarketsManager initialized successfully")
        return True
    except ImportError as e:
        logger.error(f"Failed to import MarketsManager: {e}")
        return False
    except Exception as e:
        logger.error(f"Failed to initialize MarketsManager: {e}")
        return False

async def handle_market_connection(platform: str, market_identifier: str) -> Dict[str, any]:
    """
    Handle market connection via MarketsManager
    
    Returns connection result with status and details
    """
    market_id = generate_market_id(platform, market_identifier)
    
    try:
        # Set initial state
        connection_state_manager.set_state(
            market_id=market_id,
            status="connecting", 
            platform=platform,
            identifier=market_identifier,
            message="Establishing connection to market data feed"
        )
        
        # Connect via MarketsManager
        if markets_manager is None:
            logger.error("MarketsManager not available - cannot establish market connection")
            connection_state_manager.update_status(market_id, "failed", "MarketsManager not available")
            success = False
        else:
            # Call MarketsManager.connect() with proper parameters
            logger.info(f"Connecting to {platform} market via MarketsManager: {market_identifier}")
            success = await markets_manager.connect(market_identifier, platform)
            
            if success:
                connection_state_manager.update_status(market_id, "connected", "Connection established successfully")
                logger.info(f"Successfully connected to {platform} market: {market_identifier}")
            else:
                connection_state_manager.update_status(market_id, "failed", "Failed to establish connection")
                logger.error(f"Failed to connect to {platform} market: {market_identifier}")
        
        return {
            "success": success,
            "market_id": market_id,
            "status": "connected" if success else "failed"
        }
        
    except Exception as e:
        logger.error(f"Market connection error for {platform}:{market_identifier} - {e}")
        connection_state_manager.update_status(market_id, "failed", f"Connection error: {str(e)}")
        return {
            "success": False,
            "market_id": market_id,
            "status": "failed",
            "error": str(e)
        }

# FastAPI app
app = FastAPI(title="Ticker Stream API", version="1.0.0")

# Add CORS middleware to handle cross-origin requests (including WebSocket)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", 
        "http://localhost:3001",  # Support both common frontend ports
        "http://127.0.0.1:3000", 
        "http://127.0.0.1:3001"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    """Initialize components when FastAPI app starts"""
    logger.info("Initializing FastAPI app components...")
    
    # Initialize MarketsManager
    success = await initialize_markets_manager()
    if success:
        logger.info("✅ MarketsManager ready for market connections")
    else:
        logger.warning("⚠️ MarketsManager not available - market connections will fail")
    
    logger.info("FastAPI app startup complete")

@app.websocket("/ws/ticker")
async def websocket_ticker_endpoint(websocket: WebSocket):
    """Main WebSocket endpoint for ticker streaming with multiplexed subscriptions"""
    logger.info(f"🔌 WebSocket connection attempt from {websocket.client}")
    
    await stream_manager.connect(websocket)
    logger.info(f"✅ WebSocket connected successfully from {websocket.client}")
    
    try:
        while True:
            # Listen for subscription messages
            data = await websocket.receive_text()
            logger.info(f"📨 WebSocket message received: {data}")
            try:
                message = json.loads(data)
                message_type = message.get('type')
                logger.info(f"🔍 Parsed message type: {message_type}")
                
                if message_type == 'subscribe_market':
                    market_id = message.get('market_id')
                    platform = message.get('platform', 'unknown')
                    if market_id:
                        logger.info(f"📡 Market subscription request: {market_id} (platform: {platform})")
                        stream_manager.subscribe_to_market(websocket, market_id)
                        await websocket.send_text(json.dumps({
                            'type': 'subscription_confirmed',
                            'subscription': 'market',
                            'market_id': market_id,
                            'platform': platform,
                            'timestamp': time.time()
                        }))
                        logger.info(f"✅ Market subscription confirmed: {market_id} (platform: {platform})")
                
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
                    platform = message.get('platform', 'unknown')
                    if market_id:
                        logger.info(f"📡 Market unsubscription request: {market_id} (platform: {platform})")
                        stream_manager.unsubscribe_from_market(websocket, market_id)
                        await websocket.send_text(json.dumps({
                            'type': 'unsubscription_confirmed',
                            'subscription': 'market',
                            'market_id': market_id,
                            'platform': platform,
                            'timestamp': time.time()
                        }))
                        logger.info(f"✅ Market unsubscription confirmed: {market_id} (platform: {platform})")
                
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
                    logger.warning(f"⚠️ Unknown WebSocket message type: {message_type}")
                    await websocket.send_text(json.dumps({
                        'type': 'error',
                        'message': f'Unknown message type: {message_type}',
                        'received_message': message,
                        'timestamp': time.time()
                    }))
                    
            except json.JSONDecodeError:
                logger.warning(f"❌ Invalid JSON received: {data}")
                await websocket.send_text(json.dumps({
                    'type': 'error',
                    'message': 'Invalid JSON format'
                }))
            except Exception as e:
                logger.error(f"💥 Error processing WebSocket message: {e}")
                logger.error(f"💥 Message that caused error: {data}")
                await websocket.send_text(json.dumps({
                    'type': 'error',
                    'message': 'Internal server error'
                }))
                
    except WebSocketDisconnect:
        logger.info(f"🔌 WebSocket disconnected: {websocket.client}")
    except Exception as e:
        logger.error(f"💥 Unexpected WebSocket error: {e}")
    finally:
        logger.info(f"🧹 Cleaning up WebSocket connection: {websocket.client}")
        stream_manager.disconnect(websocket)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    stats = stream_manager.channel_manager.get_stats()
    return {
        "status": "healthy",
        **stats
    }

@app.post("/api/markets/subscribe", response_model=MarketSubscriptionResponse)
async def subscribe_to_market(request: MarketSubscriptionRequest):
    """
    Subscribe to a specific market for real-time data streaming
    
    This endpoint:
    1. Validates the platform and market identifier format
    2. Establishes backend connection via MarketsManager 
    3. Returns standardized market_id for WebSocket subscription
    4. Tracks connection state for status monitoring
    
    After calling this endpoint, frontend should:
    1. Connect to WebSocket at returned websocket_url
    2. Send subscription message with returned market_id
    3. Start receiving real-time ticker updates
    """
    # Log incoming request
    logger.info(f"📥 API Request received: /api/markets/subscribe")
    logger.info(f"📊 Request details: platform={request.platform}, market_identifier={request.market_identifier}, client_id={request.client_id}")
    
    # Log market identifier parsing for different platforms
    if request.platform == "polymarket":
        try:
            token_ids = json.loads(request.market_identifier)
            logger.info(f"🔍 Polymarket token parsing: {request.market_identifier} → {token_ids} (count: {len(token_ids)})")
        except (json.JSONDecodeError, TypeError):
            logger.warning(f"⚠️ Polymarket token parsing failed for: {request.market_identifier}, using as single token")
            token_ids = [request.market_identifier]
    else:
        logger.info(f"🔍 Kalshi ticker: {request.market_identifier}")
    
    start_time = time.time()
    
    try:
        # Validate request parameters
        logger.info(f"🔎 Validating request parameters...")
        validate_market_request(request.platform, request.market_identifier)
        logger.info(f"✅ Request validation passed")
        
        # Generate standardized market ID
        market_id = generate_market_id(request.platform, request.market_identifier)
        logger.info(f"🏷️ Generated market_id: {market_id}")
        
        # Check if already connected
        existing_state = connection_state_manager.get_state(market_id)
        logger.info(f"🔍 Checking existing connection state for {market_id}: {existing_state}")
        
        if existing_state and existing_state["status"] == "connected":
            elapsed_time = time.time() - start_time
            logger.info(f"♻️ Market {market_id} already connected, returning existing connection (took {elapsed_time:.3f}s)")
            return MarketSubscriptionResponse(
                success=True,
                status="connected",
                market_id=market_id,
                platform=request.platform,
                message="Market already connected and streaming",
                websocket_url="ws://localhost:8000/ws/ticker",
                estimated_time_seconds=0,
                market_info={
                    "platform_identifier": request.market_identifier,
                    "connection_time": existing_state.get("start_time", "").isoformat() if existing_state.get("start_time") else ""
                }
            )
        
        # Handle new market connection
        logger.info(f"🚀 Initiating NEW connection to {request.platform} market: {request.market_identifier}")
        connection_result = await handle_market_connection(request.platform, request.market_identifier)
        logger.info(f"🔄 Connection result: {connection_result}")
        
        elapsed_time = time.time() - start_time
        
        # Build response based on connection result
        if connection_result["success"]:
            logger.info(f"✅ Market connection successful for {market_id} (took {elapsed_time:.3f}s)")
            return MarketSubscriptionResponse(
                success=True,
                status="connected",
                market_id=market_id,
                platform=request.platform, 
                message="Market connection established successfully",
                websocket_url="ws://localhost:8000/ws/ticker",
                estimated_time_seconds=0,
                market_info={
                    "platform_identifier": request.market_identifier,
                    "title": f"{request.platform.title()} Market",
                    "connection_established": datetime.now().isoformat()
                }
            )
        else:
            error_message = connection_result.get("error", "Unknown connection error")
            logger.error(f"❌ Market connection failed for {market_id}: {error_message} (took {elapsed_time:.3f}s)")
            return MarketSubscriptionResponse(
                success=False,
                status="failed",
                market_id=market_id,
                platform=request.platform,
                message=f"Failed to connect to market: {error_message}",
                websocket_url="ws://localhost:8000/ws/ticker",
                market_info={
                    "platform_identifier": request.market_identifier,
                    "error_details": error_message
                }
            )
            
    except ValueError as e:
        # Validation error
        elapsed_time = time.time() - start_time
        logger.warning(f"⚠️ Market subscription validation error: {e} (took {elapsed_time:.3f}s)")
        raise HTTPException(status_code=400, detail=str(e))
        
    except Exception as e:
        # Unexpected error
        elapsed_time = time.time() - start_time
        logger.error(f"💥 Unexpected error in market subscription: {e} (took {elapsed_time:.3f}s)")
        logger.error(f"💥 Full exception details:", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error during market subscription")

# TODO: Add disconnect endpoint (placeholder for future implementation)
# @app.post("/api/markets/disconnect")
# async def disconnect_from_market(request: MarketDisconnectionRequest):
#     """
#     Disconnect from a specific market
#     
#     Platform-specific considerations:
#     - Kalshi: Supports graceful removeMarkets() operation
#     - Polymarket: Requires subscription override (resubscribe without target market)
#     """
#     pass

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