"""
Test script for ArbitrageManager functionality
"""
import asyncio
import sys
import os

# Add the backend directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from backend.master_manager.arbitrage_manager import ArbitrageManager, ArbitrageAlert
from backend.master_manager.kalshi_client.models.orderbook_state import OrderbookState as KalshiOrderbookState
from backend.master_manager.polymarket_client.models.orderbook_state import PolymarketOrderbookState
from backend.master_manager.kalshi_client.models.orderbook_level import OrderbookLevel
from backend.master_manager.polymarket_client.models.orderbook_level import PolymarketOrderbookLevel
from datetime import datetime
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MockKalshiProcessor:
    """Mock Kalshi processor for testing"""
    def __init__(self):
        self.orderbooks = {}
    
    def get_orderbook(self, sid):
        return self.orderbooks.get(sid)
    
    def add_mock_orderbook(self, sid, yes_bid=None, yes_ask=None, no_bid=None, no_ask=None):
        """Add mock orderbook with specified prices (in cents)"""
        orderbook = KalshiOrderbookState(sid=sid, market_ticker=f"TEST-{sid}")
        
        # Add YES contracts (bids)
        if yes_bid:
            orderbook.yes_contracts[yes_bid] = OrderbookLevel(price=yes_bid, size=100, side="Yes")
        
        # Add NO contracts (asks)
        if no_bid:
            orderbook.no_contracts[no_bid] = OrderbookLevel(price=no_bid, size=100, side="No")
        
        self.orderbooks[sid] = orderbook
        return orderbook

class MockPolymarketProcessor:
    """Mock Polymarket processor for testing"""
    def __init__(self):
        self.orderbooks = {}
    
    def get_orderbook(self, asset_id):
        return self.orderbooks.get(asset_id)
    
    def add_mock_orderbook(self, asset_id, bid=None, ask=None):
        """Add mock orderbook with specified prices (in decimal)"""
        orderbook = PolymarketOrderbookState(asset_id=asset_id, market=f"TEST-{asset_id}")
        
        # Add bids
        if bid:
            orderbook.bids[str(bid)] = PolymarketOrderbookLevel(price=str(bid), size="100")
        
        # Add asks
        if ask:
            orderbook.asks[str(ask)] = PolymarketOrderbookLevel(price=str(ask), size="100")
        
        self.orderbooks[asset_id] = orderbook
        return orderbook

async def test_arbitrage_detection():
    """Test arbitrage detection with mock data"""
    logger.info("🧪 Starting arbitrage detection test")
    
    # Create mock processors
    kalshi_processor = MockKalshiProcessor()
    polymarket_processor = MockPolymarketProcessor()
    
    # Create arbitrage manager
    arb_manager = ArbitrageManager(min_spread_threshold=0.03)  # 3% threshold
    arb_manager.set_processors(kalshi_processor, polymarket_processor)
    
    # Set up alert callback
    received_alerts = []
    
    def alert_callback(alert: ArbitrageAlert):
        logger.info(f"📨 ALERT RECEIVED: {alert.market_pair} - {alert.direction} {alert.side} - Spread: {alert.spread:.3f}")
        received_alerts.append(alert)
    
    arb_manager.set_arbitrage_alert_callback(alert_callback)
    
    # Add market pair
    arb_manager.add_market_pair("TEST-PAIR", 12345, "poly_yes_123", "poly_no_456")
    
    # Test Case 1: No arbitrage opportunity (normal spread)
    logger.info("\n📊 Test Case 1: No arbitrage opportunity")
    # Set up prices where all combinations have spreads < threshold
    # Use wider spreads so no arbitrage is possible
    kalshi_processor.add_mock_orderbook(12345, yes_bid=45, no_bid=54)  # 45¢ YES bid, 54¢ NO bid
    polymarket_processor.add_mock_orderbook("poly_yes_123", bid=0.44, ask=0.47)  # 44¢ bid, 47¢ ask (YES)
    polymarket_processor.add_mock_orderbook("poly_no_456", bid=0.52, ask=0.55)   # 52¢ bid, 55¢ ask (NO)
    
    alerts = await arb_manager.check_arbitrage_for_pair("TEST-PAIR")
    logger.info(f"Alerts found: {len(alerts)}")
    assert len(alerts) == 0, "Should not find arbitrage opportunity"
    
    # Test Case 2: Arbitrage opportunity - Kalshi YES bid + Polymarket NO ask < 1.0
    logger.info("\n📊 Test Case 2: Arbitrage opportunity - Buy YES on Kalshi, Buy NO on Polymarket")
    kalshi_processor.add_mock_orderbook(12345, yes_bid=45, no_bid=50)  # 45¢ YES bid, 50¢ NO bid
    polymarket_processor.add_mock_orderbook("poly_yes_123", bid=0.46, ask=0.48)  # 46¢ bid, 48¢ ask
    polymarket_processor.add_mock_orderbook("poly_no_456", bid=0.52, ask=0.45)   # 52¢ bid, 45¢ ask
    
    alerts = await arb_manager.check_arbitrage_for_pair("TEST-PAIR")
    logger.info(f"Alerts found: {len(alerts)}")
    
    if alerts:
        alert = alerts[0]
        logger.info(f"Alert: {alert.direction} {alert.side} - Spread: {alert.spread:.3f}")
        assert alert.direction == "kalshi_to_polymarket"
        assert alert.side == "yes"
        assert alert.spread > 0.01, f"Spread should be > 1%, got {alert.spread:.3f}"
    
    # Test Case 3: Arbitrage opportunity - Kalshi NO bid + Polymarket YES ask < 1.0
    logger.info("\n📊 Test Case 3: Arbitrage opportunity - Buy NO on Kalshi, Buy YES on Polymarket")
    kalshi_processor.add_mock_orderbook(12345, yes_bid=60, no_bid=50)  # 60¢ YES bid, 50¢ NO bid
    polymarket_processor.add_mock_orderbook("poly_yes_123", bid=0.46, ask=0.35)  # 46¢ bid, 35¢ ask
    polymarket_processor.add_mock_orderbook("poly_no_456", bid=0.52, ask=0.54)   # 52¢ bid, 54¢ ask
    
    alerts = await arb_manager.check_arbitrage_for_pair("TEST-PAIR")
    logger.info(f"Alerts found: {len(alerts)}")
    
    if alerts:
        alert = alerts[0]
        logger.info(f"Alert: {alert.direction} {alert.side} - Spread: {alert.spread:.3f}")
        assert alert.direction == "kalshi_to_polymarket"
        assert alert.side == "no"
        assert alert.spread > 0.01, f"Spread should be > 1%, got {alert.spread:.3f}"
    
    # Test Case 4: Missing orderbook data
    logger.info("\n📊 Test Case 4: Missing orderbook data")
    # Remove one orderbook
    del kalshi_processor.orderbooks[12345]
    alerts = await arb_manager.check_arbitrage_for_pair("TEST-PAIR")
    logger.info(f"Alerts found: {len(alerts)}")
    assert len(alerts) == 0, "Should not find arbitrage when orderbook is missing"
    
    # Test Case 5: Test stats
    logger.info("\n📊 Test Case 5: Manager stats")
    stats = arb_manager.get_stats()
    logger.info(f"Stats: {stats}")
    assert stats['monitored_pairs'] == 1
    assert "TEST-PAIR" in stats['market_pairs']
    
    logger.info("\n✅ All arbitrage detection tests passed!")

async def test_orderbook_update_triggers():
    """Test that orderbook updates trigger arbitrage checks"""
    logger.info("\n🧪 Testing orderbook update triggers")
    
    # Create mock processors
    kalshi_processor = MockKalshiProcessor()
    polymarket_processor = MockPolymarketProcessor()
    
    # Create arbitrage manager
    arb_manager = ArbitrageManager(min_spread_threshold=0.01)
    arb_manager.set_processors(kalshi_processor, polymarket_processor)
    
    # Set up alert callback
    received_alerts = []
    
    async def alert_callback(alert: ArbitrageAlert):
        logger.info(f"📨 TRIGGERED ALERT: {alert.market_pair} - {alert.direction} {alert.side} - Spread: {alert.spread:.3f}")
        received_alerts.append(alert)
    
    arb_manager.set_arbitrage_alert_callback(alert_callback)
    
    # Add market pair
    arb_manager.add_market_pair("TEST-TRIGGER", 99999, "trigger_yes", "trigger_no")
    
    # Set up orderbooks with arbitrage opportunity
    kalshi_orderbook = kalshi_processor.add_mock_orderbook(99999, yes_bid=70, no_bid=40)
    polymarket_processor.add_mock_orderbook("trigger_yes", bid=0.60, ask=0.65)
    polymarket_processor.add_mock_orderbook("trigger_no", bid=0.35, ask=0.25)  # 25¢ ask creates arbitrage
    
    # Test Kalshi update trigger
    await arb_manager.handle_kalshi_orderbook_update(99999, kalshi_orderbook)
    logger.info(f"Alerts after Kalshi update: {len(received_alerts)}")
    
    # Test Polymarket update trigger
    poly_orderbook = polymarket_processor.get_orderbook("trigger_no")
    await arb_manager.handle_polymarket_orderbook_update("trigger_no", poly_orderbook)
    logger.info(f"Total alerts after Polymarket update: {len(received_alerts)}")
    
    logger.info("✅ Orderbook update trigger tests completed!")

async def main():
    """Run all tests"""
    try:
        await test_arbitrage_detection()
        await test_orderbook_update_triggers()
        logger.info("\n🎉 All tests passed successfully!")
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())