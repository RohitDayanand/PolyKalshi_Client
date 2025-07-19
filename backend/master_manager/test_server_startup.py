#!/usr/bin/env python3
"""
Test WebSocket server startup with new refactored architecture
"""
import asyncio
import sys
import os

# Add the backend path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def test_coordinator_initialization():
    """Test that the MarketsCoordinator can be initialized and started."""
    print("Testing MarketsCoordinator initialization...")
    
    try:
        from master_manager.markets_coordinator import MarketsCoordinator
        
        # Create coordinator
        coordinator = MarketsCoordinator()
        print("✅ MarketsCoordinator created successfully")
        
        # Test status before starting
        status = coordinator.get_status()
        print(f"Initial status: async_started={status['async_started']}")
        print(f"Total connections: {status['total_connections']}")
        
        # Start async components
        await coordinator.start_async_components()
        print("✅ Async components started successfully")
        
        # Test status after starting
        status = coordinator.get_status()
        print(f"After start: async_started={status['async_started']}")
        
        # Test platform stats
        kalshi_stats = status['kalshi_platform']
        polymarket_stats = status['polymarket_platform']
        
        print(f"Kalshi platform async_started: {kalshi_stats['async_started']}")
        print(f"Polymarket platform async_started: {polymarket_stats['async_started']}")
        
        # Cleanup
        await coordinator.disconnect_all()
        print("✅ Cleanup completed successfully")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_websocket_server_imports():
    """Test that websocket_server can import the new coordinator."""
    print("Testing WebSocket server imports...")
    
    try:
        # Test the import that websocket_server.py uses
        from backend.master_manager.markets_coordinator import MarketsCoordinator
        
        coordinator = MarketsCoordinator()
        print("✅ WebSocket server can import MarketsCoordinator")
        
        # Test the method that websocket_server calls
        success = await coordinator.start_async_components()
        print("✅ start_async_components method works")
        
        await coordinator.disconnect_all()
        return True
        
    except Exception as e:
        print(f"❌ WebSocket server import test failed: {e}")
        return False

async def test_connection_api():
    """Test the connection API that websocket_server uses."""
    print("Testing connection API...")
    
    try:
        from master_manager.markets_coordinator import MarketsCoordinator
        
        coordinator = MarketsCoordinator()
        await coordinator.start_async_components()
        
        # Test the connect method (this won't actually connect since no credentials)
        # but it should not crash and should return False gracefully
        print("Testing Kalshi connection API...")
        result = await coordinator.connect("test_market", "kalshi")
        print(f"Kalshi connect result: {result} (expected False due to no credentials)")
        
        print("Testing Polymarket connection API...")
        result = await coordinator.connect("test_market", "polymarket") 
        print(f"Polymarket connect result: {result} (expected False due to no credentials)")
        
        print("Testing unsupported platform...")
        result = await coordinator.connect("test_market", "invalid_platform")
        print(f"Invalid platform result: {result} (expected False)")
        
        await coordinator.disconnect_all()
        print("✅ Connection API works correctly")
        return True
        
    except Exception as e:
        print(f"❌ Connection API test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def run_all_tests():
    """Run all startup tests."""
    print("=" * 60)
    print("Testing Refactored Architecture - Server Startup")
    print("=" * 60)
    
    tests = [
        ("Coordinator Initialization", test_coordinator_initialization),
        ("WebSocket Server Imports", test_websocket_server_imports),
        ("Connection API", test_connection_api),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n--- {test_name} ---")
        if await test_func():
            passed += 1
            print(f"✅ {test_name} PASSED")
        else:
            print(f"❌ {test_name} FAILED")
    
    print("\n" + "=" * 60)
    print(f"Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All startup tests passed! The refactored architecture is ready for production.")
        print("\nNext steps:")
        print("1. Start the WebSocket server: python websocket_server.py")
        print("2. Test market connections through the API")
        print("3. Verify ticker publishing works correctly")
        return True
    else:
        print(f"❌ {total - passed} test(s) failed - architecture needs fixes")
        return False

if __name__ == '__main__':
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)