"""
Test suite for PolymarketMessageProcessor with sample messages from the specification.
"""

import asyncio
import json
from unittest.mock import Mock, AsyncMock

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from polymarket_client.polymarket_message_processor import PolymarketMessageProcessor, PolymarketOrderbookState

# Sample messages from the specification
SAMPLE_BOOK_MESSAGE = {
    "event_type": "book",
    "asset_id": "65818619657568813474341868652308942079804919287380422192892211131408793125422",
    "market": "0xbd31dc8a20211944f6b70f31557f1001557b59905b7738480ca09bd4532f84af",
    "bids": [
        {"price": ".48", "size": "30"},
        {"price": ".49", "size": "20"},
        {"price": ".50", "size": "15"}
    ],
    "asks": [
        {"price": ".52", "size": "25"},
        {"price": ".53", "size": "60"},
        {"price": ".54", "size": "10"}
    ],
    "timestamp": "123456789000",
    "hash": "0x0...."
}

SAMPLE_PRICE_CHANGE_MESSAGE = {
    "asset_id": "71321045679252212594626385532706912750332728571942532289631379312455583992563",
    "changes": [
        {
            "price": "0.4",
            "side": "SELL",
            "size": "3300"
        },
        {
            "price": "0.5",
            "side": "SELL",
            "size": "3400"
        }
    ],
    "event_type": "price_change",
    "market": "0x5f65177b394277fd294cd75650044e32ba009a95022d88a0c1d565897d72f8f1",
    "timestamp": "1729084877448",
    "hash": "3cd4d61e042c81560c9037ece0c61f3b1a8fbbdd"
}

SAMPLE_TICK_SIZE_CHANGE_MESSAGE = {
    "event_type": "tick_size_change",
    "asset_id": "65818619657568813474341868652308942079804919287380422192892211131408793125422",
    "market": "0xbd31dc8a20211944f6b70f31557f1001557b59905b7738480ca09bd4532f84af",
    "old_tick_size": "0.01",
    "new_tick_size": "0.001",
    "timestamp": "100000000"
}

SAMPLE_LAST_TRADE_PRICE_MESSAGE = {
    "event_type": "last_trade_price",
    "asset_id": "65818619657568813474341868652308942079804919287380422192892211131408793125422",
    "price": "0.55",
    "timestamp": "123456789000"
}

class TestPolymarketMessageProcessor:
    """Test the PolymarketMessageProcessor with sample messages."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.processor = PolymarketMessageProcessor()
        self.error_callback = Mock()
        self.orderbook_callback = Mock()
        
        # Set up callbacks
        self.processor.set_error_callback(self.error_callback)
        self.processor.set_orderbook_update_callback(self.orderbook_callback)
    
    async def test_book_message_processing(self):
        """Test processing of book (full orderbook snapshot) messages."""
        # Convert to JSON string as the processor expects
        raw_message = json.dumps(SAMPLE_BOOK_MESSAGE)
        metadata = {"platform": "polymarket", "subscription_id": "test"}
        
        # Process the message
        await self.processor.handle_message(raw_message, metadata)
        
        # Check that orderbook was created
        asset_id = SAMPLE_BOOK_MESSAGE["asset_id"]
        orderbook = self.processor.get_orderbook(asset_id)
        
        assert orderbook is not None
        assert orderbook.asset_id == asset_id
        assert orderbook.market == SAMPLE_BOOK_MESSAGE["market"]
        
        # Check bids were loaded correctly
        assert len(orderbook.bids) == 3
        assert ".48" in orderbook.bids
        assert ".49" in orderbook.bids
        assert ".50" in orderbook.bids
        
        # Check asks were loaded correctly
        assert len(orderbook.asks) == 3
        assert ".52" in orderbook.asks
        assert ".53" in orderbook.asks
        assert ".54" in orderbook.asks
        
        # Check best bid/ask
        best_bid = orderbook.get_best_bid()
        best_ask = orderbook.get_best_ask()
        
        assert best_bid is not None
        assert best_bid.price == ".50"  # Highest bid
        assert best_bid.size == "15"
        
        assert best_ask is not None
        assert best_ask.price == ".52"  # Lowest ask
        assert best_ask.size == "25"
        
        # Check callback was called
        assert self.orderbook_callback.called
    
    async def test_price_change_message_processing(self):
        """Test processing of price_change messages."""
        # First, set up orderbook with a book message
        book_message = {
            "event_type": "book",
            "asset_id": SAMPLE_PRICE_CHANGE_MESSAGE["asset_id"],
            "market": SAMPLE_PRICE_CHANGE_MESSAGE["market"],
            "bids": [{"price": "0.3", "size": "100"}],
            "asks": [{"price": "0.6", "size": "200"}],
            "timestamp": "123456789000"
        }
        
        await self.processor.handle_message(json.dumps(book_message), {})
        
        # Now process the price change
        raw_message = json.dumps(SAMPLE_PRICE_CHANGE_MESSAGE)
        metadata = {"platform": "polymarket", "subscription_id": "test"}
        
        await self.processor.handle_message(raw_message, metadata)
        
        # Check that price changes were applied
        asset_id = SAMPLE_PRICE_CHANGE_MESSAGE["asset_id"]
        orderbook = self.processor.get_orderbook(asset_id)
        
        assert orderbook is not None
        
        # Check that SELL side changes were applied to asks
        assert "0.4" in orderbook.asks
        assert orderbook.asks["0.4"].size == "3300"
        assert "0.5" in orderbook.asks
        assert orderbook.asks["0.5"].size == "3400"
        
        # Original ask should still be there
        assert "0.6" in orderbook.asks
    
    async def test_tick_size_change_message_processing(self):
        """Test processing of tick_size_change messages."""
        # First, set up orderbook with a book message
        book_message = {
            "event_type": "book",
            "asset_id": SAMPLE_TICK_SIZE_CHANGE_MESSAGE["asset_id"],
            "market": SAMPLE_TICK_SIZE_CHANGE_MESSAGE["market"],
            "bids": [{"price": "0.5", "size": "100"}],
            "asks": [{"price": "0.6", "size": "200"}],
            "timestamp": "123456789000"
        }
        
        await self.processor.handle_message(json.dumps(book_message), {})
        
        # Now process the tick size change
        raw_message = json.dumps(SAMPLE_TICK_SIZE_CHANGE_MESSAGE)
        metadata = {"platform": "polymarket", "subscription_id": "test"}
        
        await self.processor.handle_message(raw_message, metadata)
        
        # Check that temporary levels were created
        asset_id = SAMPLE_TICK_SIZE_CHANGE_MESSAGE["asset_id"]
        orderbook = self.processor.get_orderbook(asset_id)
        
        assert orderbook is not None
        
        # Check that temporary levels with size=1 were added at new tick size
        new_tick_size = SAMPLE_TICK_SIZE_CHANGE_MESSAGE["new_tick_size"]
        assert new_tick_size in orderbook.bids
        assert orderbook.bids[new_tick_size].size == "1"
        assert new_tick_size in orderbook.asks
        assert orderbook.asks[new_tick_size].size == "1"
    
    async def test_last_trade_price_message_processing(self):
        """Test processing of last_trade_price messages (stub implementation)."""
        raw_message = json.dumps(SAMPLE_LAST_TRADE_PRICE_MESSAGE)
        metadata = {"platform": "polymarket", "subscription_id": "test"}
        
        # Should not raise an error
        await self.processor.handle_message(raw_message, metadata)
        
        # Since it's a stub, just check it doesn't crash
        assert True
    
    async def test_market_summary_calculation(self):
        """Test calculation of market summaries."""
        # Set up orderbook
        raw_message = json.dumps(SAMPLE_BOOK_MESSAGE)
        await self.processor.handle_message(raw_message, {})
        
        asset_id = SAMPLE_BOOK_MESSAGE["asset_id"]
        summary = self.processor.get_market_summary(asset_id)
        
        assert summary is not None
        assert summary["bid"] == 0.50  # Best bid
        assert summary["ask"] == 0.52  # Best ask
        assert summary["volume"] == 160.0  # Total volume (30+20+15+25+60+10)
    
    async def test_error_handling_with_missing_fields(self):
        """Test error handling when using .get() for missing fields."""
        # Message with missing fields
        incomplete_message = {
            "event_type": "book",
            "asset_id": "test_asset_id"
            # Missing bids, asks, market, etc.
        }
        
        raw_message = json.dumps(incomplete_message)
        
        # Should not crash
        await self.processor.handle_message(raw_message, {})
        
        # Should create orderbook with empty bids/asks
        orderbook = self.processor.get_orderbook("test_asset_id")
        assert orderbook is not None
        assert len(orderbook.bids) == 0
        assert len(orderbook.asks) == 0
    
    async def test_invalid_json_handling(self):
        """Test handling of invalid JSON messages."""
        # Create fresh processor for this test
        fresh_processor = PolymarketMessageProcessor()
        
        invalid_json = '{"invalid": json}'
        
        # Should not crash
        await fresh_processor.handle_message(invalid_json, {})
        
        # Should not create any orderbooks
        assert len(fresh_processor.get_all_orderbooks()) == 0
    
    def test_processor_stats(self):
        """Test processor statistics."""
        stats = self.processor.get_stats()
        
        assert "active_assets" in stats
        assert "asset_ids" in stats
        assert "processor_status" in stats
        assert stats["processor_status"] == "running"


if __name__ == "__main__":
    # Run basic tests
    async def run_tests():
        test = TestPolymarketMessageProcessor()
        test.setup_method()
        
        print("Testing book message processing...")
        await test.test_book_message_processing()
        print("✓ Book message test passed")
        
        print("Testing price change message processing...")
        await test.test_price_change_message_processing()
        print("✓ Price change message test passed")
        
        print("Testing tick size change message processing...")
        await test.test_tick_size_change_message_processing()
        print("✓ Tick size change message test passed")
        
        print("Testing last trade price message processing...")
        await test.test_last_trade_price_message_processing()
        print("✓ Last trade price message test passed")
        
        print("Testing market summary calculation...")
        await test.test_market_summary_calculation()
        print("✓ Market summary test passed")
        
        print("Testing error handling...")
        await test.test_error_handling_with_missing_fields()
        print("✓ Error handling test passed")
        
        print("Testing invalid JSON handling...")
        await test.test_invalid_json_handling()
        print("✓ Invalid JSON test passed")
        
        print("Testing processor stats...")
        test.test_processor_stats()
        print("✓ Processor stats test passed")
        
        print("\n🎉 All tests passed!")
    
    asyncio.run(run_tests())