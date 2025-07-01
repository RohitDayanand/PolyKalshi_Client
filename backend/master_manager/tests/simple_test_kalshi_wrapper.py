"""
Simple test runner for Kalshi Client Wrapper using only standard library.

This module provides basic testing for the KalshiClient and KalshiClientConfig
classes without requiring external dependencies like pytest.

Run with: python simple_test_kalshi_wrapper.py
"""

import unittest
import asyncio
import json
import time
import threading
import sys
import os
from unittest.mock import Mock, patch, AsyncMock, MagicMock, mock_open
from datetime import datetime, timedelta

# Add the parent directory to sys.path to import the client
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from backend.master_manager.kalshi_client.kalshi_client_wrapper import (
        KalshiClient, 
        KalshiClientConfig, 
        Environment,
        create_kalshi_client
    )
    CLIENT_IMPORTED = True
except ImportError as e:
    print(f"Warning: Could not import kalshi_client_wrapper: {e}")
    CLIENT_IMPORTED = False


class TestKalshiClientConfig(unittest.TestCase):
    """Test suite for KalshiClientConfig class using unittest."""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        if not CLIENT_IMPORTED:
            self.skipTest("KalshiClient not available")
    
    @patch('kalshi_client_wrapper.KalshiClientConfig._load_private_key')
    def test_config_initialization_with_defaults(self, mock_load_key):
        """Test config initialization with default values."""
        mock_load_key.return_value = Mock()
        
        config = KalshiClientConfig(ticker="TEST-001")
        
        self.assertEqual(config.ticker, "TEST-001")
        self.assertEqual(config.channel, "orderbook_delta")
        self.assertEqual(config.environment, Environment.DEMO)
        self.assertEqual(config.ping_interval, 30)
        self.assertEqual(config.reconnect_interval, 5)
        self.assertEqual(config.log_level, "INFO")
    
    @patch('kalshi_client_wrapper.KalshiClientConfig._load_private_key')
    def test_config_initialization_with_custom_values(self, mock_load_key):
        """Test config initialization with custom values."""
        mock_load_key.return_value = Mock()
        
        config = KalshiClientConfig(
            ticker="CUSTOM-001",
            channel="trades",
            environment=Environment.PROD,
            ping_interval=60,
            reconnect_interval=10,
            log_level="DEBUG"
        )
        
        self.assertEqual(config.ticker, "CUSTOM-001")
        self.assertEqual(config.channel, "trades")
        self.assertEqual(config.environment, Environment.PROD)
        self.assertEqual(config.ping_interval, 60)
        self.assertEqual(config.reconnect_interval, 10)
        self.assertEqual(config.log_level, "DEBUG")
    
    @patch.dict('os.environ', {'PROD_KEYID': 'test_key_id'})
    @patch('kalshi_client_wrapper.KalshiClientConfig._load_private_key')
    def test_config_key_id_from_environment(self, mock_load_key):
        """Test key_id loading from environment variables."""
        mock_load_key.return_value = Mock()
        
        config = KalshiClientConfig(ticker="TEST-001")
        self.assertEqual(config.key_id, 'test_key_id')
    
    @patch.dict('os.environ', {'PROD_KEYID': 'env_key'})
    @patch('kalshi_client_wrapper.KalshiClientConfig._load_private_key')
    def test_config_explicit_key_id_overrides_environment(self, mock_load_key):
        """Test that explicit key_id overrides environment variable."""
        mock_load_key.return_value = Mock()
        
        config = KalshiClientConfig(ticker="TEST-001", key_id="explicit_key")
        self.assertEqual(config.key_id, "explicit_key")
    
    @patch("builtins.open", mock_open(read_data=b"fake_private_key_data"))
    @patch("kalshi_client_wrapper.serialization.load_pem_private_key")
    def test_private_key_loading_success(self, mock_load_key):
        """Test successful private key loading."""
        mock_private_key = Mock()
        mock_load_key.return_value = mock_private_key
        
        config = KalshiClientConfig(ticker="TEST-001")
        
        mock_load_key.assert_called_once()
        self.assertEqual(config.private_key, mock_private_key)
    
    @patch("builtins.open", side_effect=FileNotFoundError())
    def test_private_key_loading_file_not_found(self, mock_open):
        """Test private key loading when file is not found."""
        with self.assertRaises(FileNotFoundError):
            KalshiClientConfig(ticker="TEST-001")
        self.assertEqual(config.channel, "orderbook_delta")
        self.assertEqual(config.environment, Environment.DEMO)
        self.assertEqual(config.ping_interval, 30)
    
    @patch('builtins.open')
    @patch('kalshi_client_wrapper.serialization.load_pem_private_key')
    def test_client_creation(self, mock_load_key, mock_open):
        """Test basic client creation."""
        mock_key = Mock()
        mock_load_key.return_value = mock_key
        
        config = KalshiClientConfig(ticker="TEST")
        client = KalshiClient(config)
        
        self.assertEqual(client.ticker, "TEST")
        self.assertEqual(client.channel, "orderbook_delta")
        self.assertFalse(client.is_connected)
        self.assertTrue(client.should_reconnect)
    
    @patch('builtins.open')
    @patch('kalshi_client_wrapper.serialization.load_pem_private_key')
    def test_callback_setting(self, mock_load_key, mock_open):
        """Test setting callbacks."""
        mock_key = Mock()
        mock_load_key.return_value = mock_key
        
        config = KalshiClientConfig(ticker="TEST")
        client = KalshiClient(config)
        
        message_cb = Mock()
        connection_cb = Mock()
        error_cb = Mock()
        
        client.set_message_callback(message_cb)
        client.set_connection_callback(connection_cb)
        client.set_error_callback(error_cb)
        
        self.assertEqual(client.on_message_callback, message_cb)
        self.assertEqual(client.on_connection_callback, connection_cb)
        self.assertEqual(client.on_error_callback, error_cb)
    
    @patch('builtins.open')
    @patch('kalshi_client_wrapper.serialization.load_pem_private_key')
    def test_ws_url_generation(self, mock_load_key, mock_open):
        """Test WebSocket URL generation."""
        mock_key = Mock()
        mock_load_key.return_value = mock_key
        
        # Test DEMO environment
        config = KalshiClientConfig(ticker="TEST", environment=Environment.DEMO)
        client = KalshiClient(config)
        url = client._get_ws_url()
        self.assertEqual(url, "wss://demo-api.kalshi.co/trade-api/ws/v2")
        
        # Test PROD environment
        config.environment = Environment.PROD
        url = client._get_ws_url()
        self.assertEqual(url, "wss://api.elections.kalshi.com/trade-api/ws/v2")
    
    @patch('builtins.open')
    @patch('kalshi_client_wrapper.serialization.load_pem_private_key')
    def test_connect_validation(self, mock_load_key, mock_open):
        """Test connection validation."""
        mock_key = Mock()
        mock_load_key.return_value = mock_key
        
        config = KalshiClientConfig(ticker="TEST", key_id="test_key")
        client = KalshiClient(config)
        
        # Should fail validation if no key_id
        client.config.key_id = None
        result = client.connect()
        self.assertFalse(result)
        
        # Should fail validation if no private_key
        client.config.key_id = "test_key"
        client.config.private_key = None
        result = client.connect()
        self.assertFalse(result)
    
    @patch('builtins.open')
    @patch('kalshi_client_wrapper.serialization.load_pem_private_key')
    def test_status_reporting(self, mock_load_key, mock_open):
        """Test status reporting."""
        mock_key = Mock()
        mock_load_key.return_value = mock_key
        
        config = KalshiClientConfig(ticker="TEST")
        client = KalshiClient(config)
        
        status = client.get_status()
        
        self.assertIn("connected", status)
        self.assertIn("should_reconnect", status)
        self.assertIn("ticker", status)
        self.assertIn("channel", status)
        self.assertIn("environment", status)
        self.assertIn("threads_active", status)
        
        self.assertEqual(status["ticker"], "TEST")
        self.assertEqual(status["channel"], "orderbook_delta")
        self.assertEqual(status["environment"], "demo")
    
    @patch('builtins.open')
    @patch('kalshi_client_wrapper.serialization.load_pem_private_key')
    def test_is_running(self, mock_load_key, mock_open):
        """Test is_running status check."""
        mock_key = Mock()
        mock_load_key.return_value = mock_key
        
        config = KalshiClientConfig(ticker="TEST")
        client = KalshiClient(config)
        
        # Both must be True to be running
        client.is_connected = True
        client.should_reconnect = True
        self.assertTrue(client.is_running())
        
        # If either is False, not running
        client.is_connected = False
        self.assertFalse(client.is_running())
        
        client.is_connected = True
        client.should_reconnect = False
        self.assertFalse(client.is_running())
    
    @patch('time.time', return_value=1234567890.123)
    @patch('builtins.open')
    @patch('kalshi_client_wrapper.serialization.load_pem_private_key')
    def test_auth_headers(self, mock_load_key, mock_open, mock_time):
        """Test authentication header generation."""
        mock_key = Mock()
        mock_load_key.return_value = mock_key
        
        config = KalshiClientConfig(ticker="TEST", key_id="test_key_123")
        client = KalshiClient(config)
        
        with patch.object(client, '_sign_pss_text', return_value='mock_signature'):
            headers = client._create_auth_headers("GET", "/test/path")
            
            self.assertEqual(headers["KALSHI-ACCESS-KEY"], "test_key_123")
            self.assertEqual(headers["KALSHI-ACCESS-TIMESTAMP"], "1234567890123")
            self.assertEqual(headers["KALSHI-ACCESS-SIGNATURE"], "mock_signature")
    
    @patch('kalshi_client_wrapper.KalshiClient')
    @patch('kalshi_client_wrapper.KalshiClientConfig')
    def test_convenience_function(self, mock_config_class, mock_client_class):
        """Test the create_kalshi_client convenience function."""
        mock_config = Mock()
        mock_client = Mock()
        mock_config_class.return_value = mock_config
        mock_client_class.return_value = mock_client
        
        result = create_kalshi_client(
            ticker="TEST",
            channel="ticker_v2",
            environment=Environment.PROD
        )
        
        # Verify config was created
        mock_config_class.assert_called_once()
        call_kwargs = mock_config_class.call_args[1]
        self.assertEqual(call_kwargs["ticker"], "TEST")
        self.assertEqual(call_kwargs["channel"], "ticker_v2")
        self.assertEqual(call_kwargs["environment"], Environment.PROD)
        
        # Verify client was created with config
        mock_client_class.assert_called_once_with(mock_config)
        self.assertEqual(result, mock_client)


class TestKalshiClient(unittest.TestCase):
    """Test suite for KalshiClient class using unittest."""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        if not CLIENT_IMPORTED:
            self.skipTest("KalshiClient not available")
        
        # Create mock config
        self.mock_config = Mock(spec=KalshiClientConfig)
        self.mock_config.ticker = "TEST-001"
        self.mock_config.channel = "orderbook_delta"
        self.mock_config.environment = Environment.DEMO
        self.mock_config.ping_interval = 30
        self.mock_config.reconnect_interval = 5
        self.mock_config.key_id = "test_key_id"
        self.mock_config.private_key = Mock()
        
        self.client = KalshiClient(self.mock_config)
    
    def test_client_initialization(self):
        """Test client initialization with proper state."""
        self.assertEqual(self.client.config, self.mock_config)
        self.assertEqual(self.client.ticker, "TEST-001")
        self.assertEqual(self.client.channel, "orderbook_delta")
        self.assertIsNone(self.client.websocket)
        self.assertFalse(self.client.is_connected)
        self.assertTrue(self.client.should_reconnect)
        self.assertEqual(self.client.message_id, 1)
        self.assertIsInstance(self.client.last_message_time, datetime)
        self.assertEqual(self.client._threads, [])
        self.assertIsNone(self.client._loop)
        self.assertIsNone(self.client.on_message_callback)
        self.assertIsNone(self.client.on_connection_callback)
        self.assertIsNone(self.client.on_error_callback)
    
    def test_set_callbacks(self):
        """Test setting callback functions."""
        message_callback = Mock()
        connection_callback = Mock()
        error_callback = Mock()
        
        self.client.set_message_callback(message_callback)
        self.client.set_connection_callback(connection_callback)
        self.client.set_error_callback(error_callback)
        
        self.assertEqual(self.client.on_message_callback, message_callback)
        self.assertEqual(self.client.on_connection_callback, connection_callback)
        self.assertEqual(self.client.on_error_callback, error_callback)
    
    def test_get_ws_url_demo(self):
        """Test WebSocket URL generation for demo environment."""
        self.client.config.environment = Environment.DEMO
        url = self.client._get_ws_url()
        self.assertEqual(url, "wss://demo-api.kalshi.co/trade-api/ws/v2")
    
    def test_get_ws_url_prod(self):
        """Test WebSocket URL generation for production environment."""
        self.client.config.environment = Environment.PROD
        url = self.client._get_ws_url()
        self.assertEqual(url, "wss://api.elections.kalshi.com/trade-api/ws/v2")
    
    def test_get_ws_url_invalid_environment(self):
        """Test WebSocket URL generation with invalid environment."""
        self.client.config.environment = "invalid"
        with self.assertRaises(ValueError) as context:
            self.client._get_ws_url()
        self.assertIn("Invalid environment", str(context.exception))
    
    @patch('time.time', return_value=1609459200.0)  # Fixed timestamp
    def test_create_auth_headers(self, mock_time):
        """Test authentication header generation."""
        # Mock the sign method
        self.client._sign_pss_text = Mock(return_value="mock_signature")
        self.client.config.key_id = "test_key_id"
        
        headers = self.client._create_auth_headers("GET", "/trade-api/ws/v2")
        
        self.assertEqual(headers["KALSHI-ACCESS-KEY"], "test_key_id")
        self.assertEqual(headers["KALSHI-ACCESS-SIGNATURE"], "mock_signature")
        self.assertEqual(headers["KALSHI-ACCESS-TIMESTAMP"], "1609459200000")
        
        # Verify sign method was called with correct message
        expected_message = "1609459200000GET/trade-api/ws/v2"
        self.client._sign_pss_text.assert_called_once_with(expected_message)
    
    def test_connect_missing_key_id(self):
        """Test connect fails when key_id is missing."""
        self.client.config.key_id = None
        result = self.client.connect()
        self.assertFalse(result)
    
    def test_connect_missing_private_key(self):
        """Test connect fails when private_key is missing."""
        self.client.config.private_key = None
        result = self.client.connect()
        self.assertFalse(result)
    
    @patch('threading.Thread')
    @patch('time.sleep')
    def test_connect_success(self, mock_sleep, mock_thread):
        """Test successful connection initialization."""
        mock_thread_instance = Mock()
        mock_thread.return_value = mock_thread_instance
        
        result = self.client.connect()
        
        # Verify threads were started
        self.assertEqual(mock_thread.call_count, 2)  # Connection thread and monitor thread
        self.assertEqual(mock_thread_instance.start.call_count, 2)
        self.assertTrue(result)
    
    def test_disconnect(self):
        """Test client disconnection and cleanup."""
        # Setup client state
        self.client.websocket = AsyncMock()
        self.client.is_connected = True
        self.client.should_reconnect = True
        self.client._loop = Mock()
        self.client._loop.is_closed.return_value = False
        
        # Mock threads
        mock_thread = Mock()
        mock_thread.is_alive.return_value = True
        self.client._threads = [mock_thread]
        
        connection_callback = Mock()
        self.client.set_connection_callback(connection_callback)
        
        with patch('asyncio.run_coroutine_threadsafe') as mock_run_coro:
            mock_future = Mock()
            mock_run_coro.return_value = mock_future
            
            self.client.disconnect()
        
        # Verify state changes
        self.assertFalse(self.client.should_reconnect)
        self.assertFalse(self.client.is_connected)
        
        # Verify cleanup
        mock_thread.join.assert_called_once_with(timeout=2.0)
        connection_callback.assert_called_once_with(False)
    
    def test_is_running(self):
        """Test is_running status check."""
        # Test when not connected
        self.client.is_connected = False
        self.client.should_reconnect = True
        self.assertFalse(self.client.is_running())
        
        # Test when connected but shouldn't reconnect
        self.client.is_connected = True
        self.client.should_reconnect = False
        self.assertFalse(self.client.is_running())
        
        # Test when fully running
        self.client.is_connected = True
        self.client.should_reconnect = True
        self.assertTrue(self.client.is_running())
    
    def test_get_status(self):
        """Test status information retrieval."""
        self.client.is_connected = True
        self.client.should_reconnect = True
        self.client.last_message_time = datetime(2023, 1, 1, 12, 0, 0)
        
        # Mock active thread
        mock_thread = Mock()
        mock_thread.is_alive.return_value = True
        self.client._threads = [mock_thread]
        
        status = self.client.get_status()
        
        expected_status = {
            "connected": True,
            "should_reconnect": True,
            "ticker": "TEST-001",
            "channel": "orderbook_delta",
            "last_message_time": "2023-01-01T12:00:00",
            "environment": "demo",
            "threads_active": 1
        }
        
        self.assertEqual(status, expected_status)


class TestKalshiClientAsyncOperations(unittest.TestCase):
    """Test suite for async operations in KalshiClient using unittest."""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        if not CLIENT_IMPORTED:
            self.skipTest("KalshiClient not available")
        
        # Create mock config
        self.mock_config = Mock(spec=KalshiClientConfig)
        self.mock_config.ticker = "TEST-001"
        self.mock_config.channel = "orderbook_delta"
        self.mock_config.environment = Environment.DEMO
        self.mock_config.reconnect_interval = 1  # Short interval for testing
        self.mock_config.key_id = "test_key_id"
        self.mock_config.private_key = Mock()
        
        self.client = KalshiClient(self.mock_config)
    
    def run_async_test(self, async_func, *args, **kwargs):
        """Helper method to run async functions in sync tests."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(async_func(*args, **kwargs))
        finally:
            loop.close()
    
    def test_handle_websocket_message_json(self):
        """Test handling of JSON WebSocket messages."""
        callback = Mock()
        self.client.set_message_callback(callback)
        
        test_message = '{"type": "data", "ticker": "TEST-001", "data": {"price": 50}}'
        
        self.run_async_test(self.client._handle_websocket_message, test_message)
        
        callback.assert_called_once_with({
            "type": "data",
            "ticker": "TEST-001", 
            "data": {"price": 50}
        })
    
    def test_handle_websocket_message_pong(self):
        """Test handling of PONG messages."""
        callback = Mock()
        self.client.set_message_callback(callback)
        
        self.run_async_test(self.client._handle_websocket_message, "PONG")
        
        # PONG messages should not trigger callback
        callback.assert_not_called()
    
    def test_handle_websocket_message_ping(self):
        """Test handling of ping messages with pong response."""
        self.client.websocket = AsyncMock()
        ping_message = '{"type": "ping"}'
        
        self.run_async_test(self.client._handle_websocket_message, ping_message)
        
        # Verify pong response was sent
        expected_pong = json.dumps({"type": "pong"})
        self.client.websocket.send.assert_called_once_with(expected_pong)
    
    def test_handle_websocket_message_invalid_json(self):
        """Test handling of invalid JSON messages."""
        error_callback = Mock()
        self.client.set_error_callback(error_callback)
        
        self.run_async_test(self.client._handle_websocket_message, "invalid json")
        
        error_callback.assert_called_once()
        error = error_callback.call_args[0][0]
        self.assertIsInstance(error, Exception)
        self.assertIn("Invalid JSON message", str(error))
    
    def test_subscribe_to_channel(self):
        """Test channel subscription."""
        self.client.websocket = AsyncMock()
        
        self.run_async_test(self.client._subscribe_to_channel)
        
        # Verify subscription message was sent
        expected_message = {
            "id": 1,
            "cmd": "subscribe",
            "params": {
                "channels": "orderbook_delta",
                "market_tickers": ["TEST-001"]
            }
        }
        self.client.websocket.send.assert_called_once_with(json.dumps(expected_message))


class TestConvenienceFunction(unittest.TestCase):
    """Test suite for convenience functions using unittest."""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        if not CLIENT_IMPORTED:
            self.skipTest("KalshiClient not available")
    
    @patch("kalshi_client_wrapper.KalshiClientConfig")
    @patch("kalshi_client_wrapper.KalshiClient")
    def test_create_kalshi_client_default(self, mock_client_class, mock_config_class):
        """Test create_kalshi_client with default parameters."""
        mock_config = Mock()
        mock_config_class.return_value = mock_config
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        result = create_kalshi_client("TEST-001")
        
        # Verify config was created with correct parameters
        mock_config_class.assert_called_once_with(
            ticker="TEST-001",
            channel="orderbook_delta",
            environment=Environment.DEMO,
            ping_interval=30,
            log_level="INFO"
        )
        
        # Verify client was created with config
        mock_client_class.assert_called_once_with(mock_config)
        self.assertEqual(result, mock_client)
    
    @patch("kalshi_client_wrapper.KalshiClientConfig")
    @patch("kalshi_client_wrapper.KalshiClient")
    def test_create_kalshi_client_custom(self, mock_client_class, mock_config_class):
        """Test create_kalshi_client with custom parameters."""
        mock_config = Mock()
        mock_config_class.return_value = mock_config
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        result = create_kalshi_client(
            ticker="CUSTOM-001",
            channel="trades",
            environment=Environment.PROD,
            ping_interval=60,
            log_level="DEBUG"
        )
        
        # Verify config was created with custom parameters
        mock_config_class.assert_called_once_with(
            ticker="CUSTOM-001",
            channel="trades",
            environment=Environment.PROD,
            ping_interval=60,
            log_level="DEBUG"
        )
        
        self.assertEqual(result, mock_client)


class TestIntegrationScenarios(unittest.TestCase):
    """Test suite for integration scenarios and edge cases using unittest."""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        if not CLIENT_IMPORTED:
            self.skipTest("KalshiClient not available")
        
        # Create mock config
        self.mock_config = Mock(spec=KalshiClientConfig)
        self.mock_config.ticker = "INTEGRATION-001"
        self.mock_config.channel = "orderbook_delta"
        self.mock_config.environment = Environment.DEMO
        self.mock_config.ping_interval = 30
        self.mock_config.reconnect_interval = 5
        self.mock_config.key_id = "integration_key_id"
        self.mock_config.private_key = Mock()
        
        self.client = KalshiClient(self.mock_config)
    
    def test_full_callback_chain(self):
        """Test full callback chain with all callbacks set."""
        message_callback = Mock()
        connection_callback = Mock()
        error_callback = Mock()
        
        self.client.set_message_callback(message_callback)
        self.client.set_connection_callback(connection_callback)
        self.client.set_error_callback(error_callback)
        
        # Simulate various events
        test_message = {"type": "data", "ticker": "TEST-001"}
        
        # Test message callback
        if self.client.on_message_callback:
            self.client.on_message_callback(test_message)
        message_callback.assert_called_once_with(test_message)
        
        # Test connection callback
        if self.client.on_connection_callback:
            self.client.on_connection_callback(True)
        connection_callback.assert_called_once_with(True)
        
        # Test error callback
        test_error = Exception("Test error")
        if self.client.on_error_callback:
            self.client.on_error_callback(test_error)
        error_callback.assert_called_once_with(test_error)
    
    def run_async_test(self, async_func, *args, **kwargs):
        """Helper method to run async functions in sync tests."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(async_func(*args, **kwargs))
        finally:
            loop.close()
    
    def test_message_timing_updates(self):
        """Test that message timing is properly updated."""
        initial_time = self.client.last_message_time
        
        # Simulate receiving a message
        time.sleep(0.01)  # Small delay
        self.run_async_test(self.client._handle_websocket_message, '{"type": "test"}')
        
        # Verify time was updated
        self.assertGreater(self.client.last_message_time, initial_time)
    
    def test_thread_safety_considerations(self):
        """Test thread safety considerations."""
        # Verify initial thread list is empty
        self.assertEqual(self.client._threads, [])
        
        # Simulate adding threads (as would happen in connect())
        mock_thread1 = Mock()
        mock_thread2 = Mock()
        self.client._threads.extend([mock_thread1, mock_thread2])
        
        self.assertEqual(len(self.client._threads), 2)
        
        # Test thread cleanup in disconnect
        mock_thread1.is_alive.return_value = False
        mock_thread2.is_alive.return_value = True
        
        # This should not raise any exceptions
        for thread in self.client._threads:
            if thread.is_alive():
                thread.join(timeout=2.0)


def run_all_tests():
    """Run all test suites and provide a summary."""
    print("=" * 60)
    print("KALSHI CLIENT WRAPPER - SIMPLE TEST RUNNER")
    print("=" * 60)
    
    if not CLIENT_IMPORTED:
        print("ERROR: Could not import kalshi_client_wrapper module.")
        print("Make sure the module is in the same directory as this test file.")
        return False
    
    # Create test suite
    test_suite = unittest.TestSuite()
    
    # Add all test classes
    test_classes = [
        TestKalshiClientConfig,
        TestKalshiClient,
        TestKalshiClientAsyncOperations,
        TestConvenienceFunction,
        TestIntegrationScenarios
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # Print summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    
    if result.failures:
        print("\nFAILURES:")
        for test, traceback in result.failures:
            print(f"- {test}: {traceback}")
    
    if result.errors:
        print("\nERRORS:")
        for test, traceback in result.errors:
            print(f"- {test}: {traceback}")
    
    success = len(result.failures) == 0 and len(result.errors) == 0
    if success:
        print("\n✅ ALL TESTS PASSED!")
    else:
        print("\n❌ SOME TESTS FAILED!")
    
    return success


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
