"""
Polymarket timeseries data processing module

Handles fetching and processing historical timeseries data from Polymarket API
"""
import requests
import logging
from typing import Dict, List
from datetime import datetime
from fastapi import HTTPException
from ..utils.accepted_types import safe_enum_lookup, ValidRanges, ValidViews

logger = logging.getLogger(__name__)

def map_time_range_to_interval(time_range: str) -> str:
    """Map frontend time ranges to Polymarket intervals"""
    time_range_mapping = {
        "1H": "1h",     # 1 hour
        "1W": "1w",     # 1 week  
        "1M": "1m",     # 1 month
        "1Y": "max"     # Maximum available
    }
    
    if time_range not in time_range_mapping:
        raise ValueError(f"Unsupported time range: {time_range}. Supported: {list(time_range_mapping.keys())}")
    
    return time_range_mapping[time_range]

def map_time_range_to_fidelity(time_range: str) -> int:
    """Map frontend time ranges to Polymarket fidelity (resolution in minutes)"""

    #map to upper to avoid any issues
    time_range = time_range.upper()

    fidelity_mapping = {
        "1H": 1,      # 1 minute resolution
        "1W": 60,     # 1 hour resolution
        "1M": 1440,   # 1 day resolution
        "1Y": 1440    # 1 day resolution
    }
    
    return fidelity_mapping.get(time_range)  # Default to 1 hour

async def fetch_polymarket_timeseries(token_id: str, start_ts: int = None, end_ts: int = None) -> Dict:
    '''method recieves the relevant token_id, parses it into the yes/no category, calls the internal helper that returns 
    single-sided candlesticks, and then agregates them into the multi-sided candlestick the frontend expects
    '''

    #get the market metadata and correct token
    '''
        yes_token_id:
        no_token_id
        side:
        range
    '''
    parsed_market = parse_polymarket_market_string(token_id)

    if not start_ts or not end_ts:
        raise ValueError("missing start/end intervals - out of precaution ending any API calls here")

    if not parsed_market["range"] and not map_time_range_to_interval(parsed_market["range"]):
        raise ValueError("Incongruent mapping with the range to interval for Polymarket. Either check the range or check polymarket timeseries processor")


    #range of parsed market
    fidelity = map_time_range_to_fidelity(parsed_market["range"])
    interval = map_time_range_to_interval(parsed_market["range"])

    #get candlesticks
    yes_sticks = await __fetch_polymarket_timeseries(parsed_market["yes_token_id"], start_ts, end_ts, fidelity, "yes", interval)
    no_sticks = await __fetch_polymarket_timeseries(parsed_market["no_token_id"], start_ts, end_ts, fidelity, "no", interval)

    #reassign candlestick list to dictionary
    yes_sticks = process_polymarket_timeseries(yes_sticks, "yes")
    no_sticks = process_polymarket_timeseries(no_sticks, "no")

    #merge the dictionaries - yes stick values will override shared values 
    all_ts = sorted(set(yes_sticks) | set(no_sticks))

    merged_candles = []

    for ts in all_ts:
        yes = yes_sticks.get(ts, {})
        no = no_sticks.get(ts, {})

        merged_candles.append({
            "time": ts,
            "yes_open": yes.get("yes_open"),
            "yes_high": yes.get("yes_high"),
            "yes_low": yes.get("yes_low"),
            "yes_close": yes.get("yes_close"),
            "no_open": no.get("no_open"),
            "no_high": no.get("no_high"),
            "no_low": no.get("no_low"),
            "no_close": no.get("no_close"),
            "volume": yes.get("volume", 0),
            "yes_volume": yes.get("volume", 0),
            "no_volume": no.get("volume", 0),
            "yes_price": yes.get("yes_price", 0),
            "no_price": no.get("no_price", 0)
        })

    '''
    final shape of data is list of OHLC for yes/no with optional fields like open interest and volume that will be harmlessly passed through to the frontend

    '''

    processed_data = {
            "candlesticks": merged_candles,
            "metadata": {
                "count": len(merged_candles),
                "market_ticker": token_id,
                "series_ticker": token_id,
                "side": parsed_market['side'],
                "range": parsed_market['range'],
                "period_interval": "NA - check",
                "processed_at": datetime.now().isoformat()
            }
        }

    return processed_data
    

async def __fetch_polymarket_timeseries(token_id: str, start_ts: int = None, end_ts: int = None, 
                                     fidelity: int = None, side: str = "yes", interval: str = "") -> Dict:
    """Fetch timeseries data from Polymarket API"""
    try:
        base_url = "https://clob.polymarket.com/prices-history"
        
        params = {
            "market": token_id
        }
        

        # Add fidelity (resolution)
        if fidelity:
            params["fidelity"] = fidelity
        
        if range:
            params["interval"] = str(interval)
        
        headers = {
            "accept": "application/json"
        }
        
        # Enhanced logging
        if start_ts and end_ts:
            time_range_hours = (end_ts - start_ts) / 3600
            start_dt = datetime.fromtimestamp(start_ts)
            end_dt = datetime.fromtimestamp(end_ts)
            
            logger.info(f"🕐 POLYMARKET TIMESERIES REQUEST:")
            logger.info(f"   📍 URL: {base_url}")
            logger.info(f"   📊 Token ID: {token_id}")
            logger.info(f"   ⏰ Time Range: Overriding with range map because of polymarket api constraints with {interval}")
            logger.info(f"   📅 Start: {start_ts} ({start_dt.isoformat()})")
            logger.info(f"   📅 End: {end_ts} ({end_dt.isoformat()})") 
            logger.info(f"   🔍 Fidelity: {fidelity} minutes")
        else:
            logger.info(f"🕐 POLYMARKET TIMESERIES REQUEST:")
            logger.info(f"   📍 URL: {base_url}")
            logger.info(f"   📊 Token ID: {token_id}")
            logger.info(f"   🔍 Fidelity: {fidelity} minutes")
        
        logger.info(f"   🔢 Full params: {params}")
        
        response = requests.get(base_url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        history = data.get('history', [])
        
        logger.info(f"Polymarket API returned {len(history)} timeseries points")
        
        if not history:
            logger.warning("No timeseries data returned from Polymarket API")
        
        return data
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Polymarket API request failed: {str(e)}")
        raise HTTPException(status_code=502, detail=f"Failed to fetch data from Polymarket API: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error fetching Polymarket timeseries: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error while fetching timeseries data")

def process_polymarket_timeseries(raw_data: Dict,  side: str) -> Dict:
    """Process raw Polymarket timeseries data for frontend consumption"""
    try:
        history = raw_data.get('history', [])
        
        logger.info(f"🔄 PROCESSING POLYMARKET TIMESERIES:")
        logger.info(f"   📊 Raw timeseries points: {len(history)}")
        logger.info(f"   🔑 Raw data keys: {list(raw_data.keys())}")
        
        # Convert to candlestick format similar to Kalshi
        candlesticks = {}
        
        for i, point in enumerate(history):
            timestamp = point.get('t')
            price = point.get('p')
            
            # Log first few points for debugging
            if i < 3:
                point_time = datetime.fromtimestamp(timestamp) if timestamp else "N/A"
                logger.info(f"   📈 Point {i+1}: time={timestamp} ({point_time}), price={price}")
            
            # Skip invalid points
            if timestamp is None or price is None:
                logger.warning(f"   ⚠️ Point {i+1} has invalid data, skipping")
                continue
            
            # Convert timeseries point to candlestick format
            # Since we only have price data, we'll use the same price for OHLC
            candlestick = {
                "time": timestamp, #check if UTC timestamp is second bound - our frontend should deal with this anyway
                f"{side}_open": price,
                f"{side}_high": price,
                f"{side}_low": price,
                f"{side}_close": price,
                "volume": 0,  # Not available in timeseries data
                f"{side}_price": price,
                "open_interest": 0  # Not available in timeseries data
            }
            
            candlesticks[timestamp] = candlestick
        
        logger.info(f"✅ TIMESERIES PROCESSING COMPLETE:")
        logger.info(f"   ✅ Valid points processed: {len(candlesticks)}")
        
        return candlesticks
        
    except Exception as e:
        logger.error(f"Failed to process Polymarket timeseries data: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to process timeseries data")

def parse_polymarket_market_string(market_string_id: str) -> Dict[str, str]:
    """Parse market string ID to extract token_id, side, and range"""
    try:
        # Format: token_id&side&range
        parts = market_string_id.split('&')
        if len(parts) != 3:
            raise ValueError(f"Invalid market string format. Expected: token_id&side&range, got: {market_string_id}")
        
        token_id, side, range_str = parts
        
        # Validate side
        if not safe_enum_lookup(ValidViews, side):
            raise ValueError(f"Invalid side: {side}. Must be 'yes' or 'no'")
        
        # Validate range
        if not safe_enum_lookup(ValidRanges, range_str):
            raise ValueError(f"Invalid range: {range_str}. Must be one of the valid ranges")
        
        #If our side is yes, then our first token_id will be the one passed onto polymarket
        #If our side is no, then our second token_id will be the one passed onto polymarket


        token_id = token_id.removeprefix('polymarket_')
        token_id = token_id.removeprefix('kalshi_')

        real_tokens = token_id.split(',')

        if len(real_tokens) < 2:
            raise ValueError(f"Only one token passed or invalid token seperation/sequence. Raw token was {token_id} after removal of prefix polymarket_")

        if side == "yes":
            token_id = real_tokens[0]
        elif side == "no":
            token_id = real_tokens[1]

        return {
            'yes_token_id': real_tokens[0],
            'no_token_id': real_tokens[1],
            'side': side,
            'range': safe_enum_lookup(ValidRanges, range_str).value
        }
        
    except Exception as e:
        logger.error(f"Failed to parse market string ID: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Invalid market string format: {str(e)}")