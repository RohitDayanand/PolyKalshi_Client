"""
Kalshi Client - Simple WebSocket Connection Manager

This module provides a clean interface for connecting to Kalshi's WebSocket API
with connection management, reconnection, and heartbeat functionality.

Key Features:
- Simplified connection interface
- Automatic reconnection and heartbeat management
- Event-driven callbacks for message handling
- Error handling and logging
- Ticker-based subscription management
"""

import json
import asyncio
import time
import threading
import logging
import os
import websockets
import base64
from datetime import datetime, timedelta
from typing import Optional, Callable, Dict, List, Any
from pathlib import Path
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.exceptions import InvalidSignature
from enum import Enum

# Configure logging
logger = logging.getLogger(__name__)


class Environment(Enum):
    DEMO = "demo"
    PROD = "prod"


class KalshiClientConfig:
    """Configuration class for Kalshi client."""
    
    def __init__(
        self,
        ticker: str,
        channel: str = "orderbook_delta",
        key_id: Optional[str] = None,
        private_key_path: Optional[str] = None,
        environment: Environment = Environment.DEMO,
        ping_interval: int = 30,
        reconnect_interval: int = 5,
        log_level: str = "INFO"
    ):
        self.ticker = ticker
        self.channel = channel
        self.key_id = key_id or os.getenv('PROD_KEYID')
        self.private_key_path = private_key_path or self._get_default_key_path()
        self.environment = environment
        self.ping_interval = ping_interval
        self.reconnect_interval = reconnect_interval
        self.log_level = log_level
        
        # Load private key
        self.private_key = self._load_private_key()
    
    def _get_default_key_path(self) -> str:
        """Get default path to Kalshi private key file."""
        script_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(script_dir, '..', 'kalshi-starter-code-python', 'kalshi_key_file.txt')
    
    def _load_private_key(self):
        """Load the RSA private key for Kalshi authentication."""
        try:
            with open(self.private_key_path, "rb") as key_file:
                return serialization.load_pem_private_key(
                    key_file.read(),
                    password=None
                )
        except FileNotFoundError:
            logger.error(f"Private key file not found at {self.private_key_path}")
            raise
        except Exception as e:
            logger.error(f"Error loading private key: {e}")
            raise


class KalshiClient:
    """
    Simple Kalshi WebSocket client for real-time market data.
    
    This class provides a clean interface for connecting to Kalshi's WebSocket API
    with automatic reconnection and heartbeat management.
    """
    
    def __init__(self, config: KalshiClientConfig):
        self.config = config
        self.ticker = config.ticker
        self.channel = config.channel
          # Connection state
        self.websocket: Optional[websockets.WebSocketServerProtocol] = None
        self.is_connected = False
        self.should_reconnect = True
        self.last_message_time = datetime.now()
        self.message_id = 1
        
        # Threading components
        self._threads: List[threading.Thread] = []
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        
        # Event callbacks
        self.on_message_callback: Optional[Callable[[Dict], None]] = None
        self.on_connection_callback: Optional[Callable[[bool], None]] = None
        self.on_error_callback: Optional[Callable[[Exception], None]] = None
      
    def set_message_callback(self, callback: Callable[[Dict], None]) -> None:
        """Set callback for all incoming messages."""
        self.on_message_callback = callback
    
    def set_connection_callback(self, callback: Callable[[bool], None]) -> None:
        """Set callback for connection status changes."""
        self.on_connection_callback = callback
    
    def set_error_callback(self, callback: Callable[[Exception], None]) -> None:
        """Set callback for error handling."""
        self.on_error_callback = callback
    def _get_ws_url(self) -> str:
        """Get WebSocket URL based on environment."""
        if self.config.environment == Environment.DEMO:
            return "wss://demo-api.kalshi.co/trade-api/ws/v2"
        elif self.config.environment == Environment.PROD:
            return "wss://api.elections.kalshi.com/trade-api/ws/v2"
        else:
            raise ValueError("Invalid environment")
    
    def _create_auth_headers(self, method: str, path: str) -> Dict[str, str]:
        """Generate authentication headers for Kalshi API."""
        current_time_milliseconds = int(time.time() * 1000)
        timestamp_str = str(current_time_milliseconds)
        path_parts = path.split('?')
        msg_string = timestamp_str + method + path_parts[0]
        signature = self._sign_pss_text(msg_string)

        return {
            "KALSHI-ACCESS-KEY": self.config.key_id,
            "KALSHI-ACCESS-SIGNATURE": signature,
            "KALSHI-ACCESS-TIMESTAMP": timestamp_str,
        }
    
    def _sign_pss_text(self, text: str) -> str:
        """Sign text using RSA-PSS and return base64 encoded signature."""
        message = text.encode('utf-8')
        try:
            signature = self.config.private_key.sign(
                message,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.DIGEST_LENGTH
                ),
                hashes.SHA256()
            )
            return base64.b64encode(signature).decode('utf-8')
        except InvalidSignature as e:
            raise ValueError("RSA sign PSS failed") from e
    
    async def _handle_websocket_message(self, message: str) -> None:
        """Handle incoming WebSocket messages."""
        try:
            # Update last message time
            self.last_message_time = datetime.now()
            
            # Handle PONG messages
            if message == "PONG":
                logger.debug("Received PONG response")
                return
            
            # Parse JSON message
            data = json.loads(message)
            
            # Handle ping messages
            if data.get('type') == 'ping':
                pong_message = {"type": "pong"}
                await self.websocket.send(json.dumps(pong_message))
                logger.debug("Sent PONG in response to ping")
                return
            
            # Call user callback if set
            if self.on_message_callback:
                self.on_message_callback(data)
                
        except json.JSONDecodeError:
            logger.error("Failed to parse message as JSON")
            if self.on_error_callback:
                self.on_error_callback(Exception("Invalid JSON message"))
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            if self.on_error_callback:
                self.on_error_callback(e)
    
    async def _subscribe_to_channel(self) -> None:
        """Subscribe to the specified channel and ticker."""
        subscribe_message = {
            "id": 1,
            "cmd": "subscribe",
            "params": {
                "channels": self.channel,
                "market_tickers": [self.ticker]
            }
        }
        
        await self.websocket.send(json.dumps(subscribe_message))
        logger.info(f"Subscribed to {self.channel} for ticker {self.ticker}")
    
    async def _websocket_handler(self) -> None:
        """Main WebSocket message handler loop."""
        try:
            async for message in self.websocket:
                await self._handle_websocket_message(message)
        except websockets.ConnectionClosed as e:
            logger.warning(f"WebSocket connection closed: {e.code} {e.reason}")
            self.is_connected = False
            if self.on_connection_callback:
                self.on_connection_callback(False)
        except Exception as e:
            logger.error(f"WebSocket handler error: {e}")
            self.is_connected = False
            if self.on_error_callback:
                self.on_error_callback(e)
    async def _async_connect(self) -> bool:
        """Async connect method using native websockets."""
        max_retries = 3
        retries = 0
        
        while self.should_reconnect and retries < max_retries:
            try:
                # Get WebSocket URL and auth headers
                ws_url = self._get_ws_url()
                auth_headers = self._create_auth_headers("GET", "/trade-api/ws/v2")
                
                logger.info(f"Connecting to Kalshi WebSocket: {ws_url}")
                
                # Connect to WebSocket
                self.websocket = await websockets.connect(
                    ws_url,
                    additional_headers=auth_headers
                )
                
                self.is_connected = True
                logger.info(f"Successfully connected to Kalshi for ticker: {self.ticker}")
                
                if self.on_connection_callback:
                    self.on_connection_callback(True)
                
                # Subscribe to the channel
                await self._subscribe_to_channel()
                
                # Start message handler
                await self._websocket_handler()
                
                return True
                
            except websockets.ConnectionClosed as e:
                logger.warning(f"Connection closed: {e.code} {e.reason}")
                self.is_connected = False
                retries += 1
                if retries < max_retries and self.should_reconnect:
                    logger.info(f"Reconnecting in {self.config.reconnect_interval} seconds... (attempt {retries+1} of {max_retries})")
                    await asyncio.sleep(self.config.reconnect_interval)
                    
            except Exception as e:
                logger.error(f"Error connecting to Kalshi: {e}")
                self.is_connected = False
                retries += 1
                if retries < max_retries and self.should_reconnect:
                    logger.info(f"Reconnecting in {self.config.reconnect_interval} seconds... (attempt {retries+1} of {max_retries})")
                    await asyncio.sleep(self.config.reconnect_interval)
                elif self.on_error_callback:
                    self.on_error_callback(e)
        
        if retries >= max_retries:
            logger.error("Max reconnection attempts reached")
            return False
            
        return False
    def _run_async_in_thread(self):
        """Run the async connection in a dedicated thread with its own event loop."""
        try:
            # Create new event loop for this thread
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            
            # Run the connection (this will handle reconnection internally)
            self._loop.run_until_complete(self._async_connect())
            
        except Exception as e:
            logger.error(f"Error in async thread: {e}")
            if self.on_error_callback:
                self.on_error_callback(e)
        finally:
            # Clean up loop
            if self._loop and not self._loop.is_closed():
                self._loop.close()
    
    def _monitor_connection(self) -> None:
        """Monitor connection health."""
        while self.should_reconnect:
            if self.is_connected:
                # Check if we've received messages recently
                time_since_last = datetime.now() - self.last_message_time
                if time_since_last > timedelta(seconds=self.config.ping_interval * 3):
                    logger.warning("No messages received recently, connection may be stale")
                    
            time.sleep(self.config.ping_interval)
    
    def connect(self) -> bool:
        """
        Connect to Kalshi WebSocket and start processing.
        
        Returns:
            bool: True if initialization was successful, False otherwise
        """
        try:
            # Validate configuration
            if not self.config.key_id:
                logger.error("Key ID is required for Kalshi connection")
                return False
            
            if not self.config.private_key:
                logger.error("Private key is required for Kalshi connection")
                return False
            
            # Start async connection thread
            connect_thread = threading.Thread(target=self._run_async_in_thread)
            connect_thread.daemon = True
            connect_thread.start()
            self._threads.append(connect_thread)
            
            # Start connection monitor thread
            monitor_thread = threading.Thread(target=self._monitor_connection)
            monitor_thread.daemon = True
            monitor_thread.start()
            self._threads.append(monitor_thread)
            
            # Wait a moment for initial connection
            time.sleep(2)
            
            logger.info(f"Kalshi client started for ticker: {self.ticker}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start Kalshi client: {e}")
            if self.on_error_callback:
                self.on_error_callback(e)
            return False
    def disconnect(self) -> None:
        """Disconnect from Kalshi WebSocket and cleanup resources."""
        logger.info("Shutting down Kalshi client...")
        
        self.should_reconnect = False
        self.is_connected = False
        
        # Disconnect WebSocket
        if self.websocket:
            try:
                if self._loop and not self._loop.is_closed():
                    # Run disconnect in the same loop
                    future = asyncio.run_coroutine_threadsafe(
                        self.websocket.close(), 
                        self._loop
                    )
                    future.result(timeout=5.0)
            except Exception as e:
                logger.error(f"Error disconnecting WebSocket: {e}")
        
        # Wait for threads to finish (with timeout)
        for thread in self._threads:
            if thread.is_alive():
                thread.join(timeout=2.0)
        
        if self.on_connection_callback:
            self.on_connection_callback(False)
        
        logger.info("Kalshi client shutdown complete")
    
    def is_running(self) -> bool:
        """Check if the client is currently connected and running."""
        return self.is_connected and self.should_reconnect
    
    def get_status(self) -> Dict[str, Any]:
        """Get current client status information."""
        return {
            "connected": self.is_connected,
            "should_reconnect": self.should_reconnect,
            "ticker": self.ticker,
            "channel": self.channel,
            "last_message_time": self.last_message_time.isoformat() if self.last_message_time else None,
            "environment": self.config.environment.value,
            "threads_active": len([t for t in self._threads if t.is_alive()])
        }

# Convenience function for quick setup
def create_kalshi_client(
    ticker: str,
    channel: str = "orderbook_delta",
    environment: Environment = Environment.DEMO,
    ping_interval: int = 30,
    log_level: str = "INFO"
) -> KalshiClient:
    """
    Create a Kalshi client with default configuration.
    
    Args:
        ticker: Market ticker symbol
        channel: Subscription channel type
        environment: Demo or Production environment
        ping_interval: Interval between connection checks (seconds)
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
    
    Returns:
        KalshiClient: Configured client instance
    """
    config = KalshiClientConfig(
        ticker=ticker,
        channel=channel,
        environment=environment,
        ping_interval=ping_interval,
        log_level=log_level
    )
    return KalshiClient(config)
