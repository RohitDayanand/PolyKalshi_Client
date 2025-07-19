"""
Polymarket orderbook level model.

Represents a single price level in the Polymarket orderbook.
"""

from dataclasses import dataclass


@dataclass
class PolymarketOrderbookLevel:
    """Represents a single price level in the Polymarket orderbook."""
    price: str
    size: str
    
    @property
    def price_float(self) -> float:
        """Get price as float."""
        return float(self.price)
    
    @property 
    def size_float(self) -> float:
        """Get size as float."""
        return float(self.size)

    def set_size(self, size: str) -> None:
        """Set the size of this order level."""
        self.size = size
    
    # We cannot set the price level - the orderbook state will pop the levels if they are 
    # no longer needed