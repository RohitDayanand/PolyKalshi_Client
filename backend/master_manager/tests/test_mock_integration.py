#!/usr/bin/env python3
"""
Mock Integration Test - Using Existing Import Patterns

This follows the exact same import pattern as your existing integration tests.
Run from the tests directory: python test_mock_integration.py
"""

import asyncio
import json
import sys
import os
import logging
from datetime import datetime

# Add parent to path (exactly like existing integration tests)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure environment for mock servers BEFORE any imports
os.environ['POLYMARKET_WS_URL'] = 'ws://localhost:8001'
os.environ['KALSHI_WS_URL'] = 'ws://localhost:8002'
os.environ['POLYMARKET_DEBUG_LOGGING'] = 'true'

# Import mock servers (local to tests directory)
from tests.mock_polymarket_server import MockPolymarketServer
from tests.mock_kalshi_server import MockKalshiServer

# Import MarketsCoordinator (relative to master_manager)
from backend.master_manager.markets_coordinator import MarketsCoordinator

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def run_mock_integration_test():
    """Run complete integration test with mock servers and MarketsCoordinator"""
    
    print("🎯 MOCK INTEGRATION TEST - MarketsCoordinator + Mock Servers")
    print("=" * 70)
    print(f"⏰ Started: {datetime.now().isoformat()}")
    print()
    
    print("🔧 Environment Configuration:")
    print(f"   POLYMARKET_WS_URL = {os.environ['POLYMARKET_WS_URL']}")
    print(f"   KALSHI_WS_URL = {os.environ['KALSHI_WS_URL']}")
    print()
    
    # Start mock servers
    poly_server = MockPolymarketServer(port=8001)
    kalshi_server = MockKalshiServer(port=8002)
    
    try:
        print("🚀 Starting mock servers...")
        await poly_server.start()
        await kalshi_server.start()
        print("✅ Mock servers started")
        
        # Give servers a moment to start
        await asyncio.sleep(1)
        
        print("\n📊 Creating MarketsCoordinator...")
        coordinator = MarketsCoordinator()
        print("✅ MarketsCoordinator created")
        
        print("\n🔄 Starting async components...")
        await coordinator.start_async_components()
        print("✅ Async components started (queues, processors, ticker publishers)")
        
        # Test market connections
        print("\n🔍 Testing market connections...")
        
        # Test Polymarket connection with test token
        print("   📈 Connecting to Polymarket test market...")
        poly_result = await coordinator.connect("test_token_123", "polymarket")
        print(f"   {'✅ SUCCESS' if poly_result else '❌ FAILED'} - Polymarket connection")
        
        # Test Kalshi connection with test market
        print("   📈 Connecting to Kalshi test market...")
        kalshi_result = await coordinator.connect("TEST-MARKET-Y", "kalshi")
        print(f"   {'✅ SUCCESS' if kalshi_result else '❌ FAILED'} - Kalshi connection")
        
        if poly_result or kalshi_result:
            print(f"\n⏱️ Running for 20 seconds to collect market data...")
            
            # Monitor for updates
            start_time = datetime.now()
            for i in range(4):  # 4 intervals of 5 seconds each
                await asyncio.sleep(5)
                elapsed = (datetime.now() - start_time).total_seconds()
                print(f"   📊 {elapsed:.0f}s - Collecting market data...")
                
                # Get status
                status = coordinator.get_status()
                print(f"      Total connections: {status['total_connections']}")
                if status['kalshi_platform']['async_started']:
                    print(f"      ✅ Kalshi pipeline active")
                if status['polymarket_platform']['async_started']:
                    print(f"      ✅ Polymarket pipeline active")
        
        # Final status check
        print(f"\n📋 Final Status Check:")
        status = coordinator.get_status()
        print(f"   📊 Total connections: {status['total_connections']}")
        print(f"   📊 Kalshi platform active: {status['kalshi_platform']['async_started']}")
        print(f"   📊 Polymarket platform active: {status['polymarket_platform']['async_started']}")
        
        # Cleanup
        print(f"\n🧹 Cleaning up...")
        await coordinator.disconnect_all()
        print("✅ MarketsCoordinator cleanup completed")
        
        # Results
        print(f"\n📊 INTEGRATION TEST RESULTS:")
        print(f"   🔌 Polymarket Connection: {'✅ SUCCESS' if poly_result else '❌ FAILED'}")
        print(f"   🔌 Kalshi Connection: {'✅ SUCCESS' if kalshi_result else '❌ FAILED'}")
        overall_success = poly_result or kalshi_result
        print(f"   🎯 Overall Result: {'✅ SUCCESS' if overall_success else '❌ FAILED'}")
        
        return overall_success
        
    except Exception as e:
        print(f"\n💥 Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        print(f"\n🛑 Stopping mock servers...")
        await poly_server.stop()
        await kalshi_server.stop()
        print("✅ Mock servers stopped")

async def main():
    """Main entry point"""
    success = await run_mock_integration_test()
    
    print(f"\n🏁 Test completed with result: {'SUCCESS' if success else 'FAILED'}")
    return 0 if success else 1

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⏹️ Test interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)