import requests
import json
from typing import Dict, Optional, List

# Constants
MIN_VOLUME = 10  # Minimum contract volume threshold for markets
MARKETS_FILE = "current_markets.txt"

def get_markets(event_ticker: str) -> Optional[Dict]:
    """
    Fetch markets data from Kalshi API filtered by event ticker.
    
    Args:
        event_ticker (str): The ticker symbol of the event
        
    Returns:
        Optional[Dict]: The markets data if successful, None if failed
    """
    # Base URL for the Kalshi API
    base_url = "https://api.elections.kalshi.com/trade-api/v2"
    
    # Construct the URL for markets endpoint
    url = f"{base_url}/markets"
    
    # Set up headers and query parameters
    headers = {
        "accept": "application/json"
    }
    params = {
        "event_ticker": event_ticker,
        "limit": 100  # Get up to 100 markets per request
    }
    
    try:
        # Make the GET request
        response = requests.get(url, headers=headers, params=params)
        
        # Check if the request was successful
        response.raise_for_status()
        
        # Parse and return the JSON response
        my_response = response.json()

        #check if there is anything inside the response.json(), and if not try with a series ticker

        if not my_response.get("markets", []):
            print("No markets")
            params = {
                "series_ticker": event_ticker,
                "limit": 100  # Get up to 100 markets per request
            }
            response = requests.get(url, headers=headers, params=params)

        return response.json()
    
    except requests.exceptions.RequestException as e:
        print(f"Error fetching markets data: {e}")
        return None

def save_high_volume_markets(markets: List[Dict]) -> None:
    """
    Save market tickers with volume above MIN_VOLUME to a file.
    
    Args:
        markets (List[Dict]): List of market data
    """
    high_volume_markets = []
    print("I found nothing", markets)
    for market in markets:
        volume = market.get('volume', 0)
        if volume > MIN_VOLUME:
            high_volume_markets.append(market.get('ticker'))
    
    # Save to file
    with open(MARKETS_FILE, 'w') as f:
        for ticker in high_volume_markets:
            f.write(f"{ticker}\n")
    
    print(f"\nSaved {len(high_volume_markets)} high-volume markets to {MARKETS_FILE}")

def display_markets(markets_data: Dict) -> None:
    """
    Display the markets information in a readable format.
    
    Args:
        markets_data (Dict): The markets data containing the list of markets
    """
    print(markets_data)

    if not markets_data:
        print("No markets data to display")
        return
    
    # Get the markets list from the response
    markets = markets_data.get('markets', [])
    
    if markets:
        print(f"\nFound {len(markets)} markets:")
        for market in markets:
            print("\n" + "="*50)
            print(f"Market Title: {market.get('title', 'N/A')}")
            print(f"Market Ticker: {market.get('ticker', 'N/A')}")
            print(f"Status: {market.get('status', 'N/A')}")
            print(f"Volume: {market.get('volume', 'N/A')}")
            print(f"Last Price: {market.get('last_price', 'N/A')}")
            print(f"Close Time: {market.get('close_time', 'N/A')}")
            print(f"Event Ticker: {market.get('event_ticker', 'N/A')}")
        
        # Save high volume markets
        save_high_volume_markets(markets)
    else:
        print("\nNo markets found for this event")

def main():
    # Get event ticker from user input and capitalize it
    event_ticker = input("Enter the event ticker (e.g., PRESIDENT-2024): ").strip().upper()
    
    if not event_ticker:
        print("Event ticker cannot be empty")
        return
    
    # Fetch markets data
    print(f"\nFetching markets for event: {event_ticker}")
    markets_data = get_markets(event_ticker)
    
    # Display the results
    if markets_data:
        display_markets(markets_data)
    else:
        print("Failed to fetch markets data")

if __name__ == "__main__":
    main() 