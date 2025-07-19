"""
MessageForwarder - Generic message routing with rate limiting and metadata enhancement

Handles the WebSocket → Queue message forwarding pattern used by both platforms
with consistent rate limiting and metadata enhancement.
"""
import time
import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class MessageForwarder:
    """
    Generic message forwarder that handles WebSocket messages to queue routing.
    
    Features:
    - Platform-agnostic message forwarding
    - Rate limiting with configurable thresholds
    - Automatic metadata enhancement
    - Error handling and logging
    """
    
    def __init__(self, platform: str, queue, rate_limit: int = 1_000_000):
        """
        Initialize the message forwarder.
        
        Args:
            platform: Platform name (e.g., 'kalshi', 'polymarket')
            queue: Queue instance to forward messages to
            rate_limit: Maximum messages per second (default 1M)
        """
        self.platform = platform
        self.queue = queue
        self.rate_limit = rate_limit
        
        # Rate limiting state
        self.message_count = 0
        self.last_reset_time = time.time()
        
        # Statistics
        self.stats = {
            "total_messages": 0,
            "rate_limited_messages": 0,
            "errors": 0,
            "last_message_time": None
        }
        
        logger.info(f"MessageForwarder initialized for {platform} with rate limit {rate_limit}/sec")
    
    async def forward_message(self, raw_message: str, metadata: Dict[str, Any]) -> bool:
        """
        Forward a message to the queue with rate limiting and metadata enhancement.
        
        Args:
            raw_message: Raw message content from WebSocket
            metadata: Original metadata from client
            
        Returns:
            bool: True if message was forwarded, False if rate limited or failed
        """
        # Check rate limit
        if not self._check_rate_limit():
            self.stats["rate_limited_messages"] += 1
            logger.warning(f"Rate limit exceeded for {self.platform}, dropping message")
            return False
        
        try:
            # Enhance metadata with platform-specific information
            enhanced_metadata = self._enhance_metadata(metadata)
            
            # Forward to queue
            await self.queue.put_message(raw_message, enhanced_metadata)
            
            # Update statistics
            self.message_count += 1
            self.stats["total_messages"] += 1
            self.stats["last_message_time"] = datetime.now().isoformat()
            
            logger.debug(f"Message forwarded for {self.platform}: {len(raw_message)} bytes")
            return True
            
        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"Error forwarding message for {self.platform}: {e}")
            return False
    
    def _check_rate_limit(self) -> bool:
        """
        Check if message is within rate limit.
        
        Returns:
            bool: True if within rate limit, False if exceeded
        """
        current_time = time.time()
        
        # Reset counter every second
        if current_time - self.last_reset_time >= 1.0:
            self.message_count = 0
            self.last_reset_time = current_time
        
        return self.message_count < self.rate_limit
    
    def _enhance_metadata(self, original_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enhance metadata with platform-specific information.
        
        Args:
            original_metadata: Original metadata from client
            
        Returns:
            Dict[str, Any]: Enhanced metadata
        """
        enhanced_metadata = {
            **original_metadata,
            "platform": self.platform,
            "timestamp": datetime.now().isoformat(),
            "rate_limit": self.rate_limit,
            "forwarder_stats": {
                "total_messages": self.stats["total_messages"],
                "message_count_this_second": self.message_count
            }
        }
        
        # Add platform-specific metadata
        if self.platform == "kalshi":
            enhanced_metadata["channels"] = original_metadata.get("channels", "orderbook_delta")
        elif self.platform == "polymarket":
            enhanced_metadata["channels"] = ["price", "orderbook"]
        
        return enhanced_metadata
    
    def get_stats(self) -> Dict[str, Any]:
        """Get forwarder statistics."""
        return {
            "platform": self.platform,
            "rate_limit": self.rate_limit,
            "current_message_count": self.message_count,
            "time_until_reset": max(0, 1.0 - (time.time() - self.last_reset_time)),
            **self.stats
        }
    
    def reset_stats(self) -> None:
        """Reset statistics (useful for testing)."""
        self.stats = {
            "total_messages": 0,
            "rate_limited_messages": 0,
            "errors": 0,
            "last_message_time": None
        }
        logger.info(f"MessageForwarder stats reset for {self.platform}")