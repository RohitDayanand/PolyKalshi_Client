#!/usr/bin/env python3
"""
Manual Snapshot Arbitrage Testing

Creates precise orderbook snapshots and deltas manually to test arbitrage detection
with complete control over market data. This test bypasses mock server generation
and directly creates the exact orderbook states needed for controlled testing.
"""

import asyncio
import json
import sys
import os
import logging
from datetime import datetime
from typing import Dict, List, Any

# Add parent paths
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Configure environment for mock servers BEFORE any imports
os.environ['POLYMARKET_WS_URL'] = 'ws://localhost:8001'
os.environ['KALSHI_WS_URL'] = 'ws://localhost:8002'

# Import components
from backend.master_manager.tests.arbitrage_testing.mock_polymarket_server import MockPolymarketServer
from backend.master_manager.tests.arbitrage_testing.mock_kalshi_server import MockKalshiServer
from backend.master_manager.markets_coordinator import MarketsCoordinator

# Configure logging with custom levels
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Set up custom logging levels for orderbook snapshots and arbitrage detection
ORDERBOOK_SNAPSHOT_LEVEL = 25
ARBITRAGE_DETECTION_LEVEL = 26
logging.addLevelName(ORDERBOOK_SNAPSHOT_LEVEL, "ORDERBOOK_SNAPSHOT")
logging.addLevelName(ARBITRAGE_DETECTION_LEVEL, "ARBITRAGE_DETECTION")

# Create logger with custom levels enabled
logger = logging.getLogger(__name__)

# Optional: Set specific logger levels to show our custom logs
logging.getLogger("backend.master_manager.kalshi_client.message_processor").setLevel(ORDERBOOK_SNAPSHOT_LEVEL)
logging.getLogger("backend.master_manager.polymarket_client.polymarket_message_processor").setLevel(ORDERBOOK_SNAPSHOT_LEVEL)
logging.getLogger("backend.master_manager.arbitrage_detector").setLevel(ARBITRAGE_DETECTION_LEVEL)

class ManualSnapshotBuilder:
    """
    Builder for creating precise orderbook snapshots without mock server interference.
    Directly sends WebSocket messages with exact orderbook data.
    """
    
    def __init__(self, kalshi_server, polymarket_server):
        self.kalshi_server = kalshi_server
        self.polymarket_server = polymarket_server
    
    async def send_kalshi_orderbook_snapshot(self, market_ticker: str, 
                                           yes_levels: List[Dict], no_levels: List[Dict]):
        """
        Send a complete Kalshi orderbook snapshot with precise price levels.
        Works purely through WebSocket messages without touching mock server internal state.
        
        Args:
            market_ticker: Kalshi market ticker (e.g., "TEST-MARKET-Y")
            yes_levels: List of {"price": int, "size": int} for YES side
            no_levels: List of {"price": int, "size": int} for NO side
        """
        sid = self.kalshi_server._find_market_by_ticker(market_ticker)
        if not sid:
            logger.error(f"Kalshi market {market_ticker} not found")
            return
        
        # Get subscribed clients
        clients = [
            ws for ws, client_data in self.kalshi_server.connected_clients.items()
            if sid in client_data["subscriptions"]
        ]
        
        if not clients:
            logger.warning(f"No clients subscribed to Kalshi market {market_ticker}")
            return
        
        # Create snapshot message in exact Kalshi format (no mock server state manipulation)
        yes_orderbook = [[str(level["price"]), level["size"]] for level in 
                        sorted(yes_levels, key=lambda x: x["price"], reverse=True)]
        no_orderbook = [[str(level["price"]), level["size"]] for level in 
                       sorted(no_levels, key=lambda x: x["price"], reverse=True)]
        
        snapshot_msg = {
            "type": "orderbook_snapshot",
            "sid": sid,
            "seq": 9999,  # Use fixed seq number for controlled testing
            "msg": {
                "market_ticker": market_ticker,
                "yes": yes_orderbook,
                "no": no_orderbook,
                "ts": int(datetime.now().timestamp())
            }
        }
        
        # Send to all clients
        for client in clients:
            try:
                await client.send(json.dumps(snapshot_msg))
                logger.info(f"📤 Sent Kalshi snapshot for {market_ticker}: {len(yes_levels)} YES, {len(no_levels)} NO levels")
            except Exception as e:
                logger.error(f"Error sending Kalshi snapshot: {e}")
    
    async def send_polymarket_book_snapshot(self, asset_id: str, 
                                          bid_levels: List[Dict], ask_levels: List[Dict]):
        """
        Send a complete Polymarket book snapshot with precise price levels.
        Works purely through WebSocket messages without touching mock server internal state.
        
        Args:
            asset_id: Polymarket asset ID (e.g., "test_token_123")
            bid_levels: List of {"price": float, "size": float} for bid side
            ask_levels: List of {"price": float, "size": float} for ask side
        """
        # Get subscribed clients
        clients = [
            ws for ws, client_data in self.polymarket_server.connected_clients.items()
            if asset_id in client_data["subscriptions"]
        ]
        
        if not clients:
            logger.warning(f"No clients subscribed to Polymarket asset {asset_id}")
            return
        
        # Create book message in exact Polymarket format (no mock server state manipulation)
        bids = [{"price": f"{level['price']:.3f}", "size": f"{level['size']:.2f}"} 
                for level in sorted(bid_levels, key=lambda x: x["price"], reverse=True)]
        asks = [{"price": f"{level['price']:.3f}", "size": f"{level['size']:.2f}"} 
                for level in sorted(ask_levels, key=lambda x: x["price"])]
        
        book_message = {
            "event_type": "book",
            "asset_id": asset_id,
            "market": f"manual-test-{asset_id}",
            "timestamp": int(datetime.now().timestamp()),
            "bids": bids,
            "asks": asks
        }
        
        # Send to all clients
        for client in clients:
            try:
                await client.send(json.dumps([book_message]))  # Polymarket wraps in array
                logger.info(f"📤 Sent Polymarket snapshot for {asset_id}: {len(bid_levels)} bids, {len(ask_levels)} asks")
            except Exception as e:
                logger.error(f"Error sending Polymarket snapshot: {e}")
    
    async def send_kalshi_orderbook_delta(self, market_ticker: str, 
                                        side: str, price: int, size: int):
        """
        Send a specific Kalshi orderbook delta.
        
        Args:
            market_ticker: Kalshi market ticker
            side: "yes" or "no"
            price: Price level (1-99 cents)
            size: Size (0 to remove level)
        """
        sid = self.kalshi_server._find_market_by_ticker(market_ticker)
        if not sid:
            return
        
        clients = [
            ws for ws, client_data in self.kalshi_server.connected_clients.items()
            if sid in client_data["subscriptions"]
        ]
        
        if not clients:
            return
        
        # Send delta using the server's method with override
        await self.kalshi_server._send_orderbook_delta(
            clients, sid, 
            delta_override={"side": side, "price": price, "delta": size}
        )
        
        logger.info(f"📊 Sent Kalshi delta for {market_ticker}: {side} {price}¢ = {size}")
    
    async def send_polymarket_price_change(self, asset_id: str, 
                                         side: str, price: float, size: float):
        """
        Send a specific Polymarket price change.
        
        Args:
            asset_id: Polymarket asset ID
            side: "bid" or "ask"
            price: Price level (0.001-0.999)
            size: Size (0 to remove level)
        """
        clients = [
            ws for ws, client_data in self.polymarket_server.connected_clients.items()
            if asset_id in client_data["subscriptions"]
        ]
        
        if not clients:
            return
        
        # Send price change using the server's method with override
        await self.polymarket_server._send_price_change(
            clients, asset_id,
            price_change_override={"side": side, "price": price, "size": size}
        )
        
        logger.info(f"📊 Sent Polymarket price change for {asset_id}: {side} {price:.3f} = {size:.2f}")


class ArbitrageTestScenario:
    """
    Represents a single arbitrage test scenario with precise market conditions.
    """
    
    def __init__(self, name: str, description: str, expected_alerts: int):
        self.name = name
        self.description = description
        self.expected_alerts = expected_alerts
        
        # Kalshi orderbook levels
        self.kalshi_yes_levels: List[Dict] = []
        self.kalshi_no_levels: List[Dict] = []
        
        # Polymarket YES asset levels
        self.poly_yes_bids: List[Dict] = []
        self.poly_yes_asks: List[Dict] = []
        
        # Polymarket NO asset levels
        self.poly_no_bids: List[Dict] = []
        self.poly_no_asks: List[Dict] = []
        
        # Optional deltas to apply after snapshot
        self.kalshi_deltas: List[Dict] = []  # {"side", "price", "size"}
        self.polymarket_deltas: List[Dict] = []  # {"asset_id", "side", "price", "size"}
    
    def add_kalshi_yes_level(self, price: int, size: int):
        """Add a YES price level to Kalshi orderbook."""
        self.kalshi_yes_levels.append({"price": price, "size": size})
        return self
    
    def add_kalshi_no_level(self, price: int, size: int):
        """Add a NO price level to Kalshi orderbook."""
        self.kalshi_no_levels.append({"price": price, "size": size})
        return self
    
    def add_polymarket_yes_bid(self, price: float, size: float):
        """Add a bid level to Polymarket YES asset."""
        self.poly_yes_bids.append({"price": price, "size": size})
        return self
    
    def add_polymarket_yes_ask(self, price: float, size: float):
        """Add an ask level to Polymarket YES asset."""
        self.poly_yes_asks.append({"price": price, "size": size})
        return self
    
    def add_polymarket_no_bid(self, price: float, size: float):
        """Add a bid level to Polymarket NO asset."""
        self.poly_no_bids.append({"price": price, "size": size})
        return self
    
    def add_polymarket_no_ask(self, price: float, size: float):
        """Add an ask level to Polymarket NO asset."""
        self.poly_no_asks.append({"price": price, "size": size})
        return self
    
    def add_kalshi_delta(self, side: str, price: int, size: int):
        """Add a delta to apply after initial snapshot."""
        self.kalshi_deltas.append({"side": side, "price": price, "size": size})
        return self
    
    def add_polymarket_delta(self, asset_id: str, side: str, price: float, size: float):
        """Add a delta to apply after initial snapshot."""
        self.polymarket_deltas.append({
            "asset_id": asset_id, "side": side, "price": price, "size": size
        })
        return self


async def create_test_scenarios() -> List[ArbitrageTestScenario]:
    """
    Create mathematically precise test scenarios with exact arbitrage calculations.
    Each scenario targets specific arbitrage outcomes relative to the 2% threshold.
    
    Arbitrage Formula:
    - YES Arbitrage: Sell Kalshi YES + Buy Polymarket NO = Total Cost
    - NO Arbitrage: Sell Kalshi NO + Buy Polymarket YES = Total Cost  
    - Profitable when Total Cost > 100¢ (spread = (Total-100)/100)
    - Threshold: 2% = Total Cost > 102¢
    """
    scenarios = []
    
    # Scenario 1: Just below threshold (1.9% spread) - NO arbitrage expected
    scenario1 = ArbitrageTestScenario(
        name="Below Threshold (1.9%)",
        description="Spread just below 2% threshold, no arbitrage alert expected",
        expected_alerts=0
    )
    
    # Target: Sell Kalshi YES 64¢ + Buy Poly NO 37.9¢ = 101.9¢ (1.9% spread)
    scenario1.add_kalshi_yes_level(64, 100)  # Kalshi YES bid
    scenario1.add_kalshi_no_level(36, 100)   # Kalshi NO bid (complement)
    
    scenario1.add_polymarket_yes_ask(0.621, 100)  # Poly YES ask (complement)
    scenario1.add_polymarket_no_ask(0.379, 100)   # Poly NO ask
    
    # Verification: 64¢ + 37.9¢ = 101.9¢ → 1.9% spread (below 2% threshold)
    
    scenarios.append(scenario1)
    
    # Scenario 2: Just above threshold (2.1% spread) - YES arbitrage expected
    scenario2 = ArbitrageTestScenario(
        name="Above Threshold (2.1%) - YES",
        description="YES arbitrage with 2.1% spread, exactly above threshold",
        expected_alerts=1
    )
    
    # Target: Sell Kalshi YES 65¢ + Buy Poly NO 37.1¢ = 102.1¢ (2.1% spread)
    scenario2.add_kalshi_yes_level(65, 150)  # Kalshi YES bid  
    scenario2.add_kalshi_no_level(35, 150)   # Kalshi NO bid
    
    scenario2.add_polymarket_yes_ask(0.629, 150)  # Poly YES ask
    scenario2.add_polymarket_no_ask(0.371, 150)   # Poly NO ask
    
    # Verification: 65¢ + 37.1¢ = 102.1¢ → 2.1% spread (above 2% threshold)
    
    scenarios.append(scenario2)
    
    # Scenario 3: Clear NO arbitrage (3% spread)
    scenario3 = ArbitrageTestScenario(
        name="Clear NO Arbitrage (3%)",
        description="NO arbitrage with 3% spread, well above threshold",
        expected_alerts=1
    )
    
    # Target: Sell Kalshi NO 47¢ + Buy Poly YES 56¢ = 103¢ (3% spread)
    scenario3.add_kalshi_yes_level(53, 200)  # Kalshi YES bid
    scenario3.add_kalshi_no_level(47, 200)   # Kalshi NO bid
    
    scenario3.add_polymarket_yes_ask(0.56, 200)   # Poly YES ask
    scenario3.add_polymarket_no_ask(0.44, 200)    # Poly NO ask
    
    # Verification: 47¢ + 56¢ = 103¢ → 3% spread (well above threshold)
    
    scenarios.append(scenario3)
    
    # Scenario 4: Both-side arbitrage (YES=2.5%, NO=2.2%)
    scenario4 = ArbitrageTestScenario(
        name="Both-Side Arbitrage",
        description="Both YES and NO arbitrage opportunities above threshold", 
        expected_alerts=2
    )
    
    # YES arbitrage: Sell Kalshi YES 68¢ + Buy Poly NO 34.5¢ = 102.5¢ (2.5%)
    # NO arbitrage: Sell Kalshi NO 32¢ + Buy Poly YES 70.2¢ = 102.2¢ (2.2%)
    scenario4.add_kalshi_yes_level(68, 100)  # Kalshi YES bid
    scenario4.add_kalshi_no_level(32, 100)   # Kalshi NO bid
    
    scenario4.add_polymarket_yes_ask(0.702, 100)  # Poly YES ask
    scenario4.add_polymarket_no_ask(0.345, 100)   # Poly NO ask
    
    # Verification: 
    # YES: 68¢ + 34.5¢ = 102.5¢ → 2.5% spread
    # NO:  32¢ + 70.2¢ = 102.2¢ → 2.2% spread
    
    scenarios.append(scenario4)
    
    # Scenario 5: Extreme arbitrage (5% spread)
    scenario5 = ArbitrageTestScenario(
        name="Extreme Arbitrage (5%)",
        description="Large arbitrage opportunity with 5% spread",
        expected_alerts=1
    )
    
    # Target: Sell Kalshi YES 75¢ + Buy Poly NO 30¢ = 105¢ (5% spread)
    scenario5.add_kalshi_yes_level(75, 100)  # Kalshi YES bid
    scenario5.add_kalshi_no_level(25, 100)   # Kalshi NO bid
    
    scenario5.add_polymarket_yes_ask(0.70, 100)   # Poly YES ask
    scenario5.add_polymarket_no_ask(0.30, 100)    # Poly NO ask
    
    # Verification: 75¢ + 30¢ = 105¢ → 5% spread (large arbitrage)
    
    scenarios.append(scenario5)
    
    # Scenario 6: Delta-triggered arbitrage (starts balanced, ends at 2.3%)
    scenario6 = ArbitrageTestScenario(
        name="Delta-Triggered (0% → 2.3%)",
        description="Balanced market becomes arbitrage via price delta",
        expected_alerts=1
    )
    
    # Initial: Balanced at 60¢/40¢ with tight spreads
    scenario6.add_kalshi_yes_level(60, 100)  # Kalshi YES bid
    scenario6.add_kalshi_no_level(40, 100)   # Kalshi NO bid
    
    scenario6.add_polymarket_yes_ask(0.605, 100)  # Poly YES ask (tight)
    scenario6.add_polymarket_no_ask(0.395, 100)   # Poly NO ask (tight)
    
    # Initial verification: 60¢ + 39.5¢ = 99.5¢ → -0.5% (no arbitrage)
    
    # Delta: Improve Kalshi YES bid to create arbitrage
    scenario6.add_kalshi_delta("yes", 63, 150)  # New YES bid at 63¢
    
    # Final verification: 63¢ + 39.5¢ = 102.5¢ → 2.5% spread (arbitrage triggered)
    
    scenarios.append(scenario6)
    
    return scenarios


async def run_manual_snapshot_test():
    """
    Run arbitrage test with manually created snapshots and deltas.
    """
    print("🎯 MANUAL SNAPSHOT ARBITRAGE TEST")
    print("=" * 60)
    print("Testing arbitrage detection with manually crafted orderbook data")
    print()
    
    # Start mock servers in controlled mode
    poly_server = MockPolymarketServer(port=8001)
    kalshi_server = MockKalshiServer(port=8002)
    
    try:
        await poly_server.start()
        await kalshi_server.start()
        await asyncio.sleep(1)
        
        # Enable controlled mode
        print("🎛️ ENABLING CONTROLLED MODE (no background data)")
        poly_server.set_controlled_mode(True)
        kalshi_server.set_controlled_mode(True)
        
        # Test our custom logging levels
        logger.log(ORDERBOOK_SNAPSHOT_LEVEL, "🧪 TESTING ORDERBOOK_SNAPSHOT logging level")
        logger.log(ARBITRAGE_DETECTION_LEVEL, "🧪 TESTING ARBITRAGE_DETECTION logging level")
        
        # Create MarketsCoordinator
        coordinator = MarketsCoordinator()
        await coordinator.start_async_components()
        
        # Connect to markets
        await coordinator.connect("test_token_123,test_token_123_no", "polymarket")
        await coordinator.connect("TEST-MARKET-Y", "kalshi")
        
        # Wait for connection setup
        await asyncio.sleep(2)
        
        # Add arbitrage pair
        coordinator.add_arbitrage_market_pair(
            market_pair="MANUAL-TEST",
            kalshi_sid=3,  # TEST-MARKET-Y
            polymarket_yes_asset_id="test_token_123",
            polymarket_no_asset_id="test_token_123_no"
        )
        
        # Set up alert tracking
        detected_alerts = []
        def capture_alert(event_data):
            alert = event_data.get('alert')
            if alert:
                detected_alerts.append(alert)
                print(f"   🚨 ALERT: {alert.direction} {alert.side} - spread: {alert.spread:.3f}")
        
        coordinator.service_coordinator.event_bus.subscribe('arbitrage.alert', capture_alert)
        
        # Create snapshot builder
        builder = ManualSnapshotBuilder(kalshi_server, poly_server)
        
        # Load test scenarios
        scenarios = await create_test_scenarios()
        
        print(f"🧪 RUNNING {len(scenarios)} MANUAL SCENARIOS")
        print("-" * 40)
        
        total_expected = 0
        total_detected = 0
        
        for i, scenario in enumerate(scenarios):
            print(f"\\n🎯 Scenario {i+1}: {scenario.name}")
            print(f"   📋 {scenario.description}")
            print(f"   🎯 Expected alerts: {scenario.expected_alerts}")
            
            # Clear previous alerts
            detected_alerts.clear()
            
            # Wait for system to settle
            await asyncio.sleep(2)
            
            # Send initial snapshots
            await builder.send_kalshi_orderbook_snapshot(
                "TEST-MARKET-Y", scenario.kalshi_yes_levels, scenario.kalshi_no_levels
            )
            
            await builder.send_polymarket_book_snapshot(
                "test_token_123", scenario.poly_yes_bids, scenario.poly_yes_asks
            )
            
            await builder.send_polymarket_book_snapshot(
                "test_token_123_no", scenario.poly_no_bids, scenario.poly_no_asks
            )
            
            # Wait for snapshot processing
            await asyncio.sleep(2)
            
            # Apply any deltas
            for delta in scenario.kalshi_deltas:
                await builder.send_kalshi_orderbook_delta(
                    "TEST-MARKET-Y", delta["side"], delta["price"], delta["size"]
                )
                await asyncio.sleep(0.5)
            
            for delta in scenario.polymarket_deltas:
                await builder.send_polymarket_price_change(
                    delta["asset_id"], delta["side"], delta["price"], delta["size"]
                )
                await asyncio.sleep(0.5)
            
            # Wait for arbitrage detection
            await asyncio.sleep(3)
            
            # Count unique alerts
            unique_alerts = set((alert.direction, alert.side) for alert in detected_alerts)
            scenario_alerts = len(unique_alerts)
            
            total_expected += scenario.expected_alerts
            total_detected += scenario_alerts
            
            status = "✅" if scenario_alerts == scenario.expected_alerts else "❌"
            print(f"   {status} Detected: {scenario_alerts}, Expected: {scenario.expected_alerts}")
            
            if scenario_alerts != scenario.expected_alerts:
                print(f"   ⚠️ MISMATCH! Got {scenario_alerts}, expected {scenario.expected_alerts}")
                for j, alert_type in enumerate(unique_alerts):
                    direction, side = alert_type
                    example = next(a for a in detected_alerts if a.direction == direction and a.side == side)
                    print(f"      Alert {j+1}: {direction} {side} - spread: {example.spread:.3f}")
        
        # Final results
        print(f"\\n📊 MANUAL SNAPSHOT TEST RESULTS")
        print(f"   🎯 Scenarios tested: {len(scenarios)}")
        print(f"   📊 Expected total alerts: {total_expected}")
        print(f"   🚨 Detected total alerts: {total_detected}")
        print(f"   ✅ Accuracy: {'PERFECT' if total_detected == total_expected else 'NEEDS CALIBRATION'}")
        
        await coordinator.disconnect_all()
        
    finally:
        await poly_server.stop()
        await kalshi_server.stop()


if __name__ == "__main__":
    asyncio.run(run_manual_snapshot_test())