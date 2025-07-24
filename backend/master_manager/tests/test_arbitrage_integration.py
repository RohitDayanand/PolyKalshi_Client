"""
Test integration of Kalshi fee calculator with arbitrage calculator.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import with proper module path
import arbitrage_calculator
import kalshi_client.models.orderbook_state as kalshi_orderbook
import polymarket_client.models.orderbook_state as poly_orderbook
import kalshi_client.models.orderbook_level as kalshi_level
import polymarket_client.models.orderbook_level as poly_level

# Now use the classes
ArbitrageCalculator = arbitrage_calculator.ArbitrageCalculator
KalshiOrderbookSnapshot = kalshi_orderbook.OrderbookSnapshot
PolymarketOrderbookSnapshot = poly_orderbook.PolymarketOrderbookSnapshot
KalshiOrderbookLevel = kalshi_level.OrderbookLevel
PolymarketOrderbookLevel = poly_level.OrderbookLevel

def create_mock_kalshi_snapshot(sid: int, yes_bid: int, no_bid: int) -> KalshiOrderbookSnapshot:
    """Create a mock Kalshi orderbook snapshot."""
    yes_levels = {yes_bid: KalshiOrderbookLevel(yes_bid, 100.0, 100)}
    no_levels = {no_bid: KalshiOrderbookLevel(no_bid, 100.0, 100)}
    
    snapshot = KalshiOrderbookSnapshot(
        sid=sid,
        yes_contracts=yes_levels,
        no_contracts=no_levels
    )
    # Set best prices manually since they're cached properties
    snapshot.best_yes_bid = yes_bid
    snapshot.best_no_bid = no_bid
    return snapshot

def create_mock_polymarket_snapshot(asset_id: str, bid_price: str, ask_price: str) -> PolymarketOrderbookSnapshot:
    """Create a mock Polymarket orderbook snapshot."""
    bids = {bid_price: PolymarketOrderbookLevel(bid_price, 100.0, 100)}
    asks = {ask_price: PolymarketOrderbookLevel(ask_price, 100.0, 100)}
    
    snapshot = PolymarketOrderbookSnapshot(
        asset_id=asset_id,
        bids=bids,
        asks=asks
    )
    # Set best prices manually
    snapshot.best_bid_price = bid_price
    snapshot.best_ask_price = ask_price
    return snapshot

def test_fee_integration():
    """Test that fee calculations are properly integrated."""
    print("Testing fee integration with arbitrage calculator...")
    
    # Create ticker lookup with one maker fee ticker
    ticker_lookup = {
        "12345": "KXNBA",      # Maker fee ticker
        "67890": "REGULAR"     # Regular ticker
    }
    
    # Initialize calculator with ticker lookup
    calculator = ArbitrageCalculator(min_spread_threshold=0.01, ticker_lookup=ticker_lookup)
    
    # Test case 1: Regular ticker (higher fees)
    print("\n--- Test Case 1: Regular Ticker ---")
    kalshi_snapshot = create_mock_kalshi_snapshot(67890, 52, 47)  # 52 cents YES bid, 47 cents NO bid
    poly_yes_snapshot = create_mock_polymarket_snapshot("poly_yes_1", "0.48", "0.49")
    poly_no_snapshot = create_mock_polymarket_snapshot("poly_no_1", "0.51", "0.52")
    
    opportunities = calculator.calculate_arbitrage_opportunities(
        "TEST-REGULAR", kalshi_snapshot, poly_yes_snapshot, poly_no_snapshot
    )
    print(f"Found {len(opportunities)} opportunities with regular ticker")
    
    # Test case 2: Maker fee ticker (lower fees)
    print("\n--- Test Case 2: Maker Fee Ticker ---")
    kalshi_snapshot_maker = create_mock_kalshi_snapshot(12345, 52, 47)  # Same prices, different market
    
    opportunities_maker = calculator.calculate_arbitrage_opportunities(
        "TEST-MAKER", kalshi_snapshot_maker, poly_yes_snapshot, poly_no_snapshot
    )
    print(f"Found {len(opportunities_maker)} opportunities with maker fee ticker")
    
    # Test case 3: Edge case - empty orderbook handling
    print("\n--- Test Case 3: Edge Case Handling ---")
    try:
        # Create snapshot with None values to test error handling
        empty_kalshi = create_mock_kalshi_snapshot(99999, 52, 47)
        empty_kalshi.best_yes_bid = None  # Simulate empty orderbook
        
        opportunities_empty = calculator.calculate_arbitrage_opportunities(
            "TEST-EMPTY", empty_kalshi, poly_yes_snapshot, poly_no_snapshot
        )
        print(f"Handled empty orderbook gracefully: {len(opportunities_empty)} opportunities")
    except Exception as e:
        print(f"Error handling failed: {e}")
    
    print("\n✅ Fee integration test completed!")

def test_price_extraction():
    """Test the price extraction with fee calculations."""
    print("\nTesting price extraction with fees...")
    
    ticker_lookup = {"12345": "KXNBA"}
    calculator = ArbitrageCalculator(min_spread_threshold=0.01, ticker_lookup=ticker_lookup)
    
    # Create test snapshots
    kalshi_snapshot = create_mock_kalshi_snapshot(12345, 52, 47)
    poly_yes_snapshot = create_mock_polymarket_snapshot("poly_yes", "0.48", "0.49")  
    poly_no_snapshot = create_mock_polymarket_snapshot("poly_no", "0.51", "0.53")
    
    # Extract prices
    prices = calculator._extract_prices(kalshi_snapshot, poly_yes_snapshot, poly_no_snapshot)
    
    if prices:
        print("Raw vs Effective Kalshi prices:")
        print(f"  YES bid: {prices.get('k_yes_bid_raw', 'N/A'):.4f} (raw) -> {prices['k_yes_bid']:.4f} (effective)")
        print(f"  YES ask: {prices.get('k_yes_ask_raw', 'N/A'):.4f} (raw) -> {prices['k_yes_ask']:.4f} (effective)")
        print(f"  NO bid:  {prices.get('k_no_bid_raw', 'N/A'):.4f} (raw) -> {prices['k_no_bid']:.4f} (effective)")
        print(f"  NO ask:  {prices.get('k_no_ask_raw', 'N/A'):.4f} (raw) -> {prices['k_no_ask']:.4f} (effective)")
        
        print("\nPolymarket prices (no fees):")
        print(f"  YES: bid={prices['poly_yes_bid']:.4f}, ask={prices['poly_yes_ask']:.4f}")
        print(f"  NO:  bid={prices['poly_no_bid']:.4f}, ask={prices['poly_no_ask']:.4f}")
    else:
        print("❌ Failed to extract prices")
    
    print("✅ Price extraction test completed!")

if __name__ == "__main__":
    test_fee_integration()
    test_price_extraction()