#!/usr/bin/env python3
"""
Simplified Logging Demo for Arbitrage Testing

This script demonstrates the new detailed logging for:
1. Periodic updates are disabled (controlled mode)
2. Orderbook state snapshots/deltas with before/after states
3. Arbitrage detection logging with all four strategies

Run this to see the clean, structured logs.
"""

import asyncio
import json
import sys
import os
import logging
from datetime import datetime

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
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Set up custom logging levels for orderbook snapshots and arbitrage detection
ORDERBOOK_SNAPSHOT_LEVEL = 25
ARBITRAGE_DETECTION_LEVEL = 26
logging.addLevelName(ORDERBOOK_SNAPSHOT_LEVEL, "ORDERBOOK_SNAPSHOT")
logging.addLevelName(ARBITRAGE_DETECTION_LEVEL, "ARBITRAGE_DETECTION")

# Create logger with custom levels enabled
logger = logging.getLogger(__name__)

# Filter to show only our custom logs and important events
logging.getLogger("backend.master_manager.kalshi_client.message_processor").setLevel(ORDERBOOK_SNAPSHOT_LEVEL)
logging.getLogger("backend.master_manager.polymarket_client.polymarket_message_processor").setLevel(ORDERBOOK_SNAPSHOT_LEVEL)

#adding in orderbook - want to see if messages being propogated upwards
logging.getLogger("backend.master_manager.polymarket_client.models.orderbook_state").setLevel(logging.DEBUG)
logging.getLogger("backend.master_manager.kalshi_client.models.orderbook_state").setLevel(logging.DEBUG)

# Allow ArbitrageDetector DEBUG logs to show through (for initialization messages)
logging.getLogger("backend.master_manager.arbitrage_detector").setLevel(logging.DEBUG)

# Suppress verbose WebSocket logs
logging.getLogger("websockets").setLevel(logging.WARNING)
logging.getLogger("backend.master_manager.messaging").setLevel(logging.WARNING)
logging.getLogger("backend.master_manager.connection").setLevel(logging.WARNING)
logging.getLogger("backend.channel_manager").setLevel(logging.WARNING)
logging.getLogger("backend.ticker_stream_integration").setLevel(logging.WARNING)

async def run_logging_demo():
    """
    Demo the new logging functionality with a simple arbitrage scenario.
    """
    print("🎯 ARBITRAGE TESTING LOGGING DEMO")
    print("=" * 60)
    print("Testing detailed logging for:")
    print("  1. ✅ Periodic updates disabled in controlled mode")
    print("  2. 📊 Orderbook snapshots/deltas with before/after states")
    print("  3. 🔍 Arbitrage detection with spread calculations")
    print()
    
    # Start mock servers in controlled mode
    poly_server = MockPolymarketServer(port=8001)
    kalshi_server = MockKalshiServer(port=8002)
    
    try:
        await poly_server.start()
        await kalshi_server.start()
        await asyncio.sleep(1)
        
        print("🎛️ ENABLING CONTROLLED MODE (no periodic updates)")
        poly_server.set_controlled_mode(True)
        kalshi_server.set_controlled_mode(True)
        
        # Test our custom logging levels
        logger.log(ORDERBOOK_SNAPSHOT_LEVEL, "🧪 TESTING ORDERBOOK_SNAPSHOT logging level")
        logger.log(ARBITRAGE_DETECTION_LEVEL, "🧪 TESTING ARBITRAGE_DETECTION logging level")
        print()
        
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
            market_pair="DEMO-LOGGING",
            kalshi_ticker="TEST-MARKET-Y",  # Fixed parameter name
            polymarket_yes_asset_id="test_token_123",
            polymarket_no_asset_id="test_token_123_no"
        )
        
        print("📝 SENDING MANUAL SNAPSHOTS TO TRIGGER LOGGING")
        print("-" * 40)
        
        # Helper to find kalshi market
        def find_kalshi_market():
            for market in kalshi_server.markets.values():
                if market.market_ticker == "TEST-MARKET-Y":
                    return market.sid
            logger.log(30, "ERROR: Cannot find kalshi market to add to")
            return None
        
        sid = find_kalshi_market()
        
        # Send Kalshi snapshot manually
        kalshi_clients = [
            ws for ws, client_data in kalshi_server.connected_clients.items()
            if sid in client_data["subscriptions"]
        ]
        
        if kalshi_clients:
            # Create snapshot with arbitrage opportunity
            snapshot_msg = {
                "type": "orderbook_snapshot",
                "sid": sid,
                "seq": 500, #not to interfere with previous messages - deltas at 1000s level
                "msg": {
                    "market_ticker": "TEST-MARKET-Y",
                    "yes": [["65", 100]],  # 65¢ bid
                    "no": [["34", 100]],   # 34¢ bid
                    "ts": int(datetime.now().timestamp())
                }
            }
            
            print("📤 Sending Kalshi snapshot (65¢ YES bid, 34¢ NO bid)")
            for client in kalshi_clients:
                await client.send(json.dumps(snapshot_msg))
        
        # Send Polymarket snapshots manually
        poly_clients = [
            ws for ws, client_data in poly_server.connected_clients.items()
            if "test_token_123" in client_data["subscriptions"]
        ]
        
        if poly_clients:
            # YES asset snapshot
            yes_book_msg = {
                "event_type": "book",
                "asset_id": "test_token_123",
                "market": "demo-test",
                "timestamp": int(datetime.now().timestamp()),
                "bids": [{"price": "0.620", "size": "100.00"}],
                "asks": [{"price": "0.630", "size": "100.00"}]
            }
            
            # NO asset snapshot (this will create arbitrage: 65¢ + 37¢ = 102¢ > 100¢)
            no_book_msg = {
                "event_type": "book",
                "asset_id": "test_token_123_no",
                "market": "demo-test",
                "timestamp": int(datetime.now().timestamp()),
                "bids": [{"price": "0.360", "size": "100.00"}],
                "asks": [{"price": "0.370", "size": "100.00"}]
            }
            
            print("📤 Sending Polymarket YES snapshot (62¢ bid, 63¢ ask)")
            for client in poly_clients:
                await client.send(json.dumps([yes_book_msg]))
            
            await asyncio.sleep(0.5)
            
            print("📤 Sending Polymarket NO snapshot (36¢ bid, 37¢ ask)")
            for client in poly_clients:
                await client.send(json.dumps([no_book_msg]))
        
        # Wait for arbitrage detection
        await asyncio.sleep(3)
        
        print()
        print("📊 DEMO COMPLETE - Check logs above for:")
        print("  🎛️ Controlled mode status")
        print("  📸 ORDERBOOK_SNAPSHOT logs with before/after states")
        print("  🔍 ARBITRAGE_DETECTION logs with spread calculations")
        print("  🚨 Arbitrage alerts (if detected)")
        
        await coordinator.disconnect_all()
        
    finally:
        await poly_server.stop()
        await kalshi_server.stop()


if __name__ == "__main__":
    asyncio.run(run_logging_demo())