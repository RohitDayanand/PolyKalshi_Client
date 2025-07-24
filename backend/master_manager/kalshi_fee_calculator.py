"""
Kalshi Fee Calculator - Calculates effective bids after transaction fees.

Based on Kalshi's fee schedule:
- General trading fees: 0.07 * C * P * (1-P) rounded up to next cent
- Maker fees for specific tickers: 0.0175 * C * P * (1-P) rounded up to next cent
"""

import math
from typing import Dict, Set

# Maker fee tickers (subject to additional maker fees)
MAKER_FEE_TICKERS: Set[str] = {
    "KXAAAGASM", "KXGDP", "KXPAYROLLS", "KXU3", "KXEGGS", "KXCPI", "KXCPIYOY", 
    "KXFEDDECISION", "KXFED", "KXNBA", "KXNBAEAST", "KXNBAWEST", "KXNBASERIES", 
    "KXNBAGAME", "KXNHL", "KXNHLEAST", "KXNHLWEST", "KXNHLSERIES", "KXNHLGAME", 
    "KXINDY500", "KXPGA", "KXUSOPEN", "KXPGARYDER", "KXTHEOPEN", "KXPGASOLHEIM",
    "KXFOMENSINGLES", "KXFOWOMENSINGLES", "KXWMENSINGLES", "KXWWOMENSINGLES", 
    "KXUSOMENSINGLES", "KXUSOWOMENSINGLES", "KXAOMENSINGLES", "KXAOWOMENSINGLES", 
    "KXNFLGAME", "KXUEFACL", "KXNBAFINALSMVP", "KXCONNSMYTHE", "KXFOMEN", 
    "KXFOWOMEN", "KXNATHANSHD", "KXNATHANDOGS", "KXCLUBWC", "KXTOURDEFRANCE", 
    "KXNASCARRACE", "KXATPMATCH", "KXWTAMATCH", "KXMLBASGAME", "KXMLBHRDERBY"
}

def calculate_trading_fee(price_dollars: float, contracts: int, ticker: str = None) -> float:
    """
    Calculate Kalshi trading fee based on the fee schedule.
    
    Args:
        price_dollars: Contract price in dollars (e.g., 0.50 for 50 cents)
        contracts: Number of contracts being traded
        ticker: Market ticker (optional, for maker fee determination)
    
    Returns:
        Trading fee in dollars, rounded up to the nearest cent
    """
    # Validate inputs
    if price_dollars < 0 or price_dollars > 1:
        raise ValueError("Price must be between 0 and 1 dollars")
    if contracts <= 0:
        raise ValueError("Number of contracts must be positive")
    
    # Determine fee rate based on ticker pattern matching
    if ticker and any(pattern in ticker for pattern in MAKER_FEE_TICKERS):
        fee_rate = 0.0175  # Maker fee rate
    else:
        fee_rate = 0.07    # General trading fee rate
    
    # Calculate fee: fee_rate * C * P * (1-P)
    fee = fee_rate * contracts * price_dollars * (1 - price_dollars)
    
    # Round up to the nearest cent
    return math.ceil(fee * 100) / 100

def kalshi_effective_bid(kalshi_yes_bid_cents: int, contracts: int, 
                        ticker_lookup: Dict[str, str] = None, 
                        market_id: str = None) -> float:
    """
    Calculate the effective bid after accounting for Kalshi transaction fees.
    
    Args:
        kalshi_yes_bid_cents: Kalshi YES bid price in cents (1-99)
        contracts: Number of contracts to trade
        ticker_lookup: Dictionary mapping market_id to ticker symbol
        market_id: Market identifier for ticker lookup
    
    Returns:
        Effective bid price in dollars after fees (0.0-1.0)
    """
    # Convert cents to dollars
    price_dollars = kalshi_yes_bid_cents / 100.0
    
    # Determine ticker if lookup provided
    ticker = None
    if ticker_lookup and market_id and market_id in ticker_lookup:
        ticker = ticker_lookup[market_id]
    
    # Calculate trading fee
    trading_fee = calculate_trading_fee(price_dollars, contracts, ticker)
    
    # Calculate effective bid: original_bid - (fee_per_contract)
    fee_per_contract = trading_fee / contracts
    effective_bid_dollars = price_dollars - fee_per_contract
    
    # Ensure effective bid doesn't go below 0
    return max(0.0, effective_bid_dollars)

def kalshi_effective_ask(kalshi_yes_ask_cents: int, contracts: int,
                        ticker_lookup: Dict[str, str] = None,
                        market_id: str = None) -> float:
    """
    Calculate the effective ask after accounting for Kalshi transaction fees.
    
    Args:
        kalshi_yes_ask_cents: Kalshi YES ask price in cents (1-99)
        contracts: Number of contracts to trade
        ticker_lookup: Dictionary mapping market_id to ticker symbol
        market_id: Market identifier for ticker lookup
    
    Returns:
        Effective ask price in dollars after fees (0.0-1.0)
    """
    # Convert cents to dollars
    price_dollars = kalshi_yes_ask_cents / 100.0
    
    # Determine ticker if lookup provided
    ticker = None
    if ticker_lookup and market_id and market_id in ticker_lookup:
        ticker = ticker_lookup[market_id]
    
    # Calculate trading fee
    trading_fee = calculate_trading_fee(price_dollars, contracts, ticker)
    
    # Calculate effective ask: original_ask + (fee_per_contract)
    fee_per_contract = trading_fee / contracts
    effective_ask_dollars = price_dollars + fee_per_contract
    
    # Ensure effective ask doesn't go above 1.0
    return min(1.0, effective_ask_dollars)

def get_maker_fee_tickers() -> Set[str]:
    """
    Get the set of ticker symbols subject to maker fees.
    
    Returns:
        Set of ticker symbols with maker fees
    """
    return MAKER_FEE_TICKERS.copy()

'''
# Example usage and testing
if __name__ == "__main__":
    # Example calculations
    ticker_map = {
        "12345": "KXNBA",      # Maker fee ticker
        "67890": "OTHERTICKER"  # General fee ticker
    }
    
    # Test general fee calculation
    print("General fee example:")
    bid_cents = 52  # 52 cents
    contracts = 100
    effective_bid = kalshi_effective_bid(bid_cents, contracts, ticker_map, "67890")
    print(f"Original bid: {bid_cents} cents ({bid_cents/100:.2f})")
    print(f"Effective bid: {effective_bid:.4f} ({effective_bid*100:.2f} cents)")
    
    # Test maker fee calculation
    print("\nMaker fee example:")
    effective_bid_maker = kalshi_effective_bid(bid_cents, contracts, ticker_map, "12345")
    print(f"Original bid: {bid_cents} cents ({bid_cents/100:.2f})")
    print(f"Effective bid (maker): {effective_bid_maker:.4f} ({effective_bid_maker*100:.2f} cents)")
    
    # Show fee amounts
    general_fee = calculate_trading_fee(0.52, 100)
    maker_fee = calculate_trading_fee(0.52, 100, "KXNBA")
    print(f"\nFee comparison for 100 contracts at 52 cents:")
    print(f"General fee: ${general_fee:.2f}")
    print(f"Maker fee: ${maker_fee:.2f}")
'''