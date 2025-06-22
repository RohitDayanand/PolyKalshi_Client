"""
Polymarket Client - Simple WebSocket Connection Manager

This module provides a clean interface for connecting to Polymarket's WebSocket API
with connection management, reconnection, and heartbeat functionality.

Key Features:
- Simplified connection interface
- Automatic reconnection and heartbeat management
- Event-driven callbacks for message handling
- Error handling and logging
- Market data loading and subscription management
"""

import json
import websocket
import time
import threading
import logging
from datetime import datetime, timedelta
from typing import Optional, Callable, Dict, List, Any
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PolymarketClientConfig:
    """Configuration class for Polymarket client."""
    
    def __init__(
        self,
        slug: str,
        ws_url: str = "wss://ws-subscriptions-clob.polymarket.com/ws/market",
        ping_interval: int = 30,
        reconnect_interval: int = 5,
        log_level: str = "INFO"
    ):
        self.slug = slug
        self.ws_url = ws_url
        self.ping_interval = ping_interval
        self.reconnect_interval = reconnect_interval
        self.log_level = log_level


class PolymarketClient:
    """
    Simple Polymarket WebSocket client for real-time market data.
    
    This class provides a clean interface for connecting to Polymarket's WebSocket API
    with automatic reconnection and heartbeat management.
    """
    
    def __init__(self, config: PolymarketClientConfig):
        self.config = config
        self.slug = config.slug
        
        # Connection state
        self.ws: Optional[websocket.WebSocketApp] = None
        self.is_connected = False
        self.should_reconnect = True
        self.last_pong = datetime.now()
        
        # Threading components
        self._threads: List[threading.Thread] = []
        
        # Market data
        self.condition_ids: Optional[List] = None
        self.token_ids: Optional[List] = None
        
        # Event callbacks
        self.on_message_callback: Optional[Callable[[Dict], None]] = None
        self.on_connection_callback: Optional[Callable[[bool], None]] = None
        self.on_error_callback: Optional[Callable[[Exception], None]] = None
        
        # Setup logging
        logging.getLogger(__name__).setLevel(getattr(logging, config.log_level))
    
    def set_message_callback(self, callback: Callable[[Dict], None]) -> None:
        """Set callback for all incoming messages."""
        self.on_message_callback = callback
    
    def set_connection_callback(self, callback: Callable[[bool], None]) -> None:
        """Set callback for connection status changes."""
        self.on_connection_callback = callback
    
    def set_error_callback(self, callback: Callable[[Exception], None]) -> None:
        """Set callback for error handling."""
        self.on_error_callback = callback
    
    def _load_market_data(self) -> tuple[Optional[List], Optional[List]]:
        """Load market data from generated files."""
        try:
            base_path = Path(__file__).parent.parent / "poly-starter-code"
            
            with open(base_path / f'{self.slug}_condition_id_list.json', 'r') as f:
                condition_ids = json.load(f)
            
            with open(base_path / f'{self.slug}_token_ids_list.json', 'r') as f:
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
    
    def _on_message(self, ws, message) -> None:
        """Handle incoming WebSocket messages."""
        try:
            # Handle PONG messages
            if message == "PONG":
                self.last_pong = datetime.now()
                logger.debug("Received PONG response")
                return
            
            data = json.loads(message)
            messages = data if isinstance(data, list) else [data]
            
            for msg in messages:
                if msg.get('type') == 'PONG':
                    self.last_pong = datetime.now()
                    continue
                
                # Call user callback if set
                if self.on_message_callback:
                    self.on_message_callback(msg)
                
        except json.JSONDecodeError:
            logger.error("Failed to parse message as JSON")
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            if self.on_error_callback:
                self.on_error_callback(e)
    
    def _on_error(self, ws, error) -> None:
        """Handle WebSocket errors."""
        logger.error(f"WebSocket error: {error}")
        if self.on_error_callback:
            self.on_error_callback(Exception(f"WebSocket error: {error}"))
    
    def _on_close(self, ws, close_status_code, close_msg) -> None:
        """Handle WebSocket connection close."""
        logger.warning(f"WebSocket connection closed with status: {close_status_code}")
        self.is_connected = False
        if self.on_connection_callback:
            self.on_connection_callback(False)
    
    def _on_open(self, ws) -> None:
        """Handle WebSocket connection open."""
        logger.info("WebSocket connection opened")
        self.is_connected = True
        self.last_pong = datetime.now()
        
        if self.on_connection_callback:
            self.on_connection_callback(True)
        
        # Subscribe to market data
        if not self.condition_ids or not self.token_ids:
            logger.error("No market data loaded for subscription")
            ws.close()
            return
        
        subscribe_message = {
            "type": "MARKET",
            "assets_ids": self.token_ids,
        }
        
        try:
            ws.send(json.dumps(subscribe_message))
            logger.info(f"Subscribed to {len(self.token_ids)} assets")
        except Exception as e:
            logger.error(f"Failed to send subscription message: {e}")
            ws.close()
    
    def _send_ping(self) -> None:
        """Send ping messages to keep connection alive."""
        while self.should_reconnect:
            if self.is_connected and self.ws:
                try:
                    self.ws.send(json.dumps({"type": "ping"}))
                    logger.debug("Sent ping message")
                except Exception as e:
                    logger.error(f"Failed to send ping: {e}")
                    self.is_connected = False
            time.sleep(self.config.ping_interval)
    
    def _check_connection(self) -> None:
        """Monitor connection health and reconnect if necessary."""
        while self.should_reconnect:
            if not self.is_connected:
                logger.warning("Connection lost, attempting to reconnect...")
                self._connect()
            elif datetime.now() - self.last_pong > timedelta(seconds=self.config.ping_interval * 2):
                logger.warning("No pong received, reconnecting...")
                self.is_connected = False
                if self.ws:
                    self.ws.close()
            time.sleep(1)
    
    def _connect(self) -> None:
        """Establish WebSocket connection."""
        try:
            logger.info(f"Connecting to WebSocket URL: {self.config.ws_url}")
            
            self.ws = websocket.WebSocketApp(
                self.config.ws_url,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close,
                on_open=self._on_open
            )
            
            # Start WebSocket connection in a separate thread
            ws_thread = threading.Thread(target=self.ws.run_forever)
            ws_thread.daemon = True
            ws_thread.start()
            self._threads.append(ws_thread)
            
        except Exception as e:
            logger.error(f"Failed to create WebSocket connection: {e}")
            if self.on_error_callback:
                self.on_error_callback(e)
    
    def connect(self) -> bool:
        """
        Connect to Polymarket WebSocket and start processing.
        
        Returns:
            bool: True if initialization was successful, False otherwise
        """
        try:
            # Load market data
            self.condition_ids, self.token_ids = self._load_market_data()
            if not self.condition_ids or not self.token_ids:
                logger.error("Failed to load market data")
                return False
            
            # Start ping thread
            ping_thread = threading.Thread(target=self._send_ping)
            ping_thread.daemon = True
            ping_thread.start()
            self._threads.append(ping_thread)
            
            # Start connection monitor thread
            check_thread = threading.Thread(target=self._check_connection)
            check_thread.daemon = True
            check_thread.start()
            self._threads.append(check_thread)
            
            # Initial connection
            self._connect()
            
            logger.info(f"Polymarket client started for market: {self.slug}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start Polymarket client: {e}")
            if self.on_error_callback:
                self.on_error_callback(e)
            return False
    
    def disconnect(self) -> None:
        """Disconnect from Polymarket WebSocket and cleanup resources."""
        logger.info("Shutting down Polymarket client...")
        
        self.should_reconnect = False
        
        if self.ws:
            self.ws.close()
        
        # Wait for threads to finish (with timeout)
        for thread in self._threads:
            if thread.is_alive():
                thread.join(timeout=2.0)
        
        logger.info("Polymarket client shutdown complete")
    
    def is_running(self) -> bool:
        """Check if the client is currently connected and running."""
        return self.is_connected and self.should_reconnect
    
    def get_status(self) -> Dict[str, Any]:
        """Get current client status information."""
        return {
            "connected": self.is_connected,
            "should_reconnect": self.should_reconnect,
            "slug": self.slug,
            "last_pong": self.last_pong.isoformat() if self.last_pong else None,
            "condition_ids_count": len(self.condition_ids) if self.condition_ids else 0,
            "token_ids_count": len(self.token_ids) if self.token_ids else 0,
            "threads_active": len([t for t in self._threads if t.is_alive()])
        }


# Convenience function for quick setup
def create_polymarket_client(
    slug: str,
    ping_interval: int = 30,
    log_level: str = "INFO"
) -> PolymarketClient:
    """
    Create a Polymarket client with default configuration.
    
    Args:
        slug: Market slug identifier
        ping_interval: Interval between ping messages (seconds)
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
    
    Returns:
        PolymarketClient: Configured client instance
    """
    config = PolymarketClientConfig(
        slug=slug,
        ping_interval=ping_interval,
        log_level=log_level
    )
    return PolymarketClient(config)
