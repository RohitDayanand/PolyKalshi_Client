"""
FastAPI WebSocket server for streaming cleaned ticker updates
"""
import asyncio
import json
import logging
import re
import time
from typing import Dict, Optional
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pyee.asyncio import AsyncIOEventEmitter
import uvicorn
from backend.channel_manager import (
    ChannelManager,
    create_market_subscription,
    SubscriptionType
)
from backend.master_manager.kalshi_client.kalshi_candlestick_processor import (
    fetch_kalshi_candlesticks,
    process_kalshi_candlesticks,
    map_time_range_to_period_interval
)

from backend.master_manager.polymarket_client.polymarket_timeseries_processor import (
    fetch_polymarket_timeseries, parse_polymarket_market_string
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Console output
        logging.FileHandler('/home/rohit/Websocket_Polymarket_Kalshi/backend/websocket_debug.log', mode='w')  # File output
    ]
)
logger = logging.getLogger(__name__)
logger.info("📝 Logging to both console and websocket_debug.log")

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

class KalshiCandlestickResponse(BaseModel):
    success: bool
    data: Optional[Dict] = None
    error: Optional[str] = None
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

class GlobalManager:
    """Manages WebSocket connections and ticker update streaming using advanced channel manager"""
    
    def __init__(self, channel_manager=None):
        # Use provided channel_manager or import global one
        if channel_manager:
            self.channel_manager = channel_manager
        else:
            from backend.global_manager import global_channel_manager
            self.channel_manager = global_channel_manager
        
        self.event_emitter = AsyncIOEventEmitter()
        
        # Set up event listeners
        self.event_emitter.on('ticker_update', self._broadcast_ticker_update)
    
    async def connect(self, websocket: WebSocket):
        """Accept new WebSocket connection"""
        await websocket.accept()
        self.channel_manager.add_connection(websocket)
        logger.info(f"✅ STREAM MANAGER: WebSocket connection established and added to channel manager")
        logger.info(f"📊 STREAM MANAGER: Total connections: {len(self.channel_manager.connections)}")
    
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
stream_manager = GlobalManager()

# Utility functions for market subscription API
def validate_market_request(platform: str, market_identifier: str, token_ids: any = "") -> None:
    """Validate market subscription request parameters"""

    if platform not in ["polymarket", "kalshi"]:
        raise ValueError(f"Unsupported platform: {platform}. Must be 'polymarket' or 'kalshi'")
    
    if platform == "polymarket":
        # Validate Polymarket token ID format (long numeric string, typically 77+ digits)
        #attempt parsing the actual market_identifier 

        #we assume that this is correct because frontend controls logic
        print("no logic")

    elif platform == "kalshi":
        # Validate Kalshi market slug format (uppercase alphanumeric with hyphens)
        if not re.match(r'^[A-Z0-9\-]+$', market_identifier):
            raise ValueError("Invalid Kalshi market slug format. Must be uppercase alphanumeric with hyphens")

def generate_market_id(platform: str, identifier: str, token_ids: any = "") -> str:
    """Generate standardized market_id for WebSocket subscriptions"""
    if platform == 'polymarket':
        #check whet
        try: 
            token_string = ",".join(token_ids)
            return f"{platform}_{token_string}"
        except json.JSONDecodeError as e:
            print("Error detected - not jsonable. Check closely what the python server recieves")
            
    elif platform == 'kalshi':
        return f"{platform}_{identifier}"
    else:
        return "ID_GENERATION_FAILED"

def parse_market_string_id(market_string_id: str) -> Dict[str, str]:
    """Parse marketStringId format: ticker&side&range"""
    try:
        market_elements = market_string_id.split("&") #encoding for url same ampersand
        if len(market_elements) < 3:
            raise ValueError("Invalid market_string_id format. Expected: ticker&side&range")
        
        ticker = re.sub(r"^(kalshi_|polymarket_)", "", market_elements[0])
        side = market_elements[1] 
        range_str = market_elements[2]
        
        # Extract series ticker from market ticker (split by - or _, take first part)
        series_ticker = re.split(r'[-_]', ticker)[1]
        
        return {
            "market_ticker": ticker,
            "series_ticker": series_ticker,
            "side": side,
            "range": range_str
        }
    except Exception as e:
        raise ValueError(f"Failed to parse market_string_id: {str(e)}")


# Global MarketsManager instance (initialized on app startup)
markets_manager = None

async def initialize_markets_manager():
    """Initialize MarketsManager during app startup when event loop is available"""
    global markets_manager
    try:
        from backend.master_manager.MarketsManager import MarketsManager
        markets_manager = MarketsManager()
        logger.info("MarketsManager initialized successfully")
        return True
    except ImportError as e:
        logger.error(f"Failed to import MarketsManager: {e}")
        return False
    except Exception as e:
        logger.error(f"Failed to initialize MarketsManager: {e}")
        return False

async def handle_market_connection(platform: str, market_id: str) -> Dict[str, any]:
    """
    Handle market connection via MarketsManager
    
    Returns connection result with status and details
    """
    
    try:
        # Set initial state
        connection_state_manager.set_state(
            market_id=market_id,
            status="connecting", 
            platform=platform,
            identifier=market_id,
            message="Establishing connection to market data feed"
        )
        
        # Connect via MarketsManager
        if markets_manager is None:
            logger.error("MarketsManager not available - cannot establish market connection")
            connection_state_manager.update_status(market_id, "failed", "MarketsManager not available")
            success = False
        else:
            # Call MarketsManager.connect() with proper parameters
            logger.info(f"Connecting to {platform} market via MarketsManager: {market_id}")
            success = await markets_manager.connect(market_id, platform)
            
            if success:
                connection_state_manager.update_status(market_id, "connected", "Connection established successfully")
                logger.info(f"Successfully connected to {platform} market: {market_id}")
            else:
                connection_state_manager.update_status(market_id, "failed", "Failed to establish connection")
                logger.error(f"Failed to connect to {platform} market: {market_id}")
        
        return {
            "success": success,
            "market_id": market_id,
            "status": "connected" if success else "failed"
        }
        
    except Exception as e:
        logger.error(f"Market connection error for {platform}:{market_id} - {e}")
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
        
        # Start MarketsManager async components (queues and ticker publishers)
        try:
            await markets_manager.start_async_components()
            logger.info("✅ MarketsManager ticker publishers started")
        except Exception as e:
            logger.error(f"❌ Failed to start MarketsManager async components: {e}")
    else:
        logger.warning("⚠️ MarketsManager not available - market connections will fail")
    
    logger.info("FastAPI app startup complete")

@app.websocket("/ws/ticker")
async def websocket_ticker_endpoint(websocket: WebSocket):
    """Main WebSocket endpoint for ticker streaming with multiplexed subscriptions"""
    client_info = f"{websocket.client.host}:{websocket.client.port}" if websocket.client else "unknown"
    logger.info(f"🔌 WebSocket connection attempt from {client_info}")
    logger.info(f"🔌 WebSocket object ID: {id(websocket)}")
    
    await stream_manager.connect(websocket)
    logger.info(f"✅ WebSocket connected successfully from {client_info}")
    
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
                        stream_manager.subscribe_to_market(websocket, market_id)
                        await websocket.send_text(json.dumps({
                            'type': 'subscription_confirmed',
                            'subscription': 'market',
                            'market_id': market_id,
                            'platform': platform,
                            'timestamp': time.time()
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
                    platform = message.get('platform', 'unknown')
                    if market_id:
                        stream_manager.unsubscribe_from_market(websocket, market_id)
                        await websocket.send_text(json.dumps({
                            'type': 'unsubscription_confirmed',
                            'subscription': 'market',
                            'market_id': market_id,
                            'platform': platform,
                            'timestamp': time.time()
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
        logger.info(f"🔌 WebSocket disconnected: {client_info} (ID: {id(websocket)})")
    except Exception as e:
        logger.error(f"💥 Unexpected WebSocket error: {e} for {client_info} (ID: {id(websocket)})")
    finally:
        logger.info(f"🧹 Cleaning up WebSocket connection: {client_info} (ID: {id(websocket)})")
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
        #Write the raw request to a temp file that I can access later on W

        validate_market_request(
            request.platform,
            request.market_identifier,
            token_ids = locals().get("token_ids") or ""
        )
        logger.info(f"✅ Request validation passed")
        
        # Generate standardized market ID
        market_id = generate_market_id(request.platform, request.market_identifier, token_ids = locals().get("token_ids") or "")
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
        connection_result = await handle_market_connection(request.platform, market_id)
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

@app.get("/api/kalshi/candlesticks", response_model=KalshiCandlestickResponse)
async def get_kalshi_candlesticks(
    market_string_id: str = Query(..., description="Market string in format: ticker&side&range"),
    start_ts: int = Query(..., description="Start timestamp (Unix seconds)"),
    end_ts: int = Query(..., description="End timestamp (Unix seconds)")
):
    """
    Fetch historical candlestick data from Kalshi API
    
    This endpoint:
    1. Parses market_string_id to extract ticker, side, and range
    2. Maps time range to Kalshi period intervals (1H→1min, 1W→60min, 1M→1440min)
    3. Extracts series ticker from market ticker (split by - or _, take first part)
    4. Calls Kalshi candlesticks API with proper parameters
    5. Processes and returns standardized candlestick data
    
    Example usage:
    GET /api/kalshi/candlesticks?market_string_id=PRES24-DJT-Y&side&1H&start_ts=1750966620&end_ts=1750970220
    """
    start_time = time.time()
    
    try:
        logger.info(f"📥 Kalshi candlesticks request: market_string_id={market_string_id}, start_ts={start_ts}, end_ts={end_ts}")
        
        # Parse market string ID
        market_info = parse_market_string_id(market_string_id)
        logger.info(f"🔍 Parsed market info: {market_info}")
        
        # Map time range to period interval
        period_interval = map_time_range_to_period_interval(market_info["range"])
        logger.info(f"🕐 Mapped range '{market_info['range']}' to period_interval: {period_interval}")
        
        # Fetch candlestick data from Kalshi
        raw_data = await fetch_kalshi_candlesticks(
            series_ticker=market_info["series_ticker"],
            market_ticker=market_info["market_ticker"],
            start_ts=start_ts,
            end_ts=end_ts,
            period_interval=period_interval
        )
        
        # Process the raw data
        processed_data = process_kalshi_candlesticks(raw_data, market_info)
        
        elapsed_time = time.time() - start_time
        logger.info(f"✅ Kalshi candlesticks request completed successfully (took {elapsed_time:.3f}s)")
        
        return KalshiCandlestickResponse(
            success=True,
            data=processed_data,
            market_info={
                "market_ticker": market_info["market_ticker"],
                "series_ticker": market_info["series_ticker"],
                "side": market_info["side"],
                "range": market_info["range"],
                "period_interval": str(period_interval),
                "request_duration_seconds": f"{elapsed_time:.3f}"
            }
        )
        
    except ValueError as e:
        elapsed_time = time.time() - start_time
        logger.warning(f"⚠️ Kalshi candlesticks validation error: {e} (took {elapsed_time:.3f}s)")
        raise HTTPException(status_code=400, detail=str(e))
        
    except HTTPException:
        # Re-raise HTTP exceptions from helper functions
        raise
        
    except Exception as e:
        elapsed_time = time.time() - start_time
        logger.error(f"💥 Unexpected error in Kalshi candlesticks: {e} (took {elapsed_time:.3f}s)")
        logger.error(f"💥 Full exception details:", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error while fetching candlestick data")

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

'''
Add polymarket historical timeseries generation endpoint

'''
@app.get("/api/polymarket/timeseries")
async def get_polymarket_timeseries( market_string_id: str = Query(..., description="Market string in format: ticker&side&range"),
    start_ts: int = Query(..., description="Start timestamp (Unix seconds)"),
    end_ts: int = Query(..., description="End timestamp (Unix seconds)")):

    """
    Fetch historical timeseries data from Polymarket API
    
    This endpoint:
    1. Parses market_string_id to extract ticker, side, and range
    2. Maps time range to Kalshi period intervals (1H→1m, 1W->1hr, 1M→1d)
    3. Extracts series ticker from market ticker (split by - or _, take first part)
    4. Calls Polymarket timeseries API with proper parameters
    5. Processes and returns standardized timeseries data
    
    Example usage:
    GET /api/kalshi/candlesticks?market_string_id=PRES24-DJT-Y&side&1H&start_ts=1750966620&end_ts=1750970220
    """
    start_time = time.time()
    try:

        poly_yes_no_candlesticks = await fetch_polymarket_timeseries(
            market_string_id,
            start_ts,
            end_ts
        )

        return KalshiCandlestickResponse(
            success=True,
            data=poly_yes_no_candlesticks,
            market_info={
            }
        )

    except ValueError as e:
        elapsed_time = time.time() - start_time
        logger.warning(f"⚠️ Kalshi candlesticks validation error: {e} (took {elapsed_time:.3f}s)")
        raise HTTPException(status_code=400, detail=str(e))
        
    except HTTPException:
        # Re-raise HTTP exceptions from helper functions
        raise
        
    except Exception as e:
        elapsed_time = time.time() - start_time
        logger.error(f"💥 Unexpected error in Kalshi candlesticks: {e} (took {elapsed_time:.3f}s)")
        logger.error(f"💥 Full exception details:", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error while fetching candlestick data")

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
    # Use global channel manager directly to ensure same instance
    from backend.global_manager import global_channel_manager
    await global_channel_manager.broadcast_ticker_update(ticker_data)

async def publish_arbitrage_alert(alert_data: dict):
    """
    Publish arbitrage alert to WebSocket clients
    
    Expected format:
    {
        "type": "arbitrage_alert",
        "market_pair": "some_market_pair",
        "timestamp": "ISO timestamp",
        "spread": float,
        "direction": "kalshi_to_polymarket" or "polymarket_to_kalshi",
        "side": "yes" or "no",
        "kalshi_price": float,
        "polymarket_price": float,
        "kalshi_market_id": int,
        "polymarket_asset_id": str,
        "confidence": float
    }
    """
    # Use global channel manager directly to ensure same instance
    from backend.global_manager import global_channel_manager
    await global_channel_manager.broadcast_arbitrage_alert(alert_data)

if __name__ == "__main__":
    uvicorn.run(
        "websocket_server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )