"""
Tests for Kalshi fee calculator functionality.
"""

import math
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kalshi_fee_calculator import (
    calculate_trading_fee, 
    kalshi_effective_bid, 
    kalshi_effective_ask,
    get_maker_fee_tickers,
    MAKER_FEE_TICKERS
)

def test_general_trading_fee():
    """Test general trading fee calculation."""
    # Test case: 100 contracts at 52 cents
    # Formula: ceil(0.07 * 100 * 0.52 * (1-0.52)) * 100
    # = ceil(0.07 * 100 * 0.52 * 0.48) = ceil(1.7472) = 1.75
    fee = calculate_trading_fee(0.52, 100)
    expected = math.ceil(0.07 * 100 * 0.52 * 0.48 * 100) / 100
    assert fee == expected == 1.75, f"Expected {expected}, got {fee}"
    print("✓ General trading fee calculation correct")

def test_maker_fee():
    """Test maker fee calculation for special tickers."""
    # Test case: 100 contracts at 52 cents with maker fee ticker
    # Formula: ceil(0.0175 * 100 * 0.52 * (1-0.52)) * 100
    # = ceil(0.0175 * 100 * 0.52 * 0.48) = ceil(0.4368) = 0.44
    fee = calculate_trading_fee(0.52, 100, "KXNBA")
    expected = math.ceil(0.0175 * 100 * 0.52 * 0.48 * 100) / 100
    assert fee == expected == 0.44, f"Expected {expected}, got {fee}"
    print("✓ Maker fee calculation correct")

def test_effective_bid():
    """Test effective bid calculation."""
    # General fee case
    ticker_map = {"12345": "REGULAR_TICKER"}
    effective_bid = kalshi_effective_bid(52, 100, ticker_map, "12345")
    
    # Expected: 0.52 - (1.75/100) = 0.52 - 0.0175 = 0.5025
    expected = 0.52 - (1.75/100)
    assert abs(effective_bid - expected) < 0.0001, f"Expected {expected}, got {effective_bid}"
    print("✓ Effective bid calculation correct")

def test_effective_bid_with_maker_fee():
    """Test effective bid calculation with maker fee."""
    ticker_map = {"12345": "KXNBA"}
    effective_bid = kalshi_effective_bid(52, 100, ticker_map, "12345")
    
    # Expected: 0.52 - (0.44/100) = 0.52 - 0.0044 = 0.5156
    expected = 0.52 - (0.44/100)
    assert abs(effective_bid - expected) < 0.0001, f"Expected {expected}, got {effective_bid}"
    print("✓ Effective bid with maker fee calculation correct")

def test_effective_ask():
    """Test effective ask calculation."""
    ticker_map = {"12345": "REGULAR_TICKER"}
    effective_ask = kalshi_effective_ask(52, 100, ticker_map, "12345")
    
    # Expected: 0.52 + (1.75/100) = 0.52 + 0.0175 = 0.5375
    expected = 0.52 + (1.75/100)
    assert abs(effective_ask - expected) < 0.0001, f"Expected {expected}, got {effective_ask}"
    print("✓ Effective ask calculation correct")

def test_maker_fee_tickers():
    """Test that maker fee tickers are properly identified with pattern matching."""
    tickers = get_maker_fee_tickers()
    assert "KXNBA" in tickers, "KXNBA should be in maker fee tickers"
    assert "KXFED" in tickers, "KXFED should be in maker fee tickers"
    assert len(tickers) == len(MAKER_FEE_TICKERS), "Should return all maker fee tickers"
    
    # Test pattern matching
    maker_fee_exact = calculate_trading_fee(0.52, 100, "KXNBA")
    maker_fee_pattern = calculate_trading_fee(0.52, 100, "KXNBA-2024-FINALS")
    general_fee = calculate_trading_fee(0.52, 100, "PRES24-OTHER")
    
    assert maker_fee_exact == maker_fee_pattern, "Pattern matching should work same as exact match"
    assert maker_fee_pattern < general_fee, "Maker fee should be lower than general fee"
    
    print("✓ Maker fee ticker lookup and pattern matching correct")

def test_edge_cases():
    """Test edge cases and bounds."""
    # Test minimum price (1 cent)
    fee_min = calculate_trading_fee(0.01, 100)
    expected_min = math.ceil(0.07 * 100 * 0.01 * 0.99 * 100) / 100
    assert fee_min == expected_min, f"Min price: Expected {expected_min}, got {fee_min}"
    
    # Test maximum price (99 cents)
    fee_max = calculate_trading_fee(0.99, 100)
    expected_max = math.ceil(0.07 * 100 * 0.99 * 0.01 * 100) / 100
    assert fee_max == expected_max, f"Max price: Expected {expected_max}, got {fee_max}"
    
    # Test effective bid doesn't go below 0
    effective_bid_low = kalshi_effective_bid(1, 1000)  # Very low price, high volume
    assert effective_bid_low >= 0.0, "Effective bid should not go below 0"
    
    # Test effective ask doesn't go above 1.0
    effective_ask_high = kalshi_effective_ask(99, 1000)  # Very high price, high volume
    assert effective_ask_high <= 1.0, "Effective ask should not go above 1.0"
    
    print("✓ Edge cases handled correctly")

if __name__ == "__main__":
    print("Running Kalshi fee calculator tests...")
    test_general_trading_fee()
    test_maker_fee()
    test_effective_bid()
    test_effective_bid_with_maker_fee()
    test_effective_ask()
    test_maker_fee_tickers()
    test_edge_cases()
    print("✅ All tests passed!")