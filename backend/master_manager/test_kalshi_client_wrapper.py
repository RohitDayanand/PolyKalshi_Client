"""
Comprehensive test suite for Kalshi Client Wrapper.

This module provides thorough testing for the KalshiClient and KalshiClientConfig
classes, including configuration, authentication, connection management, callbacks,
and async operations.

Run with: python -m pytest test_kalshi_client_wrapper.py -v
"""

try:
    import pytest
    PYTEST_AVAILABLE = True
except ImportError:
    PYTEST_AVAILABLE = False
    # Mock pytest decorators for when pytest is not available
    class MockPytest:
        @staticmethod
        def fixture(*args, **kwargs):
            def decorator(func):
                return func
            return decorator
        
        @staticmethod
        def mark(*args, **kwargs):
            class Mark:
                @staticmethod
                def asyncio(*args, **kwargs):
                    def decorator(func):
                        return func
                    return decorator
            return Mark()
        
        @staticmethod
        def raises(*args, **kwargs):
            def decorator(func):
                return func
            return decorator
    
    pytest = MockPytest()

import asyncio
import json
import time
import threading
import unittest
from unittest.mock import Mock, patch, AsyncMock, MagicMock, mock_open
from datetime import datetime, timedelta
import os

try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    # Mock websockets for testing
    class MockWebsockets:
        class ConnectionClosed(Exception):
            def __init__(self, code, reason):
                self.code = code
                self.reason = reason
                super().__init__(f"{code}: {reason}")
    websockets = MockWebsockets()

try:
    import base64
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

# Import the modules under test
from kalshi_client_wrapper import (
    KalshiClient, 
    KalshiClientConfig, 
    Environment,
    create_kalshi_client
)


class TestKalshiClientConfig:
    """Test suite for KalshiClientConfig class."""
    
    def test_config_initialization_with_defaults(self):
        """Test config initialization with default values."""
        with patch('kalshi_client_wrapper.KalshiClientConfig._load_private_key', return_value=Mock()):
            config = KalshiClientConfig(ticker="TEST-001")
            
            assert config.ticker == "TEST-001"
            assert config.channel == "orderbook_delta"
            assert config.environment == Environment.DEMO
            assert config.ping_interval == 30
            assert config.reconnect_interval == 5
            assert config.log_level == "INFO"
    
    def test_config_initialization_with_custom_values(self):
        """Test config initialization with custom values."""
        with patch('kalshi_client_wrapper.KalshiClientConfig._load_private_key', return_value=Mock()):
            config = KalshiClientConfig(
                ticker="CUSTOM-001",
                channel="trades",
                environment=Environment.PROD,
                ping_interval=60,
                reconnect_interval=10,
                log_level="DEBUG"
            )
            
            assert config.ticker == "CUSTOM-001"
            assert config.channel == "trades"
            assert config.environment == Environment.PROD
            assert config.ping_interval == 60
            assert config.reconnect_interval == 10
            assert config.log_level == "DEBUG"
    
    @patch.dict('os.environ', {'PROD_KEYID': 'test_key_id'})
    def test_config_key_id_from_environment(self):
        """Test key_id loading from environment variables."""
        with patch('kalshi_client_wrapper.KalshiClientConfig._load_private_key', return_value=Mock()):
            config = KalshiClientConfig(ticker="TEST-001")
            assert config.key_id == 'test_key_id'
    
    def test_config_explicit_key_id_overrides_environment(self):
        """Test that explicit key_id overrides environment variable."""
        with patch.dict('os.environ', {'PROD_KEYID': 'env_key'}):
            with patch('kalshi_client_wrapper.KalshiClientConfig._load_private_key', return_value=Mock()):
                config = KalshiClientConfig(ticker="TEST-001", key_id="explicit_key")
                assert config.key_id == "explicit_key"
    
    @patch("builtins.open", mock_open(read_data=b"fake_private_key_data"))
    def test_private_key_loading_success(self):
        """Test successful private key loading."""
        with patch("kalshi_client_wrapper.serialization.load_pem_private_key") as mock_load_key:
            mock_private_key = Mock()
            mock_load_key.return_value = mock_private_key
            
            config = KalshiClientConfig(ticker="TEST-001")
            
            mock_load_key.assert_called_once()
            assert config.private_key == mock_private_key
    
    @patch("builtins.open", side_effect=FileNotFoundError())
    def test_private_key_loading_file_not_found(self, mock_open):
        """Test private key loading when file is not found."""
        try:
            KalshiClientConfig(ticker="TEST-001")
            assert False, "Should have raised FileNotFoundError"
        except FileNotFoundError:
            pass  # Expected
    
    @patch("builtins.open", mock_open(read_data=b"invalid_key_data"))
    def test_private_key_loading_invalid_format(self):
        """Test private key loading with invalid key format."""
        with patch("kalshi_client_wrapper.serialization.load_pem_private_key", side_effect=Exception("Invalid key format")):
            try:
                KalshiClientConfig(ticker="TEST-001")
                assert False, "Should have raised Exception"
            except Exception as e:
                assert "Invalid key format" in str(e)


class TestKalshiClient:
    """Test suite for KalshiClient class."""
    
    def create_mock_config(self):
        """Create a mock config for testing."""
        config = Mock(spec=KalshiClientConfig)
        config.ticker = "TEST-001"
        config.channel = "orderbook_delta"
        config.environment = Environment.DEMO
        config.ping_interval = 30
        config.reconnect_interval = 5
        config.key_id = "test_key_id"
        config.private_key = Mock()
        return config
    
    def test_client_initialization(self):
        """Test client initialization with proper state."""
        mock_config = self.create_mock_config()
        client = KalshiClient(mock_config)
        
        assert client.config == mock_config
        assert client.ticker == "TEST-001"
        assert client.channel == "orderbook_delta"
        assert client.websocket is None
        assert client.is_connected is False
        assert client.should_reconnect is True
        assert client.message_id == 1
        assert isinstance(client.last_message_time, datetime)
        assert client._threads == []
        assert client._loop is None
        assert client.on_message_callback is None
        assert client.on_connection_callback is None
        assert client.on_error_callback is None
    
    def test_set_callbacks(self):
        """Test setting callback functions."""
        mock_config = self.create_mock_config()
        client = KalshiClient(mock_config)
        
        message_callback = Mock()
        connection_callback = Mock()
        error_callback = Mock()
        
        client.set_message_callback(message_callback)
        client.set_connection_callback(connection_callback)
        client.set_error_callback(error_callback)
        
        assert client.on_message_callback == message_callback
        assert client.on_connection_callback == connection_callback
        assert client.on_error_callback == error_callback
    
    def test_get_ws_url_demo(self):
        """Test WebSocket URL generation for demo environment."""
        mock_config = self.create_mock_config()
        mock_config.environment = Environment.DEMO
        client = KalshiClient(mock_config)
        
        url = client._get_ws_url()
        assert url == "wss://demo-api.kalshi.co/trade-api/ws/v2"
    
    def test_get_ws_url_prod(self):
        """Test WebSocket URL generation for production environment."""
        mock_config = self.create_mock_config()
        mock_config.environment = Environment.PROD
        client = KalshiClient(mock_config)
        
        url = client._get_ws_url()
        assert url == "wss://api.elections.kalshi.com/trade-api/ws/v2"
    
    def test_get_ws_url_invalid_environment(self):
        """Test WebSocket URL generation with invalid environment."""
        mock_config = self.create_mock_config()
        mock_config.environment = "invalid"
        client = KalshiClient(mock_config)
        
        try:
            client._get_ws_url()
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "Invalid environment" in str(e)
    
    @patch('time.time', return_value=1609459200.0)  # Fixed timestamp
    def test_create_auth_headers(self, mock_time):
        """Test authentication header generation."""
        mock_config = self.create_mock_config()
        client = KalshiClient(mock_config)
        
        # Mock the sign method
        client._sign_pss_text = Mock(return_value="mock_signature")
        client.config.key_id = "test_key_id"
        
        headers = client._create_auth_headers("GET", "/trade-api/ws/v2")
        
        assert headers["KALSHI-ACCESS-KEY"] == "test_key_id"
        assert headers["KALSHI-ACCESS-SIGNATURE"] == "mock_signature"
        assert headers["KALSHI-ACCESS-TIMESTAMP"] == "1609459200000"
        
        # Verify sign method was called with correct message
        expected_message = "1609459200000GET/trade-api/ws/v2"
        client._sign_pss_text.assert_called_once_with(expected_message)


class TestKalshiClientAsyncOperations:
    """Test suite for async operations in KalshiClient."""
    
    def create_mock_config(self):
        """Create a mock config for async testing."""
        config = Mock(spec=KalshiClientConfig)
        config.ticker = "TEST-001"
        config.channel = "orderbook_delta"
        config.environment = Environment.DEMO
        config.reconnect_interval = 1  # Short interval for testing
        config.key_id = "test_key_id"
        config.private_key = Mock()
        return config
    
    def test_handle_websocket_message_json(self):
        """Test handling of JSON WebSocket messages."""
        mock_config = self.create_mock_config()
        client = KalshiClient(mock_config)
        
        callback = Mock()
        client.set_message_callback(callback)
        
        test_message = '{"type": "data", "ticker": "TEST-001", "data": {"price": 50}}'
        
        # Run async function in sync context for testing
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(client._handle_websocket_message(test_message))
        finally:
            loop.close()
        
        callback.assert_called_once_with({
            "type": "data",
            "ticker": "TEST-001", 
            "data": {"price": 50}
        })
    
    def test_handle_websocket_message_pong(self):
        """Test handling of PONG messages."""
        mock_config = self.create_mock_config()
        client = KalshiClient(mock_config)
        
        callback = Mock()
        client.set_message_callback(callback)
        
        # Run async function in sync context for testing
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(client._handle_websocket_message("PONG"))
        finally:
            loop.close()
        
        # PONG messages should not trigger callback
        callback.assert_not_called()
    
    def test_handle_websocket_message_ping(self):
        """Test handling of ping messages with pong response."""
        mock_config = self.create_mock_config()
        client = KalshiClient(mock_config)
        
        client.websocket = AsyncMock()
        ping_message = '{"type": "ping"}'
        
        # Run async function in sync context for testing
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(client._handle_websocket_message(ping_message))
        finally:
            loop.close()
        
        # Verify pong response was sent
        expected_pong = json.dumps({"type": "pong"})
        client.websocket.send.assert_called_once_with(expected_pong)
    
    def test_handle_websocket_message_invalid_json(self):
        """Test handling of invalid JSON messages."""
        mock_config = self.create_mock_config()
        client = KalshiClient(mock_config)
        
        error_callback = Mock()
        client.set_error_callback(error_callback)
        
        # Run async function in sync context for testing
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(client._handle_websocket_message("invalid json"))
        finally:
            loop.close()
        
        error_callback.assert_called_once()
        error = error_callback.call_args[0][0]
        assert isinstance(error, Exception)
        assert "Invalid JSON message" in str(error)
    
    def test_subscribe_to_channel(self):
        """Test channel subscription."""
        mock_config = self.create_mock_config()
        client = KalshiClient(mock_config)
        
        client.websocket = AsyncMock()
        
        # Run async function in sync context for testing
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(client._subscribe_to_channel())
        finally:
            loop.close()
        
        # Verify subscription message was sent
        expected_message = {
            "id": 1,
            "cmd": "subscribe",
            "params": {
                "channels": "orderbook_delta",
                "market_tickers": ["TEST-001"]
            }
        }
        client.websocket.send.assert_called_once_with(json.dumps(expected_message))


class TestKalshiClientConnectionManagement:
    """Test suite for connection management in KalshiClient."""
    
    def create_mock_config(self):
        """Create a mock config for connection testing."""
        config = Mock(spec=KalshiClientConfig)
        config.ticker = "TEST-001"
        config.channel = "orderbook_delta"
        config.environment = Environment.DEMO
        config.ping_interval = 30
        config.reconnect_interval = 5
        config.key_id = "test_key_id"
        config.private_key = Mock()
        return config
    
    def test_connect_missing_key_id(self):
        """Test connect fails when key_id is missing."""
        mock_config = self.create_mock_config()
        mock_config.key_id = None
        client = KalshiClient(mock_config)
        
        result = client.connect()
        assert result is False
    
    def test_connect_missing_private_key(self):
        """Test connect fails when private_key is missing."""
        mock_config = self.create_mock_config()
        mock_config.private_key = None
        client = KalshiClient(mock_config)
        
        result = client.connect()
        assert result is False
    
    @patch('threading.Thread')
    @patch('time.sleep')
    def test_connect_success(self, mock_sleep, mock_thread):
        """Test successful connection initialization."""
        mock_config = self.create_mock_config()
        client = KalshiClient(mock_config)
        
        mock_thread_instance = Mock()
        mock_thread.return_value = mock_thread_instance
        
        result = client.connect()
        
        # Verify threads were started
        assert mock_thread.call_count == 2  # Connection thread and monitor thread
        assert mock_thread_instance.start.call_count == 2
        assert result is True
    
    def test_disconnect(self):
        """Test client disconnection and cleanup."""
        mock_config = self.create_mock_config()
        client = KalshiClient(mock_config)
        
        # Setup client state
        client.websocket = AsyncMock()
        client.is_connected = True
        client.should_reconnect = True
        client._loop = Mock()
        client._loop.is_closed.return_value = False
        
        # Mock threads
        mock_thread = Mock()
        mock_thread.is_alive.return_value = True
        client._threads = [mock_thread]
        
        connection_callback = Mock()
        client.set_connection_callback(connection_callback)
        
        with patch('asyncio.run_coroutine_threadsafe') as mock_run_coro:
            mock_future = Mock()
            mock_run_coro.return_value = mock_future
            
            client.disconnect()
        
        # Verify state changes
        assert client.should_reconnect is False
        assert client.is_connected is False
        
        # Verify cleanup
        mock_thread.join.assert_called_once_with(timeout=2.0)
        connection_callback.assert_called_once_with(False)
    
    def test_is_running(self):
        """Test is_running status check."""
        mock_config = self.create_mock_config()
        client = KalshiClient(mock_config)
        
        # Test when not connected
        client.is_connected = False
        client.should_reconnect = True
        assert client.is_running() is False
        
        # Test when connected but shouldn't reconnect
        client.is_connected = True
        client.should_reconnect = False
        assert client.is_running() is False
        
        # Test when fully running
        client.is_connected = True
        client.should_reconnect = True
        assert client.is_running() is True
    
    def test_get_status(self):
        """Test status information retrieval."""
        mock_config = self.create_mock_config()
        client = KalshiClient(mock_config)
        
        client.is_connected = True
        client.should_reconnect = True
        client.last_message_time = datetime(2023, 1, 1, 12, 0, 0)
        
        # Mock active thread
        mock_thread = Mock()
        mock_thread.is_alive.return_value = True
        client._threads = [mock_thread]
        
        status = client.get_status()
        
        expected_status = {
            "connected": True,
            "should_reconnect": True,
            "ticker": "TEST-001",
            "channel": "orderbook_delta",
            "last_message_time": "2023-01-01T12:00:00",
            "environment": "demo",
            "threads_active": 1
        }
        
        assert status == expected_status


class TestConvenienceFunction:
    """Test suite for convenience functions."""
    
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
        assert result == mock_client
    
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
        
        assert result == mock_client


# Unittest compatibility layer for running without pytest
class UnittestTestRunner(unittest.TestCase):
    """Unittest runner for when pytest is not available."""
    
    def test_all_kalshi_client_tests(self):
        """Run all tests using unittest framework."""
        # Config tests
        config_tests = TestKalshiClientConfig()
        config_tests.test_config_initialization_with_defaults()
        config_tests.test_config_initialization_with_custom_values()
        
        # Client tests
        client_tests = TestKalshiClient()
        client_tests.test_client_initialization()
        client_tests.test_set_callbacks()
        client_tests.test_get_ws_url_demo()
        client_tests.test_get_ws_url_prod()
        client_tests.test_get_ws_url_invalid_environment()
        
        # Async operation tests
        async_tests = TestKalshiClientAsyncOperations()
        async_tests.test_handle_websocket_message_json()
        async_tests.test_handle_websocket_message_pong()
        async_tests.test_handle_websocket_message_invalid_json()
        async_tests.test_subscribe_to_channel()
        
        # Connection management tests
        conn_tests = TestKalshiClientConnectionManagement()
        conn_tests.test_connect_missing_key_id()
        conn_tests.test_connect_missing_private_key()
        conn_tests.test_disconnect()
        conn_tests.test_is_running()
        conn_tests.test_get_status()
        
        print("All Kalshi client tests passed!")


if __name__ == "__main__":
    if PYTEST_AVAILABLE:
        # Run with pytest if available
        import sys
        pytest.main([__file__, "-v"])
    else:
        # Fall back to unittest
        print("Running tests with unittest (pytest not available)")
        unittest.main()
            with patch('builtins.open'):
                self.config = KalshiClientConfig(
                    ticker="TEST-TICKER",
                    key_id="test_key_123"
                )
                self.client = KalshiClient(self.config)
    
    def test_ws_url_generation_demo(self):
        """Test WebSocket URL generation for demo environment."""
        self.config.environment = Environment.DEMO
        url = self.client._get_ws_url()
        assert url == "wss://demo-api.kalshi.co/trade-api/ws/v2"
    
    def test_ws_url_generation_prod(self):
        """Test WebSocket URL generation for production environment."""
        self.config.environment = Environment.PROD
        url = self.client._get_ws_url()
        assert url == "wss://api.elections.kalshi.com/trade-api/ws/v2"
    
    @patch('time.time', return_value=1234567890.123)
    @patch.object(KalshiClient, '_sign_pss_text', return_value='mock_signature')
    def test_auth_headers_generation(self, mock_sign, mock_time):
        """Test authentication headers generation."""
        headers = self.client._create_auth_headers("GET", "/trade-api/ws/v2")
        
        expected_timestamp = "1234567890123"
        assert headers["KALSHI-ACCESS-KEY"] == "test_key_123"
        assert headers["KALSHI-ACCESS-TIMESTAMP"] == expected_timestamp
        assert headers["KALSHI-ACCESS-SIGNATURE"] == "mock_signature"
        
        # Verify signing was called with correct message
        mock_sign.assert_called_once_with(expected_timestamp + "GET" + "/trade-api/ws/v2")
    
    def test_sign_pss_text(self):
        """Test PSS signing functionality."""
        mock_signature = b'mock_binary_signature'
        self.mock_key.sign.return_value = mock_signature
        
        result = self.client._sign_pss_text("test_message")
        
        # Should return base64 encoded signature
        import base64
        expected = base64.b64encode(mock_signature).decode('utf-8')
        assert result == expected


class TestKalshiClientCallbacks:
    """Test callback functionality."""
    
    @patch('builtins.open')
    @patch('kalshi_client_wrapper.serialization.load_pem_private_key')
    def setup_method(self):
        """Set up test client."""
        with patch('kalshi_client_wrapper.serialization.load_pem_private_key'):
            with patch('builtins.open'):
                self.config = KalshiClientConfig(ticker="TEST")
                self.client = KalshiClient(self.config)
    
    def test_set_callbacks(self):
        """Test setting callbacks."""
        message_cb = Mock()
        connection_cb = Mock()
        error_cb = Mock()
        
        self.client.set_message_callback(message_cb)
        self.client.set_connection_callback(connection_cb)
        self.client.set_error_callback(error_cb)
        
        assert self.client.on_message_callback == message_cb
        assert self.client.on_connection_callback == connection_cb
        assert self.client.on_error_callback == error_cb
    
    @pytest.mark.asyncio
    async def test_message_handling_json(self):
        """Test handling of JSON messages."""
        message_cb = Mock()
        self.client.set_message_callback(message_cb)
        
        test_message = '{"type": "test", "data": "value"}'
        await self.client._handle_websocket_message(test_message)
        
        message_cb.assert_called_once_with({"type": "test", "data": "value"})
    
    @pytest.mark.asyncio
    async def test_message_handling_pong(self):
        """Test handling of PONG messages."""
        message_cb = Mock()
        self.client.set_message_callback(message_cb)
        
        await self.client._handle_websocket_message("PONG")
        
        # PONG messages should not trigger user callback
        message_cb.assert_not_called()
        # But should update last message time
        assert isinstance(self.client.last_message_time, datetime)
    
    @pytest.mark.asyncio
    async def test_message_handling_ping_response(self):
        """Test handling of ping messages and sending pong response."""
        self.client.websocket = AsyncMock()
        
        ping_message = '{"type": "ping"}'
        await self.client._handle_websocket_message(ping_message)
        
        # Should send pong response
        self.client.websocket.send.assert_called_once_with('{"type": "pong"}')
    
    @pytest.mark.asyncio
    async def test_message_handling_invalid_json(self):
        """Test handling of invalid JSON messages."""
        error_cb = Mock()
        self.client.set_error_callback(error_cb)
        
        await self.client._handle_websocket_message("invalid json {")
        
        error_cb.assert_called_once()
        call_args = error_cb.call_args[0][0]
        assert "Invalid JSON message" in str(call_args)


class TestKalshiClientConnection:
    """Test connection lifecycle management."""
    
    @patch('builtins.open')
    @patch('kalshi_client_wrapper.serialization.load_pem_private_key')
    def setup_method(self):
        """Set up test client."""
        with patch('kalshi_client_wrapper.serialization.load_pem_private_key'):
            with patch('builtins.open'):
                self.config = KalshiClientConfig(
                    ticker="TEST",
                    key_id="test_key"
                )
                self.client = KalshiClient(self.config)
    
    def test_connect_validation_no_key_id(self):
        """Test connection validation fails without key ID."""
        self.config.key_id = None
        result = self.client.connect()
        assert result is False
    
    def test_connect_validation_no_private_key(self):
        """Test connection validation fails without private key."""
        self.config.private_key = None
        result = self.client.connect()
        assert result is False
    
    @patch.object(threading.Thread, 'start')
    def test_connect_starts_threads(self, mock_thread_start):
        """Test that connect starts necessary threads."""
        result = self.client.connect()
        
        # Should start async and monitor threads
        assert mock_thread_start.call_count == 2
        assert len(self.client._threads) == 2
        assert result is True
    
    def test_disconnect_cleanup(self):
        """Test disconnect cleanup."""
        # Set up some state
        self.client.should_reconnect = True
        self.client.is_connected = True
        
        mock_thread = Mock()
        mock_thread.is_alive.return_value = False
        self.client._threads = [mock_thread]
        
        connection_cb = Mock()
        self.client.set_connection_callback(connection_cb)
        
        self.client.disconnect()
        
        assert self.client.should_reconnect is False
        assert self.client.is_connected is False
        connection_cb.assert_called_once_with(False)
    
    def test_is_running(self):
        """Test is_running status check."""
        self.client.is_connected = True
        self.client.should_reconnect = True
        assert self.client.is_running() is True
        
        self.client.is_connected = False
        assert self.client.is_running() is False
        
        self.client.is_connected = True
        self.client.should_reconnect = False
        assert self.client.is_running() is False
    
    def test_get_status(self):
        """Test status information retrieval."""
        self.client.is_connected = True
        self.client.should_reconnect = True
        self.client.last_message_time = datetime(2023, 1, 1, 12, 0, 0)
        
        mock_thread = Mock()
        mock_thread.is_alive.return_value = True
        self.client._threads = [mock_thread]
        
        status = self.client.get_status()
        
        assert status["connected"] is True
        assert status["should_reconnect"] is True
        assert status["ticker"] == "TEST"
        assert status["channel"] == "orderbook_delta"
        assert status["environment"] == "demo"
        assert status["threads_active"] == 1
        assert "2023-01-01T12:00:00" in status["last_message_time"]


class TestKalshiClientWebSocketOperations:
    """Test WebSocket-specific operations."""
    
    @patch('builtins.open')
    @patch('kalshi_client_wrapper.serialization.load_pem_private_key')
    def setup_method(self):
        """Set up test client."""
        with patch('kalshi_client_wrapper.serialization.load_pem_private_key'):
            with patch('builtins.open'):
                self.config = KalshiClientConfig(ticker="TESTMARKET")
                self.client = KalshiClient(self.config)
    
    @pytest.mark.asyncio
    async def test_subscribe_to_channel(self):
        """Test channel subscription."""
        self.client.websocket = AsyncMock()
        self.client.ticker = "TESTMARKET"
        self.client.channel = "orderbook_delta"
        
        await self.client._subscribe_to_channel()
        
        # Verify subscription message was sent
        self.client.websocket.send.assert_called_once()
        sent_message = json.loads(self.client.websocket.send.call_args[0][0])
        
        assert sent_message["id"] == 1
        assert sent_message["cmd"] == "subscribe"
        assert sent_message["params"]["channels"] == "orderbook_delta"
        assert sent_message["params"]["market_tickers"] == ["TESTMARKET"]
    
    @pytest.mark.asyncio
    async def test_websocket_handler_normal_operation(self):
        """Test normal WebSocket message handling."""
        # Mock websocket that yields messages
        mock_websocket = AsyncMock()
        mock_websocket.__aiter__.return_value = [
            '{"type": "test1", "data": "value1"}',
            '{"type": "test2", "data": "value2"}'
        ]
        self.client.websocket = mock_websocket
        
        message_cb = Mock()
        self.client.set_message_callback(message_cb)
        
        # This would normally run forever, so we patch the handler
        with patch.object(self.client, '_handle_websocket_message') as mock_handler:
            await self.client._websocket_handler()
            
            # Should have called handler for each message
            assert mock_handler.call_count == 2
    
    @pytest.mark.asyncio 
    async def test_websocket_handler_connection_closed(self):
        """Test WebSocket handler when connection closes."""
        import websockets
        
        # Mock websocket that raises ConnectionClosed
        mock_websocket = AsyncMock()
        mock_websocket.__aiter__.side_effect = websockets.ConnectionClosed(1000, "Normal closure")
        self.client.websocket = mock_websocket
        
        connection_cb = Mock()
        self.client.set_connection_callback(connection_cb)
        
        await self.client._websocket_handler()
        
        assert self.client.is_connected is False
        connection_cb.assert_called_once_with(False)


class TestKalshiClientAsyncConnect:
    """Test async connection logic."""
    
    @patch('builtins.open')
    @patch('kalshi_client_wrapper.serialization.load_pem_private_key')
    def setup_method(self):
        """Set up test client."""
        with patch('kalshi_client_wrapper.serialization.load_pem_private_key'):
            with patch('builtins.open'):
                self.config = KalshiClientConfig(
                    ticker="TEST",
                    key_id="test_key"
                )
                self.client = KalshiClient(self.config)
    
    @pytest.mark.asyncio
    @patch('kalshi_client_wrapper.websockets.connect')
    async def test_async_connect_success(self, mock_websockets_connect):
        """Test successful async connection."""
        # Mock successful WebSocket connection
        mock_websocket = AsyncMock()
        mock_websockets_connect.return_value.__aenter__.return_value = mock_websocket
        
        connection_cb = Mock()
        self.client.set_connection_callback(connection_cb)
        
        # Mock the handler to avoid infinite loop
        with patch.object(self.client, '_websocket_handler'):
            with patch.object(self.client, '_subscribe_to_channel'):
                result = await self.client._async_connect()
        
        assert result is True
        assert self.client.is_connected is True
        connection_cb.assert_called_once_with(True)
    
    @pytest.mark.asyncio
    @patch('kalshi_client_wrapper.websockets.connect')
    async def test_async_connect_with_retries(self, mock_websockets_connect):
        """Test async connection with retry logic."""
        import websockets
        
        # First attempt fails, second succeeds
        mock_websocket = AsyncMock()
        mock_websockets_connect.side_effect = [
            websockets.ConnectionClosed(1006, "Connection lost"),
            AsyncMock().__aenter__.return_value  # Second attempt context manager
        ]
        
        with patch.object(self.client, '_websocket_handler'):
            with patch.object(self.client, '_subscribe_to_channel'):
                with patch('asyncio.sleep'):  # Speed up test
                    result = await self.client._async_connect()
        
        # Should have tried twice
        assert mock_websockets_connect.call_count == 2


class TestConvenienceFunction:
    """Test the convenience function."""
    
    @patch('kalshi_client_wrapper.KalshiClient')
    @patch('kalshi_client_wrapper.KalshiClientConfig')
    def test_create_kalshi_client(self, mock_config_class, mock_client_class):
        """Test the create_kalshi_client convenience function."""
        mock_config = Mock()
        mock_client = Mock()
        mock_config_class.return_value = mock_config
        mock_client_class.return_value = mock_client
        
        result = create_kalshi_client(
            ticker="TEST",
            channel="ticker_v2",
            environment=Environment.PROD,
            ping_interval=60,
            log_level="DEBUG"
        )
        
        # Verify config was created with correct parameters
        mock_config_class.assert_called_once_with(
            ticker="TEST",
            channel="ticker_v2",
            environment=Environment.PROD,
            ping_interval=60,
            log_level="DEBUG"
        )
        
        # Verify client was created with config
        mock_client_class.assert_called_once_with(mock_config)
        assert result == mock_client


class TestIntegration:
    """Integration tests that test multiple components together."""
    
    @patch('builtins.open')
    @patch('kalshi_client_wrapper.serialization.load_pem_private_key')
    def test_full_client_lifecycle_mock(self, mock_load_key, mock_open):
        """Test full client lifecycle with mocked dependencies."""
        mock_key = Mock()
        mock_load_key.return_value = mock_key
        
        # Create client
        client = create_kalshi_client(
            ticker="INTEGRATION-TEST",
            environment=Environment.DEMO,
            log_level="DEBUG"
        )
        
        # Set up callbacks
        messages_received = []
        connections = []
        errors = []
        
        def on_message(msg):
            messages_received.append(msg)
        
        def on_connection(connected):
            connections.append(connected)
        
        def on_error(error):
            errors.append(error)
        
        client.set_message_callback(on_message)
        client.set_connection_callback(on_connection)
        client.set_error_callback(on_error)
        
        # Test configuration
        assert client.ticker == "INTEGRATION-TEST"
        assert client.config.environment == Environment.DEMO
        
        # Test status when not connected
        status = client.get_status()
        assert status["connected"] is False
        assert status["ticker"] == "INTEGRATION-TEST"
        
        # Test disconnect when not connected (should be safe)
        client.disconnect()
        
        # Verify no errors occurred during setup
        assert len(errors) == 0


if __name__ == "__main__":
    # Run specific test classes or all tests
    import sys
    
    if len(sys.argv) > 1:
        test_class = sys.argv[1]
        pytest.main([f"-v", f"test_kalshi_client_wrapper.py::{test_class}"])
    else:
        pytest.main(["-v", "test_kalshi_client_wrapper.py"])
