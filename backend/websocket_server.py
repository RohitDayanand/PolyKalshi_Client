"""
FastAPI WebSocket server for streaming cleaned ticker updates
"""
import asyncio
import json
import logging
import multiprocessing as mp
import re
import time
import uuid
from typing import Dict, Optional, List, Any
from datetime import datetime
from dataclasses import asdict
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
        logging.StreamHandler(),  # Console output - this is for development
        #logging.FileHandler('/home/rohit/Websocket_Polymarket_Kalshi/backend/websocket_debug.log', mode='w')  # File output
    ]
)
logger = logging.getLogger(__name__)
logger.info("📝 Logging to both console and websocket_debug.log")

# Global multiprocessing queues for arbitrage trading process
arbitrage_alert_queue: Optional[mp.Queue] = None
trading_result_queue: Optional[mp.Queue] = None
trading_process: Optional[mp.Process] = None

# Pydantic models for API requests/responses
class MarketSubscriptionRequest(BaseModel):
    platform: str = Field(..., description="Platform name: 'polymarket' or 'kalshi'")
    market_identifier: str = Field(..., description="Token ID for Polymarket or market slug for Kalshi")
    client_id: Optional[str] = Field(None, description="Optional client identifier")
    isRemove: bool = False #will this mess with the pydantic model

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

class ArbitrageSettingsRequest(BaseModel):
    """Request model for updating arbitrage settings."""
    min_spread_threshold: Optional[float] = Field(None, ge=0.0, le=1.0, description="Minimum spread threshold (0.0-1.0)")
    min_trade_size: Optional[float] = Field(None, ge=0.0, description="Minimum trade size threshold")
    source: Optional[str] = Field("api", description="Source of the settings change")

class ArbitrageSettingsResponse(BaseModel):
    """Response model for arbitrage settings operations."""
    success: bool
    message: str
    old_settings: Optional[Dict[str, Any]] = None
    new_settings: Optional[Dict[str, Any]] = None
    changed_fields: Optional[List[str]] = None
    errors: Optional[List[str]] = None

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

# Global subscription lock to prevent concurrent subscription operations across all clients
subscription_lock = asyncio.Lock()

# Global arbitrage settings lock to prevent concurrent settings operations
arbitrage_settings_lock = asyncio.Lock()

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


# Global MarketsCoordinator instance (initialized on app startup)
markets_coordinator = None

async def initialize_markets_coordinator():
    """Initialize MarketsCoordinator during app startup when event loop is available"""
    global markets_coordinator
    try:
        from backend.master_manager.markets_coordinator import MarketsCoordinator
        markets_coordinator = MarketsCoordinator()
        logger.info("MarketsCoordinator initialized successfully")
        return True
    except ImportError as e:
        logger.error(f"Failed to import MarketsCoordinator: {e}")
        return False
    except Exception as e:
        logger.error(f"Failed to initialize MarketsCoordinator: {e}")
        return False

async def initialize_redis_publisher_background():
    """Initialize Redis publisher in background task to avoid blocking startup."""
    try:
        from backend.master_manager.trading_engine.redis_arbitrage_bridge import initialize_redis_publisher
        
        logger.info("🔄 Initializing Redis arbitrage publisher in background...")
        
        # Try to connect to Redis with retries
        max_retries = 3
        retry_delay = 2.0
        
        for attempt in range(max_retries):
            try:
                redis_url = "redis://localhost:6379/0"  # TODO: Load from config
                success = await initialize_redis_publisher(redis_url)
                
                if success:
                    logger.info("✅ Redis arbitrage publisher initialized successfully")
                    return
                else:
                    logger.warning(f"⚠️ Redis publisher initialization failed (attempt {attempt + 1}/{max_retries})")
                    
            except Exception as e:
                logger.error(f"❌ Redis connection error (attempt {attempt + 1}/{max_retries}): {e}")
            
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
                retry_delay *= 1.5  # Exponential backoff
        
        logger.error("❌ Failed to initialize Redis publisher after all retries - arbitrage alerts will not be published")
        
    except ImportError as e:
        logger.error(f"❌ Failed to import Redis bridge module: {e}")
    except Exception as e:
        logger.error(f"❌ Unexpected error initializing Redis publisher: {e}")

async def handle_market_connection(platform: str, market_id: str, optionalRemoveMarket = False) -> Dict[str, any]:
    """
    Handle market connection via MarketsCoordinator
    
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
        
        # Connect via MarketsCoordinator
        if markets_coordinator is None:
            logger.error("MarketsCoordinator not available - cannot establish market connection")
            connection_state_manager.update_status(market_id, "failed", "MarketsCoordinator not available")
            success = False
        elif optionalRemoveMarket:
            logger.info(f"Starting disconnection for {platform} market: {market_id}")
            
            # STEP 1: Clean frontend subscriptions FIRST (immediate user effect)
            from backend.global_manager import global_channel_manager
            cache_cleaned = global_channel_manager.remove_market_from_cache(market_id)
            logger.info(f"Frontend subscriptions cleaned for {market_id}: {cache_cleaned}")
            
            # STEP 2: Clean backend connections SECOND (async)
            logger.info(f"Disconnecting {platform} market via MarketsCoordinator: {market_id}")
            backend_success = await markets_coordinator.disconnect(market_id, platform)
            logger.info(f"Backend disconnection for {market_id}: {backend_success}")
            
            # Overall success requires at least one step to succeed
            success = cache_cleaned or backend_success
        else:
            # Call MarketsCoordinator.connect() with proper parameters
            logger.info(f"Connecting to {platform} market via MarketsCoordinator: {market_id}")
            success = await markets_coordinator.connect(market_id, platform)
            
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
    
    # Initialize MarketsCoordinator
    success = await initialize_markets_coordinator()
    if success:
        logger.info("✅ MarketsCoordinator ready for market connections")
        
        # Start MarketsCoordinator async components (queues and ticker publishers)
        try:
            await markets_coordinator.start_async_components()
            logger.info("✅ MarketsCoordinator ticker publishers started")
        except Exception as e:
            logger.error(f"❌ Failed to start MarketsCoordinator async components: {e}")
    else:
        logger.warning("⚠️ MarketsCoordinator not available - market connections will fail")
    
    # Initialize Redis publisher as background task (non-blocking)
    asyncio.create_task(initialize_redis_publisher_background())
    
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
    2. Establishes backend connection via lightweight markets coordinator
    3. Returns standardized market_id for WebSocket subscription
    4. Tracks connection state for status monitoring
    
    After calling this endpoint, frontend should:
    1. Connect to WebSocket at returned websocket_url
    2. Send subscription message with returned market_id
    3. Start receiving real-time ticker updates
    
    Note: This endpoint is protected by a server-wide lock to prevent
    concurrent subscription operations from multiple clients.
    """
    
    # Acquire global subscription lock to serialize all subscription requests
    async with subscription_lock:
        logger.info(f"🔒 Acquired subscription lock for {request.platform}:{request.market_identifier}")
        
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
            
            if existing_state and existing_state["status"] == "connected" and not request.isRemove:
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

            #Check if it is a remove request - and if so remove it
            if request.isRemove:
                connection_result = await handle_market_connection(request.platform, market_id, optionalRemoveMarket=True)
            else:
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
        
        finally:
            logger.info(f"🔓 Released subscription lock for {request.platform}:{request.market_identifier}")

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
@app.post("/api/arbitrage/settings", response_model=ArbitrageSettingsResponse)
async def update_arbitrage_settings(request: ArbitrageSettingsRequest):
    """
    Update arbitrage settings dynamically with proper async request-response pattern.
    
    This endpoint:
    1. Validates request parameters using Pydantic
    2. Generates correlation ID for request tracking
    3. Publishes arbitrage.settings_changed event with correlation ID
    4. Awaits response events (arbitrage.settings_updated or arbitrage.settings_error)
    5. Returns success/error response based on ArbitrageManager's actual processing
    
    The ArbitrageManager subscribes to the event and handles:
    - Settings validation and atomic updates
    - Updating ArbitrageDetector thresholds
    - Publishing correlation-matched response events
    
    Parameters (all optional - partial updates supported):
    - min_spread_threshold: Float 0.0-1.0 (e.g., 0.03 = 3% minimum spread)
    - min_trade_size: Float >= 0.0 (minimum trade size threshold)
    - source: String identifying the update source
    
    Note: This endpoint is protected by a server-wide lock to prevent
    concurrent arbitrage settings operations from multiple clients.
    """
    # Acquire global arbitrage settings lock to serialize all settings requests
    async with arbitrage_settings_lock:
        logger.info(f"🔒 Acquired arbitrage settings lock for request from {request.source}")
        
        try:
            # Import global event bus
            from backend.master_manager.events.event_bus import global_event_bus
            
            # Extract only non-None fields for partial updates
            settings_update = {}
            if request.min_spread_threshold is not None:
                settings_update['min_spread_threshold'] = request.min_spread_threshold
            if request.min_trade_size is not None:
                settings_update['min_trade_size'] = request.min_trade_size
            
            if not settings_update:
                return ArbitrageSettingsResponse(
                    success=False,
                    message="No settings provided for update",
                    errors=["Request must include at least one setting to update"]
                )
            
            # Generate unique correlation ID for this request
            correlation_id = str(uuid.uuid4())
            logger.info(f"🎯 Arbitrage settings update request {correlation_id} from {request.source}: {settings_update}")
            
            # Create future to await the response
            response_future = asyncio.Future()
            
            # Response handler for success events
            async def handle_success(event_data: Dict[str, Any]):
                if event_data.get('correlation_id') == correlation_id:
                    logger.info(f"✅ Received success response for {correlation_id}")
                    response_future.set_result(('success', event_data))
                    
            # Response handler for error events
            async def handle_error(event_data: Dict[str, Any]):
                if event_data.get('correlation_id') == correlation_id:
                    logger.info(f"❌ Received error response for {correlation_id}")
                    response_future.set_result(('error', event_data))
            
            # Subscribe to response events
            global_event_bus.subscribe('arbitrage.settings_updated', handle_success)
            global_event_bus.subscribe('arbitrage.settings_error', handle_error)
            
            try:
                # Publish request with correlation ID
                await global_event_bus.publish('arbitrage.settings_changed', {
                    'settings': settings_update,
                    'source': request.source or 'api',
                    'correlation_id': correlation_id,
                    'timestamp': datetime.now().isoformat()
                })
                
                logger.info(f"📤 Published settings change event with correlation ID: {correlation_id}")
                
                # Wait for response with timeout
                try:
                    result_type, result_data = await asyncio.wait_for(response_future, timeout=10.0)
                    
                    if result_type == 'success':
                        logger.info(f"🎉 Settings update {correlation_id} successful")
                        return ArbitrageSettingsResponse(
                            success=True,
                            message="Settings updated successfully by ArbitrageManager",
                            old_settings=result_data.get('old_settings'),
                            new_settings=result_data.get('new_settings'),
                            changed_fields=result_data.get('changed_fields')
                        )
                    else:
                        # ArbitrageManager rejected the settings
                        logger.warning(f"⚠️ Settings update {correlation_id} rejected: {result_data.get('errors')}")
                        return ArbitrageSettingsResponse(
                            success=False,
                            message="Settings update rejected by ArbitrageManager",
                            errors=result_data.get('errors', ['Unknown rejection reason'])
                        )
                        
                except asyncio.TimeoutError:
                    logger.error(f"⏰ Settings update {correlation_id} timed out")
                    return ArbitrageSettingsResponse(
                        success=False,
                        message="Settings update request timed out",
                        errors=["ArbitrageManager did not respond within 10 seconds - may be offline or busy"]
                    )
                    
            finally:
                # Always cleanup subscriptions to prevent memory leaks
                try:
                    global_event_bus.unsubscribe('arbitrage.settings_updated', handle_success)
                    global_event_bus.unsubscribe('arbitrage.settings_error', handle_error)
                    logger.debug(f"🧹 Cleaned up event subscriptions for {correlation_id}")
                except Exception as cleanup_error:
                    logger.warning(f"Warning: Failed to cleanup event subscriptions: {cleanup_error}")
                
        except Exception as e:
            logger.error(f"❌ Unexpected error in settings update endpoint: {e}")
            return ArbitrageSettingsResponse(
                success=False,
                message=f"Internal server error: {str(e)}",
                errors=[f"Unexpected error: {str(e)}"]
            )
        
        finally:
            logger.info(f"🔓 Released arbitrage settings lock for request from {request.source}")

@app.get("/api/arbitrage/settings")
async def get_arbitrage_settings():
    """
    Get current arbitrage settings.
    
    Note: This is a placeholder endpoint. In a full implementation,
    you would access the ArbitrageManager instance to get current settings.
    """
    try:
        logger.info("📖 Arbitrage settings requested")
        
        return {
            "message": "Settings retrieval via direct ArbitrageManager access not yet implemented",
            "suggestion": "Use POST /api/arbitrage/settings to update settings via EventBus",
            "default_settings": {
                "min_spread_threshold": 0.05,
                "min_trade_size": 10.0
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Error retrieving arbitrage settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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
    Publish arbitrage alert to WebSocket clients via the global ChannelManager.
    
    This function serves as the final step in the arbitrage alert pipeline before 
    reaching frontend clients. It converts the alert_data from the EventBus format
    to the WebSocket message format expected by frontend components.
    
    Data transformation:
    - Input: EventBus alert_data with 'alert' key containing ArbitrageOpportunity
    - Output: WebSocket message with 'type': 'arbitrage_alert' and flattened data
    
    Expected input format (from MarketsCoordinator):
    {
        "alert": ArbitrageOpportunity,  # dataclass instance
        "market_pair": "PRES24-DJT", 
        "spread": 0.035,
        "direction": "kalshi_to_polymarket",
        "timestamp": "2025-01-15T10:30:00Z"
    }
    
    WebSocket message format sent to frontend:
    {
        "type": "arbitrage_alert",
        "market_pair": "PRES24-DJT",
        "timestamp": "2025-01-15T10:30:00Z", 
        "spread": 0.035,
        "direction": "kalshi_to_polymarket",
        "side": "yes",
        "kalshi_price": 0.520,
        "polymarket_price": 0.480,
        "kalshi_market_id": 12345,
        "polymarket_asset_id": "asset_abc123",
        "confidence": 1.0,
        "execution_size": 100.0,
        "execution_info": {...}
    }
    
    Args:
        alert_data (dict): Alert data from EventBus containing ArbitrageOpportunity
    """
    # Use global channel manager for WebSocket broadcasting
    from backend.global_manager import global_channel_manager
    await global_channel_manager.broadcast_arbitrage_alert(alert_data)
    
    # Publish to Redis for external trading processes (fire-and-forget)
    try:
        from backend.master_manager.trading_engine.redis_arbitrage_bridge import publish_arbitrage_alert_to_redis
        
        # Extract ArbitrageOpportunity from alert_data and serialize
        opportunity = alert_data.get("alert")  # This should be the ArbitrageOpportunity dataclass
        
        if opportunity:
            # Convert dataclass to dict for Redis publishing
            redis_alert_data = {
                "market_pair": opportunity.market_pair,
                "side": opportunity.side,
                "spread": opportunity.spread,
                "direction": opportunity.direction,
                "kalshi_price": opportunity.kalshi_price,
                "polymarket_price": opportunity.polymarket_price,
                "kalshi_market_id": opportunity.kalshi_market_id,
                "polymarket_asset_id": opportunity.polymarket_asset_id,
                "confidence": opportunity.confidence,
                "execution_size": opportunity.execution_size,
                "execution_info": opportunity.execution_info,
                "timestamp": alert_data.get("timestamp", datetime.now().isoformat())
            }
            
            # Fire-and-forget Redis publish (don't await to avoid blocking)
            asyncio.create_task(publish_arbitrage_alert_to_redis(redis_alert_data))
            logger.debug(f"🚀 Dispatched arbitrage alert to Redis | market={opportunity.market_pair} | spread={opportunity.spread:.3f}")
        
    except Exception as e:
        # Don't let Redis errors break the main alert flow
        logger.warning(f"⚠️ Failed to publish arbitrage alert to Redis: {e}")

if __name__ == "__main__":
    uvicorn.run(
        "websocket_server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )