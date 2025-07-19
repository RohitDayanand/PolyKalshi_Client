"""
EventBus - Central communication hub for decoupled component communication

Replaces direct callbacks with an event-driven architecture that allows
components to communicate without tight coupling.
"""
import asyncio
import logging
from typing import Dict, List, Callable, Any, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)

class EventBus:
    """
    Central event bus for decoupled component communication.
    
    Features:
    - Async event handling with exception isolation
    - Multiple subscribers per event type
    - Wildcard event subscriptions
    - Event logging and debugging
    """
    
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self._wildcard_subscribers: List[Callable] = []
        self._event_stats = defaultdict(int)
    
    def subscribe(self, event_type: str, handler: Callable[[Any], Any]) -> None:
        """
        Subscribe to a specific event type.
        
        Args:
            event_type: Event type to subscribe to (e.g., 'kalshi.error', 'polymarket.orderbook_update')
            handler: Async function to handle the event
        """
        if event_type == "*":
            self._wildcard_subscribers.append(handler)
        else:
            self._subscribers[event_type].append(handler)
        
        logger.debug(f"Event subscription added: {event_type} -> {handler.__name__}")
    
    def unsubscribe(self, event_type: str, handler: Callable[[Any], Any]) -> bool:
        """
        Unsubscribe from a specific event type.
        
        Args:
            event_type: Event type to unsubscribe from
            handler: Handler function to remove
            
        Returns:
            bool: True if handler was found and removed
        """
        try:
            if event_type == "*":
                self._wildcard_subscribers.remove(handler)
            else:
                self._subscribers[event_type].remove(handler)
            
            logger.debug(f"Event subscription removed: {event_type} -> {handler.__name__}")
            return True
        except ValueError:
            logger.warning(f"Handler not found for unsubscribe: {event_type} -> {handler.__name__}")
            return False
    
    async def publish(self, event_type: str, event_data: Any) -> List[Exception]:
        """
        Publish an event to all subscribers.
        
        Args:
            event_type: Type of event being published
            event_data: Data to send to subscribers
            
        Returns:
            List[Exception]: Any exceptions that occurred during handling
        """
        logger.debug(f"Publishing event: {event_type} with data: {str(event_data)[:200]}")
        
        self._event_stats[event_type] += 1
        
        # Get all relevant handlers
        handlers = []
        handlers.extend(self._subscribers.get(event_type, []))
        handlers.extend(self._wildcard_subscribers)
        
        if not handlers:
            logger.debug(f"No subscribers for event: {event_type}")
            return []
        
        # Execute all handlers concurrently with exception isolation
        tasks = []
        for handler in handlers:
            task = self._safe_call_handler(handler, event_type, event_data)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Collect exceptions
        exceptions = [result for result in results if isinstance(result, Exception)]
        
        if exceptions:
            logger.warning(f"Event {event_type} had {len(exceptions)} handler exceptions")
            for exc in exceptions:
                logger.warning(f"Handler exception: {exc}")
        
        logger.debug(f"Event {event_type} published to {len(handlers)} handlers, {len(exceptions)} exceptions")
        return exceptions
    
    async def _safe_call_handler(self, handler: Callable, event_type: str, event_data: Any) -> Optional[Exception]:
        """
        Safely call an event handler with exception isolation.
        
        Args:
            handler: Handler function to call
            event_type: Type of event
            event_data: Event data
            
        Returns:
            Exception or None if successful
        """
        try:
            if asyncio.iscoroutinefunction(handler):
                await handler(event_data)
            else:
                handler(event_data)
            return None
        except Exception as e:
            logger.error(f"Exception in event handler {handler.__name__} for {event_type}: {e}")
            return e
    
    def get_stats(self) -> Dict[str, Any]:
        """Get event bus statistics."""
        return {
            "total_subscribers": sum(len(handlers) for handlers in self._subscribers.values()) + len(self._wildcard_subscribers),
            "event_types": len(self._subscribers),
            "wildcard_subscribers": len(self._wildcard_subscribers),
            "event_counts": dict(self._event_stats),
            "subscribers_by_type": {event_type: len(handlers) for event_type, handlers in self._subscribers.items()}
        }
    
    def clear_all_subscriptions(self) -> None:
        """Clear all subscriptions (useful for testing)."""
        self._subscribers.clear()
        self._wildcard_subscribers.clear()
        self._event_stats.clear()
        logger.info("All event subscriptions cleared")

# Global event bus instance
global_event_bus = EventBus()