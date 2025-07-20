"""
Mock Polymarket WebSocket Server for Testing

Replicates the exact message format and behavior of the real Polymarket WebSocket API.
Supports the 4 message types that PolymarketMessageProcessor expects:
- book: Full orderbook snapshot
- price_change: Price level updates  
- tick_size_change: Minimum tick size changes
- last_trade_price: Trade price updates
"""

import asyncio
import json
import logging
import time
import random
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import websockets
from websockets.server import WebSocketServerProtocol
from datetime import datetime, timedelta

logger = logging.getLogger()

@dataclass
class MockOrderbookLevel:
    """Represents a single orderbook level"""
    price: str  # Price as string (e.g., "0.64")
    size: str   # Size as string (e.g., "100.5")

@dataclass
class MockMarketState:
    """Tracks market state for generating realistic updates"""
    asset_id: str
    market_slug: str
    last_price: float = 0.5
    bid_levels: List[MockOrderbookLevel] = None
    ask_levels: List[MockOrderbookLevel] = None
    min_tick_size: float = 0.01
    last_update: datetime = None
    
    def __post_init__(self):
        if self.bid_levels is None:
            self.bid_levels = []
        if self.ask_levels is None:
            self.ask_levels = []
        if self.last_update is None:
            self.last_update = datetime.now()

class MockPolymarketServer:
    """
    Mock Polymarket WebSocket server that replicates real API behavior.
    
    Subscription format matches real API:
    {"auth": "", "channel": "book", "market": "asset_id"}
    
    Message formats exactly match real Polymarket responses.
    """
    
    def __init__(self, host: str = "localhost", port: int = 8001):
        self.host = host
        self.port = port
        self.connected_clients: Dict[WebSocketServerProtocol, Dict[str, Any]] = {}
        self.market_states: Dict[str, MockMarketState] = {}
        self.server = None
        self.update_task: Optional[asyncio.Task] = None
        
        # Initialize sample markets with realistic data
        self._initialize_sample_markets()
        
        logger.info(f"MockPolymarketServer initialized on {host}:{port}")
    
    def _initialize_sample_markets(self):
        """Initialize sample markets with realistic orderbook data"""
        sample_markets = [
            {
                "asset_id": "75505728818237076147318796536066812362152358606307154083407489467059230821371",
                "market_slug": "will-trump-win-2024-election-yes",
                "initial_price": 0.65
            },
            {
                "asset_id": "67369669271127885658944531351746308398542291270457462650056001798232262328240", 
                "market_slug": "will-trump-win-2024-election-no",
                "initial_price": 0.35
            },
            {
                "asset_id": "test_token_123",
                "market_slug": "test-market-yes",
                "initial_price": 0.50
            }
        ]
        
        for market in sample_markets:
            asset_id = market["asset_id"]
            initial_price = market["initial_price"]
            
            # Generate realistic bid/ask levels around initial price
            bid_levels = []
            ask_levels = []
            
            # Create 5 bid levels below current price
            for i in range(5):
                price = initial_price - (i + 1) * 0.01
                if price > 0:
                    size = random.uniform(50, 500)
                    bid_levels.append(MockOrderbookLevel(
                        price=f"{price:.3f}",
                        size=f"{size:.2f}"
                    ))
            
            # Create 5 ask levels above current price  
            for i in range(5):
                price = initial_price + (i + 1) * 0.01
                if price < 1.0:
                    size = random.uniform(50, 500)
                    ask_levels.append(MockOrderbookLevel(
                        price=f"{price:.3f}",
                        size=f"{size:.2f}"
                    ))
            
            self.market_states[asset_id] = MockMarketState(
                asset_id=asset_id,
                market_slug=market["market_slug"],
                last_price=initial_price,
                bid_levels=bid_levels,
                ask_levels=ask_levels
            )
            
            logger.info(f"Initialized mock market {asset_id} at price {initial_price}")
    
    async def start(self):
        """Start the mock WebSocket server"""
        logger.info(f"Starting MockPolymarketServer on {self.host}:{self.port}")
        logger.info(f"checkign if self is bounded, {self._handle_connection} ")
        self.server = await websockets.serve(
            self._handle_connection,
            self.host,
            self.port,
            ping_interval=30,
            ping_timeout=10
        )

        # Start background task for periodic market updates
        self.update_task = asyncio.create_task(self._periodic_updates())

        logger.info(f"MockPolymarketServer started successfully")
        return self.server
    
    async def stop(self):
        """Stop the mock server"""
        logger.info("Stopping MockPolymarketServer")
        
        if self.update_task:
            self.update_task.cancel()
            try:
                await self.update_task
            except asyncio.CancelledError:
                pass
        
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        
        logger.info("MockPolymarketServer stopped")
    
    #what is the path var
    async def _handle_connection(self, websocket: WebSocketServerProtocol):
        """Handle new WebSocket connection"""
        client_info = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        logger.info(f"New connection from {client_info}")
        
        self.connected_clients[websocket] = {
            "subscriptions": set(),
            "connected_at": datetime.now()
        }
        
        try:
            async for message in websocket:
                await self._handle_message(websocket, message)
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Connection closed: {client_info}")
        except Exception as e:
            logger.error(f"Error handling connection {client_info}: {e}")
        finally:
            if websocket in self.connected_clients:
                del self.connected_clients[websocket]
    
    async def _handle_message(self, websocket: WebSocketServerProtocol, message: str):
        """Handle incoming WebSocket message"""
        try:
            data = json.loads(message)
            logger.debug(f"Received message: {data}")
            
            # Handle subscription messages
            if data.get("channel") == "book":
                await self._handle_book_subscription(websocket, data)
            else:
                logger.warning(f"Unknown message type: {data}")
                
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON received: {e}")
        except Exception as e:
            logger.error(f"Error handling message: {e}")
    
    async def _handle_book_subscription(self, websocket: WebSocketServerProtocol, data: Dict[str, Any]):
        """Handle book channel subscription"""
        asset_id = data.get("market")
        if not asset_id:
            logger.warning("No market specified in book subscription")
            return
        
        # Add to client subscriptions
        self.connected_clients[websocket]["subscriptions"].add(asset_id)
        logger.info(f"Client subscribed to market {asset_id}")
        
        # Send initial book snapshot if market exists
        if asset_id in self.market_states:
            await self._send_book_snapshot(websocket, asset_id)
        else:
            logger.warning(f"Unknown market requested: {asset_id}")
    
    async def _send_book_snapshot(self, websocket: WebSocketServerProtocol, asset_id: str):
        """Send full orderbook snapshot to client"""
        market = self.market_states[asset_id]
        
        # Format bid levels (descending price order)
        bids = []
        for level in sorted(market.bid_levels, key=lambda x: float(x.price), reverse=True):
            bids.append([level.price, level.size])
        
        # Format ask levels (ascending price order)
        asks = []
        for level in sorted(market.ask_levels, key=lambda x: float(x.price)):
            asks.append([level.price, level.size])
        
        # Create book message in exact Polymarket format
        book_message = {
            "event_type": "book",
            "asset_id": asset_id,
            "market": market.market_slug,
            "timestamp": int(time.time()),
            "bids": bids,
            "asks": asks
        }
        
        try:
            await websocket.send(json.dumps(book_message))
            logger.debug(f"Sent book snapshot for {asset_id}: {len(bids)} bids, {len(asks)} asks")
        except Exception as e:
            logger.error(f"Error sending book snapshot: {e}")
    
    async def _periodic_updates(self):
        """Send periodic market updates to simulate real market activity"""
        while True:
            try:
                await asyncio.sleep(random.uniform(2, 8))  # Random intervals 2-8 seconds
                
                if not self.connected_clients:
                    continue
                
                # Pick a random market to update
                asset_ids = list(self.market_states.keys())
                if not asset_ids:
                    continue
                
                asset_id = random.choice(asset_ids)
                await self._generate_market_update(asset_id)
                
            except asyncio.CancelledError:
                logger.info("Periodic updates cancelled")
                break
            except Exception as e:
                logger.error(f"Error in periodic updates: {e}")
    
    async def _generate_market_update(self, asset_id: str):
        """Generate and send a random market update"""
        if asset_id not in self.market_states:
            return
        
        market = self.market_states[asset_id]
        
        # Get clients subscribed to this market
        subscribed_clients = [
            ws for ws, client_data in self.connected_clients.items()
            if asset_id in client_data["subscriptions"]
        ]
        
        if not subscribed_clients:
            return
        
        # Choose random update type
        update_type = random.choice(["price_change", "tick_size_change", "last_trade_price"])
        
        if update_type == "price_change":
            await self._send_price_change(subscribed_clients, asset_id)
        elif update_type == "tick_size_change":
            await self._send_tick_size_change(subscribed_clients, asset_id)
        elif update_type == "last_trade_price":
            await self._send_last_trade_price(subscribed_clients, asset_id)
    
    async def _send_price_change(self, clients: List[WebSocketServerProtocol], asset_id: str):
        """Send price_change message"""
        market = self.market_states[asset_id]
        
        # Randomly update a bid or ask level
        is_bid = random.choice([True, False])
        
        if is_bid and market.bid_levels:
            # Update a bid level
            level_idx = random.randint(0, len(market.bid_levels) - 1)
            old_level = market.bid_levels[level_idx]
            
            # Small price/size change
            new_price = max(0.001, float(old_level.price) + random.uniform(-0.005, 0.005))
            new_size = max(0, float(old_level.size) + random.uniform(-50, 50))
            
            market.bid_levels[level_idx] = MockOrderbookLevel(
                price=f"{new_price:.3f}",
                size=f"{new_size:.2f}"
            )
            
            side = "bid"
            price = f"{new_price:.3f}"
            size = f"{new_size:.2f}"
            
        elif market.ask_levels:
            # Update an ask level
            level_idx = random.randint(0, len(market.ask_levels) - 1)
            old_level = market.ask_levels[level_idx]
            
            # Small price/size change
            new_price = min(0.999, float(old_level.price) + random.uniform(-0.005, 0.005))
            new_size = max(0, float(old_level.size) + random.uniform(-50, 50))
            
            market.ask_levels[level_idx] = MockOrderbookLevel(
                price=f"{new_price:.3f}",
                size=f"{new_size:.2f}"
            )
            
            side = "ask"
            price = f"{new_price:.3f}"
            size = f"{new_size:.2f}"
        else:
            return
        
        # Create price_change message in exact Polymarket format
        price_change_message = {
            "event_type": "price_change",
            "asset_id": asset_id,
            "market": market.market_slug,
            "timestamp": int(time.time()),
            "side": side,
            "price": price,
            "size": size
        }
        
        # Send to all subscribed clients
        for client in clients:
            try:
                await client.send(json.dumps(price_change_message))
                logger.debug(f"Sent price_change for {asset_id}: {side} {price} @ {size}")
            except Exception as e:
                logger.error(f"Error sending price_change: {e}")
    
    async def _send_tick_size_change(self, clients: List[WebSocketServerProtocol], asset_id: str):
        """Send tick_size_change message"""
        market = self.market_states[asset_id]
        
        # Simulate temporary tick size change
        new_tick_size = random.choice([0.001, 0.005, 0.01])
        market.min_tick_size = new_tick_size
        
        tick_change_message = {
            "event_type": "tick_size_change",
            "asset_id": asset_id,
            "market": market.market_slug,
            "timestamp": int(time.time()),
            "tick_size": f"{new_tick_size:.3f}"
        }
        
        # Send to all subscribed clients
        for client in clients:
            try:
                await client.send(json.dumps(tick_change_message))
                logger.debug(f"Sent tick_size_change for {asset_id}: {new_tick_size}")
            except Exception as e:
                logger.error(f"Error sending tick_size_change: {e}")
    
    async def _send_last_trade_price(self, clients: List[WebSocketServerProtocol], asset_id: str):
        """Send last_trade_price message"""
        market = self.market_states[asset_id]
        
        # Small random price movement
        price_change = random.uniform(-0.02, 0.02)
        new_price = max(0.001, min(0.999, market.last_price + price_change))
        market.last_price = new_price
        
        trade_message = {
            "event_type": "last_trade_price",
            "asset_id": asset_id,
            "market": market.market_slug,
            "timestamp": int(time.time()),
            "price": f"{new_price:.3f}"
        }
        
        # Send to all subscribed clients
        for client in clients:
            try:
                await client.send(json.dumps(trade_message))
                logger.debug(f"Sent last_trade_price for {asset_id}: {new_price}")
            except Exception as e:
                logger.error(f"Error sending last_trade_price: {e}")
    
    def add_market(self, asset_id: str, market_slug: str, initial_price: float = 0.5):
        """Add a new market for testing"""
        if asset_id not in self.market_states:
            self.market_states[asset_id] = MockMarketState(
                asset_id=asset_id,
                market_slug=market_slug,
                last_price=initial_price
            )
            logger.info(f"Added mock market {asset_id} at price {initial_price}")
    
    def get_market_state(self, asset_id: str) -> Optional[MockMarketState]:
        """Get current market state for testing"""
        return self.market_states.get(asset_id)

# Standalone server runner for testing
'''
async def main():
    """Run the mock server standalone for testing"""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    server = MockPolymarketServer(port=8001)
    await server.start()
    
    logger.info("Mock Polymarket server running on ws://localhost:8001")
    logger.info("Test subscription: {'auth': '', 'channel': 'book', 'market': 'test_token_123'}")
    
    try:
        # Keep running
        await asyncio.Future()  # Run forever
    except KeyboardInterrupt:
        logger.info("Shutting down mock server")
        await server.stop()

if __name__ == "__main__":
    asyncio.run(main())
'''