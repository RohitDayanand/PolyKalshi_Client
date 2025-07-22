"""
ArbitrageCalculator - Pure arbitrage calculation logic separated from event handling.

This module contains the core mathematical arbitrage detection algorithms without any
event handling, callbacks, or state management dependencies.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass

from .kalshi_client.models.orderbook_state import OrderbookSnapshot as KalshiOrderbookSnapshot
from .polymarket_client.models.orderbook_state import PolymarketOrderbookSnapshot

logger = logging.getLogger()

def arbitrage_calculation_log(message: str) -> None:
    """Log arbitrage calculation messages with consistent formatting."""
    logger.info(f"[ARBITRAGE_CALCULATION] {message}")

@dataclass
class ArbitrageOpportunity:
    """Data class representing a calculated arbitrage opportunity."""
    market_pair: str
    timestamp: str
    spread: float
    direction: str  # "kalshi_to_polymarket" or "polymarket_to_kalshi"
    side: str  # "yes" or "no"
    kalshi_price: Optional[float]
    polymarket_price: Optional[float] 
    kalshi_market_id: Optional[int]
    polymarket_asset_id: Optional[str]
    confidence: float = 1.0
    execution_size: Optional[float] = None
    execution_info: Optional[Dict[str, Any]] = None

class ArbitrageCalculator:
    """
    Pure arbitrage calculation logic using immutable orderbook snapshots.
    
    This class contains only mathematical calculations and has no dependencies on:
    - Event handling or callbacks
    - State management or caching
    - External services or APIs
    - Threading or async coordination
    """
    
    def __init__(self, min_spread_threshold: float = 0.02):
        """
        Initialize the arbitrage calculator.
        
        Args:
            min_spread_threshold: Minimum spread required to consider arbitrage viable
        """
        self.min_spread_threshold = min_spread_threshold
        logger.info(f"ArbitrageCalculator initialized with min_spread_threshold={min_spread_threshold}")
    
    def calculate_arbitrage_opportunities(self, pair_name: str, 
                                       kalshi_snapshot: KalshiOrderbookSnapshot,
                                       poly_yes_snapshot: PolymarketOrderbookSnapshot, 
                                       poly_no_snapshot: PolymarketOrderbookSnapshot) -> List[ArbitrageOpportunity]:
        """
        Calculate arbitrage opportunities from immutable orderbook snapshots.
        This is the main entry point for pure arbitrage calculation.
        
        Args:
            pair_name: Market pair identifier
            kalshi_snapshot: Immutable Kalshi orderbook snapshot
            poly_yes_snapshot: Immutable Polymarket YES orderbook snapshot
            poly_no_snapshot: Immutable Polymarket NO orderbook snapshot
            
        Returns:
            List of arbitrage opportunities (empty if none found)
        """
        # Validate snapshots have required data
        if not self._validate_snapshots(pair_name, kalshi_snapshot, poly_yes_snapshot, poly_no_snapshot):
            return []
        
        arbitrage_calculation_log(f"🔍 CALCULATING | pair={pair_name} | kalshi_sid={kalshi_snapshot.sid} | poly_yes={poly_yes_snapshot.asset_id} | poly_no={poly_no_snapshot.asset_id}")
        
        # Extract and normalize prices
        prices = self._extract_prices(kalshi_snapshot, poly_yes_snapshot, poly_no_snapshot)
        if not prices:
            arbitrage_calculation_log(f"❌ INVALID PRICES | pair={pair_name}")
            return []
        
        # Log price analysis
        self._log_price_analysis(pair_name, prices)
        
        # Calculate all arbitrage strategies
        opportunities = self._calculate_all_strategies(pair_name, prices, kalshi_snapshot, poly_yes_snapshot, poly_no_snapshot)
        
        # Final calculation summary
        if opportunities:
            arbitrage_calculation_log(f"✅ CALCULATION RESULT | pair={pair_name} | found={len(opportunities)} opportunities")
        else:
            arbitrage_calculation_log(f"❌ CALCULATION RESULT | pair={pair_name} | found=0 opportunities")
        
        return opportunities
    
    def _validate_snapshots(self, pair_name: str, kalshi_snapshot: KalshiOrderbookSnapshot,
                          poly_yes_snapshot: PolymarketOrderbookSnapshot, 
                          poly_no_snapshot: PolymarketOrderbookSnapshot) -> bool:
        """Validate that all snapshots contain required data."""
        if not kalshi_snapshot.sid:
            logger.debug(f"No valid Kalshi snapshot for pair {pair_name}")
            return False
        if not poly_yes_snapshot.asset_id:
            logger.debug(f"No valid Polymarket YES snapshot for pair {pair_name}")
            return False
        if not poly_no_snapshot.asset_id:
            logger.debug(f"No valid Polymarket NO snapshot for pair {pair_name}")
            return False
        return True
    
    def _extract_prices(self, kalshi_snapshot: KalshiOrderbookSnapshot,
                       poly_yes_snapshot: PolymarketOrderbookSnapshot, 
                       poly_no_snapshot: PolymarketOrderbookSnapshot) -> Optional[Dict[str, float]]:
        """
        Extract and normalize prices from all snapshots.
        
        Returns:
            Dict with normalized prices (0.0-1.0) or None if invalid prices
        """
        # Extract Kalshi prices (in cents, 1-99)
        kalshi_yes_bid = kalshi_snapshot.best_yes_bid
        kalshi_no_bid = kalshi_snapshot.best_no_bid
        
        # Use prediction market relationship: YES ask = 100 - NO bid for Kalshi
        kalshi_yes_ask = 100 - kalshi_no_bid if kalshi_no_bid is not None else None
        kalshi_no_ask = 100 - kalshi_yes_bid if kalshi_yes_bid is not None else None
        
        # Extract Polymarket prices (convert strings to float decimals 0.0-1.0)
        poly_yes_bid = float(poly_yes_snapshot.best_bid_price) if poly_yes_snapshot.best_bid_price else None
        poly_yes_ask = float(poly_yes_snapshot.best_ask_price) if poly_yes_snapshot.best_ask_price else None
        poly_no_bid = float(poly_no_snapshot.best_bid_price) if poly_no_snapshot.best_bid_price else None
        poly_no_ask = float(poly_no_snapshot.best_ask_price) if poly_no_snapshot.best_ask_price else None
        
        # Convert Kalshi cents to decimal format (0.0-1.0)
        k_yes_bid = kalshi_yes_bid / 100.0 if kalshi_yes_bid is not None else None
        k_yes_ask = kalshi_yes_ask / 100.0 if kalshi_yes_ask is not None else None
        k_no_bid = kalshi_no_bid / 100.0 if kalshi_no_bid is not None else None
        k_no_ask = kalshi_no_ask / 100.0 if kalshi_no_ask is not None else None
        
        # Validate we have all required prices
        if None in [k_yes_bid, k_yes_ask, poly_yes_bid, poly_yes_ask, k_no_bid, k_no_ask, poly_no_bid, poly_no_ask]:
            return None
        
        return {
            'k_yes_bid': k_yes_bid,
            'k_yes_ask': k_yes_ask,
            'k_no_bid': k_no_bid,
            'k_no_ask': k_no_ask,
            'poly_yes_bid': poly_yes_bid,
            'poly_yes_ask': poly_yes_ask,
            'poly_no_bid': poly_no_bid,
            'poly_no_ask': poly_no_ask
        }
    
    def _log_price_analysis(self, pair_name: str, prices: Dict[str, float]) -> None:
        """Log detailed price information for analysis."""
        arbitrage_calculation_log(f"📊 PRICE ANALYSIS | pair={pair_name}")
        arbitrage_calculation_log(f"   🏦 Kalshi YES: bid={prices['k_yes_bid']:.3f}, ask={prices['k_yes_ask']:.3f}")
        arbitrage_calculation_log(f"   🏦 Kalshi NO:  bid={prices['k_no_bid']:.3f}, ask={prices['k_no_ask']:.3f}")
        arbitrage_calculation_log(f"   🎯 Poly YES:   bid={prices['poly_yes_bid']:.3f}, ask={prices['poly_yes_ask']:.3f}")
        arbitrage_calculation_log(f"   🎯 Poly NO:    bid={prices['poly_no_bid']:.3f}, ask={prices['poly_no_ask']:.3f}")
    
    def _calculate_all_strategies(self, pair_name: str, prices: Dict[str, float],
                                kalshi_snapshot: KalshiOrderbookSnapshot,
                                poly_yes_snapshot: PolymarketOrderbookSnapshot,
                                poly_no_snapshot: PolymarketOrderbookSnapshot) -> List[ArbitrageOpportunity]:
        """Calculate all four arbitrage strategies and return viable opportunities."""
        opportunities = []
        timestamp = datetime.now().isoformat()
        
        # Calculate all possible arbitrage spreads
        spreads = self._calculate_spreads(prices)
        self._log_spread_calculations(pair_name, prices, spreads)
        
        # Strategy 1: Sell Kalshi YES + Buy Polymarket NO
        if spreads['strategy_1'] >= self.min_spread_threshold:
            execution_info = self._calculate_execution_size(
                kalshi_snapshot, poly_yes_snapshot, poly_no_snapshot,
                kalshi_price=int(prices['k_yes_bid'] * 100), poly_no_price=prices['poly_no_ask'], side="bid"
            )
            
            opportunity = ArbitrageOpportunity(
                market_pair=pair_name,
                timestamp=timestamp,
                spread=spreads['strategy_1'],
                direction="kalshi_to_polymarket",
                side="yes",
                kalshi_price=prices['k_yes_bid'],
                polymarket_price=prices['poly_no_ask'],
                kalshi_market_id=kalshi_snapshot.sid,
                polymarket_asset_id=poly_no_snapshot.asset_id,
                execution_size=execution_info.get('min_execution_size', 0.0),
                execution_info=execution_info
            )
            opportunities.append(opportunity)
            arbitrage_calculation_log(f"🚨 OPPORTUNITY FOUND | pair={pair_name} | strategy=1 | spread={spreads['strategy_1']:.3f}")
        
        # Strategy 2: Sell Kalshi NO + Buy Polymarket YES
        if spreads['strategy_2'] >= self.min_spread_threshold:
            execution_info = self._calculate_execution_size(
                kalshi_snapshot, poly_yes_snapshot, poly_no_snapshot,
                kalshi_price=int(prices['k_no_bid'] * 100), poly_yes_price=prices['poly_yes_ask'], side="bid"
            )
            
            opportunity = ArbitrageOpportunity(
                market_pair=pair_name,
                timestamp=timestamp,
                spread=spreads['strategy_2'],
                direction="kalshi_to_polymarket",
                side="no",
                kalshi_price=prices['k_no_bid'],
                polymarket_price=prices['poly_yes_ask'],
                kalshi_market_id=kalshi_snapshot.sid,
                polymarket_asset_id=poly_yes_snapshot.asset_id,
                execution_size=execution_info.get('min_execution_size', 0.0),
                execution_info=execution_info
            )
            opportunities.append(opportunity)
            arbitrage_calculation_log(f"🚨 OPPORTUNITY FOUND | pair={pair_name} | strategy=2 | spread={spreads['strategy_2']:.3f}")
        
        # Strategy 3: Sell Polymarket YES + Buy Kalshi NO
        if spreads['strategy_3'] >= self.min_spread_threshold:
            execution_info = self._calculate_execution_size(
                kalshi_snapshot, poly_yes_snapshot, poly_no_snapshot,
                kalshi_price=int(prices['k_no_ask'] * 100), poly_yes_price=prices['poly_yes_bid'], side="ask"
            )
            
            opportunity = ArbitrageOpportunity(
                market_pair=pair_name,
                timestamp=timestamp,
                spread=spreads['strategy_3'],
                direction="polymarket_to_kalshi",
                side="yes",
                kalshi_price=prices['k_no_ask'],
                polymarket_price=prices['poly_yes_bid'],
                kalshi_market_id=kalshi_snapshot.sid,
                polymarket_asset_id=poly_yes_snapshot.asset_id,
                execution_size=execution_info.get('min_execution_size', 0.0),
                execution_info=execution_info
            )
            opportunities.append(opportunity)
            arbitrage_calculation_log(f"🚨 OPPORTUNITY FOUND | pair={pair_name} | strategy=3 | spread={spreads['strategy_3']:.3f}")
        
        # Strategy 4: Sell Polymarket NO + Buy Kalshi YES
        if spreads['strategy_4'] >= self.min_spread_threshold:
            execution_info = self._calculate_execution_size(
                kalshi_snapshot, poly_yes_snapshot, poly_no_snapshot,
                kalshi_price=int(prices['k_yes_ask'] * 100), poly_no_price=prices['poly_no_bid'], side="ask"
            )
            
            opportunity = ArbitrageOpportunity(
                market_pair=pair_name,
                timestamp=timestamp,
                spread=spreads['strategy_4'],
                direction="polymarket_to_kalshi",
                side="no",
                kalshi_price=prices['k_yes_ask'],
                polymarket_price=prices['poly_no_bid'],
                kalshi_market_id=kalshi_snapshot.sid,
                polymarket_asset_id=poly_no_snapshot.asset_id,
                execution_size=execution_info.get('min_execution_size', 0.0),
                execution_info=execution_info
            )
            opportunities.append(opportunity)
            arbitrage_calculation_log(f"🚨 OPPORTUNITY FOUND | pair={pair_name} | strategy=4 | spread={spreads['strategy_4']:.3f}")
        
        return opportunities
    
    def _calculate_spreads(self, prices: Dict[str, float]) -> Dict[str, float]:
        """Calculate spreads for all four arbitrage strategies."""
        return {
            'strategy_1': 1.0 - (prices['k_yes_bid'] + prices['poly_no_ask']),  # Sell Kalshi YES + Buy Poly NO
            'strategy_2': 1.0 - (prices['k_no_bid'] + prices['poly_yes_ask']),  # Sell Kalshi NO + Buy Poly YES
            'strategy_3': 1.0 - (prices['poly_yes_bid'] + prices['k_no_ask']),  # Sell Poly YES + Buy Kalshi NO
            'strategy_4': 1.0 - (prices['poly_no_bid'] + prices['k_yes_ask'])   # Sell Poly NO + Buy Kalshi YES
        }
    
    def _log_spread_calculations(self, pair_name: str, prices: Dict[str, float], spreads: Dict[str, float]) -> None:
        """Log detailed spread calculations for analysis."""
        arbitrage_calculation_log(f"🧮 SPREAD CALCULATIONS | pair={pair_name}")
        arbitrage_calculation_log(f"   1. Sell Kalshi YES + Buy Poly NO: {prices['k_yes_bid']:.3f} + {prices['poly_no_ask']:.3f} = {prices['k_yes_bid'] + prices['poly_no_ask']:.3f} → spread={spreads['strategy_1']:.3f}")
        arbitrage_calculation_log(f"   2. Sell Kalshi NO + Buy Poly YES: {prices['k_no_bid']:.3f} + {prices['poly_yes_ask']:.3f} = {prices['k_no_bid'] + prices['poly_yes_ask']:.3f} → spread={spreads['strategy_2']:.3f}")
        arbitrage_calculation_log(f"   3. Sell Poly YES + Buy Kalshi NO: {prices['poly_yes_bid']:.3f} + {prices['k_no_ask']:.3f} = {prices['poly_yes_bid'] + prices['k_no_ask']:.3f} → spread={spreads['strategy_3']:.3f}")
        arbitrage_calculation_log(f"   4. Sell Poly NO + Buy Kalshi YES: {prices['poly_no_bid']:.3f} + {prices['k_yes_ask']:.3f} = {prices['poly_no_bid'] + prices['k_yes_ask']:.3f} → spread={spreads['strategy_4']:.3f}")
        arbitrage_calculation_log(f"   🎯 Min threshold: {self.min_spread_threshold:.3f}")
    
    def _calculate_execution_size(self, kalshi_snapshot: KalshiOrderbookSnapshot, 
                                poly_yes_snapshot: PolymarketOrderbookSnapshot, 
                                poly_no_snapshot: PolymarketOrderbookSnapshot,
                                kalshi_price: Optional[int] = None, 
                                poly_yes_price: Optional[float] = None,
                                poly_no_price: Optional[float] = None,
                                side: str = "bid") -> Dict[str, Optional[float]]:
        """
        Calculate execution sizes as 50% of available orderbook depth at specific price levels.
        
        Args:
            kalshi_snapshot: Kalshi orderbook snapshot
            poly_yes_snapshot: Polymarket YES asset snapshot  
            poly_no_snapshot: Polymarket NO asset snapshot
            kalshi_price: Specific Kalshi price level (cents, e.g., 65)
            poly_yes_price: Specific Polymarket YES price level (decimal, e.g., 0.62)
            poly_no_price: Specific Polymarket NO price level (decimal, e.g., 0.37)
            side: "bid" or "ask" - which side of orderbook to check
            
        Returns:
            Dict with execution sizes and limiting factor
        """
        try:
            # Use best prices if specific prices not provided
            if kalshi_price is None:
                if side == "bid":
                    kalshi_price = kalshi_snapshot.best_yes_bid or kalshi_snapshot.best_no_bid
                else:
                    kalshi_price = kalshi_snapshot.best_yes_bid or kalshi_snapshot.best_no_bid
                    
            if poly_yes_price is None:
                poly_yes_price = float(poly_yes_snapshot.best_bid_price) if side == "bid" else float(poly_yes_snapshot.best_ask_price)
                
            if poly_no_price is None:
                poly_no_price = float(poly_no_snapshot.best_bid_price) if side == "bid" else float(poly_no_snapshot.best_ask_price)
            
            # Get orderbook depth at specific price levels
            kalshi_size = self._get_kalshi_depth_at_price(kalshi_snapshot, kalshi_price, side)
            poly_yes_size = self._get_polymarket_depth_at_price(poly_yes_snapshot, poly_yes_price, side)
            poly_no_size = self._get_polymarket_depth_at_price(poly_no_snapshot, poly_no_price, side)
            
            # Calculate 50% of available depth for each
            kalshi_execution = kalshi_size * 0.5 if kalshi_size else 0.0
            poly_yes_execution = poly_yes_size * 0.5 if poly_yes_size else 0.0
            poly_no_execution = poly_no_size * 0.5 if poly_no_size else 0.0
            
            # Determine limiting factor
            sizes = {
                'kalshi': kalshi_execution,
                'poly_yes': poly_yes_execution, 
                'poly_no': poly_no_execution
            }
            limiting_factor = min(sizes.keys(), key=lambda k: sizes[k]) if any(sizes.values()) else 'none'
            
            logger.debug(f"💰 EXECUTION SIZE CALC: kalshi={kalshi_execution:.2f}, poly_yes={poly_yes_execution:.2f}, poly_no={poly_no_execution:.2f}, limiting={limiting_factor}")
            
            return {
                'kalshi_size': kalshi_execution,
                'poly_yes_size': poly_yes_execution,
                'poly_no_size': poly_no_execution,
                'limiting_factor': limiting_factor,
                'min_execution_size': min(sizes.values()) if any(sizes.values()) else 0.0
            }
            
        except Exception as e:
            logger.error(f"Error calculating execution size: {e}")
            return {
                'kalshi_size': None,
                'poly_yes_size': None, 
                'poly_no_size': None,
                'limiting_factor': 'error',
                'min_execution_size': 0.0
            }
    
    def _get_kalshi_depth_at_price(self, snapshot: KalshiOrderbookSnapshot, price: int, side: str) -> float:
        """Get orderbook depth at specific Kalshi price level."""
        if price is None:
            return 0.0
            
        total_size = 0.0
        
        # Check YES contracts
        if price in snapshot.yes_contracts:
            level = snapshot.yes_contracts[price]
            total_size += level.size_float
            
        # Check NO contracts  
        if price in snapshot.no_contracts:
            level = snapshot.no_contracts[price]
            total_size += level.size_float
            
        return total_size
    
    def _get_polymarket_depth_at_price(self, snapshot: PolymarketOrderbookSnapshot, price: float, side: str) -> float:
        """Get orderbook depth at specific Polymarket price level."""
        if price is None:
            return 0.0
            
        price_str = str(price)
        
        # Choose bid or ask side
        if side == "bid":
            if price_str in snapshot.bids:
                return snapshot.bids[price_str].size_float
        else:  # ask
            if price_str in snapshot.asks:
                return snapshot.asks[price_str].size_float
                
        return 0.0