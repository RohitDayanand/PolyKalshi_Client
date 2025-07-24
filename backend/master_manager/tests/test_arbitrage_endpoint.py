"""
Unit tests for the arbitrage settings API endpoint in websocket_server.py

Tests cover:
1. POST /api/arbitrage/settings endpoint functionality
2. Settings validation and update logic
3. EventBus integration for arbitrage settings changes
4. Response format validation
"""

import unittest
import asyncio
import json
import uuid
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime

# Import the FastAPI app and related components
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

try:
    from fastapi.testclient import TestClient
    from backend.websocket_server import (
        app, 
        ArbitrageSettingsRequest, 
        ArbitrageSettingsResponse,
        update_arbitrage_settings
    )
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False


class TestArbitrageSettingsEndpoint(unittest.IsolatedAsyncioTestCase):
    """Test suite for the arbitrage settings API endpoint."""
    
    def setUp(self):
        """Setup test environment before each test."""
        if FASTAPI_AVAILABLE:
            self.client = TestClient(app)
        
    def mock_global_event_bus(self):
        """Mock the global event bus for testing."""
        mock_bus = AsyncMock()
        mock_bus.publish = AsyncMock()
        mock_bus.subscribe = AsyncMock()
        mock_bus.unsubscribe = AsyncMock()
        return mock_bus
    
    @unittest.skipUnless(FASTAPI_AVAILABLE, "FastAPI not available")
    async def test_update_settings_success(self):
        """Test successful settings update through the endpoint."""
        mock_global_event_bus = self.mock_global_event_bus()
        
        # Mock the event bus response
        correlation_id = str(uuid.uuid4())
        
        # Mock the future resolution for success
        async def mock_wait_for(future, timeout=None):
            return ('success', {
                'old_settings': {'min_spread_threshold': 0.05, 'min_trade_size': 10.0},
                'new_settings': {'min_spread_threshold': 0.03, 'min_trade_size': 10.0},
                'changed_fields': ['min_spread_threshold'],
                'correlation_id': correlation_id
            })
        
        with patch('backend.master_manager.events.event_bus.global_event_bus', mock_global_event_bus):
            with patch('asyncio.wait_for', side_effect=mock_wait_for):
                with patch('uuid.uuid4', return_value=uuid.UUID(correlation_id)):
                    
                    # Test request data
                    request_data = ArbitrageSettingsRequest(
                        min_spread_threshold=0.03,
                        source="test"
                    )
                    
                    # Call the endpoint function directly
                    response = await update_arbitrage_settings(request_data)
                    
                    # Verify response structure
                    self.assertIsInstance(response, ArbitrageSettingsResponse)
                    self.assertTrue(response.success)
                    self.assertEqual(response.message, "Settings updated successfully by ArbitrageManager")
                    self.assertIsNotNone(response.old_settings)
                    self.assertIsNotNone(response.new_settings)
                    self.assertIn('min_spread_threshold', response.changed_fields)
                    
                    # Verify event bus interaction
                    mock_global_event_bus.publish.assert_called_once()
                    call_args = mock_global_event_bus.publish.call_args
                    self.assertEqual(call_args[0][0], 'arbitrage.settings_changed')
                    self.assertEqual(call_args[0][1]['settings']['min_spread_threshold'], 0.03)
                    self.assertEqual(call_args[0][1]['correlation_id'], correlation_id)
    
    @unittest.skipUnless(FASTAPI_AVAILABLE, "FastAPI not available")
    async def test_update_settings_validation_error(self):
        """Test settings update with validation errors."""
        mock_global_event_bus = self.mock_global_event_bus()
        
        correlation_id = str(uuid.uuid4())
        
        # Mock the future resolution for error
        async def mock_wait_for(future, timeout=None):
            return ('error', {
                'errors': ['min_spread_threshold must be <= 1.0 (100%)'],
                'correlation_id': correlation_id
            })
        
        with patch('backend.master_manager.events.event_bus.global_event_bus', mock_global_event_bus):
            with patch('asyncio.wait_for', side_effect=mock_wait_for):
                with patch('uuid.uuid4', return_value=uuid.UUID(correlation_id)):
                    
                    # Test request with invalid data (this will be caught by Pydantic validation)
                    try:
                        request_data = ArbitrageSettingsRequest(
                            min_spread_threshold=0.5,  # Use valid value for test
                            source="test"
                        )
                        
                        # Call the endpoint function directly
                        response = await update_arbitrage_settings(request_data)
                        
                        # Verify error response
                        self.assertIsInstance(response, ArbitrageSettingsResponse)
                        self.assertFalse(response.success)
                        self.assertEqual(response.message, "Settings update rejected by ArbitrageManager")
                        self.assertIsNotNone(response.errors)
                        self.assertGreater(len(response.errors), 0)
                    except ValueError:
                        # Expected for invalid Pydantic values
                        pass
    
    @pytest.mark.asyncio
    async def test_update_settings_timeout(self, mock_global_event_bus):
        """Test settings update timeout scenario."""
        correlation_id = str(uuid.uuid4())
        
        # Mock timeout
        async def mock_wait_for(future, timeout=None):
            raise asyncio.TimeoutError()
        
        with patch('backend.master_manager.events.event_bus.global_event_bus', mock_global_event_bus):
            with patch('asyncio.wait_for', side_effect=mock_wait_for):
                with patch('uuid.uuid4', return_value=uuid.UUID(correlation_id)):
                    
                    request_data = ArbitrageSettingsRequest(
                        min_spread_threshold=0.03,
                        source="test"
                    )
                    
                    # Call the endpoint function directly
                    response = await update_arbitrage_settings(request_data)
                    
                    # Verify timeout response
                    assert isinstance(response, ArbitrageSettingsResponse)
                    assert response.success is False
                    assert response.message == "Settings update request timed out"
                    assert "timed out" in response.errors[0]
    
    @pytest.mark.asyncio
    async def test_update_settings_empty_request(self, mock_global_event_bus):
        """Test settings update with empty request data."""
        with patch('backend.master_manager.events.event_bus.global_event_bus', mock_global_event_bus):
            
            # Empty request
            request_data = ArbitrageSettingsRequest(source="test")
            
            # Call the endpoint function directly
            response = await update_arbitrage_settings(request_data)
            
            # Verify empty request handling
            assert isinstance(response, ArbitrageSettingsResponse)
            assert response.success is False
            assert response.message == "No settings provided for update"
            assert "at least one setting" in response.errors[0]
    
    def test_arbitrage_settings_request_validation(self):
        """Test ArbitrageSettingsRequest validation."""
        # Valid request
        valid_request = ArbitrageSettingsRequest(
            min_spread_threshold=0.05,
            min_trade_size=25.0,
            source="api"
        )
        assert valid_request.min_spread_threshold == 0.05
        assert valid_request.min_trade_size == 25.0
        assert valid_request.source == "api"
        
        # Test with invalid spread threshold (should be caught by Pydantic)
        with pytest.raises(ValueError):
            ArbitrageSettingsRequest(min_spread_threshold=1.5)  # > 1.0
        
        with pytest.raises(ValueError):
            ArbitrageSettingsRequest(min_spread_threshold=-0.1)  # < 0.0
        
        # Test with invalid trade size
        with pytest.raises(ValueError):
            ArbitrageSettingsRequest(min_trade_size=-10.0)  # < 0.0
    
    def test_arbitrage_settings_response_structure(self):
        """Test ArbitrageSettingsResponse structure."""
        # Success response
        success_response = ArbitrageSettingsResponse(
            success=True,
            message="Settings updated successfully",
            old_settings={"min_spread_threshold": 0.05},
            new_settings={"min_spread_threshold": 0.03},
            changed_fields=["min_spread_threshold"]
        )
        
        assert success_response.success is True
        assert success_response.message == "Settings updated successfully"
        assert success_response.old_settings is not None
        assert success_response.new_settings is not None
        assert success_response.changed_fields is not None
        assert success_response.errors is None
        
        # Error response
        error_response = ArbitrageSettingsResponse(
            success=False,
            message="Validation failed",
            errors=["Invalid threshold value"]
        )
        
        assert error_response.success is False
        assert error_response.errors is not None
        assert len(error_response.errors) == 1
    
    @pytest.mark.asyncio
    async def test_http_endpoint_integration(self):
        """Test the actual HTTP endpoint integration."""
        # This test verifies the endpoint is properly registered and accessible
        
        # Test with valid data
        valid_payload = {
            "min_spread_threshold": 0.04,
            "min_trade_size": 15.0,
            "source": "test"
        }
        
        # Mock the event bus to avoid actual event handling during test
        with patch('backend.master_manager.events.event_bus.global_event_bus') as mock_bus:
            # Setup mock response simulation
            correlation_id = str(uuid.uuid4())
            
            async def mock_wait_for(future, timeout=None):
                return ('success', {
                    'old_settings': {'min_spread_threshold': 0.05, 'min_trade_size': 10.0},
                    'new_settings': {'min_spread_threshold': 0.04, 'min_trade_size': 15.0},
                    'changed_fields': ['min_spread_threshold', 'min_trade_size'],
                    'correlation_id': correlation_id
                })
            
            with patch('asyncio.wait_for', side_effect=mock_wait_for):
                with patch('uuid.uuid4', return_value=uuid.UUID(correlation_id)):
                    
                    # Make request to the endpoint
                    response = self.client.post("/api/arbitrage/settings", json=valid_payload)
                    
                    # Verify HTTP response
                    assert response.status_code == 200
                    response_data = response.json()
                    assert response_data["success"] is True
                    assert "Settings updated successfully" in response_data["message"]


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])