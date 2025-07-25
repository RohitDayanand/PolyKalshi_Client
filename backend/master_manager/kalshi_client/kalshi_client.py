import json
import asyncio
import time
import logging
import websockets
import base64
from datetime import datetime, timedelta
from typing import Optional, Callable, Dict, List, Any
from .kalshi_client_config import KalshiClientConfig
from .kalshi_environment import Environment
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes
from cryptography.exceptions import InvalidSignature
from logging.handlers import MemoryHandler

logger = logging.getLogger(__name__)

# Add a constant to toggle detailed logging
LOG_ALL_MESSAGES = False

# In-memory log storage for all log levels
LOG_MEMORY_CAPACITY = 10000  # Adjust as needed
log_memory_handler = MemoryHandler(
    capacity=LOG_MEMORY_CAPACITY,
    flushLevel=logging.CRITICAL,  # Only flush to target handler on CRITICAL
    target=None  # No target, just keep in memory
)
log_memory_handler.setLevel(logging.DEBUG)

# Attach the memory handler to the root logger if not already attached
if not any(isinstance(h, MemoryHandler) for h in logging.getLogger().handlers):
    logging.getLogger().addHandler(log_memory_handler)

# Ensure all log messages are written to the console
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')
console_handler.setFormatter(formatter)

root_logger = logging.getLogger()
if not any(isinstance(h, logging.StreamHandler) for h in root_logger.handlers):
    root_logger.addHandler(console_handler)
root_logger.setLevel(logging.DEBUG)

# Optionally, you can provide a function to retrieve the stored logs

def get_recent_logs(level=logging.DEBUG):
    """Return a list of recent log records at or above the given level."""
    return [
        log_memory_handler.format(record)
        for record in log_memory_handler.buffer
        if record.levelno >= level
    ]

class KalshiClient:
    """
    Simple Kalshi WebSocket client for real-time market data.
    """
    def __init__(self, config: KalshiClientConfig):
        self.config = config
        self.ticker = config.ticker
        self.channel = config.channel
        self.websocket: Optional[websockets.WebSocketServerProtocol] = None
        self.is_connected = False
        self.should_reconnect = True
        self.last_message_time = datetime.now()
        self.message_id = 1
        self.on_message_callback: Optional[Callable[[str, Dict], None]] = None
        self.on_connection_callback: Optional[Callable[[bool], None]] = None
        self.on_error_callback: Optional[Callable[[Exception], None]] = None
        
        # Pre-compute metadata template for performance
        self._metadata_template = {
            "ticker": self.ticker,
            "channel": self.channel,
            "subscription_id": f"{self.ticker}_{self.channel}"
        }

    def set_message_callback(self, callback: Callable[[str, Dict], None]) -> None:
        self.on_message_callback = callback

    def set_connection_callback(self, callback: Callable[[bool], None]) -> None:
        self.on_connection_callback = callback

    def set_error_callback(self, callback: Callable[[Exception], None]) -> None:
        self.on_error_callback = callback

    def _get_ws_url(self) -> str:
        # Use custom URL if provided (for testing/mocking)
        if self.config.custom_ws_url:
            return self.config.custom_ws_url
        
        # Default environment-based URLs
        if self.config.environment == Environment.DEMO:
            return "wss://demo-api.kalshi.co/trade-api/ws/v2"
        elif self.config.environment == Environment.PROD:
            return "wss://api.elections.kalshi.com/trade-api/ws/v2"
        else:
            raise ValueError("Invalid environment")

    def _create_auth_headers(self, method: str, path: str) -> Dict[str, str]:
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
        try:
            self.last_message_time = datetime.now()
            
            # Send raw message directly to queue - no JSON parsing or ping/pong handling
            # (websockets library handles ping/pong automatically)
            if self.on_message_callback:
                # Use pre-computed metadata template, only add timestamp
                metadata = {**self._metadata_template, "timestamp": self.last_message_time.isoformat()}
                # Fire-and-forget to prevent WebSocket handler from blocking
                asyncio.create_task(self.on_message_callback(message, metadata))
                
        except Exception as e:
            logger.error(f"[handle_websocket_message] Error processing message: {e}")
            if self.on_error_callback:
                self.on_error_callback(e)

    async def _subscribe_to_channel(self) -> None:
        subscribe_message = {
            "id": 1,
            "cmd": "subscribe",
            "params": {
                "channels": [self.channel],
                "market_tickers": [self.ticker]
            }
        }
        logger.debug(f"[_subscribe_to_channel] Sending subscription message that is from the correct client: {subscribe_message}")
        await self.websocket.send(json.dumps(subscribe_message))
        logger.info(f"Subscribed to {self.channel} for ticker {self.ticker}")

    async def _websocket_handler(self) -> None:
        logger.debug("[_websocket_handler] Entered WebSocket handler loop")
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

    async def _monitor_connection(self) -> None:
        """Monitor connection health in async manner."""
        while self.should_reconnect:
            if self.is_connected:
                time_since_last = datetime.now() - self.last_message_time
                if time_since_last > timedelta(seconds=self.config.ping_interval * 3):
                    logger.warning("No messages received recently, connection may be stale")
            await asyncio.sleep(self.config.ping_interval)

    async def connect(self) -> bool:
        """
        Connect to Kalshi WebSocket with full async approach.
        Uses reconnection loop and concurrent monitoring.
        """
        if not self.config.key_id:
            logger.error("Key ID is required for Kalshi connection")
            return False
        if not self.config.private_key:
            logger.error("Private key is required for Kalshi connection")
            return False

        # Start the connection as a background task since it's long-running
        asyncio.create_task(self._connect_with_retry())
        
        # Wait for connection to establish with proper timeout and polling
        max_wait_time = 10.0  # Maximum 10 seconds to wait
        check_interval = 0.5  # Check every 500ms
        elapsed_time = 0.0
        
        logger.info(f"Waiting for Kalshi connection to establish (max {max_wait_time}s)...")
        
        while elapsed_time < max_wait_time:
            if self.is_connected:
                logger.info(f"Kalshi client connected successfully for ticker: {self.ticker} (took {elapsed_time:.1f}s)")
                return True
            
            await asyncio.sleep(check_interval)
            elapsed_time += check_interval
        
        logger.error(f"Failed to connect Kalshi client for ticker: {self.ticker} within {max_wait_time}s timeout")
        return False
    
    async def addTicker(self, newTicker: str, connection_sid: int, tracker_id: int):
        """
        Add a ticker to the current subscription. Checks connection state and calls _attempt_addTicker.
        Args:
            newTicker: The ticker to add
            connection_sid: The sid of the channel (tracked by MarketsManager)
            tracker_id: The id for this update message (provided by MarketsManager)
        Raises:
            RuntimeError if websocket is not connected
        """
        # Check whether the websocket is there and is_connected is true
        if not self.websocket or not self.is_connected:
            logger.error("WebSocket is not connected or not initialized. Cannot add ticker.")
            raise RuntimeError("WebSocket is not connected or not initialized. Cannot add ticker.")
        # Call the private function to attempt adding the ticker
        await self._attempt_addTicker(newTicker, connection_sid, tracker_id)

    async def _attempt_addTicker(self, newTicker: str, connection_sid: int, tracker_id: int):
        '''
        Attempt adding a ticker to some existing subscription asynchronously

        Args:
        connection_sid represents the original sid of the channel that was subscribed to. It is tracked by the [MarketsManager.py] class
        tracker_id represents the id of this message provided by the [MarketsManager] class.

        Returns:
        New message
        '''
        updateMessage = {
            "id": tracker_id,
            "cmd": "update_subscription",
            "params": {
                "sids": [connection_sid],
                "market_tickers": [newTicker],
                "action": "add_markets" #addMarkets in the @kalshi API
            }
            
        }
        logger.debug(f"Sending update subscription message: {updateMessage}")
        await self.websocket.send(json.dumps(updateMessage))

    async def removeTicker(self, oldTicker: str, connection_sid: int, tracker_id: int):
        """
        Remove a ticker from the current subscription. Checks connection state and calls _attempt_removeTicker.
        Args:
            oldTicker: The ticker to remove
            connection_sid: The sid of the channel (tracked by MarketsManager)
            tracker_id: The id for this update message (provided by MarketsManager)
        Raises:
            RuntimeError if websocket is not connected
        """
        if not self.websocket or not self.is_connected:
            logger.error("WebSocket is not connected or not initialized. Cannot remove ticker.")
            raise RuntimeError("WebSocket is not connected or not initialized. Cannot remove ticker.")
        await self._attempt_removeTicker(oldTicker, connection_sid, tracker_id)

    async def _attempt_removeTicker(self, oldTicker: str, connection_sid: int, tracker_id: int):
        '''
        Attempt removing a ticker from an existing subscription asynchronously

        Args:
        connection_sid represents the original sid of the channel that was subscribed to. It is tracked by the [MarketsManager.py] class
        tracker_id represents the id of this message provided by the [MarketsManager] class.

        Returns:
        New message
        '''
        updateMessage = {
            "id": tracker_id,
            "cmd": "update_subscription",
            "params": {
                "sids": [connection_sid],
                "market_tickers": [oldTicker],
                "action": "delete_markets" # delete markets in the @kalshiAPI
            }
            
        }
        logger.debug(f"Sending update subscription message (remove): {updateMessage}")
        await self.websocket.send(json.dumps(updateMessage))

    async def _connect_with_retry(self) -> None:
        """Main connection loop with retry logic and monitoring."""
        while self.should_reconnect:
            try:
                ws_url = self._get_ws_url()
                auth_headers = self._create_auth_headers("GET", "/trade-api/ws/v2")
                logger.info(f"Connecting to Kalshi WebSocket: {ws_url}")
                logger.debug(f"[_connect_with_retry] Auth headers: {auth_headers}")
                
                async with websockets.connect(ws_url, additional_headers=auth_headers) as websocket:
                    self.websocket = websocket
                    self.is_connected = True
                    self.last_message_time = datetime.now()
                    
                    if self.on_connection_callback:
                        logger.debug("[_connect_with_retry] Calling on_connection_callback(True)")
                        self.on_connection_callback(True)
                    
                    logger.info(f"Successfully connected to Kalshi for ticker: {self.ticker}")
                    
                    # Subscribe immediately upon connection
                    await self._subscribe_to_channel()
                    
                    # Run message handler and connection monitor concurrently
                    await asyncio.gather(
                        self._websocket_handler(),
                        self._monitor_connection()
                    )
                    
            except websockets.ConnectionClosed as e:
                logger.warning(f"Connection closed: {e.code} {e.reason}")
                self.is_connected = False
                if self.on_connection_callback:
                    self.on_connection_callback(False)
            except Exception as e:
                logger.error(f"Error connecting to Kalshi: {e}")
                self.is_connected = False
                if self.on_connection_callback:
                    self.on_connection_callback(False)
                if self.on_error_callback:
                    self.on_error_callback(e)
            
            if self.should_reconnect:
                logger.info(f"Reconnecting in {self.config.reconnect_interval} seconds...")
                await asyncio.sleep(self.config.reconnect_interval)

    async def disconnect(self) -> None:
        """Disconnect from Kalshi WebSocket."""
        logger.info("Shutting down Kalshi client...")
        self.should_reconnect = False
        self.is_connected = False
        
        if self.websocket:
            try:
                await self.websocket.close()
            except Exception as e:
                logger.error(f"Error disconnecting WebSocket: {e}")
        
        if self.on_connection_callback:
            self.on_connection_callback(False)
        
        logger.info("Kalshi client shutdown complete")

    def is_running(self) -> bool:
        return self.is_connected and self.should_reconnect

    def get_status(self) -> Dict[str, Any]:
        return {
            "connected": self.is_connected,
            "should_reconnect": self.should_reconnect,
            "ticker": self.ticker,
            "channel": self.channel,
            "last_message_time": self.last_message_time.isoformat() if self.last_message_time else None,
            "environment": self.config.environment.value,
        }

# Convenience function for quick setup

def create_kalshi_client(
    ticker: str,
    channel: str = "orderbook_delta",
    environment: Environment = Environment.DEMO,
    ping_interval: int = 30,
    log_level: str = "INFO"
) -> KalshiClient:
    config = KalshiClientConfig(
        ticker=ticker,
        channel=channel,
        environment=environment,
        ping_interval=ping_interval,
        log_level=log_level
    )
    return KalshiClient(config)
