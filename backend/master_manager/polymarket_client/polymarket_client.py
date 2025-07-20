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
import time
import threading
import logging
import os
from datetime import datetime, timedelta
from typing import Optional, Callable, Dict, List, Any
from pathlib import Path
import asyncio
import websockets

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class PolymarketClientConfig:
    """Configuration class for Polymarket client."""
    
    def __init__(
        self,
        slug: str,
        ws_url: Optional[str] = None,
        ping_interval: int = 10,
        reconnect_interval: int = 5,
        log_level: str = "INFO",
        token_ids: List[str] = [""],
        debug_websocket_logging: bool = False,
        debug_log_file: str = "polymarket_debug.txt"
    ):
        self.slug = slug
        # Dynamic URL support: env var > parameter > default
        self.ws_url = (
            os.getenv('POLYMARKET_WS_URL') or 
            ws_url or 
            "wss://ws-subscriptions-clob.polymarket.com/ws/market"
        )
        self.ping_interval = ping_interval
        self.reconnect_interval = reconnect_interval
        self.log_level = log_level
        self.token_id = token_ids
        self.debug_websocket_logging = debug_websocket_logging
        self.debug_log_file = debug_log_file


class PolymarketClient:
    """
    Fully async Polymarket WebSocket client for real-time market data using websockets and asyncio.
    Handles connection, reconnection, ping, and subscription in a fully async manner.
    """
    def __init__(self, config: PolymarketClientConfig):
        self.config = config
        self.slug = config.slug
        self.ws_url = config.ws_url
        self.ping_interval = config.ping_interval
        self.reconnect_interval = config.reconnect_interval
        self.token_id = config.token_id
        self.log_level = config.log_level
        self.debug_websocket_logging = config.debug_websocket_logging
        self.debug_log_file = config.debug_log_file
        self.websocket = None
        self.is_connected = False
        self.should_reconnect = True
        self.last_pong = datetime.now()
        self.on_message_callback: Optional[Callable[[str, Dict], None]] = None
        self.on_connection_callback: Optional[Callable[[bool], None]] = None
        self.on_error_callback: Optional[Callable[[Exception], None]] = None
        
        # Initialize debug logging if enabled
        self.debug_logger = None
        if self.debug_websocket_logging:
            self._setup_debug_logger()
        

    def set_message_callback(self, callback: Callable[[str, Dict], None]) -> None:
        self.on_message_callback = callback

    def set_connection_callback(self, callback: Callable[[bool], None]) -> None:
        self.on_connection_callback = callback

    def set_error_callback(self, callback: Callable[[Exception], None]) -> None:
        self.on_error_callback = callback

    def _setup_debug_logger(self):
        """Set up dedicated debug logger for WebSocket messages."""

    def _log_debug(self, direction: str, message: str):
        """Log debug message to file if debug logging is enabled."""
        if not self.debug_websocket_logging:
            return
        
        timestamp = datetime.now().isoformat()
        try:
            with open(self.debug_log_file, 'a') as f:
                f.write(f"[{timestamp}] {direction}: {message}\n")
        except Exception as e:
            logger.error(f"Failed to write to debug log: {e}")

    async def subscribe(self):
        if not self.is_connected or not self.websocket:
            logger.error("WebSocket not connected. Cannot subscribe.")
            return False
        subscribe_message = {
            "type": "MARKET",
            "assets_ids": self.token_id,
        }
        try:
            message_json = json.dumps(subscribe_message)
            

            outcome_id_map = {self.token_id[0]: "YES"}

            #in case it isn't binary
            if len(self.token_id) > 1:
                outcome_id_map[self.token_id[1]] = "NO"

            #tell the upstream queue what the yes/no market looks like - avoid race conditions
            await self.on_message_callback(json.dumps(outcome_id_map), {"event_type": "token_map"})

            await self.websocket.send(message_json)
            logger.info(f"Subscribed to {len(self.token_id)} assets")

            return True
        except Exception as e:
            logger.error(f"Failed to send subscription message: {e}")
            await self.websocket.close()
            return False

    async def handle_messages(self):
        try:
            async for message in self.websocket:
                # Send raw message to queue without full decoding
                if self.on_message_callback:
                    metadata = {
                        "token_hint": message[14:22], #at id 14, we begin the assetid. We want to try pattern matching in case we can quick index
                        "timestamp": datetime.now()
                    }
                    # Pass raw message string, not decoded JSON
                    await self.on_message_callback(message, metadata)
                    
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            self._log_debug("ERROR", f"WebSocket error in handle_messages: {e}")
            if self.on_error_callback:
                self.on_error_callback(e)
            self.is_connected = False

    async def connect(self):
        """
        Connect to Polymarket WebSocket with full async approach.
        Uses background task for long-running connection and returns quickly.
        """
        logger.debug("connect() called")
        
        # Start the connection as a background task since it's long-running
        asyncio.create_task(self._connect_with_retry())
        
        # Give connection time to establish
        await asyncio.sleep(2)
        
        if self.is_connected:
            logger.info(f"Polymarket client started for market: {self.slug}")
            return True
        else:
            logger.error(f"Failed to start Polymarket client for market: {self.slug}")
            return False

    async def _connect_with_retry(self):
        """Main connection loop with retry logic and monitoring."""
        while self.should_reconnect:
            try:
                logger.info(f"Connecting to WebSocket URL: {self.ws_url}")
                self._log_debug("CONNECT", f"Attempting connection to {self.ws_url}")
                async with websockets.connect(self.ws_url, ping_interval=10) as websocket:
                    self.websocket = websocket
                    self.is_connected = True
                    self.last_pong = datetime.now()
                    if self.on_connection_callback:
                        self.on_connection_callback(True)
                    logger.info("WebSocket connection opened (async)")
                    self._log_debug("CONNECT", "WebSocket connection established successfully")
                    
                    # Immediately subscribe upon connection
                    await self.subscribe()
                    
                    # Start ping and message handler concurrently
                    self._log_debug("CONNECT", "Starting ping sender and message handler")
                    await asyncio.gather(
                        self.handle_messages()
                    )
            except Exception as e:
                logger.error(f"Connection error: {e}")
                self._log_debug("ERROR", f"Connection error: {e}")
                self.is_connected = False
                if self.on_connection_callback:
                    self.on_connection_callback(False)
                if self.on_error_callback:
                    self.on_error_callback(e)
                
                if self.should_reconnect:
                    logger.info(f"Reconnecting in {self.reconnect_interval} seconds...")
                    self._log_debug("RECONNECT", f"Waiting {self.reconnect_interval} seconds before reconnect attempt")
                    await asyncio.sleep(self.reconnect_interval)

    async def disconnect(self):
        logger.info("Shutting down Polymarket client...")
        self._log_debug("DISCONNECT", "Initiating client shutdown")
        self.should_reconnect = False
        if self.websocket:
            await self.websocket.close()
            self._log_debug("DISCONNECT", "WebSocket connection closed")
        self.is_connected = False
        logger.info("Polymarket client shutdown complete")
        self._log_debug("DISCONNECT", "Client shutdown complete")

    def is_running(self) -> bool:
        return self.is_connected and self.should_reconnect

    def get_status(self) -> Dict[str, Any]:
        return {
            "connected": self.is_connected,
            "should_reconnect": self.should_reconnect,
            "slug": self.slug,
            "last_pong": self.last_pong.isoformat() if self.last_pong else None,
            "token_ids_count": len(self.token_id) if self.token_id else 0,
        }


# Convenience function for quick setup
def create_polymarket_client(
    slug: str,
    ping_interval: int = 30,
    log_level: str = "INFO",
    token_ids: list[str] = [""]
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
        log_level=log_level,
        token_ids=token_ids

    )
    return PolymarketClient(config)
