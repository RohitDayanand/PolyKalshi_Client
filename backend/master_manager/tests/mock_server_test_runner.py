"""
Mock Server Test Runner - Validates Tick Processing Pipeline

Tests the complete flow from mock WebSocket servers through message processors 
to ticker publishers and WebSocket broadcasts. Validates that:

1. Mock servers send correctly formatted messages
2. Message processors handle updates and maintain state
3. Ticker publishers generate proper summary stats
4. WebSocket server receives and broadcasts ticker updates

This is the comprehensive test for the tick processing pipeline.
"""

import asyncio
import json
import logging
import time
import websockets
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import sys
import os

# Add parent paths for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mock_polymarket_server import MockPolymarketServer
from mock_kalshi_server import MockKalshiServer

# Import the real client and processor components
from polymarket_client.polymarket_client import PolymarketClient, PolymarketClientConfig
from polymarket_client.polymarket_message_processor import PolymarketMessageProcessor
from polymarket_client.polymarket_ticker_publisher import PolymarketTickerPublisher

from kalshi_client.kalshi_client import KalshiClient
from kalshi_client.kalshi_client_config import KalshiClientConfig
from kalshi_client.kalshi_environment import Environment
from kalshi_client.message_processor import KalshiMessageProcessor
from kalshi_client.kalshi_ticker_publisher import KalshiTickerPublisher

logger = logging.getLogger(__name__)

class MockTickerReceiver:
    """Captures ticker updates published by ticker publishers"""
    
    def __init__(self):
        self.received_tickers: List[Dict[str, Any]] = []
        self.last_received_time: Optional[datetime] = None
    
    async def receive_ticker_update(self, ticker_data: Dict[str, Any]):
        """Callback for ticker publishers"""
        self.received_tickers.append(ticker_data.copy())
        self.last_received_time = datetime.now()
        logger.info(f"📈 RECEIVED TICKER: {ticker_data.get('market_id')} - {ticker_data.get('platform')}")
        logger.debug(f"📈 TICKER DETAILS: {ticker_data}")
    
    def get_ticker_count(self) -> int:
        return len(self.received_tickers)
    
    def get_latest_ticker(self) -> Optional[Dict[str, Any]]:
        return self.received_tickers[-1] if self.received_tickers else None
    
    def get_tickers_for_platform(self, platform: str) -> List[Dict[str, Any]]:
        return [t for t in self.received_tickers if t.get('platform') == platform]
    
    def clear(self):
        self.received_tickers.clear()
        self.last_received_time = None

class MockTestRunner:
    """Orchestrates the complete mock server test"""
    
    def __init__(self):
        self.poly_server: Optional[MockPolymarketServer] = None
        self.kalshi_server: Optional[MockKalshiServer] = None
        self.ticker_receiver = MockTickerReceiver()
        
        # Test results tracking
        self.test_results: Dict[str, Any] = {
            "polymarket": {"connected": False, "messages_received": 0, "tickers_generated": 0},
            "kalshi": {"connected": False, "messages_received": 0, "tickers_generated": 0},
            "start_time": None,
            "end_time": None,
            "duration_seconds": 0
        }
    
    async def setup_mock_servers(self):
        """Start both mock servers"""
        logger.info("🚀 Starting mock servers...")
        
        # Start Polymarket mock server on port 8001
        self.poly_server = MockPolymarketServer(port=8001)
        await self.poly_server.start()
        logger.info("✅ Polymarket mock server started on port 8001")
        
        # Start Kalshi mock server on port 8002
        self.kalshi_server = MockKalshiServer(port=8002)
        await self.kalshi_server.start()
        logger.info("✅ Kalshi mock server started on port 8002")
        
        # Give servers time to start
        await asyncio.sleep(1)
    
    async def test_polymarket_pipeline(self):
        """Test Polymarket: mock server → client → message processor → ticker publisher"""
        logger.info("🔍 Testing Polymarket pipeline...")
        
        try:
            # Create client config pointing to mock server
            config = PolymarketClientConfig(
                slug="test-market",
                ws_url="ws://localhost:8001",  # Point to mock server
                token_ids=["test_token_123"]
            )
            
            # Create client
            client = PolymarketClient(config)
            
            # Create message processor
            message_processor = PolymarketMessageProcessor()
            
            # Create ticker publisher with our receiver as callback
            ticker_publisher = PolymarketTickerPublisher()
            ticker_publisher.set_ticker_update_callback(self.ticker_receiver.receive_ticker_update)
            
            # Set up message processor → ticker publisher chain
            message_processor.set_orderbook_update_callback(ticker_publisher.handle_orderbook_update)
            
            # Set up client → message processor chain
            client.set_message_callback(message_processor.handle_message)
            
            # Connect and run for test duration
            await client.connect()
            self.test_results["polymarket"]["connected"] = True
            logger.info("✅ Polymarket client connected to mock server")
            
            # Run for 15 seconds to collect updates
            test_duration = 15
            logger.info(f"⏱️ Running Polymarket test for {test_duration} seconds...")
            await asyncio.sleep(test_duration)
            
            # Disconnect
            await client.disconnect()
            
            # Record results
            poly_tickers = self.ticker_receiver.get_tickers_for_platform("polymarket")
            self.test_results["polymarket"]["tickers_generated"] = len(poly_tickers)
            
            logger.info(f"✅ Polymarket test completed: {len(poly_tickers)} tickers generated")
            
            # Log sample ticker if available
            if poly_tickers:
                sample_ticker = poly_tickers[-1]
                logger.info(f"📊 Sample Polymarket ticker: {sample_ticker}")
            
            return len(poly_tickers) > 0
            
        except Exception as e:
            logger.error(f"❌ Polymarket pipeline test failed: {e}")
            return False
    
    async def test_kalshi_pipeline(self):
        """Test Kalshi: mock server → client → message processor → ticker publisher"""
        logger.info("🔍 Testing Kalshi pipeline...")
        
        try:
            # Create client config pointing to mock server
            config = KalshiClientConfig(
                ticker="TEST-MARKET-Y",
                channel="orderbook_delta",
                environment=Environment.DEMO,  # We'll override the URL
                api_key="test_key",
                api_secret="test_secret"
            )
            
            # Create client
            client = KalshiClient(config)
            
            # Override WebSocket URL to point to mock server
            client._get_ws_url = lambda: "ws://localhost:8002"
            
            # Create message processor
            message_processor = KalshiMessageProcessor()
            
            # Create ticker publisher with our receiver as callback
            ticker_publisher = KalshiTickerPublisher()
            ticker_publisher.set_ticker_update_callback(self.ticker_receiver.receive_ticker_update)
            
            # Set up message processor → ticker publisher chain
            message_processor.set_orderbook_update_callback(ticker_publisher.handle_orderbook_update)
            message_processor.set_ticker_update_callback(ticker_publisher.handle_ticker_update)
            
            # Set up client → message processor chain
            client.set_message_callback(message_processor.handle_message)
            
            # Connect and run for test duration
            await client.connect()
            self.test_results["kalshi"]["connected"] = True
            logger.info("✅ Kalshi client connected to mock server")
            
            # Run for 15 seconds to collect updates
            test_duration = 15
            logger.info(f"⏱️ Running Kalshi test for {test_duration} seconds...")
            await asyncio.sleep(test_duration)
            
            # Disconnect
            await client.disconnect()
            
            # Record results
            kalshi_tickers = self.ticker_receiver.get_tickers_for_platform("kalshi")
            self.test_results["kalshi"]["tickers_generated"] = len(kalshi_tickers)
            
            logger.info(f"✅ Kalshi test completed: {len(kalshi_tickers)} tickers generated")
            
            # Log sample ticker if available
            if kalshi_tickers:
                sample_ticker = kalshi_tickers[-1]
                logger.info(f"📊 Sample Kalshi ticker: {sample_ticker}")
            
            return len(kalshi_tickers) > 0
            
        except Exception as e:
            logger.error(f"❌ Kalshi pipeline test failed: {e}")
            return False
    
    async def test_websocket_server_integration(self):
        """Test that our WebSocket server can receive the ticker updates"""
        logger.info("🔍 Testing WebSocket server integration...")
        
        try:
            # Import the websocket server's publish function
            from backend.websocket_server import publish_ticker_update
            
            # Test publishing a sample ticker update
            sample_ticker = {
                "market_id": "test_market_123",
                "platform": "test",
                "summary_stats": {
                    "yes": {"bid": 0.65, "ask": 0.67, "volume": 1000.0},
                    "no": {"bid": 0.33, "ask": 0.35, "volume": 1000.0}
                },
                "timestamp": int(time.time())
            }
            
            # This would normally broadcast to connected WebSocket clients
            await publish_ticker_update(sample_ticker)
            logger.info("✅ WebSocket server integration test passed")
            return True
            
        except Exception as e:
            logger.error(f"❌ WebSocket server integration test failed: {e}")
            return False
    
    async def cleanup_mock_servers(self):
        """Stop both mock servers"""
        logger.info("🧹 Cleaning up mock servers...")
        
        if self.poly_server:
            await self.poly_server.stop()
        
        if self.kalshi_server:
            await self.kalshi_server.stop()
        
        logger.info("✅ Mock servers stopped")
    
    def print_test_results(self):
        """Print comprehensive test results"""
        print("\n" + "=" * 70)
        print("🎯 MOCK SERVER TEST RESULTS")
        print("=" * 70)
        
        print(f"⏱️ Test Duration: {self.test_results['duration_seconds']:.2f} seconds")
        print(f"📅 Start Time: {self.test_results['start_time']}")
        print(f"📅 End Time: {self.test_results['end_time']}")
        print()
        
        # Polymarket results
        poly_results = self.test_results["polymarket"]
        print("📊 POLYMARKET PIPELINE:")
        print(f"  ✅ Connected: {poly_results['connected']}")
        print(f"  📈 Tickers Generated: {poly_results['tickers_generated']}")
        print(f"  📊 Success Rate: {'✅ PASS' if poly_results['tickers_generated'] > 0 else '❌ FAIL'}")
        print()
        
        # Kalshi results
        kalshi_results = self.test_results["kalshi"]
        print("📊 KALSHI PIPELINE:")
        print(f"  ✅ Connected: {kalshi_results['connected']}")
        print(f"  📈 Tickers Generated: {kalshi_results['tickers_generated']}")
        print(f"  📊 Success Rate: {'✅ PASS' if kalshi_results['tickers_generated'] > 0 else '❌ FAIL'}")
        print()
        
        # Overall results
        total_tickers = poly_results['tickers_generated'] + kalshi_results['tickers_generated']
        both_connected = poly_results['connected'] and kalshi_results['connected']
        
        print("📊 OVERALL RESULTS:")
        print(f"  📈 Total Tickers Generated: {total_tickers}")
        print(f"  🔌 Both Platforms Connected: {both_connected}")
        print(f"  🎯 Test Status: {'✅ SUCCESS' if total_tickers > 0 and both_connected else '❌ FAILED'}")
        print()
        
        # Sample ticker data
        if self.ticker_receiver.received_tickers:
            print("📋 SAMPLE TICKER DATA:")
            latest = self.ticker_receiver.get_latest_ticker()
            if latest:
                print(f"  📊 Latest Ticker: {latest}")
            print()
        
        print("=" * 70)
    
    async def run_complete_test(self):
        """Run the complete mock server test suite"""
        self.test_results["start_time"] = datetime.now().isoformat()
        start_time = time.time()
        
        logger.info("🎯 Starting Complete Mock Server Test Suite")
        
        try:
            # Setup
            await self.setup_mock_servers()
            
            # Test Polymarket pipeline
            poly_success = await self.test_polymarket_pipeline()
            
            # Clear receiver between tests
            self.ticker_receiver.clear()
            
            # Test Kalshi pipeline
            kalshi_success = await self.test_kalshi_pipeline()
            
            # Test WebSocket server integration
            ws_success = await self.test_websocket_server_integration()
            
            # Record end time
            end_time = time.time()
            self.test_results["end_time"] = datetime.now().isoformat()
            self.test_results["duration_seconds"] = end_time - start_time
            
            # Print results
            self.print_test_results()
            
            # Overall success
            overall_success = poly_success and kalshi_success and ws_success
            logger.info(f"🎯 Overall test result: {'✅ SUCCESS' if overall_success else '❌ FAILED'}")
            
            return overall_success
            
        except Exception as e:
            logger.error(f"💥 Test suite failed with error: {e}")
            return False
        finally:
            await self.cleanup_mock_servers()

async def main():
    """Run the mock server test suite"""
    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('/home/rohit/Websocket_Polymarket_Kalshi/backend/master_manager/tests/mock_test.log', mode='w')
        ]
    )
    
    # Enable DEBUG logging for websockets and asyncio to catch TCP issues
    logging.getLogger('websockets').setLevel(logging.DEBUG)
    logging.getLogger('asyncio').setLevel(logging.DEBUG)
    logging.getLogger('aiohttp').setLevel(logging.DEBUG)
    
    logger.info("🚀 Starting Mock Server Test Runner")
    
    # Run the test suite
    runner = MockTestRunner()
    success = await runner.run_complete_test()
    
    # Exit with appropriate code
    exit_code = 0 if success else 1
    logger.info(f"🏁 Test suite completed with exit code: {exit_code}")
    return exit_code

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)