"""
Simple Kalshi JSON Formatter

Converts formatted tickers like "KXPRESPOLAND-NT" into Kalshi WebSocket subscription messages.
"""

import json
import time
from typing import Dict, List, Any


def KalshiJsonFormatter(tickers: List[str], channels: List[str] = None, subscription_id: int = 1) -> Dict[str, Any]:
    """
    Convert a formatted ticker into a Kalshi WebSocket subscription message.
    
    Args:
        ticker: Already formatted ticker like "KXPRESPOLAND-NT"
        channels: List of channels to subscribe to (default: ["orderbook_delta", "trade"])
        
    Returns:
        Dict containing the WebSocket subscription message
    """
    if channels is None:
        print("Channels was none")
        channels = ["orderbook_delta"]
    
    return {
        "id": subscription_id,
        "cmd": "subscribe",
        "params": {
            "channels": channels,
            "market_tickers": tickers
        }
    }

def PolyJsonFormatter(tokens: List[List[str]]): 
    #flatten the token list and return it
    
    return {
        "type": "market",
        "tokens": [item for sublist in tokens for item in sublist]
    }




