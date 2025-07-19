"""
Comprehensive tests for the refactored architecture

Tests the EventBus, MessageForwarder, ConnectionManager, platform managers,
ServiceCoordinator, and MarketsCoordinator components.
"""
import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any

# Import components to test
from ..events.event_bus import EventBus
from ..messaging.message_forwarder import MessageForwarder
from ..connection.connection_manager import ConnectionManager
from ..services.service_coordinator import ServiceCoordinator
from ..markets_coordinator import MarketsCoordinator


class TestEventBus:
    """Test the EventBus component."""
    
    def setup_method(self):
        """Set up a fresh EventBus for each test."""
        self.event_bus = EventBus()
    
    def test_event_bus_initialization(self):
        """Test EventBus initializes correctly."""
        assert len(self.event_bus._subscribers) == 0
        assert len(self.event_bus._wildcard_subscribers) == 0
        assert len(self.event_bus._event_stats) == 0
    
    def test_subscribe_and_unsubscribe(self):
        """Test event subscription and unsubscription."""
        def handler(data):
            pass
        
        # Subscribe
        self.event_bus.subscribe('test.event', handler)
        assert len(self.event_bus._subscribers['test.event']) == 1
        
        # Unsubscribe
        success = self.event_bus.unsubscribe('test.event', handler)
        assert success
        assert len(self.event_bus._subscribers['test.event']) == 0
    
    def test_wildcard_subscription(self):
        """Test wildcard event subscription."""
        def wildcard_handler(data):
            pass
        
        self.event_bus.subscribe('*', wildcard_handler)
        assert len(self.event_bus._wildcard_subscribers) == 1
    
    @pytest.mark.asyncio
    async def test_event_publishing(self):
        """Test event publishing to subscribers."""
        received_data = []
        
        async def async_handler(data):
            received_data.append(data)
        
        def sync_handler(data):
            received_data.append(f"sync_{data}")
        
        # Subscribe handlers
        self.event_bus.subscribe('test.event', async_handler)
        self.event_bus.subscribe('test.event', sync_handler)
        
        # Publish event
        test_data = {'message': 'test_data'}
        exceptions = await self.event_bus.publish('test.event', test_data)
        
        # Verify
        assert len(exceptions) == 0
        assert test_data in received_data
        assert 'sync_test_data' in received_data
        assert self.event_bus._event_stats['test.event'] == 1
    
    @pytest.mark.asyncio
    async def test_exception_handling(self):
        """Test that exceptions in handlers are isolated."""
        received_data = []
        
        async def good_handler(data):
            received_data.append('good')
        
        async def bad_handler(data):
            raise ValueError("Test exception")
        
        # Subscribe handlers
        self.event_bus.subscribe('test.event', good_handler)
        self.event_bus.subscribe('test.event', bad_handler)
        
        # Publish event
        exceptions = await self.event_bus.publish('test.event', 'test')
        
        # Verify good handler still worked despite bad handler exception
        assert 'good' in received_data
        assert len(exceptions) == 1
        assert isinstance(exceptions[0], ValueError)
    
    def test_get_stats(self):
        """Test statistics collection."""
        def handler(data):
            pass
        
        self.event_bus.subscribe('test.event', handler)
        self.event_bus.subscribe('*', handler)
        
        stats = self.event_bus.get_stats()
        assert stats['total_subscribers'] == 2
        assert stats['event_types'] == 1
        assert stats['wildcard_subscribers'] == 1


class TestMessageForwarder:
    """Test the MessageForwarder component."""
    
    def setup_method(self):
        """Set up MessageForwarder for each test."""
        self.mock_queue = Mock()
        self.mock_queue.put_message = AsyncMock()
        self.forwarder = MessageForwarder('test_platform', self.mock_queue, rate_limit=10)
    
    @pytest.mark.asyncio
    async def test_message_forwarding(self):
        """Test basic message forwarding."""
        raw_message = '{"type": "test"}'
        metadata = {'source': 'test'}
        
        success = await self.forwarder.forward_message(raw_message, metadata)
        
        assert success
        assert self.mock_queue.put_message.called
        
        # Check enhanced metadata
        call_args = self.mock_queue.put_message.call_args
        enhanced_metadata = call_args[0][1]
        assert enhanced_metadata['platform'] == 'test_platform'
        assert enhanced_metadata['source'] == 'test'
        assert 'timestamp' in enhanced_metadata
    
    @pytest.mark.asyncio
    async def test_rate_limiting(self):
        """Test rate limiting functionality."""
        # Send messages up to rate limit
        for i in range(10):
            success = await self.forwarder.forward_message(f'message_{i}', {})
            assert success
        
        # Next message should be rate limited
        success = await self.forwarder.forward_message('rate_limited', {})
        assert not success
        assert self.forwarder.stats['rate_limited_messages'] == 1
    
    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test error handling in message forwarding."""
        self.mock_queue.put_message.side_effect = Exception("Queue error")
        
        success = await self.forwarder.forward_message('test', {})
        
        assert not success
        assert self.forwarder.stats['errors'] == 1
    
    def test_get_stats(self):
        """Test statistics collection."""
        stats = self.forwarder.get_stats()
        
        assert stats['platform'] == 'test_platform'
        assert stats['rate_limit'] == 10
        assert 'total_messages' in stats


class TestConnectionManager:
    """Test the ConnectionManager component."""
    
    def setup_method(self):
        """Set up ConnectionManager for each test."""
        self.event_bus = EventBus()
        self.connection_manager = ConnectionManager('test_platform', self.event_bus)
        
        # Mock message forwarder
        self.mock_forwarder = Mock()
        self.mock_forwarder.forward_message = AsyncMock(return_value=True)
    
    def test_create_client_callbacks(self):
        """Test callback creation."""
        message_cb, connection_cb, error_cb = self.connection_manager.create_client_callbacks(
            'test_client', self.mock_forwarder
        )
        
        assert callable(message_cb)
        assert callable(connection_cb)
        assert callable(error_cb)
        assert 'test_client' in self.connection_manager.active_connections
    
    @pytest.mark.asyncio
    async def test_message_callback(self):
        """Test message callback functionality."""
        message_cb, _, _ = self.connection_manager.create_client_callbacks(
            'test_client', self.mock_forwarder
        )
        
        # Test successful message forwarding
        await message_cb('test_message', {'test': 'metadata'})
        
        assert self.mock_forwarder.forward_message.called
        assert self.connection_manager.active_connections['test_client']['message_count'] == 1
    
    def test_connection_callback(self):
        """Test connection callback functionality."""
        _, connection_cb, _ = self.connection_manager.create_client_callbacks(
            'test_client', self.mock_forwarder
        )
        
        # Test connection status change
        connection_cb(True)
        assert self.connection_manager.active_connections['test_client']['status'] == 'connected'
        
        connection_cb(False)
        assert self.connection_manager.active_connections['test_client']['status'] == 'disconnected'
    
    def test_error_callback(self):
        """Test error callback functionality."""
        _, _, error_cb = self.connection_manager.create_client_callbacks(
            'test_client', self.mock_forwarder
        )
        
        # Test error handling
        error_cb(Exception("Test error"))
        assert self.connection_manager.active_connections['test_client']['status'] == 'error'
        assert self.connection_manager.active_connections['test_client']['error_count'] == 1
    
    def test_remove_connection(self):
        """Test connection removal."""
        self.connection_manager.create_client_callbacks('test_client', self.mock_forwarder)
        
        success = self.connection_manager.remove_connection('test_client')
        assert success
        assert 'test_client' not in self.connection_manager.active_connections
    
    def test_get_connection_stats(self):
        """Test connection statistics."""
        self.connection_manager.create_client_callbacks('client1', self.mock_forwarder)
        self.connection_manager.create_client_callbacks('client2', self.mock_forwarder)
        
        stats = self.connection_manager.get_connection_stats()
        assert stats['total_connections'] == 2
        assert stats['platform'] == 'test_platform'


class TestServiceCoordinator:
    """Test the ServiceCoordinator component."""
    
    def setup_method(self):
        """Set up ServiceCoordinator for each test."""
        self.event_bus = EventBus()
        self.mock_arbitrage = Mock()
        self.mock_arbitrage.set_processors = Mock()
        self.mock_arbitrage.set_arbitrage_alert_callback = Mock()
        self.mock_arbitrage.handle_kalshi_orderbook_update = AsyncMock()
        self.mock_arbitrage.handle_polymarket_orderbook_update = AsyncMock()
        self.mock_arbitrage.get_stats = Mock(return_value={})
        
        self.service_coordinator = ServiceCoordinator(self.event_bus, self.mock_arbitrage)
    
    @pytest.mark.asyncio
    async def test_start_services(self):
        """Test service startup."""
        mock_kalshi_processor = Mock()
        mock_polymarket_processor = Mock()
        
        await self.service_coordinator.start_services(mock_kalshi_processor, mock_polymarket_processor)
        
        assert self.service_coordinator.services_started
        assert self.mock_arbitrage.set_processors.called
    
    @pytest.mark.asyncio
    async def test_kalshi_orderbook_update_handling(self):
        """Test Kalshi orderbook update handling."""
        event_data = {
            'sid': 123,
            'orderbook_state': Mock(),
            'platform': 'kalshi'
        }
        
        await self.service_coordinator._handle_kalshi_orderbook_update(event_data)
        
        self.mock_arbitrage.handle_kalshi_orderbook_update.assert_called_once_with(
            123, event_data['orderbook_state']
        )
        assert self.service_coordinator.stats['kalshi_orderbook_updates'] == 1
    
    @pytest.mark.asyncio
    async def test_polymarket_orderbook_update_handling(self):
        """Test Polymarket orderbook update handling."""
        event_data = {
            'asset_id': 'asset123',
            'orderbook_state': Mock(),
            'platform': 'polymarket'
        }
        
        await self.service_coordinator._handle_polymarket_orderbook_update(event_data)
        
        self.mock_arbitrage.handle_polymarket_orderbook_update.assert_called_once_with(
            'asset123', event_data['orderbook_state']
        )
        assert self.service_coordinator.stats['polymarket_orderbook_updates'] == 1
    
    def test_get_stats(self):
        """Test statistics collection."""
        stats = self.service_coordinator.get_stats()
        
        assert 'services_started' in stats
        assert 'coordinator_stats' in stats
        assert 'arbitrage_stats' in stats
        assert 'event_bus_stats' in stats


class TestMarketsCoordinator:
    """Test the MarketsCoordinator component."""
    
    def setup_method(self):
        """Set up MarketsCoordinator for each test."""
        with patch('backend.master_manager.markets_coordinator.KalshiPlatformManager'), \
             patch('backend.master_manager.markets_coordinator.PolymarketPlatformManager'), \
             patch('backend.master_manager.markets_coordinator.ServiceCoordinator'):
            
            self.coordinator = MarketsCoordinator()
            
            # Mock platform managers
            self.coordinator.kalshi_platform = Mock()
            self.coordinator.kalshi_platform.start_async_components = AsyncMock()
            self.coordinator.kalshi_platform.connect_market = AsyncMock(return_value=True)
            self.coordinator.kalshi_platform.disconnect_market = AsyncMock(return_value=True)
            self.coordinator.kalshi_platform.disconnect_all = AsyncMock()
            self.coordinator.kalshi_platform.get_stats = Mock(return_value={'total_connections': 1})
            
            self.coordinator.polymarket_platform = Mock()
            self.coordinator.polymarket_platform.start_async_components = AsyncMock()
            self.coordinator.polymarket_platform.connect_market = AsyncMock(return_value=True)
            self.coordinator.polymarket_platform.disconnect_market = AsyncMock(return_value=True)
            self.coordinator.polymarket_platform.disconnect_all = AsyncMock()
            self.coordinator.polymarket_platform.get_stats = Mock(return_value={'total_connections': 2})
            
            # Mock service coordinator
            self.coordinator.service_coordinator = Mock()
            self.coordinator.service_coordinator.start_services = AsyncMock()
            self.coordinator.service_coordinator.stop_services = AsyncMock()
            self.coordinator.service_coordinator.get_stats = Mock(return_value={})
    
    @pytest.mark.asyncio
    async def test_start_async_components(self):
        """Test async component startup."""
        await self.coordinator.start_async_components()
        
        assert self.coordinator._async_started
        assert self.coordinator.kalshi_platform.start_async_components.called
        assert self.coordinator.polymarket_platform.start_async_components.called
        assert self.coordinator.service_coordinator.start_services.called
    
    @pytest.mark.asyncio
    async def test_connect_kalshi_market(self):
        """Test Kalshi market connection."""
        success = await self.coordinator.connect('test_market', 'kalshi')
        
        assert success
        assert self.coordinator.kalshi_platform.connect_market.called_with('test_market')
    
    @pytest.mark.asyncio
    async def test_connect_polymarket_market(self):
        """Test Polymarket market connection.""" 
        success = await self.coordinator.connect('test_market', 'polymarket')
        
        assert success
        assert self.coordinator.polymarket_platform.connect_market.called_with('test_market')
    
    @pytest.mark.asyncio
    async def test_connect_unsupported_platform(self):
        """Test connection to unsupported platform."""
        success = await self.coordinator.connect('test_market', 'unsupported')
        
        assert not success
    
    @pytest.mark.asyncio
    async def test_disconnect_market(self):
        """Test market disconnection."""
        success = await self.coordinator.disconnect('test_market', 'kalshi')
        
        assert success
        assert self.coordinator.kalshi_platform.disconnect_market.called_with('test_market')
    
    @pytest.mark.asyncio
    async def test_disconnect_all(self):
        """Test disconnecting all markets."""
        await self.coordinator.disconnect_all()
        
        assert not self.coordinator._async_started
        assert self.coordinator.service_coordinator.stop_services.called
        assert self.coordinator.kalshi_platform.disconnect_all.called
        assert self.coordinator.polymarket_platform.disconnect_all.called
    
    def test_get_status(self):
        """Test status reporting."""
        status = self.coordinator.get_status()
        
        assert 'async_started' in status
        assert 'kalshi_platform' in status
        assert 'polymarket_platform' in status
        assert 'service_coordinator' in status
        assert 'total_connections' in status
        assert status['total_connections'] == 3  # 1 + 2 from mocked platform stats


# Integration test
@pytest.mark.asyncio
async def test_end_to_end_event_flow():
    """Test end-to-end event flow through the architecture."""
    event_bus = EventBus()
    received_events = []
    
    # Set up event handler
    async def event_handler(data):
        received_events.append(data)
    
    event_bus.subscribe('test.integration', event_handler)
    
    # Publish event
    test_data = {'integration': 'test', 'value': 42}
    await event_bus.publish('test.integration', test_data)
    
    # Verify event was received
    assert len(received_events) == 1
    assert received_events[0] == test_data


if __name__ == '__main__':
    pytest.main([__file__, '-v'])