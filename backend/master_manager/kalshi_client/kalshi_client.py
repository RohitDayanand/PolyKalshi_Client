import json
import asyncio
import time
import threading
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
LOG_ALL_MESSAGES = True

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
        self._threads: List[threading.Thread] = []
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self.on_message_callback: Optional[Callable[[Dict], None]] = None
        self.on_connection_callback: Optional[Callable[[bool], None]] = None
        self.on_error_callback: Optional[Callable[[Exception], None]] = None

    def set_message_callback(self, callback: Callable[[Dict], None]) -> None:
        self.on_message_callback = callback

    def set_connection_callback(self, callback: Callable[[bool], None]) -> None:
        self.on_connection_callback = callback

    def set_error_callback(self, callback: Callable[[Exception], None]) -> None:
        self.on_error_callback = callback

    def _get_ws_url(self) -> str:
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
            if LOG_ALL_MESSAGES:
                logger.debug(f"[handle_websocket_message] Raw message: {message}")
            if message == "PONG":
                logger.debug("[handle_websocket_message] Received PONG response")
                return
            data = json.loads(message)
            if LOG_ALL_MESSAGES:
                logger.debug(f"[handle_websocket_message] Decoded JSON: {data}")
            if data.get('type') == 'ping':
                pong_message = {"type": "pong"}
                await self.websocket.send(json.dumps(pong_message))
                logger.debug("[handle_websocket_message] Sent PONG in response to ping")
                return
            if self.on_message_callback:
                logger.debug("[handle_websocket_message] Calling on_message_callback")
                self.on_message_callback(data)
        except json.JSONDecodeError:
            logger.error("[handle_websocket_message] Failed to parse message as JSON")
            if self.on_error_callback:
                self.on_error_callback(Exception("Invalid JSON message"))
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
                logger.debug(f"[_websocket_handler] Received message: {message}")
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
        max_retries = 3
        retries = 0
        while self.should_reconnect and retries < max_retries:
            try:
                ws_url = self._get_ws_url()
                auth_headers = self._create_auth_headers("GET", "/trade-api/ws/v2")
                logger.info(f"Connecting to Kalshi WebSocket: {ws_url}")
                logger.debug(f"[_async_connect] Auth headers: {auth_headers}")
                self.websocket = await websockets.connect(
                    ws_url,
                    additional_headers=auth_headers
                )
                self.is_connected = True
                logger.info(f"Successfully connected to Kalshi for ticker: {self.ticker}")
                if self.on_connection_callback:
                    logger.debug("[_async_connect] Calling on_connection_callback(True)")
                    self.on_connection_callback(True)
                await self._subscribe_to_channel()
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
        try:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop.run_until_complete(self._async_connect())
        except Exception as e:
            logger.error(f"Error in async thread: {e}")
            if self.on_error_callback:
                self.on_error_callback(e)
        finally:
            if self._loop and not self._loop.is_closed():
                self._loop.close()

    def _monitor_connection(self) -> None:
        while self.should_reconnect:
            if self.is_connected:
                time_since_last = datetime.now() - self.last_message_time
                if time_since_last > timedelta(seconds=self.config.ping_interval * 3):
                    logger.warning("No messages received recently, connection may be stale")
            time.sleep(self.config.ping_interval)

    def connect(self) -> bool:
        try:
            if not self.config.key_id:
                logger.error("Key ID is required for Kalshi connection")
                return False
            if not self.config.private_key:
                logger.error("Private key is required for Kalshi connection")
                return False
            connect_thread = threading.Thread(target=self._run_async_in_thread)
            connect_thread.daemon = True
            connect_thread.start()
            self._threads.append(connect_thread)
            monitor_thread = threading.Thread(target=self._monitor_connection)
            monitor_thread.daemon = True
            monitor_thread.start()
            self._threads.append(monitor_thread)
            time.sleep(2)
            logger.info(f"Kalshi client started for ticker: {self.ticker}")
            return True
        except Exception as e:
            logger.error(f"Failed to start Kalshi client: {e}")
            if self.on_error_callback:
                self.on_error_callback(e)
            return False

    def disconnect(self) -> None:
        logger.info("Shutting down Kalshi client...")
        self.should_reconnect = False
        self.is_connected = False
        if self.websocket:
            try:
                if self._loop and not self._loop.is_closed():
                    future = asyncio.run_coroutine_threadsafe(
                        self.websocket.close(), 
                        self._loop
                    )
                    future.result(timeout=5.0)
            except Exception as e:
                logger.error(f"Error disconnecting WebSocket: {e}")
        for thread in self._threads:
            if thread.is_alive():
                thread.join(timeout=2.0)
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
    config = KalshiClientConfig(
        ticker=ticker,
        channel=channel,
        environment=environment,
        ping_interval=ping_interval,
        log_level=log_level
    )
    return KalshiClient(config)
