"""
Order Execution Coordinator

Coordinates simultaneous order execution across multiple platforms for arbitrage trades.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, Tuple
from datetime import datetime

from backend.master_manager.arbitrage_detector import ArbitrageOpportunity
from .executors.kalshi_executor import KalshiExecutor
from .executors.polymarket_executor import PolymarketExecutor

logger = logging.getLogger(__name__)

class OrderExecutor:
    """
    Coordinates order execution across multiple platforms for arbitrage trades.
    
    Features:
    - Simultaneous order placement across platforms
    - Execution size validation
    - Error handling and rollback
    - Execution result aggregation
    """
    
    def __init__(self, 
                 kalshi_client=None,
                 polymarket_proxy_config: Optional[Dict[str, Any]] = None):
        """
        Initialize order executor.
        
        Args:
            kalshi_client: Authenticated Kalshi client
            polymarket_proxy_config: Polymarket proxy configuration
        """
        self.kalshi_executor = KalshiExecutor(kalshi_client)
        self.polymarket_executor = PolymarketExecutor(polymarket_proxy_config)
        
        logger.info(f"OrderExecutor initialized - Kalshi: {'✓' if self.kalshi_executor.is_available else '✗'}, "
                   f"Polymarket: {'✓' if self.polymarket_executor.is_available else '✗'}")
    
    async def execute_arbitrage(self,
                              opportunity: ArbitrageOpportunity,
                              max_slippage: float = 0.01,
                              max_position_size: float = 1000.0) -> Dict[str, Any]:
        """
        Execute arbitrage trade across both platforms simultaneously.
        
        Args:
            opportunity: ArbitrageOpportunity containing execution details
            max_slippage: Maximum allowed slippage
            max_position_size: Maximum position size limit
        
        Returns:
            Execution result dictionary
        """
        try:
            logger.info(f"🚀 EXECUTING ARBITRAGE | pair={opportunity.market_pair} | "
                       f"direction={opportunity.direction} | size=${opportunity.execution_size:.1f}")
            
            # Validate execution size
            if opportunity.execution_size > max_position_size:
                return {
                    "success": False,
                    "error": f"Execution size {opportunity.execution_size:.1f} exceeds limit {max_position_size:.1f}",
                    "opportunity": opportunity
                }
            
            # Determine order parameters for each platform
            kalshi_params, polymarket_params = self._prepare_order_parameters(
                opportunity, max_slippage
            )
            
            if not kalshi_params or not polymarket_params:
                return {
                    "success": False,
                    "error": "Failed to prepare order parameters",
                    "opportunity": opportunity
                }
            
            # Execute orders simultaneously on both platforms
            execution_results = await self._execute_simultaneous_orders(
                kalshi_params, polymarket_params
            )
            
            kalshi_result = execution_results["kalshi"]
            polymarket_result = execution_results["polymarket"]
            
            # Check if both orders succeeded
            both_succeeded = kalshi_result["success"] and polymarket_result["success"]
            
            if both_succeeded:
                logger.info(f"✅ ARBITRAGE SUCCESS | pair={opportunity.market_pair} | "
                           f"kalshi_filled={kalshi_result.get('filled_quantity', 0)} | "
                           f"poly_filled={polymarket_result.get('filled_quantity', 0)}")
                
                return {
                    "success": True,
                    "opportunity": opportunity,
                    "kalshi_result": kalshi_result,
                    "polymarket_result": polymarket_result,
                    "execution_timestamp": datetime.now().isoformat(),
                    "total_value": self._calculate_total_execution_value(kalshi_result, polymarket_result)
                }
            else:
                # Handle partial execution - one platform failed
                logger.error(f"❌ PARTIAL EXECUTION | pair={opportunity.market_pair} | "
                            f"kalshi={'✓' if kalshi_result['success'] else '✗'} | "
                            f"poly={'✓' if polymarket_result['success'] else '✗'}")
                
                # TODO: Implement rollback/cleanup for successful orders
                await self._handle_partial_execution(kalshi_result, polymarket_result)
                
                return {
                    "success": False,
                    "error": "Partial execution - one platform failed",
                    "opportunity": opportunity,
                    "kalshi_result": kalshi_result,
                    "polymarket_result": polymarket_result,
                    "execution_timestamp": datetime.now().isoformat()
                }
        
        except Exception as e:
            logger.error(f"❌ ARBITRAGE EXECUTION ERROR | pair={opportunity.market_pair} | error={e}", exc_info=True)
            return {
                "success": False,
                "error": f"Execution exception: {str(e)}",
                "opportunity": opportunity,
                "execution_timestamp": datetime.now().isoformat()
            }
    
    def _prepare_order_parameters(self, 
                                 opportunity: ArbitrageOpportunity, 
                                 max_slippage: float) -> Tuple[Optional[Dict], Optional[Dict]]:
        """
        Prepare order parameters for both platforms based on arbitrage strategy.
        
        Args:
            opportunity: ArbitrageOpportunity containing execution details
            max_slippage: Maximum allowed slippage
        
        Returns:
            Tuple of (kalshi_params, polymarket_params)
        """
        try:
            execution_size = min(opportunity.execution_size, 1000.0)  # Safety limit
            
            # Parse the arbitrage strategy from opportunity
            if opportunity.direction == "kalshi_to_polymarket":
                # Sell on Kalshi, Buy on Polymarket
                if opportunity.side == "yes":
                    # Strategy 1: Sell Kalshi YES + Buy Polymarket NO
                    kalshi_params = {
                        "market_id": opportunity.kalshi_market_id,
                        "side": "yes",
                        "action": "sell",
                        "quantity": int(execution_size),
                        "price_cents": int(opportunity.kalshi_price * 100),
                        "max_slippage": max_slippage
                    }
                    polymarket_params = {
                        "asset_id": opportunity.polymarket_asset_id,
                        "side": "buy",
                        "quantity": execution_size,
                        "price": opportunity.polymarket_price,
                        "max_slippage": max_slippage
                    }
                else:
                    # Strategy 2: Sell Kalshi NO + Buy Polymarket YES
                    kalshi_params = {
                        "market_id": opportunity.kalshi_market_id,
                        "side": "no",
                        "action": "sell",
                        "quantity": int(execution_size),
                        "price_cents": int(opportunity.kalshi_price * 100),
                        "max_slippage": max_slippage
                    }
                    polymarket_params = {
                        "asset_id": opportunity.polymarket_asset_id,
                        "side": "buy",
                        "quantity": execution_size,
                        "price": opportunity.polymarket_price,
                        "max_slippage": max_slippage
                    }
            
            elif opportunity.direction == "polymarket_to_kalshi":
                # Sell on Polymarket, Buy on Kalshi
                if opportunity.side == "yes":
                    # Strategy 3: Sell Polymarket YES + Buy Kalshi NO
                    kalshi_params = {
                        "market_id": opportunity.kalshi_market_id,
                        "side": "no",
                        "action": "buy",
                        "quantity": int(execution_size),
                        "price_cents": int(opportunity.kalshi_price * 100),
                        "max_slippage": max_slippage
                    }
                    polymarket_params = {
                        "asset_id": opportunity.polymarket_asset_id,
                        "side": "sell",
                        "quantity": execution_size,
                        "price": opportunity.polymarket_price,
                        "max_slippage": max_slippage
                    }
                else:
                    # Strategy 4: Sell Polymarket NO + Buy Kalshi YES
                    kalshi_params = {
                        "market_id": opportunity.kalshi_market_id,
                        "side": "yes",
                        "action": "buy",
                        "quantity": int(execution_size),
                        "price_cents": int(opportunity.kalshi_price * 100),
                        "max_slippage": max_slippage
                    }
                    polymarket_params = {
                        "asset_id": opportunity.polymarket_asset_id,
                        "side": "sell",
                        "quantity": execution_size,
                        "price": opportunity.polymarket_price,
                        "max_slippage": max_slippage
                    }
            else:
                logger.error(f"Unknown arbitrage direction: {opportunity.direction}")
                return None, None
            
            logger.debug(f"Prepared orders - Kalshi: {kalshi_params}, Polymarket: {polymarket_params}")
            return kalshi_params, polymarket_params
        
        except Exception as e:
            logger.error(f"Error preparing order parameters: {e}", exc_info=True)
            return None, None
    
    async def _execute_simultaneous_orders(self, 
                                         kalshi_params: Dict[str, Any], 
                                         polymarket_params: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """
        Execute orders on both platforms simultaneously.
        
        Args:
            kalshi_params: Kalshi order parameters
            polymarket_params: Polymarket order parameters
        
        Returns:
            Dictionary with results from both platforms
        """
        try:
            # Execute both orders simultaneously
            kalshi_task = asyncio.create_task(
                self.kalshi_executor.place_order(**kalshi_params)
            )
            polymarket_task = asyncio.create_task(
                self.polymarket_executor.place_order(**polymarket_params)
            )
            
            # Wait for both orders to complete
            kalshi_result, polymarket_result = await asyncio.gather(
                kalshi_task, 
                polymarket_task, 
                return_exceptions=True
            )
            
            # Handle exceptions
            if isinstance(kalshi_result, Exception):
                kalshi_result = {
                    "success": False,
                    "platform": "kalshi",
                    "error": f"Exception: {str(kalshi_result)}"
                }
            
            if isinstance(polymarket_result, Exception):
                polymarket_result = {
                    "success": False,
                    "platform": "polymarket", 
                    "error": f"Exception: {str(polymarket_result)}"
                }
            
            return {
                "kalshi": kalshi_result,
                "polymarket": polymarket_result
            }
        
        except Exception as e:
            logger.error(f"Error in simultaneous order execution: {e}", exc_info=True)
            return {
                "kalshi": {
                    "success": False,
                    "platform": "kalshi",
                    "error": f"Execution error: {str(e)}"
                },
                "polymarket": {
                    "success": False,
                    "platform": "polymarket",
                    "error": f"Execution error: {str(e)}"
                }
            }
    
    async def _handle_partial_execution(self, 
                                      kalshi_result: Dict[str, Any], 
                                      polymarket_result: Dict[str, Any]):
        """
        Handle partial execution where one platform succeeded and one failed.
        
        This is a critical situation that requires immediate attention to prevent
        unhedged positions.
        
        Args:
            kalshi_result: Result from Kalshi execution
            polymarket_result: Result from Polymarket execution
        """
        logger.critical("🚨 PARTIAL EXECUTION DETECTED - IMMEDIATE ATTENTION REQUIRED")
        
        # Log the situation
        successful_platform = None
        failed_platform = None
        
        if kalshi_result["success"] and not polymarket_result["success"]:
            successful_platform = "kalshi"
            failed_platform = "polymarket"
        elif polymarket_result["success"] and not kalshi_result["success"]:
            successful_platform = "polymarket"
            failed_platform = "kalshi"
        
        logger.critical(f"   ✅ {successful_platform.upper()} order succeeded")
        logger.critical(f"   ❌ {failed_platform.upper()} order failed: {polymarket_result.get('error') if failed_platform == 'polymarket' else kalshi_result.get('error')}")
        
        # TODO: Implement cleanup strategies:
        # 1. Try to cancel the successful order if still pending
        # 2. Try to place a compensating order on the failed platform
        # 3. Alert human operators
        # 4. Record the partial execution for manual resolution
        
        logger.critical("🚨 MANUAL INTERVENTION REQUIRED - Unhedged position created")
    
    def _calculate_total_execution_value(self, 
                                       kalshi_result: Dict[str, Any], 
                                       polymarket_result: Dict[str, Any]) -> float:
        """
        Calculate total execution value from both platform results.
        
        Args:
            kalshi_result: Kalshi execution result
            polymarket_result: Polymarket execution result
        
        Returns:
            Total execution value in USD
        """
        try:
            kalshi_value = (kalshi_result.get("filled_quantity", 0) * 
                           kalshi_result.get("filled_price", 0))
            
            polymarket_value = (polymarket_result.get("filled_quantity", 0) * 
                              polymarket_result.get("filled_price", 0))
            
            return kalshi_value + polymarket_value
        
        except Exception as e:
            logger.warning(f"Error calculating execution value: {e}")
            return 0.0
    
    def get_executor_status(self) -> Dict[str, Any]:
        """Get status of both executors."""
        return {
            "kalshi": {
                "available": self.kalshi_executor.is_available,
                "status": "ready" if self.kalshi_executor.is_available else "not_configured"
            },
            "polymarket": {
                "available": self.polymarket_executor.is_available,
                "status": "ready" if self.polymarket_executor.is_available else "not_configured"
            }
        }