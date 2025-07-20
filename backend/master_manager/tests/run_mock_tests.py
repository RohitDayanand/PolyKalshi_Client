"""
Quick Test Runner for Mock Servers

This script provides simple commands to:
1. Test mock servers individually 
2. Run the full integration test
3. Start mock servers for manual testing

Usage:
  python run_mock_tests.py polymarket  # Test Polymarket mock server only
  python run_mock_tests.py kalshi      # Test Kalshi mock server only  
  python run_mock_tests.py full        # Run complete integration test
  python run_mock_tests.py servers     # Start both servers for manual testing
"""

import asyncio
import sys
import logging
from mock_polymarket_server import MockPolymarketServer
from mock_kalshi_server import MockKalshiServer
from mock_server_test_runner import MockTestRunner

async def test_polymarket_only():
    """Test only the Polymarket mock server"""
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger(__name__)
    
    logger.info("🔍 Testing Polymarket Mock Server Only")
    
    server = MockPolymarketServer(port=8001)
    await server.start()
    
    logger.info("✅ Polymarket mock server started on ws://localhost:8001")
    logger.info("📝 Test this with a WebSocket client:")
    logger.info("   Connection: ws://localhost:8001")
    logger.info("   Subscription: {'auth': '', 'channel': 'book', 'market': 'test_token_123'}")
    
    try:
        logger.info("⏳ Server running for 30 seconds...")
        await asyncio.sleep(30)
    except KeyboardInterrupt:
        logger.info("⏹️ Test interrupted by user")
    finally:
        await server.stop()
        logger.info("✅ Polymarket mock server stopped")

async def test_kalshi_only():
    """Test only the Kalshi mock server"""
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger(__name__)
    
    logger.info("🔍 Testing Kalshi Mock Server Only")
    
    server = MockKalshiServer(port=8002)
    await server.start()
    
    logger.info("✅ Kalshi mock server started on ws://localhost:8002")
    logger.info("📝 Test this with a WebSocket client:")
    logger.info("   Connection: ws://localhost:8002")
    logger.info("   Subscription: {'id': 1, 'cmd': 'subscribe', 'params': {'channels': ['orderbook_delta'], 'market_tickers': ['TEST-MARKET-Y']}}")
    
    try:
        logger.info("⏳ Server running for 30 seconds...")
        await asyncio.sleep(30)
    except KeyboardInterrupt:
        logger.info("⏹️ Test interrupted by user")
    finally:
        await server.stop()
        logger.info("✅ Kalshi mock server stopped")

async def run_full_test():
    """Run the complete integration test"""
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger(__name__)
    
    logger.info("🎯 Running Complete Mock Server Integration Test")
    
    runner = MockTestRunner()
    success = await runner.run_complete_test()
    
    if success:
        logger.info("🎉 All tests passed!")
        return 0
    else:
        logger.error("❌ Some tests failed!")
        return 1

async def start_servers_for_manual_testing():
    """Start both servers for manual testing"""
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger(__name__)
    
    logger.info("🚀 Starting Both Mock Servers for Manual Testing")
    
    poly_server = MockPolymarketServer(port=8001)
    kalshi_server = MockKalshiServer(port=8002)
    
    await poly_server.start()
    await kalshi_server.start()
    
    logger.info("✅ Both mock servers started successfully!")
    logger.info("")
    logger.info("📊 POLYMARKET SERVER:")
    logger.info("   URL: ws://localhost:8001")
    logger.info("   Test Markets:")
    logger.info("     - test_token_123 (test market)")
    logger.info("     - 75505728818237076147318796536066812362152358606307154083407489467059230821371")
    logger.info("     - 67369669271127885658944531351746308398542291270457462650056001798232262328240")
    logger.info("   Subscription: {'auth': '', 'channel': 'book', 'market': 'test_token_123'}")
    logger.info("")
    logger.info("📊 KALSHI SERVER:")
    logger.info("   URL: ws://localhost:8002")
    logger.info("   Test Markets:")
    logger.info("     - TEST-MARKET-Y (sid will be assigned)")
    logger.info("     - KXUSAIRANAGREEMENT-26")
    logger.info("     - PRES24-DJT-Y")
    logger.info("   Subscription: {'id': 1, 'cmd': 'subscribe', 'params': {'channels': ['orderbook_delta'], 'market_tickers': ['TEST-MARKET-Y']}}")
    logger.info("")
    logger.info("🔧 Both servers will send periodic updates automatically")
    logger.info("⏹️ Press Ctrl+C to stop both servers")
    
    try:
        # Keep running until interrupted
        await asyncio.Future()
    except KeyboardInterrupt:
        logger.info("⏹️ Shutting down servers...")
    finally:
        await poly_server.stop()
        await kalshi_server.stop()
        logger.info("✅ Both servers stopped")

def print_usage():
    """Print usage instructions"""
    print("Mock Server Test Runner")
    print("======================")
    print()
    print("Usage:")
    print("  python run_mock_tests.py polymarket  # Test Polymarket mock server only")
    print("  python run_mock_tests.py kalshi      # Test Kalshi mock server only")
    print("  python run_mock_tests.py full        # Run complete integration test")
    print("  python run_mock_tests.py servers     # Start both servers for manual testing")
    print()
    print("Examples:")
    print("  python run_mock_tests.py full        # Best for automated testing")
    print("  python run_mock_tests.py servers     # Best for manual WebSocket client testing")

async def main():
    """Main entry point"""
    if len(sys.argv) != 2:
        print_usage()
        return 1
    
    command = sys.argv[1].lower()
    
    if command == "polymarket":
        await test_polymarket_only()
        return 0
    elif command == "kalshi":
        await test_kalshi_only()
        return 0
    elif command == "full":
        return await run_full_test()
    elif command == "servers":
        await start_servers_for_manual_testing()
        return 0
    else:
        print(f"Unknown command: {command}")
        print_usage()
        return 1

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⏹️ Interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"💥 Error: {e}")
        sys.exit(1)