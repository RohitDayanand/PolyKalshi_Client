"""
Polymarket WebSocket Client

This script implements a WebSocket client for connecting to Polymarket's real-time market data API.
It handles subscription to market channels and processes incoming messages for order book and price updates.

Key Features:
- Connects to Polymarket's WebSocket endpoint
- Subscribes to specific markets and assets
- Processes and displays real-time order book updates
- Handles price change notifications
- Includes error handling and logging
"""

import json
import websocket
import time
import threading
import logging
import sys
from datetime import datetime, timedelta
from models import Session, OrderBook, PriceChange, TickSizeChange, init_db

# Configure logging
logging.basicConfig(
    level=logging.WARNING,  # Change to WARNING level
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('error_diagnosis.log'),
        logging.StreamHandler(sys.stdout)
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
        self.session = Session()
        
        # Initialize database
        init_db()

    def load_market_data(self):
        """Load market data from the generated files."""
        try:
            # Read condition IDs
            with open(f'poly-starter-code/{self.slug}_condition_id_list.json', 'r') as f:
                condition_ids = json.load(f)  # This will be a list
                if not isinstance(condition_ids, list) or len(condition_ids) == 0:
                    logger.error("Invalid condition IDs format")
                    return None, None
            
            # Read token IDs
            with open(f'poly-starter-code/{self.slug}_token_ids_list.json', 'r') as f:
                token_ids = json.load(f)  # This will be a list
                if not isinstance(token_ids, list) or len(token_ids) == 0:
                    logger.error("Invalid token IDs format")
                    return None, None
            
            logger.info(f"Loaded {len(condition_ids)} condition IDs")
            logger.info(f"Loaded {len(token_ids)} token IDs")
            return condition_ids, token_ids
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Error loading market data: {e}")
            return None, None

    def get_market_metrics_with_depth(self, order_book):
        """Calculate market metrics from orderbook data."""
        # Convert prices and group by price level - growth vs. 

        #college - insanity 

        buy_levels = {}
        sell_levels = {}

        for order in order_book.get("bids", []):
            #print(f"Order: {order}, I made it here")
            price = float(order["price"])
            #print(f"Price: {price}, I made it here")
            size = float(order["size"])
           # print(f"Size: {size}, I made it here")
            buy_levels[price] = buy_levels.get(price, 0) + size
           # print(f"Buy levels: {buy_levels}, I made it here")

        for order in order_book.get("asks", []):
            #print(f"Order: {order}, I made it here")
            price = float(order["price"])
            #print(f"Price: {price}, I made it here")
            size = float(order["size"])
            #print(f"Size: {size}, I made it here")
            sell_levels[price] = sell_levels.get(price, 0) + size
            #print(f"Sell levels: {sell_levels}, I made it here")

        #If there is neither bid nor ask, return None. This market is not tradable
        if not buy_levels and not sell_levels:
            return None
        
        #If there is no bid, return the lowest ask. This market is a buy market
        elif not sell_levels:
            best_bid = max(buy_levels)
            best_ask = None 

        #If there is no ask, return the highest bid. This market is not currently tradable
        elif not buy_levels:
            best_bid = None
            best_ask = min(sell_levels)
        #otherwise there are bids and asks
        else:
            best_ask = min(sell_levels)
            best_bid = max(buy_levels)

        print(f"Best bid: {best_bid}, Best ask: {best_ask}")

        #Calculate mid_price, but only if there are bids and asks

        if best_bid and best_ask:
            mid_price = round((best_bid + best_ask) / 2, 4)
        else:
            mid_price = None

        #Calculate spread, but only if there are bids and asks
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

    def handle_orderbook(self, data):
        """Handle orderbook message and log to database."""
        try:
            market_metrics = self.get_market_metrics_with_depth(data)
            if market_metrics:
                # Only log essential info at INFO level
                logger.info(f"Market {data['market']}: Bid {market_metrics['best_bid']} Ask {market_metrics['best_ask']} Mid {market_metrics['mid_price']}")
            else:
                logger.warning(f"No market metrics for market {data['market']}")
                return
            
            # Log market metrics
            order = OrderBook(
                event_type=data['event_type'],
                asset_id=data['asset_id'],
                market=data['market'],
                best_bid=market_metrics['best_bid'],
                bid_size=market_metrics['bid_size'],
                best_ask=market_metrics['best_ask'],
                ask_size=market_metrics['ask_size'],
                mid_price=market_metrics['mid_price'],
                spread=market_metrics['spread'],
                timestamp=data['timestamp']
            )
            self.session.add(order)
            self.session.commit()

        except Exception as e:
            logger.error(f"Error handling orderbook data: {e}")
            self.session.rollback()

    def handle_price_change(self, data):
        """Handle price change message and log to database."""
        try:
            for change in data.get('changes', []):
                price_change = PriceChange(
                    event_type=data['event_type'],
                    asset_id=data['asset_id'],
                    market=data['market'],
                    price=change['price'],
                    size=change['size'],
                    side=change['side'],
                    timestamp=data['timestamp'],
                    hash=data.get('hash', '')
                )
                self.session.add(price_change)
            
            self.session.commit()
            logger.debug(f"Logged price change data for market {data['market']}")
        except Exception as e:
            logger.error(f"Error handling price change data: {e}")
            self.session.rollback()

    def handle_tick_size_change(self, data):
        """Handle tick size change message and log to database."""
        try:
            tick_change = TickSizeChange(
                event_type=data['event_type'],
                asset_id=data['asset_id'],
                market=data['market'],
                old_tick_size=data['old_tick_size'],
                new_tick_size=data['new_tick_size'],
                timestamp=data['timestamp']
            )
            self.session.add(tick_change)
            self.session.commit()
            logger.debug(f"Logged tick size change for market {data['market']}")
        except Exception as e:
            logger.error(f"Error handling tick size change data: {e}")
            self.session.rollback()

    def save_raw_message(self, message):
        """Save raw message to a file for debugging."""
        try:
            timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
            with open(f'poly-starter-code/raw_messages_{self.slug}.txt', 'a') as f:
                f.write(f"\n{'='*50}\n")
                f.write(f"Timestamp: {timestamp}\n")
                # Only save the first 100 characters of the message to avoid huge files
                f.write(f"Message preview: {str(message)[:100]}...\n")
                f.write(f"{'='*50}\n")
        except Exception as e:
            logger.error(f"Error saving raw message: {e}")

    def on_message(self, ws, message):
        """Handle incoming messages."""
        try:
            # Save raw message to file
            self.save_raw_message(message)
            
            data = json.loads(message)
            
            # Handle both single messages and arrays of messages
            messages = data if isinstance(data, list) else [data]

           
            for msg in messages:
                # Handle different message types
                if msg.get('type') == 'PONG':
                    self.last_pong = datetime.now()
                    continue
                event_type = msg.get('event_type')
                if event_type == 'book':
                    self.handle_orderbook(msg)
                elif event_type == 'price_change':
                    self.handle_price_change(msg)
                elif event_type == 'tick_size_change':
                    self.handle_tick_size_change(msg)
                
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
            self.session.close()

def main():
    # Get slug from command line argument
    if len(sys.argv) < 2:
        logger.error("Please provide a market slug as an argument")
        sys.exit(1)
    
    slug = sys.argv[1]
    logger.info(f"Starting WebSocket connection for market: {slug}")
    
    # Create and run WebSocket client
    client = PolymarketWebSocket(slug)
    client.run()

if __name__ == "__main__":
    main()
