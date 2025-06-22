"""
Simple Kalshi JSON Formatter

Converts formatted tickers like "KXPRESPOLAND-NT" into Kalshi WebSocket subscription messages.
"""

import json
import time
from typing import Dict, List, Any


def KalshiJsonFormatter(ticker: str, channels: List[str] = None) -> Dict[str, Any]:
    """
    Convert a formatted ticker into a Kalshi WebSocket subscription message.
    
    Args:
        ticker: Already formatted ticker like "KXPRESPOLAND-NT"
        channels: List of channels to subscribe to (default: ["orderbook_delta", "trade"])
        
    Returns:
        Dict containing the WebSocket subscription message
    """
    if channels is None:
        channels = ["orderbook_delta", "trade"]
    
    return {
        "id": int(time.time()),
        "cmd": "subscribe",
        "params": {
            "channels": channels,
            "market_tickers": [ticker]
        }
    }