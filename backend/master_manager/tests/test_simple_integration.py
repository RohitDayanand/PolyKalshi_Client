"""
Simple test to verify fee calculator integration with arbitrage calculator.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_import_integration():
    """Test that imports work correctly."""
    print("Testing imports...")
    
    # Test fee calculator import
    try:
        from kalshi_fee_calculator import kalshi_effective_bid, kalshi_effective_ask
        print("✅ Fee calculator imports successful")
        
        # Test basic calculation
        result = kalshi_effective_bid(52, 100)
        print(f"✅ Basic fee calculation works: {result:.4f}")
        
    except Exception as e:
        print(f"❌ Fee calculator import failed: {e}")
        return False
    
    # Test arbitrage calculator import
    try:
        # We need to set up the path properly for relative imports
        import arbitrage_calculator
        print("✅ Arbitrage calculator import successful")
        
        # Test that ArbitrageCalculator can be initialized with ticker lookup
        calculator = arbitrage_calculator.ArbitrageCalculator(
            min_spread_threshold=0.01, 
            ticker_lookup={"12345": "KXNBA"}
        )
        print("✅ ArbitrageCalculator initialization with ticker lookup successful")
        print(f"   Ticker lookup: {calculator.ticker_lookup}")
        
    except Exception as e:
        print(f"❌ Arbitrage calculator import/init failed: {e}")
        return False
    
    return True

def test_fee_calculation_logic():
    """Test that fee calculations work as expected."""
    print("\nTesting fee calculation logic...")
    
    try:
        from kalshi_fee_calculator import calculate_trading_fee, kalshi_effective_bid
        
        # Test regular fee
        regular_fee = calculate_trading_fee(0.52, 100)
        print(f"✅ Regular fee (52¢, 100 contracts): ${regular_fee:.2f}")
        
        # Test maker fee
        maker_fee = calculate_trading_fee(0.52, 100, "KXNBA")
        print(f"✅ Maker fee (52¢, 100 contracts): ${maker_fee:.2f}")
        
        # Test effective bid calculations
        regular_effective = kalshi_effective_bid(52, 100)
        maker_effective = kalshi_effective_bid(52, 100, {"12345": "KXNBA"}, "12345")
        
        print(f"✅ Regular effective bid: {regular_effective:.4f}")
        print(f"✅ Maker effective bid: {maker_effective:.4f}")
        
        # Verify maker fee is lower (better effective price)
        if maker_effective > regular_effective:
            print("✅ Maker fee produces better effective price as expected")
        else:
            print("❌ Maker fee logic error")
            return False
            
    except Exception as e:
        print(f"❌ Fee calculation test failed: {e}")
        return False
    
    return True

if __name__ == "__main__":
    print("Running simple integration tests...\n")
    
    success = True
    success &= test_import_integration()
    success &= test_fee_calculation_logic()
    
    print(f"\n{'✅ All tests passed!' if success else '❌ Some tests failed!'}")