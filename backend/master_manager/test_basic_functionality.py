#!/usr/bin/env python3
"""
Basic functionality test for the refactored architecture
Tests imports and basic operations without requiring pytest
"""
import asyncio
import sys
import os

# Add the backend path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_imports():
    """Test that all new components can be imported."""
    print("Testing imports...")
    
    try:
        from .events.event_bus import EventBus, global_event_bus
        from .messaging.message_forwarder import MessageForwarder
        from .connection.connection_manager import ConnectionManager
        from .services.service_coordinator import ServiceCoordinator
        from .markets_coordinator import MarketsCoordinator, create_markets_manager
        print("✅ All imports successful")
        return True
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False

def test_event_bus():
    """Test basic EventBus functionality."""
    print("Testing EventBus...")
    
    try:
        event_bus = EventBus()
        
        # Test subscription
        received_events = []
        def handler(data):
            received_events.append(data)
        
        event_bus.subscribe('test.event', handler)
        
        # Test stats
        stats = event_bus.get_stats()
        assert stats['total_subscribers'] == 1
        
        print("✅ EventBus basic functionality works")
        return True
    except Exception as e:
        print(f"❌ EventBus test failed: {e}")
        return False

async def test_event_publishing():
    """Test EventBus publishing."""
    print("Testing EventBus publishing...")
    
    try:
        event_bus = EventBus()
        received_events = []
        
        async def async_handler(data):
            received_events.append(data)
        
        event_bus.subscribe('test.async', async_handler)
        
        # Publish event
        test_data = {'test': 'data'}
        exceptions = await event_bus.publish('test.async', test_data)
        
        assert len(exceptions) == 0
        assert len(received_events) == 1
        assert received_events[0] == test_data
        
        print("✅ EventBus publishing works")
        return True
    except Exception as e:
        print(f"❌ EventBus publishing test failed: {e}")
        return False

def test_message_forwarder():
    """Test MessageForwarder basic functionality."""
    print("Testing MessageForwarder...")
    
    try:
        # Mock queue
        class MockQueue:
            def __init__(self):
                self.messages = []
            
            async def put_message(self, raw_message, metadata):
                self.messages.append((raw_message, metadata))
        
        mock_queue = MockQueue()
        forwarder = MessageForwarder('test_platform', mock_queue, rate_limit=100)
        
        # Test stats
        stats = forwarder.get_stats()
        assert stats['platform'] == 'test_platform'
        assert stats['rate_limit'] == 100
        
        print("✅ MessageForwarder basic functionality works")
        return True
    except Exception as e:
        print(f"❌ MessageForwarder test failed: {e}")
        return False

async def test_message_forwarding():
    """Test actual message forwarding."""
    print("Testing message forwarding...")
    
    try:
        # Mock queue
        class MockQueue:
            def __init__(self):
                self.messages = []
            
            async def put_message(self, raw_message, metadata):
                self.messages.append((raw_message, metadata))
        
        mock_queue = MockQueue()
        forwarder = MessageForwarder('test_platform', mock_queue)
        
        # Forward a message
        success = await forwarder.forward_message('test_message', {'test': 'metadata'})
        
        assert success
        assert len(mock_queue.messages) == 1
        assert mock_queue.messages[0][0] == 'test_message'
        assert mock_queue.messages[0][1]['platform'] == 'test_platform'
        
        print("✅ Message forwarding works")
        return True
    except Exception as e:
        print(f"❌ Message forwarding test failed: {e}")
        return False

def test_connection_manager():
    """Test ConnectionManager basic functionality."""
    print("Testing ConnectionManager...")
    
    try:
        from .events.event_bus import EventBus
        from .connection.connection_manager import ConnectionManager
        
        event_bus = EventBus()
        conn_manager = ConnectionManager('test_platform', event_bus)
        
        # Mock message forwarder
        class MockForwarder:
            async def forward_message(self, raw_message, metadata):
                return True
        
        mock_forwarder = MockForwarder()
        
        # Create callbacks
        message_cb, connection_cb, error_cb = conn_manager.create_client_callbacks(
            'test_client', mock_forwarder
        )
        
        assert callable(message_cb)
        assert callable(connection_cb) 
        assert callable(error_cb)
        assert 'test_client' in conn_manager.active_connections
        
        # Test stats
        stats = conn_manager.get_connection_stats()
        assert stats['total_connections'] == 1
        
        print("✅ ConnectionManager basic functionality works")
        return True
    except Exception as e:
        print(f"❌ ConnectionManager test failed: {e}")
        return False

def test_markets_coordinator():
    """Test MarketsCoordinator basic functionality.""" 
    print("Testing MarketsCoordinator...")
    
    try:
        from .markets_coordinator import create_markets_manager
        
        # This will test imports and basic initialization
        coordinator = create_markets_manager()
        
        # Test status (should not fail even without connections)
        status = coordinator.get_status()
        assert 'async_started' in status
        assert 'total_connections' in status
        
        print("✅ MarketsCoordinator basic functionality works")
        return True
    except Exception as e:
        print(f"❌ MarketsCoordinator test failed: {e}")
        return False

async def run_all_tests():
    """Run all tests."""
    print("=" * 50)
    print("Testing Refactored Architecture")
    print("=" * 50)
    
    tests_passed = 0
    total_tests = 7
    
    # Sync tests
    if test_imports():
        tests_passed += 1
    
    if test_event_bus():
        tests_passed += 1
    
    if test_message_forwarder():
        tests_passed += 1
        
    if test_connection_manager():
        tests_passed += 1
        
    if test_markets_coordinator():
        tests_passed += 1
    
    # Async tests
    if await test_event_publishing():
        tests_passed += 1
        
    if await test_message_forwarding():
        tests_passed += 1
    
    print("=" * 50)
    print(f"Test Results: {tests_passed}/{total_tests} tests passed")
    
    if tests_passed == total_tests:
        print("🎉 All tests passed! Refactored architecture is working correctly.")
        return True
    else:
        print(f"❌ {total_tests - tests_passed} test(s) failed")
        return False

if __name__ == '__main__':
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)