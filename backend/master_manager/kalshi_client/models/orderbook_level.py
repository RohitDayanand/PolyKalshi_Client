"""
OrderbookLevel - Represents a single price level in the orderbook.
"""

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class OrderbookLevel:
    """Represents a single price level in the orderbook."""
    price: int
    size: int
    side: str 
    
    @property
    def price_float(self) -> float:
        """Get price as float."""
        return float(self.price)
    
    @property 
    def size_float(self) -> float:
        """Get size as float."""
        return float(self.size)
    
    def get_size(self) -> int:
        """Get the current size of this orderbook level."""
        return self.size
    
    def apply_delta(self, delta: int) -> None:
        """Apply a size delta to this orderbook level with logging."""
        old_size = self.size
        self.size += delta
        
        # Conditional logging for debugging
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"📊 LEVEL DELTA: price={self.price}, side={self.side}, "
                        f"old_size={old_size}, delta={delta}, new_size={self.size}")
        
        # Log warning if size goes negative (shouldn't happen in normal operation)
        if self.size <= 0:
            logger.warning(f"⚠️ NEGATIVE SIZE OR MINIMUM SIZE: price={self.price}, side={self.side}, "
                          f"size={self.size} (delta={delta} applied to {old_size})")
        
        # Return size to remove bad keys
        return self.get_size()