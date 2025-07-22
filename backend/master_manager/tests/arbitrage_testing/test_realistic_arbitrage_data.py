#!/usr/bin/env python3
"""
Realistic Arbitrage Test with Controlled Market Data

Tests arbitrage detection with precise, realistic orderbook snapshots
that should generate a known number of arbitrage opportunities.
"""

import asyncio
import json
import sys
import os
import logging
from datetime import datetime

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure environment for mock servers BEFORE any imports
os.environ['POLYMARKET_WS_URL'] = 'ws://localhost:8001'
os.environ['KALSHI_WS_URL'] = 'ws://localhost:8002'

# Import components
from backend.master_manager.tests.arbitrage_testing.mock_polymarket_server import MockPolymarketServer
from backend.master_manager.tests.arbitrage_testing.mock_kalshi_server import MockKalshiServer
from backend.master_manager.markets_coordinator import MarketsCoordinator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s 1- %(message)s'
)
logger = logging.getLogger(__name__)

class ControlledArbitrageTest:
    """
    Sends precise orderbook data to test arbitrage detection accuracy.
    """
    
    def __init__(self, kalshi_server, polymarket_server):
        self.kalshi_server = kalshi_server
        self.polymarket_server = polymarket_server
        self.test_scenarios = self._create_realistic_scenarios()
    
    def _create_realistic_scenarios(self):
        """Create realistic arbitrage test scenarios with expected outcomes."""
        return [
            {
                "name": "No Arbitrage - Market Equilibrium",
                "description": "Tight spreads, no arbitrage opportunity",
                "kalshi_prices": {"yes_bid": 64, "yes_ask": 66, "no_bid": 34, "no_ask": 36},
                "poly_prices": {"yes_bid": 0.645, "yes_ask": 0.655, "no_bid": 0.345, "no_ask": 0.355},
                "expected_alerts": 0,
                "reason": "All spreads < 2% threshold"
            },
            {
            "name": "Single YES Arbitrage",
                "description": "Kalshi YES overpriced by exactly 3%",
                "kalshi_prices": {"yes_bid": 70, "yes_ask": 72, "no_bid": 28, "no_ask": 30},
                "poly_prices": {"yes_bid": 0.67, "yes_ask": 0.69, "no_bid": 0.31, "no_ask": 0.33},
                "expected_alerts": 1,
                "reason": "Sell Kalshi YES (70¢), Buy Poly NO (33¢) = 1.03 total > 1.0 → spread = 3%"
            },
            {
                "name": "Single NO Arbitrage", 
                "description": "Kalshi NO overpriced by exactly 2.5%",
                "kalshi_prices": {"yes_bid": 45, "yes_ask": 47, "no_bid": 53, "no_ask": 55},
                "poly_prices": {"yes_bid": 0.47, "yes_ask": 0.49, "no_bid": 0.51, "no_ask": 0.525},
                "expected_alerts": 1,
                "reason": "Sell Kalshi NO (53¢), Buy Poly YES (49¢) = 1.02 total > 1.0 → spread = 2.5%"
            },
            {
                "name": "Extreme Arbitrage - Both Sides",
                "description": "Large spread creating multiple opportunities",
                "kalshi_prices": {"yes_bid": 75, "yes_ask": 77, "no_bid": 20, "no_ask": 22},
                "poly_prices": {"yes_bid": 0.70, "yes_ask": 0.72, "no_bid": 0.25, "no_ask": 0.27},
                "expected_alerts": 2,
                "reason": "Both YES and NO arbitrage opportunities (5%+ spreads each)"
            },
            {
                "name": "Tight Arbitrage - Just Above Threshold",
                "description": "Minimal arbitrage opportunity at 2.1%",
                "kalshi_prices": {"yes_bid": 62, "yes_ask": 64, "no_bid": 36, "no_ask": 38},
                "poly_prices": {"yes_bid": 0.60, "yes_ask": 0.619, "no_bid": 0.381, "no_ask": 0.40},
                "expected_alerts": 1,
                "reason": "Sell Kalshi YES (62¢), Buy Poly NO (40¢) = 1.02 total > 1.0 → spread = 2.1%"
            }
        ]
    
    async def send_controlled_scenario(self, scenario_index: int):
        """Send a specific test scenario to both servers using full orderbook snapshots."""
        scenario = self.test_scenarios[scenario_index]
        
        print(f"\n🎯 Testing Scenario {scenario_index + 1}: {scenario['name']}")
        print(f"   📋 {scenario['description']}")
        print(f"   🎯 Expected alerts: {scenario['expected_alerts']}")
        print(f"   💡 Reason: {scenario['reason']}")
        
        k_prices = scenario["kalshi_prices"]
        p_prices = scenario["poly_prices"]
        
        # Send Kalshi orderbook_snapshot with controlled prices
        await self._send_kalshi_snapshot(k_prices)
        
        # Send Polymarket book snapshots for YES and NO assets with controlled prices
        await self._send_polymarket_snapshots(p_prices)
        
        # Log the raw data being sent
        print(f"   📊 Raw Kalshi Prices: {k_prices}")
        print(f"   📊 Raw Polymarket Prices: {p_prices}")
    
    async def _send_kalshi_snapshot(self, k_prices: dict):
        """Send a complete Kalshi orderbook snapshot with controlled prices."""
        kalshi_sid = self.kalshi_server._find_market_by_ticker("TEST-MARKET-Y")
        if not kalshi_sid:
            print("   ⚠️ Kalshi market TEST-MARKET-Y not found")
            return
            
        kalshi_clients = [
            ws for ws, client_data in self.kalshi_server.connected_clients.items()
            if kalshi_sid in client_data["subscriptions"]
        ]
        
        if not kalshi_clients:
            print("   ⚠️ No Kalshi clients subscribed to TEST-MARKET-Y")
            return
        
        # Update the market's internal state to match our controlled scenario
        market = self.kalshi_server.markets[kalshi_sid]
        market.yes_bid = k_prices["yes_bid"]
        market.yes_ask = k_prices["yes_ask"]
        
        # Clear existing orderbook and rebuild with controlled prices
        market.yes.clear()
        market.no.clear()
        
        # Build YES orderbook levels around our controlled prices
        from backend.master_manager.tests.arbitrage_testing.mock_kalshi_server import MockOrderbookLevel
        
        # YES bids (below yes_ask)
        for i in range(3):
            price = k_prices["yes_bid"] - i
            if price >= 1:
                size = 100 + i * 10  # Varying sizes
                market.yes[str(price)] = MockOrderbookLevel(price=str(price), size=size)
        
        # YES asks (above yes_bid)
        for i in range(3):
            price = k_prices["yes_ask"] + i
            if price <= 99:
                size = 100 + i * 10
                market.yes[str(price)] = MockOrderbookLevel(price=str(price), size=size)
        
        # NO levels (complement of YES prices)
        for yes_price_str in market.yes:
            no_price = 100 - int(yes_price_str)
            if 1 <= no_price <= 99:
                size = 100  # Fixed size for NO
                market.no[str(no_price)] = MockOrderbookLevel(price=str(no_price), size=size)
        
        # Send snapshot to all subscribed clients
        for client in kalshi_clients:
            await self.kalshi_server._send_orderbook_snapshot(client, kalshi_sid)
        
        print(f"   📤 Sent Kalshi snapshot: YES bid={k_prices['yes_bid']}, ask={k_prices['yes_ask']}")
    
    async def _send_polymarket_snapshots(self, p_prices: dict):
        """Send complete Polymarket book snapshots for YES and NO assets."""
        # Send YES asset snapshot
        await self._send_polymarket_asset_snapshot("test_token_123", 
                                                   p_prices["yes_bid"], p_prices["yes_ask"])
        
        # Send NO asset snapshot  
        await self._send_polymarket_asset_snapshot("test_token_123_no", 
                                                   p_prices["no_bid"], p_prices["no_ask"])
    
    async def _send_polymarket_asset_snapshot(self, asset_id: str, bid_price: float, ask_price: float):
        """Send a book snapshot for a specific Polymarket asset."""
        poly_clients = [
            ws for ws, client_data in self.polymarket_server.connected_clients.items()
            if asset_id in client_data["subscriptions"]
        ]
        
        if not poly_clients:
            print(f"   ⚠️ No Polymarket clients subscribed to {asset_id}")
            return
        
        # Update the market's internal state
        if asset_id in self.polymarket_server.market_states:
            market = self.polymarket_server.market_states[asset_id]
            
            # Clear existing levels
            market.bid_levels.clear()
            market.ask_levels.clear()
            
            # Create controlled bid/ask levels around our target prices
            from backend.master_manager.tests.arbitrage_testing.mock_polymarket_server import MockOrderbookLevel
            
            # Create bid levels (descending from bid_price)
            for i in range(3):
                price = bid_price - (i * 0.01)
                if price > 0:
                    size = 100.0 + (i * 10.0)  # Varying sizes
                    market.bid_levels.append(MockOrderbookLevel(
                        price=f"{price:.3f}", 
                        size=f"{size:.2f}"
                    ))
            
            # Create ask levels (ascending from ask_price)
            for i in range(3):
                price = ask_price + (i * 0.01)
                if price < 1.0:
                    size = 100.0 + (i * 10.0)
                    market.ask_levels.append(MockOrderbookLevel(
                        price=f"{price:.3f}", 
                        size=f"{size:.2f}"
                    ))
            
            # Send snapshot to all subscribed clients
            for client in poly_clients:
                await self.polymarket_server._send_book_snapshot(client, asset_id)
            
            asset_type = "YES" if not asset_id.endswith("_no") else "NO"
            print(f"   📤 Sent Polymarket {asset_type} snapshot: bid={bid_price:.3f}, ask={ask_price:.3f}")


async def run_controlled_arbitrage_test():
    """Run controlled arbitrage test with precise market data."""
    
    print("🎯 CONTROLLED ARBITRAGE TEST")
    print("=" * 60)
    print("Testing arbitrage detection with precise, realistic market data")
    print()
    
    # Start mock servers
    poly_server = MockPolymarketServer(port=8001)
    kalshi_server = MockKalshiServer(port=8002)
    
    try:
        await poly_server.start()
        await kalshi_server.start()
        await asyncio.sleep(1)
        
        # Enable controlled mode to disable background noise
        print("🎛️ ENABLING CONTROLLED MODE (disabling background updates)")
        poly_server.set_controlled_mode(True)
        kalshi_server.set_controlled_mode(True)
        
        # Create MarketsCoordinator
        coordinator = MarketsCoordinator()
        await coordinator.start_async_components()
        
        # Connect to markets
        await coordinator.connect("test_token_123,test_token_123_no", "polymarket")
        await coordinator.connect("TEST-MARKET-Y", "kalshi") 
        
        # Wait for initial connection setup to complete
        await asyncio.sleep(2)
        
        # Add arbitrage pair
        coordinator.add_arbitrage_market_pair(
            market_pair="CONTROLLED-TEST",
            kalshi_sid=3,  # TEST-MARKET-Y
            polymarket_yes_asset_id="test_token_123",
            polymarket_no_asset_id="test_token_123_no"
        )
        
        # Track alerts
        detected_alerts = []
        alert_count = 0
        def capture_alert(event_data):
            nonlocal alert_count
            alert = event_data.get('alert')
            if alert:
                alert_count += 1
                detected_alerts.append(alert)
                print(f"   🚨 ALERT #{alert_count}: {alert.direction} {alert.side} - spread: {alert.spread:.3f}")
        
        coordinator.service_coordinator.event_bus.subscribe('arbitrage.alert', capture_alert)
        
        # Create controlled test
        test_runner = ControlledArbitrageTest(kalshi_server, poly_server)
        
        # Run each scenario
        print("\n🧪 RUNNING CONTROLLED SCENARIOS")
        print("-" * 40)
        
        total_expected = 0
        total_detected = 0
        
        for i in range(len(test_runner.test_scenarios)):
            # Clear alerts before each scenario and capture count
            detected_alerts.clear()
            
            print(f"\n⏳ Waiting 3 seconds for system to settle before scenario {i+1}...")
            await asyncio.sleep(3)  # Let the system settle
            
            # Send scenario and wait for processing
            await test_runner.send_controlled_scenario(i)
            
            print(f"   ⏳ Waiting 5 seconds for arbitrage detection to process...")
            await asyncio.sleep(5)  # Give more time for arbitrage detection
            
            # Count unique alerts (deduplication by direction+side combination)
            unique_alerts = set()
            for alert in detected_alerts:
                unique_alerts.add((alert.direction, alert.side))
            
            scenario_alerts = len(unique_alerts)
            expected_alerts = test_runner.test_scenarios[i]["expected_alerts"]
            
            total_expected += expected_alerts
            total_detected += scenario_alerts
            
            status = "✅" if scenario_alerts == expected_alerts else "❌"
            print(f"   {status} Detected: {scenario_alerts}, Expected: {expected_alerts}")
            
            if scenario_alerts != expected_alerts:
                print(f"   ⚠️  MISMATCH! Got {scenario_alerts}, expected {expected_alerts}")
                print(f"   📋 Raw alerts received: {len(detected_alerts)}")
                print(f"   🔄 Unique alert types: {len(unique_alerts)}")
                # Show unique alerts detected
                for j, alert_type in enumerate(unique_alerts):
                    direction, side = alert_type
                    # Find example alert with this type
                    example_alert = next(a for a in detected_alerts if a.direction == direction and a.side == side)
                    print(f"      Alert {j+1}: {direction} {side} - spread: {example_alert.spread:.3f}")
            
            print(f"   ✅ Scenario {i+1} completed")
        
        # Final results
        print(f"\n📊 CONTROLLED TEST RESULTS")
        print(f"   🎯 Scenarios tested: {len(test_runner.test_scenarios)}")
        print(f"   📊 Expected total alerts: {total_expected}")
        print(f"   🚨 Detected total alerts: {total_detected}")
        print(f"   ✅ Accuracy: {'PERFECT' if total_detected == total_expected else 'NEEDS ADJUSTMENT'}")
        
        await coordinator.disconnect_all()
        
    finally:
        await poly_server.stop()
        await kalshi_server.stop()


if __name__ == "__main__":
    asyncio.run(run_controlled_arbitrage_test())