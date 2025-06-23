"""
Test script for MarketsManager.

This script instantiates the MarketsManager class and tests its basic functionality
with dummy arguments. Replace the constants with real market IDs to test actual behavior.
"""

import logging
from MarketsManager import MarketsManager

# Constants for testing (replace with real market IDs as needed)
DUMMY_POLYMARKET_ID = "5044658213116494392261893544497225363846217319105609804585534197935770239191,107816283868337218117379783608318587331517916696607930361272175815275915222107"
DUMMY_KALSHI_TICKER = "KXUSAIRANAGREEMENT-26"

# Configure logging for better visibility during testing
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_markets_manager():
    """Test the MarketsManager with dummy arguments."""
    try:
        # Instantiate the MarketsManager
        manager = MarketsManager()

        # Test connecting to Polymarket
        print("\n🔗 Testing Polymarket connection")
        success_poly = manager.connect(DUMMY_POLYMARKET_ID, platform="polymarket")
        print(f"Polymarket connection success: {success_poly}")

        # Test connecting to Kalshi
        print("\n🔗 Testing Kalshi connection")
        success_kalshi = manager.connect(DUMMY_KALSHI_TICKER, platform="kalshi")
        print(f"Kalshi connection success: {success_kalshi}")

        # Get and print the status of the manager
        print("\n📊 Manager Status")
        status = manager.get_status()
        print(status)

        # Disconnect all connections
        print("\n🔌 Disconnecting all connections")
        manager.disconnect_all()
        print("All connections disconnected successfully.")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_markets_manager()
