"""
Kalshi candlestick data processing module

Handles fetching and processing candlestick data from Kalshi API
"""
import requests
import logging
from typing import Dict
from datetime import datetime
from fastapi import HTTPException

from backend.utils.util_functions import OHLC, quote_midprice

logger = logging.getLogger(__name__)

def map_time_range_to_period_interval(time_range: str) -> int:
    """Map frontend time ranges to Kalshi period intervals"""
    time_range_mapping = {
        "1H": 1,     # 1 minute
        "1W": 60,    # 60 minutes  
        "1M": 1440,  # 1440 minutes (1 day)
        "1Y": 1440   # 1440 minutes (1 day) - closest available
    }
    
    if time_range not in time_range_mapping:
        raise ValueError(f"Unsupported time range: {time_range}. Supported: {list(time_range_mapping.keys())}")
    
    return time_range_mapping[time_range]

async def fetch_kalshi_candlesticks(series_ticker: str, market_ticker: str, start_ts: int, end_ts: int, period_interval: int) -> Dict:
    """Fetch candlestick data from Kalshi API"""
    try:
        url = f"https://api.elections.kalshi.com/trade-api/v2/series/{series_ticker}/markets/{market_ticker}/candlesticks"
        
        params = {
            "start_ts": start_ts,
            "end_ts": end_ts,
            "period_interval": period_interval
        }
        
        headers = {
            "accept": "application/json"
        }
        
        # Enhanced timestamp logging
        time_range_hours = (end_ts - start_ts) / 3600
        start_dt = datetime.fromtimestamp(start_ts)
        end_dt = datetime.fromtimestamp(end_ts)
        
        logger.info(f"🕐 KALSHI CANDLESTICKS REQUEST:")
        logger.info(f"   📍 URL: {url}")
        logger.info(f"   📊 Market: {series_ticker}/{market_ticker}")
        logger.info(f"   ⏰ Time Range: {time_range_hours:.1f} hours ({time_range_hours/24:.1f} days)")
        logger.info(f"   📅 Start: {start_ts} ({start_dt.isoformat()})")
        logger.info(f"   📅 End: {end_ts} ({end_dt.isoformat()})")
        logger.info(f"   ⏱️ Period Interval: {period_interval} minutes")
        logger.info(f"   🔢 Full params: {params}")
        
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        candlesticks = data.get('candlesticks', [])
        
        logger.info(f"Kalshi API returned {len(candlesticks)} candlesticks")
        
        if not candlesticks:
            logger.warning("No candlesticks returned from Kalshi API")
        
        return data
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Kalshi API request failed: {str(e)}")
        raise HTTPException(status_code=502, detail=f"Failed to fetch data from Kalshi API: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error fetching Kalshi candlesticks: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error while fetching candlestick data")

def process_kalshi_candlesticks(raw_data: Dict, market_info: Dict[str, str]) -> Dict:
    """Process raw Kalshi candlestick data for frontend consumption"""
    try:
        candlesticks = raw_data.get('candlesticks', [])
        
        logger.info(f"🔄 PROCESSING KALSHI CANDLESTICKS:")
        logger.info(f"   📊 Raw candlesticks count: {len(candlesticks)}")
        logger.info(f"   📋 Market info: {market_info}")
        logger.info(f"   🔑 Raw data keys: {list(raw_data.keys())}")
        
        processed_data = {
            "candlesticks": [],
            "metadata": {
                "count": len(candlesticks),
                "market_ticker": market_info.get('market_ticker'),
                "series_ticker": market_info.get('series_ticker'),
                "side": market_info.get('side'),
                "range": market_info.get('range'),
                "period_interval": raw_data.get('period_interval'),
                "processed_at": datetime.now().isoformat()
            }
        }
        
        # Process each candlestick
        valid_candles = 0
        invalid_candles = 0
        
        for i, candle in enumerate(candlesticks):
            yes_bid = candle.get("yes_bid")
            yes_ask = candle.get("yes_ask")
            end_period_ts = candle.get('end_period_ts')

            # Log first few candles for debugging
            if i < 3:
                candle_time = datetime.fromtimestamp(end_period_ts) if end_period_ts else "N/A"
                logger.info(f"   🕯️ Candle {i+1}: time={end_period_ts} ({candle_time}), yes_bid={yes_bid}, yes_ask={yes_ask}")
                logger.info(f"      🔑 Candle keys: {list(candle.keys())}")

            # Check if we have valid bid/ask data
            if yes_bid is None or yes_ask is None:
                invalid_candles += 1
                logger.warning(f"   ⚠️ Candle {i+1} has no bid/ask data, skipping")
                continue

            processed_candle = {
                "time": end_period_ts,
                "yes_open": quote_midprice(yes_bid, yes_ask, OHLC.OPEN),
                "yes_high": quote_midprice(yes_bid, yes_ask, OHLC.HIGH), 
                "yes_low": quote_midprice(yes_bid, yes_ask, OHLC.LOW),
                "yes_close": quote_midprice(yes_bid, yes_ask, OHLC.CLOSE),
                "no_open": quote_midprice(yes_bid, yes_ask, OHLC.OPEN, isNo=True),
                "no_high": quote_midprice(yes_bid, yes_ask, OHLC.HIGH, isNo=True),
                "no_low": quote_midprice(yes_bid, yes_ask, OHLC.LOW, isNo=True),
                "no_close": quote_midprice(yes_bid, yes_ask, OHLC.CLOSE, isNo=True),
                "volume": candle.get("volume", 0),
                "yes_price": quote_midprice(yes_bid, yes_ask, OHLC.CLOSE),
                "no_price": quote_midprice(yes_ask, yes_bid, OHLC.CLOSE, isNo=True),
                "open_interest": candle.get("open_interest", 0)
            }

            processed_data["candlesticks"].append(processed_candle)
            valid_candles += 1
        
        logger.info(f"✅ CANDLESTICK PROCESSING COMPLETE:")
        logger.info(f"   ✅ Valid candles processed: {valid_candles}")
        logger.info(f"   ❌ Invalid candles skipped: {invalid_candles}")
        logger.info(f"   📊 Final count sent to frontend: {len(processed_data['candlesticks'])}")
        
        return processed_data
        
    except Exception as e:
        logger.error(f"Failed to process Kalshi candlestick data: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to process candlestick data")