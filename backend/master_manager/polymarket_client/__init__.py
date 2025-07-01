"""
Polymarket Client Package

This package provides a WebSocket client for connecting to Polymarket's real-time market data API.
"""

from .polymarket_client import PolymarketClient, PolymarketClientConfig, create_polymarket_client

__all__ = ['PolymarketClient', 'PolymarketClientConfig', 'create_polymarket_client']