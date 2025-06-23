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
        ws_url: str = "wss://ws-subscriptions-clob.polymarket.com/ws/market",
        ping_interval: int = 30,
        reconnect_interval: int = 5,
        log_level: str = "INFO",
        token_id: List[str] = [""]
    ):
        self.slug = slug
        self.ws_url = ws_url
        self.ping_interval = ping_interval
        self.reconnect_interval = reconnect_interval
        self.log_level = log_level
        self.token_id = token_id


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
        self.websocket = None
        self.is_connected = False
        self.should_reconnect = True
        self.last_pong = datetime.now()
        self.on_message_callback: Optional[Callable[[str, Dict], None]] = None
        self.on_connection_callback: Optional[Callable[[bool], None]] = None
        self.on_error_callback: Optional[Callable[[Exception], None]] = None
        logger.debug(f"PolymarketClient initialized with slug={self.slug}, token_id={self.token_id}")

    def set_message_callback(self, callback: Callable[[str, Dict], None]) -> None:
        self.on_message_callback = callback

    def set_connection_callback(self, callback: Callable[[bool], None]) -> None:
        self.on_connection_callback = callback

    def set_error_callback(self, callback: Callable[[Exception], None]) -> None:
        self.on_error_callback = callback

    async def subscribe(self):
        if not self.is_connected or not self.websocket:
            logger.error("WebSocket not connected. Cannot subscribe.")
            return False
        subscribe_message = {
            "type": "MARKET",
            "assets_ids": self.token_id,
        }
        try:
            await self.websocket.send(json.dumps(subscribe_message))
            logger.info(f"Subscribed to {len(self.token_id)} assets: {self.token_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to send subscription message: {e}")
            await self.websocket.close()
            return False

    async def send_ping(self):
        while self.should_reconnect:
            if self.is_connected and self.websocket:
                try:
                    await self.websocket.send(json.dumps({"type": "ping"}))
                    logger.debug("Sent ping message")
                except Exception as e:
                    logger.error(f"Failed to send ping: {e}")
                    self.is_connected = False
            await asyncio.sleep(self.ping_interval)

    async def handle_messages(self):
        try:
            async for message in self.websocket:
                logger.debug(f"Received WebSocket message: {message}")
                
                # Handle simple PONG responses without JSON parsing
                if message == "PONG":
                    self.last_pong = datetime.now()
                    logger.debug("Received PONG response")
                    continue
                
                # Handle PONG in JSON format
                try:
                    data = json.loads(message)
                    if isinstance(data, dict) and data.get('type') == 'PONG':
                        self.last_pong = datetime.now()
                        continue
                    elif isinstance(data, list):
                        # Check if any message in array is PONG
                        has_pong = any(msg.get('type') == 'PONG' for msg in data if isinstance(msg, dict))
                        if has_pong:
                            self.last_pong = datetime.now()
                except json.JSONDecodeError:
                    # Not JSON, will be handled by queue processor
                    pass
                
                # Send raw message to queue without full decoding
                if self.on_message_callback:
                    logger.debug("Forwarding raw message to queue")
                    metadata = {
                        "slug": self.slug,
                        "token_id": self.token_id,
                        "subscription_id": f"{self.slug}_market",
                        "timestamp": datetime.now().isoformat()
                    }
                    # Pass raw message string, not decoded JSON
                    await self.on_message_callback(message, metadata)
                    
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
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
                async with websockets.connect(self.ws_url, ping_interval=None) as websocket:
                    self.websocket = websocket
                    self.is_connected = True
                    self.last_pong = datetime.now()
                    if self.on_connection_callback:
                        self.on_connection_callback(True)
                    logger.info("WebSocket connection opened (async)")
                    
                    # Immediately subscribe upon connection
                    await self.subscribe()
                    
                    # Start ping and message handler concurrently
                    await asyncio.gather(
                        self.send_ping(),
                        self.handle_messages()
                    )
            except Exception as e:
                logger.error(f"Connection error: {e}")
                self.is_connected = False
                if self.on_connection_callback:
                    self.on_connection_callback(False)
                if self.on_error_callback:
                    self.on_error_callback(e)
                
                if self.should_reconnect:
                    logger.info(f"Reconnecting in {self.reconnect_interval} seconds...")
                    await asyncio.sleep(self.reconnect_interval)

    async def disconnect(self):
        logger.info("Shutting down Polymarket client...")
        self.should_reconnect = False
        if self.websocket:
            await self.websocket.close()
        self.is_connected = False
        logger.info("Polymarket client shutdown complete")

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
