"""
Simple unit test for arbitrage endpoint functionality

This test verifies that:
1. ArbitrageManager can handle settings updates
2. Settings validation works correctly
3. EventBus integration for arbitrage updates functions
"""

import unittest
import asyncio
import sys
import os
from unittest.mock import Mock, AsyncMock, patch

# Add parent directories to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from backend.master_manager.arbitrage_manager import ArbitrageSettings, ArbitrageManager
from backend.master_manager.events.event_bus import EventBus


class TestArbitrageSettings(unittest.TestCase):
    """Test ArbitrageSettings dataclass functionality."""
    
    def test_settings_validation_valid(self):
        """Test valid settings pass validation."""
        settings = ArbitrageSettings(min_spread_threshold=0.05, min_trade_size=10.0)
        errors = settings.validate()
        self.assertEqual(len(errors), 0)
    
    def test_settings_validation_invalid_spread(self):
        """Test invalid spread threshold fails validation."""
        # Negative spread
        settings = ArbitrageSettings(min_spread_threshold=-0.01, min_trade_size=10.0)
        errors = settings.validate()
        self.assertGreater(len(errors), 0)
        self.assertTrue(any("non-negative" in error for error in errors))
        
        # Spread > 1.0
        settings = ArbitrageSettings(min_spread_threshold=1.5, min_trade_size=10.0)
        errors = settings.validate()
        self.assertGreater(len(errors), 0)
        self.assertTrue(any("<= 1.0" in error for error in errors))
    
    def test_settings_validation_invalid_trade_size(self):
        """Test invalid trade size fails validation."""
        settings = ArbitrageSettings(min_spread_threshold=0.05, min_trade_size=-5.0)
        errors = settings.validate()
        self.assertGreater(len(errors), 0)
        self.assertTrue(any("non-negative" in error for error in errors))
    
    def test_settings_update_from_dict(self):
        """Test updating settings from dictionary."""
        settings = ArbitrageSettings(min_spread_threshold=0.05, min_trade_size=10.0)
        updated = settings.update_from_dict({'min_spread_threshold': 0.03})
        
        self.assertEqual(updated.min_spread_threshold, 0.03)
        self.assertEqual(updated.min_trade_size, 10.0)  # Unchanged
        
        # Original settings should be unchanged
        self.assertEqual(settings.min_spread_threshold, 0.05)


class TestArbitrageManagerSettings(unittest.IsolatedAsyncioTestCase):
    """Test ArbitrageManager settings handling."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.event_bus = Mock()
        self.event_bus.subscribe = Mock()
        self.event_bus.publish = AsyncMock()
        
        self.manager = ArbitrageManager(
            min_spread_threshold=0.05,
            min_trade_size=10.0,
            event_bus=self.event_bus
        )
    
    def test_initial_settings(self):
        """Test manager initializes with correct settings."""
        settings = self.manager.get_settings()
        self.assertEqual(settings['min_spread_threshold'], 0.05)
        self.assertEqual(settings['min_trade_size'], 10.0)
    
    async def test_settings_update_success(self):
        """Test successful settings update via EventBus."""
        # Mock event data
        event_data = {
            'settings': {'min_spread_threshold': 0.03},
            'source': 'test',
            'correlation_id': 'test-123'
        }
        
        # Get current settings before update
        old_settings = self.manager.get_settings()
        
        # Call the settings change handler
        await self.manager._handle_settings_changed(event_data)
        
        # Verify settings were updated
        new_settings = self.manager.get_settings()
        self.assertEqual(new_settings['min_spread_threshold'], 0.03)
        self.assertEqual(new_settings['min_trade_size'], 10.0)  # Unchanged
        
        # Verify success event was published
        self.event_bus.publish.assert_called_once()
        call_args = self.event_bus.publish.call_args
        self.assertEqual(call_args[0][0], 'arbitrage.settings_updated')
        self.assertEqual(call_args[0][1]['correlation_id'], 'test-123')
    
    async def test_settings_update_validation_error(self):
        """Test settings update with validation errors."""
        # Mock invalid event data
        event_data = {
            'settings': {'min_spread_threshold': -0.01},  # Invalid
            'source': 'test',
            'correlation_id': 'test-456'
        }
        
        # Get current settings before update
        old_settings = self.manager.get_settings()
        
        # Call the settings change handler
        await self.manager._handle_settings_changed(event_data)
        
        # Verify settings were NOT updated
        current_settings = self.manager.get_settings()
        self.assertEqual(current_settings, old_settings)
        
        # Verify error event was published
        self.event_bus.publish.assert_called_once()
        call_args = self.event_bus.publish.call_args
        self.assertEqual(call_args[0][0], 'arbitrage.settings_error')
        self.assertEqual(call_args[0][1]['correlation_id'], 'test-456')
        self.assertIsNotNone(call_args[0][1]['errors'])
    
    def test_add_remove_market_pair(self):
        """Test market pair lifecycle management."""
        # Add market pair
        self.manager.add_market_pair(
            "TEST-MARKET",
            "KALSHI-TICKER", 
            "poly-yes-123",
            "poly-no-456"
        )
        
        # Verify pair was added
        stats = self.manager.get_stats()
        self.assertEqual(stats['monitored_pairs'], 1)
        self.assertIn("TEST-MARKET", stats['market_pairs'])
        
        # Remove market pair
        self.manager.remove_market_pair("TEST-MARKET")
        
        # Verify pair was removed
        stats = self.manager.get_stats()
        self.assertEqual(stats['monitored_pairs'], 0)
        self.assertNotIn("TEST-MARKET", stats['market_pairs'])


class TestArbitrageUpdateFlow(unittest.IsolatedAsyncioTestCase):
    """Test that arbitrage updates flow through the system correctly."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.event_bus = Mock()
        self.event_bus.subscribe = Mock()
        self.event_bus.publish = AsyncMock()
        
        # Mock processors
        self.kalshi_processor = Mock()
        self.polymarket_processor = Mock()
        
        self.manager = ArbitrageManager(
            event_bus=self.event_bus,
            kalshi_processor=self.kalshi_processor,
            polymarket_processor=self.polymarket_processor
        )
        
        # Add a test market pair
        self.manager.add_market_pair(
            "TEST-PAIR",
            "KALSHI-TEST",
            "poly-yes-123", 
            "poly-no-456"
        )
    
    async def test_kalshi_update_triggers_arbitrage_check(self):
        """Test that Kalshi orderbook updates trigger arbitrage checks."""
        # Mock orderbook states
        self.kalshi_processor.get_orderbook.return_value = Mock(
            best_yes_bid=0.52, best_yes_ask=0.53,
            best_no_bid=0.47, best_no_ask=0.48
        )
        self.polymarket_processor.get_orderbook.return_value = Mock(
            best_yes_bid=0.49, best_yes_ask=0.50,
            best_no_bid=0.50, best_no_ask=0.51
        )
        
        # Mock event data for Kalshi update
        event_data = {
            'ticker': 'KALSHI-TEST',
            'platform': 'kalshi'
        }
        
        # Call the Kalshi update handler
        await self.manager._handle_kalshi_updated(event_data)
        
        # Verify that orderbook methods were called (indicating arbitrage check)
        self.kalshi_processor.get_orderbook.assert_called_with('KALSHI-TEST')
        # Check that polymarket get_orderbook was called for both assets
        calls = self.polymarket_processor.get_orderbook.call_args_list
        called_assets = [call[0][0] for call in calls]
        self.assertIn('poly-yes-123', called_assets)
        self.assertIn('poly-no-456', called_assets)
    
    async def test_polymarket_update_triggers_arbitrage_check(self):
        """Test that Polymarket orderbook updates trigger arbitrage checks."""
        # Mock orderbook states
        self.kalshi_processor.get_orderbook.return_value = Mock()
        self.polymarket_processor.get_orderbook.return_value = Mock()
        
        # Mock event data for Polymarket update
        event_data = {
            'asset_id': 'poly-yes-123',
            'platform': 'polymarket'
        }
        
        # Call the Polymarket update handler
        await self.manager._handle_polymarket_updated(event_data)
        
        # Verify that orderbook methods were called
        self.kalshi_processor.get_orderbook.assert_called_with('KALSHI-TEST')
        self.polymarket_processor.get_orderbook.assert_called()


if __name__ == '__main__':
    # Run the tests
    unittest.main(verbosity=2)