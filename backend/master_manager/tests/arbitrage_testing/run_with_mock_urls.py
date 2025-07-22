#!/usr/bin/env python3
"""
Run Tests with Mock Server URLs

This script sets environment variables to use mock servers and runs tests using
the MarketsCoordinator factory pattern. No code changes needed!

Usage:
  python run_with_mock_urls.py [command] [--log-level LEVEL]
  
  Commands:
    servers     Start mock servers
    test        Test MarketsCoordinator with mocks  
    websocket   Test WebSocket server integration
    help        Show this help message
    
  Options:
    --log-level LEVEL    Set logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
"""

import os
import sys
import asyncio
import logging
import argparse
from datetime import datetime
from pathlib import Path

from .mock_polymarket_server import MockPolymarketServer
from .mock_kalshi_server import MockKalshiServer
# Test ticker publishing
from backend.websocket_server import publish_ticker_update

# Import and test MarketsCoordinator
from backend.master_manager.markets_coordinator import MarketsCoordinator

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Run Tests with Mock Server URLs',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  servers     Start mock servers
  test        Test MarketsCoordinator with mocks  
  websocket   Test WebSocket server integration
  help        Show this help message

Examples:
  python run_with_mock_urls.py servers
  python run_with_mock_urls.py test --log-level INFO
  python run_with_mock_urls.py websocket --log-level WARNING
        """
    )
    parser.add_argument(
        'command',
        nargs='?',
        choices=['servers', 'test', 'websocket', 'help'],
        default='help',
        help='Command to execute'
    )
    parser.add_argument(
        '--log-level', 
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        default='ERROR',  # Default to ERROR for console, DEBUG for file
        help='Set the logging level (default: ERROR for console)'
    )
    return parser.parse_args()

def setup_logging(log_level: str = "ERROR"):
    """Configure logging with dual handlers (file and console)"""
    # Set up root logger manually so all submodules inherit handlers
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Always DEBUG for file handler

    # Remove any default handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # File handler - always DEBUG level
    file_handler = logging.FileHandler("websocket_debug.log")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    root_logger.addHandler(file_handler)

    # Console handler - user-specified level
    console_level = getattr(logging, log_level.upper(), None)
    if not isinstance(console_level, int):
        raise ValueError(f'Invalid log level: {log_level}')
        
    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_level)
    console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    root_logger.addHandler(console_handler)

def print_usage():
    """Print usage information"""
    print("🔧 Mock Test Runner")
    print("=" * 50)
    print()
    print("This script automatically configures environment variables to use mock servers")
    print("and tests the MarketsCoordinator factory pattern with your existing codebase.")
    print()
    print("Usage:")
    print("  python run_with_mock_urls.py [command] [--log-level LEVEL]")
    print()
    print("Commands:")
    print("  servers     Start mock servers for manual testing")
    print("  test        Test MarketsCoordinator with mocks")
    print("  websocket   Test WebSocket server integration")
    print("  help        Show this help message")
    print()
    print("Options:")
    print("  --log-level LEVEL   Set logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)")
    print("                      Default: ERROR for console, DEBUG for file")
    print()
    print("Examples:")
    print("  python run_with_mock_urls.py servers")
    print("  python run_with_mock_urls.py test --log-level INFO")
    print("  python run_with_mock_urls.py websocket --log-level DEBUG")
    print()
    print("Environment Variables Set:")
    print("  POLYMARKET_WS_URL=ws://localhost:8001")
    print("  KALSHI_WS_URL=ws://localhost:8002")
    print()
    print("Your existing MarketsCoordinator and platform managers will automatically")
    print("use these URLs instead of the real APIs for testing.")

def set_mock_environment():
    """Set environment variables to point to mock servers"""
    print("🔧 Configuring environment for mock servers...")
    
    # Set URLs for mock servers
    os.environ['POLYMARKET_WS_URL'] = 'ws://localhost:8001'
    os.environ['KALSHI_WS_URL'] = 'ws://localhost:8002'
    
    # Optional: Enable debug logging
    os.environ['POLYMARKET_DEBUG_LOGGING'] = 'true'
    
    print("✅ Environment configured:")
    print(f"   POLYMARKET_WS_URL = {os.environ['POLYMARKET_WS_URL']}")
    print(f"   KALSHI_WS_URL = {os.environ['KALSHI_WS_URL']}")
    print(f"   POLYMARKET_DEBUG_LOGGING = {os.environ.get('POLYMARKET_DEBUG_LOGGING', 'false')}")
    print()

async def start_mock_servers():
    """Start both mock servers for testing"""
    print("🚀 Starting mock servers...")
    
    
    
    poly_server = MockPolymarketServer(port=8001)
    kalshi_server = MockKalshiServer(port=8002)
    
    await poly_server.start()
    await kalshi_server.start()
    
    print("✅ Mock servers started successfully!")
    print()
    print("📊 MOCK SERVER INFO:")
    print("   Polymarket: ws://localhost:8001")
    print("     - Test markets: test_token_123, real token IDs")
    print("     - Subscription: {'auth': '', 'channel': 'book', 'market': 'test_token_123'}")
    print()
    print("   Kalshi: ws://localhost:8002") 
    print("     - Test markets: TEST-MARKET-Y, KXUSAIRANAGREEMENT-26, PRES24-DJT-Y")
    print("     - Subscription: {'id': 1, 'cmd': 'subscribe', 'params': {'channels': ['orderbook_delta'], 'market_tickers': ['TEST-MARKET-Y']}}")
    print()
    print("🔄 Servers will send periodic updates automatically")
    print("⏹️ Press Ctrl+C to stop servers")
    
    try:
        # Keep running until interrupted
        await asyncio.Future()
    except KeyboardInterrupt:
        print("\n⏹️ Shutting down servers...")
    finally:
        await poly_server.stop()
        await kalshi_server.stop()
        print("✅ Servers stopped")

async def test_markets_coordinator():
    """Test MarketsCoordinator with mock servers"""
    print("🎯 Testing MarketsCoordinator with mock servers...")
    
    # Add parent directory to path for imports (matching existing test pattern)
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    
    
    poly_server = MockPolymarketServer(port=8001)
    kalshi_server = MockKalshiServer(port=8002)
    
    try:
        await poly_server.start()
        await kalshi_server.start()
        print("✅ Mock servers started")
        
        coordinator = MarketsCoordinator()
        print("✅ MarketsCoordinator created")
        
        # Start async components
        await coordinator.start_async_components()
        print("✅ Async components started")
        
        # Test Polymarket connection
        print("🔍 Testing Polymarket connection...")
        poly_result = await coordinator.connect("test_token_123", "polymarket")
        print(f"   Polymarket connection: {'✅ SUCCESS' if poly_result else '❌ FAILED'}")
        
        # Test Kalshi connection  
        print("🔍 Testing Kalshi connection...")
        kalshi_result = await coordinator.connect("TEST-MARKET-Y", "kalshi")
        print(f"   Kalshi connection: {'✅ SUCCESS' if kalshi_result else '❌ FAILED'}")
        
        # Let it run for a bit to collect data
        if poly_result or kalshi_result:
            print("⏱️ Running for 15 seconds to collect market data...")
            await asyncio.sleep(15)
            
            # Check status
            status = coordinator.get_status()
            print(f"📊 Final Status:")
            print(f"   Total connections: {status['total_connections']}")
            print(f"   Kalshi async_started: {status['kalshi_platform']['async_started']}")
            print(f"   Polymarket async_started: {status['polymarket_platform']['async_started']}")
            
            # Test arbitrage detection setup
            print("🔍 Testing arbitrage detection setup...")
            try:
                # Register a test market pair for arbitrage detection
                coordinator.service_coordinator.arbitrage_service.register_market_pair(
                    "TEST-ELECTION-2024",
                    kalshi_sid=1,
                    polymarket_yes_asset_id="test_token_123",
                    polymarket_no_asset_id="test_token_456"
                )
                
                # Manually check arbitrage to test processor setup
                alerts = await coordinator.service_coordinator.arbitrage_service.check_arbitrage_for_pair("TEST-ELECTION-2024")
                print(f"✅ Arbitrage check completed. Alerts: {len(alerts)}")
                
            except Exception as e:
                print(f"❌ Arbitrage detection error: {e}")
                # Check if processors are set
                arb_mgr = coordinator.service_coordinator.arbitrage_service
                print(f"   Kalshi processor set: {arb_mgr.kalshi_processor is not None}")
                print(f"   Polymarket processor set: {arb_mgr.polymarket_processor is not None}")
        
        # Cleanup
        await coordinator.disconnect_all()
        print("✅ MarketsCoordinator test completed")
        
        return poly_result or kalshi_result
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await poly_server.stop()
        await kalshi_server.stop()

async def test_websocket_server():
    """Test WebSocket server with MarketsCoordinator"""
    print("🌐 Testing WebSocket server integration...")
    
    # Add paths for websocket server imports
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    sys.path.insert(0, project_root)
    
    
    
    poly_server = MockPolymarketServer(port=8001)
    kalshi_server = MockKalshiServer(port=8002)
    
    try:
        await poly_server.start()
        await kalshi_server.start()
        print("✅ Mock servers started")
        
        # Test websocket server startup with MarketsCoordinator
        try:
            from backend.websocket_server import initialize_markets_coordinator
            success = await initialize_markets_coordinator()
            print(f"   WebSocket server MarketsCoordinator init: {'✅ SUCCESS' if success else '❌ FAILED'}")
            
            sample_ticker = {
                "market_id": "test_market",
                "platform": "test",
                "summary_stats": {
                    "yes": {"bid": 0.65, "ask": 0.67, "volume": 1000.0},
                    "no": {"bid": 0.33, "ask": 0.35, "volume": 1000.0}
                },
                "timestamp": int(datetime.now().timestamp())
            }
            await publish_ticker_update(sample_ticker)
            print("✅ Ticker publishing test passed")
            
            return success
            
        except Exception as e:
            print(f"❌ WebSocket server test failed: {e}")
            return False
            
    finally:
        await poly_server.stop() 
        await kalshi_server.stop()

async def main():
    """Main entry point with argument parsing"""
    # Parse command line arguments
    args = parse_arguments()
    
    # Always configure environment for mock servers
    set_mock_environment()
    
    # Configure logging with user-specified level
    setup_logging(args.log_level)
    
    print(f"🎯 MOCK TESTS - Command: {args.command}, Log Level: {args.log_level}")
    print("=" * 70)
    
    if args.command == "servers":
        await start_mock_servers()
        return 0
    elif args.command == "test":
        success = await test_markets_coordinator()
        return 0 if success else 1
    elif args.command == "websocket":
        success = await test_websocket_server()
        return 0 if success else 1
    elif args.command == "help":
        print_usage()
        return 0
    else:
        print(f"Unknown command: {args.command}")
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
        import traceback
        traceback.print_exc()
        sys.exit(1)