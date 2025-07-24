"""
ArbitrageCalculator - Pure arbitrage calculation logic separated from event handling.

This module contains the core mathematical arbitrage detection algorithms without any
event handling, callbacks, or state management dependencies.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass, asdict

try:
    # Try relative imports first (when used as a module)
    from .kalshi_client.models.orderbook_state import OrderbookSnapshot as KalshiOrderbookSnapshot
    from .polymarket_client.models.orderbook_state import PolymarketOrderbookSnapshot
    from .kalshi_fee_calculator import kalshi_effective_bid, kalshi_effective_ask
except ImportError:
    # Fall back to absolute imports (when run directly)
    from kalshi_client.models.orderbook_state import OrderbookSnapshot as KalshiOrderbookSnapshot
    from polymarket_client.models.orderbook_state import PolymarketOrderbookSnapshot
    from kalshi_fee_calculator import kalshi_effective_bid, kalshi_effective_ask

logger = logging.getLogger()

def arbitrage_calculation_log(message: str) -> None:
    """Log arbitrage calculation messages with consistent formatting."""
    logger.info(f"[ARBITRAGE_CALCULATION] {message}")

@dataclass
class ArbitrageOpportunity:
    """
    Data class representing a calculated arbitrage opportunity.
    
    This structure flows through the entire arbitrage alert system:
    ArbitrageCalculator -> ArbitrageDetector -> ArbitrageManager -> EventBus -> 
    MarketsCoordinator -> WebSocket -> Frontend
    
    Attributes:
        market_pair (str): Human-readable market pair identifier (e.g., "PRES24-DJT")
        timestamp (str): ISO timestamp when the opportunity was detected
        spread (float): Profit spread as decimal (0.035 = 3.5% profit opportunity)
        direction (str): Trading direction - "kalshi_to_polymarket" or "polymarket_to_kalshi"
        side (str): Contract side - "yes" or "no" 
        kalshi_price (Optional[float]): Kalshi price as decimal (0.0-1.0)
        polymarket_price (Optional[float]): Polymarket price as decimal (0.0-1.0)
        kalshi_market_id (Optional[int]): Kalshi market SID for execution
        polymarket_asset_id (Optional[str]): Polymarket asset ID for execution
        confidence (float): Confidence level (1.0 = high confidence, default: 1.0)
        execution_size (Optional[float]): Minimum executable size across both platforms
        execution_info (Optional[Dict[str, Any]]): Detailed execution constraints and liquidity info
        
    Example:
        {
            "market_pair": "PRES24-DJT",
            "timestamp": "2025-01-15T10:30:00Z",
            "spread": 0.035,
            "direction": "kalshi_to_polymarket", 
            "side": "yes",
            "kalshi_price": 0.520,
            "polymarket_price": 0.480,
            "kalshi_market_id": 12345,
            "polymarket_asset_id": "asset_abc123",
            "confidence": 1.0,
            "execution_size": 100.0,
            "execution_info": {
                "kalshi_size": 150.0,
                "polymarket_size": 100.0,
                "min_execution_size": 100.0,
                "limiting_factor": "polymarket"
            }
        }
    """
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
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert ArbitrageOpportunity to JSON-serializable dictionary."""
        return asdict(self)

class ArbitrageCalculator:
    """
    Pure arbitrage calculation logic using immutable orderbook snapshots.
    
    This class contains only mathematical calculations and has no dependencies on:
    - Event handling or callbacks
    - State management or caching
    - External services or APIs
    - Threading or async coordination
    """
    
    def __init__(self, min_spread_threshold, min_trade_size: float = 10.0, ticker_lookup: Optional[Dict[str, str]] = None):
        """
        Initialize the arbitrage calculator.
        
        Args:
            min_spread_threshold: Minimum spread required to consider arbitrage viable
            min_trade_size: Minimum trade size threshold for execution
            ticker_lookup: Optional dictionary mapping market_id to ticker symbols for fee calculation
        """
        self.min_spread_threshold = min_spread_threshold
        self.min_trade_size = min_trade_size
        self.ticker_lookup = ticker_lookup or {}
        logger.info(f"ArbitrageCalculator initialized with min_spread_threshold={min_spread_threshold}, min_trade_size={min_trade_size}")
    
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
        
        # Extract and normalize prices (with fee adjustments)
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
        Extract and normalize prices from all snapshots, including fee adjustments for Kalshi.
        
        Returns:
            Dict with normalized prices (0.0-1.0) including fee-adjusted Kalshi prices, or None if invalid prices
        """
        try:
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
            
            # Validate we have all required raw prices
            if None in [kalshi_yes_bid, kalshi_yes_ask, poly_yes_bid, poly_yes_ask, kalshi_no_bid, kalshi_no_ask, poly_no_bid, poly_no_ask]:
                logger.debug("Missing required price data in orderbooks")
                return None
            
            # Calculate fee-adjusted Kalshi prices
            # Use a standard contract size of 100 for fee calculations
            standard_contracts = 100
            market_id = str(kalshi_snapshot.sid) if kalshi_snapshot.sid else None
            
            # Fee-adjusted Kalshi prices (effective prices after fees)
            try:
                k_yes_bid_effective = kalshi_effective_bid(kalshi_yes_bid, standard_contracts, self.ticker_lookup, market_id)
                k_yes_ask_effective = kalshi_effective_ask(kalshi_yes_ask, standard_contracts, self.ticker_lookup, market_id)
                k_no_bid_effective = kalshi_effective_bid(kalshi_no_bid, standard_contracts, self.ticker_lookup, market_id)
                k_no_ask_effective = kalshi_effective_ask(kalshi_no_ask, standard_contracts, self.ticker_lookup, market_id)
            except Exception as e:
                logger.warning(f"Error calculating Kalshi fees, using raw prices: {e}")
                # Fallback to raw prices if fee calculation fails
                k_yes_bid_effective = kalshi_yes_bid / 100.0
                k_yes_ask_effective = kalshi_yes_ask / 100.0
                k_no_bid_effective = kalshi_no_bid / 100.0
                k_no_ask_effective = kalshi_no_ask / 100.0
            
            # Validate effective prices are reasonable (0-1 range)
            for price, name in [(k_yes_bid_effective, 'k_yes_bid'), (k_yes_ask_effective, 'k_yes_ask'),
                              (k_no_bid_effective, 'k_no_bid'), (k_no_ask_effective, 'k_no_ask')]:
                if price < 0 or price > 1:
                    logger.warning(f"Invalid effective price for {name}: {price}, using raw price")
                    # Fall back to raw price if effective price is out of bounds
                    if name == 'k_yes_bid':
                        k_yes_bid_effective = kalshi_yes_bid / 100.0
                    elif name == 'k_yes_ask':
                        k_yes_ask_effective = kalshi_yes_ask / 100.0
                    elif name == 'k_no_bid':
                        k_no_bid_effective = kalshi_no_bid / 100.0
                    elif name == 'k_no_ask':
                        k_no_ask_effective = kalshi_no_ask / 100.0
            
            return {
                'k_yes_bid': k_yes_bid_effective,
                'k_yes_ask': k_yes_ask_effective,
                'k_no_bid': k_no_bid_effective,
                'k_no_ask': k_no_ask_effective,
                'poly_yes_bid': poly_yes_bid,
                'poly_yes_ask': poly_yes_ask,
                'poly_no_bid': poly_no_bid,
                'poly_no_ask': poly_no_ask,
                # Also include raw Kalshi prices for logging/debugging
                'k_yes_bid_raw': kalshi_yes_bid / 100.0,
                'k_yes_ask_raw': kalshi_yes_ask / 100.0,
                'k_no_bid_raw': kalshi_no_bid / 100.0,
                'k_no_ask_raw': kalshi_no_ask / 100.0
            }
            
        except Exception as e:
            logger.error(f"Error extracting prices from orderbook snapshots: {e}")
            return None
    
    def _log_price_analysis(self, pair_name: str, prices: Dict[str, float]) -> None:
        """Log detailed price information for analysis, including fee adjustments."""
        arbitrage_calculation_log(f"📊 PRICE ANALYSIS | pair={pair_name}")
        
        # Show effective (fee-adjusted) prices
        arbitrage_calculation_log(f"   🏦 Kalshi YES (effective): bid={prices['k_yes_bid']:.3f}, ask={prices['k_yes_ask']:.3f}")
        arbitrage_calculation_log(f"   🏦 Kalshi NO  (effective): bid={prices['k_no_bid']:.3f}, ask={prices['k_no_ask']:.3f}")
        
        # Show raw Kalshi prices for comparison if available
        if 'k_yes_bid_raw' in prices:
            arbitrage_calculation_log(f"   📊 Kalshi YES (raw):      bid={prices['k_yes_bid_raw']:.3f}, ask={prices['k_yes_ask_raw']:.3f}")
            arbitrage_calculation_log(f"   📊 Kalshi NO  (raw):      bid={prices['k_no_bid_raw']:.3f}, ask={prices['k_no_ask_raw']:.3f}")
        
        # Polymarket prices (no fees applied)
        arbitrage_calculation_log(f"   🎯 Poly YES:              bid={prices['poly_yes_bid']:.3f}, ask={prices['poly_yes_ask']:.3f}")
        arbitrage_calculation_log(f"   🎯 Poly NO:               bid={prices['poly_no_bid']:.3f}, ask={prices['poly_no_ask']:.3f}")
    
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
                kalshi_snapshot, "yes", int(prices['k_yes_bid'] * 100),
                poly_no_snapshot, "ask", prices['poly_no_ask']
            )
            
            # Only create opportunity if execution size meets minimum threshold
            if execution_info.get('min_execution_size', 0.0) >= self.min_trade_size:
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
                arbitrage_calculation_log(f"🚨 OPPORTUNITY FOUND | pair={pair_name} | strategy=1 | spread={spreads['strategy_1']:.3f} | size={execution_info.get('min_execution_size', 0.0):.1f}")
            else:
                arbitrage_calculation_log(f"❌ OPPORTUNITY FILTERED | pair={pair_name} | strategy=1 | spread={spreads['strategy_1']:.3f} | size={execution_info.get('min_execution_size', 0.0):.1f} < min_trade_size={self.min_trade_size}")
        
        # Strategy 2: Sell Kalshi NO + Buy Polymarket YES
        if spreads['strategy_2'] >= self.min_spread_threshold:
            execution_info = self._calculate_execution_size(
                kalshi_snapshot, "no", int(prices['k_no_bid'] * 100),
                poly_yes_snapshot, "ask", prices['poly_yes_ask']
            )
            
            # Only create opportunity if execution size meets minimum threshold
            if execution_info.get('min_execution_size', 0.0) >= self.min_trade_size:
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
                arbitrage_calculation_log(f"🚨 OPPORTUNITY FOUND | pair={pair_name} | strategy=2 | spread={spreads['strategy_2']:.3f} | size={execution_info.get('min_execution_size', 0.0):.1f}")
            else:
                arbitrage_calculation_log(f"❌ OPPORTUNITY FILTERED | pair={pair_name} | strategy=2 | spread={spreads['strategy_2']:.3f} | size={execution_info.get('min_execution_size', 0.0):.1f} < min_trade_size={self.min_trade_size}")
        
        # Strategy 3: Sell Polymarket YES + Buy Kalshi NO
        if spreads['strategy_3'] >= self.min_spread_threshold:
            execution_info = self._calculate_execution_size(
                kalshi_snapshot, "no", int(prices['k_no_ask'] * 100),
                poly_yes_snapshot, "bid", prices['poly_yes_bid']
            )
            
            # Only create opportunity if execution size meets minimum threshold
            if execution_info.get('min_execution_size', 0.0) >= self.min_trade_size:
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
                arbitrage_calculation_log(f"🚨 OPPORTUNITY FOUND | pair={pair_name} | strategy=3 | spread={spreads['strategy_3']:.3f} | size={execution_info.get('min_execution_size', 0.0):.1f}")
            else:
                arbitrage_calculation_log(f"❌ OPPORTUNITY FILTERED | pair={pair_name} | strategy=3 | spread={spreads['strategy_3']:.3f} | size={execution_info.get('min_execution_size', 0.0):.1f} < min_trade_size={self.min_trade_size}")
        
        # Strategy 4: Sell Polymarket NO + Buy Kalshi YES
        if spreads['strategy_4'] >= self.min_spread_threshold:
            execution_info = self._calculate_execution_size(
                kalshi_snapshot, "yes", int(prices['k_yes_ask'] * 100),
                poly_no_snapshot, "bid", prices['poly_no_bid']
            )
            
            # Only create opportunity if execution size meets minimum threshold
            if execution_info.get('min_execution_size', 0.0) >= self.min_trade_size:
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
                arbitrage_calculation_log(f"🚨 OPPORTUNITY FOUND | pair={pair_name} | strategy=4 | spread={spreads['strategy_4']:.3f} | size={execution_info.get('min_execution_size', 0.0):.1f}")
            else:
                arbitrage_calculation_log(f"❌ OPPORTUNITY FILTERED | pair={pair_name} | strategy=4 | spread={spreads['strategy_4']:.3f} | size={execution_info.get('min_execution_size', 0.0):.1f} < min_trade_size={self.min_trade_size}")
        
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
                                kalshi_contract_type: str, kalshi_price: int,
                                poly_snapshot: PolymarketOrderbookSnapshot, poly_side: str, poly_price: float) -> Dict[str, Optional[float]]:
        """
        Calculate execution sizes for a specific arbitrage strategy.
        
        Args:
            kalshi_snapshot: Kalshi orderbook snapshot
            kalshi_contract_type: "yes" or "no" - which Kalshi contract we're trading
            kalshi_price: Kalshi price level in cents (1-99)
            poly_snapshot: Polymarket orderbook snapshot (YES or NO asset)
            poly_side: "bid" or "ask" - which side we're taking  
            poly_price: Polymarket price level as decimal (0.0-1.0)
            
        Returns:
            Dict with execution sizes and limiting factor
        """
        try:
            # Get Kalshi liquidity at specific contract type and price
            kalshi_size = self._get_kalshi_liquidity(kalshi_snapshot, kalshi_contract_type, kalshi_price)
            
            # Get Polymarket liquidity at specific side and price
            poly_size = self._get_polymarket_liquidity(poly_snapshot, poly_side, poly_price)
            
            # Return the limiting factor (minimum of the two)
            min_size = min(kalshi_size, poly_size) if kalshi_size > 0 and poly_size > 0 else 0.0
            
            logger.debug(f"💰 EXECUTION SIZE: kalshi_{kalshi_contract_type}={kalshi_size:.2f}, poly={poly_size:.2f}, min={min_size:.2f}")
            
            return {
                'kalshi_size': kalshi_size,
                'polymarket_size': poly_size,
                'min_execution_size': min_size,
                'limiting_factor': 'kalshi' if kalshi_size < poly_size else 'polymarket'
            }
            
        except Exception as e:
            logger.error(f"Error calculating execution size: {e}")
            return {
                'kalshi_size': 0.0,
                'polymarket_size': 0.0,
                'min_execution_size': 0.0,
                'limiting_factor': 'error'
            }
    
    def _get_kalshi_liquidity(self, snapshot: KalshiOrderbookSnapshot, contract_type: str, price: int) -> float:
        """Get Kalshi liquidity for specific contract type at price level."""
        if price is None:
            return 0.0
            
        # Choose YES or NO contracts based on what we're trading
        if contract_type.lower() == "yes":
            if price in snapshot.yes_contracts:
                return snapshot.yes_contracts[price].size_float
        elif contract_type.lower() == "no":
            if price in snapshot.no_contracts:
                return snapshot.no_contracts[price].size_float
                
        return 0.0
    
    def _get_polymarket_liquidity(self, snapshot: PolymarketOrderbookSnapshot, side: str, price: float) -> float:
        """Get Polymarket liquidity for specific side at price level."""
        if price is None:
            logger.info(f"[POLYMARKET ORDERBOOK] Price is None, returning 0.0")
            return 0.0
        
        # Use the cached best price strings directly (no float conversion issues)
        if side.lower() == "bid":
            if snapshot.best_bid_price and snapshot.best_bid_price in snapshot.bids:
                size = snapshot.bids[snapshot.best_bid_price].size_float
                #logger.info(f"[POLYMARKET ORDERBOOK] ✅ Using best bid: price={snapshot.best_bid_price}, size={size}")
                return size
            else:
                logger.error(f"[POLYMARKET ORDERBOOK] ❌ No best bid available - string best key cached is None (which is an error) or concurrency leak happened")
        elif side.lower() == "ask":
            if snapshot.best_ask_price and snapshot.best_ask_price in snapshot.asks:
                size = snapshot.asks[snapshot.best_ask_price].size_float
                logger.info(f"[POLYMARKET ORDERBOOK] ✅ Using best ask: price={snapshot.best_ask_price}, size={size}")
                return size
            else:
                logger.error(f"[POLYMARKET ORDERBOOK] ❌ No best ask available- string best key cached is None (which is an error) or concurrency leak happened")
                
        logger.info(f"[POLYMARKET ORDERBOOK] Returning 0.0 - no liquidity found")
        return 0.0