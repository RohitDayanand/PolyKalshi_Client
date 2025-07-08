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
from datetime import datetime, timedelta
from typing import Optional, Callable, Dict, List, Any
from pathlib import Path
from cryptography.hazmat.primitives import serialization

# Import from the existing Kalshi client
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'kalshi-starter-code-python'))
from backend.master_manager.tests.kalshi_client import KalshiWebSocketClient, Environment

# Configure logging
logger = logging.getLogger(__name__)


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
        self.kalshi_ws_client: Optional[KalshiWebSocketClient] = None
        self.is_connected = False
        self.should_reconnect = True
        self.last_message_time = datetime.now()
        
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
    
    def _create_kalshi_client(self) -> KalshiWebSocketClient:
        """Create a new Kalshi WebSocket client with custom message handling."""
        client = KalshiWebSocketClient(
            key_id=self.config.key_id,
            private_key=self.config.private_key,
            environment=self.config.environment
        )
        
        # Override the on_message method to add our callback
        original_on_message = client.on_message
        
        async def enhanced_on_message(message):
            """Enhanced message handler that calls our callback."""
            try:
                # Update last message time
                self.last_message_time = datetime.now()
                
                # Parse message
                if isinstance(message, str):
                    data = json.loads(message)
                else:
                    data = message
                
                # Call original handler first (for internal processing)
                await original_on_message(message)
                
                # Call our custom callback if set
                if self.on_message_callback:
                    self.on_message_callback(data)
                    
            except json.JSONDecodeError:
                logger.error("Failed to parse message as JSON")
                if self.on_error_callback:
                    self.on_error_callback(Exception("Invalid JSON message"))
            except Exception as e:
                logger.error(f"Error in enhanced message handler: {e}")
                if self.on_error_callback:
                    self.on_error_callback(e)
        
        # Replace the on_message method
        client.on_message = enhanced_on_message
        
        return client
    
    async def _async_connect(self) -> bool:
        """Async connect method."""
        try:
            self.kalshi_ws_client = self._create_kalshi_client()
            
            # Connect to Kalshi WebSocket
            await self.kalshi_ws_client.connect(self.channel, [self.ticker])
            
            if self.kalshi_ws_client.is_connected:
                self.is_connected = True
                logger.info(f"Successfully connected to Kalshi for ticker: {self.ticker}")
                
                if self.on_connection_callback:
                    self.on_connection_callback(True)
                
                return True
            else:
                logger.error("Failed to establish Kalshi WebSocket connection")
                return False
                
        except Exception as e:
            logger.error(f"Error connecting to Kalshi: {e}")
            if self.on_error_callback:
                self.on_error_callback(e)
            return False
    
    def _run_async_in_thread(self):
        """Run the async connection in a dedicated thread with its own event loop."""
        try:
            # Create new event loop for this thread
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            
            # Run the connection
            success = self._loop.run_until_complete(self._async_connect())
            
            if success:
                # Keep the loop running to handle async operations
                while self.should_reconnect and self.is_connected:
                    time.sleep(0.1)
                    
                    # Check if connection is still alive
                    if (self.kalshi_ws_client and 
                        not self.kalshi_ws_client.is_connected and 
                        self.should_reconnect):
                        
                        logger.warning("Connection lost, attempting to reconnect...")
                        self.is_connected = False
                        if self.on_connection_callback:
                            self.on_connection_callback(False)
                        
                        # Attempt reconnection
                        try:
                            success = self._loop.run_until_complete(self._async_connect())
                            if not success:
                                time.sleep(self.config.reconnect_interval)
                        except Exception as e:
                            logger.error(f"Reconnection failed: {e}")
                            time.sleep(self.config.reconnect_interval)
            
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
        
        # Disconnect Kalshi client
        if self.kalshi_ws_client:
            try:
                if self._loop and not self._loop.is_closed():
                    # Run disconnect in the same loop
                    future = asyncio.run_coroutine_threadsafe(
                        self.kalshi_ws_client.disconnect(), 
                        self._loop
                    )
                    future.result(timeout=5.0)
            except Exception as e:
                logger.error(f"Error disconnecting Kalshi WebSocket: {e}")
        
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
