
from enum import Enum
from pydantic import BaseModel

class OHLC(str, Enum):
    OPEN = "open"
    CLOSE = "close"
    HIGH = "high"
    LOW = "low"

def quote_midprice(yes_bid: dict, yes_ask: dict, selected_ohlc: str, isNo: bool = False) -> float | None:

    """
    Compute the rounded midpoint between yes_bid and yes_ask 'close' prices.
    Returns None if either value is missing.
    """
    bid_close = yes_bid.get(selected_ohlc) / 100
    ask_close = yes_ask.get(selected_ohlc) / 100
    
    if bid_close is None or ask_close is None:
        return None
    
    if isNo: 
        return round(((1 - bid_close) + (1 - ask_close)) / 2, 2)

    return round((bid_close + ask_close) / 2, 2)

class ValidRanges(str, Enum):
    MINUTE = "1H"
    HOUR = "1W" 
    DAY = "1M"
    WEEK = "1Y"

    @classmethod
    def _missing_(cls, value):
        if isinstance(value, str):
            for member in cls:
                if member.value.lower() == value.lower():
                    return member
        return None
    
class ValidViews(str, Enum):
    YES = "yes"
    NO = "no"

    @classmethod
    def _missing_(cls, value):
        if isinstance(value, str):
            for member in cls:
                if member.value.lower() == value.lower():
                    return member
        return None
