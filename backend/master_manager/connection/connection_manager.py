"""
ConnectionManager - Standardized client callback factory and lifecycle management

Creates consistent callback patterns for WebSocket clients across platforms
and manages connection state through the event bus.
"""
import logging
from typing import Callable, Tuple, Dict, Any, Optional
from ..events.event_bus import EventBus
from ..messaging.message_forwarder import MessageForwarder

logger = logging.getLogger(__name__)

class ConnectionManager:
    """
    Manages WebSocket client connections and creates standardized callbacks.
    
    Features:
    - Standardized callback factory for all platforms
    - Event-driven connection state management
    - Platform-agnostic error handling
    - Connection lifecycle tracking
    """
    
    def __init__(self, platform: str, event_bus: EventBus):
        """
        Initialize the connection manager.
        
        Args:
            platform: Platform name (e.g., 'kalshi', 'polymarket')
            event_bus: Event bus for publishing connection events
        """
        self.platform = platform
        self.event_bus = event_bus
        
        # Connection tracking
        self.active_connections: Dict[str, Dict[str, Any]] = {}
        
        logger.info(f"ConnectionManager initialized for {platform}")
    
    def create_client_callbacks(self, client_id: str, message_forwarder: MessageForwarder) -> Tuple[Callable, Callable, Callable]:
        """
        Create standardized callback functions for a WebSocket client.
        
        Args:
            client_id: Unique identifier for the client connection
            message_forwarder: MessageForwarder instance for message routing
            
        Returns:
            Tuple[Callable, Callable, Callable]: (message_callback, connection_callback, error_callback)
        """
        logger.info(f"Creating callbacks for {self.platform} client: {client_id}")
        
        # Track this connection
        self.active_connections[client_id] = {
            "platform": self.platform,
            "status": "initializing",
            "message_count": 0,
            "error_count": 0
        }
        
        async def message_callback(raw_message: str, metadata: Dict[str, Any]):
            """Handle incoming WebSocket messages."""
            try:
                # Forward message through the message forwarder
                success = await message_forwarder.forward_message(raw_message, metadata)
                
                if success:
                    self.active_connections[client_id]["message_count"] += 1
                    logger.debug(f"{self.platform} client {client_id}: Message forwarded")
                else:
                    logger.warning(f"{self.platform} client {client_id}: Message forwarding failed")
                
                # Publish message received event
                await self.event_bus.publish(f'{self.platform}.message_received', {
                    'client_id': client_id,
                    'success': success,
                    'message_size': len(raw_message),
                    'metadata': metadata
                })
                
            except Exception as e:
                self.active_connections[client_id]["error_count"] += 1
                logger.error(f"{self.platform} client {client_id}: Message callback error: {e}")
                
                await self.event_bus.publish(f'{self.platform}.message_error', {
                    'client_id': client_id,
                    'error': str(e),
                    'message_size': len(raw_message) if raw_message else 0
                })
        
        def connection_callback(connected: bool):
            """Handle connection status changes."""
            status = "connected" if connected else "disconnected"
            self.active_connections[client_id]["status"] = status
            
            logger.info(f"{self.platform} client {client_id}: Connection {status}")
            
            # Publish connection status event (sync event)
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(self.event_bus.publish(f'{self.platform}.connection_status', {
                        'client_id': client_id,
                        'connected': connected,
                        'platform': self.platform
                    }))
                else:
                    # If no event loop is running, we can't publish the event
                    logger.warning(f"No event loop running, skipping connection status event for {client_id}")
            except RuntimeError:
                # No event loop available
                logger.warning(f"No event loop available, skipping connection status event for {client_id}")
        
        def error_callback(error: Exception):
            """Handle connection errors."""
            self.active_connections[client_id]["error_count"] += 1
            self.active_connections[client_id]["status"] = "error"
            
            logger.error(f"{self.platform} client {client_id}: Connection error: {error}")
            
            # Publish error event (sync event)
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(self.event_bus.publish(f'{self.platform}.client_error', {
                        'client_id': client_id,
                        'error': str(error),
                        'platform': self.platform
                    }))
                else:
                    logger.warning(f"No event loop running, skipping error event for {client_id}")
            except RuntimeError:
                logger.warning(f"No event loop available, skipping error event for {client_id}")
        
        return message_callback, connection_callback, error_callback
    
    def remove_connection(self, client_id: str) -> bool:
        """
        Remove a connection from tracking.
        
        Args:
            client_id: Client identifier to remove
            
        Returns:
            bool: True if connection was found and removed
        """
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            logger.info(f"{self.platform} client {client_id}: Connection removed from tracking")
            return True
        else:
            logger.warning(f"{self.platform} client {client_id}: Connection not found for removal")
            return False
    
    def get_connection_stats(self, client_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get connection statistics.
        
        Args:
            client_id: Specific client to get stats for, or None for all
            
        Returns:
            Dict[str, Any]: Connection statistics
        """
        if client_id:
            return self.active_connections.get(client_id, {})
        else:
            return {
                "platform": self.platform,
                "total_connections": len(self.active_connections),
                "connections_by_status": self._get_connections_by_status(),
                "total_messages": sum(conn.get("message_count", 0) for conn in self.active_connections.values()),
                "total_errors": sum(conn.get("error_count", 0) for conn in self.active_connections.values()),
                "connections": dict(self.active_connections)
            }
    
    def _get_connections_by_status(self) -> Dict[str, int]:
        """Get count of connections by status."""
        status_counts = {}
        for conn in self.active_connections.values():
            status = conn.get("status", "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1
        return status_counts
    
    def clear_all_connections(self) -> None:
        """Clear all connection tracking (useful for testing)."""
        self.active_connections.clear()
        logger.info(f"All {self.platform} connections cleared")