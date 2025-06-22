"""
Polymarket WebSocket Client with Async Database Support

This script implements a WebSocket client for connecting to Polymarket's real-time market data API
with async SQLAlchemy 2.0 + asyncpg for high-performance database operations.

Key Features:
- Connects to Polymarket's WebSocket endpoint
- Subscribes to specific markets and assets
- Processes and displays real-time order book updates
- Handles price change notifications with async database writes
- Includes error handling and logging
- Uses async database operations for concurrent high-frequency data ingestion
"""

import asyncio
import json
import websocket
import time
import threading
import logging
import sys
print(sys.executable)
from datetime import datetime, timedelta
from models import get_async_session
from models import OrderBook, PriceChange, TickSizeChange 
from models import ensure_async_db_initialized
from models import AsyncDatabaseUtils

# Configure logging
logging.basicConfig(
    level=logging.WARNING,  # Change to WARNING level
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('error_diagnosis.log'),
        #logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class PolymarketWebSocket:
    def __init__(self, slug):
        self.slug = slug
        self.ws = None
        self.last_pong = datetime.now()
        self.ping_interval = 30  # seconds
        self.reconnect_interval = 5  # seconds
        self.is_connected = False
        self.should_reconnect = True
        self.event_loop = None
          # Initialize async database - will be called in async context
        # Note: Database initialization moved to async_init() method
    
    async def async_init(self):
        """Async initialization for database setup."""
        try:
            await ensure_async_db_initialized()
            logger.info("Async database initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize async database: {e}")
            raise

    def load_market_data(self):
        """Load market data from the generated files."""
        try:
            with open(f'{self.slug}_condition_id_list.json', 'r') as f:
                condition_ids = json.load(f)
            
            with open(f'{self.slug}_event_token_ids_dict.json', 'r') as f:
                event_token_ids = json.load(f)
                
            with open(f'{self.slug}_token_ids_list.json', 'r') as f:
                token_ids = json.load(f)
            
            logger.info(f"Loaded {len(condition_ids)} condition IDs and {len(token_ids)} token IDs")
            return condition_ids, token_ids
            
        except FileNotFoundError as e:
            logger.error(f"Market data file not found: {e}")
            logger.info("Please run Market_Finder.py first to generate market data files")
            return None, None
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing market data JSON: {e}")
            return None, None

    def get_market_metrics_with_depth(self, order_book):
        """Calculate market metrics from orderbook data."""
        # Convert prices and group by price level

        buy_levels = {}
        sell_levels = {}

        for order in order_book.get("bids", []):
            price = float(order["price"])
            size = float(order["size"])
            buy_levels[price] = buy_levels.get(price, 0) + size

        for order in order_book.get("asks", []):
            price = float(order["price"])
            size = float(order["size"])
            sell_levels[price] = sell_levels.get(price, 0) + size

        # Get best bid and ask
        best_bid = max(buy_levels.keys()) if buy_levels else None
        best_ask = min(sell_levels.keys()) if sell_levels else None

        print(f"Best bid: {best_bid}, Best ask: {best_ask}")

        # Calculate mid_price, but only if there are bids and asks
        if best_bid and best_ask:
            mid_price = round((best_bid + best_ask) / 2, 4)
        else:
            mid_price = None

        # Calculate spread, but only if there are bids and asks
        if best_bid and best_ask:
            spread = round(best_ask - best_bid, 4)
        else:
            spread = None

        return {
            "best_bid": best_bid,
            "bid_size": buy_levels.get(best_bid, 0),
            "best_ask": best_ask,
            "ask_size": sell_levels.get(best_ask, 0),
            "mid_price": mid_price,
            "spread": spread
        }

    async def handle_orderbook(self, data):
        """Handle orderbook message and log to database (async)."""
        try:
            market_metrics = self.get_market_metrics_with_depth(data)
            if market_metrics:
                # Only log essential info at INFO level
                logger.info(f"Market {data['market']}: Bid {market_metrics['best_bid']} Ask {market_metrics['best_ask']} Mid {market_metrics['mid_price']}")
            else:
                logger.warning(f"No market metrics for market {data['market']}")
                return
            
            # Prepare orderbook data for async insertion
            orderbook_data = {
                'event_type': data['event_type'],
                'asset_id': data['asset_id'],
                'market': data['market'],
                'best_bid': market_metrics['best_bid'],
                'bid_size': market_metrics['bid_size'],
                'best_ask': market_metrics['best_ask'],
                'ask_size': market_metrics['ask_size'],
                'mid_price': market_metrics['mid_price'],
                'spread': market_metrics['spread'],
                'timestamp': data['timestamp']            }
            
            # Use async session context manager for database operations
            async with get_async_session() as session:
                order = OrderBook(**orderbook_data)
                session.add(order)
                await session.commit()

        except Exception as e:
            logger.error(f"Error handling orderbook data: {e}")

    async def handle_price_change(self, data):
        """Handle price change message and log to database (async)."""
        try:
            # Prepare price change data for bulk insert
            price_changes = []
            for change in data.get('changes', []):
                price_change_data = {
                    'event_type': data['event_type'],
                    'asset_id': data['asset_id'],
                    'market': data['market'],
                    'price': change['price'],
                    'size': change['size'],
                    'side': change['side'],
                    'timestamp': data['timestamp'],
                    'hash': data.get('hash', '')            }
                price_changes.append(price_change_data)
            
            # Use async bulk insert for better performance
            async with get_async_session() as session:
                success = await AsyncDatabaseUtils.bulk_insert_price_changes(session, price_changes)
                if success:
                    logger.debug(f"Logged {len(price_changes)} price changes for market {data['market']}")

        except Exception as e:
            logger.error(f"Error handling price change data: {e}")

    async def handle_tick_size_change(self, data):
        """Handle tick size change message and log to database (async)."""
        try:
            # Prepare tick change data
            tick_change_data = {
                'event_type': data['event_type'],
                'asset_id': data['asset_id'],
                'market': data['market'],
                'old_tick_size': data['old_tick_size'],
                'new_tick_size': data['new_tick_size'],
                'timestamp': data['timestamp']            }
            
            # Use async session context manager
            async with get_async_session() as session:
                tick_change = TickSizeChange(**tick_change_data)                
                session.add(tick_change)
                await session.commit()
                logger.debug(f"Logged tick size change for market {data['market']}")

        except Exception as e:
            logger.error(f"Error handling tick size change data: {e}")

    def save_raw_message(self, message):
        """Save raw message to a file for debugging."""
        try:
            timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
            with open(f'raw_messages_{self.slug}.txt', 'a') as f:
                f.write(f"\n{'='*50}\n")
                f.write(f"Timestamp: {timestamp}\n")
                # Only save the first 100 characters of the message to avoid huge files
                f.write(f"Message preview: {str(message)[:100]}...\n")
                f.write(f"{'='*50}\n")
        except Exception as e:
            logger.error(f"Error saving raw message: {e}")    
    def on_message(self, ws, message):
        try:
            # Save raw message to file
            self.save_raw_message(message)
            
            # Handle PONG messages first (they're not JSON)
            if message == "PONG":
                self.last_pong = datetime.now()
                logger.debug("Received PONG response")
                return
            
            data = json.loads(message)
            
            # Handle both single messages and arrays of messages
            messages = data if isinstance(data, list) else [data]

           
            for msg in messages:
                # Handle different message types
                if msg.get('type') == 'PONG':
                    self.last_pong = datetime.now()
                    continue
                    
                event_type = msg.get('event_type')
                
                # Run async database operations in event loop
                if event_type == 'book':
                    asyncio.run_coroutine_threadsafe(
                        self.handle_orderbook(msg), 
                        self.event_loop
                    )
                elif event_type == 'price_change':
                    asyncio.run_coroutine_threadsafe(
                        self.handle_price_change(msg), 
                        self.event_loop
                    )
                elif event_type == 'tick_size_change':
                    asyncio.run_coroutine_threadsafe(
                        self.handle_tick_size_change(msg), 
                        self.event_loop
                    )
                
        except json.JSONDecodeError:
            logger.error(f"Failed to parse message")
        except Exception as e:
            logger.error(f"Error processing message: {e}")

    def on_error(self, ws, error):
        """Handle WebSocket errors."""
        logger.error(f"WebSocket error: {error}")

    def on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket connection close."""
        logger.warning(f"WebSocket connection closed with status: {close_status_code}")

    def on_open(self, ws):
        """Handle WebSocket connection open."""
        logger.info("WebSocket connection opened")
        self.is_connected = True
        self.last_pong = datetime.now()
        
        condition_ids, token_ids = self.load_market_data()
        
        if not condition_ids or not token_ids:
            logger.error("Failed to load market data")
            ws.close()
            return
        
        # Subscribe to the market data with correct format
        subscribe_message = {
            "type": "MARKET",  # Channel type
            "assets_ids": token_ids,  # Array of token IDs
        }
        
        try:
            ws.send(json.dumps(subscribe_message))
            logger.info("Subscription message sent successfully")
        except Exception as e:
            logger.error(f"Failed to send subscription message: {str(e)}")
            ws.close()
            return
        
        logger.info(f"Subscribed to {len(condition_ids)} markets and {len(token_ids)} assets")

    def send_ping(self):
        """Send ping message to keep connection alive."""
        while self.should_reconnect:
            if self.is_connected:
                try:
                    self.ws.send(json.dumps({"type": "ping"}))
                except Exception as e:
                    logger.error(f"Failed to send ping: {e}")
                    self.is_connected = False
            time.sleep(self.ping_interval)

    def check_connection(self):
        """Check connection health and reconnect if necessary."""
        while self.should_reconnect:
            if not self.is_connected:
                logger.warning("Connection lost, attempting to reconnect...")
                self.connect()
            elif datetime.now() - self.last_pong > timedelta(seconds=self.ping_interval * 2):
                logger.warning("No pong received, reconnecting...")
                self.is_connected = False
                self.ws.close()
            time.sleep(1)

    def connect(self):
        """Establish WebSocket connection."""
        websocket.enableTrace(True)
        ws_url = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
        logger.info(f"Connecting to WebSocket URL: {ws_url}")
        
        self.ws = websocket.WebSocketApp(ws_url,
                                      on_message=self.on_message,
                                      on_error=self.on_error,
                                      on_close=self.on_close,
                                      on_open=self.on_open)
        
        # Start WebSocket connection in a separate thread
        wst = threading.Thread(target=self.ws.run_forever)
        wst.daemon = True
        wst.start()

    def run(self):
        """Run the WebSocket client with heartbeat and reconnection."""
        # Set up event loop for async operations
        self.event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.event_loop)
        
        # Initialize async database in the event loop
        try:
            self.event_loop.run_until_complete(self.async_init())
        except Exception as e:
            logger.error(f"Failed to initialize async components: {e}")
            return
        
        # Start async event loop in a separate thread
        def run_event_loop():
            self.event_loop.run_forever()
        
        loop_thread = threading.Thread(target=run_event_loop)
        loop_thread.daemon = True
        loop_thread.start()
        
        # Start ping thread
        ping_thread = threading.Thread(target=self.send_ping)
        ping_thread.daemon = True
        ping_thread.start()

        # Start connection check thread
        check_thread = threading.Thread(target=self.check_connection)
        check_thread.daemon = True
        check_thread.start()

        # Initial connection
        self.connect()

        try:
            # Keep the main thread alive
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down...")
            self.should_reconnect = False
            if self.ws:
                self.ws.close()
            # Stop the event loop
            if self.event_loop and self.event_loop.is_running():
                self.event_loop.call_soon_threadsafe(self.event_loop.stop)

def main():
    # Get slug from command line argument
    if len(sys.argv) < 2:
        logger.error("Please provide a market slug as an argument")
        sys.exit(1)
    
    slug = sys.argv[1]
    logger.info(f"Starting async WebSocket connection for market: {slug}")
    
    # Create and run WebSocket client with async database support
    client = PolymarketWebSocket(slug)
    client.run()

if __name__ == "__main__":
    main()
