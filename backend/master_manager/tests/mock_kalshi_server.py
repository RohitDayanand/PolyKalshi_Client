"""
Mock Kalshi WebSocket Server for Testing

Replicates the exact message format and behavior of the real Kalshi WebSocket API.
Supports the 5 message types that KalshiMessageProcessor expects:
- error: Error messages
- ok: Subscription confirmations
- orderbook_snapshot: Full orderbook state
- orderbook_delta: Incremental orderbook updates  
- ticker_v2: Price/volume ticker updates
"""

import asyncio
import json
import logging
import time
import random
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, field
import websockets
from websockets.server import WebSocketServerProtocol
from datetime import datetime, timedelta

logger = logging.getLogger()

@dataclass
class MockOrderbookLevel:
    """Represents a single orderbook level"""
    price: str  # Price as string (e.g., "64")
    size: int   # Size as integer

@dataclass
class MockKalshiMarket:
    """Tracks market state for generating realistic updates"""
    sid: int
    market_ticker: str
    
    # Current ticker state (1-99 cents)
    last_price: Optional[int] = 65
    yes_bid: Optional[int] = 64
    yes_ask: Optional[int] = 66
    volume: int = 1000
    open_interest: int = 5000
    dollar_volume: int = 50000
    dollar_open_interest: int = 250000
    
    # Orderbook levels (all outstanding orders for yes and no)
    yes: Dict[str, MockOrderbookLevel] = field(default_factory=dict)  # price -> level
    no: Dict[str, MockOrderbookLevel] = field(default_factory=dict)   # price -> level
    
    # Tracking
    last_seq: int = 1000
    last_update: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        if not self.yes and not self.no:
            self._initialize_orderbook()

    def _initialize_orderbook(self):
        """Initialize realistic orderbook around current yes_bid/yes_ask"""
        if self.yes_bid is None or self.yes_ask is None:
            return

        # Create yes levels (bids below yes_ask, asks above yes_bid, all in one dict)
        for i in range(5):
            price = self.yes_bid - i
            if price >= 1:
                size = random.randint(50, 200)
                self.yes[str(price)] = MockOrderbookLevel(price=str(price), size=size)
        for i in range(5):
            price = self.yes_ask + i
            if price <= 99:
                size = random.randint(50, 200)
                self.yes[str(price)] = MockOrderbookLevel(price=str(price), size=size)

        # Create no levels (complement of yes, all in one dict)
        for yes_price in self.yes:
            no_price = 100 - int(yes_price)
            if 1 <= no_price <= 99:
                size = random.randint(50, 200)
                self.no[str(no_price)] = MockOrderbookLevel(price=str(no_price), size=size)

class MockKalshiServer:
    """
    Mock Kalshi WebSocket server that replicates real API behavior.
    
    Handles authentication, subscriptions, and sends realistic market updates.
    """
    
    def __init__(self, host: str = "localhost", port: int = 8002):
        self.host = host
        self.port = port
        self.connected_clients: Dict[WebSocketServerProtocol, Dict[str, Any]] = {}
        self.markets: Dict[int, MockKalshiMarket] = {}
        self.next_sid = 1
        self.server = None
        self.update_task: Optional[asyncio.Task] = None
        
        # Initialize sample markets
        self._initialize_sample_markets()
        
        logger.info(f"MockKalshiServer initialized on {host}:{port}")
    
    def _initialize_sample_markets(self):
        """Initialize sample markets with realistic data"""
        sample_markets = [
            {
                "market_ticker": "KXUSAIRANAGREEMENT-26",
                "initial_price": 65,
                "yes_bid": 64,
                "yes_ask": 66
            },
            {
                "market_ticker": "PRES24-DJT-Y",
                "initial_price": 55,
                "yes_bid": 54,
                "yes_ask": 56
            },
            {
                "market_ticker": "TEST-MARKET-Y",
                "initial_price": 50,
                "yes_bid": 49,
                "yes_ask": 51
            }
        ]
        
        for market_data in sample_markets:
            sid = self.next_sid
            self.next_sid += 1
            
            self.markets[sid] = MockKalshiMarket(
                sid=sid,
                market_ticker=market_data["market_ticker"],
                last_price=market_data["initial_price"],
                yes_bid=market_data["yes_bid"],
                yes_ask=market_data["yes_ask"],
                volume=random.randint(500, 2000),
                open_interest=random.randint(2000, 10000)
            )
            
            logger.info(f"Initialized mock market {market_data['market_ticker']} (sid={sid})")
    
    async def start(self):
        """Start the mock WebSocket server"""
        logger.info(f"Starting MockKalshiServer on {self.host}:{self.port}")
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
        
        logger.info("MockKalshiServer started successfully")
        return self.server
    
    async def stop(self):
        """Stop the mock server"""
        logger.info("Stopping MockKalshiServer")
        
        if self.update_task:
            self.update_task.cancel()
            try:
                await self.update_task
            except asyncio.CancelledError:
                pass
        
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        
        logger.info("MockKalshiServer stopped")
    
    async def _handle_connection(self, websocket: WebSocketServerProtocol):
        """Handle new WebSocket connection"""
        client_info = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        logger.info(f"New Kalshi connection from {client_info}")
        
        self.connected_clients[websocket] = {
            "subscriptions": set(),
            "authenticated": False,
            "connected_at": datetime.now()
        }
        
        try:
            async for message in websocket:
                await self._handle_message(websocket, message)
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Kalshi connection closed: {client_info}")
        except Exception as e:
            logger.error(f"Error handling Kalshi connection {client_info}: {e}")
        finally:
            if websocket in self.connected_clients:
                del self.connected_clients[websocket]
    
    async def _handle_message(self, websocket: WebSocketServerProtocol, message: str):
        """Handle incoming WebSocket message"""
        try:
            data = json.loads(message)
            logger.debug(f"Received Kalshi message: {data}")
            
            # Handle subscription commands
            if data.get("cmd") == "subscribe":
                await self._handle_subscription(websocket, data)
            elif data.get("cmd") == "unsubscribe":
                await self._handle_unsubscription(websocket, data)
            else:
                logger.warning(f"Unknown Kalshi command: {data}")
                
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON received: {e}")
            await self._send_error(websocket, "Invalid JSON format")
        except Exception as e:
            logger.error(f"Error handling Kalshi message: {e}")
            await self._send_error(websocket, "Internal server error")
    
    async def _handle_subscription(self, websocket: WebSocketServerProtocol, data: Dict[str, Any]):
        """Handle subscription command"""
        msg_id = data.get("id", 1)
        params = data.get("params", {})
        channels = params.get("channels", [])
        market_tickers = params.get("market_tickers", [])
        
        # Validate subscription request
        if not channels or not market_tickers:
            await self._send_error(websocket, "Missing channels or market_tickers", msg_id)
            return
        
        # Find markets by ticker
        subscribed_sids = []
        for ticker in market_tickers:
            market_sid = self._find_market_by_ticker(ticker)
            if market_sid is not None:
                self.connected_clients[websocket]["subscriptions"].add(market_sid)
                subscribed_sids.append(market_sid)
                logger.info(f"Subscribed to {ticker} (sid={market_sid})")
            else:
                logger.warning(f"Market not found: {ticker}")
        
        # Send confirmation for each subscribed market
        for sid in subscribed_sids:
            await self._send_ok_message(websocket, sid, msg_id)
            
            # Send initial orderbook snapshot
            if "orderbook_delta" in channels:
                await self._send_orderbook_snapshot(websocket, sid)
    
    async def _handle_unsubscription(self, websocket: WebSocketServerProtocol, data: Dict[str, Any]):
        """Handle unsubscription command"""
        msg_id = data.get("id", 1)
        params = data.get("params", {})
        market_tickers = params.get("market_tickers", [])
        
        # Remove subscriptions
        for ticker in market_tickers:
            market_sid = self._find_market_by_ticker(ticker)
            if market_sid is not None and market_sid in self.connected_clients[websocket]["subscriptions"]:
                self.connected_clients[websocket]["subscriptions"].remove(market_sid)
                logger.info(f"Unsubscribed from {ticker} (sid={market_sid})")
        
        # Send confirmation
        await self._send_ok_message(websocket, None, msg_id)
    
    def _find_market_by_ticker(self, ticker: str) -> Optional[int]:
        """Find market SID by ticker symbol"""
        for sid, market in self.markets.items():
            if market.market_ticker == ticker:
                return sid
        return None
    
    async def _send_error(self, websocket: WebSocketServerProtocol, message: str, msg_id: int = None):
        """Send error message"""
        error_msg = {
            "type": "error",
            "msg": message,
            "code": "MOCK_ERROR"
        }
        if msg_id is not None:
            error_msg["id"] = msg_id
        
        try:
            await websocket.send(json.dumps(error_msg))
            logger.debug(f"Sent error: {message}")
        except Exception as e:
            logger.error(f"Error sending error message: {e}")
    
    async def _send_ok_message(self, websocket: WebSocketServerProtocol, sid: Optional[int], msg_id: int):
        """Send subscription confirmation"""
        ok_msg = {
            "type": "ok",
            "id": msg_id
        }
        if sid is not None:
            ok_msg["sid"] = sid
        
        try:
            await websocket.send(json.dumps(ok_msg))
            logger.debug(f"Sent ok for sid={sid}")
        except Exception as e:
            logger.error(f"Error sending ok message: {e}")
    
    async def _send_orderbook_snapshot(self, websocket: WebSocketServerProtocol, sid: int):
        """Send orderbook snapshot"""
        if sid not in self.markets:
            return

        market = self.markets[sid]
        market.last_seq += 1

        yes_levels = []
        for price, level in sorted(market.yes.items(), key=lambda x: int(x[0]), reverse=True):
            yes_levels.append([price, level.size])

        no_levels = []
        for price, level in sorted(market.no.items(), key=lambda x: int(x[0]), reverse=True):
            no_levels.append([price, level.size])

        snapshot_msg = {
            "type": "orderbook_snapshot",
            "sid": sid,
            "seq": market.last_seq,
            "msg": {
                "market_ticker": market.market_ticker,
                "yes": yes_levels,
                "no": no_levels,
                "ts": int(time.time())
            }
        }

        try:
            await websocket.send(json.dumps(snapshot_msg))
            logger.debug(f"Sent orderbook_snapshot for sid={sid}, seq={market.last_seq}")
        except Exception as e:
            logger.error(f"Error sending orderbook snapshot: {e}")
    
    async def _periodic_updates(self):
        """Send periodic market updates to simulate real market activity"""
        while True:
            try:
                await asyncio.sleep(random.uniform(3, 10))  # Random intervals 3-10 seconds
                
                if not self.connected_clients:
                    continue
                
                # Pick a random market to update
                market_sids = list(self.markets.keys())
                if not market_sids:
                    continue
                
                sid = random.choice(market_sids)
                
                # Get clients subscribed to this market
                subscribed_clients = [
                    ws for ws, client_data in self.connected_clients.items()
                    if sid in client_data["subscriptions"]
                ]
                
                if not subscribed_clients:
                    continue
                
                # Choose random update type
                update_type = random.choice(["orderbook_delta", "ticker_v2"])
                
                if update_type == "orderbook_delta":
                    await self._send_orderbook_delta(subscribed_clients, sid)
                elif update_type == "ticker_v2":
                    await self._send_ticker_update(subscribed_clients, sid)
                
            except asyncio.CancelledError:
                logger.info("Kalshi periodic updates cancelled")
                break
            except Exception as e:
                logger.error(f"Error in Kalshi periodic updates: {e}")
    
    async def _send_orderbook_delta(self, clients: List[WebSocketServerProtocol], sid: int):
        """Send orderbook delta update"""
        if sid not in self.markets:
            return

        market = self.markets[sid]
        market.last_seq += 1

        # Generate random orderbook change for yes or no
        is_yes = random.choice([True, False])
        book = market.yes if is_yes else market.no
        contract_type = "yes" if is_yes else "no"

        # If there are levels, update one; else, add a new one
        if book:
            price = random.choice(list(book.keys()))
            old_level = book[price]
            new_size = max(0, old_level.size + random.randint(-50, 50))
            if new_size == 0:
                del book[price]
                delta_data = [price, 0]
            else:
                book[price] = MockOrderbookLevel(price=price, size=new_size)
                delta_data = [price, new_size]
        else:
            # Add a new random price level
            price = str(random.randint(1, 99))
            size = random.randint(50, 200)
            book[price] = MockOrderbookLevel(price=price, size=size)
            delta_data = [price, size]

        # Create delta message in Kalshi format (flat yes/no, no bids/asks distinction)
        delta_msg = {
            "type": "orderbook_delta",
            "sid": sid,
            "seq": market.last_seq,
            "msg": {
                "market_ticker": market.market_ticker,
                contract_type: [delta_data],
                "ts": int(time.time())
            }
        }

        # Send to all subscribed clients
        for client in clients:
            try:
                await client.send(json.dumps(delta_msg))
                logger.debug(f"Sent orderbook_delta for sid={sid}: {contract_type} {delta_data}")
            except Exception as e:
                logger.error(f"Error sending orderbook delta: {e}")
    
    async def _send_ticker_update(self, clients: List[WebSocketServerProtocol], sid: int):
        """Send ticker_v2 update"""
        if sid not in self.markets:
            return
        
        market = self.markets[sid]
        
        # Generate random ticker update
        update_fields = {}
        
        # Possibly update price (trade occurred)
        if random.random() < 0.3:  # 30% chance of trade
            price_change = random.randint(-2, 2)
            new_price = max(1, min(99, market.last_price + price_change))
            market.last_price = new_price
            update_fields["price"] = new_price
            
            # Add volume deltas on trades
            volume_delta = random.randint(1, 50)
            market.volume += volume_delta
            update_fields["volume_delta"] = volume_delta
            
            oi_delta = random.randint(-10, 20)
            market.open_interest = max(0, market.open_interest + oi_delta)
            update_fields["open_interest_delta"] = oi_delta
            
            # Dollar volume updates
            dollar_vol_delta = volume_delta * new_price
            market.dollar_volume += dollar_vol_delta
            update_fields["dollar_volume_delta"] = dollar_vol_delta
            
            dollar_oi_delta = oi_delta * new_price if oi_delta > 0 else 0
            market.dollar_open_interest += dollar_oi_delta
            update_fields["dollar_open_interest_delta"] = dollar_oi_delta
        
        # Possibly update bid/ask (orderbook change)
        if random.random() < 0.7:  # 70% chance of bid/ask update
            bid_change = random.randint(-1, 1)
            ask_change = random.randint(-1, 1)
            
            new_yes_bid = max(1, min(98, market.yes_bid + bid_change))
            new_yes_ask = max(2, min(99, market.yes_ask + ask_change))
            
            # Ensure bid < ask
            if new_yes_bid >= new_yes_ask:
                new_yes_ask = new_yes_bid + 1
            
            market.yes_bid = new_yes_bid
            market.yes_ask = new_yes_ask
            
            update_fields["yes_bid"] = new_yes_bid
            update_fields["yes_ask"] = new_yes_ask
        
        # Only send if we have updates
        if not update_fields:
            return
        
        # Create ticker_v2 message in exact Kalshi format
        ticker_msg = {
            "type": "ticker_v2",
            "sid": sid,
            "msg": {
                "market_ticker": market.market_ticker,
                "ts": int(time.time()),
                **update_fields
            }
        }
        
        # Send to all subscribed clients
        for client in clients:
            try:
                await client.send(json.dumps(ticker_msg))
                logger.debug(f"Sent ticker_v2 for sid={sid}: {update_fields}")
            except Exception as e:
                logger.error(f"Error sending ticker update: {e}")
    
    def add_market(self, market_ticker: str, initial_price: int = 50, yes_bid: int = 49, yes_ask: int = 51) -> int:
        """Add a new market for testing"""
        sid = self.next_sid
        self.next_sid += 1
        
        self.markets[sid] = MockKalshiMarket(
            sid=sid,
            market_ticker=market_ticker,
            last_price=initial_price,
            yes_bid=yes_bid,
            yes_ask=yes_ask
        )
        
        logger.info(f"Added mock Kalshi market {market_ticker} (sid={sid})")
        return sid
    
    def get_market(self, sid: int) -> Optional[MockKalshiMarket]:
        """Get market state for testing"""
        return self.markets.get(sid)

'''
# Standalone server runner for testing
async def main():
    """Run the mock server standalone for testing"""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    server = MockKalshiServer(port=8002)
    await server.start()
    
    logger.info("Mock Kalshi server running on ws://localhost:8002")
    logger.info("Test subscription: {'id': 1, 'cmd': 'subscribe', 'params': {'channels': ['orderbook_delta'], 'market_tickers': ['TEST-MARKET-Y']}}")
    
    try:
        # Keep running
        await asyncio.Future()  # Run forever
    except KeyboardInterrupt:
        logger.info("Shutting down mock Kalshi server")
        await server.stop()

if __name__ == "__main__":
    asyncio.run(main())
'''