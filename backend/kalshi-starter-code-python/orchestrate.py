import os
import time
import asyncio
from datetime import datetime
import logging
from pathlib import Path
from dotenv import load_dotenv
from cryptography.hazmat.primitives import serialization
from find_kalshi_markets import get_markets, MIN_VOLUME, MARKETS_FILE
from kalshi_client import KalshiWebSocketClient, Environment
#from config import paths

# Always load .env from the project root
env_path = Path(__file__).resolve().parents[1] / '.env'
load_dotenv(dotenv_path=env_path)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('orchestration.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def read_market_tickers():
    """Read market tickers from the current_markets.txt file."""
    try:
        with open(MARKETS_FILE, 'r') as f:
            return [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        logger.error(f"Market tickers file {MARKETS_FILE} not found!")
        return []

def update_market_list(event_ticker: str):
    """Update the list of high-volume markets."""
    logger.info(f"Updating market list for event: {event_ticker}")
    markets_data = get_markets(event_ticker)
    
    if not markets_data:
        logger.error("Failed to fetch markets data")
        return False
    
    print(markets_data)
    
    markets = markets_data.get('markets', [])
    high_volume_markets = []
    
    for market in markets:
        volume = market.get('volume', 0)
        if volume > MIN_VOLUME:
            high_volume_markets.append(market.get('ticker'))
    
    # Save to file
    with open(MARKETS_FILE, 'w') as f:
        for ticker in high_volume_markets:
            f.write(f"{ticker}\n")
    
    logger.info(f"Updated {len(high_volume_markets)} high-volume markets")
    return True

async def run_websocket_client():
    """Run the WebSocket client with current market tickers."""
    market_tickers = read_market_tickers()
    
    if not market_tickers:
        logger.error("No market tickers available to monitor")
        return
    
    logger.info(f"Found {len(market_tickers)} high-volume markets to monitor:")
    for ticker in market_tickers:
        logger.info(f"- {ticker}")
    
    # Ask for user confirmation
    confirm = input("\nDo you want to start monitoring these markets? (y/n): ").strip().lower()
    if confirm != 'y':
        logger.info("Monitoring cancelled by user")
        return
    
    logger.info("Starting WebSocket client...")
    
    # Get environment and key ID
    env = Environment.PROD
    #get API Key ID
    key_id = os.getenv('PROD_KEYID')
    
    # Get the directory where the script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    keyfile = 'kalshi_key_file.txt'
    
    try:
        # Load private key
        with open(keyfile, "rb") as key_file:
            private_key = serialization.load_pem_private_key(
                key_file.read(),
                password=None
            )
        
        # Initialize WebSocket client
        ws_client = KalshiWebSocketClient(
            key_id=key_id,
            private_key=private_key,
            environment=env
        )
        
        # Connect to WebSocket with market tickers
        channels = ["orderbook_delta", "trade", "fill", "ticker_v2"]
        
        try:
            await ws_client.connect(channel=channels, market_ticker=market_tickers)
        except KeyboardInterrupt:
            logger.info("Shutting down WebSocket connection...")
            await ws_client.disconnect()
        except Exception as e:
            logger.error(f"Error in WebSocket connection: {e}")
            if ws_client.is_connected:
                await ws_client.disconnect()
        
    except FileNotFoundError:
        logger.error(f"Private key file not found at {keyfile}")
    except Exception as e:
        logger.error(f"Error initializing WebSocket client: {e}")

async def main():
    # Get event ticker from user
    event_ticker = input("Enter the event ticker to monitor (e.g., PRESIDENT-2024): ").strip().upper()
    
    if not event_ticker:
        logger.error("Event ticker cannot be empty")
        return
    
    # Update market list
    if not update_market_list(event_ticker):
        return
    
    # Run WebSocket client
    try:
        await run_websocket_client()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Error running WebSocket client: {e}")

if __name__ == "__main__":
    asyncio.run(main())

