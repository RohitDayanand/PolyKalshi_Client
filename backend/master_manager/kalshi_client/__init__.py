"""
Kalshi Client Package - WebSocket client and orderbook management for Kalshi markets.

This package provides:
- KalshiClient: WebSocket connection to Kalshi
- KalshiQueue: Message queuing and processing
- KalshiMessageProcessor: Orderbook state management
- Data models: OrderbookLevel, OrderbookState, CandlestickState

Usage:
    from backend.master_manager.kalshi_client import (
        KalshiMessageProcessor,
        OrderbookState, 
        OrderbookLevel,
        CandlestickState
    )
"""

# Core processor
from .message_processor import KalshiMessageProcessor

# Data models  
from .models import OrderbookLevel, OrderbookState, CandlestickState

# Client components
from .kalshi_client import KalshiClient
from .kalshi_queue import KalshiQueue
from .kalshi_client_config import KalshiClientConfig
from .kalshi_environment import Environment

__all__ = [
    # Core processor
    'KalshiMessageProcessor',
    
    # Data models
    'OrderbookLevel', 
    'OrderbookState',
    'CandlestickState',
    
    # Client components
    'KalshiClient',
    'KalshiQueue', 
    'KalshiClientConfig',
    'Environment'
]

# Singleton instance for shared usage (optional pattern)
_shared_processor_instance = None

def get_shared_processor() -> KalshiMessageProcessor:
    """
    Get or create a shared KalshiMessageProcessor instance.
    
    This is useful when you need a singleton pattern for the processor
    across different parts of the application.
    
    Returns:
        KalshiMessageProcessor: Shared processor instance
    """
    global _shared_processor_instance
    if _shared_processor_instance is None:
        _shared_processor_instance = KalshiMessageProcessor()
    return _shared_processor_instance

def reset_shared_processor() -> None:
    """
    Reset the shared processor instance.
    
    Useful for testing or when you need to completely reinitialize
    the processor state.
    """
    global _shared_processor_instance
    if _shared_processor_instance:
        _shared_processor_instance.cleanup()
        _shared_processor_instance = None