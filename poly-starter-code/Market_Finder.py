"""
Polymarket Gamma API Market Data Fetcher

This script fetches market data from Polymarket's Gamma API for a specific market slug.
"""


import requests
import json
from typing import Dict, Optional, List
import logging
import sys
import os
#

# Configure logging
logging.basicConfig(
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_market_by_slug(slug: str) -> Optional[Dict]:
    """
    Fetches market data from Polymarket's Gamma API using the market slug.
    
    Args:
        slug (str): The market slug to search for (e.g., 'romania-presidential-election-winner')
        
    Returns:
        Optional[Dict]: Market data if found, None if not found or error occurs
    """
    url = "https://gamma-api.polymarket.com/events"
    params = {
        "slug": slug,
        "active": True  # Only get active markets
    }
    
    try:
        logger.info(f"Fetching market data for slug: {slug}")
        response = requests.get(url, params=params)
        response.raise_for_status()  # Raise exception for bad status codes
        
        markets = response.json()
        logger.info(f"Found {len(markets)} markets")
        print(markets)
        
        if not markets:
            logger.warning(f"No market found with slug: {slug}")
            return None
            
        market = markets[0]  # Get the first matching market
        logger.info(f"Successfully found market: {market['slug']}")
        return market
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch market data: {e}")
        return None

def search_markets(query: str) -> List[Dict]:
    """
    Searches for markets containing the query string in their slug.
    
    Args:
        query (str): The search query
        
    Returns:
        List[Dict]: List of matching markets
    """
    url = "https://gamma-api.polymarket.com/markets"
    params = {
        "active": True
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        
        all_markets = response.json()
        matching_markets = [
            market for market in all_markets 
            if query.lower() in market['slug'].lower()
        ]
        
        return matching_markets
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to search markets: {e}")
        return []

def print_market_details(market: Dict):
    """
    Prints formatted market details.
    
    Args:
        market (Dict): Market data dictionary
    """
    if not market:
        return
        
    print("\nMarket Details:")
    print("-" * 50)
    print(f"ID: {market.get('id')}")
    print(f"Slug: {market.get('slug')}")
    print(f"Status: {'Active' if market.get('active') else 'Inactive'}")
    print(f"Archived: {market.get('archived')}")
    print(f"Closed: {market.get('closed')}")
    print(f"Liquidity: {market.get('liquidity')}")
    print(f"Volume: {market.get('volume')}")
    print(f"Start Date: {market.get('start_date')}")
    print(f"End Date: {market.get('end_date')}")   
    # Print formatted JSON to console
    print(json.dumps(market, indent=4))
    #Now append the market data to a file
    script_dir = os.path.dirname(os.path.abspath(__file__))
    market_data_file = os.path.join(script_dir, 'market_data.json')
    with open(market_data_file, 'a') as f:
        f.write(json.dumps(market, indent=4))
        f.write('\n')
    
def store_event_data(event_data: Dict):
    #Take the event dictionary and grab the condition_id and token_ids
    condition_id = event_data.get('conditionId')
    token_ids = event_data.get('clobTokenIds')
    question = event_data.get('question')
    #Store the data in a dictionary
    event_data_dict = {
        'condition_id': condition_id,
        'token_ids': json.loads(token_ids),
        'question': question
    }
    return event_data_dict

def create_events_data(event_list: Dict):
    condition_id_list = []
    token_ids_list = []
    for event in event_list:
        condition_id_list.append(store_event_data(event).get('condition_id'))
        #don't add the list of token_ids to the list, just the first element

        token_ids_list.append(store_event_data(event).get('token_ids')[0])
        token_ids_list.append(store_event_data(event).get('token_ids')[1])

        #build a dictionary that maps the event to the token_ids as a JSON file
        event_token_ids_dict = {
           store_event_data(event).get('token_ids')[0]: f"yes_{event.get('question')}",
           store_event_data(event).get('token_ids')[1]: f"no_{event.get('question')}"
        }        #now store the event_token_ids_dict in a JSON file  
        script_dir = os.path.dirname(os.path.abspath(__file__))
        event_token_ids_file = os.path.join(script_dir, f'{slug}_event_token_ids_dict.json')
        with open(event_token_ids_file, 'w') as f:
            json.dump(event_token_ids_dict, f, indent=4)

    return condition_id_list, token_ids_list

if __name__ == "__main__":
    # Get slug from command line argument or use default
    slug = sys.argv[1] if len(sys.argv) > 1 else "poland-presidential-election"
    
    # Try to get market data for the specified slug
    market_data = get_market_by_slug(slug)
    if market_data:
        print_market_details(market_data)
        condition_id_list, token_ids_list = create_events_data(market_data.get('markets'))
        #now store the condition id and token ids in a seperate file
        script_dir = os.path.dirname(os.path.abspath(__file__))
        condition_id_file = os.path.join(script_dir, f'{slug}_condition_id_list.json')
        token_ids_file = os.path.join(script_dir, f'{slug}_token_ids_list.json')
        
        with open(condition_id_file, 'w') as f:
            json.dump(condition_id_list, f, indent=4)
        with open(token_ids_file, 'w') as f:
            json.dump(token_ids_list, f, indent=4)
    else:
        logger.error("No market found")