"""
Kalshi-specific async queue for handling raw WebSocket messages.
Maintains separate queue to handle Kalshi orderbook pressure independently.
"""

import asyncio
import logging
from typing import Optional, Callable, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

class KalshiQueue:
    """
    Async queue manager specifically for Kalshi raw messages.
    Handles Kalshi-specific orderbook message flow and processing.
    """
    
    def __init__(self, max_queue_size: int = 1000):
        self.max_queue_size = max_queue_size
        self.queue = asyncio.Queue(maxsize=max_queue_size)
        self.processor_task: Optional[asyncio.Task] = None
        self.message_handler: Optional[Callable[[str, Dict[str, Any]], None]] = None
        self.is_running = False
        
        logger.info(f"KalshiQueue initialized with max_queue_size={max_queue_size}")
    
    def set_message_handler(self, handler: Callable[[str, Dict[str, Any]], None]) -> None:
        """Set the handler for processed Kalshi messages."""
        self.message_handler = handler
        logger.info("Kalshi message handler set")
    
    async def put_message(self, raw_message: str, metadata: Dict[str, Any]) -> None:
        """
        Add a raw Kalshi message to the processing queue.
        
        Args:
            raw_message: Raw WebSocket message string (not decoded)
            metadata: Additional metadata like subscription_id, ticker, etc.
        """
        try:
            message_data = {
                "raw_message": raw_message,
                "metadata": metadata,
                "timestamp": datetime.now().isoformat(),
                "platform": "kalshi"
            }
            await self.queue.put(message_data)
            logger.info(f"[KalshiQueue] Enqueued message: {metadata}")
            logger.debug(f"[KalshiQueue] Queue size after enqueue: {self.queue.qsize()}")
        except asyncio.QueueFull:
            logger.warning("[KalshiQueue] Queue is full, dropping message")
        except Exception as e:
            logger.error(f"[KalshiQueue] Error adding message to queue: {e}")
    
    async def _process_queue(self) -> None:
        """
        Lightweight async processor for Kalshi messages.
        Continuously processes messages from the Kalshi queue.
        """
        logger.info("Kalshi queue processor started")
        import time
        last_stats_time = time.time()
        while self.is_running:
            try:
                message_data = await asyncio.wait_for(self.queue.get(), timeout=1.0)
                logger.info(f"[KalshiQueue] Dequeued message for processing: {message_data['metadata']}")
                if self.message_handler:
                    asyncio.create_task(
                        self._safe_call_handler(message_data["raw_message"], message_data["metadata"])
                    )
                self.queue.task_done()
            except asyncio.TimeoutError:
                pass
            except Exception as e:
                logger.error(f"[KalshiQueue] Error processing message: {e}")
            # Periodically print queue stats
            if time.time() - last_stats_time > 5:
                stats = self.get_stats()
                logger.info(f"[KalshiQueue] Stats: {stats}")
                last_stats_time = time.time()
        logger.info("Kalshi queue processor stopped")
    
    async def _safe_call_handler(self, raw_message: str, metadata: Dict[str, Any]) -> None:
        """Safely call the message handler with error handling."""
        try:
            if asyncio.iscoroutinefunction(self.message_handler):
                await self.message_handler(raw_message, metadata)
            else:
                self.message_handler(raw_message, metadata)
        except Exception as e:
            logger.error(f"Error in Kalshi message handler: {e}")
    
    async def start(self) -> None:
        """Start the async queue processor."""
        if self.is_running:
            logger.warning("Kalshi queue processor is already running")
            return
        
        self.is_running = True
        self.processor_task = asyncio.create_task(self._process_queue())
        logger.info("Kalshi queue processor started")
    
    async def stop(self) -> None:
        """Stop the async queue processor."""
        if not self.is_running:
            return
        
        logger.info("Stopping Kalshi queue processor...")
        self.is_running = False
        
        if self.processor_task:
            self.processor_task.cancel()
            try:
                await self.processor_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Kalshi queue processor stopped")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current Kalshi queue statistics."""
        return {
            "queue_size": self.queue.qsize(),
            "max_queue_size": self.max_queue_size,
            "is_running": self.is_running,
            "processor_running": self.processor_task is not None and not self.processor_task.done()
        }