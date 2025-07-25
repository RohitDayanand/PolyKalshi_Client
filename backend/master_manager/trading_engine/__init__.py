"""
Trading Engine Package

Provides automated arbitrage order execution capabilities.
"""

from .trading_engine import TradingEngine
from .order_executor import OrderExecutor

__all__ = ["TradingEngine", "OrderExecutor"]