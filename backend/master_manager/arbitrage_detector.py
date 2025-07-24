"""
ArbitrageDetector - Event-driven arbitrage detection coordinator.

This module handles event subscriptions, triggers, and coordinates with ArbitrageCalculator
for pure calculation logic. It acts as the bridge between market events and arbitrage detection.
The ArbitrageManager handles pair registration, state management, and coordination.
"""

import logging
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass

from .events.event_bus import EventBus
from .kalshi_client.models.orderbook_state import OrderbookState as KalshiOrderbookState, OrderbookSnapshot as KalshiOrderbookSnapshot
from .polymarket_client.models.orderbook_state import PolymarketOrderbookState, PolymarketOrderbookSnapshot
from .arbitrage_calculator import ArbitrageCalculator, ArbitrageOpportunity

logger = logging.getLogger()

def arbitrage_detection_log(message: str) -> None:
    """Log arbitrage detection messages with consistent formatting."""
    logger.info(f"[ARBITRAGE_DETECTION] {message}")

# Re-export ArbitrageOpportunity as ArbitrageAlert for backward compatibility
ArbitrageAlert = ArbitrageOpportunity

class ArbitrageDetector:
    """
    Event-driven arbitrage detection coordinator.
    
    This class handles:
    - Event subscriptions and triggers from market data updates
    - Coordination with ArbitrageCalculator for pure calculation logic
    - Publishing arbitrage alerts via EventBus
    - No state caching - uses fresh snapshots for atomic consistency
    """
    
    def __init__(self, event_bus: EventBus, min_spread_threshold: float = 0.05, min_trade_size: float = 10.0):
        """
        Initialize the arbitrage detector.
        
        Args:
            event_bus: EventBus instance for communication and alert publishing
            min_spread_threshold: Minimum spread required to trigger arbitrage alert
            min_trade_size: Minimum trade size threshold for execution
        """
        self.event_bus = event_bus
        self.calculator = ArbitrageCalculator(min_spread_threshold, min_trade_size)
        
        # Subscribe to price change events as triggers (no state caching)
        self._subscribe_to_events()
        
        logger.info(f"ArbitrageDetector initialized with min_spread_threshold={min_spread_threshold}, min_trade_size={min_trade_size}")
        logger.info("Using event-triggered, snapshot-based arbitrage detection with separated calculation logic")
    
    def _subscribe_to_events(self):
        """Subscribe to price change events as triggers (no state caching)."""
        # Subscribe to Kalshi ticker updates (passes sid)
        self.event_bus.subscribe('kalshi.bid_ask_updated', self._handle_kalshi_bid_ask_change)
        
        # Subscribe to Polymarket best bid/ask updates (passes condition_id for identification)
        self.event_bus.subscribe('polymarket.bid_ask_updated', self._handle_polymarket_bid_ask_change)
        # Optionally, keep other subscriptions as needed
        logger.info("ArbitrageDetector subscribed to polymarket.bid_ask_updated events as triggers")

    async def _handle_kalshi_bid_ask_change(self, event_data: Dict[str, Any]):
        """
        Handle Kalshi orderbook update events as triggers.
        
        Event data format:
        {
            'platform': str,
            'sid': int,
            'orderbook_state': OrderbookState,  # Ignored - we use fresh snapshots
            'market_ticker': str,
            'timestamp': str
        }
        """
        try:
            ticker = event_data.get('market_ticker')
            
            if not ticker:
                logger.warning("Invalid kalshi.orderbook_update event data - missing market_ticker")
                return
            
            logger.debug(f"🔄 ARBITRAGE: Kalshi orderbook update for ticker={ticker}, triggering arbitrage check")
            await self._notify_kalshi_update(ticker)
            
        except Exception as e:
            logger.error(f"Error handling Kalshi orderbook update: {e}")
    
    async def _handle_polymarket_bid_ask_change(self, event_data: Dict[str, Any]):
        """
        Handle Polymarket price change events as triggers.
        
        Event data format:
        {
            'asset_id': str,
            'orderbook_state': PolymarketOrderbookState,  # Ignored - we use fresh snapshots
            'price_changed': bool,
            'market': str
        }
        """
        try:
            asset_id = event_data.get('asset_id')
            price_changed = event_data.get('price_changed', False)
            
            if not asset_id:
                logger.warning("Invalid polymarket.price_change event data - missing asset_id")
                return
            
            # Only trigger arbitrage check if price actually changed
            if price_changed:
                logger.debug(f"🔄 ARBITRAGE CHECK: Polymarket price change for asset_id={asset_id}, triggering arbitrage check")
                await self._notify_polymarket_update(asset_id)
            
        except Exception as e:
            logger.error(f"Error handling Polymarket price change: {e}")

    async def _handle_polymarket_orderbook_update(self, event_data: Dict[str, Any]):
        """
        Handle Polymarket orderbook update events as triggers.
        
        Event data format:
        {
            'platform': str,
            'asset_id': str,
            'orderbook_state': PolymarketOrderbookState,  # Ignored - we use fresh snapshots
            'market': str,
            'timestamp': str
        }
        """
        try:
            asset_id = event_data.get('asset_id')
            
            if not asset_id:
                logger.warning("Invalid polymarket.orderbook_update event data - missing asset_id")
                return
            
            logger.debug(f"🔄 ARBITRAGE: Polymarket orderbook update for asset_id={asset_id}, triggering arbitrage check")
            await self._notify_polymarket_update(asset_id)
            
        except Exception as e:
            logger.error(f"Error handling Polymarket orderbook update: {e}")
    
    async def _notify_kalshi_update(self, ticker: str):
        """Notify that Kalshi has updated - ArbitrageManager will handle pair matching."""
        await self.event_bus.publish('arbitrage.kalshi_updated', {
            'ticker': ticker,
            'timestamp': datetime.now().isoformat()
        })
    
    async def _notify_polymarket_update(self, asset_id: str):
        """Notify that Polymarket has updated - ArbitrageManager will handle pair matching."""
        await self.event_bus.publish('arbitrage.polymarket_updated', {
            'asset_id': asset_id,
            'timestamp': datetime.now().isoformat()
        })
    
    async def check_arbitrage_for_pair(self, pair_name: str, 
                                     kalshi_orderbook_state: KalshiOrderbookState,
                                     poly_yes_orderbook_state: PolymarketOrderbookState, 
                                     poly_no_orderbook_state: PolymarketOrderbookState) -> List[ArbitrageAlert]:
        """
        Check arbitrage for a specific pair using immutable orderbook snapshots.
        This ensures atomic price calculations across platforms at the exact same moment.
        
        Args:
            pair_name: Market pair identifier
            kalshi_orderbook_state: Kalshi OrderbookState for direct snapshot access
            poly_yes_orderbook_state: Polymarket YES OrderbookState for snapshot access
            poly_no_orderbook_state: Polymarket NO OrderbookState for snapshot access
            
        Returns:
            List of arbitrage alerts (empty if no opportunities found)
        """
        # Get immutable snapshots at exact same moment - atomic consistency
        kalshi_snapshot = kalshi_orderbook_state.get_snapshot()
        poly_yes_snapshot = poly_yes_orderbook_state.get_snapshot()
        poly_no_snapshot = poly_no_orderbook_state.get_snapshot()
        
        logger.debug(f"🔄 ARBITRAGE: Checking {pair_name} - using immutable snapshots")
        logger.debug(f"   Kalshi sid={kalshi_snapshot.sid}, Poly YES={poly_yes_snapshot.asset_id}, NO={poly_no_snapshot.asset_id}")
        
        # Log arbitrage detection attempt
        arbitrage_detection_log(f"🔍 ARBITRAGE CHECK | pair={pair_name} | kalshi_sid={kalshi_snapshot.sid} | poly_yes={poly_yes_snapshot.asset_id} | poly_no={poly_no_snapshot.asset_id}")
        
        # Delegate to pure calculation logic
        opportunities = self.calculator.calculate_arbitrage_opportunities(
            pair_name, kalshi_snapshot, poly_yes_snapshot, poly_no_snapshot
        )
        
        # Convert ArbitrageOpportunity to ArbitrageAlert for backward compatibility
        return opportunities
    
    
    async def publish_arbitrage_alert(self, alert: ArbitrageAlert):
        """
        Publish arbitrage alert via EventBus for distribution to frontend WebSocket clients.
        
        This method publishes an 'arbitrage.alert' event containing the ArbitrageOpportunity data.
        The event flows through this path:
        
        1. ArbitrageDetector publishes 'arbitrage.alert' event
        2. MarketsCoordinator subscribes to 'arbitrage.alert' and receives the event
        3. MarketsCoordinator calls publish_arbitrage_alert() from websocket_server
        4. WebSocket server broadcasts to all connected frontend clients via ChannelManager
        5. Frontend receives arbitrage_alert message with 'type': 'arbitrage_alert'
        
        Event data structure:
        {
            'alert': ArbitrageOpportunity,  # Complete arbitrage opportunity object
            'market_pair': str,             # Redundant for quick access
            'spread': float,                # Redundant for quick access
            'direction': str,               # Redundant for quick access
            'timestamp': str                # Redundant for quick access
        }
        
        Args:
            alert (ArbitrageAlert): The arbitrage opportunity to broadcast
        """
        try:
            # Publish to EventBus for other components to consume
            await self.event_bus.publish('arbitrage.alert', {
                'alert': alert.to_dict(),
                'market_pair': alert.market_pair,
                'spread': alert.spread,
                'direction': alert.direction,
                'timestamp': alert.timestamp
            })
            
            logger.info(f"🚨 ARBITRAGE ALERT: {alert.market_pair} - {alert.direction} - spread: {alert.spread:.3f}")
            
        except Exception as e:
            logger.error(f"Error publishing arbitrage alert: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get detector statistics."""
        return {
            'detection_method': 'snapshot-based',
            'min_spread_threshold': self.calculator.min_spread_threshold,
            'event_subscriptions': ['kalshi.bid_ask_updated', 'polymarket.bid_ask_updated'],
            'status': 'active'
        }
        
