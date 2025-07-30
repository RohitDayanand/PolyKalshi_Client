"""
Trading Engine Package

Provides automated arbitrage order execution capabilities.
"""

from .trading_engine import TradingEngine, TradingSettings
from .order_executor import OrderExecutor
from .redis_arbitrage_bridge import (
    RedisArbitragePublisher,
    RedisArbitrageSubscriber,
    initialize_redis_publisher,
    publish_arbitrage_alert_to_redis
)

__all__ = [
    "TradingEngine", 
    "TradingSettings",
    "OrderExecutor", 
    "RedisArbitragePublisher",
    "RedisArbitrageSubscriber",
    "initialize_redis_publisher",
    "publish_arbitrage_alert_to_redis"
]