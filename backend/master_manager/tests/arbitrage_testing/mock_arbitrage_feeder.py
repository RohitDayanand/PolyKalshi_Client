"""
Mock Arbitrage Feeder - Generates Market Data Designed to Trigger Arbitrage Opportunities

This feeder pushes realistic snapshots and deltas to mock servers that create
price spreads exceeding the min_spread_threshold (default 2%).

Key Arbitrage Scenarios:
1. Kalshi YES bid > Polymarket YES ask (sell Kalshi, buy Polymarket)
2. Polymarket YES bid > Kalshi YES ask (sell Polymarket, buy Kalshi)  
3. Kalshi NO bid > Polymarket NO ask (sell Kalshi, buy Polymarket)
4. Polymarket NO bid > Kalshi NO ask (sell Polymarket, buy Kalshi)

Since YES + NO = 1.0, we focus on creating realistic spreads that violate this constraint.
"""

import asyncio
import logging
import random
import time
import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class ArbitrageScenario:
    """Defines a specific arbitrage opportunity scenario"""
    name: str
    description: str
    kalshi_deltas: list  # List of orderbook_delta dicts for Kalshi
    poly_price_changes: list  # List of price_change dicts for Polymarket
    expected_spread: float
    expected_direction: str
    expected_side: str

class MockArbitrageFeeder:
    """
    Feeds arbitrage-triggering market data to mock servers.
    
    This feeder orchestrates price movements across both platforms to create
    realistic arbitrage opportunities that exceed the minimum spread threshold.
    """
    
    def __init__(self, 
                 kalshi_server=None, 
                 polymarket_server=None,
                 min_spread_threshold: float = 0.02,
                 feed_interval: float = 3.0):
        """
        Initialize the arbitrage feeder.
        
        Args:
            kalshi_server: MockKalshiServer instance
            polymarket_server: MockPolymarketServer instance  
            min_spread_threshold: Minimum spread to trigger (default 2%)
            feed_interval: Seconds between price updates
        """
        self.kalshi_server = kalshi_server
        self.polymarket_server = polymarket_server
        self.min_spread_threshold = min_spread_threshold
        self.feed_interval = feed_interval
        
        # Target market identifiers
        self.kalshi_market_ticker = "TEST-MARKET-Y"
        self.kalshi_sid = 1001  # Auto-assigned in mock server
        self.poly_yes_asset_id = "test_token_123"
        self.poly_no_asset_id = "test_token_123_no"
        
        # Feeding state
        self.is_feeding = False
        self.scenario_index = 0
        self.scenarios = self._create_arbitrage_scenarios()
        
        logger.info(f"MockArbitrageFeeder initialized with {len(self.scenarios)} scenarios")
        logger.info(f"Target spread threshold: {min_spread_threshold:.1%}")
    
    def _create_arbitrage_scenarios(self) -> List[ArbitrageScenario]:
        """Create a series of arbitrage scenarios as orderbook_delta and price_change events."""
        scenarios = [
            ArbitrageScenario(
                name="Kalshi YES Overpriced",
                description="Kalshi YES bid > Polymarket YES ask by 3%",
                kalshi_deltas=[
                    {"side": "yes", "price": 72, "delta": 100},  # Add YES bid at 72
                    {"side": "no", "price": 26, "delta": 100}   # Add NO bid at 26
                ],
                poly_price_changes=[
                    {"side": "ask", "price": 0.69, "size": 100.0},  # Polymarket YES ask at 0.69
                    {"side": "bid", "price": 0.68, "size": 100.0}   # Polymarket YES bid at 0.68
                ],
                expected_spread=0.03,
                expected_direction="kalshi_to_polymarket",
                expected_side="yes"
            ),
            ArbitrageScenario(
                name="Polymarket YES Overpriced",
                description="Polymarket YES bid > Kalshi YES ask by 4%",
                kalshi_deltas=[
                    {"side": "yes", "price": 60, "delta": 100},  # Add YES ask at 60
                    {"side": "no", "price": 40, "delta": 100}
                ],
                poly_price_changes=[
                    {"side": "bid", "price": 0.64, "size": 100.0},  # Polymarket YES bid at 0.64
                    {"side": "ask", "price": 0.66, "size": 100.0}
                ],
                expected_spread=0.04,
                expected_direction="polymarket_to_kalshi",
                expected_side="yes"
            ),
            ArbitrageScenario(
                name="Kalshi NO Overpriced",
                description="Kalshi NO bid > Polymarket NO ask by 2.5%",
                kalshi_deltas=[
                    {"side": "no", "price": 55, "delta": 100},  # Add NO bid at 55
                    {"side": "yes", "price": 43, "delta": 100}
                ],
                poly_price_changes=[
                    {"side": "ask", "price": 0.525, "size": 100.0},  # Polymarket NO ask at 0.525
                    {"side": "bid", "price": 0.52, "size": 100.0}
                ],
                expected_spread=0.025,
                expected_direction="kalshi_to_polymarket",
                expected_side="no"
            ),
            ArbitrageScenario(
                name="Polymarket NO Overpriced",
                description="Polymarket NO bid > Kalshi NO ask by 3.5%",
                kalshi_deltas=[
                    {"side": "no", "price": 38, "delta": 100},  # Add NO ask at 38
                    {"side": "yes", "price": 62, "delta": 100}
                ],
                poly_price_changes=[
                    {"side": "bid", "price": 0.415, "size": 100.0},  # Polymarket NO bid at 0.415
                    {"side": "ask", "price": 0.42, "size": 100.0}
                ],
                expected_spread=0.035,
                expected_direction="polymarket_to_kalshi",
                expected_side="no"
            ),
            ArbitrageScenario(
                name="Extreme Arbitrage",
                description="Large price discrepancy - 5% spread",
                kalshi_deltas=[
                    {"side": "yes", "price": 75, "delta": 100},
                    {"side": "no", "price": 23, "delta": 100}
                ],
                poly_price_changes=[
                    {"side": "ask", "price": 0.70, "size": 100.0},
                    {"side": "bid", "price": 0.69, "size": 100.0}
                ],
                expected_spread=0.05,
                expected_direction="kalshi_to_polymarket",
                expected_side="yes"
            ),
            ArbitrageScenario(
                name="Market Equilibrium",
                description="No arbitrage opportunity - tight spreads",
                kalshi_deltas=[
                    {"side": "yes", "price": 65, "delta": 100},
                    {"side": "no", "price": 34, "delta": 100}
                ],
                poly_price_changes=[
                    {"side": "bid", "price": 0.645, "size": 100.0},
                    {"side": "ask", "price": 0.655, "size": 100.0}
                ],
                expected_spread=0.005,
                expected_direction="none",
                expected_side="none"
            )
        ]
        return scenarios
    
    async def start_feeding(self, duration_seconds: Optional[int] = None):
        """
        Start feeding arbitrage scenarios to mock servers.
        
        Args:
            duration_seconds: How long to feed data (None = indefinite)
        """
        if not self.kalshi_server or not self.polymarket_server:
            logger.error("Cannot start feeding - mock servers not provided")
            return
            
        if self.is_feeding:
            logger.warning("Arbitrage feeder already running")
            return
            
        self.is_feeding = True
        self.scenario_index = 0
        
        logger.info(f"🎯 Starting arbitrage feeder - {len(self.scenarios)} scenarios")
        logger.info(f"📊 Feed interval: {self.feed_interval}s, Duration: {duration_seconds or 'indefinite'}s")
        
        start_time = datetime.now()
        
        try:
            while self.is_feeding:
                # Check duration limit
                if duration_seconds:
                    elapsed = (datetime.now() - start_time).total_seconds()
                    if elapsed >= duration_seconds:
                        logger.info(f"⏰ Feeding duration reached: {elapsed:.1f}s")
                        break
                
                # Feed current scenario
                await self._feed_current_scenario()
                
                # Move to next scenario
                self.scenario_index = (self.scenario_index + 1) % len(self.scenarios)
                
                # Wait before next update
                await asyncio.sleep(self.feed_interval)
                
        except Exception as e:
            logger.error(f"Error in arbitrage feeding: {e}")
        finally:
            self.is_feeding = False
            logger.info("🛑 Arbitrage feeder stopped")
    
    async def _feed_current_scenario(self):
        """Feed the current arbitrage scenario to both mock servers as deltas/price changes."""
        scenario = self.scenarios[self.scenario_index]

        logger.info(f"📈 Feeding scenario: {scenario.name}")
        logger.info(f"   📋 {scenario.description}")

        # Send Kalshi orderbook_delta events with override data
        sid = self.kalshi_server._find_market_by_ticker(self.kalshi_market_ticker)
        if sid is not None:
            subscribed_clients = [
                ws for ws, client_data in self.kalshi_server.connected_clients.items()
                if sid in client_data["subscriptions"]
            ]
            
            for delta in scenario.kalshi_deltas:
                await self.kalshi_server._send_orderbook_delta(subscribed_clients, sid, delta_override=delta)

        # Send Polymarket price_change events with override data
        subscribed_clients = [
            ws for ws, client_data in self.polymarket_server.connected_clients.items()
            if self.poly_yes_asset_id in client_data["subscriptions"]
        ]
        
        # Ensure the market exists
        if self.poly_yes_asset_id not in self.polymarket_server.market_states:
            self.polymarket_server.add_market(self.poly_yes_asset_id, "test-market-yes", 0.5)
        
        for price_change in scenario.poly_price_changes:
            await self.polymarket_server._send_price_change(subscribed_clients, self.poly_yes_asset_id, price_change_override=price_change)

        # Log expected arbitrage
        if scenario.expected_spread >= self.min_spread_threshold:
            logger.info(f"   🚨 Expected arbitrage: {scenario.expected_direction} {scenario.expected_side}")
            logger.info(f"   💰 Expected spread: {scenario.expected_spread:.1%}")
        else:
            logger.info(f"   📊 No arbitrage expected (spread: {scenario.expected_spread:.1%})")

    async def stop_feeding(self):
        """Stop the arbitrage feeder."""
        logger.info("🛑 Stopping arbitrage feeder...")
        self.is_feeding = False
    
    def get_current_scenario(self) -> ArbitrageScenario:
        """Get the currently active scenario."""
        return self.scenarios[self.scenario_index]
    
    def get_scenario_summary(self) -> Dict:
        """Get summary of all scenarios."""
        return {
            'total_scenarios': len(self.scenarios),
            'current_index': self.scenario_index,
            'arbitrage_scenarios': len([s for s in self.scenarios if s.expected_spread >= self.min_spread_threshold]),
            'equilibrium_scenarios': len([s for s in self.scenarios if s.expected_spread < self.min_spread_threshold]),
            'scenarios': [
                {
                    'name': s.name,
                    'expected_spread': s.expected_spread,
                    'direction': s.expected_direction,
                    'side': s.expected_side
                }
                for s in self.scenarios
            ]
        }

# Utility function for easy integration
async def run_arbitrage_feeding_demo(kalshi_server, polymarket_server, duration: int = 30):
    """
    Run a demonstration of arbitrage feeding for testing.
    
    Args:
        kalshi_server: MockKalshiServer instance
        polymarket_server: MockPolymarketServer instance
        duration: Duration in seconds
    """
    feeder = MockArbitrageFeeder(kalshi_server, polymarket_server)
    
    print("🎯 ARBITRAGE FEEDING DEMO")
    print("=" * 40)
    
    summary = feeder.get_scenario_summary()
    print(f"📊 Scenarios: {summary['total_scenarios']} total, {summary['arbitrage_scenarios']} arbitrage")
    print(f"⏰ Duration: {duration} seconds")
    print()
    
    await feeder.start_feeding(duration_seconds=duration)
    
    print("✅ Arbitrage feeding demo completed")